"""
Warning suppression model for suppressible warnings.

Phase 4: UX Enhancements - Warning Suppression Model

Provides:
- WarningSuppression database model
- WarningType enumeration
- Suppression tracking with reason and user
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class WarningType(str, PyEnum):
    """Types of suppressible warnings."""
    INCOMPLETE_PLATE = "incomplete_plate"
    TEMPERATURE_DEVIATION = "temperature_deviation"
    MISSING_NEGATIVE_CONTROL = "missing_negative_control"
    LOW_REPLICATE_COUNT = "low_replicate_count"
    HIGH_CV = "high_cv"
    OUTLIER_DETECTED = "outlier_detected"
    EDGE_EFFECT = "edge_effect"
    MISSING_WELLS = "missing_wells"


class WarningSuppression(db.Model, TimestampMixin):
    """
    Model for tracking suppressed warnings.

    When a user suppresses a warning (e.g., incomplete plate warning),
    this record stores the suppression details for audit purposes.

    Attributes:
        id: Primary key.
        plate_id: Foreign key to the plate this warning relates to.
        well_id: Optional foreign key to a specific well.
        warning_type: Type of warning being suppressed.
        reason: User-provided justification for suppression.
        suppressed_by: Username of the person who suppressed the warning.
        suppressed_at: Timestamp when the warning was suppressed.
    """
    __tablename__ = "warning_suppressions"

    # Primary key
    id = Column(Integer, primary_key=True)

    # Foreign keys
    plate_id = Column(
        Integer,
        ForeignKey("plates.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Optional well-specific suppression
    well_id = Column(
        Integer,
        ForeignKey("wells.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Warning details
    warning_type = Column(
        Enum(WarningType),
        nullable=False
    )

    # User justification (required, minimum length enforced at service level)
    reason = Column(
        Text,
        nullable=False
    )

    # Audit fields
    suppressed_by = Column(
        String(255),
        nullable=False
    )

    suppressed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    # Relationships (using backref to auto-create reverse relationship)
    plate = relationship("Plate", backref="warning_suppressions")
    well = relationship("Well", backref="warning_suppressions")

    def __init__(
        self,
        plate_id: int,
        warning_type: WarningType,
        reason: str,
        suppressed_by: str,
        well_id: Optional[int] = None,
        suppressed_at: Optional[datetime] = None
    ):
        """
        Create a new warning suppression record.

        Args:
            plate_id: ID of the plate this warning relates to.
            warning_type: Type of warning being suppressed.
            reason: User-provided justification.
            suppressed_by: Username of the person suppressing.
            well_id: Optional specific well ID.
            suppressed_at: Optional timestamp (defaults to now).
        """
        self.plate_id = plate_id
        self.well_id = well_id
        self.warning_type = warning_type
        self.reason = reason
        self.suppressed_by = suppressed_by
        self.suppressed_at = suppressed_at or datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<WarningSuppression id={self.id} plate={self.plate_id} [{self.warning_type.value}]>"

    def to_dict(self) -> dict:
        """
        Convert suppression to dictionary.

        Returns:
            Dictionary representation of the suppression.
        """
        return {
            "id": self.id,
            "plate_id": self.plate_id,
            "well_id": self.well_id,
            "warning_type": self.warning_type.value,
            "reason": self.reason,
            "suppressed_by": self.suppressed_by,
            "suppressed_at": self.suppressed_at.isoformat() if self.suppressed_at else None
        }
