"""AnalysisVersion models - named checkpoints and hierarchical results."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
import enum

from app.extensions import db
from app.models.base import TimestampMixin


class AnalysisStatus(enum.Enum):
    """Analysis checkpoint status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisVersion(db.Model, TimestampMixin):
    """
    Named analysis checkpoint.

    Stores a snapshot of analysis parameters and results at a point in time.
    """
    __tablename__ = "analysis_versions"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Status tracking
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.RUNNING)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Snapshot of analysis parameters
    model_type = Column(String(50), nullable=False)
    mcmc_chains = Column(Integer, default=4)
    mcmc_draws = Column(Integer, default=2000)
    mcmc_tune = Column(Integer, default=1000)
    mcmc_thin = Column(Integer, default=5)
    random_seed = Column(Integer, nullable=True)

    # Model comparison results
    model_comparison = Column(JSON, nullable=True)
    best_model_type = Column(String(50), nullable=True)

    # Adaptive model tier metadata
    # Stores: tier, n_sessions, n_plates, user_message, etc.
    model_tier_metadata = Column(JSON, nullable=True)

    # Model residuals (observed - predicted) per parameter
    # Stores: {"log_fc_fmax": [r1, r2, ...], "log_fc_kobs": [...]}
    model_residuals = Column(JSON, nullable=True)

    # Trace storage
    trace_file_path = Column(String(500), nullable=True)
    trace_thin_factor = Column(Integer, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="analysis_versions")
    hierarchical_results = relationship("HierarchicalResult", back_populates="analysis_version", cascade="all, delete-orphan")
    parameter_correlations = relationship("ParameterCorrelation", back_populates="analysis_version", cascade="all, delete-orphan")
    mcmc_checkpoints = relationship("MCMCCheckpoint", back_populates="analysis_version", cascade="all, delete-orphan")
    precision_weights = relationship("PrecisionWeight", back_populates="analysis_version")
    precision_histories = relationship("PrecisionHistory", back_populates="analysis_version")
    precision_overrides = relationship("PrecisionOverride", back_populates="analysis_version")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_analysis_project_name"),
    )

    def __repr__(self):
        status = self.status.value if self.status else "unknown"
        return f"<AnalysisVersion id={self.id} {self.name!r} [{status}]>"

    @property
    def is_complete(self) -> bool:
        """Check if analysis completed successfully."""
        return self.status == AnalysisStatus.COMPLETED


class HierarchicalResult(db.Model):
    """
    Hierarchical model result for a construct.

    Stores posterior/estimate summaries and variance components.
    """
    __tablename__ = "hierarchical_results"

    id = Column(Integer, primary_key=True)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False, index=True)
    parameter_type = Column(String(50), nullable=False)  # "log_fc_fmax", "log_fc_kobs", "delta_tlag"
    analysis_type = Column(String(50), nullable=False)  # "bayesian", "frequentist"
    ligand_condition = Column(String(10), nullable=True, default=None)  # "+Lig", "-Lig", or None (all conditions)

    # Posterior/Estimate summaries
    mean = Column(Float, nullable=False)
    std = Column(Float, nullable=False)
    ci_lower = Column(Float, nullable=False)
    ci_upper = Column(Float, nullable=False)

    # Bayesian-specific
    prob_positive = Column(Float, nullable=True)
    prob_meaningful = Column(Float, nullable=True)

    # Variance components
    var_session = Column(Float, nullable=True)
    var_plate = Column(Float, nullable=True)
    var_residual = Column(Float, nullable=True)

    # MCMC diagnostics
    n_samples = Column(Integer, nullable=True)
    r_hat = Column(Float, nullable=True)
    ess_bulk = Column(Float, nullable=True)
    ess_tail = Column(Float, nullable=True)

    # Posterior samples for on-demand probability computation (JSON array of floats)
    # Stored as thinned samples (~500-1000) to keep size manageable
    posterior_samples = Column(JSON, nullable=True)

    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    analysis_version = relationship("AnalysisVersion", back_populates="hierarchical_results")
    construct = relationship("Construct", back_populates="hierarchical_results")

    def __repr__(self):
        return f"<HierarchicalResult id={self.id} {self.parameter_type} construct={self.construct_id} mean={self.mean:.3f}>"

    @property
    def ci_width(self) -> float:
        """Width of the confidence/credible interval."""
        return self.ci_upper - self.ci_lower


class ParameterCorrelation(db.Model):
    """
    Correlation between parameters from multivariate model.
    """
    __tablename__ = "parameter_correlations"

    id = Column(Integer, primary_key=True)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=False)
    parameter_1 = Column(String(50), nullable=False)
    parameter_2 = Column(String(50), nullable=False)

    # Correlation at construct level
    correlation = Column(Float, nullable=False)
    ci_lower = Column(Float, nullable=True)
    ci_upper = Column(Float, nullable=True)

    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    analysis_version = relationship("AnalysisVersion", back_populates="parameter_correlations")
    construct = relationship("Construct", back_populates="parameter_correlations")

    def __repr__(self):
        return f"<ParameterCorrelation id={self.id} {self.parameter_1}~{self.parameter_2} r={self.correlation:.3f}>"


class CheckpointStatus(enum.Enum):
    """Checkpoint status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class MCMCCheckpoint(db.Model):
    """
    MCMC checkpoint for crash recovery.

    PRD Reference: Section 0.2, F11.4-F11.5

    Stores checkpoint metadata and file paths to enable:
    - Resume from checkpoint on worker restart
    - Error checkpoints for debugging
    - Cleanup after successful completion
    """
    __tablename__ = "mcmc_checkpoints"

    id = Column(Integer, primary_key=True)
    analysis_version_id = Column(Integer, ForeignKey("analysis_versions.id"), nullable=False)

    # Progress tracking
    draw_idx = Column(Integer, nullable=False)  # Current draw number
    chain_idx = Column(Integer, nullable=False)  # Chain number (0 for aggregate)
    total_draws = Column(Integer, nullable=True)  # Total draws expected
    total_chains = Column(Integer, nullable=True)  # Total chains

    # Status
    status = Column(Enum(CheckpointStatus), default=CheckpointStatus.IN_PROGRESS)

    # File paths
    checkpoint_path = Column(String(500), nullable=False)  # Path to trace file
    config_path = Column(String(500), nullable=True)  # Path to config JSON

    # Timestamps
    checkpoint_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_final = Column(Boolean, default=False)

    # Error information (for error checkpoints)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Relationships
    analysis_version = relationship("AnalysisVersion", back_populates="mcmc_checkpoints")

    def __repr__(self):
        status = f" [{self.status.value}]" if self.status else ""
        return f"<MCMCCheckpoint id={self.id} draw={self.draw_idx}/{self.total_draws or '?'}{status}>"

    @property
    def progress_fraction(self) -> float:
        """Get progress as fraction 0-1."""
        if self.total_draws and self.total_draws > 0:
            return self.draw_idx / self.total_draws
        return 0.0

    @property
    def is_resumable(self) -> bool:
        """Check if this checkpoint can be resumed from."""
        return (
            self.status == CheckpointStatus.COMPLETED and
            self.is_final and
            self.checkpoint_path is not None
        )

    @classmethod
    def create_checkpoint(
        cls,
        analysis_version_id: int,
        draw_idx: int,
        total_draws: int,
        checkpoint_path: str,
        config_path: str = None,
        chain_idx: int = 0,
        total_chains: int = 4,
        is_final: bool = False,
        status: CheckpointStatus = CheckpointStatus.IN_PROGRESS
    ) -> 'MCMCCheckpoint':
        """
        Create a new checkpoint record.

        Args:
            analysis_version_id: Analysis version ID
            draw_idx: Current draw index
            total_draws: Total draws expected
            checkpoint_path: Path to trace file
            config_path: Path to config JSON (optional)
            chain_idx: Chain index (0 for aggregate)
            total_chains: Total number of chains
            is_final: Whether this is the final checkpoint
            status: Checkpoint status

        Returns:
            New MCMCCheckpoint instance (not yet committed)
        """
        return cls(
            analysis_version_id=analysis_version_id,
            draw_idx=draw_idx,
            total_draws=total_draws,
            chain_idx=chain_idx,
            total_chains=total_chains,
            checkpoint_path=checkpoint_path,
            config_path=config_path,
            is_final=is_final,
            status=status,
            checkpoint_at=datetime.now(timezone.utc)
        )

    @classmethod
    def create_error_checkpoint(
        cls,
        analysis_version_id: int,
        draw_idx: int,
        total_draws: int,
        checkpoint_path: str,
        error_message: str,
        error_traceback: str = None
    ) -> 'MCMCCheckpoint':
        """
        Create an error checkpoint for debugging.

        PRD Reference: F11.4

        Args:
            analysis_version_id: Analysis version ID
            draw_idx: Draw index at failure
            total_draws: Total draws expected
            checkpoint_path: Path to partial trace (if any)
            error_message: Error message
            error_traceback: Full traceback

        Returns:
            New MCMCCheckpoint with error status
        """
        return cls(
            analysis_version_id=analysis_version_id,
            draw_idx=draw_idx,
            total_draws=total_draws,
            chain_idx=0,
            total_chains=0,
            checkpoint_path=checkpoint_path,
            status=CheckpointStatus.ERROR,
            is_final=False,
            error_message=error_message,
            error_traceback=error_traceback,
            checkpoint_at=datetime.now(timezone.utc)
        )

    @classmethod
    def get_latest_for_version(cls, analysis_version_id: int) -> 'MCMCCheckpoint':
        """
        Get the latest checkpoint for an analysis version.

        Args:
            analysis_version_id: Analysis version ID

        Returns:
            Latest MCMCCheckpoint or None
        """
        return cls.query.filter_by(
            analysis_version_id=analysis_version_id
        ).order_by(cls.checkpoint_at.desc()).first()

    @classmethod
    def get_resumable_checkpoint(cls, analysis_version_id: int) -> 'MCMCCheckpoint':
        """
        Get a resumable checkpoint for an analysis version.

        Args:
            analysis_version_id: Analysis version ID

        Returns:
            Resumable MCMCCheckpoint or None
        """
        return cls.query.filter_by(
            analysis_version_id=analysis_version_id,
            status=CheckpointStatus.COMPLETED,
            is_final=True
        ).order_by(cls.checkpoint_at.desc()).first()

    @classmethod
    def cleanup_for_version(cls, analysis_version_id: int) -> int:
        """
        Clean up non-final checkpoints for an analysis version.

        Keeps only the final checkpoint and deletes intermediates.

        Args:
            analysis_version_id: Analysis version ID

        Returns:
            Number of checkpoints deleted
        """
        from pathlib import Path

        # Get non-final checkpoints
        non_final = cls.query.filter_by(
            analysis_version_id=analysis_version_id,
            is_final=False
        ).all()

        count = 0
        for checkpoint in non_final:
            # Delete checkpoint file if exists
            try:
                cp_path = Path(checkpoint.checkpoint_path)
                if cp_path.exists():
                    cp_path.unlink()
                if checkpoint.config_path:
                    config_path = Path(checkpoint.config_path)
                    if config_path.exists():
                        config_path.unlink()
            except Exception:
                pass  # File cleanup is best-effort

            # Delete database record
            from app.extensions import db
            db.session.delete(checkpoint)
            count += 1

        return count
