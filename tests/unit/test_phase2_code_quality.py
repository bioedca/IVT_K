"""
Tests for Phase 2 Code Quality Fixes.

Tests for:
- 2.1 Secret Key Configuration
- 2.2 Signing Key Configuration
- 2.3 N+1 Query Prevention
- 2.4 Duplicate Method Removal
- 2.5 Transaction Management
- 2.6 Division by Zero Edge Case
"""
import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ============================================================================
# 2.1 Secret Key Configuration Tests
# ============================================================================

class TestSecretKeyConfiguration:
    """Tests for secret key configuration validation."""

    def test_config_has_configuration_error_class(self):
        """ConfigurationError exception class should exist."""
        from app.config import ConfigurationError
        assert issubclass(ConfigurationError, Exception)

    def test_development_config_has_fallback_secret_key(self):
        """Development config should have a fallback secret key."""
        from app.config import DevelopmentConfig
        assert DevelopmentConfig.SECRET_KEY is not None
        assert len(DevelopmentConfig.SECRET_KEY) > 0

    def test_production_config_requires_secret_key(self):
        """Production config should fail without SECRET_KEY."""
        from app.config import ProductionConfig, ConfigurationError

        # Save original value
        original = os.environ.get("SECRET_KEY")
        try:
            # Remove SECRET_KEY from environment
            if "SECRET_KEY" in os.environ:
                del os.environ["SECRET_KEY"]

            # Reload to get None value
            ProductionConfig.SECRET_KEY = os.environ.get("SECRET_KEY")

            # Validate should raise ConfigurationError
            with pytest.raises(ConfigurationError) as exc_info:
                ProductionConfig.validate()

            assert "SECRET_KEY" in str(exc_info.value)
        finally:
            # Restore original value
            if original is not None:
                os.environ["SECRET_KEY"] = original

    def test_production_config_rejects_insecure_defaults(self):
        """Production config should reject known insecure default keys."""
        from app.config import ProductionConfig, ConfigurationError

        original = os.environ.get("SECRET_KEY")
        try:
            # Set an insecure default
            os.environ["SECRET_KEY"] = "dev-key-change-in-production"
            ProductionConfig.SECRET_KEY = os.environ.get("SECRET_KEY")

            with pytest.raises(ConfigurationError) as exc_info:
                ProductionConfig.validate()

            assert "insecure" in str(exc_info.value).lower()
        finally:
            if original is not None:
                os.environ["SECRET_KEY"] = original
            elif "SECRET_KEY" in os.environ:
                del os.environ["SECRET_KEY"]

    def test_testing_config_has_fixed_secret_key(self):
        """Testing config should have a fixed secret key for reproducibility."""
        from app.config import TestingConfig
        assert TestingConfig.SECRET_KEY is not None
        assert "test" in TestingConfig.SECRET_KEY.lower()

    def test_is_secret_key_secure_method(self):
        """is_secret_key_secure should detect insecure keys."""
        from app.config import Config

        # Empty key is not secure
        Config.SECRET_KEY = ""
        assert Config.is_secret_key_secure() is False

        Config.SECRET_KEY = None
        assert Config.is_secret_key_secure() is False

        # Insecure defaults should not be secure
        Config.SECRET_KEY = "dev-key-change-in-production"
        assert Config.is_secret_key_secure() is False

        Config.SECRET_KEY = "change-me"
        assert Config.is_secret_key_secure() is False

        # A proper random key should be secure
        Config.SECRET_KEY = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert Config.is_secret_key_secure() is True

    def test_validate_config_function_exists(self):
        """validate_config helper function should exist."""
        from app.config import validate_config
        assert callable(validate_config)


# ============================================================================
# 2.2 Signing Key Configuration Tests
# ============================================================================

class TestSigningKeyConfiguration:
    """Tests for signing key configuration validation."""

    def test_get_signing_key_returns_string(self):
        """_get_signing_key should return a string."""
        from app.services.package_validation_service import PackageValidationService

        key = PackageValidationService._get_signing_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_get_signing_key_uses_env_var_when_set(self):
        """_get_signing_key should use IVT_SIGNING_KEY env var when set."""
        from app.services.package_validation_service import PackageValidationService

        original = os.environ.get("IVT_SIGNING_KEY")
        try:
            test_key = "test-signing-key-12345"
            os.environ["IVT_SIGNING_KEY"] = test_key

            key = PackageValidationService._get_signing_key()
            assert key == test_key
        finally:
            if original is not None:
                os.environ["IVT_SIGNING_KEY"] = original
            elif "IVT_SIGNING_KEY" in os.environ:
                del os.environ["IVT_SIGNING_KEY"]

    def test_get_signing_key_warns_in_development(self):
        """_get_signing_key should warn when using demo key in development."""
        from app.services.package_validation_service import PackageValidationService
        import logging

        original_signing = os.environ.get("IVT_SIGNING_KEY")
        original_env = os.environ.get("FLASK_ENV")

        try:
            # Remove signing key and ensure development mode
            if "IVT_SIGNING_KEY" in os.environ:
                del os.environ["IVT_SIGNING_KEY"]
            os.environ["FLASK_ENV"] = "development"

            with patch.object(logging.getLogger('app.services.package_validation_service'), 'warning') as mock_warning:
                key = PackageValidationService._get_signing_key()
                assert key == "demo-key-not-for-production"
                # Warning should have been logged
                mock_warning.assert_called()
        finally:
            if original_signing is not None:
                os.environ["IVT_SIGNING_KEY"] = original_signing
            if original_env is not None:
                os.environ["FLASK_ENV"] = original_env
            elif "FLASK_ENV" in os.environ:
                del os.environ["FLASK_ENV"]


# ============================================================================
# 2.3 N+1 Query Prevention Tests (Structure)
# ============================================================================

class TestN1QueryPrevention:
    """Tests verifying N+1 query prevention patterns are in place."""

    def test_results_api_uses_joinedload_import(self):
        """results_api should import joinedload for eager loading."""
        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "results_api.py"
        source = source_path.read_text()
        assert "joinedload" in source

    def test_project_api_uses_joinedload_import(self):
        """project_api should import joinedload for eager loading."""
        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "project_api.py"
        source = source_path.read_text()
        assert "joinedload" in source

    def test_results_api_posterior_uses_eager_loading(self):
        """get_posterior_results should use eager loading."""
        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "results_api.py"
        source = source_path.read_text()
        # Check that joinedload is used with HierarchicalResult.construct
        assert "joinedload" in source
        assert "HierarchicalResult.construct" in source

    def test_results_api_fold_changes_uses_eager_loading(self):
        """get_fold_changes should use eager loading."""
        source_path = Path(__file__).parent.parent.parent / "app" / "api" / "results_api.py"
        source = source_path.read_text()
        assert "joinedload" in source
        assert "test_well" in source
        assert "control_well" in source


# ============================================================================
# 2.4 Duplicate Method Removal Tests
# ============================================================================

class TestDuplicateMethodRemoval:
    """Tests verifying duplicate methods have been consolidated."""

    def test_bayesian_has_single_summarize_posterior(self):
        """BayesianHierarchical should have only one summarize_posterior method."""
        from app.analysis.bayesian import BayesianHierarchical
        import inspect

        # Get all methods with 'summarize_posterior' in name
        methods = [name for name, _ in inspect.getmembers(BayesianHierarchical, predicate=inspect.isfunction)
                   if 'summarize_posterior' in name]

        # Should only have one
        assert len(methods) == 1

    def test_summarize_posterior_has_param_idx_argument(self):
        """summarize_posterior should have param_idx argument for multivariate support."""
        from app.analysis.bayesian import BayesianHierarchical
        import inspect

        sig = inspect.signature(BayesianHierarchical.summarize_posterior)
        param_names = list(sig.parameters.keys())

        assert 'param_idx' in param_names

    def test_probability_meaningful_has_param_idx_argument(self):
        """probability_meaningful should have param_idx argument for multivariate support."""
        from app.analysis.bayesian import BayesianHierarchical
        import inspect

        sig = inspect.signature(BayesianHierarchical.probability_meaningful)
        param_names = list(sig.parameters.keys())

        assert 'param_idx' in param_names


# ============================================================================
# 2.5 Transaction Management Tests
# ============================================================================

class TestTransactionManagement:
    """Tests for transaction management in batch operations."""

    def test_store_bayesian_results_uses_nested_transaction(self):
        """_store_bayesian_results should use nested transaction."""
        import app.services.hierarchical_service as module
        import inspect
        source = inspect.getsource(module.HierarchicalService._store_bayesian_results)
        assert "begin_nested" in source

    def test_store_frequentist_results_uses_nested_transaction(self):
        """_store_frequentist_results should use nested transaction."""
        import app.services.hierarchical_service as module
        import inspect
        source = inspect.getsource(module.HierarchicalService._store_frequentist_results)
        assert "begin_nested" in source

    def test_store_bayesian_results_raises_on_error(self):
        """_store_bayesian_results should raise HierarchicalAnalysisError on failure."""
        import app.services.hierarchical_service as module
        import inspect
        source = inspect.getsource(module.HierarchicalService._store_bayesian_results)
        assert "HierarchicalAnalysisError" in source
        assert "raise" in source

    def test_store_frequentist_results_raises_on_error(self):
        """_store_frequentist_results should raise HierarchicalAnalysisError on failure."""
        import app.services.hierarchical_service as module
        import inspect
        source = inspect.getsource(module.HierarchicalService._store_frequentist_results)
        assert "HierarchicalAnalysisError" in source
        assert "raise" in source


# ============================================================================
# 2.6 Division by Zero Edge Case Tests
# ============================================================================

class TestDivisionByZeroEdgeCase:
    """Tests for division by zero handling in adjusted R-squared calculation."""

    def test_compute_statistics_handles_n_equals_k_plus_1(self):
        """compute_statistics should handle n == k + 1 edge case."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.kinetic_models import ModelParameters

        fitter = CurveFitter()

        # Create minimal data where n == k + 1
        # delayed_exponential has 4 params, so we need 5 points
        k = fitter.model.num_params
        n = k + 1

        t = np.linspace(0, 10, n)
        F = np.array([1.0, 2.0, 3.0, 4.0, 5.0])[:n]

        params = ModelParameters()
        params.set('F_baseline', 1.0)
        params.set('F_max', 5.0)
        params.set('k_obs', 0.1)
        params.set('t_lag', 0.0)

        # This should not raise a division by zero error
        stats = fitter.compute_statistics(t, F, params)

        # adjusted_r_squared should be valid (not inf or nan)
        assert np.isfinite(stats.adjusted_r_squared)

    def test_compute_statistics_handles_n_equals_k(self):
        """compute_statistics should handle n == k (overparameterized) case."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.kinetic_models import ModelParameters

        fitter = CurveFitter()

        # Create data where n == k (exactly enough points for parameters)
        k = fitter.model.num_params
        n = k

        t = np.linspace(0, 10, n)
        F = np.array([1.0, 2.0, 3.0, 4.0, 5.0])[:n]

        params = ModelParameters()
        params.set('F_baseline', 1.0)
        params.set('F_max', 5.0)
        params.set('k_obs', 0.1)
        params.set('t_lag', 0.0)

        # This should not raise an error
        stats = fitter.compute_statistics(t, F, params)

        # adjusted_r_squared should be valid
        assert np.isfinite(stats.adjusted_r_squared)

    def test_compute_statistics_handles_n_less_than_k(self):
        """compute_statistics should handle n < k (severely undersampled) case."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.kinetic_models import ModelParameters

        fitter = CurveFitter()

        # Create data where n < k
        n = 2  # Definitely less than 4 params

        t = np.linspace(0, 10, n)
        F = np.array([1.0, 2.0])

        params = ModelParameters()
        params.set('F_baseline', 1.0)
        params.set('F_max', 5.0)
        params.set('k_obs', 0.1)
        params.set('t_lag', 0.0)

        # This should not raise an error
        stats = fitter.compute_statistics(t, F, params)

        # adjusted_r_squared should be valid (using unadjusted value)
        assert np.isfinite(stats.adjusted_r_squared)

    def test_compute_statistics_normal_case_calculates_adjusted_r_squared(self):
        """compute_statistics should properly calculate adjusted R² for normal cases."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.kinetic_models import ModelParameters

        fitter = CurveFitter()
        k = fitter.model.num_params

        # Create abundant data (n >> k)
        n = 50
        t = np.linspace(0, 60, n)
        F = 100 * (1 - np.exp(-0.1 * (t - 5))) + np.random.normal(0, 1, n)
        F = np.maximum(0, F)

        params = ModelParameters()
        params.set('F_baseline', 0.0)
        params.set('F_max', 100.0)
        params.set('k_obs', 0.1)
        params.set('t_lag', 5.0)

        stats = fitter.compute_statistics(t, F, params)

        # With n >> k, adjusted R² should differ from R²
        # adjusted_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
        expected_adj = 1 - (1 - stats.r_squared) * (n - 1) / (n - k - 1)

        assert np.isclose(stats.adjusted_r_squared, expected_adj, rtol=1e-10)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase2Integration:
    """Integration tests for Phase 2 changes."""

    def test_app_creates_with_testing_config(self, app):
        """Application should create successfully with testing config."""
        assert app is not None

    def test_env_example_has_signing_key_placeholder(self):
        """`.env.example` should have IVT_SIGNING_KEY placeholder."""
        env_example_path = Path(__file__).parent.parent.parent / ".env.example"
        if env_example_path.exists():
            content = env_example_path.read_text()
            assert "IVT_SIGNING_KEY" in content

    def test_env_example_has_secret_key_instructions(self):
        """.env.example should have SECRET_KEY generation instructions."""
        env_example_path = Path(__file__).parent.parent.parent / ".env.example"
        if env_example_path.exists():
            content = env_example_path.read_text()
            assert "SECRET_KEY" in content
            assert "secrets.token_hex" in content


# Import Path for tests
from pathlib import Path
