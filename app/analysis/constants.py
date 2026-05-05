"""Analysis module constants.

Centralizes magic numbers and configuration defaults used across
Bayesian, Frequentist, and comparison analysis modules.
"""

# --------------------------------------------------------------------------- #
# MCMC / Bayesian defaults
# --------------------------------------------------------------------------- #
DEFAULT_MCMC_CHAINS = 4
DEFAULT_MCMC_DRAWS = 2000
DEFAULT_MCMC_TUNE = 1000
DEFAULT_MCMC_THIN = 5
MCMC_CHECKPOINT_INTERVAL = 500
DEFAULT_MCMC_TARGET_ACCEPT = 0.95  # Higher than PyMC default (0.8) to reduce divergences

# --------------------------------------------------------------------------- #
# Effect-size thresholds
# --------------------------------------------------------------------------- #
# log2(1.135) — smallest fold change considered scientifically meaningful.
# A 13.5 % change in Fmax is the minimum for meaningful biological effect.
MEANINGFUL_EFFECT_THRESHOLD = 0.182

# --------------------------------------------------------------------------- #
# Confidence / credible intervals
# --------------------------------------------------------------------------- #
DEFAULT_CI_LEVEL = 0.95

# --------------------------------------------------------------------------- #
# Curve fitting quality thresholds
# --------------------------------------------------------------------------- #
MIN_R_SQUARED_ACCEPTABLE = 0.9   # "good fit" quality gate
MIN_R_SQUARED_VALID = 0.5        # minimum for any usable fit
PERTURBATION_SCALES = [0.5, 0.8, 1.2, 2.0]  # multi-start perturbation factors
HIGH_CORRELATION_THRESHOLD = 0.99  # flag near-degenerate parameter pairs

# --------------------------------------------------------------------------- #
# Comparison / fold-change analysis
# --------------------------------------------------------------------------- #
LOW_PRECISION_CI_WIDTH = 0.5     # CI width (log2 units) above which precision is flagged as low
BAYESIAN_FREQUENTIST_TOLERANCE = 0.10  # relative tolerance for method agreement

# --------------------------------------------------------------------------- #
# Fit reliability filter
# --------------------------------------------------------------------------- #
# Defaults calibrated against the live IVT dataset (438 fits, 21 sessions):
# uniformly high-quality fits (median R²=0.996, plateau=0.93, fmax_se%≈1.4),
# so the original wt_fmax_qc_findings cutoffs flagged ~91% of fits as WEAK.
# These tighter thresholds key off observed quantiles and only flag wells
# whose metrics genuinely fall outside the bulk of the distribution.

# Plateau-reached cutoffs: 1 - exp(-k_obs * (run_length - t_lag))
PCT_PLATEAU_BAD = 0.70
PCT_PLATEAU_WEAK = 0.85
PCT_PLATEAU_GOOD = 0.95

# F_max relative SE (%) cutoffs
F_MAX_SE_PCT_BAD = 5.0
F_MAX_SE_PCT_WEAK = 3.0
F_MAX_SE_PCT_GOOD = 1.5

# Shape diagnostics. We use the Durbin-Watson statistic on residuals (bounded
# [0, 4]; ≈2 means uncorrelated). Replaces the Shapiro-Wilk normality cutoff
# and Ljung-Box p-value, both of which saturate on long fluorescence traces
# (n=120-180) and stop discriminating real fit-quality differences.
# A fit is flagged when DW falls outside [DW_LOW, DW_HIGH].
SHAPE_DW_LOW = 1.5              # DW < 1.5 -> substantial positive autocorr
SHAPE_DW_HIGH = 2.5             # DW > 2.5 -> substantial negative autocorr
SHAPE_RMSE_FRAC_BAD = 0.06      # rmse/mean_signal cutoff

# Legacy alias kept for callers that imported the old constant. Reads as a
# distance from DW=2 (i.e. 0.5 -> reject if |DW - 2| > 0.5). Will be removed
# in a future release once downstream code has migrated.
SHAPE_DW_TOLERANCE = 0.5

# Outlier detection — fractional rule (|x - median| / |median| > threshold).
# More interpretable than MAD on tight replicate clusters where small absolute
# deviations from median trip a 3·MAD gate even for normal biological variation.
OUTLIER_FRAC_THRESHOLD = 0.20
OUTLIER_MIN_GROUP_SIZE = 3

# Default R^2 threshold used by the reliability filter UI (separate from
# MIN_R_SQUARED_ACCEPTABLE which gates the curve-fitting engine itself)
DEFAULT_RELIABILITY_R2_THRESHOLD = 0.97
