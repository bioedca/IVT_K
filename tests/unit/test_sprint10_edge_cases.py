"""
Sprint 10: Edge Cases & Polish Tests

Tests for robust handling of statistical edge cases.

PRD Reference:
- T5.16: MCMC divergent transitions handled
- T5.17: Zero random effect variance
- T5.18: Model degeneracy detected
- T5.19: Extreme posterior shapes
- T5.20: Insufficient data for hierarchical model
- T4.20-T4.24: Convergence failure handling
- T7.9-T7.11: Extreme sample size recommendations
"""
import pytest
import numpy as np
import pandas as pd

from app.analysis.edge_cases import (
    # MCMC diagnostics
    MCMCDiagnostics,
    assess_mcmc_diagnostics,
    # Data validation
    DataValidationResult,
    validate_hierarchical_data,
    # Posterior quality
    PosteriorQualityAssessment,
    assess_posterior_quality,
    # Convergence failures
    ConvergenceFailureInfo,
    ConvergenceFailureType,
    diagnose_convergence_failure,
    # Sample size recommendations
    SampleSizeRecommendation,
    compute_sample_size_recommendation,
    # Diagnostic messages
    DiagnosticMessage,
    DiagnosticSeverity,
)


class TestMCMCDiagnostics:
    """Tests for MCMC diagnostic assessment (T5.16)."""

    def test_mcmc_diagnostics_basic_properties(self):
        """Test basic MCMCDiagnostics properties."""
        diag = MCMCDiagnostics(n_chains=4, n_draws=2000, n_tune=1000)

        assert diag.total_samples == 8000
        assert not diag.has_divergences
        assert not diag.divergence_is_severe
        assert diag.convergence_ok  # r_hat_max defaults to 1.0

    def test_divergence_detection(self):
        """T5.16: Divergent transitions are detected."""
        diag = MCMCDiagnostics(
            n_chains=4,
            n_draws=2000,
            n_tune=1000,
            divergent_count=100,
            divergent_rate=0.0125  # 1.25%
        )

        assert diag.has_divergences
        assert diag.divergence_is_severe  # >1%

    def test_divergence_levels(self):
        """T5.16: Different divergence levels classified correctly."""
        # 10% divergent
        diag_10 = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            divergent_count=800, divergent_rate=0.10
        )
        assert diag_10.divergence_is_severe

        # 50% divergent
        diag_50 = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            divergent_count=4000, divergent_rate=0.50
        )
        assert diag_50.divergence_is_severe
        assert not diag_50.is_reliable

    def test_convergence_r_hat(self):
        """Test R-hat convergence check."""
        # Good convergence
        diag_good = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            r_hat_max=1.005
        )
        assert diag_good.convergence_ok

        # Poor convergence
        diag_poor = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            r_hat_max=1.05
        )
        assert not diag_poor.convergence_ok

    def test_ess_adequacy(self):
        """Test ESS adequacy check."""
        # Adequate ESS
        diag_ok = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            ess_bulk_min=500, ess_tail_min=450
        )
        assert diag_ok.ess_ok

        # Inadequate ESS
        diag_low = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            ess_bulk_min=100, ess_tail_min=50
        )
        assert not diag_low.ess_ok

    def test_overall_reliability(self):
        """Test overall reliability assessment."""
        # Reliable
        diag_reliable = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            divergent_rate=0.005,  # <1%
            r_hat_max=1.005,
            ess_bulk_min=500,
            ess_tail_min=450
        )
        assert diag_reliable.is_reliable

        # Unreliable due to divergences
        diag_unreliable = MCMCDiagnostics(
            n_chains=4, n_draws=2000, n_tune=1000,
            divergent_rate=0.15,  # >1%
            r_hat_max=1.005,
            ess_bulk_min=500,
            ess_tail_min=450
        )
        assert not diag_unreliable.is_reliable


class TestDataValidation:
    """Tests for hierarchical data validation (T5.17, T5.18, T5.20)."""

    def test_empty_data(self):
        """T5.20: Empty data rejected."""
        result = validate_hierarchical_data(pd.DataFrame())

        assert not result.is_valid
        assert not result.can_fit_hierarchical
        assert any(w.code == "DATA_EMPTY" for w in result.warnings)

    def test_insufficient_observations(self):
        """T5.20: Insufficient observations detected."""
        df = pd.DataFrame({
            'construct_id': [1, 1, 1],
            'session_id': [1, 1, 1],
            'plate_id': [1, 1, 1],
            'log_fc_fmax': [0.1, 0.2, 0.15]
        })

        result = validate_hierarchical_data(df, min_observations=4)

        assert not result.is_valid
        assert any(w.code == "DATA_INSUFFICIENT_OBS" for w in result.warnings)

    def test_single_plate_warning(self):
        """T5.20: Single plate warns about hierarchical model."""
        df = pd.DataFrame({
            'construct_id': [1, 1, 2, 2, 3, 3],
            'session_id': [1, 1, 1, 1, 1, 1],
            'plate_id': [1, 1, 1, 1, 1, 1],  # Single plate
            'log_fc_fmax': [0.1, 0.2, 0.15, 0.25, 0.3, 0.35]
        })

        result = validate_hierarchical_data(df)

        assert result.is_valid  # Data is valid
        assert not result.can_fit_hierarchical  # But can't fit hierarchical
        assert any(w.code == "DATA_SINGLE_PLATE" for w in result.warnings)

    def test_zero_variance_detection(self):
        """T5.17: Zero variance constructs detected."""
        df = pd.DataFrame({
            'construct_id': [1, 1, 1, 2, 2, 2],
            'session_id': [1, 1, 1, 1, 1, 1],
            'plate_id': [1, 2, 3, 1, 2, 3],
            'log_fc_fmax': [0.5, 0.5, 0.5, 0.1, 0.2, 0.3]  # Construct 1 has zero variance
        })

        result = validate_hierarchical_data(df)

        assert 1 in result.zero_variance_constructs
        assert 2 not in result.zero_variance_constructs
        assert any(w.code == "DATA_ZERO_VARIANCE" for w in result.warnings)

    def test_single_replicate_warning(self):
        """T5.20: Single replicate constructs warned."""
        df = pd.DataFrame({
            'construct_id': [1, 2, 2, 3, 3, 3],  # Construct 1 has only 1 replicate
            'session_id': [1, 1, 1, 1, 1, 1],
            'plate_id': [1, 1, 2, 1, 2, 3],
            'log_fc_fmax': [0.1, 0.2, 0.25, 0.3, 0.35, 0.4]
        })

        result = validate_hierarchical_data(df)

        assert any(w.code == "DATA_SINGLE_REPLICATE" for w in result.warnings)

    def test_valid_data(self):
        """Test valid hierarchical data passes validation."""
        df = pd.DataFrame({
            'construct_id': [1, 1, 1, 1, 2, 2, 2, 2],
            'session_id': [1, 1, 2, 2, 1, 1, 2, 2],
            'plate_id': [1, 2, 3, 4, 1, 2, 3, 4],
            'log_fc_fmax': [0.1, 0.15, 0.2, 0.18, 0.3, 0.35, 0.32, 0.28]
        })

        result = validate_hierarchical_data(df)

        assert result.is_valid
        assert result.can_fit_hierarchical
        assert result.n_observations == 8
        assert result.n_constructs == 2
        assert result.n_plates == 4


class TestPosteriorQuality:
    """Tests for posterior quality assessment (T5.19)."""

    def test_normal_posterior(self):
        """Normal posterior should pass quality checks."""
        np.random.seed(42)
        samples = np.random.normal(0, 1, 1000)

        result = assess_posterior_quality(samples, "test_param")

        assert result.is_acceptable
        assert not result.is_bimodal
        assert not result.has_heavy_tails
        assert not result.is_at_boundary

    def test_bimodal_detection(self):
        """T5.19: Bimodal posterior detected."""
        np.random.seed(42)
        # Create bimodal distribution
        samples = np.concatenate([
            np.random.normal(-2, 0.5, 500),
            np.random.normal(2, 0.5, 500)
        ])

        result = assess_posterior_quality(samples, "test_param")

        # Bimodality coefficient should indicate bimodality
        assert result.bimodality_coefficient > 0.5

    def test_heavy_tails_detection(self):
        """T5.19: Heavy-tailed posterior detected."""
        np.random.seed(42)
        # Student's t with df=2 has heavy tails
        samples = np.random.standard_t(df=2, size=1000)

        result = assess_posterior_quality(samples, "test_param")

        assert result.kurtosis_excess > 3  # Heavy tails

    def test_boundary_mode_detection(self):
        """T5.19: Boundary modes detected."""
        np.random.seed(42)
        # Create samples with many values at exactly the boundary
        samples = np.concatenate([
            np.zeros(100),  # Values at boundary
            np.random.uniform(0, 1, 900)
        ])

        result = assess_posterior_quality(
            samples,
            "test_param",
            lower_bound=0.0
        )

        assert result.is_at_boundary
        assert result.boundary_fraction >= 0.05

    def test_skewed_distribution(self):
        """T5.19: Highly skewed distribution flagged."""
        np.random.seed(42)
        # Log-normal with high sigma is very skewed
        samples = np.random.lognormal(0, 2, 1000)

        result = assess_posterior_quality(samples, "test_param")

        assert result.is_highly_skewed
        assert abs(result.skewness) > 2

    def test_insufficient_samples(self):
        """Too few samples should fail quality check."""
        samples = np.array([0.1, 0.2, 0.3])

        result = assess_posterior_quality(samples, "test_param")

        assert not result.is_acceptable
        assert any(w.code == "POSTERIOR_INSUFFICIENT_SAMPLES" for w in result.warnings)


class TestConvergenceFailure:
    """Tests for convergence failure diagnosis (T4.20-T4.24)."""

    def test_insufficient_points(self):
        """T4.24: Insufficient data points detected."""
        t = np.array([0, 1, 2])  # Only 3 points
        F = np.array([100, 150, 200])

        result = diagnose_convergence_failure(data_t=t, data_F=F)

        assert result.failure_type == ConvergenceFailureType.INSUFFICIENT_POINTS.value
        assert not result.recoverable
        assert result.severity == DiagnosticSeverity.ERROR

    def test_flat_data(self):
        """T4.23: Flat data detected."""
        t = np.linspace(0, 60, 61)
        F = np.full(61, 100.0)  # Completely flat

        result = diagnose_convergence_failure(data_t=t, data_F=F)

        assert result.failure_type == ConvergenceFailureType.FLAT_DATA.value
        assert not result.recoverable

    def test_saturated_data(self):
        """T4.23: Saturated signal detected."""
        t = np.linspace(0, 60, 61)
        # Data that rises then saturates
        F = np.concatenate([
            np.linspace(1000, 65000, 20),  # Rising portion
            np.full(41, 65535.0)  # Saturated portion
        ])

        result = diagnose_convergence_failure(data_t=t, data_F=F)

        assert result.failure_type == ConvergenceFailureType.DATA_SATURATION.value
        assert result.recoverable

    def test_nan_parameters(self):
        """T4.20: NaN parameters detected."""
        params = np.array([100.0, np.nan, 0.1, 5.0])

        result = diagnose_convergence_failure(params=params)

        assert result.failure_type == ConvergenceFailureType.NAN_PARAMETERS.value
        assert result.severity == DiagnosticSeverity.ERROR

    def test_gradient_explosion(self):
        """T4.20: Gradient explosion detected."""
        params = np.array([100.0, np.inf, 0.1, 5.0])

        result = diagnose_convergence_failure(params=params)

        assert result.failure_type == ConvergenceFailureType.GRADIENT_EXPLOSION.value

    def test_parameter_at_bound(self):
        """T4.21: Parameter at boundary detected."""
        params = np.array([100.0, 500.0, 0.001, 5.0])  # k_obs at lower bound
        bounds = (
            np.array([0.0, 0.0, 0.001, 0.0]),  # Lower bounds
            np.array([np.inf, np.inf, 10.0, 30.0])  # Upper bounds
        )

        result = diagnose_convergence_failure(params=params, bounds=bounds)

        assert result.failure_type == ConvergenceFailureType.PARAMETER_AT_BOUND.value
        assert result.severity == DiagnosticSeverity.WARNING

    def test_ill_conditioned_covariance(self):
        """T4.22: Ill-conditioned covariance detected."""
        # Create ill-conditioned matrix
        cov = np.array([
            [1e10, 1e9, 0, 0],
            [1e9, 1e8, 0, 0],
            [0, 0, 1e-10, 0],
            [0, 0, 0, 1e-12]
        ])

        result = diagnose_convergence_failure(covariance=cov)

        assert result.failure_type == ConvergenceFailureType.ILL_CONDITIONED.value

    def test_high_parameter_correlation(self):
        """T4.22: High parameter correlation detected."""
        # Create matrix with high correlation
        cov = np.array([
            [1.0, 0.999, 0, 0],
            [0.999, 1.0, 0, 0],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1.0]
        ])

        result = diagnose_convergence_failure(covariance=cov)

        assert result.failure_type == ConvergenceFailureType.PARAMETER_CORRELATION.value

    def test_max_iterations_exceeded(self):
        """T4.20: Max iterations exceeded."""
        result = diagnose_convergence_failure(
            n_iterations=5000,
            max_iterations=5000
        )

        assert result.failure_type == ConvergenceFailureType.MAX_ITERATIONS.value
        assert result.recoverable


class TestSampleSizeRecommendation:
    """Tests for sample size recommendation edge cases (T7.9-T7.11)."""

    def test_normal_recommendation(self):
        """Normal sample size recommendation."""
        result = compute_sample_size_recommendation(
            target_precision=0.3,
            current_variance=0.25,
            current_n=10
        )

        assert result.is_achievable
        assert result.recommended_n > 0
        assert len(result.warnings) == 0

    def test_very_tight_precision(self):
        """T7.11: Very tight precision target."""
        result = compute_sample_size_recommendation(
            target_precision=0.005,  # Very tight
            current_variance=0.25,
            current_n=10
        )

        assert any(w.code == "PRECISION_VERY_TIGHT" for w in result.warnings)

    def test_very_loose_precision(self):
        """T7.11: Very loose precision target."""
        result = compute_sample_size_recommendation(
            target_precision=15.0,  # Very loose
            current_variance=0.25,
            current_n=10
        )

        assert any(w.code == "PRECISION_VERY_LOOSE" for w in result.warnings)
        assert result.recommended_n <= 4

    def test_invalid_precision(self):
        """T7.11: Invalid (negative) precision target."""
        result = compute_sample_size_recommendation(
            target_precision=-0.5,
            current_variance=0.25,
            current_n=10
        )

        assert not result.is_achievable
        assert any(w.code == "PRECISION_INVALID" for w in result.warnings)

    def test_zero_variance(self):
        """T7.10: Zero variance construct."""
        result = compute_sample_size_recommendation(
            target_precision=0.3,
            current_variance=0.0,
            current_n=10
        )

        assert not result.is_achievable
        assert any(w.code == "VARIANCE_ZERO" for w in result.warnings)

    def test_near_zero_variance(self):
        """T7.10: Near-zero variance construct."""
        result = compute_sample_size_recommendation(
            target_precision=0.3,
            current_variance=1e-15,
            current_n=10
        )

        assert any(w.code == "VARIANCE_NEAR_ZERO" for w in result.warnings)

    def test_impractically_large_sample(self):
        """T7.9: Impractically large sample size required."""
        result = compute_sample_size_recommendation(
            target_precision=0.001,  # Very tight
            current_variance=100.0,  # High variance
            current_n=10,
            max_practical_n=500
        )

        assert not result.is_achievable
        assert result.recommended_n == 500  # Capped at practical max

    def test_small_sample_below_minimum(self):
        """T7.9: Sample below minimum."""
        result = compute_sample_size_recommendation(
            target_precision=10.0,  # Very loose
            current_variance=0.01,  # Low variance
            current_n=10,
            min_n=4
        )

        assert result.recommended_n >= 4


class TestDiagnosticMessage:
    """Tests for diagnostic message handling."""

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = DiagnosticMessage(
            code="TEST_CODE",
            message="Test message",
            severity=DiagnosticSeverity.WARNING,
            details={"key": "value"}
        )

        d = msg.to_dict()

        assert d["code"] == "TEST_CODE"
        assert d["message"] == "Test message"
        assert d["severity"] == "warning"
        assert d["details"]["key"] == "value"

    def test_severity_levels(self):
        """Test all severity levels."""
        assert DiagnosticSeverity.INFO.value == "info"
        assert DiagnosticSeverity.WARNING.value == "warning"
        assert DiagnosticSeverity.ERROR.value == "error"
        assert DiagnosticSeverity.CRITICAL.value == "critical"
