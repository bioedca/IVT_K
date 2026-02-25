"""PlateLayout and WellAssignment models - plate layout templates."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.base import TimestampMixin


class WellType(enum.Enum):
    """
    Well type classifications - describes physical contents of wells.
    
    Analytical roles (unregulated, wildtype, mutant) are derived from
    the Construct's is_unregulated and is_wildtype flags, NOT from well_type.
    """
    EMPTY = "empty"
    SAMPLE = "sample"
    BLANK = "blank"
    NEGATIVE_CONTROL_NO_TEMPLATE = "negative_control_no_template"
    NEGATIVE_CONTROL_NO_DYE = "negative_control_no_dye"


class PlateLayout(db.Model, TimestampMixin):
    """
    Plate layout template for organizing well assignments.

    Templates can be reused across multiple plates. When a plate needs
    modifications, an instance is created linked to the source template.
    """
    __tablename__ = "plate_layouts"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    plate_format = Column(String(10), default="384", nullable=False)  # "96" or "384"
    rows = Column(Integer, nullable=False)  # 8 for 96-well, 16 for 384-well
    cols = Column(Integer, nullable=False)  # 12 for 96-well, 24 for 384-well
    is_template = Column(Boolean, default=True)
    parent_template_id = Column(Integer, ForeignKey("plate_layouts.id"), nullable=True)

    # Draft/publish state
    is_draft = Column(Boolean, default=True)

    # Relationships
    project = relationship("Project", back_populates="plate_layouts")
    well_assignments = relationship("WellAssignment", back_populates="layout", cascade="all, delete-orphan")
    parent_template = relationship("PlateLayout", remote_side=[id], backref="instances")
    plates = relationship("Plate", back_populates="layout")

    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_layout_project_name_version"),
    )

    def __init__(self, project_id: int, name: str, plate_format: str = "384", **kwargs):
        """Create a new plate layout with auto-populated dimensions."""
        super().__init__(project_id=project_id, name=name, plate_format=plate_format, **kwargs)
        if plate_format == "96":
            self.rows = 8
            self.cols = 12
        else:  # 384
            self.rows = 16
            self.cols = 24

    def __repr__(self):
        ver = f" v{self.version}" if self.version and self.version > 1 else ""
        return f"<PlateLayout id={self.id} {self.name!r}{ver}>"

    @property
    def total_wells(self) -> int:
        """Total number of wells in this layout."""
        return self.rows * self.cols

    def create_instance(self) -> "PlateLayout":
        """Create a modifiable instance from this template."""
        instance = PlateLayout(
            project_id=self.project_id,
            name=self.name,
            plate_format=self.plate_format,
            is_template=False,
            parent_template_id=self.id
        )
        # Copy well assignments including ligand concentration
        # First pass: create assignments without paired_with
        position_to_new_assignment = {}
        old_paired_with_positions = {}

        for assignment in self.well_assignments:
            new_assignment = WellAssignment(
                well_position=assignment.well_position,
                construct_id=assignment.construct_id,
                well_type=assignment.well_type,
                family_id=assignment.family_id,
                replicate_group=assignment.replicate_group,
                ligand_concentration=assignment.ligand_concentration,
                ligand_condition=assignment.ligand_condition
            )
            instance.well_assignments.append(new_assignment)
            position_to_new_assignment[assignment.well_position] = new_assignment

            # Track paired_with relationships to restore later
            if assignment.paired_with:
                old_paired_with_positions[assignment.well_position] = assignment.paired_with.well_position

        # Second pass: restore paired_with relationships
        for position, paired_position in old_paired_with_positions.items():
            if position in position_to_new_assignment and paired_position in position_to_new_assignment:
                position_to_new_assignment[position].paired_with = position_to_new_assignment[paired_position]

        return instance


class WellAssignment(db.Model):
    """
    Well assignment within a plate layout.

    Defines what construct or control type is assigned to each well position.
    Supports ligand concentration assignment for dose-response experiments.
    """
    __tablename__ = "well_assignments"

    id = Column(Integer, primary_key=True)
    layout_id = Column(Integer, ForeignKey("plate_layouts.id"), nullable=False)
    well_position = Column(String(10), nullable=False)  # e.g., "A1"
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=True, index=True)
    well_type = Column(Enum(WellType), default=WellType.EMPTY, nullable=False)
    
    # New Hierarchical Fields
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    paired_with_id = Column(Integer, ForeignKey("well_assignments.id"), nullable=True)
    
    replicate_group = Column(String(50), nullable=True)

    # Ligand concentration (F5.10) - 0 or null means no ligand
    ligand_concentration = Column(Float, nullable=True, default=None)

    # Ligand condition (+Lig/-Lig) for binary ligand experiments
    ligand_condition = Column(String(10), nullable=True, default=None)

    # Relationships
    layout = relationship("PlateLayout", back_populates="well_assignments")
    construct = relationship("Construct", back_populates="well_assignments")
    family = relationship("Family")
    paired_with = relationship("WellAssignment", remote_side=[id], backref="paired_by")

    __table_args__ = (
        UniqueConstraint("layout_id", "well_position", name="uq_assignment_layout_position"),
    )

    def __repr__(self):
        wt = self.well_type.value if self.well_type else "unset"
        return f"<WellAssignment id={self.id} {self.well_position}:{wt}>"

    @property
    def has_ligand(self) -> bool:
        """Check if well has ligand assigned."""
        return self.ligand_concentration is not None and self.ligand_concentration > 0
