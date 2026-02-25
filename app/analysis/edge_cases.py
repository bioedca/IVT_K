"""
Edge Case Handling for IVT Kinetics Analysis.

Sprint 10: Edge Cases & Polish

Provides robust handling of statistical edge cases:
- T5.16: MCMC divergent transitions
- T5.17: Zero variance random effects
- T5.18: Model degeneracy detection
- T5.19: Extreme posterior shapes
- T5.20: Insufficient data warnings
- T4.20-T4.24: Curve fitting convergence failures
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum
import logging
import warnings

from app.analysis.constants import HIGH_CORRELATION_THRESHOLD

logger = logging.getLogger(__name__)


class DiagnosticSeverity(Enum):
    """Severity levels for diagnostic warnings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticMessage:
    """A diagnostic warning or error message."""
    code: str
    message: str
    severity: DiagnosticSeverity
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details
        }


@dataclass
class MCMCDiagnostics:
    """
    MCMC sampling diagnostics for quality assessment.

    T5.16: Handle divergent transitions
    """
    n_chains: int
    n_draws: int
    n_tune: int

    # Divergence statistics
    divergent_count: int = 0
    divergent_rate: float = 0.0

    # Tree depth statistics
    max_treedepth_count: int = 0
    max_treedepth_rate: float = 0.0

    # R-hat statistics (should be < 1.01 for convergence)
    r_hat_max: float = 1.0
    r_hat_values: Dict[str, float] = field(default_factory=dict)

    # Effective sample size (should be > 400 for reliable inference)
    ess_bulk_min: float = float('inf')
    ess_tail_min: float = float('inf')
    ess_values: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Energy diagnostics (BFMI should be > 0.3)
    bfmi_values: List[float] = field(default_factory=list)
    bfmi_min: float = float('inf')

    # Overall assessment
    warnings: List[DiagnosticMessage] = field(default_factory=list)

    @property
    def total_samples(self) -> int:
        """Total number of post-warmup samples."""
        return self.n_chains * self.n_draws

    @property
    def has_divergences(self) -> bool:
        """Check if any divergent transitions occurred."""
        return self.divergent_count > 0

    @property
    def divergence_is_severe(self) -> bool:
        """Check if divergence rate is concerning (>1%)."""
        return self.divergent_rate > 0.01

    @property
    def convergence_ok(self) -> bool:
        """Check if MCMC has converged based on R-hat."""
        return self.r_hat_max < 1.01

    @property
    def ess_ok(self) -> bool:
        """Check if effective sample size is adequate."""
        return self.ess_bulk_min > 400 and self.ess_tail_min > 400

    @property
    def energy_ok(self) -> bool:
        """Check if energy diagnostics are acceptable."""
        return self.bfmi_min > 0.3

    @property
    def is_reliable(self) -> bool:
        """Overall reliability assessment."""
        return (
            not self.divergence_is_severe and
            self.convergence_ok and
            self.ess_ok
        )


def assess_mcmc_diagnostics(
    trace,
    n_chains: int,
    n_draws: int,
    n_tune: int
) -> MCMCDiagnostics:
    """
    Assess MCMC sampling quality from ArviZ InferenceData.

    T5.16: MCMC divergent transitions handled

    Args:
        trace: ArviZ InferenceData object
        n_chains: Number of MCMC chains
        n_draws: Number of draws per chain
        n_tune: Number of tuning samples

    Returns:
        MCMCDiagnostics with quality assessment
    """
    diagnostics = MCMCDiagnostics(
        n_chains=n_chains,
        n_draws=n_draws,
        n_tune=n_tune
    )

    total_samples = n_chains * n_draws

    # Check for divergences
    try:
        if hasattr(trace, 'sample_stats') and 'diverging' in trace.sample_stats:
            div_array = trace.sample_stats['diverging'].values
            diagnostics.divergent_count = int(np.sum(div_array))
            diagnostics.divergent_rate = diagnostics.divergent_count / total_samples if total_samples > 0 else 0.0
    except Exception as e:
        logger.warning(f"Could not check divergences: {e}")

    # Check tree depth
    try:
        if hasattr(trace, 'sample_stats') and 'tree_depth' in trace.sample_stats:
            tree_depth = trace.sample_stats['tree_depth'].values
            max_depth = 10  # Default max tree depth
            at_max = np.sum(tree_depth >= max_depth)
            diagnostics.max_treedepth_count = int(at_max)
            diagnostics.max_treedepth_rate = at_max / total_samples if total_samples > 0 else 0.0
    except Exception:
        pass

    # Check R-hat and ESS
    try:
        import arviz as az
        summary = az.summary(trace)

        if 'r_hat' in summary.columns:
            r_hat_vals = summary['r_hat'].dropna()
            diagnostics.r_hat_max = float(r_hat_vals.max()) if len(r_hat_vals) > 0 else 1.0
            diagnostics.r_hat_values = r_hat_vals.to_dict()

        if 'ess_bulk' in summary.columns:
            ess_bulk = summary['ess_bulk'].dropna()
            diagnostics.ess_bulk_min = float(ess_bulk.min()) if len(ess_bulk) > 0 else 0.0
            diagnostics.ess_values['bulk'] = ess_bulk.to_dict()

        if 'ess_tail' in summary.columns:
            ess_tail = summary['ess_tail'].dropna()
            diagnostics.ess_tail_min = float(ess_tail.min()) if len(ess_tail) > 0 else 0.0
            diagnostics.ess_values['tail'] = ess_tail.to_dict()

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Could not compute MCMC summary: {e}")

    # Check BFMI (Bayesian Fraction of Missing Information)
    try:
        if hasattr(trace, 'sample_stats') and 'energy' in trace.sample_stats:
            import arviz as az
            bfmi = az.bfmi(trace)
            diagnostics.bfmi_values = list(bfmi)
            diagnostics.bfmi_min = float(np.min(bfmi))
    except Exception:
        pass

    # Generate warnings
    _generate_mcmc_warnings(diagnostics)

    return diagnostics


def _generate_mcmc_warnings(diagnostics: MCMCDiagnostics) -> None:
    """Generate warning messages based on MCMC diagnostics."""
    warnings_list = []

    # Divergence warnings
    if diagnostics.divergent_count > 0:
        rate_pct = diagnostics.divergent_rate * 100
        if rate_pct >= 50:
            warnings_list.append(DiagnosticMessage(
                code="MCMC_DIVERGENCE_CRITICAL",
                message=f"Critical: {diagnostics.divergent_count} divergent transitions ({rate_pct:.1f}%). Results are unreliable.",
                severity=DiagnosticSeverity.CRITICAL,
                details={"divergent_count": diagnostics.divergent_count, "rate": rate_pct}
            ))
        elif rate_pct >= 10:
            warnings_list.append(DiagnosticMessage(
                code="MCMC_DIVERGENCE_HIGH",
                message=f"High divergence rate: {diagnostics.divergent_count} transitions ({rate_pct:.1f}%). Consider reparameterization.",
                severity=DiagnosticSeverity.ERROR,
                details={"divergent_count": diagnostics.divergent_count, "rate": rate_pct}
            ))
        elif rate_pct >= 1:
            warnings_list.append(DiagnosticMessage(
                code="MCMC_DIVERGENCE_MODERATE",
                message=f"Some divergent transitions: {diagnostics.divergent_count} ({rate_pct:.1f}%). Results may be biased.",
                severity=DiagnosticSeverity.WARNING,
                details={"divergent_count": diagnostics.divergent_count, "rate": rate_pct}
            ))
        else:
            warnings_list.append(DiagnosticMessage(
                code="MCMC_DIVERGENCE_LOW",
                message=f"Minor divergences: {diagnostics.divergent_count} ({rate_pct:.2f}%). Usually acceptable.",
                severity=DiagnosticSeverity.INFO,
                details={"divergent_count": diagnostics.divergent_count, "rate": rate_pct}
            ))

    # R-hat warnings
    if diagnostics.r_hat_max > 1.1:
        warnings_list.append(DiagnosticMessage(
            code="MCMC_RHAT_CRITICAL",
            message=f"R-hat = {diagnostics.r_hat_max:.3f} indicates severe convergence failure. Run more iterations.",
            severity=DiagnosticSeverity.CRITICAL,
            details={"r_hat_max": diagnostics.r_hat_max}
        ))
    elif diagnostics.r_hat_max > 1.01:
        warnings_list.append(DiagnosticMessage(
            code="MCMC_RHAT_WARNING",
            message=f"R-hat = {diagnostics.r_hat_max:.3f} > 1.01 indicates incomplete convergence.",
            severity=DiagnosticSeverity.WARNING,
            details={"r_hat_max": diagnostics.r_hat_max}
        ))

    # ESS warnings
    if diagnostics.ess_bulk_min < 100:
        warnings_list.append(DiagnosticMessage(
            code="MCMC_ESS_CRITICAL",
            message=f"ESS bulk = {diagnostics.ess_bulk_min:.0f} is critically low. Need more samples.",
            severity=DiagnosticSeverity.CRITICAL,
            details={"ess_bulk_min": diagnostics.ess_bulk_min}
        ))
    elif diagnostics.ess_bulk_min < 400:
        warnings_list.append(DiagnosticMessage(
            code="MCMC_ESS_LOW",
            message=f"ESS bulk = {diagnostics.ess_bulk_min:.0f} < 400. Consider running longer chains.",
            severity=DiagnosticSeverity.WARNING,
            details={"ess_bulk_min": diagnostics.ess_bulk_min}
        ))

    # BFMI warnings
    if diagnostics.bfmi_min < 0.2:
        warnings_list.append(DiagnosticMessage(
            code="MCMC_BFMI_LOW",
            message=f"BFMI = {diagnostics.bfmi_min:.3f} < 0.2 indicates poor energy transition. Consider reparameterization.",
            severity=DiagnosticSeverity.WARNING,
            details={"bfmi_min": diagnostics.bfmi_min}
        ))

    diagnostics.warnings = warnings_list


@dataclass
class DataValidationResult:
    """
    Result of data validation for hierarchical modeling.

    T5.17: Zero variance random effects
    T5.18: Model degeneracy detection
    T5.20: Insufficient data warnings
    """
    is_valid: bool = True
    can_fit_hierarchical: bool = True
    warnings: List[DiagnosticMessage] = field(default_factory=list)

    # Data dimensions
    n_observations: int = 0
    n_constructs: int = 0
    n_sessions: int = 0
    n_plates: int = 0
    n_replicates_per_construct: Dict[int, int] = field(default_factory=dict)

    # Variance diagnostics
    zero_variance_constructs: List[int] = field(default_factory=list)
    near_zero_variance_constructs: List[int] = field(default_factory=list)

    # Degeneracy indicators
    is_rank_deficient: bool = False
    collinear_groups: List[List[int]] = field(default_factory=list)
    condition_number: float = 0.0


def validate_hierarchical_data(
    fold_changes,
    min_observations: int = 4,
    min_constructs: int = 1,
    min_plates: int = 1,
    variance_threshold: float = 1e-10
) -> DataValidationResult:
    """
    Validate data for hierarchical modeling.

    T5.17: Zero variance random effects
    T5.18: Model degeneracy detection
    T5.20: Insufficient data warnings

    Args:
        fold_changes: DataFrame with fold change data
        min_observations: Minimum required observations
        min_constructs: Minimum required constructs
        min_plates: Minimum required plates
        variance_threshold: Threshold for zero variance detection

    Returns:
        DataValidationResult with validation status
    """
    result = DataValidationResult()

    if fold_changes is None or len(fold_changes) == 0:
        result.is_valid = False
        result.can_fit_hierarchical = False
        result.warnings.append(DiagnosticMessage(
            code="DATA_EMPTY",
            message="No data provided for analysis.",
            severity=DiagnosticSeverity.CRITICAL
        ))
        return result

    # Get data dimensions
    result.n_observations = len(fold_changes)
    result.n_constructs = fold_changes['construct_id'].nunique()
    result.n_sessions = fold_changes['session_id'].nunique() if 'session_id' in fold_changes.columns else 1
    result.n_plates = fold_changes['plate_id'].nunique() if 'plate_id' in fold_changes.columns else 1

    # Count replicates per construct
    for construct_id, group in fold_changes.groupby('construct_id'):
        result.n_replicates_per_construct[construct_id] = len(group)

    # T5.20: Check minimum data requirements
    if result.n_observations < min_observations:
        result.is_valid = False
        result.can_fit_hierarchical = False
        result.warnings.append(DiagnosticMessage(
            code="DATA_INSUFFICIENT_OBS",
            message=f"Only {result.n_observations} observations. Minimum {min_observations} required.",
            severity=DiagnosticSeverity.CRITICAL,
            details={"n_observations": result.n_observations, "minimum": min_observations}
        ))

    if result.n_constructs < min_constructs:
        result.is_valid = False
        result.warnings.append(DiagnosticMessage(
            code="DATA_INSUFFICIENT_CONSTRUCTS",
            message=f"Only {result.n_constructs} construct(s). Minimum {min_constructs} required.",
            severity=DiagnosticSeverity.CRITICAL,
            details={"n_constructs": result.n_constructs, "minimum": min_constructs}
        ))

    if result.n_plates < 2:
        result.can_fit_hierarchical = False
        result.warnings.append(DiagnosticMessage(
            code="DATA_SINGLE_PLATE",
            message=f"Only {result.n_plates} plate(s). Hierarchical model requires multiple plates for variance estimation.",
            severity=DiagnosticSeverity.WARNING,
            details={"n_plates": result.n_plates}
        ))

    # Check for constructs with single observation
    single_obs_constructs = [c for c, n in result.n_replicates_per_construct.items() if n < 2]
    if single_obs_constructs:
        result.warnings.append(DiagnosticMessage(
            code="DATA_SINGLE_REPLICATE",
            message=f"{len(single_obs_constructs)} construct(s) have only 1 replicate. Variance cannot be estimated.",
            severity=DiagnosticSeverity.WARNING,
            details={"construct_ids": single_obs_constructs}
        ))

    # T5.17: Check for zero/near-zero variance
    param_col = 'log_fc_fmax' if 'log_fc_fmax' in fold_changes.columns else fold_changes.columns[0]

    for construct_id, group in fold_changes.groupby('construct_id'):
        if len(group) >= 2:
            variance = group[param_col].var()
            if variance < variance_threshold:
                result.zero_variance_constructs.append(construct_id)
            elif variance < 1e-6:
                result.near_zero_variance_constructs.append(construct_id)

    if result.zero_variance_constructs:
        result.warnings.append(DiagnosticMessage(
            code="DATA_ZERO_VARIANCE",
            message=f"{len(result.zero_variance_constructs)} construct(s) have zero variance. Random effects cannot be estimated.",
            severity=DiagnosticSeverity.ERROR,
            details={"construct_ids": result.zero_variance_constructs}
        ))

    # T5.18: Check for model degeneracy (rank deficiency)
    try:
        _check_design_matrix_rank(fold_changes, result)
    except Exception as e:
        logger.warning(f"Could not check design matrix rank: {e}")

    return result


def _check_design_matrix_rank(fold_changes, result: DataValidationResult) -> None:
    """Check design matrix for rank deficiency."""
    # Create simple design matrix
    construct_dummies = np.zeros((len(fold_changes), result.n_constructs))
    construct_ids = fold_changes['construct_id'].unique()
    construct_map = {c: i for i, c in enumerate(construct_ids)}

    for i, row in fold_changes.iterrows():
        construct_dummies[fold_changes.index.get_loc(i), construct_map[row['construct_id']]] = 1

    # Compute condition number
    try:
        cond_num = np.linalg.cond(construct_dummies)
        result.condition_number = cond_num

        if cond_num > 1e10:
            result.is_rank_deficient = True
            result.warnings.append(DiagnosticMessage(
                code="DATA_RANK_DEFICIENT",
                message=f"Design matrix is rank-deficient (condition number: {cond_num:.2e}).",
                severity=DiagnosticSeverity.ERROR,
                details={"condition_number": cond_num}
            ))
    except Exception:
        pass


@dataclass
class PosteriorQualityAssessment:
    """
    Assessment of posterior distribution quality.

    T5.19: Extreme posterior shapes
    """
    is_acceptable: bool = True
    warnings: List[DiagnosticMessage] = field(default_factory=list)

    # Shape diagnostics
    is_bimodal: bool = False
    bimodality_coefficient: float = 0.0
    has_heavy_tails: bool = False
    kurtosis_excess: float = 0.0
    is_at_boundary: bool = False
    boundary_fraction: float = 0.0

    # Skewness
    skewness: float = 0.0
    is_highly_skewed: bool = False


def assess_posterior_quality(
    samples: np.ndarray,
    param_name: str = "parameter",
    lower_bound: Optional[float] = None,
    upper_bound: Optional[float] = None
) -> PosteriorQualityAssessment:
    """
    Assess posterior distribution quality.

    T5.19: Extreme posterior shapes (bimodal, heavy tails, boundary modes)

    Args:
        samples: 1D array of posterior samples
        param_name: Parameter name for messages
        lower_bound: Lower bound for parameter (if constrained)
        upper_bound: Upper bound for parameter (if constrained)

    Returns:
        PosteriorQualityAssessment
    """
    result = PosteriorQualityAssessment()

    if len(samples) < 10:
        result.is_acceptable = False
        result.warnings.append(DiagnosticMessage(
            code="POSTERIOR_INSUFFICIENT_SAMPLES",
            message=f"Only {len(samples)} samples for {param_name}. Cannot assess posterior quality.",
            severity=DiagnosticSeverity.ERROR
        ))
        return result

    samples = np.asarray(samples).flatten()

    # Compute basic statistics
    from scipy import stats

    # Skewness
    result.skewness = float(stats.skew(samples))
    if abs(result.skewness) > 2:
        result.is_highly_skewed = True
        result.warnings.append(DiagnosticMessage(
            code="POSTERIOR_HIGHLY_SKEWED",
            message=f"Posterior for {param_name} is highly skewed (skewness={result.skewness:.2f}).",
            severity=DiagnosticSeverity.WARNING,
            details={"skewness": result.skewness}
        ))

    # Kurtosis (heavy tails)
    result.kurtosis_excess = float(stats.kurtosis(samples))
    if result.kurtosis_excess > 7:  # Very heavy tails
        result.has_heavy_tails = True
        result.warnings.append(DiagnosticMessage(
            code="POSTERIOR_HEAVY_TAILS",
            message=f"Posterior for {param_name} has heavy tails (excess kurtosis={result.kurtosis_excess:.2f}).",
            severity=DiagnosticSeverity.WARNING,
            details={"kurtosis_excess": result.kurtosis_excess}
        ))

    # Bimodality (using Hartigan's dip test approximation via coefficient)
    # BC = (skewness^2 + 1) / (kurtosis + 3)
    # BC > 0.555 suggests bimodality
    kurt = result.kurtosis_excess + 3  # Convert to raw kurtosis
    if kurt > 0:
        result.bimodality_coefficient = (result.skewness ** 2 + 1) / kurt
        if result.bimodality_coefficient > 0.555:
            result.is_bimodal = True
            result.warnings.append(DiagnosticMessage(
                code="POSTERIOR_BIMODAL",
                message=f"Posterior for {param_name} may be bimodal (BC={result.bimodality_coefficient:.3f}).",
                severity=DiagnosticSeverity.WARNING,
                details={"bimodality_coefficient": result.bimodality_coefficient}
            ))

    # Boundary modes
    if lower_bound is not None:
        at_lower = np.sum(samples <= lower_bound + 1e-6) / len(samples)
        if at_lower > 0.05:
            result.is_at_boundary = True
            result.boundary_fraction = at_lower
            result.warnings.append(DiagnosticMessage(
                code="POSTERIOR_AT_LOWER_BOUND",
                message=f"{at_lower*100:.1f}% of posterior for {param_name} is at lower bound.",
                severity=DiagnosticSeverity.WARNING,
                details={"boundary_fraction": at_lower, "bound": lower_bound}
            ))

    if upper_bound is not None:
        at_upper = np.sum(samples >= upper_bound - 1e-6) / len(samples)
        if at_upper > 0.05:
            result.is_at_boundary = True
            result.boundary_fraction = max(result.boundary_fraction, at_upper)
            result.warnings.append(DiagnosticMessage(
                code="POSTERIOR_AT_UPPER_BOUND",
                message=f"{at_upper*100:.1f}% of posterior for {param_name} is at upper bound.",
                severity=DiagnosticSeverity.WARNING,
                details={"boundary_fraction": at_upper, "bound": upper_bound}
            ))

    # Overall assessment
    result.is_acceptable = not (
        result.is_bimodal or
        result.is_at_boundary or
        (result.has_heavy_tails and result.kurtosis_excess > 20)
    )

    return result


@dataclass
class ConvergenceFailureInfo:
    """
    Information about curve fitting convergence failure.

    T4.20-T4.24: Convergence failure handling
    """
    failure_type: str
    message: str
    severity: DiagnosticSeverity
    recoverable: bool = True
    suggested_action: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class ConvergenceFailureType(Enum):
    """Types of convergence failures in curve fitting."""
    MAX_ITERATIONS = "max_iterations"
    GRADIENT_EXPLOSION = "gradient_explosion"
    NAN_PARAMETERS = "nan_parameters"
    ILL_CONDITIONED = "ill_conditioned"
    SINGULAR_MATRIX = "singular_matrix"
    PARAMETER_CORRELATION = "parameter_correlation"
    DATA_SATURATION = "data_saturation"
    INSUFFICIENT_POINTS = "insufficient_points"
    PARAMETER_AT_BOUND = "parameter_at_bound"
    FLAT_DATA = "flat_data"


def diagnose_convergence_failure(
    exception: Optional[Exception] = None,
    params: Optional[np.ndarray] = None,
    covariance: Optional[np.ndarray] = None,
    n_iterations: int = 0,
    max_iterations: int = 5000,
    data_t: Optional[np.ndarray] = None,
    data_F: Optional[np.ndarray] = None,
    bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None
) -> ConvergenceFailureInfo:
    """
    Diagnose the cause of curve fitting convergence failure.

    T4.20: Convergence failure handled gracefully
    T4.21: Parameter bounds enforced
    T4.22: Ill-conditioned covariance matrix
    T4.23: Data clipping/saturation detected
    T4.24: Insufficient data points for fit

    Args:
        exception: The exception that was raised (if any)
        params: Final parameter values (may contain NaN/inf)
        covariance: Covariance matrix (may be singular)
        n_iterations: Number of iterations performed
        max_iterations: Maximum allowed iterations
        data_t: Time data
        data_F: Fluorescence data
        bounds: Parameter bounds (lower, upper)

    Returns:
        ConvergenceFailureInfo with diagnosis
    """
    # T4.24: Check for insufficient data points
    if data_t is not None and len(data_t) < 4:
        return ConvergenceFailureInfo(
            failure_type=ConvergenceFailureType.INSUFFICIENT_POINTS.value,
            message=f"Only {len(data_t)} data points. Minimum 4 required for fitting.",
            severity=DiagnosticSeverity.ERROR,
            recoverable=False,
            suggested_action="Collect more data points or use simpler model.",
            details={"n_points": len(data_t), "minimum_required": 4}
        )

    # T4.23: Check for flat/saturated data
    if data_F is not None and len(data_F) > 1:
        data_range = np.max(data_F) - np.min(data_F)
        data_std = np.std(data_F)

        # Completely flat data
        if data_range < 1e-10 or data_std < 1e-10:
            return ConvergenceFailureInfo(
                failure_type=ConvergenceFailureType.FLAT_DATA.value,
                message="Data is completely flat. No kinetic signal detected.",
                severity=DiagnosticSeverity.ERROR,
                recoverable=False,
                suggested_action="Check data quality. Well may be empty or saturated.",
                details={"data_range": float(data_range), "data_std": float(data_std)}
            )

        # Saturated signal (at 65535 for 16-bit)
        max_val = np.max(data_F)
        if max_val >= 65535 or max_val >= 65000:
            sat_fraction = np.sum(data_F >= 65000) / len(data_F)
            if sat_fraction > 0.1:
                return ConvergenceFailureInfo(
                    failure_type=ConvergenceFailureType.DATA_SATURATION.value,
                    message=f"Signal appears saturated ({sat_fraction*100:.1f}% at max).",
                    severity=DiagnosticSeverity.WARNING,
                    recoverable=True,
                    suggested_action="Reduce gain or dilute sample. Fit parameters may be biased.",
                    details={"saturation_fraction": float(sat_fraction), "max_value": float(max_val)}
                )

    # T4.20: Check for NaN parameters
    if params is not None and np.any(np.isnan(params)):
        return ConvergenceFailureInfo(
            failure_type=ConvergenceFailureType.NAN_PARAMETERS.value,
            message="Optimization produced NaN parameter values.",
            severity=DiagnosticSeverity.ERROR,
            recoverable=True,
            suggested_action="Try different initial parameters or constrain parameter bounds.",
            details={"nan_params": [i for i, p in enumerate(params) if np.isnan(p)]}
        )

    # Check for gradient explosion (inf values)
    if params is not None and np.any(np.isinf(params)):
        return ConvergenceFailureInfo(
            failure_type=ConvergenceFailureType.GRADIENT_EXPLOSION.value,
            message="Optimization diverged to infinity.",
            severity=DiagnosticSeverity.ERROR,
            recoverable=True,
            suggested_action="Constrain parameter bounds more tightly.",
            details={"inf_params": [i for i, p in enumerate(params) if np.isinf(p)]}
        )

    # T4.21: Check for parameters at bounds
    if params is not None and bounds is not None:
        lower, upper = bounds
        at_lower = np.isclose(params, lower, rtol=1e-6)
        at_upper = np.isclose(params, upper, rtol=1e-6)
        if np.any(at_lower) or np.any(at_upper):
            return ConvergenceFailureInfo(
                failure_type=ConvergenceFailureType.PARAMETER_AT_BOUND.value,
                message="One or more parameters converged to boundary.",
                severity=DiagnosticSeverity.WARNING,
                recoverable=True,
                suggested_action="Review parameter bounds or check data quality.",
                details={
                    "at_lower": [i for i, b in enumerate(at_lower) if b],
                    "at_upper": [i for i, b in enumerate(at_upper) if b]
                }
            )

    # T4.22: Check for ill-conditioned covariance
    if covariance is not None:
        try:
            if np.any(np.isnan(covariance)) or np.any(np.isinf(covariance)):
                return ConvergenceFailureInfo(
                    failure_type=ConvergenceFailureType.ILL_CONDITIONED.value,
                    message="Covariance matrix contains NaN/inf values.",
                    severity=DiagnosticSeverity.WARNING,
                    recoverable=True,
                    suggested_action="Parameters may be poorly determined. Use caution with uncertainties."
                )

            cond_num = np.linalg.cond(covariance)
            if cond_num > 1e10:
                return ConvergenceFailureInfo(
                    failure_type=ConvergenceFailureType.ILL_CONDITIONED.value,
                    message=f"Covariance matrix is ill-conditioned (condition number: {cond_num:.2e}).",
                    severity=DiagnosticSeverity.WARNING,
                    recoverable=True,
                    suggested_action="Parameter uncertainties may be unreliable.",
                    details={"condition_number": float(cond_num)}
                )

            # Check for near-singular
            eigvals = np.linalg.eigvalsh(covariance)
            if np.min(eigvals) < 1e-15:
                return ConvergenceFailureInfo(
                    failure_type=ConvergenceFailureType.SINGULAR_MATRIX.value,
                    message="Covariance matrix is singular or near-singular.",
                    severity=DiagnosticSeverity.WARNING,
                    recoverable=True,
                    suggested_action="Some parameters may be highly correlated or unidentifiable.",
                    details={"min_eigenvalue": float(np.min(eigvals))}
                )

            # Check for high parameter correlation
            diag = np.sqrt(np.diag(covariance))
            if np.all(diag > 0):
                corr = covariance / np.outer(diag, diag)
                np.fill_diagonal(corr, 0)
                max_corr = np.max(np.abs(corr))
                if max_corr > HIGH_CORRELATION_THRESHOLD:
                    return ConvergenceFailureInfo(
                        failure_type=ConvergenceFailureType.PARAMETER_CORRELATION.value,
                        message=f"Parameters are highly correlated (max |r| = {max_corr:.3f}).",
                        severity=DiagnosticSeverity.WARNING,
                        recoverable=True,
                        suggested_action="Consider using a simpler model or fixing some parameters.",
                        details={"max_correlation": float(max_corr)}
                    )

        except Exception as e:
            logger.warning(f"Error analyzing covariance: {e}")

    # T4.20: Check for max iterations exceeded
    if n_iterations >= max_iterations:
        return ConvergenceFailureInfo(
            failure_type=ConvergenceFailureType.MAX_ITERATIONS.value,
            message=f"Maximum iterations ({max_iterations}) exceeded without convergence.",
            severity=DiagnosticSeverity.WARNING,
            recoverable=True,
            suggested_action="Try different initial parameters or increase max iterations.",
            details={"n_iterations": n_iterations, "max_iterations": max_iterations}
        )

    # Generic exception-based diagnosis
    if exception is not None:
        exc_str = str(exception).lower()
        if 'singular' in exc_str or 'svd' in exc_str:
            return ConvergenceFailureInfo(
                failure_type=ConvergenceFailureType.SINGULAR_MATRIX.value,
                message=f"Singular matrix encountered: {exception}",
                severity=DiagnosticSeverity.ERROR,
                recoverable=True,
                suggested_action="Data may not support all model parameters."
            )
        elif 'overflow' in exc_str or 'inf' in exc_str:
            return ConvergenceFailureInfo(
                failure_type=ConvergenceFailureType.GRADIENT_EXPLOSION.value,
                message=f"Numerical overflow: {exception}",
                severity=DiagnosticSeverity.ERROR,
                recoverable=True,
                suggested_action="Constrain parameter bounds."
            )

        return ConvergenceFailureInfo(
            failure_type="unknown",
            message=f"Convergence failed: {exception}",
            severity=DiagnosticSeverity.ERROR,
            recoverable=True,
            suggested_action="Try different initial parameters."
        )

    # No specific failure identified
    return ConvergenceFailureInfo(
        failure_type="unknown",
        message="Convergence failed for unknown reason.",
        severity=DiagnosticSeverity.ERROR,
        recoverable=True,
        suggested_action="Try different initial parameters or check data quality."
    )


@dataclass
class SampleSizeRecommendation:
    """
    Sample size recommendation with edge case handling.

    T7.9-T7.11: Extreme sample size recommendations
    """
    recommended_n: int
    is_achievable: bool = True
    warnings: List[DiagnosticMessage] = field(default_factory=list)

    # Input parameters
    target_precision: float = 0.3
    current_variance: float = 0.0
    current_n: int = 0

    # Computed values
    required_variance_reduction: float = 0.0


def compute_sample_size_recommendation(
    target_precision: float,
    current_variance: float,
    current_n: int,
    min_n: int = 4,
    max_practical_n: int = 500
) -> SampleSizeRecommendation:
    """
    Compute sample size recommendation with edge case handling.

    T7.9: Extreme sample size recommendations
    T7.10: Zero variance construct power analysis
    T7.11: Precision target extremes

    Args:
        target_precision: Target CI width (e.g., 0.3 for ±0.15)
        current_variance: Current variance estimate
        current_n: Current sample size
        min_n: Minimum practical sample size
        max_practical_n: Maximum practical sample size to recommend

    Returns:
        SampleSizeRecommendation with recommended n and warnings
    """
    result = SampleSizeRecommendation(
        recommended_n=current_n,
        target_precision=target_precision,
        current_variance=current_variance,
        current_n=current_n
    )

    # T7.11: Handle extreme precision targets
    if target_precision <= 0:
        result.is_achievable = False
        result.warnings.append(DiagnosticMessage(
            code="PRECISION_INVALID",
            message="Target precision must be positive.",
            severity=DiagnosticSeverity.ERROR,
            details={"target_precision": target_precision}
        ))
        return result

    if target_precision < 0.01:
        result.warnings.append(DiagnosticMessage(
            code="PRECISION_VERY_TIGHT",
            message=f"Target precision {target_precision:.3f} is extremely tight. May require impractically large samples.",
            severity=DiagnosticSeverity.WARNING,
            details={"target_precision": target_precision}
        ))

    if target_precision > 10:
        result.warnings.append(DiagnosticMessage(
            code="PRECISION_VERY_LOOSE",
            message=f"Target precision {target_precision:.1f} is very loose. Current data likely already meets target.",
            severity=DiagnosticSeverity.INFO,
            details={"target_precision": target_precision}
        ))
        result.recommended_n = max(min_n, 1)
        return result

    # T7.10: Handle zero/near-zero variance
    if current_variance <= 0:
        result.warnings.append(DiagnosticMessage(
            code="VARIANCE_ZERO",
            message="Zero or negative variance. Cannot compute sample size.",
            severity=DiagnosticSeverity.ERROR,
            details={"current_variance": current_variance}
        ))
        result.recommended_n = min_n
        result.is_achievable = False
        return result

    if current_variance < 1e-10:
        result.warnings.append(DiagnosticMessage(
            code="VARIANCE_NEAR_ZERO",
            message=f"Variance is extremely low ({current_variance:.2e}). Data may have no true variability.",
            severity=DiagnosticSeverity.WARNING,
            details={"current_variance": current_variance}
        ))
        result.recommended_n = min_n
        return result

    # Compute required sample size
    # CI width ≈ 2 * z * sqrt(variance / n)
    # For 95% CI, z ≈ 1.96
    # target_precision = 2 * 1.96 * sqrt(variance / n)
    # n = (2 * 1.96)^2 * variance / target_precision^2

    z = 1.96
    required_n = int(np.ceil((2 * z) ** 2 * current_variance / (target_precision ** 2)))

    # T7.9: Handle extreme sample size requirements
    if required_n < min_n:
        result.recommended_n = min_n
        result.warnings.append(DiagnosticMessage(
            code="SAMPLE_SIZE_SMALL",
            message=f"Calculated n={required_n} is below minimum. Recommending n={min_n}.",
            severity=DiagnosticSeverity.INFO,
            details={"calculated_n": required_n, "recommended_n": min_n}
        ))
        return result

    if required_n > 10000:
        result.is_achievable = False
        result.recommended_n = max_practical_n
        result.warnings.append(DiagnosticMessage(
            code="SAMPLE_SIZE_INFINITE",
            message=f"Required n={required_n} is impractically large. Target may be unachievable.",
            severity=DiagnosticSeverity.ERROR,
            details={"calculated_n": required_n, "practical_max": max_practical_n}
        ))
        return result

    if required_n > max_practical_n:
        result.is_achievable = False
        result.recommended_n = max_practical_n
        result.warnings.append(DiagnosticMessage(
            code="SAMPLE_SIZE_LARGE",
            message=f"Required n={required_n} exceeds practical limit ({max_practical_n}). Consider relaxing precision target.",
            severity=DiagnosticSeverity.WARNING,
            details={"calculated_n": required_n, "practical_max": max_practical_n}
        ))
        return result

    result.recommended_n = required_n
    result.required_variance_reduction = 1 - (target_precision ** 2) / (4 * z ** 2 * current_variance / current_n) if current_n > 0 else 0

    return result
