"""
Curve fitting engine for IVT kinetics data.

Phase 4.3: Nonlinear fitting engine
Phase 4.4: Goodness of fit metrics (R², AIC)
Phase 4.5: Covariance & uncertainty
Phase 4.8: Fit failure handling (continue-always with recovery sequence)
"""
import numpy as np
from scipy import optimize
from scipy import stats as scipy_stats
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any, Callable
import warnings
import logging

from app.analysis.kinetic_models import (
    KineticModel, ModelParameters, DelayedExponential,
    get_model, list_models
)
from app.analysis.constants import (
    MIN_R_SQUARED_ACCEPTABLE,
    MIN_R_SQUARED_VALID,
    PERTURBATION_SCALES,
    HIGH_CORRELATION_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class FitStatistics:
    """Goodness of fit statistics."""
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    aic: float
    bic: float
    residual_mean: float
    residual_std: float
    residual_normality_pvalue: Optional[float] = None

    @property
    def is_good_fit(self) -> bool:
        """Check if fit quality is acceptable."""
        return self.r_squared >= MIN_R_SQUARED_ACCEPTABLE and self.residual_normality_pvalue is not None and self.residual_normality_pvalue > 0.05


@dataclass
class FitResult:
    """Complete result of a curve fitting operation."""
    model_name: str
    parameters: ModelParameters
    statistics: FitStatistics
    converged: bool
    n_points: int
    n_params: int

    # Covariance matrix for uncertainty
    covariance_matrix: Optional[np.ndarray] = None
    correlation_matrix: Optional[np.ndarray] = None

    # Fit metadata
    n_iterations: int = 0
    fit_method: str = "curve_fit"
    recovery_stage: int = 0  # 0=initial, 1=retry, 2=global, 3=manual_review

    # Error information
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def get_param(self, name: str) -> Optional[float]:
        """Get parameter value by name."""
        return self.parameters.values.get(name)

    def get_param_se(self, name: str) -> Optional[float]:
        """Get parameter standard error by name."""
        return self.parameters.standard_errors.get(name)

    @property
    def is_valid(self) -> bool:
        """Check if fit result is usable."""
        return self.converged and self.statistics.r_squared >= MIN_R_SQUARED_VALID


class CurveFitter:
    """
    Curve fitting engine with robust failure recovery.

    Implements the PRD-specified recovery sequence:
    1. Initial attempt with default parameters
    2. Retry with perturbed initial parameters
    3. Global optimizer fallback (differential_evolution)
    4. Flag for manual review
    """

    # Default fitting settings
    MAX_ITERATIONS = 5000
    TOLERANCE = 1e-8

    # Recovery settings
    N_RETRY_ATTEMPTS = 8  # Number of perturbed starting points
    GLOBAL_OPT_MAXITER = 200
    GLOBAL_OPT_POPSIZE = 10

    def __init__(self, model: Optional[KineticModel] = None):
        """
        Initialize curve fitter.

        Args:
            model: KineticModel to use (default: DelayedExponential)
        """
        self.model = model or DelayedExponential()

    def fit(
        self,
        t: np.ndarray,
        F: np.ndarray,
        initial_params: Optional[ModelParameters] = None,
        bounds: Optional[Dict[str, Tuple[float, float]]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> FitResult:
        """
        Fit model to data with automatic failure recovery.

        Args:
            t: Timepoints (minutes)
            F: Fluorescence values
            initial_params: Starting parameters (auto-estimated if None)
            bounds: Parameter bounds (default bounds if None)
            progress_callback: Optional callback for progress updates

        Returns:
            FitResult with fitted parameters and statistics
        """
        # Validate input
        t = np.asarray(t, dtype=float)
        F = np.asarray(F, dtype=float)

        if len(t) < self.model.num_params:
            return self._create_failure_result(
                f"Insufficient data points: {len(t)} < {self.model.num_params} parameters",
                t, F, recovery_stage=3
            )

        # Get initial parameters and bounds
        if initial_params is None:
            initial_params = self.model.initial_guess(t, F)

        if bounds is None:
            bounds = self.model.get_default_bounds(t, F)

        # Stage 1: Initial attempt
        result = self._attempt_fit(t, F, initial_params, bounds, recovery_stage=0)
        if result.converged:
            return result

        if progress_callback:
            progress_callback(1, 4)

        # Stage 2: Retry with perturbed parameters
        result = self._retry_with_perturbations(t, F, initial_params, bounds)
        if result.converged:
            return result

        if progress_callback:
            progress_callback(2, 4)

        # Stage 3: Global optimizer
        result = self._global_optimization(t, F, bounds)
        if result.converged:
            return result

        if progress_callback:
            progress_callback(3, 4)

        # Stage 4: Flag for manual review
        result.recovery_stage = 3
        result.error_message = "Fit failed after all recovery attempts. Manual review required."
        result.warnings.append("NEEDS_MANUAL_REVIEW")

        if progress_callback:
            progress_callback(4, 4)

        return result

    def _attempt_fit(
        self,
        t: np.ndarray,
        F: np.ndarray,
        initial_params: ModelParameters,
        bounds: Dict[str, Tuple[float, float]],
        recovery_stage: int = 0
    ) -> FitResult:
        """Single fitting attempt using scipy.optimize.curve_fit."""
        # Prepare bounds for scipy
        param_names = self.model.param_names
        lower_bounds = [bounds.get(name, (-np.inf, np.inf))[0] for name in param_names]
        upper_bounds = [bounds.get(name, (-np.inf, np.inf))[1] for name in param_names]
        scipy_bounds = (lower_bounds, upper_bounds)

        # Initial parameter array
        p0 = initial_params.to_array(param_names)

        # Clip initial params to bounds
        p0 = np.clip(p0, lower_bounds, upper_bounds)

        # Create wrapper function for curve_fit
        # curve_fit expects f(x, *params), not f(x, param_array)
        def model_func(x, *params):
            param_array = np.array(params)
            return self.model.evaluate_array(x, param_array)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt, pcov = optimize.curve_fit(
                    model_func,
                    t, F,
                    p0=p0,
                    bounds=scipy_bounds,
                    maxfev=self.MAX_ITERATIONS,
                    ftol=self.TOLERANCE,
                    xtol=self.TOLERANCE
                )

            # Check for valid covariance
            if np.any(np.isinf(pcov)) or np.any(np.isnan(pcov)):
                raise ValueError("Invalid covariance matrix")

            # Create result
            return self._create_success_result(
                t, F, popt, pcov, param_names, bounds, recovery_stage
            )

        except Exception as e:
            return self._create_failure_result(
                str(e), t, F, recovery_stage=recovery_stage
            )

    def _retry_with_perturbations(
        self,
        t: np.ndarray,
        F: np.ndarray,
        base_params: ModelParameters,
        bounds: Dict[str, Tuple[float, float]]
    ) -> FitResult:
        """
        Retry fitting with perturbed initial parameters.

        Perturbation strategy from PRD:
        - t_lag shifted ±20% of measurement window
        - k_obs scaled by 0.5x and 2x
        - F_max scaled by 0.8x and 1.2x
        - Different F_baseline assumptions
        """
        best_result = None
        best_rss = np.inf

        param_names = self.model.param_names
        base_array = base_params.to_array(param_names)

        # Generate perturbations
        perturbations = self._generate_perturbations(base_params, t, F)

        for perturbed_params in perturbations:
            result = self._attempt_fit(t, F, perturbed_params, bounds, recovery_stage=1)

            if result.converged:
                # Calculate RSS
                predicted = self.model.evaluate(t, result.parameters)
                rss = np.sum((F - predicted) ** 2)

                if rss < best_rss:
                    best_rss = rss
                    best_result = result

        if best_result is not None:
            best_result.recovery_stage = 1
            return best_result

        return self._create_failure_result(
            "All perturbed fits failed", t, F, recovery_stage=1
        )

    def _generate_perturbations(
        self,
        base_params: ModelParameters,
        t: np.ndarray,
        F: np.ndarray
    ) -> List[ModelParameters]:
        """Generate perturbed parameter sets for retry phase."""
        perturbations = []

        param_names = self.model.param_names
        t_range = np.max(t) - np.min(t)
        F_range = np.max(F) - np.min(F)

        base_values = base_params.values.copy()

        # Perturbation multipliers
        scale_factors = PERTURBATION_SCALES

        for scale in scale_factors:
            perturbed = ModelParameters()

            for name in param_names:
                base_val = base_values.get(name, 0.0)

                if name == "t_lag":
                    # Shift t_lag by ±20% of time range
                    shift = (scale - 1.0) * 0.2 * t_range
                    perturbed.set(name, max(0, base_val + shift))
                elif name == "k_obs" or name == "k" or name.startswith("k"):
                    # Scale rate constants
                    perturbed.set(name, base_val * scale)
                elif name == "F_max" or name.startswith("A"):
                    # Scale amplitudes
                    perturbed.set(name, max(0.1, base_val * scale))
                elif name == "F_baseline":
                    # Try different baseline assumptions
                    if scale < 1:
                        perturbed.set(name, np.min(F))
                    elif scale > 1.5:
                        perturbed.set(name, np.mean(F[:3]) if len(F) >= 3 else np.min(F))
                    else:
                        perturbed.set(name, base_val)
                else:
                    perturbed.set(name, base_val)

            perturbations.append(perturbed)

        # Also add a completely fresh guess from the data
        fresh_guess = self.model.initial_guess(t, F)
        perturbations.append(fresh_guess)

        return perturbations

    def _global_optimization(
        self,
        t: np.ndarray,
        F: np.ndarray,
        bounds: Dict[str, Tuple[float, float]]
    ) -> FitResult:
        """
        Global optimization using differential evolution.

        Used as fallback when local optimization fails.
        """
        param_names = self.model.param_names

        # Create bounds list for differential_evolution
        de_bounds = []
        for name in param_names:
            b = bounds.get(name, (-1e6, 1e6))
            # Clamp infinite bounds
            lower = max(b[0], -1e6) if np.isfinite(b[0]) else -1e6
            upper = min(b[1], 1e6) if np.isfinite(b[1]) else 1e6
            de_bounds.append((lower, upper))

        def objective(p):
            """Sum of squared residuals."""
            params = ModelParameters.from_array(p, param_names)
            predicted = self.model.evaluate(t, params)
            return np.sum((F - predicted) ** 2)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = optimize.differential_evolution(
                    objective,
                    bounds=de_bounds,
                    maxiter=self.GLOBAL_OPT_MAXITER,
                    popsize=self.GLOBAL_OPT_POPSIZE,
                    tol=1e-4,
                    seed=42
                )

            if result.success:
                # Refine with local optimizer
                def model_func(x, *params):
                    param_array = np.array(params)
                    return self.model.evaluate_array(x, param_array)

                try:
                    popt, pcov = optimize.curve_fit(
                        model_func,
                        t, F,
                        p0=result.x,
                        bounds=([b[0] for b in de_bounds], [b[1] for b in de_bounds]),
                        maxfev=1000
                    )
                    return self._create_success_result(
                        t, F, popt, pcov, param_names, bounds, recovery_stage=2
                    )
                except Exception:
                    # Use DE result without covariance
                    return self._create_success_result(
                        t, F, result.x, None, param_names, bounds, recovery_stage=2
                    )

        except Exception as e:
            logger.warning(f"Global optimization failed: {e}")

        return self._create_failure_result(
            "Global optimization failed", t, F, recovery_stage=2
        )

    def _create_success_result(
        self,
        t: np.ndarray,
        F: np.ndarray,
        popt: np.ndarray,
        pcov: Optional[np.ndarray],
        param_names: List[str],
        bounds: Dict[str, Tuple[float, float]],
        recovery_stage: int
    ) -> FitResult:
        """Create FitResult from successful optimization."""
        # Extract standard errors from covariance
        if pcov is not None and not np.any(np.isinf(pcov)):
            std_errors = np.sqrt(np.diag(pcov))
        else:
            std_errors = None

        # Create ModelParameters
        parameters = ModelParameters.from_array(popt, param_names, std_errors)
        parameters.bounds = bounds

        # Compute statistics
        statistics = self.compute_statistics(t, F, parameters)

        # Create correlation matrix
        correlation_matrix = None
        if pcov is not None and not np.any(np.isinf(pcov)):
            try:
                std_diag = np.sqrt(np.diag(pcov))
                # Avoid division by zero if any std is zero
                if np.all(std_diag > 0):
                    correlation_matrix = pcov / np.outer(std_diag, std_diag)
            except Exception:
                pass

        # Check for warnings
        fit_warnings = []

        # Check if parameters hit bounds
        for i, name in enumerate(param_names):
            b = bounds.get(name, (-np.inf, np.inf))
            if np.isfinite(b[0]) and np.abs(popt[i] - b[0]) < 1e-6:
                fit_warnings.append(f"{name} at lower bound")
            if np.isfinite(b[1]) and np.abs(popt[i] - b[1]) < 1e-6:
                fit_warnings.append(f"{name} at upper bound")

        # Check for high parameter correlations
        if correlation_matrix is not None:
            for i in range(len(param_names)):
                for j in range(i + 1, len(param_names)):
                    if np.abs(correlation_matrix[i, j]) > HIGH_CORRELATION_THRESHOLD:
                        fit_warnings.append(
                            f"High correlation between {param_names[i]} and {param_names[j]}"
                        )

        return FitResult(
            model_name=self.model.name,
            parameters=parameters,
            statistics=statistics,
            converged=True,
            n_points=len(t),
            n_params=len(param_names),
            covariance_matrix=pcov,
            correlation_matrix=correlation_matrix,
            fit_method="curve_fit" if recovery_stage < 2 else "differential_evolution",
            recovery_stage=recovery_stage,
            warnings=fit_warnings
        )

    def _create_failure_result(
        self,
        error_message: str,
        t: np.ndarray,
        F: np.ndarray,
        recovery_stage: int
    ) -> FitResult:
        """Create FitResult for failed fit."""
        # Create empty parameters
        param_names = self.model.param_names
        parameters = ModelParameters()
        for name in param_names:
            parameters.set(name, np.nan)

        # Create failure statistics
        statistics = FitStatistics(
            r_squared=0.0,
            adjusted_r_squared=0.0,
            rmse=np.inf,
            aic=np.inf,
            bic=np.inf,
            residual_mean=np.nan,
            residual_std=np.nan
        )

        return FitResult(
            model_name=self.model.name,
            parameters=parameters,
            statistics=statistics,
            converged=False,
            n_points=len(t),
            n_params=len(param_names),
            recovery_stage=recovery_stage,
            error_message=error_message
        )

    def compute_statistics(
        self,
        t: np.ndarray,
        F: np.ndarray,
        parameters: ModelParameters
    ) -> FitStatistics:
        """
        Compute goodness of fit statistics.

        Args:
            t: Timepoints
            F: Observed fluorescence
            parameters: Fitted parameters

        Returns:
            FitStatistics object
        """
        n = len(F)
        k = self.model.num_params

        # Predicted values
        predicted = self.model.evaluate(t, parameters)

        # Residuals
        residuals = F - predicted

        # Sum of squares
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((F - np.mean(F)) ** 2)

        # R-squared
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        # Adjusted R-squared
        # Requires n > k + 1 to have positive denominator for adjustment
        if n > k + 1:
            adjusted_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
        else:
            # Not enough degrees of freedom for adjustment
            # When n == k + 1, denominator would be 0 (division by zero)
            # When n <= k, model is overparameterized
            adjusted_r_squared = r_squared
            if n <= k:
                logger.warning(
                    f"Insufficient degrees of freedom for adjusted R²: n={n}, k={k}. "
                    f"Using unadjusted R² value."
                )

        # RMSE
        rmse = np.sqrt(ss_res / n)

        # AIC and BIC
        # AIC = n * ln(RSS/n) + 2k
        # BIC = n * ln(RSS/n) + k * ln(n)
        if ss_res > 0:
            log_likelihood = -n / 2 * (np.log(2 * np.pi * ss_res / n) + 1)
            aic = -2 * log_likelihood + 2 * k
            bic = -2 * log_likelihood + k * np.log(n)
        else:
            aic = -np.inf
            bic = -np.inf

        # Residual statistics
        residual_mean = np.mean(residuals)
        residual_std = np.std(residuals)

        # Residual normality test (Shapiro-Wilk)
        residual_normality_pvalue = None
        if n >= 3:
            try:
                _, p_value = scipy_stats.shapiro(residuals)
                residual_normality_pvalue = p_value
            except Exception:
                pass

        return FitStatistics(
            r_squared=r_squared,
            adjusted_r_squared=adjusted_r_squared,
            rmse=rmse,
            aic=aic,
            bic=bic,
            residual_mean=residual_mean,
            residual_std=residual_std,
            residual_normality_pvalue=residual_normality_pvalue
        )

    def select_best_model(
        self,
        t: np.ndarray,
        F: np.ndarray,
        model_types: Optional[List[str]] = None
    ) -> Tuple[str, FitResult, Dict[str, FitResult]]:
        """
        Fit multiple models and select best by AIC.

        Note: The delayed_exponential model is the primary model for
        hierarchical analysis. Alternative models are for diagnostics only.

        Args:
            t: Timepoints
            F: Fluorescence values
            model_types: List of model names to try (default: all)

        Returns:
            Tuple of (best_model_name, best_result, all_results_dict)
        """
        if model_types is None:
            model_types = list_models()

        results = {}
        best_aic = np.inf
        best_model = None
        best_result = None

        for model_type in model_types:
            try:
                model = get_model(model_type)
                fitter = CurveFitter(model)
                result = fitter.fit(t, F)

                results[model_type] = result

                if result.converged and result.statistics.aic < best_aic:
                    best_aic = result.statistics.aic
                    best_model = model_type
                    best_result = result
            except Exception as e:
                logger.warning(f"Model {model_type} failed: {e}")

        if best_model is None:
            # Return delayed_exponential as default even if failed
            best_model = "delayed_exponential"
            best_result = results.get(best_model)

        return best_model, best_result, results


def fit_delayed_exponential(
    t: np.ndarray,
    F: np.ndarray,
    **kwargs
) -> FitResult:
    """
    Convenience function to fit delayed exponential model.

    Args:
        t: Timepoints (minutes)
        F: Fluorescence values
        **kwargs: Additional arguments passed to CurveFitter.fit()

    Returns:
        FitResult
    """
    fitter = CurveFitter(DelayedExponential())
    return fitter.fit(t, F, **kwargs)
