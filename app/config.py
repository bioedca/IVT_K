"""
Configuration settings for IVT Kinetics Analyzer.
"""
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


class Config:
    """Base configuration."""

    # Application paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    PROJECTS_DIR = DATA_DIR / "projects"
    LOGS_DIR = BASE_DIR / "logs"

    # Database (SQLite with WAL mode for concurrent reads)
    DATABASE_PATH = BASE_DIR / "ivt_kinetics.db"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False,
        },
        "pool_pre_ping": True,
    }

    # Huey task queue (SQLite backend)
    HUEY_DATABASE_PATH = BASE_DIR / "huey.db"
    HUEY_IMMEDIATE = False  # Don't process in web process
    HUEY_WORKERS = 1  # Single worker for SQLite

    # Secret key for Flask sessions - NO DEFAULT VALUE
    # Must be set via environment variable in production
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Known insecure default keys that should never be used in production
    INSECURE_DEFAULT_KEYS = {
        "dev-key-change-in-production",
        "change-me",
        "secret",
        "your-secret-key-here",
    }

    @classmethod
    def validate(cls):
        """
        Validate configuration settings.

        Raises:
            ConfigurationError: If required settings are missing or invalid.
        """
        # Base config allows missing SECRET_KEY for backwards compatibility
        # Subclasses should override this for stricter validation
        pass

    @classmethod
    def is_secret_key_secure(cls) -> bool:
        """Check if the secret key is set and not a known insecure default."""
        if not cls.SECRET_KEY:
            return False
        return cls.SECRET_KEY.lower() not in cls.INSECURE_DEFAULT_KEYS

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = LOGS_DIR / "app.jsonl"

    # Browser requirements (desktop only)
    BROWSER_REQUIREMENTS = {
        "supported_browsers": [
            "Chrome 90+",
            "Firefox 88+",
            "Safari 14+",
            "Edge 90+"
        ],
        "minimum_viewport": {"width": 1024, "height": 768},
        "required_features": [
            "localStorage",
            "fetch",
            "CSS Grid",
            "ES6 modules"
        ],
        "offline_support": False,
        "mobile_support": False
    }

    # Analysis defaults
    DEFAULT_MODEL = "plateau"  # Default kinetic model
    MAX_CURVE_POINTS = 500  # Maximum points per curve
    MCMC_DEFAULT_SAMPLES = 2000
    MCMC_DEFAULT_CHAINS = 4
    MCMC_DEFAULT_TUNE = 1000

    # Background task settings
    PROGRESS_POLL_INTERVAL = 2000  # ms - UI polling interval

    # Request timeout settings (Phase 3.4)
    # These are timeouts for synchronous API operations
    REQUEST_TIMEOUT_DEFAULT = 30  # seconds - Default API request timeout
    REQUEST_TIMEOUT_ANALYSIS = 300  # seconds - Analysis operations (5 min)
    REQUEST_TIMEOUT_EXPORT = 120  # seconds - Data export operations (2 min)

    # Expected operation times (for documentation and client hints)
    OPERATION_TIMES = {
        "curve_fitting": {"typical": "10-30 seconds", "max": "2 minutes"},
        "mcmc_analysis": {"typical": "5-15 minutes", "max": "30 minutes"},
        "frequentist_analysis": {"typical": "30-60 seconds", "max": "5 minutes"},
        "data_export": {"typical": "5-30 seconds", "max": "2 minutes"},
        "file_parsing": {"typical": "1-5 seconds", "max": "30 seconds"},
    }

    # Access gate PIN (set via environment variable to enable)
    IVT_ACCESS_PIN = os.environ.get("IVT_ACCESS_PIN")

    # File upload limits
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload
    ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx"}


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = "DEBUG"

    # Development allows a fallback secret key with warning
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-DO-NOT-USE-IN-PRODUCTION")

    @classmethod
    def validate(cls):
        """Validate development configuration."""
        super().validate()
        if not cls.is_secret_key_secure():
            logger.warning(
                "Using insecure default SECRET_KEY. "
                "Set SECRET_KEY environment variable for production use."
            )


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = "INFO"

    # Production REQUIRES explicit SECRET_KEY from environment
    SECRET_KEY = os.environ.get("SECRET_KEY")

    @classmethod
    def validate(cls):
        """
        Validate production configuration.

        Raises:
            ConfigurationError: If required settings are missing.
        """
        super().validate()
        if not cls.SECRET_KEY:
            raise ConfigurationError(
                "SECRET_KEY environment variable is required in production. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not cls.is_secret_key_secure():
            raise ConfigurationError(
                "SECRET_KEY is set to a known insecure default value. "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE_PATH = Path(":memory:")
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    HUEY_IMMEDIATE = True  # Process tasks immediately in tests
    RATELIMIT_ENABLED = False  # Disable rate limiting in tests

    # Testing uses a fixed key for reproducibility
    SECRET_KEY = "test-secret-key-for-testing-only"

    @classmethod
    def validate(cls):
        """Testing config doesn't require validation."""
        pass


# Config mapping
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}


def get_config():
    """Get configuration based on environment."""
    env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, config["default"])


def validate_config(config_class):
    """
    Validate configuration at application startup.

    Args:
        config_class: The configuration class to validate.

    Raises:
        ConfigurationError: If validation fails.
    """
    config_class.validate()
