"""
Flask/Dash extensions initialization.

Phase 1 Security: Added CSRF protection via Flask-WTF.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event

# SQLAlchemy instance
db = SQLAlchemy()

# CSRF Protection instance (Phase 1 Security Fix)
csrf = CSRFProtect()


def init_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)

    # Initialize CSRF protection (Phase 1 Security Fix)
    # CSRF is primarily needed for browser-based form submissions
    csrf.init_app(app)

    # Exempt Dash internal routes from CSRF protection
    # Dash uses POST requests for callbacks but handles its own security model
    _exempt_dash_routes_from_csrf(app)

    # Enable WAL mode for SQLite after connection
    with app.app_context():
        _enable_wal_mode(db.engine)


def _exempt_dash_routes_from_csrf(app):
    """
    Exempt Dash internal routes from CSRF protection.

    Dash's internal routes (/_dash-update-component, /_dash-layout, etc.)
    use POST requests for callbacks but don't use traditional form submissions.
    Dash has its own request validation and doesn't rely on cookie-based CSRF tokens.
    """
    from flask import request

    # Wrap the protect method to skip Dash routes
    original_protect = csrf.protect

    def custom_protect():
        # Skip CSRF check for Dash internal routes
        if request.path.startswith('/_dash'):
            return
        return original_protect()

    csrf.protect = custom_protect


def exempt_api_from_csrf(blueprint):
    """
    Exempt a blueprint from CSRF protection.

    Phase 1 Security Fix: API endpoints use X-Username header auth,
    not cookie-based sessions, so CSRF protection is not applicable.

    Args:
        blueprint: Flask Blueprint to exempt
    """
    csrf.exempt(blueprint)


def _enable_wal_mode(engine):
    """Enable Write-Ahead Logging mode for SQLite."""
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrent read performance
        cursor.execute("PRAGMA journal_mode=WAL")
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
