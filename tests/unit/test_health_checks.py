"""Tests for health check API (app.api.health_api) individual functions and endpoints."""
import pytest
from unittest.mock import patch, MagicMock


class TestCheckDatabase:
    """Tests for check_database() function."""

    def test_healthy_db(self, app, db_session):
        from app.api.health_api import check_database
        result = check_database()
        assert result["status"] == "healthy"

    def test_response_time_numeric(self, app, db_session):
        from app.api.health_api import check_database
        result = check_database()
        assert isinstance(result["response_time_ms"], float)
        assert result["response_time_ms"] >= 0

    def test_db_error_returns_unhealthy(self, app):
        from app.api.health_api import check_database
        with app.server.app_context():
            with patch("app.api.health_api.db.session") as mock_session:
                mock_session.execute.side_effect = Exception("Connection refused")
                result = check_database()
                assert result["status"] == "unhealthy"
                assert "error" in result


class TestCheckHueyWorker:
    """Tests for check_huey_worker() function."""

    def test_db_not_found_returns_unknown(self, app):
        from app.api.health_api import check_huey_worker
        with app.server.app_context():
            with patch("os.path.exists", return_value=False):
                result = check_huey_worker()
                assert result["status"] == "unknown"

    def test_accessible_returns_healthy(self, app):
        from app.api.health_api import check_huey_worker
        with app.server.app_context():
            with patch("os.path.exists", return_value=True), \
                 patch("os.access", return_value=True), \
                 patch("app.api.health_api.huey", create=True) as mock_huey:
                # Mock the import
                mock_module = MagicMock()
                mock_module.huey.pending_count.return_value = 0
                with patch.dict("sys.modules", {"app.tasks.huey_config": mock_module}):
                    result = check_huey_worker()
                    assert result["status"] in ("healthy", "degraded")

    def test_not_accessible_returns_unhealthy(self, app):
        from app.api.health_api import check_huey_worker
        with app.server.app_context():
            with patch("os.path.exists", return_value=True), \
                 patch("os.access", return_value=False):
                result = check_huey_worker()
                assert result["status"] == "unhealthy"


class TestCheckDiskSpace:
    """Tests for check_disk_space() function."""

    def _mock_statvfs(self, free_gb, total_gb):
        """Create a mock statvfs result with desired free/total GB."""
        mock = MagicMock()
        block_size = 4096
        total_blocks = int(total_gb * (1024 ** 3) / block_size)
        free_blocks = int(free_gb * (1024 ** 3) / block_size)
        mock.f_frsize = block_size
        mock.f_blocks = total_blocks
        mock.f_bavail = free_blocks
        return mock

    def test_healthy_plenty_of_space(self, app):
        from app.api.health_api import check_disk_space
        with app.server.app_context():
            with patch("os.path.exists", return_value=True), \
                 patch("os.statvfs", return_value=self._mock_statvfs(50, 100)):
                result = check_disk_space()
                assert result["status"] == "healthy"

    def test_degraded(self, app):
        from app.api.health_api import check_disk_space
        with app.server.app_context():
            # 3 GB free out of 30 GB total → 90% used (>85% but ≤95%), free >1 GB → degraded
            with patch("os.path.exists", return_value=True), \
                 patch("os.statvfs", return_value=self._mock_statvfs(3, 30)):
                result = check_disk_space()
                assert result["status"] == "degraded"

    def test_unhealthy(self, app):
        from app.api.health_api import check_disk_space
        with app.server.app_context():
            with patch("os.path.exists", return_value=True), \
                 patch("os.statvfs", return_value=self._mock_statvfs(0.5, 100)):
                result = check_disk_space()
                assert result["status"] == "unhealthy"

    def test_exception_returns_unknown(self, app):
        from app.api.health_api import check_disk_space
        with app.server.app_context():
            with patch("os.path.exists", return_value=True), \
                 patch("os.statvfs", side_effect=OSError("Permission denied")):
                result = check_disk_space()
                assert result["status"] == "unknown"


class TestHealthEndpointAggregation:
    """Tests for the /api/health endpoint aggregation logic."""

    def test_all_healthy_returns_200(self, app, db_session):
        with app.server.test_client() as c:
            with patch("app.api.health_api.check_huey_worker", return_value={"status": "healthy"}), \
                 patch("app.api.health_api.check_disk_space", return_value={"status": "healthy"}):
                resp = c.get("/api/health")
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["status"] == "healthy"

    def test_any_unhealthy_returns_503(self, app, db_session):
        with app.server.test_client() as c:
            with patch("app.api.health_api.check_huey_worker", return_value={"status": "unhealthy", "error": "down"}), \
                 patch("app.api.health_api.check_disk_space", return_value={"status": "healthy"}):
                resp = c.get("/api/health")
                assert resp.status_code == 503
                data = resp.get_json()
                assert data["status"] == "unhealthy"

    def test_degraded_returns_200(self, app, db_session):
        with app.server.test_client() as c:
            with patch("app.api.health_api.check_huey_worker", return_value={"status": "degraded"}), \
                 patch("app.api.health_api.check_disk_space", return_value={"status": "healthy"}):
                resp = c.get("/api/health")
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["status"] in ("degraded", "healthy")

    def test_version_field_present(self, app, db_session):
        with app.server.test_client() as c:
            with patch("app.api.health_api.check_huey_worker", return_value={"status": "healthy"}), \
                 patch("app.api.health_api.check_disk_space", return_value={"status": "healthy"}):
                resp = c.get("/api/health")
                data = resp.get_json()
                assert "version" in data
