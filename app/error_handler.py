"""
Centralized error handling for IVT Kinetics Analyzer.

Phase 11.2: Error handling & user guidance

This module provides:
- User-friendly error messages for common exceptions
- Full traceback logging for debugging
- Error notification components for the UI
- Callback decorator for consistent error handling
"""
import functools
import traceback
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

import dash_mantine_components as dmc
from dash import html, no_update
from flask import Flask

from app.logging_config import get_logger, log_exception

logger = get_logger(__name__)


# Error categories with user-friendly messages
ERROR_MESSAGES: Dict[Type[Exception], str] = {
    ValueError: "Invalid input value. Please check your data and try again.",
    TypeError: "Data type mismatch. Please ensure the input format is correct.",
    KeyError: "Required field is missing. Please provide all necessary information.",
    FileNotFoundError: "The requested file could not be found.",
    PermissionError: "Permission denied. Please check file access rights.",
    ConnectionError: "Unable to connect. Please check your network connection.",
    TimeoutError: "The operation timed out. Please try again later.",
}

# Application-specific error messages
APP_ERROR_MESSAGES: Dict[str, str] = {
    "ProjectValidationError": "Project validation failed. Please check the project settings.",
    "LayoutValidationError": "Plate layout is invalid. Please review the layout configuration.",
    "PlateLayoutValidationError": "Plate layout validation failed. Please review the layout.",
    "AnalysisError": "Analysis could not be completed. The data may be insufficient.",
    "HierarchicalAnalysisError": "Hierarchical analysis failed. The data may be insufficient.",
    "FittingError": "Curve fitting failed. The data may not fit the selected model.",
    "QCError": "Quality control check failed. Please review the flagged wells.",
    "ComparisonError": "Comparison computation failed. Please check the data.",
    "ConstructValidationError": "Construct validation failed. Please check the construct settings.",
    "SmartPlannerError": "Experiment planning failed. Please check the project configuration.",
    "UploadValidationError": "Upload validation failed. Please check the file format.",
    "UploadProcessingError": "Upload processing failed. Please try again.",
    "BioTekParseError": "File parsing failed. Please check the file format.",
    "StatisticsServiceError": "Statistical analysis failed. Please check the data.",
    "PackageValidationError": "Package validation failed. Please check the package.",
    "PublicationPackageError": "Publication package generation failed.",
    "PowerAnalysisServiceError": "Power analysis failed. Please check the parameters.",
}


def get_user_friendly_message(exc: Exception) -> str:
    """
    Get a user-friendly error message for the given exception.

    Args:
        exc: The exception to get a message for

    Returns:
        A user-friendly error message string
    """
    # Check for application-specific errors first
    exc_name = type(exc).__name__
    if exc_name in APP_ERROR_MESSAGES:
        return APP_ERROR_MESSAGES[exc_name]

    # Check standard exception types
    for exc_type, message in ERROR_MESSAGES.items():
        if isinstance(exc, exc_type):
            return message

    # Default message for unknown errors
    return "An unexpected error occurred. Please try again or contact support."


def create_error_notification(
    message: str,
    title: str = "Error",
    details: Optional[str] = None,
    auto_close: Union[int, bool] = 10000,
) -> dmc.Notification:
    """
    Create an error notification component.

    Args:
        message: User-friendly error message
        title: Notification title
        details: Optional technical details (shown in smaller text)
        auto_close: Auto-close time in ms, or False to disable

    Returns:
        A Mantine Notification component
    """
    children = [message]
    if details:
        children.append(html.Br())
        children.append(
            dmc.Text(details, size="xs", c="dimmed", style={"marginTop": "4px"})
        )

    return dmc.Notification(
        title=title,
        message=html.Div(children),
        color="red",
        action="show",
        autoClose=auto_close,
    )


def create_error_alert(
    message: str,
    title: str = "Error",
    details: Optional[str] = None,
    variant: str = "light",
) -> dmc.Alert:
    """
    Create an error alert component for inline display.

    Args:
        message: User-friendly error message
        title: Alert title
        details: Optional technical details
        variant: Alert variant (light, filled, outline)

    Returns:
        A Mantine Alert component
    """
    children = [dmc.Text(message)]
    if details:
        children.append(
            dmc.Text(details, size="xs", c="dimmed", style={"marginTop": "8px"})
        )

    return dmc.Alert(
        title=title,
        color="red",
        variant=variant,
        children=children,
    )


def callback_error_handler(
    return_error_notification: bool = False,
    error_output_index: Optional[int] = None,
    default_return: Any = no_update,
    log_context: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Decorator for Dash callbacks to provide consistent error handling.

    Catches exceptions, logs the full traceback, and returns a user-friendly
    error message or notification.

    Args:
        return_error_notification: If True, returns dmc.Notification on error
        error_output_index: Index in return tuple where error should be placed
        default_return: Value to return for other outputs on error
        log_context: Additional context to include in error logs

    Returns:
        Decorated callback function

    Example:
        @app.callback(...)
        @callback_error_handler(return_error_notification=True)
        def my_callback(input_value):
            # If an exception occurs, it will be logged and a
            # user-friendly notification will be returned
            return process_data(input_value)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Log the full exception with traceback
                context = log_context or {}
                context.update({
                    "callback": func.__name__,
                    "args_count": len(args),
                })
                log_exception(
                    logger,
                    exc,
                    f"Error in callback {func.__name__}",
                    **context,
                )

                # Get user-friendly message
                user_message = get_user_friendly_message(exc)

                if return_error_notification:
                    notification = create_error_notification(
                        message=user_message,
                        details=f"Technical: {type(exc).__name__}",
                    )
                    return notification

                if error_output_index is not None:
                    # Return error at specific index
                    error_alert = create_error_alert(
                        message=user_message,
                        details=f"Error: {type(exc).__name__}",
                    )
                    # This requires knowing the number of outputs
                    # The caller should handle this case appropriately
                    return error_alert

                return default_return

        return wrapper
    return decorator


def handle_callback_error(
    exc: Exception,
    callback_name: str,
    return_type: str = "notification",
    **context,
) -> Union[dmc.Notification, dmc.Alert, Tuple[Any, ...]]:
    """
    Handle an error in a Dash callback manually.

    Use this function within a try/except block in callbacks that need
    custom error handling logic.

    Args:
        exc: The exception that occurred
        callback_name: Name of the callback for logging
        return_type: "notification", "alert", or "tuple"
        **context: Additional context to include in logs

    Returns:
        Error component based on return_type

    Example:
        @app.callback(...)
        def my_callback(data):
            try:
                result = process(data)
                return result, None
            except Exception as e:
                return no_update, handle_callback_error(
                    e, "my_callback", return_type="alert"
                )
    """
    # Log with full traceback
    log_exception(
        logger,
        exc,
        f"Error in callback {callback_name}",
        callback=callback_name,
        **context,
    )

    # Get user-friendly message
    user_message = get_user_friendly_message(exc)

    if return_type == "notification":
        return create_error_notification(
            message=user_message,
            details=f"Technical: {type(exc).__name__}",
        )
    elif return_type == "alert":
        return create_error_alert(
            message=user_message,
            details=f"Error: {type(exc).__name__}",
        )
    else:
        return (no_update,)


def register_error_handlers(app) -> None:
    """
    Register error handlers for the Flask server.

    Args:
        app: The Dash application instance
    """
    server = app.server

    @server.errorhandler(404)
    def not_found_error(error):
        logger.warning("Page not found", path=error.description if hasattr(error, 'description') else "unknown")
        return {"error": "Not found", "message": "The requested resource was not found."}, 404

    @server.errorhandler(500)
    def internal_error(error):
        logger.error(
            "Internal server error",
            error=str(error),
            traceback=traceback.format_exc(),
        )
        return {
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        }, 500

    @server.errorhandler(Exception)
    def unhandled_exception(error):
        logger.error(
            "Unhandled exception",
            error_type=type(error).__name__,
            error=str(error),
            traceback=traceback.format_exc(),
        )
        return {
            "error": "Server error",
            "message": get_user_friendly_message(error),
        }, 500

    logger.info("Error handlers registered")


class AppError(Exception):
    """Base exception for application-specific errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(message)


class ProjectValidationError(AppError):
    """Raised when project validation fails."""
    pass


class LayoutValidationError(AppError):
    """Raised when plate layout validation fails."""
    pass


class AnalysisError(AppError):
    """Raised when analysis fails."""
    pass


class FittingError(AppError):
    """Raised when curve fitting fails."""
    pass


class QCError(AppError):
    """Raised when quality control check fails."""
    pass
