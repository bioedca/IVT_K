"""Construct model - DNA constructs for IVT experiments."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Construct(db.Model, TimestampMixin):
    """
    A DNA construct used in IVT experiments.

    Constructs are organized into families (e.g., "Tbox1", "Tbox2") with
    one wild-type per family and multiple mutants. The unregulated construct
    serves as the universal reference.
    """
    __tablename__ = "constructs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    identifier = Column(String(100), nullable=False)  # e.g., "Tbox1_WT"
    family = Column(String(100), nullable=False)  # e.g., "Tbox1", or "universal"
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True) # New FK
    
    description = Column(Text, nullable=True)  # Description of the construct
    sequence = Column(Text, nullable=True)  # DNA sequence
    plasmid_size_bp = Column(Integer, nullable=True)  # Plasmid size in base pairs
    is_wildtype = Column(Boolean, default=False)
    is_unregulated = Column(Boolean, default=False)
    mutation_description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Draft/publish state
    is_draft = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="constructs", foreign_keys=[project_id])
    family_rel = relationship("Family", back_populates="constructs")
    wells = relationship("Well", back_populates="construct")
    well_assignments = relationship("WellAssignment", back_populates="construct")
    hierarchical_results = relationship("HierarchicalResult", back_populates="construct")
    parameter_correlations = relationship("ParameterCorrelation", back_populates="construct")
    precision_histories = relationship("PrecisionHistory", back_populates="construct")
    precision_overrides = relationship("PrecisionOverride", back_populates="construct")

    __table_args__ = (
        UniqueConstraint("project_id", "identifier", name="uq_construct_project_identifier"),
    )

    def __repr__(self):
        return f"<Construct id={self.id} {self.identifier}>"

    @property
    def display_name(self) -> str:
        """Display name with family context."""
        if self.is_unregulated:
            return f"{self.identifier} (Unregulated)"
        elif self.is_wildtype:
            return f"{self.identifier} (WT)"
        else:
            return self.identifier
