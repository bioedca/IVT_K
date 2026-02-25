"""Tests for the PIN access gate (app.api.access_gate)."""
import pytest

from app.api.access_gate import _hash_pin, _pin_matches


class TestPinHashing:
    """Tests for _hash_pin()."""

    def test_hex_output(self):
        """Hash returns a hex string of correct length (SHA-256 = 64 hex chars)."""
        h = _hash_pin("1234")
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # Validates it's hex

    def test_deterministic(self):
        """Same PIN always produces the same hash."""
        assert _hash_pin("secret") == _hash_pin("secret")

    def test_different_pins_differ(self):
        assert _hash_pin("1234") != _hash_pin("5678")


class TestPinMatches:
    """Tests for _pin_matches() constant-time comparison."""

    def test_correct_match(self):
        assert _pin_matches("mypin", "mypin") is True

    def test_wrong_match(self):
        assert _pin_matches("wrong", "correct") is False


class TestAccessGateDisabled:
    """Tests when IVT_ACCESS_PIN is not set (gate disabled)."""

    @pytest.fixture(autouse=True)
    def _setup(self, app):
        self.app = app
        self.server = app.server
        # Ensure PIN is not set
        self.server.config.pop("IVT_ACCESS_PIN", None)

    def test_requests_pass_through(self):
        with self.server.test_client() as c:
            resp = c.get("/api/health")
            assert resp.status_code == 200

    def test_auth_status_no_pin_required(self):
        with self.server.test_client() as c:
            resp = c.get("/auth/status")
            data = resp.get_json()
            assert data["pin_required"] is False
            assert data["authenticated"] is True

    def test_login_page_accessible(self):
        with self.server.test_client() as c:
            resp = c.get("/auth/login")
            assert resp.status_code == 200


class TestAccessGateEnabled:
    """Tests when IVT_ACCESS_PIN is set (gate enabled)."""

    PIN = "testpin123"

    @pytest.fixture(autouse=True)
    def _setup(self, app, db_session):
        self.app = app
        self.server = app.server
        self.server.config["IVT_ACCESS_PIN"] = self.PIN
        yield
        self.server.config.pop("IVT_ACCESS_PIN", None)

    def test_unauthenticated_browser_gets_403(self):
        with self.server.test_client() as c:
            resp = c.get("/", headers={"Accept": "text/html"})
            assert resp.status_code == 403
            assert b"Access PIN" in resp.data or b"pin" in resp.data.lower()

    def test_unauthenticated_api_gets_401_json(self):
        with self.server.test_client() as c:
            resp = c.get("/api/projects", headers={"Accept": "application/json"})
            assert resp.status_code == 401
            data = resp.get_json()
            assert "error" in data
            assert "login_url" in data

    def test_exempt_paths_bypass_gate(self):
        with self.server.test_client() as c:
            # /auth/* is exempt
            resp = c.get("/auth/login")
            assert resp.status_code == 200
            # /api/health/* sub-paths are exempt
            resp = c.get("/api/health/live")
            assert resp.status_code == 200

    def test_correct_pin_sets_session(self):
        with self.server.test_client() as c:
            # Get the CSRF token from the login page
            login_resp = c.get("/auth/login")
            html = login_resp.data.decode()
            # Extract CSRF token from hidden field
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            assert match, "CSRF token not found in login page"
            csrf_token = match.group(1)

            resp = c.post(
                "/auth/verify-pin",
                data={"pin": self.PIN, "csrf_token": csrf_token},
                follow_redirects=False,
            )
            assert resp.status_code == 302
            assert resp.headers.get("Location", "").endswith("/")

            # Now authenticated requests should pass
            resp = c.get("/api/health")
            assert resp.status_code == 200

    def test_wrong_pin_returns_403(self):
        with self.server.test_client() as c:
            login_resp = c.get("/auth/login")
            html = login_resp.data.decode()
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            assert match, "CSRF token not found in login page"
            csrf_token = match.group(1)

            resp = c.post(
                "/auth/verify-pin",
                data={"pin": "wrongpin", "csrf_token": csrf_token},
            )
            assert resp.status_code == 403

    def test_too_long_pin_returns_403(self):
        with self.server.test_client() as c:
            login_resp = c.get("/auth/login")
            html = login_resp.data.decode()
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            assert match, "CSRF token not found in login page"
            csrf_token = match.group(1)

            resp = c.post(
                "/auth/verify-pin",
                data={"pin": "x" * 100, "csrf_token": csrf_token},
            )
            # 403 for invalid format, or 429 if rate limited from prior tests
            assert resp.status_code in (403, 429)

    def test_authenticated_session_passes(self):
        with self.server.test_client() as c:
            # Set session directly
            with c.session_transaction() as sess:
                sess["pin_verified"] = True
            resp = c.get("/api/health")
            assert resp.status_code == 200

    def test_logout_clears_session(self):
        with self.server.test_client() as c:
            # Authenticate first
            with c.session_transaction() as sess:
                sess["pin_verified"] = True
            # Logout
            resp = c.post("/auth/logout", follow_redirects=False)
            assert resp.status_code == 302
            # Session should be cleared
            resp = c.get("/", headers={"Accept": "text/html"})
            assert resp.status_code == 403

    def test_auth_status_unauthenticated(self):
        with self.server.test_client() as c:
            resp = c.get("/auth/status")
            data = resp.get_json()
            assert data["pin_required"] is True
            assert data["authenticated"] is False

    def test_auth_status_authenticated(self):
        with self.server.test_client() as c:
            with c.session_transaction() as sess:
                sess["pin_verified"] = True
            resp = c.get("/auth/status")
            data = resp.get_json()
            assert data["pin_required"] is True
            assert data["authenticated"] is True


class TestLoginPageRendering:
    """Tests for the login page HTML."""

    @pytest.fixture(autouse=True)
    def _setup(self, app):
        self.server = app.server

    def test_contains_form_and_input(self):
        with self.server.test_client() as c:
            resp = c.get("/auth/login")
            html = resp.data.decode()
            assert '<form' in html
            assert 'type="password"' in html
            assert 'name="pin"' in html

    def test_csrf_token_present(self):
        with self.server.test_client() as c:
            resp = c.get("/auth/login")
            html = resp.data.decode()
            assert 'csrf_token' in html
