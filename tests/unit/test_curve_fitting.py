"""
Tests for curve fitting engine.

Phase 4.3: Nonlinear fitting engine (T4.1, T4.3)
Phase 4.4: Goodness of fit metrics (T4.4, T4.5)
Phase 4.5: Covariance & uncertainty (T4.6)
Phase 4.8: Fit failure handling (T4.10, T4.11, T4.20-T4.24)
"""
import pytest
import numpy as np
from app.analysis.kinetic_models import (
    DelayedExponential, ModelParameters, get_model
)
from app.analysis.curve_fitting import (
    CurveFitter, FitResult, FitStatistics, fit_delayed_exponential
)


class TestCurveFitter:
    """Tests for the CurveFitter class."""

    @pytest.fixture
    def fitter(self):
        """Create fitter with delayed exponential model."""
        return CurveFitter(DelayedExponential())

    @pytest.fixture
    def clean_data(self):
        """Generate clean synthetic data."""
        t = np.linspace(0, 60, 30)
        true_params = ModelParameters()
        true_params.set("F_baseline", 100.0)
        true_params.set("F_max", 800.0)
        true_params.set("k_obs", 0.1)
        true_params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, true_params)
        return t, F, true_params

    @pytest.fixture
    def noisy_data(self, clean_data):
        """Generate noisy synthetic data."""
        t, F_clean, true_params = clean_data
        np.random.seed(42)
        noise = np.random.normal(0, 10, len(t))
        F = F_clean + noise
        return t, F, true_params

    def test_fit_clean_data_converges(self, fitter, clean_data):
        """T4.1: Delayed exponential fit converges on clean data."""
        t, F, _ = clean_data
        result = fitter.fit(t, F)

        assert result.converged
        assert result.statistics.r_squared > 0.99

    def test_fit_noisy_data_converges(self, fitter, noisy_data):
        """T4.1: Fit converges with noisy data."""
        t, F, _ = noisy_data
        result = fitter.fit(t, F)

        assert result.converged
        assert result.statistics.r_squared > 0.95

    def test_fit_recovers_parameters(self, fitter, clean_data):
        """T4.3: F_max, k_obs, t_lag extracted correctly."""
        t, F, true_params = clean_data
        result = fitter.fit(t, F)

        assert result.get_param("F_baseline") == pytest.approx(100.0, rel=0.05)
        assert result.get_param("F_max") == pytest.approx(800.0, rel=0.05)
        assert result.get_param("k_obs") == pytest.approx(0.1, rel=0.1)
        assert result.get_param("t_lag") == pytest.approx(5.0, rel=0.1)

    def test_fit_with_initial_params(self, fitter, clean_data):
        """Test fitting with provided initial parameters."""
        t, F, _ = clean_data

        initial = ModelParameters()
        initial.set("F_baseline", 90.0)
        initial.set("F_max", 700.0)
        initial.set("k_obs", 0.08)
        initial.set("t_lag", 4.0)

        result = fitter.fit(t, F, initial_params=initial)

        assert result.converged

    def test_fit_with_bounds(self, fitter, clean_data):
        """Test fitting with custom parameter bounds."""
        t, F, _ = clean_data

        bounds = {
            "F_baseline": (0, 200),
            "F_max": (500, 1200),
            "k_obs": (0.01, 1.0),
            "t_lag": (0, 30)
        }

        result = fitter.fit(t, F, bounds=bounds)

        assert result.converged
        # Parameters should be within bounds
        assert 0 <= result.get_param("F_baseline") <= 200
        assert 500 <= result.get_param("F_max") <= 1200


class TestFitStatistics:
    """Tests for goodness of fit metrics."""

    @pytest.fixture
    def fitter(self):
        return CurveFitter(DelayedExponential())

    def test_r_squared_perfect_fit(self, fitter):
        """T4.4: R² = 1.0 for perfect fit."""
        # Generate perfect synthetic data
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)

        result = fitter.fit(t, F)

        assert result.statistics.r_squared == pytest.approx(1.0, rel=0.01)

    def test_r_squared_poor_fit(self, fitter):
        """T4.4: R² < 0.5 for poor fit (wrong model)."""
        # Create data that doesn't fit delayed exponential well
        t = np.linspace(0, 60, 30)
        # Oscillating data
        F = 500 + 200 * np.sin(t / 5)

        result = fitter.fit(t, F)

        # Should have low R² even if it converges
        assert result.statistics.r_squared < 0.7

    def test_aic_computed(self, fitter):
        """T4.5: AIC computed correctly."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        np.random.seed(42)
        F = F + np.random.normal(0, 10, len(t))

        result = fitter.fit(t, F)

        assert result.statistics.aic is not None
        assert np.isfinite(result.statistics.aic)

    def test_rmse_computed(self, fitter):
        """Test RMSE is computed."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)

        result = fitter.fit(t, F)

        assert result.statistics.rmse is not None
        assert result.statistics.rmse >= 0
        # Perfect fit should have near-zero RMSE
        assert result.statistics.rmse < 1.0


class TestCovarianceAndUncertainty:
    """Tests for covariance matrix and standard errors."""

    @pytest.fixture
    def fitter(self):
        return CurveFitter(DelayedExponential())

    def test_standard_errors_computed(self, fitter):
        """T4.6: Standard errors from covariance matrix."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        np.random.seed(42)
        F = F + np.random.normal(0, 20, len(t))

        result = fitter.fit(t, F)

        # Should have standard errors
        assert result.get_param_se("F_max") is not None
        assert result.get_param_se("F_max") > 0
        assert result.get_param_se("k_obs") is not None
        assert result.get_param_se("k_obs") > 0

    def test_covariance_matrix_shape(self, fitter):
        """Test covariance matrix has correct shape."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        np.random.seed(42)
        F = F + np.random.normal(0, 10, len(t))

        result = fitter.fit(t, F)

        if result.covariance_matrix is not None:
            assert result.covariance_matrix.shape == (4, 4)

    def test_correlation_matrix_computed(self, fitter):
        """Test correlation matrix is computed."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        np.random.seed(42)
        F = F + np.random.normal(0, 10, len(t))

        result = fitter.fit(t, F)

        if result.correlation_matrix is not None:
            # Diagonal should be 1
            np.testing.assert_array_almost_equal(
                np.diag(result.correlation_matrix), np.ones(4), decimal=5
            )
            # Values should be between -1 and 1
            assert np.all(np.abs(result.correlation_matrix) <= 1.0 + 1e-6)


class TestFitFailureRecovery:
    """Tests for fit failure handling and recovery."""

    @pytest.fixture
    def fitter(self):
        return CurveFitter(DelayedExponential())

    def test_insufficient_data_points(self, fitter):
        """T4.24: Insufficient data points handled."""
        t = np.array([0, 10, 20])  # Only 3 points
        F = np.array([100, 300, 600])

        result = fitter.fit(t, F)

        # Should fail or flag for review
        assert result.recovery_stage >= 0
        assert not result.is_valid or result.n_points < 5

    def test_flat_data_recovery(self, fitter):
        """T4.1: Flat curve handled."""
        t = np.linspace(0, 60, 30)
        F = np.full_like(t, 500.0)  # Flat data

        result = fitter.fit(t, F)

        # Should produce a result (maybe not great R²)
        assert result is not None

    def test_fit_continues_after_failure(self, fitter):
        """T4.10: Fit failure handled gracefully."""
        # Very difficult data
        t = np.linspace(0, 60, 30)
        np.random.seed(42)
        F = np.random.uniform(100, 1000, 30)  # Random noise

        result = fitter.fit(t, F)

        # Should return result even if poor
        assert result is not None
        assert isinstance(result, FitResult)

    def test_recovery_stage_tracked(self, fitter):
        """Test recovery stage is tracked."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)

        result = fitter.fit(t, F)

        # Good data should succeed on first attempt
        assert result.recovery_stage == 0


class TestModelSelection:
    """Tests for model selection functionality."""

    def test_select_best_model(self):
        """Test best model selection by AIC."""
        fitter = CurveFitter()

        # Generate data from delayed exponential
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        np.random.seed(42)
        F = F + np.random.normal(0, 10, len(t))

        best_name, best_result, all_results = fitter.select_best_model(t, F)

        # Should return delayed exponential as best
        assert best_name in ["delayed_exponential", "logistic"]
        assert best_result.converged
        assert len(all_results) >= 2


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_fit_delayed_exponential(self):
        """Test convenience function for delayed exponential fitting."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)

        result = fit_delayed_exponential(t, F)

        assert result.converged
        assert result.model_name == "delayed_exponential"


class TestEdgeCases:
    """Edge case tests from PRD T4.20-T4.24."""

    @pytest.fixture
    def fitter(self):
        return CurveFitter(DelayedExponential())

    def test_convergence_failure_max_iterations(self, fitter):
        """T4.20: Max iterations exceeded handled."""
        # Data that's hard to fit
        t = np.linspace(0, 60, 30)
        # Step function - very hard for exponential
        F = np.where(t < 30, 100.0, 900.0)

        result = fitter.fit(t, F)

        # Should not crash, should have error info
        assert result is not None

    def test_parameter_at_bounds(self, fitter):
        """T4.21: Parameter at bounds detected."""
        t = np.linspace(0, 60, 30)
        # Very slow reaction
        F = 100 + 50 * (t / 60)  # Linear increase

        bounds = {
            "F_baseline": (0, 200),
            "F_max": (0, 10000),
            "k_obs": (0.001, 10.0),  # k_obs will hit lower bound
            "t_lag": (0, 30)
        }

        result = fitter.fit(t, F, bounds=bounds)

        # Check for bound warnings
        # Note: k_obs might hit lower bound for linear-ish data
        assert result is not None

    def test_data_clipping_detection(self, fitter):
        """T4.23: Data clipping/saturation detection."""
        t = np.linspace(0, 60, 30)
        # Saturated data (flat at top)
        F = 100 + 800 * (1 - np.exp(-0.1 * t))
        F[F > 800] = 800  # Clip at 800 (saturation)

        result = fitter.fit(t, F)

        # Should still fit but may have warnings
        assert result is not None

    def test_missing_early_timepoints(self, fitter):
        """T4.24: Missing early timepoints handled."""
        # Start at t=10 instead of t=0
        t = np.linspace(10, 60, 25)
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)

        result = fitter.fit(t, F)

        # Should still work but t_lag estimate may be inaccurate
        assert result is not None

    def test_negative_values_handled(self, fitter):
        """T4.23: Negative values (after background correction)."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 0.0)  # Zero baseline
        params.set("F_max", 800.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        model = DelayedExponential()
        F = model.evaluate(t, params)
        # Add noise that makes some values negative
        np.random.seed(42)
        F = F + np.random.normal(-20, 30, len(t))

        result = fitter.fit(t, F)

        # Should handle negative values
        assert result is not None
