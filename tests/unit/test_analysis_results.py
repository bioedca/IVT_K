"""
Unit tests for analysis results layout and callbacks.

Phase 5.5-5.7: Posterior Summaries UI (F11.7-F11.13)
"""
import pytest
from unittest.mock import MagicMock, patch
import dash_mantine_components as dmc
import plotly.graph_objects as go


class TestAnalysisResultsLayout:
    """Tests for analysis results layout functions."""

    def test_create_analysis_results_layout_returns_component(self):
        """Test that create_analysis_results_layout returns a valid component."""
        from app.layouts.analysis_results import create_analysis_results_layout

        layout = create_analysis_results_layout()
        assert layout is not None

    def test_create_empty_results_message(self):
        """Test empty results message creation."""
        from app.layouts.analysis_results import create_empty_results_message

        result = create_empty_results_message()
        assert result is not None

    def test_create_posterior_table_empty_list(self):
        """Test posterior table with empty posteriors list."""
        from app.layouts.analysis_results import create_posterior_table

        result = create_posterior_table([], "log2_fc")
        assert result is not None

    def test_create_posterior_table_with_data(self):
        """Test posterior table with sample data."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [
            {
                "construct_name": "Test Construct",
                "mean": 1.5,
                "std": 0.2,
                "ci_lower": 1.1,
                "ci_upper": 1.9,
                "r_hat": 1.001,
                "ess_bulk": 1500,
                "ess_tail": 1200,
                "prob_positive": 0.99,
                "prob_meaningful": 0.85,
            }
        ]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_create_posterior_table_multiple_constructs(self):
        """Test posterior table with multiple constructs."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [
            {
                "construct_name": f"Construct {i}",
                "mean": 1.0 + i * 0.1,
                "std": 0.2,
                "ci_lower": 0.8 + i * 0.1,
                "ci_upper": 1.2 + i * 0.1,
                "r_hat": 1.001,
                "ess_bulk": 1500,
                "ess_tail": 1200,
                "prob_positive": 0.95,
                "prob_meaningful": 0.80,
            }
            for i in range(5)
        ]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_create_probability_display(self):
        """Test probability display creation."""
        from app.layouts.analysis_results import create_probability_display

        result = create_probability_display(
            construct_name="Test Construct",
            prob_direction=0.95,
            prob_meaningful=0.80,
            threshold=1.5,
        )
        assert result is not None

    def test_create_probability_display_low_probs(self):
        """Test probability display with low probabilities."""
        from app.layouts.analysis_results import create_probability_display

        result = create_probability_display(
            construct_name="Low Probability Construct",
            prob_direction=0.55,
            prob_meaningful=0.30,
            threshold=1.5,
        )
        assert result is not None

    def test_create_probability_display_high_probs(self):
        """Test probability display with high probabilities."""
        from app.layouts.analysis_results import create_probability_display

        result = create_probability_display(
            construct_name="High Probability Construct",
            prob_direction=0.999,
            prob_meaningful=0.95,
            threshold=1.5,
        )
        assert result is not None

    def test_create_variance_pie_chart_returns_figure(self):
        """Test that variance pie chart returns a plotly figure."""
        from app.layouts.analysis_results import create_variance_pie_chart

        result = create_variance_pie_chart(
            var_session=0.3,
            var_plate=0.2,
            var_residual=0.5,
        )
        assert isinstance(result, go.Figure)

    def test_create_variance_pie_chart_zero_values(self):
        """Test variance pie chart with zero values."""
        from app.layouts.analysis_results import create_variance_pie_chart

        result = create_variance_pie_chart(
            var_session=0.0,
            var_plate=0.0,
            var_residual=1.0,
        )
        assert isinstance(result, go.Figure)

    def test_create_variance_pie_chart_equal_values(self):
        """Test variance pie chart with equal variance components."""
        from app.layouts.analysis_results import create_variance_pie_chart

        result = create_variance_pie_chart(
            var_session=0.33,
            var_plate=0.33,
            var_residual=0.34,
        )
        assert isinstance(result, go.Figure)

    def test_create_diagnostics_panel_good_diagnostics(self):
        """Test diagnostics panel with good MCMC diagnostics."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=4,
            n_draws=2000,
            divergent_count=0,
            duration_seconds=120,
            warnings=[],
        )
        assert result is not None

    def test_create_diagnostics_panel_with_divergences(self):
        """Test diagnostics panel with divergent transitions."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=4,
            n_draws=2000,
            divergent_count=15,
            duration_seconds=180,
            warnings=["Some divergent transitions detected"],
        )
        assert result is not None

    def test_create_diagnostics_panel_with_warnings(self):
        """Test diagnostics panel with multiple warnings."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=4,
            n_draws=1000,
            divergent_count=5,
            duration_seconds=60,
            warnings=[
                "Low ESS for some parameters",
                "R-hat > 1.01 for some parameters",
            ],
        )
        assert result is not None

    def test_create_correlations_panel_empty(self):
        """Test correlations panel with empty data."""
        from app.layouts.analysis_results import create_correlations_panel

        result = create_correlations_panel({})
        assert result is not None

    def test_create_correlations_panel_with_data(self):
        """Test correlations panel with correlation data."""
        from app.layouts.analysis_results import create_correlations_panel

        correlations = {
            "log2fc_vs_kobs": 0.85,
            "log2fc_vs_amax": 0.72,
            "kobs_vs_amax": 0.65,
        }

        result = create_correlations_panel(correlations)
        assert result is not None


class TestAnalysisCallbacksHelpers:
    """Tests for analysis callback helper functions."""

    def test_dmc_text_dimmed_helper(self):
        """Test the dmc_text_dimmed helper function."""
        from app.callbacks.analysis_callbacks import dmc_text_dimmed

        result = dmc_text_dimmed("Test message")
        assert result is not None


class TestPosteriorTableFormatting:
    """Tests for posterior table data formatting."""

    def test_r_hat_formatting_good(self):
        """Test R-hat value formatting for good convergence."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [{
            "construct_name": "Good Convergence",
            "mean": 1.0,
            "std": 0.1,
            "ci_lower": 0.8,
            "ci_upper": 1.2,
            "r_hat": 1.001,  # Good R-hat
            "ess_bulk": 2000,
            "ess_tail": 1800,
            "prob_positive": 0.99,
            "prob_meaningful": 0.90,
        }]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_r_hat_formatting_marginal(self):
        """Test R-hat value formatting for marginal convergence."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [{
            "construct_name": "Marginal Convergence",
            "mean": 1.0,
            "std": 0.2,
            "ci_lower": 0.6,
            "ci_upper": 1.4,
            "r_hat": 1.008,  # Marginal R-hat
            "ess_bulk": 800,
            "ess_tail": 600,
            "prob_positive": 0.95,
            "prob_meaningful": 0.75,
        }]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_r_hat_formatting_bad(self):
        """Test R-hat value formatting for poor convergence."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [{
            "construct_name": "Poor Convergence",
            "mean": 1.0,
            "std": 0.5,
            "ci_lower": 0.0,
            "ci_upper": 2.0,
            "r_hat": 1.05,  # Bad R-hat
            "ess_bulk": 200,
            "ess_tail": 150,
            "prob_positive": 0.80,
            "prob_meaningful": 0.50,
        }]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_ess_formatting_good(self):
        """Test ESS value formatting for good effective sample size."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [{
            "construct_name": "Good ESS",
            "mean": 1.0,
            "std": 0.1,
            "ci_lower": 0.8,
            "ci_upper": 1.2,
            "r_hat": 1.001,
            "ess_bulk": 2500,  # Good ESS
            "ess_tail": 2000,
            "prob_positive": 0.99,
            "prob_meaningful": 0.90,
        }]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None

    def test_ess_formatting_low(self):
        """Test ESS value formatting for low effective sample size."""
        from app.layouts.analysis_results import create_posterior_table

        posteriors = [{
            "construct_name": "Low ESS",
            "mean": 1.0,
            "std": 0.3,
            "ci_lower": 0.4,
            "ci_upper": 1.6,
            "r_hat": 1.015,
            "ess_bulk": 150,  # Low ESS
            "ess_tail": 100,
            "prob_positive": 0.90,
            "prob_meaningful": 0.60,
        }]

        result = create_posterior_table(posteriors, "log2_fc")
        assert result is not None


class TestProbabilityCalculations:
    """Tests for probability display calculations."""

    def test_probability_direction_positive(self):
        """Test probability of direction for positive effect."""
        from app.layouts.analysis_results import create_probability_display

        # High probability positive
        result = create_probability_display(
            construct_name="Positive Effect",
            prob_direction=0.98,
            prob_meaningful=0.85,
            threshold=1.5,
        )
        assert result is not None

    def test_probability_direction_negative(self):
        """Test probability of direction for negative effect."""
        from app.layouts.analysis_results import create_probability_display

        # Low probability positive means high probability negative
        result = create_probability_display(
            construct_name="Negative Effect",
            prob_direction=0.05,  # 95% probability negative
            prob_meaningful=0.80,
            threshold=1.5,
        )
        assert result is not None

    def test_probability_direction_uncertain(self):
        """Test probability of direction for uncertain effect."""
        from app.layouts.analysis_results import create_probability_display

        # Probability near 0.5 means uncertain direction
        result = create_probability_display(
            construct_name="Uncertain Effect",
            prob_direction=0.52,
            prob_meaningful=0.20,
            threshold=1.5,
        )
        assert result is not None

    def test_probability_meaningful_high(self):
        """Test high probability of meaningful effect."""
        from app.layouts.analysis_results import create_probability_display

        result = create_probability_display(
            construct_name="Meaningful Effect",
            prob_direction=0.95,
            prob_meaningful=0.92,  # High probability meaningful
            threshold=1.5,
        )
        assert result is not None

    def test_probability_meaningful_low(self):
        """Test low probability of meaningful effect."""
        from app.layouts.analysis_results import create_probability_display

        result = create_probability_display(
            construct_name="Small Effect",
            prob_direction=0.90,
            prob_meaningful=0.15,  # Low probability meaningful
            threshold=1.5,
        )
        assert result is not None


class TestVarianceDecomposition:
    """Tests for variance decomposition visualization."""

    def test_variance_total_normalization(self):
        """Test that variance components are properly handled."""
        from app.layouts.analysis_results import create_variance_pie_chart

        # Components that sum to 1
        result = create_variance_pie_chart(
            var_session=0.25,
            var_plate=0.35,
            var_residual=0.40,
        )
        assert isinstance(result, go.Figure)

    def test_variance_large_session_effect(self):
        """Test variance with large session effect."""
        from app.layouts.analysis_results import create_variance_pie_chart

        result = create_variance_pie_chart(
            var_session=0.6,
            var_plate=0.1,
            var_residual=0.3,
        )
        assert isinstance(result, go.Figure)

    def test_variance_large_residual(self):
        """Test variance with large residual component."""
        from app.layouts.analysis_results import create_variance_pie_chart

        result = create_variance_pie_chart(
            var_session=0.05,
            var_plate=0.05,
            var_residual=0.90,
        )
        assert isinstance(result, go.Figure)


class TestMCMCDiagnostics:
    """Tests for MCMC diagnostics display."""

    def test_diagnostics_short_run(self):
        """Test diagnostics for short MCMC run."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=2,
            n_draws=500,
            divergent_count=0,
            duration_seconds=30,
            warnings=[],
        )
        assert result is not None

    def test_diagnostics_long_run(self):
        """Test diagnostics for long MCMC run."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=8,
            n_draws=10000,
            divergent_count=2,
            duration_seconds=3600,
            warnings=[],
        )
        assert result is not None

    def test_diagnostics_problematic_run(self):
        """Test diagnostics for problematic MCMC run."""
        from app.layouts.analysis_results import create_diagnostics_panel

        result = create_diagnostics_panel(
            n_chains=4,
            n_draws=2000,
            divergent_count=50,
            duration_seconds=300,
            warnings=[
                "High number of divergent transitions",
                "Some chains did not converge",
                "Low effective sample size for key parameters",
            ],
        )
        assert result is not None


class TestCorrelationsPanel:
    """Tests for correlations panel."""

    def test_correlations_high_positive(self):
        """Test correlations panel with high positive correlations."""
        from app.layouts.analysis_results import create_correlations_panel

        correlations = {
            "param1_param2": 0.95,
            "param1_param3": 0.88,
        }

        result = create_correlations_panel(correlations)
        assert result is not None

    def test_correlations_negative(self):
        """Test correlations panel with negative correlations."""
        from app.layouts.analysis_results import create_correlations_panel

        correlations = {
            "param1_param2": -0.75,
            "param2_param3": -0.60,
        }

        result = create_correlations_panel(correlations)
        assert result is not None

    def test_correlations_mixed(self):
        """Test correlations panel with mixed correlations."""
        from app.layouts.analysis_results import create_correlations_panel

        correlations = {
            "positive_pair": 0.85,
            "negative_pair": -0.70,
            "weak_pair": 0.15,
        }

        result = create_correlations_panel(correlations)
        assert result is not None
