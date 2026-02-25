"""
IVT Kinetics Analyzer - Application Factory

Single-tenant scientific web application for analyzing in-vitro transcription kinetics.
"""
from dash import Dash
import dash_mantine_components as dmc
from flask import Flask

from app.config import Config
from app.logging_config import configure_logging, get_logger


def _setup_logging(config_class):
    """Configure structured logging and return a logger instance."""
    is_development = getattr(config_class, 'DEBUG', False)
    configure_logging(
        log_level=getattr(config_class, 'LOG_LEVEL', 'INFO'),
        log_file=getattr(config_class, 'LOG_FILE', None),
        json_format=not is_development,
        development=is_development,
    )
    logger = get_logger(__name__)
    logger.info("Application initializing", config=config_class.__name__)
    return logger


def _validate_and_init(server, config_class):
    """Validate configuration and initialize Flask extensions."""
    from app.config import validate_config
    validate_config(config_class)

    from app.extensions import init_extensions
    init_extensions(server)


def _discover_plugins(config_class, logger):
    """Discover and load kinetic model plugins."""
    from app.analysis.kinetic_models import ModelRegistry
    plugin_dir = str(config_class.BASE_DIR / "plugins" / "kinetic_models")
    loaded_plugins = ModelRegistry.discover_plugins(plugin_dir)
    if loaded_plugins:
        logger.info("Loaded kinetic model plugins", plugins=loaded_plugins)
    plugin_errors = ModelRegistry.get_plugin_errors()
    if plugin_errors:
        for plugin, error in plugin_errors.items():
            logger.warning("Plugin load error", plugin=plugin, error=str(error))


def _register_middleware(server):
    """Register access gate and user identity middleware."""
    from app.api.access_gate import register_access_gate
    register_access_gate(server)

    from app.api.middleware import register_user_identity_middleware
    register_user_identity_middleware(server)


def _register_api_blueprints(server):
    """Import, register, and CSRF-exempt all API blueprints."""
    from app.api import (
        task_api, register_task_api,
        project_api, register_project_api,
        layout_bp, register_layout_api,
        calculator_bp, register_calculator_api,
        smart_planner_bp, register_smart_planner_api,
        openapi_bp, register_openapi,
        uploads_api, register_uploads_api,
        results_api, register_results_api,
        health_bp, register_health_api,
    )
    from app.api.cross_project_api import cross_project_api, register_cross_project_api
    from app.extensions import exempt_api_from_csrf

    # Register blueprints
    register_task_api(server)
    register_project_api(server)
    register_layout_api(server)
    register_calculator_api(server)
    register_smart_planner_api(server)
    register_cross_project_api(server)
    register_openapi(server)
    register_uploads_api(server)
    register_results_api(server)
    register_health_api(server)

    # Exempt API blueprints from CSRF (Phase 1 Security Fix)
    # API endpoints use X-Username header auth, not cookie-based sessions
    for blueprint in [task_api, project_api, layout_bp, calculator_bp,
                      smart_planner_bp, cross_project_api, uploads_api, results_api]:
        exempt_api_from_csrf(blueprint)


def _setup_dash_app(server):
    """Create Dash app, set layout, register callbacks and error handlers."""
    app = Dash(
        __name__,
        server=server,
        suppress_callback_exceptions=True,
        external_stylesheets=[
            dmc.styles.ALL,
            "https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Source+Sans+3:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap",
        ],
        title="IVT Kinetics Analyzer"
    )

    # Set main layout with user identity and browser compatibility
    from app.layouts import create_main_layout
    app.layout = create_main_layout()

    # Register callbacks
    from app.callbacks import register_callbacks
    register_callbacks(app)

    # Register error handlers (Phase 11.2)
    from app.error_handler import register_error_handlers
    register_error_handlers(app)

    return app


def create_app(config_class=Config):
    """Application factory for IVT Kinetics Analyzer."""

    # Create Flask server
    server = Flask(__name__)
    server.config.from_object(config_class)

    logger = _setup_logging(config_class)
    _validate_and_init(server, config_class)
    _discover_plugins(config_class, logger)
    _register_middleware(server)
    _register_api_blueprints(server)
    app = _setup_dash_app(server)

    logger.info("Application initialized successfully")

    return app


def create_worker_app(config_class=Config):
    """
    Lightweight Flask app for background worker tasks (Huey).

    Only initializes Flask + SQLAlchemy — no Dash, no callbacks, no
    blueprints, no middleware.  This avoids polluting the worker process
    with global side-effects that can break the Huey consumer after the
    first task completes.
    """
    server = Flask(__name__)
    server.config.from_object(config_class)

    from app.extensions import db
    from sqlalchemy import event

    db.init_app(server)

    # Enable WAL mode for SQLite (same as init_extensions)
    with server.app_context():
        @event.listens_for(db.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return server


__version__ = "0.1.0"
