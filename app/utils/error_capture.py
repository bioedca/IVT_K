"""
Exception capture utilities.

Phase 3: Service Layer Decomposition
Provides helpers for logging exceptions to model fields and logger.
"""
import logging
import traceback

logger = logging.getLogger(__name__)


def capture_exception_to_model(
    exception,
    model,
    message_field='error_message',
    traceback_field='error_traceback',
):
    """
    Log exception details to model fields and to the logger.

    Sets the specified fields on the model instance with the
    exception message and traceback string. Also logs via logger.error().

    Args:
        exception: The caught exception.
        model: SQLAlchemy model instance to update.
        message_field: Name of the field for the error message.
        traceback_field: Name of the field for the traceback string.
    """
    msg = str(exception)
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    if hasattr(model, message_field):
        setattr(model, message_field, msg[:2000])  # Truncate for DB
    if hasattr(model, traceback_field):
        setattr(model, traceback_field, tb[:10000])  # Truncate for DB

    logger.error(
        f"Exception captured on {model.__class__.__name__}: {msg}",
        exc_info=exception,
    )
