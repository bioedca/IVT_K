"""FitResult models - curve fitting and fold change results."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import FitResultMixin


class FitResult(db.Model, FitResultMixin):
    """
    Curve fitting result for a single well.

    Stores fitted parameters, goodness of fit metrics, and quality flags.
    Inherits parameter columns and is_good_fit from FitResultMixin.
    """
    __tablename__ = "fit_results"

    id = Column(Integer, primary_key=True)
    well_id = Column(Integer, ForeignKey("wells.id"), unique=True, nullable=False)
    model_type = Column(String(50), nullable=False)  # "delayed_exponential", "logistic", etc.

    fitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    well = relationship("Well", back_populates="fit_result")
    signal_quality = relationship("SignalQualityMetrics", back_populates="fit_result", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        r2 = f" R²={self.r_squared:.3f}" if self.r_squared is not None else ""
        return f"<FitResult id={self.id} {self.model_type}{r2}>"


class FoldChange(db.Model):
    """
    Fold change calculation between a test and control well.

    Computes fold changes for F_max, k_obs, and delta t_lag.
    """
    __tablename__ = "fold_changes"

    id = Column(Integer, primary_key=True)
    test_well_id = Column(Integer, ForeignKey("wells.id"), nullable=False, index=True)
    control_well_id = Column(Integer, ForeignKey("wells.id"), nullable=False, index=True)

    # Computed values (linear scale)
    fc_fmax = Column(Float, nullable=True)
    fc_fmax_se = Column(Float, nullable=True)
    fc_kobs = Column(Float, nullable=True)
    fc_kobs_se = Column(Float, nullable=True)
    delta_tlag = Column(Float, nullable=True)
    delta_tlag_se = Column(Float, nullable=True)

    # Log-transformed
    log_fc_fmax = Column(Float, nullable=True)
    log_fc_fmax_se = Column(Float, nullable=True)
    log_fc_kobs = Column(Float, nullable=True)
    log_fc_kobs_se = Column(Float, nullable=True)

    # Ligand condition tracking
    ligand_condition = Column(String(10), nullable=True, default=None)  # "+Lig", "-Lig", or None
    comparison_type = Column(String(30), nullable=True, default=None)  # "within_condition", "ligand_effect"

    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    test_well = relationship("Well", foreign_keys=[test_well_id], back_populates="fold_changes_as_test")
    control_well = relationship("Well", foreign_keys=[control_well_id], back_populates="fold_changes_as_control")

    __table_args__ = (
        UniqueConstraint("test_well_id", "control_well_id", name="uq_foldchange_test_control"),
    )

    def __repr__(self):
        fc = f" FC={self.fc_fmax:.2f}" if self.fc_fmax is not None else ""
        return f"<FoldChange id={self.id}{fc}>"


class FitResultArchive(db.Model, FitResultMixin):
    """
    Archived fit result preserving historical fits before refitting.

    When a well is refitted, the previous FitResult is copied here
    to maintain a complete audit trail of all fits performed.
    Inherits parameter columns and is_good_fit from FitResultMixin.

    PRD Reference: Section 0.20, F8.7 - Fit Result Archival
    """
    __tablename__ = "fit_result_archives"

    id = Column(Integer, primary_key=True)
    well_id = Column(Integer, ForeignKey("wells.id"), nullable=False, index=True)

    # Reference to the fit that replaced this one (optional - may be null if deleted)
    superseding_fit_id = Column(Integer, ForeignKey("fit_results.id"), nullable=True)

    # Original fit metadata
    original_fit_id = Column(Integer, nullable=False)  # ID of the original fit (for reference)
    model_type = Column(String(50), nullable=False)

    # Timestamps
    original_fitted_at = Column(DateTime, nullable=False)  # When original fit was done
    superseded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)  # When archived

    # Audit information
    superseded_by = Column(String(100), nullable=True)  # Username who triggered refit
    superseded_reason = Column(String(500), nullable=True)  # Optional reason for refit

    # Relationships
    well = relationship("Well", backref="fit_archives")
    superseding_fit = relationship("FitResult", foreign_keys=[superseding_fit_id])

    def __repr__(self):
        ts = self.superseded_at.strftime('%Y-%m-%d %H:%M') if self.superseded_at else 'N/A'
        return f"<FitResultArchive id={self.id} well={self.well_id} orig={self.original_fit_id} ({ts})>"

    @classmethod
    def from_fit_result(
        cls,
        fit_result: 'FitResult',
        superseded_by: str = None,
        superseded_reason: str = None
    ) -> 'FitResultArchive':
        """
        Create an archive record from an existing FitResult.

        Args:
            fit_result: The FitResult to archive
            superseded_by: Username who triggered the refit
            superseded_reason: Optional reason for refitting

        Returns:
            New FitResultArchive instance (not yet committed)
        """
        return cls(
            well_id=fit_result.well_id,
            original_fit_id=fit_result.id,
            model_type=fit_result.model_type,
            # Parameters (from FitResultMixin)
            f_baseline=fit_result.f_baseline,
            f_baseline_se=fit_result.f_baseline_se,
            f_max=fit_result.f_max,
            f_max_se=fit_result.f_max_se,
            k_obs=fit_result.k_obs,
            k_obs_se=fit_result.k_obs_se,
            t_lag=fit_result.t_lag,
            t_lag_se=fit_result.t_lag_se,
            # Statistics (from FitResultMixin)
            r_squared=fit_result.r_squared,
            rmse=fit_result.rmse,
            aic=fit_result.aic,
            # Quality (from FitResultMixin)
            converged=fit_result.converged,
            residual_normality_pvalue=fit_result.residual_normality_pvalue,
            residual_autocorr_dw=fit_result.residual_autocorr_dw,
            # Reliability metrics (from FitResultMixin)
            run_length_min=fit_result.run_length_min,
            pct_plateau_reached=fit_result.pct_plateau_reached,
            mean_signal=fit_result.mean_signal,
            # Timestamps
            original_fitted_at=fit_result.fitted_at or datetime.now(timezone.utc),
            superseded_at=datetime.now(timezone.utc),
            # Audit
            superseded_by=superseded_by,
            superseded_reason=superseded_reason,
        )


class SignalQualityMetrics(db.Model):
    """
    Signal quality metrics for a fit result.

    Includes SNR, SBR, and detection limit information.
    """
    __tablename__ = "signal_quality_metrics"

    id = Column(Integer, primary_key=True)
    fit_result_id = Column(Integer, ForeignKey("fit_results.id"), unique=True, nullable=False)

    # Signal quality metrics
    snr = Column(Float, nullable=True)  # Signal-to-Noise Ratio
    sbr = Column(Float, nullable=True)  # Signal-to-Background Ratio

    # Detection limits
    above_lod = Column(Boolean, nullable=True)
    above_loq = Column(Boolean, nullable=True)
    lod_value = Column(Float, nullable=True)
    loq_value = Column(Float, nullable=True)
    min_detectable_fc = Column(Float, nullable=True)

    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    fit_result = relationship("FitResult", back_populates="signal_quality")

    def __repr__(self):
        snr = f" SNR={self.snr:.1f}" if self.snr is not None else ""
        return f"<SignalQualityMetrics id={self.id}{snr}>"
