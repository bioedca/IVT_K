"""
Transaction management utilities.

Phase 3: Service Layer Decomposition
Provides decorators for automatic rollback on exceptions.
"""
import functools
import logging

from app.extensions import db

logger = logging.getLogger(__name__)


def auto_rollback_on_error(func):
    """
    Decorator that rolls back db.session on exception.

    Catches any exception during the wrapped function, rolls back
    the database session, logs the error, and re-raises.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            db.session.rollback()
            logger.exception(
                f"Transaction rolled back in {func.__qualname__}"
            )
            raise
    return wrapper
