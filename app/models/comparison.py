"""
Comparison models - comparison graphs and precision tracking.

PRD Extension: Supports Section 3.10 (Comparison Hierarchy) and Section 3.12
(Precision Tracking). Provides database models for comparison graph structure,
precision history, and VIF-based variance inflation tracking.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
import enum

from app.extensions import db


class PathType(enum.Enum):
    """Comparison path types."""
    DIRECT = "direct"
    ONE_HOP = "one_hop"
    TWO_HOP = "two_hop"
    FOUR_HOP = "four_hop"


class ComparisonGraph(db.Model):
    """
    Tracks comparison paths between constructs.

    Enables the hierarchical comparison system for calculating fold changes
    between constructs that may not appear on the same plate.
    """
    __tablename__ = "comparison_graphs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    target_construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    path_type = Column(Enum(PathType), nullable=False)
    intermediate_construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=True)
    co_occurrence_count = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="comparison_graphs")
    source_construct = relationship("Construct", foreign_keys=[source_construct_id])
    target_construct = relationship("Construct", foreign_keys=[target_construct_id])
    intermediate_construct = relationship("Construct", foreign_keys=[intermediate_construct_id])
    precision_weights = relationship("PrecisionWeight", back_populates="comparison_graph")

    __table_args__ = (
        UniqueConstraint("project_id", "source_construct_id", "target_construct_id",
                        name="uq_comparison_project_source_target"),
    )

    def __repr__(self):
        return f"<ComparisonGraph id={self.id} {self.source_construct_id}->{self.target_construct_id} [{self.path_type.value}]>"


class PrecisionWeight(db.Model):
    """
    Precision weights for construct comparisons based on path type.
    """
    __tablename__ = "precision_weights"

    id = Column(Integer, primary_key=True)
    comparison_graph_id = Column(Integer, ForeignKey("comparison_graphs.id"), nullable=False)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)
    variance_inflation_factor = Column(Float, nullable=False)
    precision_weight = Column(Float, nullable=False)
    effective_sample_size = Column(Float, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comparison_graph = relationship("ComparisonGraph", back_populates="precision_weights")
    analysis_version = relationship("AnalysisVersion", back_populates="precision_weights")

    def __repr__(self):
        return f"<PrecisionWeight id={self.id} VIF={self.variance_inflation_factor:.2f}>"


class PrecisionHistory(db.Model):
    """
    Tracks precision improvements over time as plates are added.
    """
    __tablename__ = "precision_histories"

    id = Column(Integer, primary_key=True)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)
    ci_width = Column(Float, nullable=False)
    comparison_type = Column(String(50), nullable=False)  # 'mutant_wt', 'wt_unregulated', etc.
    path_type = Column(String(50), nullable=False)  # 'direct', 'one_hop', etc.
    plate_count = Column(Integer, nullable=False)
    replicate_count = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    construct = relationship("Construct", back_populates="precision_histories")
    analysis_version = relationship("AnalysisVersion", back_populates="precision_histories")

    def __repr__(self):
        return f"<PrecisionHistory id={self.id} CI±{self.ci_width:.3f} ({self.plate_count} plates)>"


class PrecisionOverride(db.Model):
    """
    Tracks user overrides when precision target not met but marked acceptable.

    PRD Ref: F12.6 - Precision target override with justification (min 20 chars).
    """
    __tablename__ = "precision_overrides"

    id = Column(Integer, primary_key=True)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)
    ci_width_actual = Column(Float, nullable=False)
    ci_width_target = Column(Float, nullable=False)
    is_acceptable = Column(Boolean, default=True)
    justification = Column(Text, nullable=False)  # Required, min 20 chars
    override_by = Column(String(100), nullable=False)
    override_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    construct = relationship("Construct", back_populates="precision_overrides")
    analysis_version = relationship("AnalysisVersion", back_populates="precision_overrides")

    __table_args__ = (
        UniqueConstraint("construct_id", "analysis_version_id", name="uq_override_construct_version"),
    )

    def __repr__(self):
        return f"<PrecisionOverride id={self.id} actual={self.ci_width_actual:.3f} target={self.ci_width_target:.3f}>"
