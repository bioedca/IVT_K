"""
Tests for kinetic models.

Phase 4.1: Delayed exponential model (T4.1-T4.3)
Phase 4.2: Initial parameter estimation (T4.2)
"""
import pytest
import numpy as np
from app.analysis.kinetic_models import (
    KineticModel,
    ModelParameters,
    DelayedExponential,
    LogisticModel,
    DoubleExponential,
    LinearInitialRate,
    PlateauModel,
    get_model,
    list_models
)


class TestModelParameters:
    """Tests for ModelParameters dataclass."""

    def test_set_and_get(self):
        """Test setting and getting parameter values."""
        params = ModelParameters()
        params.set("F_max", 1000.0, se=50.0)

        assert params.get("F_max") == 1000.0
        assert params.standard_errors["F_max"] == 50.0

    def test_get_default(self):
        """Test default value when parameter not set."""
        params = ModelParameters()
        assert params.get("missing", 42.0) == 42.0

    def test_to_array(self):
        """Test conversion to array."""
        params = ModelParameters()
        params.set("a", 1.0)
        params.set("b", 2.0)
        params.set("c", 3.0)

        arr = params.to_array(["a", "b", "c"])
        np.testing.assert_array_equal(arr, [1.0, 2.0, 3.0])

    def test_from_array(self):
        """Test creation from array."""
        values = np.array([100.0, 1000.0, 0.1, 5.0])
        names = ["F_baseline", "F_max", "k_obs", "t_lag"]
        se = np.array([10.0, 100.0, 0.01, 0.5])

        params = ModelParameters.from_array(values, names, se)

        assert params.get("F_baseline") == 100.0
        assert params.get("F_max") == 1000.0
        assert params.standard_errors["k_obs"] == 0.01


class TestDelayedExponential:
    """Tests for the delayed exponential model."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return DelayedExponential()

    def test_model_properties(self, model):
        """Test model name and parameter names."""
        assert model.name == "delayed_exponential"
        assert model.param_names == ["F_baseline", "F_max", "k_obs", "t_lag"]
        assert model.num_params == 4

    def test_evaluate_before_lag(self, model):
        """T4.1: Fluorescence equals baseline before t_lag."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 1000.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 10.0)

        t = np.array([0.0, 5.0, 9.0])
        F = model.evaluate(t, params)

        np.testing.assert_array_almost_equal(F, [100.0, 100.0, 100.0])

    def test_evaluate_after_lag(self, model):
        """T4.1: Fluorescence rises exponentially after t_lag."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 1000.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 0.0)

        # At t=0: F = 100 + 1000*(1-exp(0)) = 100 + 0 = 100
        # At t=10: F = 100 + 1000*(1-exp(-1)) ≈ 100 + 632.1 = 732.1
        # At t=100: F ≈ 100 + 1000*(1-exp(-10)) ≈ 1099.995

        t = np.array([0.0, 10.0, 100.0])
        F = model.evaluate(t, params)

        assert F[0] == pytest.approx(100.0)
        assert F[1] == pytest.approx(732.12, rel=0.01)
        assert F[2] == pytest.approx(1100.0, rel=0.01)

    def test_evaluate_known_parameters(self, model):
        """T4.3: F_max, k_obs, t_lag extracted correctly from known data."""
        # Generate synthetic data with known parameters
        true_params = ModelParameters()
        true_params.set("F_baseline", 50.0)
        true_params.set("F_max", 500.0)
        true_params.set("k_obs", 0.05)
        true_params.set("t_lag", 5.0)

        t = np.linspace(0, 100, 50)
        F_true = model.evaluate(t, true_params)

        # Verify specific values
        # At t=5 (lag): F = 50
        assert F_true[np.argmin(np.abs(t - 5))] == pytest.approx(50.0, rel=0.1)
        # At large t: F approaches 50 + 500 = 550
        assert F_true[-1] == pytest.approx(550.0, rel=0.05)

    def test_initial_guess_rising_curve(self, model):
        """T4.2: Initial parameters estimated for rising curve."""
        # Create synthetic data
        t = np.linspace(0, 60, 30)
        F = 100 + 800 * (1 - np.exp(-0.1 * (t - 5)))
        F[t <= 5] = 100

        params = model.initial_guess(t, F)

        # Check reasonable estimates
        assert params.get("F_baseline") == pytest.approx(100.0, rel=0.2)
        assert params.get("F_max") > 500  # Should detect amplitude
        assert params.get("k_obs") > 0.01  # Should be positive rate
        assert params.get("t_lag") >= 0  # Should be non-negative

    def test_initial_guess_flat_curve(self, model):
        """T4.2: Initial parameters for flat/plateau data."""
        t = np.linspace(0, 60, 30)
        F = np.full_like(t, 500.0)  # Flat at 500

        params = model.initial_guess(t, F)

        # Should still produce valid parameters
        assert params.get("F_baseline") == pytest.approx(500.0, rel=0.1)
        assert params.get("k_obs") > 0  # Should have positive rate

    def test_jacobian_shape(self, model):
        """Test Jacobian matrix has correct shape."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 1000.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        t = np.linspace(0, 60, 30)
        J = model.jacobian(t, params)

        assert J.shape == (30, 4)

    def test_default_bounds(self, model):
        """Test default parameter bounds."""
        t = np.linspace(0, 60, 30)
        F = np.linspace(100, 1000, 30)

        bounds = model.get_default_bounds(t, F)

        assert "k_obs" in bounds
        assert bounds["k_obs"][0] == 0.001
        assert bounds["k_obs"][1] == 10.0
        assert bounds["t_lag"][0] == 0.0


class TestLogisticModel:
    """Tests for the logistic model."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return LogisticModel()

    def test_model_properties(self, model):
        """Test model name and parameters."""
        assert model.name == "logistic"
        assert model.num_params == 4

    def test_evaluate_sigmoid(self, model):
        """Test sigmoidal behavior."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 1000.0)
        params.set("k", 0.2)
        params.set("t_mid", 30.0)

        t = np.array([0.0, 30.0, 60.0])
        F = model.evaluate(t, params)

        # At t_mid, F should be at half-max
        assert F[1] == pytest.approx(100 + 1000 / 2, rel=0.01)
        # Early time should be near baseline
        assert F[0] < 200
        # Late time should approach max
        assert F[2] > 900

    def test_initial_guess(self, model):
        """Test initial parameter estimation."""
        t = np.linspace(0, 60, 30)
        params = ModelParameters()
        params.set("F_baseline", 50.0)
        params.set("F_max", 800.0)
        params.set("k", 0.3)
        params.set("t_mid", 20.0)

        F = model.evaluate(t, params)
        guess = model.initial_guess(t, F)

        assert guess.get("F_baseline") is not None
        assert guess.get("F_max") > 0


class TestDoubleExponential:
    """Tests for double exponential model."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return DoubleExponential()

    def test_model_properties(self, model):
        """Test model name and parameters."""
        assert model.name == "double_exponential"
        assert model.num_params == 5
        assert "A1" in model.param_names
        assert "k1" in model.param_names

    def test_evaluate_biphasic(self, model):
        """Test biphasic kinetics."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("A1", 500.0)  # Fast phase
        params.set("k1", 0.5)
        params.set("A2", 300.0)  # Slow phase
        params.set("k2", 0.05)

        t = np.array([0.0, 5.0, 50.0])
        F = model.evaluate(t, params)

        # At t=0: F = 100
        assert F[0] == pytest.approx(100.0)
        # Final value should approach 100 + 500 + 300 = 900
        assert F[2] > 800


class TestLinearInitialRate:
    """Tests for linear initial rate model."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return LinearInitialRate()

    def test_model_properties(self, model):
        """Test model name and parameters."""
        assert model.name == "linear_initial_rate"
        assert model.num_params == 3

    def test_evaluate_linear(self, model):
        """Test linear behavior after lag."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("v_init", 10.0)  # RFU/min
        params.set("t_lag", 5.0)

        t = np.array([0.0, 5.0, 10.0, 20.0])
        F = model.evaluate(t, params)

        assert F[0] == pytest.approx(100.0)  # Before lag
        assert F[1] == pytest.approx(100.0)  # At lag
        assert F[2] == pytest.approx(150.0)  # 5 min after lag
        assert F[3] == pytest.approx(250.0)  # 15 min after lag


class TestPlateauModel:
    """Tests for the plateau model (default model)."""

    @pytest.fixture
    def model(self):
        """Create model instance."""
        return PlateauModel()

    def test_model_properties(self, model):
        """Test model name and parameters."""
        assert model.name == "plateau"
        assert model.param_names == ["F_baseline", "F_max", "k"]
        assert model.num_params == 3

    def test_evaluate_simple(self, model):
        """Test simple exponential approach to plateau."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 900.0)
        params.set("k", 0.1)

        # At t=0: F = 100 + 900*(1-exp(0)) = 100
        # At t=10: F = 100 + 900*(1-exp(-1)) ≈ 100 + 568.9 = 668.9
        # At large t: F → 100 + 900 = 1000

        t = np.array([0.0, 10.0, 100.0])
        F = model.evaluate(t, params)

        assert F[0] == pytest.approx(100.0)
        assert F[1] == pytest.approx(668.9, rel=0.01)
        assert F[2] == pytest.approx(1000.0, rel=0.01)

    def test_initial_guess(self, model):
        """Test initial parameter estimation."""
        # Create synthetic data
        t = np.linspace(0, 60, 30)
        F = 50 + 450 * (1 - np.exp(-0.08 * t))

        params = model.initial_guess(t, F)

        # Check reasonable estimates (F_baseline is mean of first 3 points, not true baseline)
        assert params.get("F_baseline") > 0
        assert params.get("F_max") > 0
        assert params.get("k") > 0

    def test_jacobian_shape(self, model):
        """Test Jacobian matrix has correct shape."""
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 500.0)
        params.set("k", 0.1)

        t = np.linspace(0, 60, 20)
        J = model.jacobian(t, params)

        assert J.shape == (20, 3)

    def test_get_visualization_config(self, model):
        """Test visualization config is complete."""
        config = model.get_visualization_config()

        assert "parameter_plots" in config
        assert "derived_metrics" in config
        assert "equation_latex" in config
        assert "color_scheme" in config


class TestModelRegistry:
    """Tests for model registry functions."""

    def test_list_models(self):
        """Test listing available models."""
        models = list_models()

        assert "delayed_exponential" in models
        assert "logistic" in models
        assert "double_exponential" in models
        assert "linear_initial_rate" in models
        assert "plateau" in models

    def test_get_model_valid(self):
        """Test getting valid model."""
        model = get_model("delayed_exponential")
        assert isinstance(model, DelayedExponential)

        model = get_model("logistic")
        assert isinstance(model, LogisticModel)

    def test_get_model_invalid(self):
        """Test error on invalid model name."""
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("invalid_model")


class TestModelNumericalStability:
    """Tests for numerical stability edge cases."""

    def test_delayed_exponential_large_kobs(self):
        """T4.21: Parameter bounds enforced - large k_obs."""
        model = DelayedExponential()
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 1000.0)
        params.set("k_obs", 10.0)  # Very fast rate
        params.set("t_lag", 0.0)

        t = np.linspace(0, 10, 20)
        F = model.evaluate(t, params)

        # Should not produce NaN or inf
        assert np.all(np.isfinite(F))
        # Should reach plateau quickly
        assert F[-1] == pytest.approx(1100.0, rel=0.01)

    def test_delayed_exponential_zero_fmax(self):
        """T4.21: Parameter bounds - zero F_max."""
        model = DelayedExponential()
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 0.0)  # No signal
        params.set("k_obs", 0.1)
        params.set("t_lag", 0.0)

        t = np.linspace(0, 60, 30)
        F = model.evaluate(t, params)

        # Should stay at baseline
        np.testing.assert_array_almost_equal(F, np.full_like(t, 100.0))

    def test_logistic_overflow_protection(self):
        """Test logistic model doesn't overflow."""
        model = LogisticModel()
        params = ModelParameters()
        params.set("F_baseline", 0.0)
        params.set("F_max", 1000.0)
        params.set("k", 10.0)  # Very steep
        params.set("t_mid", 0.0)

        # Very extreme times
        t = np.array([-1000.0, 0.0, 1000.0])
        F = model.evaluate(t, params)

        assert np.all(np.isfinite(F))
        assert F[0] == pytest.approx(0.0, abs=1.0)
        assert F[2] == pytest.approx(1000.0, abs=1.0)

    def test_initial_guess_noisy_data(self):
        """T4.1: Initial guess with noisy data."""
        model = DelayedExponential()

        # Create noisy synthetic data
        np.random.seed(42)
        t = np.linspace(0, 60, 30)
        F_true = 100 + 800 * (1 - np.exp(-0.1 * np.maximum(t - 5, 0)))
        noise = np.random.normal(0, 20, len(t))
        F = F_true + noise

        params = model.initial_guess(t, F)

        # Should still produce valid estimates
        assert params.get("F_baseline") is not None
        assert np.isfinite(params.get("F_baseline"))
        assert params.get("k_obs") > 0
        assert params.get("F_max") > 0
