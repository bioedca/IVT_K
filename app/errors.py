"""
Centralized exception hierarchy for IVT Kinetics Analyzer.

Phase 3: Service Layer Decomposition
Provides typed exceptions with user-safe messages and internal details.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """
    Base exception for all service-layer errors.

    Attributes:
        user_message: Safe message for client/API responses.
        detail: Internal detail logged server-side only.
        error_code: Machine-readable error code string.
    """

    error_code = "SERVICE_ERROR"

    def __init__(self, user_message: str, detail: Optional[str] = None):
        self.user_message = user_message
        self.detail = detail or user_message
        super().__init__(self.detail)


class FittingError(ServiceError):
    """Raised when curve fitting operations fail."""
    error_code = "FITTING_ERROR"


class ComparisonError(ServiceError):
    """Raised when comparison computation fails."""
    error_code = "COMPARISON_ERROR"


class HierarchicalAnalysisError(ServiceError):
    """Raised when hierarchical analysis fails."""
    error_code = "HIERARCHICAL_ERROR"


class ValidationError(ServiceError):
    """Raised when input validation fails."""
    error_code = "VALIDATION_ERROR"


class ExportError(ServiceError):
    """Raised when export operations fail."""
    error_code = "EXPORT_ERROR"
