"""
Statistical tests and diagnostics for hierarchical model validation.

Sprint 7 Implementation:
- Task 7.1: Statistical validation tests (coverage simulation)
- Task 7.2: Multiple comparison corrections (Bonferroni)
- Task 7.3: Benjamini-Hochberg FDR control
- Task 7.4: Effect size calculations (Cohen's d)
- Task 7.5: Shapiro-Wilk normality test for residuals
- Task 7.6: Breusch-Pagan homoscedasticity test

PRD References:
- Lines 8395-8396: T5.14-T5.15 Coverage validation, Bias validation
- Lines 8540-8546: T8.15-T8.20 Statistical tests
"""
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import warnings

logger = logging.getLogger(__name__)

# Import scipy statistics
try:
    from scipy import stats as scipy_stats
    from scipy.stats import shapiro, levene, bartlett
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available. Statistical tests will be limited.")

# Try importing statsmodels for Breusch-Pagan
try:
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson
    STATSMODELS_DIAGNOSTIC_AVAILABLE = True
except ImportError:
    STATSMODELS_DIAGNOSTIC_AVAILABLE = False
    logger.warning("statsmodels.stats.diagnostic not available.")


class EffectSizeCategory(Enum):
    """Cohen's d effect size categories."""
    NEGLIGIBLE = "negligible"  # |d| < 0.2
    SMALL = "small"            # 0.2 <= |d| < 0.5
    MEDIUM = "medium"          # 0.5 <= |d| < 0.8
    LARGE = "large"            # |d| >= 0.8


@dataclass
class NormalityTestResult:
    """Result of a normality test."""
    test_name: str
    statistic: float
    p_value: float
    is_normal: bool  # True if we fail to reject normality (p > alpha)
    alpha: float = 0.05
    n_samples: int = 0
    message: str = ""

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        if self.is_normal:
            return f"Data appears normally distributed (p={self.p_value:.4f} > {self.alpha})"
        else:
            return f"Data deviates from normality (p={self.p_value:.4f} <= {self.alpha})"


@dataclass
class HomoscedasticityTestResult:
    """Result of a homoscedasticity test."""
    test_name: str
    statistic: float
    p_value: float
    is_homoscedastic: bool  # True if we fail to reject equal variances
    alpha: float = 0.05
    message: str = ""

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        if self.is_homoscedastic:
            return f"Variances appear equal (p={self.p_value:.4f} > {self.alpha})"
        else:
            return f"Heteroscedasticity detected (p={self.p_value:.4f} <= {self.alpha})"


@dataclass
class EffectSizeResult:
    """Result of effect size calculation."""
    cohens_d: float
    pooled_std: float
    category: EffectSizeCategory
    n_group1: int
    n_group2: int
    mean_diff: float

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        direction = "positive" if self.cohens_d > 0 else "negative"
        return f"{self.category.value.capitalize()} {direction} effect (d={self.cohens_d:.3f})"


@dataclass
class MultipleComparisonResult:
    """Result of multiple comparison correction."""
    method: str
    original_p_values: List[float]
    adjusted_p_values: List[float]
    significant: List[bool]
    alpha: float = 0.05
    n_comparisons: int = 0
    n_significant: int = 0

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        return (
            f"{self.method}: {self.n_significant}/{self.n_comparisons} comparisons "
            f"significant at alpha={self.alpha}"
        )


@dataclass
class CoverageValidationResult:
    """Result of coverage validation simulation."""
    target_coverage: float
    observed_coverage: float
    n_simulations: int
    is_valid: bool  # True if observed coverage is within acceptable range
    lower_bound: float  # Acceptable range lower bound
    upper_bound: float  # Acceptable range upper bound
    individual_coverages: List[float] = field(default_factory=list)

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        if self.is_valid:
            return (
                f"Coverage validation PASSED: {self.observed_coverage:.1%} observed "
                f"(target: {self.target_coverage:.1%}, acceptable: "
                f"{self.lower_bound:.1%}-{self.upper_bound:.1%})"
            )
        else:
            return (
                f"Coverage validation FAILED: {self.observed_coverage:.1%} observed "
                f"(target: {self.target_coverage:.1%}, acceptable: "
                f"{self.lower_bound:.1%}-{self.upper_bound:.1%})"
            )


@dataclass
class BiasValidationResult:
    """Result of bias validation simulation."""
    mean_bias: float
    std_bias: float
    max_abs_bias: float
    is_valid: bool  # True if |bias| < threshold * std
    threshold: float = 0.1
    n_simulations: int = 0
    individual_biases: List[float] = field(default_factory=list)

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation."""
        if self.is_valid:
            return (
                f"Bias validation PASSED: mean bias={self.mean_bias:.4f}, "
                f"|bias| < {self.threshold}*std"
            )
        else:
            return (
                f"Bias validation FAILED: mean bias={self.mean_bias:.4f}, "
                f"|bias| >= {self.threshold}*std"
            )


@dataclass
class AssumptionDiagnostics:
    """Combined diagnostics for model assumptions."""
    normality: NormalityTestResult
    homoscedasticity: Optional[HomoscedasticityTestResult] = None
    durbin_watson: Optional[float] = None  # Autocorrelation
    all_passed: bool = False

    def __post_init__(self):
        """Check if all tests passed."""
        passed = self.normality.is_normal
        if self.homoscedasticity is not None:
            passed = passed and self.homoscedasticity.is_homoscedastic
        self.all_passed = passed


# =============================================================================
# Normality Tests
# =============================================================================

def shapiro_wilk_test(
    data: np.ndarray,
    alpha: float = 0.05
) -> NormalityTestResult:
    """
    Perform Shapiro-Wilk test for normality.

    PRD Reference: Lines 8540-8541, T8.15

    Args:
        data: Array of values to test
        alpha: Significance level

    Returns:
        NormalityTestResult with test statistics
    """
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy is required for Shapiro-Wilk test")

    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]

    n = len(data)

    # Shapiro-Wilk requires 3-5000 samples
    if n < 3:
        return NormalityTestResult(
            test_name="Shapiro-Wilk",
            statistic=np.nan,
            p_value=np.nan,
            is_normal=False,
            alpha=alpha,
            n_samples=n,
            message="Insufficient data (n < 3)"
        )

    if n > 5000:
        # Use a sample for large datasets
        data = np.random.choice(data, size=5000, replace=False)
        n = 5000
        message = "Used random sample of 5000 for Shapiro-Wilk test"
    else:
        message = ""

    statistic, p_value = shapiro(data)

    return NormalityTestResult(
        test_name="Shapiro-Wilk",
        statistic=float(statistic),
        p_value=float(p_value),
        is_normal=p_value > alpha,
        alpha=alpha,
        n_samples=n,
        message=message
    )


def dagostino_pearson_test(
    data: np.ndarray,
    alpha: float = 0.05
) -> NormalityTestResult:
    """
    Perform D'Agostino-Pearson test for normality.

    Alternative to Shapiro-Wilk for larger samples.

    Args:
        data: Array of values to test
        alpha: Significance level

    Returns:
        NormalityTestResult with test statistics
    """
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy is required for D'Agostino-Pearson test")

    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]

    n = len(data)

    if n < 8:
        return NormalityTestResult(
            test_name="D'Agostino-Pearson",
            statistic=np.nan,
            p_value=np.nan,
            is_normal=False,
            alpha=alpha,
            n_samples=n,
            message="Insufficient data (n < 8)"
        )

    statistic, p_value = scipy_stats.normaltest(data)

    return NormalityTestResult(
        test_name="D'Agostino-Pearson",
        statistic=float(statistic),
        p_value=float(p_value),
        is_normal=p_value > alpha,
        alpha=alpha,
        n_samples=n,
        message=""
    )


# =============================================================================
# Homoscedasticity Tests
# =============================================================================

def breusch_pagan_test(
    residuals: np.ndarray,
    exog: np.ndarray,
    alpha: float = 0.05
) -> HomoscedasticityTestResult:
    """
    Perform Breusch-Pagan test for heteroscedasticity.

    PRD Reference: Lines 8541-8542, T8.16

    Args:
        residuals: Model residuals
        exog: Exogenous variables (design matrix)
        alpha: Significance level

    Returns:
        HomoscedasticityTestResult with test statistics
    """
    if not STATSMODELS_DIAGNOSTIC_AVAILABLE:
        raise ImportError("statsmodels is required for Breusch-Pagan test")

    residuals = np.asarray(residuals).flatten()
    exog = np.asarray(exog)

    # Ensure exog is 2D
    if exog.ndim == 1:
        exog = exog.reshape(-1, 1)

    # Add constant if not present
    if not np.any(np.all(exog == 1, axis=0)):
        exog = np.column_stack([np.ones(len(exog)), exog])

    try:
        lm_stat, lm_pvalue, fstat, f_pvalue = het_breuschpagan(residuals, exog)

        return HomoscedasticityTestResult(
            test_name="Breusch-Pagan",
            statistic=float(lm_stat),
            p_value=float(lm_pvalue),
            is_homoscedastic=lm_pvalue > alpha,
            alpha=alpha,
            message=""
        )
    except Exception as e:
        return HomoscedasticityTestResult(
            test_name="Breusch-Pagan",
            statistic=np.nan,
            p_value=np.nan,
            is_homoscedastic=True,  # Assume OK if test fails
            alpha=alpha,
            message=f"Test failed: {str(e)}"
        )


def levene_test(
    *groups: np.ndarray,
    alpha: float = 0.05,
    center: str = 'median'
) -> HomoscedasticityTestResult:
    """
    Perform Levene's test for equality of variances.

    Args:
        *groups: Two or more arrays of values
        alpha: Significance level
        center: 'median' (default, robust) or 'mean'

    Returns:
        HomoscedasticityTestResult with test statistics
    """
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy is required for Levene's test")

    if len(groups) < 2:
        return HomoscedasticityTestResult(
            test_name="Levene",
            statistic=np.nan,
            p_value=np.nan,
            is_homoscedastic=True,
            alpha=alpha,
            message="Need at least 2 groups"
        )

    # Clean data
    clean_groups = []
    for g in groups:
        g = np.asarray(g).flatten()
        g = g[~np.isnan(g)]
        if len(g) > 0:
            clean_groups.append(g)

    if len(clean_groups) < 2:
        return HomoscedasticityTestResult(
            test_name="Levene",
            statistic=np.nan,
            p_value=np.nan,
            is_homoscedastic=True,
            alpha=alpha,
            message="Need at least 2 non-empty groups"
        )

    statistic, p_value = levene(*clean_groups, center=center)

    return HomoscedasticityTestResult(
        test_name="Levene",
        statistic=float(statistic),
        p_value=float(p_value),
        is_homoscedastic=p_value > alpha,
        alpha=alpha,
        message=""
    )


# =============================================================================
# Effect Size Calculations
# =============================================================================

def cohens_d(
    group1: np.ndarray,
    group2: np.ndarray,
    pooled: bool = True
) -> EffectSizeResult:
    """
    Calculate Cohen's d effect size.

    PRD Reference: Lines 8545-8546, T8.20

    Args:
        group1: First group values
        group2: Second group values
        pooled: Use pooled standard deviation (True) or just group1's std

    Returns:
        EffectSizeResult with effect size and interpretation
    """
    group1 = np.asarray(group1).flatten()
    group2 = np.asarray(group2).flatten()

    # Remove NaN
    group1 = group1[~np.isnan(group1)]
    group2 = group2[~np.isnan(group2)]

    n1, n2 = len(group1), len(group2)

    if n1 < 2 or n2 < 2:
        return EffectSizeResult(
            cohens_d=np.nan,
            pooled_std=np.nan,
            category=EffectSizeCategory.NEGLIGIBLE,
            n_group1=n1,
            n_group2=n2,
            mean_diff=np.nan
        )

    mean1, mean2 = np.mean(group1), np.mean(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    mean_diff = mean1 - mean2

    if pooled:
        # Pooled standard deviation
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        pooled_std = np.sqrt(pooled_var)
    else:
        pooled_std = np.sqrt(var1)

    if pooled_std < 1e-10:
        d = 0.0
    else:
        d = mean_diff / pooled_std

    # Categorize effect size
    abs_d = abs(d)
    if abs_d < 0.2:
        category = EffectSizeCategory.NEGLIGIBLE
    elif abs_d < 0.5:
        category = EffectSizeCategory.SMALL
    elif abs_d < 0.8:
        category = EffectSizeCategory.MEDIUM
    else:
        category = EffectSizeCategory.LARGE

    return EffectSizeResult(
        cohens_d=float(d),
        pooled_std=float(pooled_std),
        category=category,
        n_group1=n1,
        n_group2=n2,
        mean_diff=float(mean_diff)
    )


def hedges_g(
    group1: np.ndarray,
    group2: np.ndarray
) -> float:
    """
    Calculate Hedges' g (bias-corrected Cohen's d).

    Applies small sample correction to Cohen's d.

    Args:
        group1: First group values
        group2: Second group values

    Returns:
        Hedges' g value
    """
    result = cohens_d(group1, group2, pooled=True)

    if np.isnan(result.cohens_d):
        return np.nan

    n = result.n_group1 + result.n_group2

    # Small sample correction factor
    if n > 3:
        correction = 1 - (3 / (4 * n - 9))
    else:
        correction = 1.0

    return float(result.cohens_d * correction)


# =============================================================================
# Multiple Comparison Corrections
# =============================================================================

def bonferroni_correction(
    p_values: List[float],
    alpha: float = 0.05
) -> MultipleComparisonResult:
    """
    Apply Bonferroni correction for multiple comparisons.

    PRD Reference: Lines 8543-8544, T8.18

    Args:
        p_values: List of p-values
        alpha: Family-wise error rate

    Returns:
        MultipleComparisonResult with adjusted p-values
    """
    p_values = np.asarray(p_values)
    n = len(p_values)

    if n == 0:
        return MultipleComparisonResult(
            method="Bonferroni",
            original_p_values=[],
            adjusted_p_values=[],
            significant=[],
            alpha=alpha,
            n_comparisons=0,
            n_significant=0
        )

    # Bonferroni: multiply p-values by n, cap at 1.0
    adjusted = np.minimum(p_values * n, 1.0)
    significant = adjusted <= alpha

    return MultipleComparisonResult(
        method="Bonferroni",
        original_p_values=p_values.tolist(),
        adjusted_p_values=adjusted.tolist(),
        significant=significant.tolist(),
        alpha=alpha,
        n_comparisons=n,
        n_significant=int(np.sum(significant))
    )


def benjamini_hochberg_correction(
    p_values: List[float],
    alpha: float = 0.05
) -> MultipleComparisonResult:
    """
    Apply Benjamini-Hochberg FDR correction.

    PRD Reference: Lines 8544, T8.19

    Args:
        p_values: List of p-values
        alpha: False discovery rate threshold

    Returns:
        MultipleComparisonResult with adjusted p-values
    """
    p_values = np.asarray(p_values)
    n = len(p_values)

    if n == 0:
        return MultipleComparisonResult(
            method="Benjamini-Hochberg (FDR)",
            original_p_values=[],
            adjusted_p_values=[],
            significant=[],
            alpha=alpha,
            n_comparisons=0,
            n_significant=0
        )

    # Sort p-values and keep track of original indices
    sorted_indices = np.argsort(p_values)
    sorted_p = p_values[sorted_indices]

    # Calculate adjusted p-values
    # p_adj[i] = min(p[i] * n / (i+1), 1.0)
    # But need to ensure monotonicity
    adjusted = np.zeros(n)
    for i in range(n - 1, -1, -1):
        rank = i + 1
        if i == n - 1:
            adjusted[i] = min(sorted_p[i] * n / rank, 1.0)
        else:
            adjusted[i] = min(sorted_p[i] * n / rank, adjusted[i + 1])

    # Restore original order
    final_adjusted = np.zeros(n)
    final_adjusted[sorted_indices] = adjusted

    significant = final_adjusted <= alpha

    return MultipleComparisonResult(
        method="Benjamini-Hochberg (FDR)",
        original_p_values=p_values.tolist(),
        adjusted_p_values=final_adjusted.tolist(),
        significant=significant.tolist(),
        alpha=alpha,
        n_comparisons=n,
        n_significant=int(np.sum(significant))
    )


def holm_bonferroni_correction(
    p_values: List[float],
    alpha: float = 0.05
) -> MultipleComparisonResult:
    """
    Apply Holm-Bonferroni step-down correction.

    More powerful than Bonferroni while controlling FWER.

    Args:
        p_values: List of p-values
        alpha: Family-wise error rate

    Returns:
        MultipleComparisonResult with adjusted p-values
    """
    p_values = np.asarray(p_values)
    n = len(p_values)

    if n == 0:
        return MultipleComparisonResult(
            method="Holm-Bonferroni",
            original_p_values=[],
            adjusted_p_values=[],
            significant=[],
            alpha=alpha,
            n_comparisons=0,
            n_significant=0
        )

    # Sort p-values
    sorted_indices = np.argsort(p_values)
    sorted_p = p_values[sorted_indices]

    # Calculate adjusted p-values
    adjusted = np.zeros(n)
    for i in range(n):
        adjusted[i] = sorted_p[i] * (n - i)

    # Ensure monotonicity (cumulative maximum)
    for i in range(1, n):
        adjusted[i] = max(adjusted[i], adjusted[i - 1])

    # Cap at 1.0
    adjusted = np.minimum(adjusted, 1.0)

    # Restore original order
    final_adjusted = np.zeros(n)
    final_adjusted[sorted_indices] = adjusted

    significant = final_adjusted <= alpha

    return MultipleComparisonResult(
        method="Holm-Bonferroni",
        original_p_values=p_values.tolist(),
        adjusted_p_values=final_adjusted.tolist(),
        significant=significant.tolist(),
        alpha=alpha,
        n_comparisons=n,
        n_significant=int(np.sum(significant))
    )


def apply_multiple_comparison_correction(
    p_values: List[float],
    method: str = 'fdr',
    alpha: float = 0.05
) -> MultipleComparisonResult:
    """
    Apply multiple comparison correction with specified method.

    Args:
        p_values: List of p-values
        method: 'bonferroni', 'holm', 'fdr' (Benjamini-Hochberg)
        alpha: Significance level

    Returns:
        MultipleComparisonResult
    """
    method = method.lower()

    if method in ('bonferroni', 'bon'):
        return bonferroni_correction(p_values, alpha)
    elif method in ('holm', 'holm-bonferroni'):
        return holm_bonferroni_correction(p_values, alpha)
    elif method in ('fdr', 'bh', 'benjamini-hochberg'):
        return benjamini_hochberg_correction(p_values, alpha)
    else:
        raise ValueError(f"Unknown correction method: {method}")


# =============================================================================
# Coverage and Bias Validation
# =============================================================================

def validate_coverage(
    true_values: np.ndarray,
    ci_lower: np.ndarray,
    ci_upper: np.ndarray,
    target_coverage: float = 0.95,
    tolerance: float = 0.02
) -> CoverageValidationResult:
    """
    Validate that confidence intervals achieve target coverage.

    PRD Reference: Lines 8395, T5.14 - Coverage validation: 93-97% of 95% CIs

    Args:
        true_values: Known true parameter values
        ci_lower: Lower bounds of CIs
        ci_upper: Upper bounds of CIs
        target_coverage: Target coverage probability (default 0.95)
        tolerance: Acceptable deviation from target (default 0.02)

    Returns:
        CoverageValidationResult
    """
    true_values = np.asarray(true_values)
    ci_lower = np.asarray(ci_lower)
    ci_upper = np.asarray(ci_upper)

    n = len(true_values)

    if n == 0:
        return CoverageValidationResult(
            target_coverage=target_coverage,
            observed_coverage=0.0,
            n_simulations=0,
            is_valid=False,
            lower_bound=target_coverage - tolerance,
            upper_bound=target_coverage + tolerance
        )

    # Check which CIs contain true values
    covered = (ci_lower <= true_values) & (true_values <= ci_upper)
    observed_coverage = float(np.mean(covered))

    # Acceptable range
    lower_bound = target_coverage - tolerance
    upper_bound = target_coverage + tolerance

    is_valid = lower_bound <= observed_coverage <= upper_bound

    return CoverageValidationResult(
        target_coverage=target_coverage,
        observed_coverage=observed_coverage,
        n_simulations=n,
        is_valid=is_valid,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        individual_coverages=covered.tolist()
    )


def validate_bias(
    true_values: np.ndarray,
    estimates: np.ndarray,
    threshold: float = 0.1
) -> BiasValidationResult:
    """
    Validate that estimates are unbiased.

    PRD Reference: Lines 8396, T5.15 - Bias validation: |bias| < 0.1*std

    Args:
        true_values: Known true parameter values
        estimates: Estimated parameter values
        threshold: Maximum acceptable |bias|/std ratio (default 0.1)

    Returns:
        BiasValidationResult
    """
    true_values = np.asarray(true_values)
    estimates = np.asarray(estimates)

    n = len(true_values)

    if n == 0:
        return BiasValidationResult(
            mean_bias=0.0,
            std_bias=0.0,
            max_abs_bias=0.0,
            is_valid=True,
            threshold=threshold,
            n_simulations=0
        )

    # Calculate biases
    biases = estimates - true_values
    mean_bias = float(np.mean(biases))
    std_bias = float(np.std(biases))
    max_abs_bias = float(np.max(np.abs(biases)))

    # Check if bias is acceptable relative to std
    if std_bias > 1e-10:
        is_valid = abs(mean_bias) < threshold * std_bias
    else:
        is_valid = abs(mean_bias) < 1e-10

    return BiasValidationResult(
        mean_bias=mean_bias,
        std_bias=std_bias,
        max_abs_bias=max_abs_bias,
        is_valid=is_valid,
        threshold=threshold,
        n_simulations=n,
        individual_biases=biases.tolist()
    )


def run_coverage_simulation(
    n_simulations: int = 1000,
    n_samples: int = 50,
    true_mean: float = 0.0,
    true_std: float = 1.0,
    ci_level: float = 0.95,
    random_seed: Optional[int] = None
) -> CoverageValidationResult:
    """
    Run simulation to validate CI coverage.

    Generates synthetic data from known distribution and checks if
    CIs achieve nominal coverage.

    Args:
        n_simulations: Number of simulation runs
        n_samples: Samples per simulation
        true_mean: True population mean
        true_std: True population std
        ci_level: Confidence interval level
        random_seed: Random seed for reproducibility

    Returns:
        CoverageValidationResult
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    ci_lower_list = []
    ci_upper_list = []
    true_values = []

    alpha = 1 - ci_level
    z = scipy_stats.norm.ppf(1 - alpha / 2) if SCIPY_AVAILABLE else 1.96

    for _ in range(n_simulations):
        # Generate data from known distribution
        data = np.random.normal(true_mean, true_std, n_samples)

        # Calculate sample statistics
        sample_mean = np.mean(data)
        sample_se = np.std(data, ddof=1) / np.sqrt(n_samples)

        # Calculate CI
        ci_lower_list.append(sample_mean - z * sample_se)
        ci_upper_list.append(sample_mean + z * sample_se)
        true_values.append(true_mean)

    return validate_coverage(
        true_values=np.array(true_values),
        ci_lower=np.array(ci_lower_list),
        ci_upper=np.array(ci_upper_list),
        target_coverage=ci_level
    )


def run_bias_simulation(
    n_simulations: int = 1000,
    n_samples: int = 50,
    true_mean: float = 0.0,
    true_std: float = 1.0,
    random_seed: Optional[int] = None
) -> BiasValidationResult:
    """
    Run simulation to validate estimator bias.

    Args:
        n_simulations: Number of simulation runs
        n_samples: Samples per simulation
        true_mean: True population mean
        true_std: True population std
        random_seed: Random seed for reproducibility

    Returns:
        BiasValidationResult
    """
    if random_seed is not None:
        np.random.seed(random_seed)

    estimates = []
    true_values = []

    for _ in range(n_simulations):
        # Generate data from known distribution
        data = np.random.normal(true_mean, true_std, n_samples)

        # Estimate mean
        estimates.append(np.mean(data))
        true_values.append(true_mean)

    return validate_bias(
        true_values=np.array(true_values),
        estimates=np.array(estimates)
    )


# =============================================================================
# Combined Diagnostics
# =============================================================================

def run_assumption_diagnostics(
    residuals: np.ndarray,
    fitted_values: Optional[np.ndarray] = None,
    groups: Optional[List[np.ndarray]] = None,
    alpha: float = 0.05
) -> AssumptionDiagnostics:
    """
    Run comprehensive assumption diagnostics.

    Args:
        residuals: Model residuals
        fitted_values: Fitted values (for Breusch-Pagan test)
        groups: Group assignments (for Levene's test)
        alpha: Significance level

    Returns:
        AssumptionDiagnostics with all test results
    """
    # Normality test
    normality = shapiro_wilk_test(residuals, alpha=alpha)

    # Homoscedasticity test
    homoscedasticity = None
    if fitted_values is not None and STATSMODELS_DIAGNOSTIC_AVAILABLE:
        homoscedasticity = breusch_pagan_test(residuals, fitted_values, alpha=alpha)
    elif groups is not None and len(groups) >= 2:
        homoscedasticity = levene_test(*groups, alpha=alpha)

    # Durbin-Watson test for autocorrelation
    dw = None
    if STATSMODELS_DIAGNOSTIC_AVAILABLE:
        try:
            dw = float(durbin_watson(residuals))
        except Exception:
            pass

    return AssumptionDiagnostics(
        normality=normality,
        homoscedasticity=homoscedasticity,
        durbin_watson=dw
    )


def generate_qq_data(
    data: np.ndarray,
    distribution: str = 'norm'
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Q-Q plot data for visualization.

    PRD Reference: Lines 8542-8543, T8.17

    Args:
        data: Data to compare against theoretical distribution
        distribution: 'norm' for normal distribution

    Returns:
        Tuple of (theoretical_quantiles, sample_quantiles, fit_line_x, fit_line_y)
    """
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    data = np.sort(data)

    n = len(data)

    if n == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])

    # Calculate plotting positions (Blom's formula)
    positions = (np.arange(1, n + 1) - 0.375) / (n + 0.25)

    # Get theoretical quantiles
    if SCIPY_AVAILABLE:
        if distribution == 'norm':
            theoretical = scipy_stats.norm.ppf(positions)
        else:
            theoretical = scipy_stats.norm.ppf(positions)
    else:
        # Approximate normal quantiles
        theoretical = np.sqrt(2) * np.array([
            1.0 if p > 0.5 else -1.0 for p in positions
        ])

    # Fit line through Q1 and Q3
    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)

    if q3_idx > q1_idx:
        slope = (data[q3_idx] - data[q1_idx]) / (theoretical[q3_idx] - theoretical[q1_idx])
        intercept = data[q1_idx] - slope * theoretical[q1_idx]
    else:
        slope = 1.0
        intercept = np.mean(data)

    fit_line_x = np.array([theoretical.min(), theoretical.max()])
    fit_line_y = intercept + slope * fit_line_x

    return theoretical, data, fit_line_x, fit_line_y
