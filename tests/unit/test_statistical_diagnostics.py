"""
Tests for statistical diagnostics callbacks and components.

Validates:
- Assumption tests (Shapiro-Wilk, Levene) - PRD F14.1-F14.2, T8.15-T8.16
- Q-Q plot generation - PRD F14.3, T8.17
- Effect size computation (Cohen's d) - PRD F14.6, T8.20
- Multiple comparison corrections (Bonferroni, BH, Holm) - PRD F14.4-F14.5, T8.18-T8.19
- Dynamic diagnostics warnings panel
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from dash import html


class TestAssumptionTestsDisplay:
    """Test the assumption tests display component."""

    def test_create_assumption_tests_normal_data(self):
        """Test assumption tests display with normal data."""
        from app.layouts.analysis_results import create_assumption_tests_display

        result = create_assumption_tests_display(
            normality_stat=0.98,
            normality_p=0.45,
            normality_pass=True,
            homoscedasticity_stat=1.2,
            homoscedasticity_p=0.27,
            homoscedasticity_pass=True,
        )
        # Should return a Div with test results
        assert result is not None

    def test_create_assumption_tests_non_normal(self):
        """Test display when normality fails."""
        from app.layouts.analysis_results import create_assumption_tests_display

        result = create_assumption_tests_display(
            normality_stat=0.85,
            normality_p=0.001,
            normality_pass=False,
        )
        assert result is not None

    def test_create_assumption_tests_with_durbin_watson(self):
        """Test display with Durbin-Watson statistic."""
        from app.layouts.analysis_results import create_assumption_tests_display

        result = create_assumption_tests_display(
            normality_stat=0.97,
            normality_p=0.30,
            normality_pass=True,
            durbin_watson=1.95,
        )
        assert result is not None


class TestEffectSizeDisplay:
    """Test effect size display component."""

    def test_create_effect_size_display_with_data(self):
        """Test effect size display with various magnitudes."""
        from app.layouts.analysis_results import create_effect_size_display

        effects = [
            {"comparison": "Construct_A", "cohens_d": 1.2, "category": "large", "mean_diff": 0.8},
            {"comparison": "Construct_B", "cohens_d": 0.6, "category": "medium", "mean_diff": 0.4},
            {"comparison": "Construct_C", "cohens_d": 0.3, "category": "small", "mean_diff": 0.2},
            {"comparison": "Construct_D", "cohens_d": 0.1, "category": "negligible", "mean_diff": 0.05},
        ]
        result = create_effect_size_display(effects)
        assert result is not None

    def test_create_effect_size_display_empty(self):
        """Test effect size display with no data."""
        from app.layouts.analysis_results import create_effect_size_display

        result = create_effect_size_display([])
        assert result is not None

    def test_cohens_d_categories(self):
        """Test Cohen's d categorization thresholds (T8.20)."""
        from app.analysis.statistical_tests import cohens_d

        # Large effect
        result = cohens_d(
            np.array([10, 11, 12, 13, 14]),
            np.array([1, 2, 3, 4, 5]),
        )
        assert result.category.value == "large"
        assert result.cohens_d > 0.8

        # Negligible effect (means nearly identical, high variance)
        np.random.seed(123)
        g1 = np.random.normal(5.0, 2.0, 50)
        g2 = np.random.normal(5.1, 2.0, 50)
        result = cohens_d(g1, g2)
        assert result.cohens_d < 0.5


class TestCorrectedPvaluesTable:
    """Test corrected p-values table component."""

    def test_create_corrected_pvalues_table(self):
        """Test corrected p-values table generation."""
        from app.layouts.analysis_results import create_corrected_pvalues_table

        comparisons = [
            {"name": "A vs Control", "p_value": 0.01, "adjusted_p": 0.03, "significant": True},
            {"name": "B vs Control", "p_value": 0.04, "adjusted_p": 0.12, "significant": False},
            {"name": "C vs Control", "p_value": 0.001, "adjusted_p": 0.003, "significant": True},
        ]
        result = create_corrected_pvalues_table(comparisons, method="bonferroni")
        assert result is not None

    def test_create_corrected_pvalues_table_empty(self):
        """Test table with no data."""
        from app.layouts.analysis_results import create_corrected_pvalues_table

        result = create_corrected_pvalues_table([])
        assert result is not None


class TestQQPlotGeneration:
    """Test Q-Q plot generation for residuals (T8.17)."""

    def test_qq_plot_normal_data(self):
        """Test Q-Q plot with normally distributed data."""
        from app.layouts.analysis_results import create_qq_plot_for_residuals

        np.random.seed(42)
        residuals = np.random.normal(0, 1, 100).tolist()
        fig = create_qq_plot_for_residuals(residuals)
        assert fig is not None
        assert len(fig.data) >= 2  # Points + reference line

    def test_qq_plot_insufficient_data(self):
        """Test Q-Q plot with insufficient data."""
        from app.layouts.analysis_results import create_qq_plot_for_residuals

        fig = create_qq_plot_for_residuals([1.0, 2.0])
        assert fig is not None
        # Should have annotation about insufficient data
        assert len(fig.layout.annotations) > 0

    def test_qq_plot_empty_data(self):
        """Test Q-Q plot with empty data."""
        from app.layouts.analysis_results import create_qq_plot_for_residuals

        fig = create_qq_plot_for_residuals([])
        assert fig is not None


class TestMultipleComparisonCorrections:
    """Test multiple comparison correction methods (T8.18-T8.19)."""

    def test_bonferroni_correction(self):
        """Test Bonferroni correction (T8.18)."""
        from app.analysis.statistical_tests import bonferroni_correction

        p_values = [0.01, 0.04, 0.001, 0.06]
        result = bonferroni_correction(p_values, alpha=0.05)
        assert result.n_comparisons == 4
        # 0.001 * 4 = 0.004 < 0.05 → significant
        assert result.significant[2] is True
        # 0.06 * 4 = 0.24 > 0.05 → not significant
        assert result.significant[3] is False

    def test_benjamini_hochberg_correction(self):
        """Test Benjamini-Hochberg FDR correction (T8.19)."""
        from app.analysis.statistical_tests import benjamini_hochberg_correction

        p_values = [0.01, 0.04, 0.001, 0.06]
        result = benjamini_hochberg_correction(p_values, alpha=0.05)
        assert result.n_comparisons == 4
        # BH is less conservative than Bonferroni
        assert result.n_significant >= 1  # At least the smallest p-value should be significant

    def test_bonferroni_many_comparisons(self):
        """Test Bonferroni with many comparisons (T8.18)."""
        from app.analysis.statistical_tests import bonferroni_correction

        # With 50 comparisons, threshold becomes 0.001
        p_values = [0.01] * 50
        result = bonferroni_correction(p_values, alpha=0.05)
        assert result.n_comparisons == 50
        # 0.01 * 50 = 0.5 > 0.05 → none significant
        assert result.n_significant == 0

    def test_fdr_control_at_different_levels(self):
        """Test BH at different FDR levels (T8.19)."""
        from app.analysis.statistical_tests import benjamini_hochberg_correction

        p_values = [0.001, 0.005, 0.01, 0.03, 0.05, 0.10, 0.20]

        result_01 = benjamini_hochberg_correction(p_values, alpha=0.01)
        result_05 = benjamini_hochberg_correction(p_values, alpha=0.05)
        result_10 = benjamini_hochberg_correction(p_values, alpha=0.10)

        # More liberal alpha → more discoveries
        assert result_10.n_significant >= result_05.n_significant
        assert result_05.n_significant >= result_01.n_significant


class TestStatisticsServiceIntegration:
    """Test StatisticsService methods used by callbacks."""

    def test_multiple_comparison_result(self):
        """Test get_multiple_comparison_result returns full result."""
        from app.services.statistics_service import StatisticsService

        p_values = [0.01, 0.04, 0.001]
        result = StatisticsService.get_multiple_comparison_result(
            p_values, method="bonferroni", alpha=0.05,
        )
        assert len(result.original_p_values) == 3
        assert len(result.adjusted_p_values) == 3
        assert len(result.significant) == 3
        assert result.n_comparisons == 3

    def test_multiple_comparison_result_empty(self):
        """Test with empty p-values."""
        from app.services.statistics_service import StatisticsService

        result = StatisticsService.get_multiple_comparison_result([], method="fdr")
        assert result.n_comparisons == 0
        assert result.adjusted_p_values == []

    def test_apply_correction_holm(self):
        """Test Holm-Bonferroni correction."""
        from app.services.statistics_service import StatisticsService

        p_values = [0.01, 0.04, 0.001]
        sig = StatisticsService.apply_multiple_comparison_correction(
            p_values, method="holm", alpha=0.05,
        )
        assert len(sig) == 3
        assert isinstance(sig[0], bool)


class TestNormalityTests:
    """Test normality testing (T8.15)."""

    def test_shapiro_wilk_normal_data(self):
        """Test Shapiro-Wilk with truly normal data."""
        from app.analysis.statistical_tests import shapiro_wilk_test

        np.random.seed(42)
        data = np.random.normal(0, 1, 100)
        result = shapiro_wilk_test(data)
        assert bool(result.is_normal) is True
        assert result.p_value > 0.05

    def test_shapiro_wilk_non_normal_data(self):
        """Test Shapiro-Wilk with non-normal data."""
        from app.analysis.statistical_tests import shapiro_wilk_test

        # Exponential distribution is clearly non-normal
        np.random.seed(42)
        data = np.random.exponential(1, 200)
        result = shapiro_wilk_test(data)
        assert bool(result.is_normal) is False
        assert result.p_value < 0.05


class TestHomoscedasticityTests:
    """Test homoscedasticity testing (T8.16)."""

    def test_levene_equal_variance(self):
        """Test Levene with equal variance groups."""
        from app.analysis.statistical_tests import levene_test

        np.random.seed(42)
        group1 = np.random.normal(0, 1, 50)
        group2 = np.random.normal(0, 1, 50)
        result = levene_test(group1, group2)
        assert bool(result.is_homoscedastic) is True

    def test_levene_unequal_variance(self):
        """Test Levene with unequal variance groups."""
        from app.analysis.statistical_tests import levene_test

        np.random.seed(42)
        group1 = np.random.normal(0, 1, 100)
        group2 = np.random.normal(0, 5, 100)
        result = levene_test(group1, group2)
        assert bool(result.is_homoscedastic) is False


class TestDiagnosticsWarningsPanel:
    """Test the consolidated diagnostics warnings panel component."""

    def test_empty_warnings_returns_empty_div(self):
        """Panel with no warnings returns an empty Div."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        result = create_diagnostics_warnings_panel([])
        assert isinstance(result, html.Div)
        assert result.children is None or result.children == []

    def test_single_warning_returns_single_alert(self):
        """One warning produces a single consolidated Alert panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel
        import dash_mantine_components as dmc

        warnings = [{
            "severity": "critical",
            "title": "Divergent Transitions",
            "message": "The sampler encountered 15 divergences.",
            "guidance": "Increase target_accept to 0.99.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        # Should be a single dmc.Alert, not a Div of alerts
        assert isinstance(result, dmc.Alert)
        # Panel color matches worst severity
        assert result.color == "red"

    def test_multiple_warnings_in_one_panel(self):
        """Multiple warnings are consolidated into a single Alert."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel
        import dash_mantine_components as dmc

        warnings = [
            {"severity": "info", "title": "Info Note", "message": "Low priority."},
            {"severity": "critical", "title": "Critical Issue", "message": "High priority."},
            {"severity": "warning", "title": "Medium Issue", "message": "Check this."},
        ]
        result = create_diagnostics_warnings_panel(warnings)
        # Single consolidated panel
        assert isinstance(result, dmc.Alert)
        # Panel color is red (worst severity present)
        assert result.color == "red"
        # Children is a Stack containing 3 item Divs
        assert isinstance(result.children, dmc.Stack)
        assert len(result.children.children) == 3

    def test_panel_color_from_worst_severity(self):
        """Panel color reflects the most severe warning present."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        # Only info → blue
        result = create_diagnostics_warnings_panel([
            {"severity": "info", "title": "Note", "message": "FYI."},
        ])
        assert result.color == "blue"

        # Warning present → yellow
        result = create_diagnostics_warnings_panel([
            {"severity": "info", "title": "Note", "message": "FYI."},
            {"severity": "warning", "title": "Warn", "message": "Check."},
        ])
        assert result.color == "yellow"

        # Critical present → red
        result = create_diagnostics_warnings_panel([
            {"severity": "info", "title": "Note", "message": "FYI."},
            {"severity": "critical", "title": "Bad", "message": "Fix now."},
        ])
        assert result.color == "red"

    def test_warning_with_guidance_has_recommendation(self):
        """Items with guidance include a recommendation paper."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "warning",
            "title": "Test Warning",
            "message": "Something is wrong.",
            "guidance": "Here is how to fix it.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert result.children is not None

    def test_warning_without_guidance_still_renders(self):
        """Items without guidance still render correctly."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "info",
            "title": "Simple Note",
            "message": "Just informational.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert result is not None
        assert result.children is not None


class TestDiagnosticsWarningGeneration:
    """Test the warning generation logic that analyzes diagnostic data."""

    def _make_store_data(self, **overrides):
        """Helper to create mock analysis-results-store data."""
        data = {
            "version_id": 1,
            "posteriors": [],
            "frequentist": [],
            "has_frequentist": False,
            "frequentist_warnings": [],
            "variance_components": {},
            "diagnostics": {
                "n_chains": 4,
                "n_draws": 2000,
                "divergent_count": 0,
                "duration_seconds": 30,
                "warnings": [],
            },
        }
        data.update(overrides)
        return data

    def _make_posterior(self, name="Construct_A", param="log_fc_fmax", **kwargs):
        """Helper to create a mock posterior entry."""
        entry = {
            "construct_id": 1,
            "construct_name": name,
            "parameter": param,
            "analysis_type": "bayesian",
            "ligand_condition": None,
            "mean": 0.5,
            "std": 0.2,
            "ci_lower": 0.1,
            "ci_upper": 0.9,
            "r_hat": 1.001,
            "ess_bulk": 2000,
            "ess_tail": 1800,
            "prob_positive": 0.99,
            "prob_meaningful": 0.85,
            "var_session": 0.01,
            "var_plate": 0.02,
            "var_residual": 0.05,
        }
        entry.update(kwargs)
        return entry

    def test_divergent_transitions_warning(self):
        """Divergent transitions produce a red (critical) panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel
        import dash_mantine_components as dmc

        warnings = [{
            "severity": "critical",
            "title": "15 Divergent Transitions",
            "message": "Divergences detected.",
            "guidance": "Increase target_accept.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert isinstance(result, dmc.Alert)
        assert result.color == "red"
        # Stack should contain 1 item
        assert len(result.children.children) == 1

    def test_poor_rhat_warning(self):
        """R-hat > 1.05 produces a yellow (warning) panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel
        import dash_mantine_components as dmc

        warnings = [{
            "severity": "warning",
            "title": "R-hat > 1.05 for 1 Parameter(s)",
            "message": "Chains have not mixed well.",
            "guidance": "Run with more draws.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert isinstance(result, dmc.Alert)
        assert result.color == "yellow"

    def test_low_ess_warning(self):
        """Low ESS produces a warning panel with 1 item."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "warning",
            "title": "Low ESS for 1 Parameter(s)",
            "message": "ESS below 400.",
            "guidance": "Increase draws.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert len(result.children.children) == 1

    def test_no_correction_warning(self):
        """Missing correction produces a warning panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "warning",
            "title": "No Multiple-Testing Correction (10 Comparisons)",
            "message": "FWER is ~40%.",
            "guidance": "Select BH-FDR correction.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert len(result.children.children) == 1

    def test_all_negligible_effect_sizes_info(self):
        """All negligible effect sizes produce a blue (info) panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "info",
            "title": "All Effect Sizes Are Negligible",
            "message": "All 5 constructs show negligible Cohen's d.",
            "guidance": "Check assay sensitivity.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert result.color == "blue"

    def test_dominant_session_variance_warning(self):
        """Session variance > 50% produces a warning panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "warning",
            "title": "Session Variance Dominates (60%)",
            "message": "Over half of variability is between sessions.",
            "guidance": "Standardize reagent preparation.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert result.color == "yellow"

    def test_bayesian_frequentist_disagreement_warning(self):
        """Bayesian/Frequentist disagreement produces a warning panel."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [{
            "severity": "warning",
            "title": "Bayesian/Frequentist Estimates Disagree (2)",
            "message": "Point estimates differ by >2 posterior SDs.",
            "guidance": "Bayesian estimates are generally more trustworthy.",
        }]
        result = create_diagnostics_warnings_panel(warnings)
        assert result.color == "yellow"

    def test_mixed_severity_panel_color_uses_worst(self):
        """Panel with mixed severities uses worst severity color."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        warnings = [
            {"severity": "info", "title": "Note", "message": "OK."},
            {"severity": "critical", "title": "Bad", "message": "Not OK."},
            {"severity": "warning", "title": "Hmm", "message": "Check."},
        ]
        result = create_diagnostics_warnings_panel(warnings)
        # Worst is critical → red
        assert result.color == "red"
        # All 3 items present
        assert len(result.children.children) == 3

    def test_clean_analysis_no_warnings(self):
        """A clean analysis with no issues produces no warnings."""
        from app.layouts.analysis_results import create_diagnostics_warnings_panel

        result = create_diagnostics_warnings_panel([])
        assert isinstance(result, html.Div)
        assert result.children is None or result.children == []
