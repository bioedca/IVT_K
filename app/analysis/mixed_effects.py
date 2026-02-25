"""
Unified interface for hierarchical mixed-effects modeling.

PRD Reference: Section 1.2 - mixed_effects.py for hierarchical models

This module provides a unified interface for hierarchical modeling,
supporting both Bayesian (PyMC) and Frequentist (statsmodels REML)
implementations.
"""
from typing import Literal, Union

# Import Bayesian implementation
from app.analysis.bayesian import (
    BayesianHierarchical,
    BayesianResult,
    PosteriorSummary,
    VarianceComponents,
    check_pymc_available,
    PYMC_AVAILABLE,
)

# Import Frequentist implementation
from app.analysis.frequentist import (
    FrequentistHierarchical,
    FrequentistResult,
    FrequentistEstimate,
    FrequentistVarianceComponents,
    compare_bayesian_frequentist,
    check_statsmodels_available,
    STATSMODELS_AVAILABLE,
)

# Aliases for PRD compatibility
BayesianHierarchicalModel = BayesianHierarchical
FrequentistMixedEffects = FrequentistHierarchical


class HierarchicalModel:
    """
    Factory for hierarchical models supporting both Bayesian and Frequentist analysis.

    This class provides a unified interface for creating hierarchical models
    regardless of the underlying statistical framework.

    Usage:
        >>> model = HierarchicalModel.create(analysis_type="bayesian")
        >>> result = model.run_analysis(fold_changes_df)

        >>> model = HierarchicalModel.create(analysis_type="frequentist")
        >>> result = model.run_analysis(fold_changes_df)
    """

    @staticmethod
    def create(
        analysis_type: Literal["bayesian", "frequentist"] = "bayesian",
        **kwargs
    ) -> Union[BayesianHierarchical, FrequentistHierarchical]:
        """
        Create a hierarchical model of the specified type.

        Args:
            analysis_type: Type of analysis ("bayesian" or "frequentist")
            **kwargs: Additional arguments passed to the model constructor
                For Bayesian: chains, draws, tune, thin, random_seed
                For Frequentist: ci_level

        Returns:
            BayesianHierarchical or FrequentistHierarchical instance

        Raises:
            ValueError: If analysis_type is not recognized
            ImportError: If required dependencies are not available
        """
        if analysis_type == "bayesian":
            if not PYMC_AVAILABLE:
                raise ImportError(
                    "PyMC is required for Bayesian analysis. "
                    "Install with: pip install pymc arviz"
                )
            return BayesianHierarchical(**kwargs)

        elif analysis_type == "frequentist":
            if not STATSMODELS_AVAILABLE:
                raise ImportError(
                    "statsmodels is required for Frequentist analysis. "
                    "Install with: pip install statsmodels"
                )
            return FrequentistHierarchical(**kwargs)

        else:
            raise ValueError(
                f"Unknown analysis type: '{analysis_type}'. "
                f"Must be 'bayesian' or 'frequentist'."
            )

    @staticmethod
    def available_types() -> list:
        """
        List available analysis types based on installed dependencies.

        Returns:
            List of available analysis type strings
        """
        available = []
        if PYMC_AVAILABLE:
            available.append("bayesian")
        if STATSMODELS_AVAILABLE:
            available.append("frequentist")
        return available

    @staticmethod
    def is_available(analysis_type: str) -> bool:
        """
        Check if a specific analysis type is available.

        Args:
            analysis_type: Type to check ("bayesian" or "frequentist")

        Returns:
            True if the analysis type is available
        """
        if analysis_type == "bayesian":
            return PYMC_AVAILABLE
        elif analysis_type == "frequentist":
            return STATSMODELS_AVAILABLE
        return False


# Export all public interfaces
__all__ = [
    # Factory class
    "HierarchicalModel",
    # Bayesian
    "BayesianHierarchical",
    "BayesianHierarchicalModel",  # Alias
    "BayesianResult",
    "PosteriorSummary",
    "VarianceComponents",
    "check_pymc_available",
    "PYMC_AVAILABLE",
    # Frequentist
    "FrequentistHierarchical",
    "FrequentistMixedEffects",  # Alias
    "FrequentistResult",
    "FrequentistEstimate",
    "FrequentistVarianceComponents",
    "compare_bayesian_frequentist",
    "check_statsmodels_available",
    "STATSMODELS_AVAILABLE",
]
