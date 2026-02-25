"""
Statistical analysis utilities for fold changes and uncertainty quantification.

PRD Reference: Section 1.2 - statistics.py for fold changes, uncertainty

This module re-exports statistical testing functions from statistical_tests.py
to provide PRD-compliant naming while maintaining backwards compatibility.
"""

# Re-export everything from statistical_tests
from app.analysis.statistical_tests import (
    # Normality tests
    shapiro_wilk_test,
    dagostino_pearson_test,
    NormalityTestResult,
    # Homoscedasticity tests
    breusch_pagan_test,
    levene_test,
    HomoscedasticityTestResult,
    # Effect size calculations
    cohens_d,
    hedges_g,
    EffectSizeResult,
    EffectSizeCategory,
    # Multiple comparison corrections
    bonferroni_correction,
    benjamini_hochberg_correction,
    holm_bonferroni_correction,
    apply_multiple_comparison_correction,
    MultipleComparisonResult,
    # Coverage and bias validation
    validate_coverage,
    validate_bias,
    run_coverage_simulation,
    run_bias_simulation,
    CoverageValidationResult,
    BiasValidationResult,
    # Combined diagnostics
    run_assumption_diagnostics,
    AssumptionDiagnostics,
    # Q-Q plot data generation
    generate_qq_data,
)

# Check for scipy availability
try:
    from app.analysis.statistical_tests import SCIPY_AVAILABLE
except ImportError:
    SCIPY_AVAILABLE = False

# Check for statsmodels diagnostic availability
try:
    from app.analysis.statistical_tests import STATSMODELS_DIAGNOSTIC_AVAILABLE
except ImportError:
    STATSMODELS_DIAGNOSTIC_AVAILABLE = False


__all__ = [
    # Normality tests
    "shapiro_wilk_test",
    "dagostino_pearson_test",
    "NormalityTestResult",
    # Homoscedasticity tests
    "breusch_pagan_test",
    "levene_test",
    "HomoscedasticityTestResult",
    # Effect size calculations
    "cohens_d",
    "hedges_g",
    "EffectSizeResult",
    "EffectSizeCategory",
    # Multiple comparison corrections
    "bonferroni_correction",
    "benjamini_hochberg_correction",
    "holm_bonferroni_correction",
    "apply_multiple_comparison_correction",
    "MultipleComparisonResult",
    # Coverage and bias validation
    "validate_coverage",
    "validate_bias",
    "run_coverage_simulation",
    "run_bias_simulation",
    "CoverageValidationResult",
    "BiasValidationResult",
    # Combined diagnostics
    "run_assumption_diagnostics",
    "AssumptionDiagnostics",
    # Q-Q plot data generation
    "generate_qq_data",
    # Availability flags
    "SCIPY_AVAILABLE",
    "STATSMODELS_DIAGNOSTIC_AVAILABLE",
]
