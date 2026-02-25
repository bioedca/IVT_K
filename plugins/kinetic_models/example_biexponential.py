"""
Example Plugin: Biexponential Model with Photobleaching.

Sprint 9: Plugin Architecture Enhancement (PRD Section 0.12)

This is an example kinetic model plugin that demonstrates how to create
custom models for the IVT Kinetics Analyzer.

F(t) = F0 + F_max * (1 - exp(-k_obs * t)) + k_bleach * t

This model extends the basic delayed exponential by adding a linear
photobleaching term to account for fluorescence decay over long experiments.
"""
import numpy as np
from typing import Dict, List, Tuple, Any

from app.analysis.kinetic_models import (
    KineticModel,
    kinetic_model,
    ModelParameters,
)


@kinetic_model
class BiexponentialWithBleaching(KineticModel):
    """
    Biexponential model with photobleaching correction.

    F(t) = F0 + F_max * (1 - exp(-k_obs * t)) + k_bleach * t

    Parameters:
        F0: Initial fluorescence level (RFU)
        F_max: Maximum amplitude (RFU)
        k_obs: Observed rate constant (min^-1)
        k_bleach: Photobleaching rate (RFU/min), typically negative

    This model is useful for long experiments where photobleaching
    causes a linear decrease in fluorescence over time.
    """

    @property
    def name(self) -> str:
        return "biexponential_bleaching"

    @property
    def param_names(self) -> List[str]:
        return ["F0", "F_max", "k_obs", "k_bleach"]

    @property
    def num_params(self) -> int:
        return 4

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate the biexponential model with bleaching."""
        F0 = params.get("F0")
        F_max = params.get("F_max")
        k_obs = params.get("k_obs")
        k_bleach = params.get("k_bleach")

        return F0 + F_max * (1 - np.exp(-k_obs * t)) + k_bleach * t

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian for biexponential with bleaching."""
        F_max = params.get("F_max")
        k_obs = params.get("k_obs")

        n = len(t)
        J = np.zeros((n, 4))

        exp_term = np.exp(-k_obs * t)

        # dF/dF0 = 1
        J[:, 0] = 1.0

        # dF/dF_max = 1 - exp(-k_obs * t)
        J[:, 1] = 1 - exp_term

        # dF/dk_obs = F_max * t * exp(-k_obs * t)
        J[:, 2] = F_max * t * exp_term

        # dF/dk_bleach = t
        J[:, 3] = t

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """Estimate initial parameters from data."""
        params = ModelParameters()

        # F0: initial fluorescence
        params.set("F0", F[0] if len(F) > 0 else 0.0)

        # F_max: range of data
        F0 = F[0] if len(F) > 0 else 0.0
        F_max = max(np.max(F) - F0, 1.0)
        params.set("F_max", F_max)

        # k_obs: estimate from half-max
        half_max = F0 + 0.5 * F_max
        idx_half = np.where(F > half_max)[0]
        if len(idx_half) > 0:
            t_half = t[idx_half[0]]
            k_obs = np.log(2) / max(t_half, 0.1)
        else:
            k_obs = 0.1
        params.set("k_obs", np.clip(k_obs, 0.001, 10.0))

        # k_bleach: small negative value (photobleaching)
        params.set("k_bleach", -0.001)

        return params

    def get_default_bounds(
        self, t: np.ndarray, F: np.ndarray
    ) -> Dict[str, Tuple[float, float]]:
        """Get default parameter bounds."""
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F0": (-np.inf, np.inf),
            "F_max": (0.0, 10 * max_F),
            "k_obs": (0.001, 10.0),
            "k_bleach": (-np.inf, 0.0),  # Must be negative (bleaching)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for this model."""
        return {
            "parameter_plots": ["k_obs", "F_max", "k_bleach"],
            "derived_metrics": [
                {
                    "name": "t_half",
                    "label": "Half-time",
                    "units": "min",
                    "formula": "ln(2)/k_obs",
                },
                {
                    "name": "plateau",
                    "label": "Plateau",
                    "units": "RFU",
                    "formula": "F0 + F_max",
                },
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": r"F(t) = F_0 + F_{max}(1 - e^{-k_{obs}t}) + k_{bleach}t",
            "color_scheme": {
                "primary": "#1f77b4",
                "secondary": "#ff7f0e",
                "residuals": "#2ca02c",
            },
        }
