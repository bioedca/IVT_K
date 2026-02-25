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
