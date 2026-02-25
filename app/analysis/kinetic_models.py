"""
Kinetic models for IVT fluorescence time-course fitting.

Phase 4.1: Delayed exponential model (primary)
Phase 4.2: Initial parameter estimation
Phase 4.7: Alternative models for diagnostics (logistic, double exponential, linear)
Sprint 9: Plugin architecture with ModelRegistry (PRD Section 0.12)
"""
import logging
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Type

logger = logging.getLogger(__name__)


@dataclass
class ModelParameters:
    """Container for model parameters and their uncertainties."""
    values: Dict[str, float] = field(default_factory=dict)
    standard_errors: Dict[str, Optional[float]] = field(default_factory=dict)
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def get(self, name: str, default: float = 0.0) -> float:
        """Get parameter value with optional default."""
        return self.values.get(name, default)

    def set(self, name: str, value: float, se: Optional[float] = None) -> None:
        """Set parameter value and optionally its standard error."""
        self.values[name] = value
        if se is not None:
            self.standard_errors[name] = se

    def to_array(self, param_names: List[str]) -> np.ndarray:
        """Convert parameters to array in specified order."""
        return np.array([self.values.get(name, 0.0) for name in param_names])

    @classmethod
    def from_array(cls, values: np.ndarray, param_names: List[str],
                   standard_errors: Optional[np.ndarray] = None) -> 'ModelParameters':
        """Create from array with named parameters."""
        params = cls()
        for i, name in enumerate(param_names):
            se = standard_errors[i] if standard_errors is not None else None
            params.set(name, values[i], se)
        return params


class ModelRegistry:
    """
    Registry for kinetic model plugins.

    Sprint 9: PRD Section 0.12 - Plugin Architecture

    This registry provides:
    - Model registration via @kinetic_model decorator
    - Model lookup by name
    - Plugin auto-discovery from directory
    - Graceful error handling for plugin imports

    Usage:
        @kinetic_model
        class MyModel(KineticModel):
            ...

        # Get model instance
        model = ModelRegistry.get("my_model")()

        # List all models
        models = ModelRegistry.all_models()
    """

    _models: Dict[str, Type['KineticModel']] = {}
    _plugin_errors: Dict[str, str] = {}

    @classmethod
    def register(cls, model_class: Type['KineticModel']) -> Type['KineticModel']:
        """
        Register a model class.

        Args:
            model_class: The KineticModel subclass to register

        Returns:
            The model class (for decorator chaining)
        """
        # Get model name from instance (need to instantiate temporarily)
        try:
            instance = model_class()
            name = instance.name
            cls._models[name] = model_class
            logger.debug(f"Registered kinetic model: {name}")
        except Exception as e:
            logger.warning(f"Failed to register model {model_class.__name__}: {e}")
        return model_class

    @classmethod
    def get(cls, name: str) -> Type['KineticModel']:
        """
        Get model class by name.

        Args:
            name: The model name identifier

        Returns:
            The KineticModel subclass

        Raises:
            ValueError: If model name not found in registry
        """
        if name not in cls._models:
            available = list(cls._models.keys())
            raise ValueError(f"Unknown model: {name}. Available: {available}")
        return cls._models[name]

    @classmethod
    def all_models(cls) -> Dict[str, Type['KineticModel']]:
        """
        Get all registered models.

        Returns:
            Copy of the model registry dict
        """
        return cls._models.copy()

    @classmethod
    def list_available(cls) -> List[str]:
        """
        Get list of available model names.

        Returns:
            List of model name strings
        """
        return list(cls._models.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a model is registered.

        Args:
            name: The model name to check

        Returns:
            True if model is registered
        """
        return name in cls._models

    @classmethod
    def discover_plugins(cls, plugin_dir: str = "plugins/kinetic_models") -> List[str]:
        """
        Auto-discover and load model plugins from directory.

        Sprint 9.2: Plugin directory structure (PRD Lines 8710, T12.4)

        Scans the plugin directory for Python files and attempts to
        import them. Each file should use the @kinetic_model decorator
        to register its models.

        Args:
            plugin_dir: Path to plugin directory (relative or absolute)

        Returns:
            List of successfully loaded plugin module names
        """
        loaded = []
        plugin_path = Path(plugin_dir)

        if not plugin_path.exists():
            logger.debug(f"Plugin directory does not exist: {plugin_dir}")
            return loaded

        for py_file in plugin_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            # Construct module name
            module_name = f"plugins.kinetic_models.{py_file.stem}"

            try:
                import_module(module_name)
                loaded.append(module_name)
                logger.info(f"Loaded plugin module: {module_name}")
            except ImportError as e:
                cls._plugin_errors[py_file.name] = str(e)
                logger.warning(f"Failed to load plugin {py_file}: {e}")
            except Exception as e:
                cls._plugin_errors[py_file.name] = str(e)
                logger.error(f"Error loading plugin {py_file}: {e}")

        return loaded

    @classmethod
    def get_plugin_errors(cls) -> Dict[str, str]:
        """
        Get errors from plugin loading.

        Sprint 9.3: Plugin import error handling (PRD Lines 8711, T12.5)

        Returns:
            Dict mapping plugin filename to error message
        """
        return cls._plugin_errors.copy()

    @classmethod
    def clear_plugin_errors(cls) -> None:
        """Clear recorded plugin errors."""
        cls._plugin_errors.clear()

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a model (useful for testing).

        Args:
            name: The model name to unregister

        Returns:
            True if model was unregistered, False if not found
        """
        if name in cls._models:
            del cls._models[name]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (useful for testing)."""
        cls._models.clear()
        cls._plugin_errors.clear()


def kinetic_model(cls: Type['KineticModel']) -> Type['KineticModel']:
    """
    Decorator to register a kinetic model.

    Sprint 9.1: Model registry with auto-discovery (PRD Lines 8707-8710, T12.2)

    Usage:
        @kinetic_model
        class MyCustomModel(KineticModel):
            @property
            def name(self) -> str:
                return "my_custom_model"
            ...

    Args:
        cls: The KineticModel subclass to register

    Returns:
        The model class (unchanged)
    """
    ModelRegistry.register(cls)
    return cls


class KineticModel(ABC):
    """
    Abstract base class for kinetic models.

    All kinetic models must implement:
    - evaluate(): compute F(t) given parameters
    - jacobian(): compute partial derivatives for fitting
    - initial_guess(): estimate starting parameters from data
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name identifier."""
        pass

    @property
    @abstractmethod
    def param_names(self) -> List[str]:
        """List of parameter names in order."""
        pass

    @property
    @abstractmethod
    def num_params(self) -> int:
        """Number of parameters."""
        pass

    @abstractmethod
    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """
        Evaluate the model at timepoints t.

        Args:
            t: Array of timepoints (minutes)
            params: ModelParameters container

        Returns:
            Array of fluorescence values
        """
        pass

    @abstractmethod
    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """
        Compute the Jacobian matrix (partial derivatives w.r.t. parameters).

        Args:
            t: Array of timepoints
            params: ModelParameters container

        Returns:
            Jacobian matrix of shape (len(t), num_params)
        """
        pass

    @abstractmethod
    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """
        Estimate initial parameters from data.

        Args:
            t: Array of timepoints (minutes)
            F: Array of fluorescence values

        Returns:
            ModelParameters with initial guesses
        """
        pass

    @abstractmethod
    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """
        Get default parameter bounds based on data.

        Args:
            t: Array of timepoints
            F: Array of fluorescence values

        Returns:
            Dict mapping parameter names to (lower, upper) bounds
        """
        pass

    def get_visualization_config(self) -> Dict[str, Any]:
        """
        Return visualization configuration for this model.

        Sprint 9.4: Visualization configuration API (PRD Lines 8712, T12.6)

        Returns:
            Dict containing:
                - parameter_plots: List of parameters to show in main plots
                - derived_metrics: List of derived values with formulas
                - diagnostic_plots: List of diagnostic plot types
                - equation_latex: LaTeX representation of the model
                - color_scheme: Suggested colors for plotting

        Note: This has a default implementation but can be overridden by
        subclasses for custom visualization needs.
        """
        return {
            "parameter_plots": self.param_names,
            "derived_metrics": [],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": None,
            "color_scheme": {
                "primary": "#1f77b4",
                "secondary": "#ff7f0e",
                "residuals": "#2ca02c"
            }
        }

    def evaluate_array(self, t: np.ndarray, param_array: np.ndarray) -> np.ndarray:
        """Evaluate with parameters as array (for scipy.optimize)."""
        params = ModelParameters.from_array(param_array, self.param_names)
        return self.evaluate(t, params)

    def jacobian_array(self, t: np.ndarray, param_array: np.ndarray) -> np.ndarray:
        """Jacobian with parameters as array (for scipy.optimize)."""
        params = ModelParameters.from_array(param_array, self.param_names)
        return self.jacobian(t, params)


@kinetic_model
class DelayedExponential(KineticModel):
    """
    Delayed exponential model for IVT kinetics (primary model).

    F(t) = F_baseline                                              for t <= t_lag
    F(t) = F_baseline + F_max * (1 - exp(-k_obs * (t - t_lag)))    for t > t_lag

    Parameters:
        F_baseline: Initial fluorescence level (RFU)
        F_max: Maximum amplitude above baseline (RFU)
        k_obs: Observed rate constant (min⁻¹)
        t_lag: Lag time before exponential rise (min)
    """

    @property
    def name(self) -> str:
        return "delayed_exponential"

    @property
    def param_names(self) -> List[str]:
        return ["F_baseline", "F_max", "k_obs", "t_lag"]

    @property
    def num_params(self) -> int:
        return 4

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate the delayed exponential model."""
        F_baseline = params.get("F_baseline")
        F_max = params.get("F_max")
        k_obs = params.get("k_obs")
        t_lag = params.get("t_lag")

        F = np.full_like(t, F_baseline, dtype=float)
        mask = t > t_lag
        F[mask] = F_baseline + F_max * (1 - np.exp(-k_obs * (t[mask] - t_lag)))
        return F

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian matrix for delayed exponential."""
        F_baseline = params.get("F_baseline")
        F_max = params.get("F_max")
        k_obs = params.get("k_obs")
        t_lag = params.get("t_lag")

        n = len(t)
        J = np.zeros((n, 4))

        # Partial derivative w.r.t. F_baseline: always 1
        J[:, 0] = 1.0

        mask = t > t_lag
        t_eff = t[mask] - t_lag
        exp_term = np.exp(-k_obs * t_eff)

        # dF/d(F_max) = 1 - exp(-k_obs * (t - t_lag))
        J[mask, 1] = 1 - exp_term

        # dF/d(k_obs) = F_max * (t - t_lag) * exp(-k_obs * (t - t_lag))
        J[mask, 2] = F_max * t_eff * exp_term

        # dF/d(t_lag) = -F_max * k_obs * exp(-k_obs * (t - t_lag))
        J[mask, 3] = -F_max * k_obs * exp_term

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """
        Estimate initial parameters from data.

        Strategy (from PRD F8.2):
        - F_baseline: mean of first 3 timepoints
        - F_max: max(F) - F_baseline
        - t_lag: time when F first exceeds F_baseline + 0.1 * F_max
        - k_obs: ln(2) / (t_half - t_lag)
        """
        params = ModelParameters()

        # F_baseline: mean of first 3 points (or all if fewer)
        n_baseline = min(3, len(F))
        F_baseline = np.mean(F[:n_baseline])
        params.set("F_baseline", F_baseline)

        # F_max: max(F) - F_baseline (ensure positive)
        F_max = max(np.max(F) - F_baseline, 1.0)
        params.set("F_max", F_max)

        # t_lag: time when F first exceeds F_baseline + 0.1 * F_max
        threshold = F_baseline + 0.1 * F_max
        idx_above = np.where(F > threshold)[0]
        if len(idx_above) > 0:
            t_lag = t[idx_above[0]]
        else:
            t_lag = 0.0
        params.set("t_lag", max(t_lag, 0.0))

        # k_obs: estimate from half-max time
        # Find t_half where F = F_baseline + 0.5 * F_max
        half_max = F_baseline + 0.5 * F_max
        idx_half = np.where(F > half_max)[0]
        if len(idx_half) > 0:
            t_half = t[idx_half[0]]
            if t_half > t_lag:
                k_obs = np.log(2) / (t_half - t_lag)
            else:
                k_obs = 0.1  # Default rate
        else:
            k_obs = 0.1  # Default rate if can't estimate

        # Clamp k_obs to reasonable range
        k_obs = np.clip(k_obs, 0.001, 10.0)
        params.set("k_obs", k_obs)

        return params

    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """Get default parameter bounds from PRD."""
        max_t = np.max(t) if len(t) > 0 else 100.0
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F_baseline": (-np.inf, np.inf),
            "F_max": (0.0, 10 * max_F),
            "k_obs": (0.001, 10.0),
            "t_lag": (0.0, max_t / 2)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for delayed exponential model."""
        return {
            "parameter_plots": ["k_obs", "F_max"],
            "derived_metrics": [
                {
                    "name": "t_half",
                    "label": "Half-time",
                    "units": "min",
                    "formula": "ln(2)/k_obs"
                },
                {
                    "name": "plateau",
                    "label": "Plateau",
                    "units": "RFU",
                    "formula": "F_baseline + F_max"
                }
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": r"F(t) = F_{baseline} + F_{max}(1 - e^{-k_{obs}(t - t_{lag})})",
            "color_scheme": {
                "primary": "#1f77b4",
                "secondary": "#ff7f0e",
                "residuals": "#2ca02c"
            }
        }


@kinetic_model
class LogisticModel(KineticModel):
    """
    Logistic (sigmoidal) model for diagnostic purposes.

    F(t) = F_baseline + F_max / (1 + exp(-k * (t - t_mid)))

    Parameters:
        F_baseline: Baseline fluorescence (RFU)
        F_max: Maximum amplitude (RFU)
        k: Growth rate (min⁻¹)
        t_mid: Midpoint time (min)

    Note: This model is for diagnostics only. If data fits this model
    significantly better than delayed exponential (ΔAIC > 10), the well
    is flagged for review but parameters do NOT enter hierarchical analysis.
    """

    @property
    def name(self) -> str:
        return "logistic"

    @property
    def param_names(self) -> List[str]:
        return ["F_baseline", "F_max", "k", "t_mid"]

    @property
    def num_params(self) -> int:
        return 4

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate the logistic model."""
        F_baseline = params.get("F_baseline")
        F_max = params.get("F_max")
        k = params.get("k")
        t_mid = params.get("t_mid")

        # Use stable computation to avoid overflow
        z = -k * (t - t_mid)
        # Clip to avoid overflow in exp
        z = np.clip(z, -500, 500)
        return F_baseline + F_max / (1 + np.exp(z))

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian for logistic model."""
        F_baseline = params.get("F_baseline")
        F_max = params.get("F_max")
        k = params.get("k")
        t_mid = params.get("t_mid")

        n = len(t)
        J = np.zeros((n, 4))

        z = -k * (t - t_mid)
        z = np.clip(z, -500, 500)
        exp_z = np.exp(z)
        denom = (1 + exp_z)
        denom_sq = denom ** 2

        # dF/d(F_baseline) = 1
        J[:, 0] = 1.0

        # dF/d(F_max) = 1 / (1 + exp(-k*(t-t_mid)))
        J[:, 1] = 1.0 / denom

        # dF/d(k) = F_max * (t - t_mid) * exp(-k*(t-t_mid)) / (1 + exp(...))²
        J[:, 2] = F_max * (t - t_mid) * exp_z / denom_sq

        # dF/d(t_mid) = -F_max * k * exp(-k*(t-t_mid)) / (1 + exp(...))²
        J[:, 3] = -F_max * k * exp_z / denom_sq

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """Estimate initial parameters for logistic model."""
        params = ModelParameters()

        # F_baseline: minimum of data
        F_baseline = np.min(F)
        params.set("F_baseline", F_baseline)

        # F_max: range of data
        F_max = max(np.max(F) - F_baseline, 1.0)
        params.set("F_max", F_max)

        # t_mid: time at which F is closest to F_baseline + F_max/2
        half_level = F_baseline + F_max / 2
        idx_mid = np.argmin(np.abs(F - half_level))
        t_mid = t[idx_mid]
        params.set("t_mid", t_mid)

        # k: estimate from slope at midpoint
        # Approximate slope = F_max * k / 4 at midpoint
        # Use finite difference near midpoint
        if idx_mid > 0 and idx_mid < len(t) - 1:
            dt = t[idx_mid + 1] - t[idx_mid - 1]
            if dt > 0:
                slope = (F[idx_mid + 1] - F[idx_mid - 1]) / dt
                k = max(4 * slope / F_max, 0.01) if F_max > 0 else 0.1
            else:
                k = 0.1
        else:
            k = 0.1
        params.set("k", np.clip(k, 0.001, 10.0))

        return params

    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """Get default bounds for logistic model."""
        max_t = np.max(t) if len(t) > 0 else 100.0
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F_baseline": (-np.inf, np.inf),
            "F_max": (0.0, 10 * max_F),
            "k": (0.001, 10.0),
            "t_mid": (0.0, max_t)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for logistic model."""
        return {
            "parameter_plots": ["k", "F_max", "t_mid"],
            "derived_metrics": [
                {
                    "name": "plateau",
                    "label": "Plateau",
                    "units": "RFU",
                    "formula": "F_baseline + F_max"
                }
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": r"F(t) = F_{baseline} + \frac{F_{max}}{1 + e^{-k(t - t_{mid})}}",
            "color_scheme": {
                "primary": "#d62728",
                "secondary": "#9467bd",
                "residuals": "#8c564b"
            }
        }


@kinetic_model
class DoubleExponential(KineticModel):
    """
    Double exponential model for diagnostic purposes.

    F(t) = F_baseline + A1 * (1 - exp(-k1 * t)) + A2 * (1 - exp(-k2 * t))

    Parameters:
        F_baseline: Baseline fluorescence (RFU)
        A1: Amplitude of fast phase (RFU)
        k1: Rate constant of fast phase (min⁻¹)
        A2: Amplitude of slow phase (RFU)
        k2: Rate constant of slow phase (min⁻¹)

    Note: This is a diagnostic model. Wells fitting this significantly better
    than delayed exponential may indicate biphasic kinetics requiring investigation.
    """

    @property
    def name(self) -> str:
        return "double_exponential"

    @property
    def param_names(self) -> List[str]:
        return ["F_baseline", "A1", "k1", "A2", "k2"]

    @property
    def num_params(self) -> int:
        return 5

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate double exponential model."""
        F_baseline = params.get("F_baseline")
        A1 = params.get("A1")
        k1 = params.get("k1")
        A2 = params.get("A2")
        k2 = params.get("k2")

        return F_baseline + A1 * (1 - np.exp(-k1 * t)) + A2 * (1 - np.exp(-k2 * t))

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian for double exponential."""
        A1 = params.get("A1")
        k1 = params.get("k1")
        A2 = params.get("A2")
        k2 = params.get("k2")

        n = len(t)
        J = np.zeros((n, 5))

        exp_k1t = np.exp(-k1 * t)
        exp_k2t = np.exp(-k2 * t)

        J[:, 0] = 1.0  # dF/d(F_baseline)
        J[:, 1] = 1 - exp_k1t  # dF/d(A1)
        J[:, 2] = A1 * t * exp_k1t  # dF/d(k1)
        J[:, 3] = 1 - exp_k2t  # dF/d(A2)
        J[:, 4] = A2 * t * exp_k2t  # dF/d(k2)

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """Estimate initial parameters for double exponential."""
        params = ModelParameters()

        # F_baseline: first value
        F_baseline = F[0] if len(F) > 0 else 0.0
        params.set("F_baseline", F_baseline)

        # Total amplitude
        total_amp = max(np.max(F) - F_baseline, 1.0)

        # Assume 60% fast, 40% slow
        params.set("A1", 0.6 * total_amp)
        params.set("A2", 0.4 * total_amp)

        # Estimate rates from early and late behavior
        params.set("k1", 0.2)  # Faster rate
        params.set("k2", 0.05)  # Slower rate

        return params

    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """Get default bounds for double exponential."""
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F_baseline": (-np.inf, np.inf),
            "A1": (0.0, 10 * max_F),
            "k1": (0.001, 10.0),
            "A2": (0.0, 10 * max_F),
            "k2": (0.0001, 5.0)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for double exponential model."""
        return {
            "parameter_plots": ["k1", "k2", "A1", "A2"],
            "derived_metrics": [
                {
                    "name": "t_half_fast",
                    "label": "Half-time (fast)",
                    "units": "min",
                    "formula": "ln(2)/k1"
                },
                {
                    "name": "t_half_slow",
                    "label": "Half-time (slow)",
                    "units": "min",
                    "formula": "ln(2)/k2"
                },
                {
                    "name": "total_amplitude",
                    "label": "Total Amplitude",
                    "units": "RFU",
                    "formula": "A1 + A2"
                }
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals", "phase_separation"],
            "equation_latex": r"F(t) = F_{baseline} + A_1(1 - e^{-k_1 t}) + A_2(1 - e^{-k_2 t})",
            "color_scheme": {
                "primary": "#17becf",
                "secondary": "#bcbd22",
                "residuals": "#7f7f7f"
            }
        }


@kinetic_model
class LinearInitialRate(KineticModel):
    """
    Linear initial rate model for diagnostic purposes.

    F(t) = F_baseline + v_init * (t - t_lag)    for t > t_lag
    F(t) = F_baseline                            for t <= t_lag

    Parameters:
        F_baseline: Baseline fluorescence (RFU)
        v_init: Initial rate (RFU/min)
        t_lag: Lag time (min)

    Note: This is a diagnostic model useful for very early kinetics
    or when the reaction is far from completion.
    """

    @property
    def name(self) -> str:
        return "linear_initial_rate"

    @property
    def param_names(self) -> List[str]:
        return ["F_baseline", "v_init", "t_lag"]

    @property
    def num_params(self) -> int:
        return 3

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate linear initial rate model."""
        F_baseline = params.get("F_baseline")
        v_init = params.get("v_init")
        t_lag = params.get("t_lag")

        F = np.full_like(t, F_baseline, dtype=float)
        mask = t > t_lag
        F[mask] = F_baseline + v_init * (t[mask] - t_lag)
        return F

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian for linear model."""
        v_init = params.get("v_init")
        t_lag = params.get("t_lag")

        n = len(t)
        J = np.zeros((n, 3))

        J[:, 0] = 1.0  # dF/d(F_baseline)

        mask = t > t_lag
        J[mask, 1] = t[mask] - t_lag  # dF/d(v_init)
        J[mask, 2] = -v_init  # dF/d(t_lag)

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """Estimate initial parameters for linear model."""
        params = ModelParameters()

        # F_baseline: mean of first few points
        n_baseline = min(3, len(F))
        F_baseline = np.mean(F[:n_baseline])
        params.set("F_baseline", F_baseline)

        # t_lag: similar to delayed exponential
        threshold = F_baseline + 0.1 * (np.max(F) - F_baseline)
        idx_above = np.where(F > threshold)[0]
        t_lag = t[idx_above[0]] if len(idx_above) > 0 else 0.0
        params.set("t_lag", max(t_lag, 0.0))

        # v_init: slope of data after lag
        mask = t > t_lag
        if np.sum(mask) >= 2:
            t_active = t[mask]
            F_active = F[mask]
            # Simple linear regression
            dt = t_active[-1] - t_active[0]
            if dt > 0:
                slope = (F_active[-1] - F_active[0]) / dt
                params.set("v_init", max(slope, 0.0))
            else:
                params.set("v_init", 1.0)
        else:
            params.set("v_init", 1.0)

        return params

    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """Get default bounds for linear model."""
        max_t = np.max(t) if len(t) > 0 else 100.0
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F_baseline": (-np.inf, np.inf),
            "v_init": (0.0, max_F),
            "t_lag": (0.0, max_t / 2)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for linear initial rate model."""
        return {
            "parameter_plots": ["v_init", "t_lag"],
            "derived_metrics": [
                {
                    "name": "rate",
                    "label": "Initial Rate",
                    "units": "RFU/min",
                    "formula": "v_init"
                }
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": r"F(t) = F_{baseline} + v_{init}(t - t_{lag})",
            "color_scheme": {
                "primary": "#e377c2",
                "secondary": "#7f7f7f",
                "residuals": "#bcbd22"
            }
        }


@kinetic_model
class PlateauModel(KineticModel):
    """
    Simple plateau model - exponential approach to maximum.

    F(t) = F_baseline + F_max * (1 - exp(-k * t))

    Parameters:
        F_baseline: Initial fluorescence level (RFU)
        F_max: Maximum amplitude above baseline (RFU)
        k: Rate constant (min⁻¹)

    Note: This is the default model - simpler than delayed exponential
    as it assumes no significant lag phase. Good for reactions where
    product formation begins immediately.
    """

    @property
    def name(self) -> str:
        return "plateau"

    @property
    def param_names(self) -> List[str]:
        return ["F_baseline", "F_max", "k"]

    @property
    def num_params(self) -> int:
        return 3

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Evaluate the plateau model."""
        F_baseline = params.get("F_baseline")
        F_max = params.get("F_max")
        k = params.get("k")

        return F_baseline + F_max * (1 - np.exp(-k * t))

    def jacobian(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        """Compute Jacobian matrix for plateau model."""
        F_max = params.get("F_max")
        k = params.get("k")

        n = len(t)
        J = np.zeros((n, 3))

        exp_term = np.exp(-k * t)

        # dF/d(F_baseline) = 1
        J[:, 0] = 1.0

        # dF/d(F_max) = 1 - exp(-k * t)
        J[:, 1] = 1 - exp_term

        # dF/d(k) = F_max * t * exp(-k * t)
        J[:, 2] = F_max * t * exp_term

        return J

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        """
        Estimate initial parameters from data.

        Strategy:
        - F_baseline: mean of first 3 timepoints
        - F_max: max(F) - F_baseline
        - k: estimate from half-max time
        """
        params = ModelParameters()

        # F_baseline: mean of first 3 points (or all if fewer)
        n_baseline = min(3, len(F))
        F_baseline = np.mean(F[:n_baseline])
        params.set("F_baseline", F_baseline)

        # F_max: max(F) - F_baseline (ensure positive)
        F_max = max(np.max(F) - F_baseline, 1.0)
        params.set("F_max", F_max)

        # k: estimate from half-max time
        # Find t_half where F = F_baseline + 0.5 * F_max
        half_max = F_baseline + 0.5 * F_max
        idx_half = np.where(F > half_max)[0]
        if len(idx_half) > 0:
            t_half = t[idx_half[0]]
            if t_half > 0:
                k = np.log(2) / t_half
            else:
                k = 0.1  # Default rate
        else:
            k = 0.1  # Default rate if can't estimate

        # Clamp k to reasonable range
        k = np.clip(k, 0.001, 10.0)
        params.set("k", k)

        return params

    def get_default_bounds(self, t: np.ndarray, F: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """Get default parameter bounds."""
        max_F = np.max(F) if len(F) > 0 else 10000.0

        return {
            "F_baseline": (-np.inf, np.inf),
            "F_max": (0.0, 10 * max_F),
            "k": (0.001, 10.0)
        }

    def get_visualization_config(self) -> Dict[str, Any]:
        """Return visualization configuration for plateau model."""
        return {
            "parameter_plots": ["k", "F_max"],
            "derived_metrics": [
                {
                    "name": "t_half",
                    "label": "Half-time",
                    "units": "min",
                    "formula": "ln(2)/k"
                },
                {
                    "name": "plateau",
                    "label": "Plateau",
                    "units": "RFU",
                    "formula": "F_baseline + F_max"
                }
            ],
            "diagnostic_plots": ["residuals", "qq_plot", "time_vs_residuals"],
            "equation_latex": r"F(t) = F_{baseline} + F_{max}(1 - e^{-kt})",
            "color_scheme": {
                "primary": "#9467bd",
                "secondary": "#8c564b",
                "residuals": "#e377c2"
            }
        }


# Legacy MODEL_REGISTRY - maintained for backward compatibility
# New code should use ModelRegistry.get() and ModelRegistry.all_models()
MODEL_REGISTRY: Dict[str, type] = ModelRegistry.all_models()


def get_model(model_type: str) -> KineticModel:
    """
    Get a kinetic model instance by name.

    Args:
        model_type: Model name from registry

    Returns:
        KineticModel instance

    Raises:
        ValueError: If model type not found

    Note: This is a backward-compatible wrapper around ModelRegistry.get()
    """
    model_class = ModelRegistry.get(model_type)
    return model_class()


def list_models() -> List[str]:
    """
    Get list of available model names.

    Note: This is a backward-compatible wrapper around ModelRegistry.list_available()
    """
    return ModelRegistry.list_available()
