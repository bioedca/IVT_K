"""
Structured JSON logging configuration for IVT Kinetics Analyzer.

Phase 11.1: Structured JSON logging (structlog)

This module provides structured logging with JSON output for production debugging
and monitoring. Logs are written to both the console and a JSON log file.

Usage:
    from app.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing started", project_id=123, user="admin")
"""
import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
from structlog.types import Processor


def configure_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    json_format: bool = True,
    development: bool = False,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to JSON log file (optional)
        json_format: Output logs in JSON format (True for production)
        development: Enable development-friendly console output
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Shared processors for all loggers
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if development:
        # Development: colorful console output
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Console formatter for development
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )
    else:
        # Production: JSON output
        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # JSON formatter for production
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # File handler for JSON logs
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # JSON formatter for file output
        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    for lib in [
        "werkzeug",                        # Flask dev server
        "urllib3",                         # HTTP client
        "dash",                            # Dash framework
        "sqlalchemy.engine",              # SQL echo
        "watchdog",                        # File watcher
    ]:
        logging.getLogger(lib).setLevel(logging.ERROR)

    for lib in [
        "numba", "matplotlib", "arviz",   # Scientific computing
        "weasyprint",                      # PDF rendering
        "fontTools", "cssselect2",         # WeasyPrint dependencies
        "html5lib", "PIL",                 # HTML parsing, image processing
        "kaleido",                         # Plotly static image export
        "choreographer", "browser_proc",   # Kaleido's headless Chrome
        "asyncio",                         # Event loop internals
    ]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for the given module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog bound logger

    Example:
        logger = get_logger(__name__)
        logger.info("User action", user_id=42, action="login")
    """
    return structlog.get_logger(name)


def log_exception(
    logger: structlog.stdlib.BoundLogger,
    exc: Exception,
    message: str = "An error occurred",
    **context,
) -> None:
    """
    Log an exception with full traceback and context.

    Args:
        logger: The structlog logger instance
        exc: The exception to log
        message: Human-readable error message
        **context: Additional context to include in the log

    Example:
        try:
            process_data()
        except Exception as e:
            log_exception(logger, e, "Data processing failed", project_id=123)
    """
    logger.exception(
        message,
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        **context,
    )


def bind_request_context(**context) -> None:
    """
    Bind context variables that will be included in all subsequent logs.

    Useful for adding request-specific context like user ID or project ID.

    Args:
        **context: Key-value pairs to bind to the logging context

    Example:
        bind_request_context(user_id=42, project_id=123)
        logger.info("Starting analysis")  # Will include user_id and project_id
    """
    structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """
    Clear all bound context variables.

    Call this at the end of a request to prevent context leaking.
    """
    structlog.contextvars.clear_contextvars()
