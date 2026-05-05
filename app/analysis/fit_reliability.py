"""Fit reliability evaluation.

Replaces the simple R^2 gate with a multi-metric evaluator that flags fits as
GOOD / OK / WEAK / BAD based on extrapolation, statistical outliers, shape
quality, and R^2. Operates on stored fit metrics + a user-tunable
ReliabilityThresholds dataclass; no DB writes happen here.
"""
from __future__ import annotations

import dataclasses
import enum
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.analysis import constants


class ReliabilityFlag(str, enum.Enum):
    """Overall reliability classification."""

    GOOD = "GOOD"
    OK = "OK"
    WEAK = "WEAK"
    BAD = "BAD"

    def __str__(self) -> str:
        return self.value


class FilterReason(str, enum.Enum):
    """Specific reason a fit was flagged."""

    OK = "OK"
    LOW_R2 = "LOW_R2"
    EXTRAPOLATED_FMAX = "EXTRAPOLATED_FMAX"
    HIGH_FMAX_SE = "HIGH_FMAX_SE"
    POOR_SHAPE = "POOR_SHAPE"
    OUTLIER = "OUTLIER"

    def __str__(self) -> str:
        return self.value


@dataclass
class ReliabilityThresholds:
    """User-tunable thresholds for the reliability evaluator.

    All values default to the constants in app.analysis.constants. Constructed
    fresh from UI sliders on each Apply Filter click so changes are live.
    """

    r2_threshold: float = constants.DEFAULT_RELIABILITY_R2_THRESHOLD
    pct_plateau_bad: float = constants.PCT_PLATEAU_BAD
    pct_plateau_weak: float = constants.PCT_PLATEAU_WEAK
    pct_plateau_good: float = constants.PCT_PLATEAU_GOOD
    f_max_se_pct_bad: float = constants.F_MAX_SE_PCT_BAD
    f_max_se_pct_weak: float = constants.F_MAX_SE_PCT_WEAK
    f_max_se_pct_good: float = constants.F_MAX_SE_PCT_GOOD
    # Shape: Durbin-Watson statistic must lie in [shape_dw_low, shape_dw_high]
    # (DW≈2 means no autocorrelation). Replaces the Shapiro-Wilk normality
    # alpha which over-fired on long traces.
    shape_dw_low: float = constants.SHAPE_DW_LOW
    shape_dw_high: float = constants.SHAPE_DW_HIGH
    shape_rmse_frac_bad: float = constants.SHAPE_RMSE_FRAC_BAD
    # Outlier: fractional deviation rule. |x - median| / |median| > threshold
    # is more interpretable than 3·MAD on tight replicate clusters.
    outlier_fraction_threshold: float = constants.OUTLIER_FRAC_THRESHOLD
    outlier_min_group_size: int = constants.OUTLIER_MIN_GROUP_SIZE

    # UI toggles. Shape checking is OFF by default: the Durbin-Watson statistic
    # on raw fluorescence residuals doesn't discriminate fit quality at typical
    # IVT trace lengths (residuals are always temporally smooth, regardless of
    # whether the model fits well). The DW value is still computed and stored
    # on every fit so users can inspect it; flip this to True to enable gating.
    check_outliers: bool = True
    check_shape: bool = False

    # Action
    exclude_weak: bool = False  # If True, WEAK is excluded along with BAD


@dataclass
class ReliabilityResult:
    """Per-fit evaluation output."""

    flag: ReliabilityFlag
    reasons: List[FilterReason] = field(default_factory=list)
    f_max_se_pct: Optional[float] = None
    rmse_frac: Optional[float] = None

    @property
    def is_excluded(self) -> bool:
        """Default action: exclude only BAD fits.

        For threshold-aware exclusion (honoring ``exclude_weak``), call
        :meth:`is_excluded_by` instead.
        """
        return self.flag == ReliabilityFlag.BAD

    def is_excluded_by(self, thresholds: "ReliabilityThresholds") -> bool:
        """Return True iff this fit should be excluded under the given thresholds."""
        if self.flag == ReliabilityFlag.BAD:
            return True
        if thresholds.exclude_weak and self.flag == ReliabilityFlag.WEAK:
            return True
        return False


def _f_max_se_pct(fit: Any) -> Optional[float]:
    f_max = getattr(fit, "f_max", None)
    f_max_se = getattr(fit, "f_max_se", None)
    if f_max is None or f_max_se is None:
        return None
    if f_max == 0:
        return None
    return 100.0 * abs(f_max_se) / abs(f_max)


def _rmse_frac(fit: Any) -> Optional[float]:
    rmse = getattr(fit, "rmse", None)
    mean_signal = getattr(fit, "mean_signal", None)
    if rmse is None or mean_signal is None:
        return None
    if not mean_signal:
        return None
    return abs(rmse) / abs(mean_signal)


def _classify_three_tier(
    value: Optional[float],
    bad_cut: float,
    weak_cut: float,
    good_cut: float,
    *,
    higher_is_better: bool,
) -> ReliabilityFlag:
    """Map a metric to GOOD/OK/WEAK/BAD using three thresholds.

    With higher_is_better=True (e.g. plateau-reached):
      value >= good_cut  -> GOOD
      value >= weak_cut  -> OK
      value >= bad_cut   -> WEAK
      value <  bad_cut   -> BAD

    With higher_is_better=False (e.g. fmax SE %):
      value <= good_cut -> GOOD
      value <= weak_cut -> OK
      value <= bad_cut  -> WEAK
      value >  bad_cut  -> BAD
    """
    if value is None:
        return ReliabilityFlag.OK  # unknown -> don't penalize
    if higher_is_better:
        if value >= good_cut:
            return ReliabilityFlag.GOOD
        if value >= weak_cut:
            return ReliabilityFlag.OK
        if value >= bad_cut:
            return ReliabilityFlag.WEAK
        return ReliabilityFlag.BAD
    # lower-is-better
    if value <= good_cut:
        return ReliabilityFlag.GOOD
    if value <= weak_cut:
        return ReliabilityFlag.OK
    if value <= bad_cut:
        return ReliabilityFlag.WEAK
    return ReliabilityFlag.BAD


_FLAG_RANK = {
    ReliabilityFlag.GOOD: 0,
    ReliabilityFlag.OK: 1,
    ReliabilityFlag.WEAK: 2,
    ReliabilityFlag.BAD: 3,
}


def _worse(a: ReliabilityFlag, b: ReliabilityFlag) -> ReliabilityFlag:
    return a if _FLAG_RANK[a] >= _FLAG_RANK[b] else b


def evaluate(
    fit: Any,
    *,
    thresholds: ReliabilityThresholds,
    is_outlier: bool = False,
) -> ReliabilityResult:
    """Evaluate a single fit's reliability.

    Args:
        fit: Object with f_max, f_max_se, k_obs, t_lag, r_squared, rmse,
            residual_autocorr_dw, pct_plateau_reached, mean_signal.
            Either a FitResult ORM model or any equivalent duck-typed object.
        thresholds: User-tunable cutoffs.
        is_outlier: Whether the per-group fractional check (computed externally
            over a replicate set) classified this fit as an outlier. Pass False
            to skip.

    Returns:
        ReliabilityResult with overall flag + list of failing reasons.
    """
    reasons: List[FilterReason] = []
    overall = ReliabilityFlag.GOOD

    # R^2
    r2 = getattr(fit, "r_squared", None)
    if r2 is not None and r2 < thresholds.r2_threshold:
        reasons.append(FilterReason.LOW_R2)
        overall = _worse(overall, ReliabilityFlag.BAD)

    # Plateau reached (extrapolation check) — higher is better
    plateau = getattr(fit, "pct_plateau_reached", None)
    plateau_flag = _classify_three_tier(
        plateau,
        bad_cut=thresholds.pct_plateau_bad,
        weak_cut=thresholds.pct_plateau_weak,
        good_cut=thresholds.pct_plateau_good,
        higher_is_better=True,
    )
    if plateau_flag in (ReliabilityFlag.WEAK, ReliabilityFlag.BAD):
        reasons.append(FilterReason.EXTRAPOLATED_FMAX)
    overall = _worse(overall, plateau_flag)

    # F_max SE % — lower is better
    f_max_se_pct_val = _f_max_se_pct(fit)
    fmax_flag = _classify_three_tier(
        f_max_se_pct_val,
        bad_cut=thresholds.f_max_se_pct_bad,
        weak_cut=thresholds.f_max_se_pct_weak,
        good_cut=thresholds.f_max_se_pct_good,
        higher_is_better=False,
    )
    if fmax_flag in (ReliabilityFlag.WEAK, ReliabilityFlag.BAD):
        reasons.append(FilterReason.HIGH_FMAX_SE)
    overall = _worse(overall, fmax_flag)

    # Shape (residual autocorrelation + RMSE/mean). Durbin-Watson stays
    # informative on long traces where Ljung-Box p-values saturate to ~0.
    rmse_frac_val = _rmse_frac(fit)
    if thresholds.check_shape:
        dw = getattr(fit, "residual_autocorr_dw", None)
        bad_autocorr = dw is not None and (
            dw < thresholds.shape_dw_low or dw > thresholds.shape_dw_high
        )
        bad_rmse = (
            rmse_frac_val is not None and rmse_frac_val > thresholds.shape_rmse_frac_bad
        )
        if bad_autocorr or bad_rmse:
            reasons.append(FilterReason.POOR_SHAPE)
            overall = _worse(overall, ReliabilityFlag.WEAK)

    # Outlier
    if thresholds.check_outliers and is_outlier:
        reasons.append(FilterReason.OUTLIER)
        overall = _worse(overall, ReliabilityFlag.WEAK)

    if not reasons:
        reasons = [FilterReason.OK]

    return ReliabilityResult(
        flag=overall,
        reasons=reasons,
        f_max_se_pct=f_max_se_pct_val,
        rmse_frac=rmse_frac_val,
    )


def _median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def detect_outliers(
    fits: Iterable[Any],
    *,
    group_key,
    thresholds: ReliabilityThresholds,
    metrics: Tuple[str, ...] = ("f_max", "k_obs", "t_lag"),
) -> Dict[int, bool]:
    """Detect outliers within replicate groups via fractional deviation.

    A fit is flagged as an outlier if any of its metric values satisfies
    ``|value - median| / |median| > outlier_fraction_threshold`` against
    its replicate group's median. Groups smaller than
    ``outlier_min_group_size`` are skipped, as are groups whose median is
    zero (the fractional rule is undefined).

    Compared to a 3·MAD rule, the fractional rule is:
      * Interpretable — "more than X% deviation from the median".
      * Robust on tightly-clustered data, where MAD shrinks toward zero and
        any small departure trips the gate.

    Args:
        fits: Iterable of fit objects with .id and the named metric attributes.
        group_key: Callable taking a fit and returning a hashable group key.
        thresholds: Threshold dataclass.
        metrics: Attribute names to check.

    Returns:
        Dict mapping fit.id -> True if outlier, False otherwise.
    """
    groups: Dict[Any, List[Any]] = defaultdict(list)
    for fit in fits:
        groups[group_key(fit)].append(fit)

    flags: Dict[int, bool] = {}
    frac = thresholds.outlier_fraction_threshold
    min_n = thresholds.outlier_min_group_size

    for members in groups.values():
        for fit in members:
            flags.setdefault(fit.id, False)
        if len(members) < min_n:
            continue
        for metric in metrics:
            values: List[Tuple[Any, float]] = []
            for fit in members:
                v = getattr(fit, metric, None)
                if v is None:
                    continue
                values.append((fit, float(v)))
            if len(values) < min_n:
                continue
            med = _median([v for _, v in values])
            denom = abs(med)
            # Skip when the median is essentially zero — the fractional rule
            # is undefined and would otherwise inflate trivial deviations.
            if denom < 1e-8:
                continue
            for fit, v in values:
                if abs(v - med) / denom > frac:
                    flags[fit.id] = True

    return flags


def evaluate_batch(
    fits: List[Any],
    *,
    thresholds: ReliabilityThresholds,
    group_key,
) -> Dict[int, ReliabilityResult]:
    """Evaluate a batch of fits, including replicate-group outlier detection.

    Args:
        fits: List of fit objects.
        thresholds: Threshold dataclass.
        group_key: Callable for outlier grouping.

    Returns:
        Dict mapping fit.id -> ReliabilityResult.
    """
    if thresholds.check_outliers:
        outliers = detect_outliers(fits, group_key=group_key, thresholds=thresholds)
    else:
        outliers = {}

    results: Dict[int, ReliabilityResult] = {}
    for fit in fits:
        results[fit.id] = evaluate(
            fit,
            thresholds=thresholds,
            is_outlier=bool(outliers.get(fit.id, False)),
        )
    return results


def thresholds_from_dict(payload: Dict[str, Any]) -> ReliabilityThresholds:
    """Construct ReliabilityThresholds from a (UI) dict, falling back to defaults."""
    valid_fields = {f.name for f in dataclasses.fields(ReliabilityThresholds)}
    overrides = {
        name: value
        for name, value in payload.items()
        if name in valid_fields and value is not None
    }
    return dataclasses.replace(ReliabilityThresholds(), **overrides)


def reasons_to_label(reasons: List[FilterReason]) -> str:
    """Compact label for a list of filter reasons (for badge tooltips)."""
    if not reasons or reasons == [FilterReason.OK]:
        return "OK"
    seen = []
    for r in reasons:
        if r is FilterReason.OK:
            continue
        if r not in seen:
            seen.append(r)
    return ", ".join(r.value for r in seen)
