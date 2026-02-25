"""Scientific computation modules for kinetics analysis."""
from app.analysis.kinetic_models import (
    KineticModel,
    ModelParameters,
    DelayedExponential,
    LogisticModel,
    DoubleExponential,
    LinearInitialRate,
    get_model,
    list_models,
    MODEL_REGISTRY
)
from app.analysis.curve_fitting import (
    CurveFitter,
    FitResult,
    FitStatistics,
    fit_delayed_exponential
)
from app.analysis.data_structure import (
    ModelTier,
    ModelMetadata,
    DataStructure,
    DataStructureAnalyzer,
)
from app.analysis.variance_components import (
    VarianceComponents,
    FrequentistVarianceComponents,
)
from app.analysis.constants import (
    DEFAULT_MCMC_CHAINS,
    DEFAULT_MCMC_DRAWS,
    DEFAULT_MCMC_TUNE,
    DEFAULT_MCMC_THIN,
    MCMC_CHECKPOINT_INTERVAL,
    DEFAULT_MCMC_TARGET_ACCEPT,
    MEANINGFUL_EFFECT_THRESHOLD,
    DEFAULT_CI_LEVEL,
    MIN_R_SQUARED_ACCEPTABLE,
    MIN_R_SQUARED_VALID,
    PERTURBATION_SCALES,
    HIGH_CORRELATION_THRESHOLD,
    LOW_PRECISION_CI_WIDTH,
    BAYESIAN_FREQUENTIST_TOLERANCE,
)
from app.analysis.bayesian import (
    BayesianHierarchical,
    BayesianResult,
    PosteriorSummary,
    check_pymc_available,
    PYMC_AVAILABLE
)
from app.analysis.frequentist import (
    FrequentistHierarchical,
    FrequentistResult,
    FrequentistEstimate,
    compare_bayesian_frequentist,
    check_statsmodels_available,
    STATSMODELS_AVAILABLE
)
# Phase A: mixed_effects unified interface
from app.analysis.mixed_effects import (
    HierarchicalModel,
    BayesianHierarchicalModel,
    FrequentistMixedEffects,
)
# Phase A: power_analysis re-exports
from app.analysis.power_analysis import (
    PowerResult,
    SampleSizeResult,
    calculate_power_for_fold_change,
    calculate_sample_size_for_power,
    calculate_sample_size_for_precision,
)
from app.analysis.comparison import (
    PairedAnalysis,
    ComparisonGraph,
    ComparisonType,
    PathType,
    FoldChangeResult,
    ComparisonPath,
    AnalysisScope,
    VIF_VALUES,
    compute_effective_sample_size
)
from app.analysis.quality_control import (
    QualityControl,
    QCSettings,
    QCFlag,
    QCSeverity,
    QCIssue,
    DriftResult,
    SaturationResult,
    OutlierResult,
    WellQCReport,
    PlateQCReport,
)
from app.analysis.negative_control import (
    NegativeControlAnalyzer,
    BackgroundStatistics,
    PolynomialFit,
    SpatialGradient,
    DetectionLimits,
    SignalQualityMetrics,
    NegativeControlReport,
    CorrectionMethod,
    DetectionStatus,
    classify_signal_quality,
)
from app.analysis.statistical_tests import (
    # Normality tests
    shapiro_wilk_test,
    dagostino_pearson_test,
    NormalityTestResult,
    # Homoscedasticity tests
    breusch_pagan_test,
    levene_test,
    HomoscedasticityTestResult,
    # Effect size
    cohens_d,
    hedges_g,
    EffectSizeResult,
    EffectSizeCategory,
    # Multiple comparisons
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
    generate_qq_data,
)
from app.analysis.edge_cases import (
    # MCMC diagnostics (T5.16)
    MCMCDiagnostics,
    assess_mcmc_diagnostics,
    # Data validation (T5.17, T5.18, T5.20)
    DataValidationResult,
    validate_hierarchical_data,
    # Posterior quality (T5.19)
    PosteriorQualityAssessment,
    assess_posterior_quality,
    # Convergence failures (T4.20-T4.24)
    ConvergenceFailureInfo,
    ConvergenceFailureType,
    diagnose_convergence_failure,
    # Sample size recommendations (T7.9-T7.11)
    SampleSizeRecommendation,
    compute_sample_size_recommendation,
    # Diagnostic messages
    DiagnosticMessage,
    DiagnosticSeverity,
)

__all__ = [
    # Kinetic models
    "KineticModel",
    "ModelParameters",
    "DelayedExponential",
    "LogisticModel",
    "DoubleExponential",
    "LinearInitialRate",
    "get_model",
    "list_models",
    "MODEL_REGISTRY",
    # Curve fitting
    "CurveFitter",
    "FitResult",
    "FitStatistics",
    "fit_delayed_exponential",
    # Data structure & model tiers (Phase 5)
    "ModelTier",
    "ModelMetadata",
    "DataStructure",
    "DataStructureAnalyzer",
    # Variance components (Phase 5)
    "VarianceComponents",
    "FrequentistVarianceComponents",
    # Analysis constants (Phase 5)
    "DEFAULT_MCMC_CHAINS",
    "DEFAULT_MCMC_DRAWS",
    "DEFAULT_MCMC_TUNE",
    "DEFAULT_MCMC_THIN",
    "MCMC_CHECKPOINT_INTERVAL",
    "DEFAULT_MCMC_TARGET_ACCEPT",
    "MEANINGFUL_EFFECT_THRESHOLD",
    "DEFAULT_CI_LEVEL",
    "MIN_R_SQUARED_ACCEPTABLE",
    "MIN_R_SQUARED_VALID",
    "PERTURBATION_SCALES",
    "HIGH_CORRELATION_THRESHOLD",
    "LOW_PRECISION_CI_WIDTH",
    "BAYESIAN_FREQUENTIST_TOLERANCE",
    # Bayesian analysis
    "BayesianHierarchical",
    "BayesianResult",
    "PosteriorSummary",
    "check_pymc_available",
    "PYMC_AVAILABLE",
    # Frequentist analysis
    "FrequentistHierarchical",
    "FrequentistResult",
    "FrequentistEstimate",
    "compare_bayesian_frequentist",
    "check_statsmodels_available",
    "STATSMODELS_AVAILABLE",
    # Phase A: mixed_effects unified interface
    "HierarchicalModel",
    "BayesianHierarchicalModel",
    "FrequentistMixedEffects",
    # Phase A: power_analysis
    "PowerResult",
    "SampleSizeResult",
    "calculate_power_for_fold_change",
    "calculate_sample_size_for_power",
    "calculate_sample_size_for_precision",
    # Comparison hierarchy
    "PairedAnalysis",
    "ComparisonGraph",
    "ComparisonType",
    "PathType",
    "FoldChangeResult",
    "ComparisonPath",
    "AnalysisScope",
    "VIF_VALUES",
    "compute_effective_sample_size",
    # Quality control
    "QualityControl",
    "QCSettings",
    "QCFlag",
    "QCSeverity",
    "QCIssue",
    "DriftResult",
    "SaturationResult",
    "OutlierResult",
    "WellQCReport",
    "PlateQCReport",
    # Negative control analysis
    "NegativeControlAnalyzer",
    "BackgroundStatistics",
    "PolynomialFit",
    "SpatialGradient",
    "DetectionLimits",
    "SignalQualityMetrics",
    "NegativeControlReport",
    "CorrectionMethod",
    "DetectionStatus",
    "classify_signal_quality",
    # Statistical tests (Sprint 7)
    "shapiro_wilk_test",
    "dagostino_pearson_test",
    "NormalityTestResult",
    "breusch_pagan_test",
    "levene_test",
    "HomoscedasticityTestResult",
    "cohens_d",
    "hedges_g",
    "EffectSizeResult",
    "EffectSizeCategory",
    "bonferroni_correction",
    "benjamini_hochberg_correction",
    "holm_bonferroni_correction",
    "apply_multiple_comparison_correction",
    "MultipleComparisonResult",
    "validate_coverage",
    "validate_bias",
    "run_coverage_simulation",
    "run_bias_simulation",
    "CoverageValidationResult",
    "BiasValidationResult",
    "run_assumption_diagnostics",
    "AssumptionDiagnostics",
    "generate_qq_data",
    # Edge case handling (Sprint 10)
    "MCMCDiagnostics",
    "assess_mcmc_diagnostics",
    "DataValidationResult",
    "validate_hierarchical_data",
    "PosteriorQualityAssessment",
    "assess_posterior_quality",
    "ConvergenceFailureInfo",
    "ConvergenceFailureType",
    "diagnose_convergence_failure",
    "SampleSizeRecommendation",
    "compute_sample_size_recommendation",
    "DiagnosticMessage",
    "DiagnosticSeverity",
]
