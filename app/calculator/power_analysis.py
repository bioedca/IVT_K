"""Power analysis functions for IVT experiment planning.

Tier-aware power analysis for planning experiments and estimating required
sample sizes to achieve target precision.

Supports adaptive model complexity:
- Tier 1 (residual only): Uses conservative prior for session variance
- Tier 2a (session + residual): SE = sqrt[τ_session²/n_s + τ_residual²/(n_s*n_r)]
- Tier 2b (plate + residual): SE = sqrt[τ_plate²/n_p + τ_residual²/(n_p*n_r)]
- Tier 3 (full hierarchy): SE = sqrt[τ_session²/n_s + τ_plate²/(n_s*n_p) + τ_residual²/(n_s*n_p*n_r)]
"""
from dataclasses import dataclass
from enum import Enum
from math import ceil, sqrt

import scipy.stats as stats


class ModelTierForPower(Enum):
    """Model tiers for power analysis (mirrors bayesian.ModelTier)."""
    TIER_1_RESIDUAL_ONLY = "tier_1"
    TIER_2A_SESSION = "tier_2a"
    TIER_2B_PLATE = "tier_2b"
    TIER_3_FULL = "tier_3"


@dataclass
class VarianceComponentsForPower:
    """Variance components for hierarchical SE calculation."""
    var_session: float | None = None  # τ²_session
    var_plate: float | None = None    # τ²_plate
    var_residual: float = 0.09           # σ²_residual (default)

    # Default priors for components not yet estimable
    prior_var_session: float = 0.04      # Conservative prior τ²_session
    prior_var_plate: float = 0.02        # Conservative prior τ²_plate


@dataclass
class HierarchicalSampleSizeResult:
    """Result of tier-aware sample size calculation."""
    n_sessions_required: int
    n_plates_per_session: int
    n_replicates_per_plate: int
    current_n_sessions: int
    current_n_plates_per_session: int
    current_n_replicates: int
    additional_sessions_needed: int
    additional_plates_needed: int
    additional_replicates_needed: int
    target_ci_width: float
    current_ci_width: float | None
    current_se: float | None
    projected_se: float
    tier: str
    recommendation_text: str
    recommendation_unit: str  # "sessions", "plates", or "replicates"


@dataclass
class PowerResult:
    """Result of power calculation."""
    power: float
    sample_size: int
    effect_size: float
    alpha: float
    description: str


@dataclass
class SampleSizeResult:
    """Result of sample size calculation."""
    n_required: int
    current_n: int
    additional_needed: int
    target_ci_width: float
    current_ci_width: float | None
    description: str


def calculate_power_for_fold_change(
    n: int,
    effect_size: float,
    sigma: float,
    alpha: float = 0.05,
) -> float:
    """
    Calculate power to detect a fold change effect.

    Uses two-sided t-test power calculation for log fold change.

    Args:
        n: Sample size (number of replicates)
        effect_size: Expected log fold change (e.g., log2(1.5) = 0.58)
        sigma: Standard deviation of log fold change
        alpha: Significance level

    Returns:
        Statistical power (0-1)
    """
    if n < 2 or sigma <= 0:
        return 0.0

    # Non-centrality parameter: effect_size / (sigma / sqrt(n))
    se = sigma / sqrt(n)
    ncp = abs(effect_size) / se

    # Critical value for two-sided test
    t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)

    # Power = P(|T| > t_crit | H1)
    # For non-central t distribution
    power = 1 - stats.nct.cdf(t_crit, df=n - 1, nc=ncp) + stats.nct.cdf(-t_crit, df=n - 1, nc=ncp)

    return min(1.0, max(0.0, power))


def calculate_sample_size_for_power(
    effect_size: float,
    sigma: float,
    target_power: float = 0.80,
    alpha: float = 0.05,
    max_n: int = 100,
) -> int:
    """
    Calculate required sample size to achieve target power.

    Args:
        effect_size: Expected log fold change
        sigma: Standard deviation of log fold change
        target_power: Desired power level (default 80%)
        alpha: Significance level
        max_n: Maximum sample size to consider

    Returns:
        Required sample size
    """
    if effect_size == 0 or sigma <= 0:
        return max_n

    # Iteratively find required n
    for n in range(2, max_n + 1):
        power = calculate_power_for_fold_change(n, effect_size, sigma, alpha)
        if power >= target_power:
            return n

    return max_n


def calculate_ci_width(se: float, n: int, confidence: float = 0.95) -> float:
    """
    Calculate confidence interval width.

    CI width = 2 * t_crit * SE

    Args:
        se: Standard error
        n: Sample size
        confidence: Confidence level

    Returns:
        CI width (full width, not half-width)
    """
    if n < 2:
        return float('inf')

    alpha = 1 - confidence
    t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)
    return 2 * t_crit * se


def calculate_se_from_ci_width(ci_width: float, n: int, confidence: float = 0.95) -> float:
    """
    Calculate standard error from CI width.

    SE = CI_width / (2 * t_crit)

    Args:
        ci_width: Confidence interval width
        n: Sample size
        confidence: Confidence level

    Returns:
        Standard error
    """
    if n < 2 or ci_width <= 0:
        return float('inf')

    alpha = 1 - confidence
    t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)
    return ci_width / (2 * t_crit)


def calculate_sample_size_for_precision(
    current_ci_width: float | None,
    current_n: int,
    target_ci_width: float,
    confidence: float = 0.95,
) -> SampleSizeResult:
    """
    Calculate sample size needed to achieve target CI width.

    Uses the relationship: SE ∝ 1/√n, so CI_width ∝ 1/√n

    Args:
        current_ci_width: Current CI width (None if no data)
        current_n: Current sample size (0 if no data)
        target_ci_width: Desired CI width
        confidence: Confidence level

    Returns:
        SampleSizeResult with required and additional samples
    """
    # Minimum replicates for statistical validity
    MIN_REPLICATES = 4

    if current_ci_width is None or current_n == 0:
        # No data - use minimum replicates
        return SampleSizeResult(
            n_required=MIN_REPLICATES,
            current_n=0,
            additional_needed=MIN_REPLICATES,
            target_ci_width=target_ci_width,
            current_ci_width=None,
            description="Starting point for new construct",
        )

    if current_ci_width <= target_ci_width:
        # Already at target
        return SampleSizeResult(
            n_required=current_n,
            current_n=current_n,
            additional_needed=0,
            target_ci_width=target_ci_width,
            current_ci_width=current_ci_width,
            description=f"Target precision achieved (CI: ±{current_ci_width / 2:.2f})",
        )

    # SE scales as σ/√n, so n_required = (current_se/target_se)² * current_n
    # Since CI ∝ SE, we can use the CI ratio directly:
    ratio = current_ci_width / target_ci_width
    n_required = ceil(current_n * ratio ** 2)
    n_required = max(n_required, MIN_REPLICATES)

    additional_needed = max(0, n_required - current_n)

    # Estimate plates needed (assuming 4 replicates per plate)
    plates_needed = ceil(additional_needed / 4) if additional_needed > 0 else 0

    description = f"Need ~{additional_needed} more replicates"
    if plates_needed > 0:
        description += f" (~{plates_needed} plate{'s' if plates_needed > 1 else ''})"

    return SampleSizeResult(
        n_required=n_required,
        current_n=current_n,
        additional_needed=additional_needed,
        target_ci_width=target_ci_width,
        current_ci_width=current_ci_width,
        description=description,
    )


def estimate_precision_improvement(
    current_ci_width: float,
    current_n: int,
    additional_n: int,
) -> float:
    """
    Estimate CI width after adding more replicates.

    CI_new = CI_old * √(n_old / n_new)

    Args:
        current_ci_width: Current CI width
        current_n: Current sample size
        additional_n: Additional replicates to add

    Returns:
        Estimated new CI width
    """
    if current_n == 0 or additional_n < 0:
        return current_ci_width

    new_n = current_n + additional_n
    if new_n == 0:
        return float('inf')

    # CI scales as 1/√n
    return current_ci_width * sqrt(current_n / new_n)


def calculate_precision_gap_score(
    current_ci_width: float | None,
    target_ci_width: float,
) -> float:
    """
    Calculate precision gap score for recommendation system.

    Score = (Current_CI - Target_CI) / Target_CI * 100, normalized to 0-100

    Args:
        current_ci_width: Current CI width (None if no data)
        target_ci_width: Target CI width

    Returns:
        Precision gap score (0-100)
    """
    if current_ci_width is None:
        # No data - return moderate score (untested score handles this separately)
        return 50.0

    if current_ci_width <= target_ci_width:
        # At or below target
        return 0.0

    gap_ratio = (current_ci_width - target_ci_width) / target_ci_width
    # Normalize: 0% gap = 0, 100% gap = 100, cap at 100
    return min(100.0, gap_ratio * 100.0)


def calculate_untested_score(has_data: bool) -> float:
    """
    Calculate untested score for recommendation system.

    Fixed 100 for constructs with zero data; 0 otherwise.

    Args:
        has_data: Whether construct has any uploaded data

    Returns:
        Untested score (0 or 100)
    """
    return 0.0 if has_data else 100.0


def estimate_coplating_benefit(
    constructs_on_plate: list,
    new_construct_family: str,
    families_on_plate: set,
) -> float:
    """
    Estimate co-plating benefit score.

    Benefits from:
    - Having WT and mutants on same plate (direct comparison)
    - Reducing total plates needed

    Args:
        constructs_on_plate: Current constructs planned
        new_construct_family: Family of construct being considered
        families_on_plate: Set of families already on plate

    Returns:
        Co-plating benefit score (0-100)
    """
    if not constructs_on_plate:
        # First construct - neutral
        return 50.0

    # Benefit if same family as existing constructs (enables direct comparison)
    if new_construct_family in families_on_plate:
        return 80.0

    # Adding new family requires new WT - moderate benefit
    return 30.0


# =============================================================================
# Tier-Aware Hierarchical Power Analysis (PRD Section 3.12, Adaptive Complexity)
# =============================================================================

def calculate_hierarchical_se(
    n_sessions: int,
    n_plates_per_session: int,
    n_replicates_per_plate: int,
    var_session: float | None,
    var_plate: float | None,
    var_residual: float,
    tier: str = "tier_2a",
) -> float:
    """
    Calculate standard error using hierarchical variance formula.

    SE formulas by tier:
    - Tier 1: SE = sqrt[τ²_session_prior/1 + σ²_residual/(1*n_r)]
    - Tier 2a: SE = sqrt[τ²_session/n_s + σ²_residual/(n_s*n_r)]
    - Tier 2b: SE = sqrt[τ²_plate/n_p + σ²_residual/(n_p*n_r)]
    - Tier 3: SE = sqrt[τ²_session/n_s + τ²_plate/(n_s*n_p) + σ²_residual/(n_s*n_p*n_r)]

    Args:
        n_sessions: Number of sessions
        n_plates_per_session: Plates per session (1 for Tier 2a)
        n_replicates_per_plate: Replicates per plate
        var_session: Session variance (τ²_session), None if not estimated
        var_plate: Plate variance (τ²_plate), None if not estimated
        var_residual: Residual variance (σ²_residual)
        tier: Model tier string ("tier_1", "tier_2a", "tier_2b", "tier_3")

    Returns:
        Standard error of the mean estimate
    """
    # Use conservative priors for non-estimated components
    DEFAULT_VAR_SESSION = 0.04  # Conservative prior
    DEFAULT_VAR_PLATE = 0.02    # Conservative prior

    n_s = max(1, n_sessions)
    n_p = max(1, n_plates_per_session)
    n_r = max(1, n_replicates_per_plate)

    if tier == "tier_1":
        # Single session, single plate - use prior for session variance
        tau_session = var_session if var_session is not None else DEFAULT_VAR_SESSION
        se_squared = tau_session / 1 + var_residual / n_r
    elif tier == "tier_2a":
        # Multiple sessions, single plate per session
        tau_session = var_session if var_session is not None else DEFAULT_VAR_SESSION
        se_squared = tau_session / n_s + var_residual / (n_s * n_r)
    elif tier == "tier_2b":
        # Single session, multiple plates
        tau_plate = var_plate if var_plate is not None else DEFAULT_VAR_PLATE
        total_replicates = n_p * n_r
        se_squared = tau_plate / n_p + var_residual / total_replicates
    else:  # tier_3
        # Full hierarchy
        tau_session = var_session if var_session is not None else DEFAULT_VAR_SESSION
        tau_plate = var_plate if var_plate is not None else DEFAULT_VAR_PLATE
        total_obs = n_s * n_p * n_r
        se_squared = (
            tau_session / n_s +
            tau_plate / (n_s * n_p) +
            var_residual / total_obs
        )

    return sqrt(max(0, se_squared))


def calculate_tier_aware_sample_size(
    target_ci_width: float,
    variance_components: VarianceComponentsForPower | None = None,
    current_n_sessions: int = 0,
    current_n_plates_per_session: int = 1,
    current_n_replicates: int = 0,
    tier: str = "tier_2a",
    confidence: float = 0.95,
    replicates_per_plate: int = 4,
) -> HierarchicalSampleSizeResult:
    """
    Calculate sample size needed to achieve target CI width, respecting model tier.

    For Tier 1/2a (single-plate-per-session), recommends additional sessions.
    For Tier 2b/3 (multi-plate), may recommend plates or sessions.

    Args:
        target_ci_width: Target CI width
        variance_components: Variance components (uses defaults if None)
        current_n_sessions: Current number of sessions
        current_n_plates_per_session: Current plates per session (typically 1)
        current_n_replicates: Current total replicates
        tier: Model tier
        confidence: Confidence level (default 0.95)
        replicates_per_plate: Assumed replicates per plate for planning

    Returns:
        HierarchicalSampleSizeResult with tier-appropriate recommendations
    """
    if variance_components is None:
        variance_components = VarianceComponentsForPower()

    var_session = variance_components.var_session or variance_components.prior_var_session
    var_plate = variance_components.var_plate or variance_components.prior_var_plate
    var_residual = variance_components.var_residual

    # Calculate current SE if we have data
    current_se = None
    current_ci = None
    if current_n_sessions > 0 and current_n_replicates > 0:
        current_se = calculate_hierarchical_se(
            n_sessions=current_n_sessions,
            n_plates_per_session=current_n_plates_per_session,
            n_replicates_per_plate=current_n_replicates // max(1, current_n_sessions * current_n_plates_per_session),
            var_session=var_session if tier in ("tier_2a", "tier_3") else None,
            var_plate=var_plate if tier in ("tier_2b", "tier_3") else None,
            var_residual=var_residual,
            tier=tier,
        )
        alpha = 1 - confidence
        z_crit = stats.norm.ppf(1 - alpha / 2)
        current_ci = 2 * z_crit * current_se

    # Target SE from CI width
    alpha = 1 - confidence
    z_crit = stats.norm.ppf(1 - alpha / 2)
    target_se = target_ci_width / (2 * z_crit)

    # For Tier 1/2a, optimize sessions (single plate per session workflow)
    if tier in ("tier_1", "tier_2a"):
        # Find n_sessions needed
        # SE² = τ²_session/n_s + σ²_residual/(n_s * n_r)
        # SE² = (τ²_session + σ²_residual/n_r) / n_s
        # n_s = (τ²_session + σ²_residual/n_r) / SE²
        effective_var = var_session + var_residual / replicates_per_plate
        n_sessions_needed = ceil(effective_var / (target_se ** 2))
        n_sessions_needed = max(1, n_sessions_needed)

        additional_sessions = max(0, n_sessions_needed - current_n_sessions)

        # Calculate projected SE
        projected_se = calculate_hierarchical_se(
            n_sessions=n_sessions_needed,
            n_plates_per_session=1,
            n_replicates_per_plate=replicates_per_plate,
            var_session=var_session,
            var_plate=None,
            var_residual=var_residual,
            tier=tier,
        )

        if additional_sessions == 0:
            rec_text = f"Target precision achieved with {current_n_sessions} sessions."
        elif current_n_sessions == 0:
            rec_text = f"Run {n_sessions_needed} sessions to reach target precision (±{target_ci_width/2:.2f})."
        else:
            rec_text = f"Run {additional_sessions} more session{'s' if additional_sessions > 1 else ''} to reach target precision."

        return HierarchicalSampleSizeResult(
            n_sessions_required=n_sessions_needed,
            n_plates_per_session=1,
            n_replicates_per_plate=replicates_per_plate,
            current_n_sessions=current_n_sessions,
            current_n_plates_per_session=current_n_plates_per_session,
            current_n_replicates=current_n_replicates,
            additional_sessions_needed=additional_sessions,
            additional_plates_needed=additional_sessions,  # 1 plate per session
            additional_replicates_needed=additional_sessions * replicates_per_plate,
            target_ci_width=target_ci_width,
            current_ci_width=current_ci,
            current_se=current_se,
            projected_se=projected_se,
            tier=tier,
            recommendation_text=rec_text,
            recommendation_unit="sessions",
        )

    elif tier == "tier_2b":
        # Single session, optimize plates
        # SE² = τ²_plate/n_p + σ²_residual/(n_p * n_r)
        effective_var = var_plate + var_residual / replicates_per_plate
        n_plates_needed = ceil(effective_var / (target_se ** 2))
        n_plates_needed = max(1, n_plates_needed)

        current_plates = current_n_plates_per_session
        additional_plates = max(0, n_plates_needed - current_plates)

        projected_se = calculate_hierarchical_se(
            n_sessions=1,
            n_plates_per_session=n_plates_needed,
            n_replicates_per_plate=replicates_per_plate,
            var_session=None,
            var_plate=var_plate,
            var_residual=var_residual,
            tier=tier,
        )

        if additional_plates == 0:
            rec_text = f"Target precision achieved with {current_plates} plates."
        else:
            rec_text = (
                f"Run {additional_plates} more plate{'s' if additional_plates > 1 else ''} "
                f"to reach target. Consider running on additional days (sessions) "
                f"to separate session vs plate variance."
            )

        return HierarchicalSampleSizeResult(
            n_sessions_required=1,
            n_plates_per_session=n_plates_needed,
            n_replicates_per_plate=replicates_per_plate,
            current_n_sessions=1,
            current_n_plates_per_session=current_plates,
            current_n_replicates=current_n_replicates,
            additional_sessions_needed=0,
            additional_plates_needed=additional_plates,
            additional_replicates_needed=additional_plates * replicates_per_plate,
            target_ci_width=target_ci_width,
            current_ci_width=current_ci,
            current_se=current_se,
            projected_se=projected_se,
            tier=tier,
            recommendation_text=rec_text,
            recommendation_unit="plates",
        )

    else:  # tier_3
        # Full hierarchy - optimize sessions first, then plates
        # Start with current structure and find optimal
        best_n_sessions = current_n_sessions or 2
        best_n_plates = current_n_plates_per_session or 2

        # Iteratively find minimum sessions needed
        for n_s in range(max(2, current_n_sessions), 20):
            for n_p in range(max(1, current_n_plates_per_session), 10):
                se = calculate_hierarchical_se(
                    n_sessions=n_s,
                    n_plates_per_session=n_p,
                    n_replicates_per_plate=replicates_per_plate,
                    var_session=var_session,
                    var_plate=var_plate,
                    var_residual=var_residual,
                    tier=tier,
                )
                if se <= target_se:
                    best_n_sessions = n_s
                    best_n_plates = n_p
                    break
            else:
                continue
            break

        additional_sessions = max(0, best_n_sessions - current_n_sessions)
        additional_plates = max(0, best_n_sessions * best_n_plates -
                               current_n_sessions * current_n_plates_per_session)

        projected_se = calculate_hierarchical_se(
            n_sessions=best_n_sessions,
            n_plates_per_session=best_n_plates,
            n_replicates_per_plate=replicates_per_plate,
            var_session=var_session,
            var_plate=var_plate,
            var_residual=var_residual,
            tier=tier,
        )

        if additional_sessions == 0 and additional_plates == 0:
            rec_text = "Target precision achieved."
        else:
            rec_text = (
                f"Run {additional_sessions} more session{'s' if additional_sessions != 1 else ''} "
                f"with {best_n_plates} plate{'s' if best_n_plates != 1 else ''} each "
                f"to reach target precision."
            )

        return HierarchicalSampleSizeResult(
            n_sessions_required=best_n_sessions,
            n_plates_per_session=best_n_plates,
            n_replicates_per_plate=replicates_per_plate,
            current_n_sessions=current_n_sessions,
            current_n_plates_per_session=current_n_plates_per_session,
            current_n_replicates=current_n_replicates,
            additional_sessions_needed=additional_sessions,
            additional_plates_needed=additional_plates,
            additional_replicates_needed=additional_plates * replicates_per_plate,
            target_ci_width=target_ci_width,
            current_ci_width=current_ci,
            current_se=current_se,
            projected_se=projected_se,
            tier=tier,
            recommendation_text=rec_text,
            recommendation_unit="sessions" if additional_sessions > 0 else "plates",
        )


def get_tier_aware_recommendation_text(
    tier: str,
    additional_sessions: int,
    additional_plates: int,
    current_session_variance: float | None = None,
    target_achieved: bool = False,
) -> str:
    """
    Generate tier-aware recommendation text.

    Args:
        tier: Model tier
        additional_sessions: Sessions needed
        additional_plates: Plates needed
        current_session_variance: Current τ_session estimate
        target_achieved: Whether target is already achieved

    Returns:
        Human-readable recommendation string
    """
    if target_achieved:
        return "Target precision achieved."

    if tier == "tier_1":
        return (
            "Collect data from additional sessions to enable session-level "
            "variance estimation and improve precision."
        )
    elif tier == "tier_2a":
        tau_str = f" Current session variance: τ = {sqrt(current_session_variance):.3f}." if current_session_variance else ""
        return (
            f"Run {additional_sessions} more session{'s' if additional_sessions != 1 else ''} "
            f"to reach target.{tau_str}"
        )
    elif tier == "tier_2b":
        return (
            "Run experiments on additional days (sessions) to separate "
            "session vs plate variance. Currently have data from single session."
        )
    else:  # tier_3
        return (
            f"Full hierarchical model active. Need {additional_sessions} more sessions "
            f"to reach target precision."
        )


def detect_tier_from_data_structure(
    n_sessions: int,
    max_plates_per_session: int,
) -> str:
    """
    Detect model tier from data structure.

    Args:
        n_sessions: Number of sessions
        max_plates_per_session: Maximum plates in any session

    Returns:
        Tier string
    """
    if n_sessions == 1 and max_plates_per_session <= 1:
        return "tier_1"
    elif n_sessions >= 2 and max_plates_per_session <= 1:
        return "tier_2a"
    elif n_sessions == 1 and max_plates_per_session >= 2:
        return "tier_2b"
    else:
        return "tier_3"
