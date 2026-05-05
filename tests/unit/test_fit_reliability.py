"""Unit tests for app.analysis.fit_reliability."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from app.analysis.fit_reliability import (
    FilterReason,
    ReliabilityFlag,
    ReliabilityThresholds,
    detect_outliers,
    evaluate,
    evaluate_batch,
    reasons_to_label,
    thresholds_from_dict,
)
from app.services.fit_computation_service import compute_pct_plateau_reached


@dataclass
class _Fit:
    """Minimal duck-typed fit object for evaluator tests."""

    id: int = 1
    # Default values land squarely in GOOD territory for the calibrated defaults
    # so each test exercises a single failure mode.
    f_max: Optional[float] = 1000.0
    f_max_se: Optional[float] = 10.0
    k_obs: Optional[float] = 0.05
    t_lag: Optional[float] = 1.0
    r_squared: Optional[float] = 0.99
    rmse: Optional[float] = 5.0
    residual_normality_pvalue: Optional[float] = 0.5
    residual_autocorr_dw: Optional[float] = 2.0  # uncorrelated residuals
    pct_plateau_reached: Optional[float] = 0.99
    mean_signal: Optional[float] = 500.0


# --------------------------------------------------------------------------- #
# Durbin-Watson helper
# --------------------------------------------------------------------------- #


def test_durbin_watson_white_noise_near_two():
    """White-noise residuals should give DW close to 2."""
    import numpy as np

    from app.analysis.curve_fitting import compute_durbin_watson

    rng = np.random.default_rng(0)
    dw = compute_durbin_watson(rng.standard_normal(500))
    assert dw is not None
    assert 1.7 < dw < 2.3


def test_durbin_watson_positive_autocorr_below_two():
    """Strongly positively autocorrelated residuals give DW well below 2."""
    import numpy as np

    from app.analysis.curve_fitting import compute_durbin_watson

    rng = np.random.default_rng(0)
    eps = rng.standard_normal(500)
    x = np.zeros_like(eps)
    for i in range(1, len(x)):
        x[i] = 0.9 * x[i - 1] + eps[i]
    dw = compute_durbin_watson(x)
    assert dw is not None
    assert dw < 1.0


def test_durbin_watson_negative_autocorr_above_two():
    """Anti-correlated residuals (alternating sign) give DW well above 2."""
    import numpy as np

    from app.analysis.curve_fitting import compute_durbin_watson

    arr = np.array([1.0, -1.0] * 50)
    dw = compute_durbin_watson(arr)
    assert dw is not None
    assert dw > 3.5


def test_durbin_watson_short_or_invalid_returns_none():
    from app.analysis.curve_fitting import compute_durbin_watson

    assert compute_durbin_watson([1.0]) is None
    assert compute_durbin_watson(None) is None
    assert compute_durbin_watson([0.0, 0.0, 0.0]) is None  # zero denom


# --------------------------------------------------------------------------- #
# compute_pct_plateau_reached
# --------------------------------------------------------------------------- #


def test_compute_plateau_reached_basic():
    pct = compute_pct_plateau_reached(k_obs=0.1, t_lag=2.0, run_length_min=20.0)
    assert pct is not None
    # 1 - exp(-0.1 * 18) ~= 0.835
    assert 0.83 < pct < 0.84


def test_compute_plateau_reached_run_length_le_t_lag():
    assert compute_pct_plateau_reached(k_obs=0.1, t_lag=10.0, run_length_min=5.0) == 0.0


def test_compute_plateau_reached_missing_inputs():
    assert compute_pct_plateau_reached(k_obs=None, t_lag=1.0, run_length_min=10.0) is None
    assert compute_pct_plateau_reached(k_obs=0.0, t_lag=1.0, run_length_min=10.0) is None


def test_compute_plateau_reached_clipped_to_unit_interval():
    # huge k_obs * (run_length - t_lag) -> 1.0
    pct = compute_pct_plateau_reached(k_obs=100.0, t_lag=0.0, run_length_min=1000.0)
    assert pct == 1.0


# --------------------------------------------------------------------------- #
# evaluate()
# --------------------------------------------------------------------------- #


def test_evaluate_good_fit_passes():
    fit = _Fit()
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    assert result.flag == ReliabilityFlag.GOOD
    assert result.reasons == [FilterReason.OK]


def test_evaluate_low_r2_flags_bad():
    # Below the 0.97 calibrated threshold
    fit = _Fit(r_squared=0.85)
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    assert result.flag == ReliabilityFlag.BAD
    assert FilterReason.LOW_R2 in result.reasons


def test_evaluate_extrapolated_fmax():
    # pct_plateau 0.50 < BAD cutoff 0.70
    fit = _Fit(pct_plateau_reached=0.50)
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    assert result.flag == ReliabilityFlag.BAD
    assert FilterReason.EXTRAPOLATED_FMAX in result.reasons


def test_evaluate_high_fmax_se():
    # f_max_se / f_max = 100/1000 = 10% -> > 5% bad cutoff
    fit = _Fit(f_max=1000.0, f_max_se=100.0)
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    assert result.flag == ReliabilityFlag.BAD
    assert FilterReason.HIGH_FMAX_SE in result.reasons


def test_evaluate_poor_shape_dw_low_positive_autocorr():
    # DW=1.0 indicates strong positive autocorrelation (model bias).
    # Opt in to shape gating — it's off by default.
    fit = _Fit(residual_autocorr_dw=1.0)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert FilterReason.POOR_SHAPE in result.reasons
    assert result.flag == ReliabilityFlag.WEAK


def test_evaluate_poor_shape_dw_high_negative_autocorr():
    # DW=3.5 indicates strong negative autocorrelation
    fit = _Fit(residual_autocorr_dw=3.5)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert FilterReason.POOR_SHAPE in result.reasons


def test_evaluate_dw_in_band_passes():
    # DW=2.0 is the no-autocorrelation centre — should not trigger POOR_SHAPE
    fit = _Fit(residual_autocorr_dw=2.0)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert FilterReason.POOR_SHAPE not in result.reasons


def test_evaluate_poor_shape_high_rmse():
    # rmse/mean_signal = 50/500 = 0.10 > 0.06 cutoff
    fit = _Fit(rmse=50.0, mean_signal=500.0)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert FilterReason.POOR_SHAPE in result.reasons


def test_shape_gate_off_by_default():
    # With check_shape=False (the default), bad DW shouldn't flag POOR_SHAPE.
    fit = _Fit(residual_autocorr_dw=0.5)
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    assert FilterReason.POOR_SHAPE not in result.reasons


def test_evaluate_normality_no_longer_used():
    # Old gate (Shapiro-Wilk) should be ignored — only DW gates if shape=True.
    fit = _Fit(residual_normality_pvalue=1e-12, residual_autocorr_dw=2.0)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert FilterReason.POOR_SHAPE not in result.reasons


def test_evaluate_outlier_only_when_passed_in():
    fit = _Fit()
    res_no = evaluate(fit, thresholds=ReliabilityThresholds(), is_outlier=False)
    res_yes = evaluate(fit, thresholds=ReliabilityThresholds(), is_outlier=True)
    assert FilterReason.OUTLIER not in res_no.reasons
    assert FilterReason.OUTLIER in res_yes.reasons
    assert res_yes.flag == ReliabilityFlag.WEAK


def test_evaluate_outlier_disabled_via_thresholds():
    fit = _Fit()
    thresholds = ReliabilityThresholds(check_outliers=False)
    result = evaluate(fit, thresholds=thresholds, is_outlier=True)
    assert FilterReason.OUTLIER not in result.reasons


def test_evaluate_shape_disabled_via_thresholds():
    fit = _Fit(residual_autocorr_dw=0.5)
    thresholds = ReliabilityThresholds(check_shape=False)
    result = evaluate(fit, thresholds=thresholds)
    assert FilterReason.POOR_SHAPE not in result.reasons


def test_evaluate_takes_worst_flag():
    # LOW_R2 (BAD) + POOR_SHAPE (WEAK) -> overall BAD
    fit = _Fit(r_squared=0.5, residual_autocorr_dw=0.5)
    result = evaluate(fit, thresholds=ReliabilityThresholds(check_shape=True))
    assert result.flag == ReliabilityFlag.BAD


def test_evaluate_unknown_metrics_default_to_ok():
    fit = _Fit(
        f_max=None,
        f_max_se=None,
        pct_plateau_reached=None,
        mean_signal=None,
        residual_normality_pvalue=None,
        residual_autocorr_dw=None,
    )
    result = evaluate(fit, thresholds=ReliabilityThresholds())
    # Unknown metrics are not failures, but they don't earn the GOOD tier either
    # (we don't know they're great). Overall lands at OK.
    assert result.flag == ReliabilityFlag.OK
    assert result.reasons == [FilterReason.OK]


# --------------------------------------------------------------------------- #
# detect_outliers / evaluate_batch
# --------------------------------------------------------------------------- #


def _replicate_group(value: float, n: int = 4):
    return [_Fit(id=i, f_max=value) for i in range(1, n + 1)]


def test_detect_outliers_skips_small_groups():
    # group of size 2 — below the min-group-size cutoff
    fits = [_Fit(id=1, f_max=1000.0), _Fit(id=2, f_max=10.0)]
    flags = detect_outliers(
        fits, group_key=lambda f: "g1", thresholds=ReliabilityThresholds()
    )
    assert flags == {1: False, 2: False}


def test_detect_outliers_flags_fractional_deviation():
    # Inliers cluster ±2% of median; one well at 30% deviation is an outlier
    # under the default 0.20 fraction threshold.
    fits = [
        _Fit(id=1, f_max=1000.0),
        _Fit(id=2, f_max=1010.0),
        _Fit(id=3, f_max=990.0),
        _Fit(id=4, f_max=1005.0),
    ]
    fits.append(_Fit(id=99, f_max=1300.0))  # +30% deviation
    flags = detect_outliers(
        fits, group_key=lambda f: "g1", thresholds=ReliabilityThresholds()
    )
    assert flags[99] is True
    assert all(flags[i] is False for i in (1, 2, 3, 4))


def test_detect_outliers_tolerates_normal_biological_variation():
    # ±5% spread around 1000 — typical replicate noise. Nothing should flag.
    fits = [
        _Fit(id=1, f_max=950.0),
        _Fit(id=2, f_max=1000.0),
        _Fit(id=3, f_max=1050.0),
        _Fit(id=4, f_max=970.0),
        _Fit(id=5, f_max=1030.0),
    ]
    flags = detect_outliers(
        fits, group_key=lambda f: "g1", thresholds=ReliabilityThresholds()
    )
    assert all(v is False for v in flags.values())


def test_detect_outliers_zero_median_skips():
    # When median == 0 the fractional rule is undefined; skip the metric.
    fits = [
        _Fit(id=1, t_lag=0.0),
        _Fit(id=2, t_lag=0.0),
        _Fit(id=3, t_lag=10.0),
    ]
    flags = detect_outliers(
        fits, group_key=lambda f: "g1", thresholds=ReliabilityThresholds()
    )
    # f_max metric still flags nothing (all default 1000), t_lag is skipped.
    assert all(v is False for v in flags.values())


def test_detect_outliers_custom_threshold():
    # With a tight 5% threshold, even the ±5% inliers become outliers.
    fits = [
        _Fit(id=1, f_max=950.0),
        _Fit(id=2, f_max=1000.0),
        _Fit(id=3, f_max=1100.0),
    ]
    th = ReliabilityThresholds(outlier_fraction_threshold=0.05)
    flags = detect_outliers(fits, group_key=lambda f: "g1", thresholds=th)
    # 1100 vs median 1000 is +10% — outside the 5% gate.
    assert flags[3] is True


def test_evaluate_batch_combines_outlier_with_per_fit_eval():
    fits = [
        _Fit(id=1, f_max=1000.0),
        _Fit(id=2, f_max=1010.0),
        _Fit(id=3, f_max=990.0),
        _Fit(id=99, f_max=1500.0, k_obs=0.05),  # +50% from median
    ]
    results = evaluate_batch(
        fits, thresholds=ReliabilityThresholds(), group_key=lambda f: "g1"
    )
    assert FilterReason.OUTLIER in results[99].reasons
    for i in (1, 2, 3):
        assert FilterReason.OUTLIER not in results[i].reasons


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def test_thresholds_from_dict_overrides_defaults():
    thresholds = thresholds_from_dict({"r2_threshold": 0.5, "exclude_weak": True})
    assert thresholds.r2_threshold == 0.5
    assert thresholds.exclude_weak is True
    # untouched fields keep defaults
    assert thresholds.pct_plateau_bad == ReliabilityThresholds().pct_plateau_bad


def test_thresholds_from_dict_ignores_none_values():
    thresholds = thresholds_from_dict({"r2_threshold": None})
    assert thresholds.r2_threshold == ReliabilityThresholds().r2_threshold


def test_reasons_to_label_handles_empty():
    assert reasons_to_label([]) == "OK"
    assert reasons_to_label([FilterReason.OK]) == "OK"


def test_reasons_to_label_dedupes():
    label = reasons_to_label(
        [FilterReason.LOW_R2, FilterReason.LOW_R2, FilterReason.HIGH_FMAX_SE]
    )
    assert "LOW_R2" in label
    assert "HIGH_FMAX_SE" in label
    # dedup -> LOW_R2 appears once
    assert label.count("LOW_R2") == 1
