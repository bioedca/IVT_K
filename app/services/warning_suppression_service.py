"""
Warning suppression service.

Phase 4: UX Enhancements - Warning Suppression Service

Provides:
- Warning suppression operations
- Suppression validation
- Suppression history retrieval
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.extensions import db
from app.models.warning_suppression import WarningSuppression, WarningType


# Minimum reason length for meaningful justification
MINIMUM_REASON_LENGTH = 10


class WarningSuppressionError(Exception):
    """Exception raised for warning suppression errors."""
    pass


def suppress_warning(
    plate_id: int,
    warning_type: WarningType,
    reason: str,
    suppressed_by: str,
    well_id: Optional[int] = None
) -> WarningSuppression:
    """
    Suppress a warning with required reason.

    Args:
        plate_id: ID of the plate this warning relates to.
        warning_type: Type of warning to suppress.
        reason: User-provided justification (minimum 10 characters).
        suppressed_by: Username of the person suppressing.
        well_id: Optional specific well ID.

    Returns:
        The created WarningSuppression record.

    Raises:
        ValueError: If reason or suppressed_by is invalid.
    """
    # Validate reason
    if not reason or not reason.strip():
        raise ValueError("Reason is required for warning suppression")

    if len(reason.strip()) < MINIMUM_REASON_LENGTH:
        raise ValueError(
            f"Reason must be at least {MINIMUM_REASON_LENGTH} characters"
        )

    # Validate user
    if not suppressed_by or not suppressed_by.strip():
        raise ValueError("Suppressed by user is required")

    # Create suppression record
    suppression = WarningSuppression(
        plate_id=plate_id,
        warning_type=warning_type,
        reason=reason.strip(),
        suppressed_by=suppressed_by.strip(),
        well_id=well_id
    )

    db.session.add(suppression)
    db.session.commit()

    return suppression


def get_suppressed_warnings(
    plate_id: int,
    warning_type: Optional[WarningType] = None
) -> List[WarningSuppression]:
    """
    Get all suppressed warnings for a plate.

    Args:
        plate_id: ID of the plate.
        warning_type: Optional filter by warning type.

    Returns:
        List of WarningSuppression records.
    """
    query = WarningSuppression.query.filter_by(plate_id=plate_id)

    if warning_type:
        query = query.filter_by(warning_type=warning_type)

    return query.order_by(WarningSuppression.suppressed_at.desc()).all()


def is_warning_suppressed(
    plate_id: int,
    warning_type: WarningType,
    well_id: Optional[int] = None
) -> bool:
    """
    Check if a specific warning is suppressed.

    Args:
        plate_id: ID of the plate.
        warning_type: Type of warning to check.
        well_id: Optional specific well ID.

    Returns:
        True if the warning is suppressed, False otherwise.
    """
    query = WarningSuppression.query.filter_by(
        plate_id=plate_id,
        warning_type=warning_type
    )

    if well_id:
        # Check for well-specific suppression or plate-wide suppression
        query = query.filter(
            (WarningSuppression.well_id == well_id) |
            (WarningSuppression.well_id.is_(None))
        )

    return query.first() is not None


def get_suppression_history(
    plate_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get suppression history for a plate.

    Args:
        plate_id: ID of the plate.
        limit: Maximum number of records to return.

    Returns:
        List of suppression dictionaries with all details.
    """
    suppressions = (
        WarningSuppression.query
        .filter_by(plate_id=plate_id)
        .order_by(WarningSuppression.suppressed_at.desc())
        .limit(limit)
        .all()
    )

    return [s.to_dict() for s in suppressions]


class WarningSuppressionService:
    """
    Service class for warning suppression operations.

    Provides static methods for managing warning suppressions.
    """

    @staticmethod
    def suppress(
        plate_id: int,
        warning_type: WarningType,
        reason: str,
        suppressed_by: str,
        well_id: Optional[int] = None
    ) -> WarningSuppression:
        """
        Suppress a warning.

        Args:
            plate_id: ID of the plate.
            warning_type: Type of warning to suppress.
            reason: User justification.
            suppressed_by: Username.
            well_id: Optional well ID.

        Returns:
            Created suppression record.
        """
        return suppress_warning(
            plate_id=plate_id,
            warning_type=warning_type,
            reason=reason,
            suppressed_by=suppressed_by,
            well_id=well_id
        )

    @staticmethod
    def unsuppress(
        suppression_id: int,
        unsuppressed_by: str
    ) -> bool:
        """
        Remove a warning suppression.

        Args:
            suppression_id: ID of the suppression to remove.
            unsuppressed_by: Username of the person removing.

        Returns:
            True if successfully removed, False if not found.
        """
        suppression = WarningSuppression.query.get(suppression_id)

        if not suppression:
            return False

        db.session.delete(suppression)
        db.session.commit()

        return True

    @staticmethod
    def get_suppressions(
        plate_id: int,
        warning_type: Optional[WarningType] = None
    ) -> List[WarningSuppression]:
        """
        Get suppressions for a plate.

        Args:
            plate_id: ID of the plate.
            warning_type: Optional filter by type.

        Returns:
            List of suppression records.
        """
        return get_suppressed_warnings(plate_id, warning_type)

    @staticmethod
    def is_suppressed(
        plate_id: int,
        warning_type: WarningType,
        well_id: Optional[int] = None
    ) -> bool:
        """
        Check if warning is suppressed.

        Args:
            plate_id: ID of the plate.
            warning_type: Type of warning.
            well_id: Optional well ID.

        Returns:
            True if suppressed.
        """
        return is_warning_suppressed(plate_id, warning_type, well_id)
