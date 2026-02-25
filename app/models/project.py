"""Project model - main container for IVT kinetics experiments."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.path_utils import slugify


class PlateFormat(enum.Enum):
    """Supported plate formats."""
    PLATE_96 = "96"
    PLATE_384 = "384"


class Project(db.Model, TimestampMixin):
    """
    Main project container for IVT kinetics experiments.

    A project groups related experiments analyzing transcription kinetics
    of various RNA constructs using fluorogenic reporters.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    name_slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    reporter_system = Column(String(100), nullable=True)  # e.g., "iSpinach"

    # Plate format (project-level, cannot mix formats)
    plate_format = Column(
        Enum(PlateFormat),
        default=PlateFormat.PLATE_384,
        nullable=False
    )

    # Analysis settings
    kinetic_model_type = Column(String(50), default="delayed_exponential")
    meaningful_fc_threshold = Column(Float, default=1.5)

    # QC threshold settings
    qc_cv_threshold = Column(Float, default=0.20)
    qc_outlier_threshold = Column(Float, default=3.0)
    qc_drift_threshold = Column(Float, default=0.1)
    qc_saturation_threshold = Column(Float, default=0.95)
    qc_temperature_drift_threshold = Column(Float, default=5.0)
    qc_empty_well_threshold = Column(Float, default=100.0)

    # Negative control QC thresholds
    qc_snr_threshold = Column(Float, default=10.0)
    qc_bsi_threshold = Column(Float, default=0.10)
    qc_neg_cv_threshold = Column(Float, default=0.15)
    lod_coverage_factor = Column(Float, default=3.0)
    loq_coverage_factor = Column(Float, default=10.0)

    # Ligand experiment settings
    has_ligand_conditions = Column(Boolean, default=False)
    ligand_name = Column(String(100), nullable=True)
    ligand_unit = Column(String(20), default="µM")
    ligand_max_concentration = Column(Float, nullable=True)

    # Draft/publish state
    is_draft = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(100), nullable=True)
    is_archived = Column(Boolean, default=False)

    # Activity tracking for inactivity flagging (Phase H.3)
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    inactivity_warning_sent = Column(Boolean, default=False)

    # Downstream validity tracking
    results_valid = Column(Boolean, default=True)

    # Fitting publication state
    fitting_published = Column(Boolean, default=False)
    fitting_published_at = Column(DateTime, nullable=True)
    fitting_published_by = Column(String(100), nullable=True)

    # Precision analysis settings
    precision_target = Column(Float, default=0.3)  # Target CI width for fold change

    # Notes
    notes = Column(Text, nullable=True)

    # Comparison hierarchy - project-level unregulated reference
    unregulated_construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=True)

    # Relationships
    constructs = relationship("Construct", back_populates="project", foreign_keys="Construct.project_id")
    sessions = relationship("ExperimentalSession", back_populates="project")
    plate_layouts = relationship("PlateLayout", back_populates="project")
    analysis_versions = relationship("AnalysisVersion", back_populates="project")
    comparison_graphs = relationship("ComparisonGraph", back_populates="project")
    reaction_setups = relationship("ReactionSetup", back_populates="project")
    methods_text = relationship("MethodsText", back_populates="project", uselist=False)

    def __init__(self, name: str, **kwargs):
        """Create a new project with auto-generated slug."""
        super().__init__(name=name, **kwargs)
        self.name_slug = slugify(name)

    def __repr__(self):
        return f"<Project id={self.id} {self.name!r}>"

    @property
    def plate_rows(self) -> int:
        """Number of rows based on plate format."""
        return 8 if self.plate_format == PlateFormat.PLATE_96 else 16

    @property
    def plate_cols(self) -> int:
        """Number of columns based on plate format."""
        return 12 if self.plate_format == PlateFormat.PLATE_96 else 24

    def invalidate_results(self):
        """Mark results as invalid when upstream data changes."""
        self.results_valid = False

    @property
    def has_plates(self) -> bool:
        """Check if project has any experimental plates."""
        from app.models import Plate, ExperimentalSession
        return Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == self.id
        ).first() is not None

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc)
        self.inactivity_warning_sent = False

    @property
    def days_since_activity(self) -> int:
        """Get number of days since last activity."""
        if self.last_activity_at:
            last = self.last_activity_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - last
            return delta.days
        return 0

    @property
    def is_inactive(self) -> bool:
        """Check if project has been inactive for 6 months (180 days)."""
        return self.days_since_activity >= 180

    @property
    def inactivity_status(self) -> str:
        """Get human-readable inactivity status."""
        days = self.days_since_activity
        if days < 30:
            return "active"
        elif days < 90:
            return "recent"
        elif days < 180:
            return "aging"
        else:
            return "inactive"
