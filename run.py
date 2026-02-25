#!/usr/bin/env python
"""
IVT Kinetics Analyzer - Application Entry Point

Start the application with:
    python run.py                    # Development mode
    python run.py --production       # Production mode
    python run.py --host 0.0.0.0     # Custom host
    python run.py --port 8080        # Custom port

For production deployment with Gunicorn:
    gunicorn -w 1 -b 0.0.0.0:8050 wsgi:server
"""
import argparse
import os
import sys
from pathlib import Path

# Ensure the application root is in Python path
APP_ROOT = Path(__file__).parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Load .env file (must happen before config is imported)
from dotenv import load_dotenv
load_dotenv(APP_ROOT / ".env")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="IVT Kinetics Analyzer - Scientific web application for IVT kinetics analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                     Start in development mode (debug enabled)
  python run.py --production        Start in production mode
  python run.py --port 8080         Use custom port
  python run.py --host 0.0.0.0      Listen on all interfaces

Environment Variables:
  FLASK_ENV        Set to 'development', 'production', or 'testing'
  SECRET_KEY       Required for production (session security)
  IVT_HOST         Default host (overridden by --host)
  IVT_PORT         Default port (overridden by --port)
  DEBUG            Set to 'true' to enable debug mode
  LOG_LEVEL        Logging level (DEBUG, INFO, WARNING, ERROR)
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("IVT_HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for all interfaces)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("IVT_PORT", "8050")),
        help="Port to listen on (default: 8050)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.environ.get("DEBUG", "true").lower() == "true",
        help="Enable debug mode (auto-reload, detailed errors)",
    )

    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (disables debug, sets FLASK_ENV=production)",
    )

    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize the database before starting (creates tables if missing)",
    )

    return parser.parse_args()


def init_database(app):
    """Initialize database tables if they don't exist."""
    from app.extensions import db

    with app.server.app_context():
        # Import all models to ensure they're registered
        from app import models  # noqa: F401

        # Create tables
        db.create_all()

        # Verify WAL mode is enabled
        result = db.session.execute(db.text("PRAGMA journal_mode")).scalar()
        if result != "wal":
            db.session.execute(db.text("PRAGMA journal_mode=WAL"))
            db.session.commit()

        print(f"Database initialized (journal_mode={result})")


def ensure_directories(config):
    """Ensure required directories exist."""
    dirs_to_create = [
        config.DATA_DIR,
        config.PROJECTS_DIR,
        config.LOGS_DIR,
    ]

    for directory in dirs_to_create:
        directory.mkdir(parents=True, exist_ok=True)


def main():
    """Main entry point for the application."""
    # Silence Werkzeug logs
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    args = parse_args()

    # Set environment based on arguments
    if args.production:
        os.environ["FLASK_ENV"] = "production"
        args.debug = False
    elif "FLASK_ENV" not in os.environ:
        os.environ["FLASK_ENV"] = "development"

    # Import configuration
    from app.config import get_config
    config_class = get_config()

    # Validate production requirements
    if os.environ.get("FLASK_ENV") == "production":
        if not os.environ.get("SECRET_KEY"):
            print("ERROR: SECRET_KEY environment variable must be set in production mode")
            print("Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
            sys.exit(1)

    # Ensure required directories exist
    ensure_directories(config_class)

    # Create the application
    from app import create_app
    app = create_app(config_class)

    # Initialize database if requested
    if args.init_db:
        init_database(app)

    # Print startup information
    mode = "production" if args.production else "development"
    pin_enabled = bool(app.server.config.get("IVT_ACCESS_PIN"))
    print(f"\n{'=' * 60}")
    print(f"  IVT Kinetics Analyzer")
    print(f"  Mode: {mode}")
    print(f"  URL: http://{args.host}:{args.port}")
    if args.debug:
        print(f"  Debug: enabled (auto-reload active)")
    print(f"  PIN gate: {'enabled' if pin_enabled else 'disabled'}")
    print(f"{'=' * 60}\n")

    # Run the server
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
