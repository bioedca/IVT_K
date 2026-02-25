"""
Sprint 9: Plugin Architecture Tests

Tests for the extensible kinetic model system with plugin architecture.

PRD Reference: Phase 12 - Extensibility (Plugin System)

Test Coverage:
- T12.1: KineticModel abstract methods enforced
- T12.2: Model registered via decorator
- T12.3: Registry.get returns correct model
- T12.4: Plugin discovered from directory
- T12.5: Plugin import error handled gracefully
- T12.6: Visualization config returned
"""
import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np

from app.analysis.kinetic_models import (
    KineticModel,
    ModelRegistry,
    kinetic_model,
    ModelParameters,
    DelayedExponential,
    LogisticModel,
    DoubleExponential,
    LinearInitialRate,
    get_model,
    list_models,
)


class TestModelRegistry:
    """Tests for ModelRegistry class (T12.2, T12.3)."""

    def test_registry_has_builtin_models(self):
        """T12.2: Verify built-in models are registered."""
        registered = ModelRegistry.list_available()
        assert "delayed_exponential" in registered
        assert "logistic" in registered
        assert "double_exponential" in registered
        assert "linear_initial_rate" in registered

    def test_registry_get_valid_model(self):
        """T12.3: Registry.get returns correct model class."""
        model_class = ModelRegistry.get("delayed_exponential")
        assert model_class is DelayedExponential

        model_class = ModelRegistry.get("logistic")
        assert model_class is LogisticModel

    def test_registry_get_invalid_model_raises(self):
        """T12.3: Registry.get raises ValueError for unknown model."""
        with pytest.raises(ValueError, match="Unknown model"):
            ModelRegistry.get("nonexistent_model")

    def test_registry_all_models_returns_copy(self):
        """Verify all_models returns a copy, not the original dict."""
        models = ModelRegistry.all_models()
        original_count = len(models)

        # Modifying the copy should not affect the registry
        models["test"] = None
        assert len(ModelRegistry.all_models()) == original_count

    def test_registry_is_registered(self):
        """Test is_registered method."""
        assert ModelRegistry.is_registered("delayed_exponential")
        assert not ModelRegistry.is_registered("nonexistent")

    def test_registry_list_available(self):
        """Test list_available method."""
        available = ModelRegistry.list_available()
        assert isinstance(available, list)
        assert len(available) >= 4  # At least the 4 built-in models


class TestKineticModelDecorator:
    """Tests for @kinetic_model decorator (T12.2)."""

    def test_decorator_registers_model(self):
        """T12.2: @kinetic_model decorator registers the model."""
        # Create a test model with unique name
        @kinetic_model
        class TestModel(KineticModel):
            @property
            def name(self) -> str:
                return "test_decorator_model"

            @property
            def param_names(self) -> List[str]:
                return ["a", "b"]

            @property
            def num_params(self) -> int:
                return 2

            def evaluate(self, t, params):
                return t * params.get("a") + params.get("b")

            def jacobian(self, t, params):
                return np.column_stack([t, np.ones_like(t)])

            def initial_guess(self, t, F):
                return ModelParameters()

            def get_default_bounds(self, t, F):
                return {"a": (0, 10), "b": (0, 10)}

        # Verify it was registered
        assert ModelRegistry.is_registered("test_decorator_model")

        # Clean up
        ModelRegistry.unregister("test_decorator_model")

    def test_decorator_preserves_class(self):
        """Decorator should return the original class unchanged."""
        @kinetic_model
        class AnotherTestModel(KineticModel):
            @property
            def name(self) -> str:
                return "another_test_model"

            @property
            def param_names(self) -> List[str]:
                return ["x"]

            @property
            def num_params(self) -> int:
                return 1

            def evaluate(self, t, params):
                return t * params.get("x")

            def jacobian(self, t, params):
                return t.reshape(-1, 1)

            def initial_guess(self, t, F):
                return ModelParameters()

            def get_default_bounds(self, t, F):
                return {"x": (0, 10)}

        # Verify the class is still usable
        model = AnotherTestModel()
        assert model.name == "another_test_model"

        # Clean up
        ModelRegistry.unregister("another_test_model")


class TestKineticModelAbstract:
    """Tests for KineticModel abstract base class (T12.1)."""

    def test_cannot_instantiate_abstract_class(self):
        """T12.1: Cannot instantiate KineticModel directly."""
        with pytest.raises(TypeError):
            KineticModel()

    def test_must_implement_name_property(self):
        """T12.1: Subclass must implement name property."""
        class IncompleteModel(KineticModel):
            @property
            def param_names(self) -> List[str]:
                return ["a"]

            @property
            def num_params(self) -> int:
                return 1

            def evaluate(self, t, params):
                return t

            def jacobian(self, t, params):
                return t.reshape(-1, 1)

            def initial_guess(self, t, F):
                return ModelParameters()

            def get_default_bounds(self, t, F):
                return {"a": (0, 10)}

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_must_implement_evaluate(self):
        """T12.1: Subclass must implement evaluate method."""
        class IncompleteModel(KineticModel):
            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def param_names(self) -> List[str]:
                return ["a"]

            @property
            def num_params(self) -> int:
                return 1

            def jacobian(self, t, params):
                return t.reshape(-1, 1)

            def initial_guess(self, t, F):
                return ModelParameters()

            def get_default_bounds(self, t, F):
                return {"a": (0, 10)}

        with pytest.raises(TypeError):
            IncompleteModel()


class TestVisualizationConfig:
    """Tests for visualization configuration API (T12.6)."""

    def test_delayed_exponential_viz_config(self):
        """T12.6: DelayedExponential returns visualization config."""
        model = DelayedExponential()
        config = model.get_visualization_config()

        assert "parameter_plots" in config
        assert "derived_metrics" in config
        assert "diagnostic_plots" in config
        assert "equation_latex" in config
        assert "color_scheme" in config

        # Check parameter_plots contains expected values
        assert "k_obs" in config["parameter_plots"]
        assert "F_max" in config["parameter_plots"]

        # Check derived_metrics has expected structure
        assert len(config["derived_metrics"]) >= 1
        metric = config["derived_metrics"][0]
        assert "name" in metric
        assert "label" in metric
        assert "units" in metric
        assert "formula" in metric

    def test_logistic_viz_config(self):
        """T12.6: LogisticModel returns visualization config."""
        model = LogisticModel()
        config = model.get_visualization_config()

        assert "parameter_plots" in config
        assert "equation_latex" in config
        assert config["equation_latex"] is not None

    def test_double_exponential_viz_config(self):
        """T12.6: DoubleExponential returns visualization config."""
        model = DoubleExponential()
        config = model.get_visualization_config()

        assert "parameter_plots" in config
        assert "k1" in config["parameter_plots"]
        assert "k2" in config["parameter_plots"]

        # Should have multiple derived metrics for biphasic
        assert len(config["derived_metrics"]) >= 2

    def test_linear_viz_config(self):
        """T12.6: LinearInitialRate returns visualization config."""
        model = LinearInitialRate()
        config = model.get_visualization_config()

        assert "parameter_plots" in config
        assert "v_init" in config["parameter_plots"]

    def test_all_models_have_viz_config(self):
        """All registered models should have visualization config."""
        for model_name in ModelRegistry.list_available():
            model_class = ModelRegistry.get(model_name)
            model = model_class()
            config = model.get_visualization_config()

            assert isinstance(config, dict)
            assert "parameter_plots" in config
            assert "diagnostic_plots" in config


class TestPluginDiscovery:
    """Tests for plugin discovery system (T12.4, T12.5)."""

    def test_discover_plugins_nonexistent_dir(self):
        """T12.4: discover_plugins handles nonexistent directory gracefully."""
        # Should not raise, just return empty list
        loaded = ModelRegistry.discover_plugins("/nonexistent/path/plugins")
        assert loaded == []

    def test_discover_plugins_empty_dir(self):
        """T12.4: discover_plugins handles empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = os.path.join(tmpdir, "kinetic_models")
            os.makedirs(plugin_dir)

            loaded = ModelRegistry.discover_plugins(plugin_dir)
            assert loaded == []

    def test_plugin_error_tracking(self):
        """T12.5: Plugin import errors are tracked gracefully."""
        # Clear previous errors
        ModelRegistry.clear_plugin_errors()

        # Create a temporary directory with a bad plugin
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = os.path.join(tmpdir, "kinetic_models")
            os.makedirs(plugin_dir)

            # Create a plugin file with syntax error
            bad_plugin = os.path.join(plugin_dir, "bad_plugin.py")
            with open(bad_plugin, "w") as f:
                f.write("this is not valid python syntax !!!")

            # Attempt discovery
            loaded = ModelRegistry.discover_plugins(plugin_dir)

            # The bad plugin should not be loaded
            assert "bad_plugin.py" not in [os.path.basename(p) for p in loaded]

    def test_get_plugin_errors(self):
        """T12.5: Can retrieve plugin errors."""
        errors = ModelRegistry.get_plugin_errors()
        assert isinstance(errors, dict)


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy functions."""

    def test_get_model_function(self):
        """Legacy get_model() function works."""
        model = get_model("delayed_exponential")
        assert isinstance(model, DelayedExponential)

    def test_list_models_function(self):
        """Legacy list_models() function works."""
        models = list_models()
        assert "delayed_exponential" in models
        assert "logistic" in models

    def test_get_model_invalid_raises(self):
        """Legacy get_model() raises ValueError for invalid model."""
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("invalid_model_name")


class TestModelParametersIntegration:
    """Integration tests for ModelParameters with models."""

    def test_model_with_parameters(self):
        """Test model evaluation with ModelParameters."""
        model = DelayedExponential()
        params = ModelParameters()
        params.set("F_baseline", 100.0)
        params.set("F_max", 500.0)
        params.set("k_obs", 0.1)
        params.set("t_lag", 5.0)

        t = np.linspace(0, 60, 61)
        F = model.evaluate(t, params)

        assert len(F) == 61
        assert F[0] == pytest.approx(100.0, rel=1e-10)  # Before lag
        assert F[-1] > 100.0  # Should rise after lag

    def test_initial_guess_to_evaluate(self):
        """Test round-trip: initial_guess -> evaluate."""
        model = DelayedExponential()

        # Create synthetic data
        t = np.linspace(0, 60, 61)
        true_params = ModelParameters()
        true_params.set("F_baseline", 100.0)
        true_params.set("F_max", 500.0)
        true_params.set("k_obs", 0.15)
        true_params.set("t_lag", 5.0)

        F_true = model.evaluate(t, true_params)

        # Get initial guess from data
        guess = model.initial_guess(t, F_true)

        # Initial guess should be reasonable
        assert guess.get("F_baseline") > 0
        assert guess.get("F_max") > 0
        assert guess.get("k_obs") > 0
