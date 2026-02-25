"""
E2E tests for analysis workflow.

PRD Reference: Section 4.1 - E2E testing

Tests the complete analysis execution workflow:
- Run curve fitting with CurveFitter
- Execute hierarchical analysis (frequentist)
- Generate fold-change comparisons via PairedAnalysis
- Verify result structures
"""
import pytest
from pathlib import Path
import numpy as np
import pandas as pd


class TestCurveFittingWorkflow:
    """Test curve fitting workflow using CurveFitter class."""

    def test_fit_single_curve(self):
        """Test fitting a single kinetic curve with the delayed exponential model."""
        from app.analysis.curve_fitting import CurveFitter, FitResult
        from app.analysis.kinetic_models import DelayedExponential

        # Generate synthetic delayed-exponential kinetic data
        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        true_baseline = 100.0
        true_fmax = 1500.0
        true_kobs = 0.05
        true_tlag = 5.0

        fluorescence = np.where(
            time > true_tlag,
            true_baseline + true_fmax * (1 - np.exp(-true_kobs * (time - true_tlag))),
            true_baseline
        )
        fluorescence += np.random.normal(0, 20, len(time))

        # Fit curve
        fitter = CurveFitter(DelayedExponential())
        result = fitter.fit(time, fluorescence)

        # Verify result is a FitResult and converged
        assert isinstance(result, FitResult)
        assert result.converged
        assert result.is_valid
        assert result.model_name == "delayed_exponential"

        # Verify fitted parameters are close to true values
        fitted_fmax = result.get_param("F_max")
        fitted_kobs = result.get_param("k_obs")
        assert fitted_fmax is not None
        assert abs(fitted_fmax - true_fmax) < 300  # Tolerance for noise
        assert fitted_kobs is not None
        assert abs(fitted_kobs - true_kobs) < 0.02

        # Verify statistics
        assert result.statistics.r_squared > 0.95
        assert result.statistics.rmse < 100

    def test_fit_multiple_curves(self):
        """Test fitting multiple curves from different wells."""
        from app.analysis.curve_fitting import CurveFitter

        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        n_wells = 4

        results = []
        for i in range(n_wells):
            fmax = 1000 + i * 200
            kobs = 0.04 + i * 0.01
            tlag = 3.0

            fluorescence = np.where(
                time > tlag,
                100 + fmax * (1 - np.exp(-kobs * (time - tlag))),
                100.0
            )
            fluorescence += np.random.normal(0, 15, len(time))

            fitter = CurveFitter()
            result = fitter.fit(time, fluorescence)
            results.append(result)

        # All should converge with clean synthetic data
        converged_count = sum(1 for r in results if r.converged)
        assert converged_count >= n_wells - 1  # Allow one failure at most

    def test_fit_convenience_function(self):
        """Test the fit_delayed_exponential convenience function."""
        from app.analysis.curve_fitting import fit_delayed_exponential

        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        fluorescence = np.where(
            time > 5.0,
            100 + 1200 * (1 - np.exp(-0.06 * (time - 5.0))),
            100.0
        )
        fluorescence += np.random.normal(0, 15, len(time))

        result = fit_delayed_exponential(time, fluorescence)
        assert result.converged
        assert result.statistics.r_squared > 0.9

    def test_fit_returns_statistics(self):
        """Test that FitResult contains complete statistics."""
        from app.analysis.curve_fitting import CurveFitter, FitStatistics

        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        fluorescence = np.where(
            time > 3.0,
            80 + 1000 * (1 - np.exp(-0.05 * (time - 3.0))),
            80.0
        )
        fluorescence += np.random.normal(0, 10, len(time))

        fitter = CurveFitter()
        result = fitter.fit(time, fluorescence)

        assert result.converged
        stats = result.statistics
        assert isinstance(stats, FitStatistics)
        assert 0.0 <= stats.r_squared <= 1.0
        assert stats.rmse >= 0
        assert np.isfinite(stats.aic)
        assert np.isfinite(stats.bic)
        assert np.isfinite(stats.residual_mean)
        assert np.isfinite(stats.residual_std)

    def test_fit_failure_recovery(self):
        """Test that curve fitter handles bad data gracefully via recovery stages."""
        from app.analysis.curve_fitting import CurveFitter

        # Very noisy, nearly-flat data should still return a result
        np.random.seed(42)
        time = np.linspace(0, 120, 10)
        fluorescence = np.random.normal(500, 200, len(time))

        fitter = CurveFitter()
        result = fitter.fit(time, fluorescence)

        # Should always return a FitResult, even if not converged
        assert result is not None
        assert result.n_points == len(time)


class TestHierarchicalAnalysisWorkflow:
    """Test hierarchical analysis workflow."""

    def test_prepare_hierarchical_data(self):
        """Test preparing a DataFrame suitable for hierarchical analysis."""
        np.random.seed(42)

        data_rows = []
        n_sessions = 3
        n_plates = 2
        n_constructs = 4

        for session in range(n_sessions):
            session_effect = np.random.normal(0, 0.1)
            for plate in range(n_plates):
                plate_effect = np.random.normal(0, 0.05)
                for construct in range(n_constructs):
                    construct_effect = 0.3 * construct

                    log_fc = (
                        construct_effect
                        + session_effect
                        + plate_effect
                        + np.random.normal(0, 0.15)
                    )

                    data_rows.append({
                        'session_id': f'S{session}',
                        'plate_id': f'P{session}_{plate}',
                        'construct_id': f'C{construct}',
                        'log_fc_fmax': log_fc
                    })

        df = pd.DataFrame(data_rows)

        # Verify data structure matches FrequentistHierarchical expectations
        assert len(df) == n_sessions * n_plates * n_constructs
        required_cols = {'session_id', 'plate_id', 'construct_id', 'log_fc_fmax'}
        assert required_cols.issubset(set(df.columns))

    def test_frequentist_analysis(self):
        """Test running frequentist hierarchical analysis end-to-end."""
        try:
            from app.analysis.frequentist import (
                FrequentistHierarchical,
                FrequentistResult,
                check_statsmodels_available
            )
            if not check_statsmodels_available():
                pytest.skip("statsmodels not available")
        except ImportError:
            pytest.skip("Frequentist module not available")

        # Create test data with multiple sessions and plates for full Tier 3 model
        np.random.seed(42)
        rows = []
        for session in ['S1', 'S2']:
            for plate in ['P1', 'P2']:
                for construct in ['C1', 'C2']:
                    base = 0.3 if construct == 'C1' else 0.6
                    for rep in range(3):
                        rows.append({
                            'construct_id': construct,
                            'session_id': session,
                            'plate_id': f'{session}_{plate}',
                            'log_fc_fmax': np.random.normal(base, 0.15),
                        })

        df = pd.DataFrame(rows)
        model = FrequentistHierarchical()
        result = model.run_analysis(df)

        assert isinstance(result, FrequentistResult)
        assert result.estimates is not None
        assert len(result.estimates) > 0
        assert result.model_metadata is not None

    def test_frequentist_tier_selection(self):
        """Test that the frequentist model correctly selects adaptive tiers."""
        try:
            from app.analysis.frequentist import (
                FrequentistHierarchical,
                check_statsmodels_available,
            )
            from app.analysis.bayesian import ModelTier
            if not check_statsmodels_available():
                pytest.skip("statsmodels not available")
        except ImportError:
            pytest.skip("Required modules not available")

        model = FrequentistHierarchical()

        # Tier 1: single session, single plate
        tier1_data = {'n_sessions': 1, 'n_plates': 1, 'max_plates_per_session': 1}
        meta1 = model.select_model_tier(tier1_data)
        assert meta1.tier == ModelTier.TIER_1_RESIDUAL_ONLY

        # Tier 2a: multiple sessions, one plate each
        tier2a_data = {'n_sessions': 3, 'n_plates': 3, 'max_plates_per_session': 1}
        meta2a = model.select_model_tier(tier2a_data)
        assert meta2a.tier == ModelTier.TIER_2A_SESSION

        # Tier 3: multiple sessions and plates
        tier3_data = {'n_sessions': 3, 'n_plates': 6, 'max_plates_per_session': 2}
        meta3 = model.select_model_tier(tier3_data)
        assert meta3.tier == ModelTier.TIER_3_FULL


class TestComparisonWorkflow:
    """Test fold-change comparison analysis workflow using PairedAnalysis."""

    def test_primary_fold_change(self):
        """Test computing a primary fold change (test vs control)."""
        from app.analysis.comparison import PairedAnalysis, FoldChangeResult

        analyzer = PairedAnalysis()
        result = analyzer.compute_fold_change(
            test_fmax=1500.0,
            test_fmax_se=50.0,
            control_fmax=1000.0,
            control_fmax_se=40.0,
        )

        assert isinstance(result, FoldChangeResult)
        assert result.is_valid
        assert result.fc_fmax == pytest.approx(1.5, rel=1e-6)
        assert result.log_fc_fmax is not None
        assert result.log_fc_fmax > 0  # test > control
        assert result.log_fc_fmax_se is not None

    def test_fold_change_with_kobs_and_tlag(self):
        """Test fold change computation including k_obs and t_lag parameters."""
        from app.analysis.comparison import PairedAnalysis

        analyzer = PairedAnalysis()
        result = analyzer.compute_fold_change(
            test_fmax=1300.0,
            test_fmax_se=40.0,
            control_fmax=1000.0,
            control_fmax_se=35.0,
            test_kobs=0.06,
            test_kobs_se=0.005,
            control_kobs=0.05,
            control_kobs_se=0.004,
            test_tlag=4.0,
            test_tlag_se=0.5,
            control_tlag=5.0,
            control_tlag_se=0.4,
        )

        assert result.is_valid
        assert result.fc_kobs is not None
        assert result.fc_kobs > 1.0  # test k_obs > control k_obs
        assert result.delta_tlag is not None
        assert result.delta_tlag == pytest.approx(-1.0)  # test tlag < control tlag

    def test_derived_fold_change(self):
        """Test derived fold change (mutant vs unregulated through WT)."""
        from app.analysis.comparison import PairedAnalysis, ComparisonType, PathType

        analyzer = PairedAnalysis()

        # Primary: mutant vs WT
        fc_primary = analyzer.compute_fold_change(
            test_fmax=1500.0, test_fmax_se=50.0,
            control_fmax=1000.0, control_fmax_se=40.0,
            comparison_type=ComparisonType.PRIMARY,
        )

        # Secondary: WT vs unregulated
        fc_secondary = analyzer.compute_fold_change(
            test_fmax=1000.0, test_fmax_se=40.0,
            control_fmax=800.0, control_fmax_se=30.0,
            comparison_type=ComparisonType.SECONDARY,
        )

        # Derived: mutant vs unregulated
        fc_derived = analyzer.compute_derived_fc(fc_primary, fc_secondary)

        assert fc_derived.is_valid
        assert fc_derived.comparison_type == ComparisonType.TERTIARY
        assert fc_derived.path_type == PathType.TWO_HOP
        assert fc_derived.variance_inflation_factor == 2.0
        # FC should be product of primary and secondary
        expected_fc = fc_primary.fc_fmax * fc_secondary.fc_fmax
        assert fc_derived.fc_fmax == pytest.approx(expected_fc, rel=1e-6)

    def test_mutant_to_mutant_comparison(self):
        """Test mutant-to-mutant comparison through shared WT reference."""
        from app.analysis.comparison import PairedAnalysis, ComparisonType

        analyzer = PairedAnalysis()

        # Mutant A vs WT
        fc_a_wt = analyzer.compute_fold_change(
            test_fmax=1300.0, test_fmax_se=45.0,
            control_fmax=1000.0, control_fmax_se=40.0,
            comparison_type=ComparisonType.PRIMARY,
        )

        # Mutant B vs WT
        fc_b_wt = analyzer.compute_fold_change(
            test_fmax=900.0, test_fmax_se=35.0,
            control_fmax=1000.0, control_fmax_se=40.0,
            comparison_type=ComparisonType.PRIMARY,
        )

        # Mutant A vs Mutant B
        fc_a_b = analyzer.compute_mutant_to_mutant_fc(fc_a_wt, fc_b_wt)

        assert fc_a_b.is_valid
        assert fc_a_b.comparison_type == ComparisonType.MUTANT_MUTANT
        assert fc_a_b.variance_inflation_factor == pytest.approx(np.sqrt(2))

    def test_variance_inflation_factors(self):
        """Test that variance inflation factors match expected values."""
        from app.analysis.comparison import PairedAnalysis, PathType, VIF_VALUES

        analyzer = PairedAnalysis()

        assert analyzer.get_variance_inflation_factor(PathType.DIRECT) == 1.0
        assert analyzer.get_variance_inflation_factor(PathType.ONE_HOP) == pytest.approx(np.sqrt(2))
        assert analyzer.get_variance_inflation_factor(PathType.TWO_HOP) == 2.0
        assert analyzer.get_variance_inflation_factor(PathType.FOUR_HOP) == 4.0

    def test_invalid_fold_change(self):
        """Test fold change with invalid inputs returns invalid result."""
        from app.analysis.comparison import PairedAnalysis

        analyzer = PairedAnalysis()
        result = analyzer.compute_fold_change(
            test_fmax=-100.0,  # negative - invalid
            test_fmax_se=10.0,
            control_fmax=1000.0,
            control_fmax_se=40.0,
        )

        assert not result.is_valid
        assert result.warning_message is not None


class TestComparisonGraphWorkflow:
    """Test comparison graph construction and path finding."""

    def test_comparison_graph_connectivity(self):
        """Test building a comparison graph and checking connectivity."""
        from app.analysis.comparison import ComparisonGraph

        graph = ComparisonGraph()

        # Add constructs in one family
        graph.add_construct(1, "FamilyA", is_wildtype=True)
        graph.add_construct(2, "FamilyA")
        graph.add_construct(3, "FamilyA")

        # Add direct comparisons (same plate)
        graph.add_direct_comparison(2, 1)  # mutant 2 vs WT 1
        graph.add_direct_comparison(3, 1)  # mutant 3 vs WT 1

        # Build derived paths
        graph.build_derived_paths()

        assert graph.is_connected()

        # Should have a mutant-to-mutant path via WT
        path_2_3 = graph.get_comparison_path(2, 3)
        assert path_2_3 is not None

    def test_analysis_scope_determination(self):
        """Test that analysis scope is correctly determined from graph structure."""
        from app.analysis.comparison import ComparisonGraph

        graph = ComparisonGraph()

        # Add two families with WTs and an unregulated reference
        graph.add_construct(1, "FamilyA", is_wildtype=True)
        graph.add_construct(2, "FamilyA")
        graph.add_construct(3, "FamilyB", is_wildtype=True)
        graph.add_construct(4, "FamilyB")
        graph.add_construct(5, "Unregulated", is_unregulated=True)

        # Direct comparisons
        graph.add_direct_comparison(2, 1)
        graph.add_direct_comparison(4, 3)
        graph.add_direct_comparison(1, 5)
        graph.add_direct_comparison(3, 5)

        graph.build_derived_paths()

        scope = graph.determine_analysis_scope()
        assert scope.can_analyze
        assert scope.scope == "full"


class TestAnalysisWorkflowIntegration:
    """Integration tests for the full analysis pipeline (fitting + comparison)."""

    def test_complete_analysis_pipeline(self):
        """Test the complete pipeline: synthetic data -> curve fit -> fold change."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.comparison import PairedAnalysis

        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        fitter = CurveFitter()

        # Generate and fit WT replicates
        wt_fmax_vals = []
        wt_fmax_ses = []
        for rep in range(3):
            true_fmax = np.random.normal(1000, 30)
            fluorescence = np.where(
                time > 3.0,
                100 + true_fmax * (1 - np.exp(-0.05 * (time - 3.0))),
                100.0,
            )
            fluorescence += np.random.normal(0, 15, len(time))
            result = fitter.fit(time, fluorescence)
            if result.converged:
                wt_fmax_vals.append(result.get_param("F_max"))
                wt_fmax_ses.append(result.get_param_se("F_max") or 0.0)

        # Generate and fit variant replicates (higher Fmax)
        var_fmax_vals = []
        var_fmax_ses = []
        for rep in range(3):
            true_fmax = np.random.normal(1300, 30)
            fluorescence = np.where(
                time > 3.0,
                100 + true_fmax * (1 - np.exp(-0.05 * (time - 3.0))),
                100.0,
            )
            fluorescence += np.random.normal(0, 15, len(time))
            result = fitter.fit(time, fluorescence)
            if result.converged:
                var_fmax_vals.append(result.get_param("F_max"))
                var_fmax_ses.append(result.get_param_se("F_max") or 0.0)

        assert len(wt_fmax_vals) >= 2, "Need at least 2 converged WT fits"
        assert len(var_fmax_vals) >= 2, "Need at least 2 converged variant fits"

        # Compute fold change from mean parameters
        analyzer = PairedAnalysis()
        fc_result = analyzer.compute_fold_change(
            test_fmax=float(np.mean(var_fmax_vals)),
            test_fmax_se=float(np.mean(var_fmax_ses)),
            control_fmax=float(np.mean(wt_fmax_vals)),
            control_fmax_se=float(np.mean(wt_fmax_ses)),
        )

        assert fc_result.is_valid
        # Variant has higher Fmax, so fold change should be > 1
        assert fc_result.fc_fmax > 1.0

    def test_model_selection_across_models(self):
        """Test fitting data with multiple kinetic models and selecting the best."""
        from app.analysis.curve_fitting import CurveFitter
        from app.analysis.kinetic_models import DelayedExponential

        np.random.seed(42)
        time = np.linspace(0, 120, 25)
        fluorescence = np.where(
            time > 5.0,
            100 + 1200 * (1 - np.exp(-0.06 * (time - 5.0))),
            100.0,
        )
        fluorescence += np.random.normal(0, 10, len(time))

        fitter = CurveFitter(DelayedExponential())
        best_model, best_result, all_results = fitter.select_best_model(time, fluorescence)

        assert best_model is not None
        assert best_result is not None
        assert isinstance(all_results, dict)
        # delayed_exponential should be among the candidates
        assert "delayed_exponential" in all_results

