"""
Power analysis module for sample size estimation.

PRD Reference: Section 1.2 - power_analysis.py for sample size estimation

This module re-exports power analysis functions from app/calculator/power_analysis.py
to provide PRD-compliant module location in the analysis package.
"""

# Re-export everything from calculator.power_analysis
from app.calculator.power_analysis import (
    HierarchicalSampleSizeResult,
    ModelTierForPower,
    # Result dataclasses
    PowerResult,
    SampleSizeResult,
    VarianceComponentsForPower,
    calculate_ci_width,
    # Tier-aware hierarchical power analysis
    calculate_hierarchical_se,
    # Core calculation functions
    calculate_power_for_fold_change,
    # Scoring functions for recommendations
    calculate_precision_gap_score,
    calculate_sample_size_for_power,
    calculate_sample_size_for_precision,
    calculate_se_from_ci_width,
    calculate_tier_aware_sample_size,
    calculate_untested_score,
    detect_tier_from_data_structure,
    # Co-plating benefit estimation
    estimate_coplating_benefit,
    # Estimation functions
    estimate_precision_improvement,
    get_tier_aware_recommendation_text,
)

__all__ = [
    # Result dataclasses
    "PowerResult",
    "SampleSizeResult",
    "HierarchicalSampleSizeResult",
    "VarianceComponentsForPower",
    "ModelTierForPower",
    # Core calculation functions
    "calculate_power_for_fold_change",
    "calculate_sample_size_for_power",
    "calculate_ci_width",
    "calculate_se_from_ci_width",
    "calculate_sample_size_for_precision",
    # Estimation functions
    "estimate_precision_improvement",
    # Scoring functions for recommendations
    "calculate_precision_gap_score",
    "calculate_untested_score",
    # Co-plating benefit estimation
    "estimate_coplating_benefit",
    # Tier-aware hierarchical power analysis
    "calculate_hierarchical_se",
    "calculate_tier_aware_sample_size",
    "get_tier_aware_recommendation_text",
    "detect_tier_from_data_structure",
]
