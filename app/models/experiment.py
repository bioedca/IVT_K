"""Experiment models - sessions, plates, reactions, wells, and raw data."""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Date,
    ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.base import TimestampMixin
from app.models.plate_layout import WellType


class FitStatus(enum.Enum):
    """Curve fit status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class QCStatus(enum.Enum):
    """QC review status for experimental sessions."""
    PENDING = "pending"          # Not yet reviewed
    IN_REVIEW = "in_review"      # Currently being reviewed
    APPROVED = "approved"        # QC passed, ready for analysis
    REJECTED = "rejected"        # QC failed, needs attention


class ExperimentalSession(db.Model, TimestampMixin):
    """
    An experimental session grouping multiple plates.

    Represents a batch of experiments performed on the same day.
    """
    __tablename__ = "experimental_sessions"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    date = Column(Date, nullable=False)
    batch_identifier = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)

    # QC Review fields
    qc_status = Column(Enum(QCStatus), default=QCStatus.PENDING, nullable=False)
    qc_reviewed_at = Column(DateTime, nullable=True)
    qc_reviewed_by = Column(String(100), nullable=True)
    qc_notes = Column(Text, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="sessions")
    plates = relationship("Plate", back_populates="session", cascade="all, delete-orphan")
    reaction_setups = relationship("ReactionSetup", back_populates="session")

    def __repr__(self):
        return f"<ExperimentalSession id={self.id} {self.batch_identifier} ({self.date})>"

    @property
    def is_qc_approved(self) -> bool:
        """Check if QC has been approved."""
        return self.qc_status == QCStatus.APPROVED


class Plate(db.Model, TimestampMixin):
    """
    A physical plate with uploaded data.

    Links an experimental session with a plate layout and contains wells.
    """
    __tablename__ = "plates"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("experimental_sessions.id"), nullable=False)
    layout_id = Column(Integer, ForeignKey("plate_layouts.id"), nullable=False)
    plate_number = Column(Integer, nullable=False)
    raw_file_path = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ExperimentalSession", back_populates="plates")
    layout = relationship("PlateLayout", back_populates="plates")
    wells = relationship("Well", back_populates="plate", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="plate", cascade="all, delete-orphan")
    background_estimates = relationship("BackgroundEstimate", back_populates="plate", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Plate id={self.id} num={self.plate_number} session={self.session_id}>"


class Reaction(db.Model):
    """
    A single IVT reaction that may span multiple wells (split wells).

    For standard setups, one reaction = one well. For split-well designs,
    one reaction spans multiple wells.
    """
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True)
    plate_id = Column(Integer, ForeignKey("plates.id"), nullable=False)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    replicate_number = Column(Integer, nullable=False)
    total_volume_ul = Column(Float, nullable=False)
    wells_count = Column(Integer, default=1)

    # Relationships
    plate = relationship("Plate", back_populates="reactions")
    construct = relationship("Construct")
    wells = relationship("Well", back_populates="reaction")

    def __repr__(self):
        return f"<Reaction id={self.id} construct={self.construct_id} rep={self.replicate_number}>"


class Well(db.Model):
    """
    An individual well on a plate.

    Contains raw data points and links to fit results.
    """
    __tablename__ = "wells"

    id = Column(Integer, primary_key=True)
    plate_id = Column(Integer, ForeignKey("plates.id"), nullable=False, index=True)
    reaction_id = Column(Integer, ForeignKey("reactions.id"), nullable=True)
    position = Column(String(10), nullable=False)  # e.g., "A1"
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=True, index=True)
    well_type = Column(Enum(WellType), default=WellType.EMPTY, nullable=False)
    
    # Hierarchical Model Fields
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    paired_with_id = Column(Integer, ForeignKey("wells.id"), nullable=True)
    
    volume_ul = Column(Float, nullable=True)
    split_index = Column(Integer, default=1)
    ligand_concentration = Column(Float, nullable=True)
    ligand_condition = Column(String(10), nullable=True, default=None)  # "+Lig" or "-Lig"
    is_excluded = Column(Boolean, default=False)
    exclusion_reason = Column(String(500), nullable=True)
    exclude_from_fc = Column(Boolean, default=False)  # Excluded from FC calculation due to low R²

    # QC status tracking
    fit_status = Column(Enum(FitStatus), default=FitStatus.PENDING)

    # Checkerboard validation (384-well only)
    is_checkerboard_valid = Column(Boolean, nullable=True)

    # Relationships
    plate = relationship("Plate", back_populates="wells")
    reaction = relationship("Reaction", back_populates="wells")
    construct = relationship("Construct", back_populates="wells")
    family = relationship("Family")
    paired_with = relationship("Well", remote_side=[id], backref="paired_by")
    
    raw_data = relationship("RawDataPoint", back_populates="well", cascade="all, delete-orphan")
    fit_result = relationship("FitResult", back_populates="well", uselist=False, cascade="all, delete-orphan")

    # Fold changes where this well is the test
    fold_changes_as_test = relationship(
        "FoldChange",
        foreign_keys="FoldChange.test_well_id",
        back_populates="test_well",
        cascade="all, delete-orphan"
    )
    # Fold changes where this well is the control
    fold_changes_as_control = relationship(
        "FoldChange",
        foreign_keys="FoldChange.control_well_id",
        back_populates="control_well",
        cascade="all, delete",
        passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("plate_id", "position", name="uq_well_plate_position"),
    )

    def __repr__(self):
        excluded = " [excluded]" if self.is_excluded else ""
        return f"<Well id={self.id} {self.position} ({self.well_type.value}){excluded}>"

    @property
    def row_letter(self) -> str:
        """Extract row letter from position (e.g., 'A' from 'A1')."""
        return self.position[0]

    @property
    def col_number(self) -> int:
        """Extract column number from position (e.g., 1 from 'A1')."""
        return int(self.position[1:])


class RawDataPoint(db.Model):
    """
    A single raw fluorescence measurement at a timepoint.
    """
    __tablename__ = "raw_data_points"

    id = Column(Integer, primary_key=True)
    well_id = Column(Integer, ForeignKey("wells.id"), nullable=False)
    timepoint = Column(Float, nullable=False)  # minutes
    fluorescence_raw = Column(Float, nullable=False)
    fluorescence_corrected = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)

    # Relationships
    well = relationship("Well", back_populates="raw_data")

    def __repr__(self):
        return f"<RawDataPoint id={self.id} t={self.timepoint:.1f}min F={self.fluorescence_raw:.1f}>"
