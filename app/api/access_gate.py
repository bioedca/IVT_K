"""
Server-side PIN access gate for IVT Kinetics Analyzer.

Intercepts ALL requests via Flask before_request.  When IVT_ACCESS_PIN is set,
unauthenticated requests get a self-contained HTML login page (no Dash/JS
dependencies) so the gate cannot be bypassed by skipping the frontend.

When IVT_ACCESS_PIN is not set the gate is completely transparent.
"""
import hashlib
import hmac
import html as html_escape
import logging

from flask import Blueprint, request, session, redirect, url_for, jsonify, current_app
from flask_wtf.csrf import generate_csrf

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_pin(pin: str) -> str:
    """Return hex SHA-256 of the PIN."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def _pin_matches(submitted: str, expected: str) -> bool:
    """Constant-time comparison of PIN hashes."""
    return hmac.compare_digest(
        _hash_pin(submitted),
        _hash_pin(expected),
    )


# ---------------------------------------------------------------------------
# Self-contained HTML login page (zero external dependencies)
# ---------------------------------------------------------------------------

_LOGIN_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IVT Kinetics Analyzer — Access</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f8f9fa; color: #212529;
  }}
  .card {{
    background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08);
    padding: 2.5rem 2rem; width: 100%; max-width: 380px;
  }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .25rem; text-align: center; }}
  .subtitle {{ text-align: center; color: #868e96; font-size: .85rem; margin-bottom: 1.5rem; }}
  label {{ display: block; font-weight: 600; font-size: .85rem; margin-bottom: .35rem; }}
  input[type="password"] {{
    width: 100%; padding: .6rem .75rem; border: 1px solid #ced4da; border-radius: 6px;
    font-size: 1rem; outline: none; transition: border-color .15s;
  }}
  input[type="password"]:focus {{ border-color: #228be6; box-shadow: 0 0 0 3px rgba(34,139,230,.15); }}
  .btn {{
    display: block; width: 100%; padding: .65rem; margin-top: 1rem;
    background: #228be6; color: #fff; border: none; border-radius: 6px;
    font-size: .95rem; font-weight: 600; cursor: pointer; transition: background .15s;
  }}
  .btn:hover {{ background: #1c7ed6; }}
  .error {{
    background: #fff5f5; border: 1px solid #ffc9c9; color: #c92a2a;
    border-radius: 6px; padding: .55rem .75rem; margin-bottom: 1rem;
    font-size: .85rem; text-align: center;
  }}
  .icon {{ text-align: center; margin-bottom: .75rem; font-size: 2rem; }}
</style>
</head>
<body>
<form class="card" method="POST" action="/auth/verify-pin">
  <input type="hidden" name="csrf_token" value="{csrf_token}">
  <div class="icon">&#128300;</div>
  <h1>IVT Kinetics Analyzer</h1>
  <p class="subtitle">Enter the lab PIN to continue</p>
  {error_html}
  <label for="pin">Access PIN</label>
  <input type="password" id="pin" name="pin" required autofocus
         autocomplete="current-password" inputmode="numeric" placeholder="Enter PIN">
  <button class="btn" type="submit">Unlock</button>
</form>
</body>
</html>
"""


def _render_login_page(error: str = "") -> str:
    error_html = f'<div class="error">{html_escape.escape(error)}</div>' if error else ""
    return _LOGIN_PAGE_HTML.format(error_html=error_html, csrf_token=generate_csrf())


# ---------------------------------------------------------------------------
# Auth blueprint routes
# ---------------------------------------------------------------------------

@auth_bp.route("/login")
def login_page():
    """Show the PIN login page."""
    return _render_login_page(), 200


@auth_bp.route("/verify-pin", methods=["POST"])
def verify_pin():
    """Verify submitted PIN and set session cookie."""
    from app.api.middleware import get_rate_limiter
    from app.models.access_log import AccessLog

    # Rate limit PIN attempts (5/min, stricter than default write limit)
    limiter = get_rate_limiter("analysis")  # Reuse 5/min analysis tier
    ip = request.remote_addr or "unknown"
    allowed, remaining, reset_seconds = limiter.is_allowed(ip)
    if not allowed:
        AccessLog.log_event("pin_attempt", False, ip_address=ip, details="rate limited")
        logger.warning("Rate limited PIN attempt from %s", ip)
        return _render_login_page(error="Too many attempts. Please wait and try again."), 429

    pin = request.form.get("pin", "")
    expected = current_app.config.get("IVT_ACCESS_PIN")
    ua = request.headers.get("User-Agent", "")

    if not expected:
        # Gate disabled — shouldn't reach here, but just in case
        return redirect("/")

    # Validate PIN length to prevent DoS via large inputs
    if len(pin) > 64:
        return _render_login_page(error="Invalid PIN format."), 403

    if _pin_matches(pin, expected):
        # Regenerate session to prevent fixation
        session.clear()
        session.permanent = True
        session["pin_verified"] = True
        AccessLog.log_event("login", True, ip_address=ip, user_agent=ua)
        logger.info("PIN login successful from %s", ip)
        return redirect("/")
    else:
        AccessLog.log_event("pin_attempt", False, ip_address=ip, user_agent=ua, details="wrong pin")
        logger.warning("Failed PIN attempt from %s", ip)
        return _render_login_page(error="Incorrect PIN. Please try again."), 403


@auth_bp.route("/status")
def auth_status():
    """Return JSON auth status — used by Dash client-side check."""
    pin_required = bool(current_app.config.get("IVT_ACCESS_PIN"))
    authenticated = bool(session.get("pin_verified"))
    return jsonify({
        "pin_required": pin_required,
        "authenticated": authenticated or not pin_required,
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the PIN session. CSRF-exempt since logout is rendered from Dash (no form token injection) and is low-risk."""
    from app.models.access_log import AccessLog

    ip = request.remote_addr or "unknown"
    ua = request.headers.get("User-Agent", "")
    AccessLog.log_event("logout", True, ip_address=ip, user_agent=ua)
    session.pop("pin_verified", None)
    return redirect("/auth/login")


# ---------------------------------------------------------------------------
# before_request gate
# ---------------------------------------------------------------------------

# Paths that are always allowed through (no session required)
_EXEMPT_PREFIXES = (
    "/auth/",
    "/api/health/",
)


def _check_pin_gate():
    """
    Flask before_request hook.

    - If IVT_ACCESS_PIN is not set → pass through (gate disabled).
    - If session["pin_verified"] → pass through.
    - If request path is exempt → pass through.
    - Otherwise block: JSON 401 for API/Dash requests, HTML 403 for browsers.
    """
    expected = current_app.config.get("IVT_ACCESS_PIN")
    if not expected:
        return None  # gate disabled

    if session.get("pin_verified"):
        return None  # already authenticated

    path = request.path

    # Exempt paths
    for prefix in _EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return None

    # Static assets for Dash (JS/CSS) — let these through so the login
    # page can't interfere with cached Dash assets on subsequent loads.
    # Actually, the login page is self-contained, but we block Dash assets
    # too to prevent any data leakage. Only /auth/* and /api/health/* pass.

    # Determine if this is a JSON/API request
    is_json_request = (
        path.startswith("/_dash")
        or path.startswith("/api/")
        or request.is_json
        or "application/json" in request.headers.get("Accept", "")
    )

    if is_json_request:
        return jsonify({"error": "Authentication required", "login_url": "/auth/login"}), 401

    # Browser HTML request — log and return login page
    try:
        from app.models.access_log import AccessLog
        ip = request.remote_addr or "unknown"
        AccessLog.log_event(
            "page_blocked", False, ip_address=ip,
            details=f"unauthenticated: {path}",
        )
    except Exception:
        pass  # Don't let logging failures break the gate
    return _render_login_page(), 403


def register_access_gate(server):
    """
    Register the PIN access gate on the Flask server.

    Must be called BEFORE user-identity middleware so the gate
    fires first in the before_request chain.
    """
    server.register_blueprint(auth_bp)

    # Exempt only the logout route from CSRF (rendered in Dash, no form token injection)
    # verify-pin keeps CSRF protection via the self-contained HTML login form
    from app.extensions import csrf
    csrf.exempt(logout)

    @server.before_request
    def pin_gate():
        return _check_pin_gate()

    pin_configured = bool(server.config.get("IVT_ACCESS_PIN"))
    logger.info("Access gate registered (enabled=%s)", pin_configured)
