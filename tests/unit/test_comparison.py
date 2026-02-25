"""
Tests for comparison hierarchy and fold change computation.

Phase 6: Comparison Hierarchy & Partial Analysis
T6.1-T6.17: Comparison and VIF tests
"""
import pytest
import numpy as np
from datetime import date
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import Project, Construct
from app.models.project import PlateFormat
from app.models.experiment import ExperimentalSession, Plate, Well, FitStatus
from app.models.plate_layout import WellType
from app.models.fit_result import FitResult, FoldChange
from app.analysis.comparison import (
    PairedAnalysis,
    ComparisonGraph,
    ComparisonType,
    PathType,
    FoldChangeResult,
    AnalysisScope,
    VIF_VALUES,
    compute_effective_sample_size
)
from app.services import (
    ProjectService, ConstructService, PlateLayoutService
)


class TestFoldChangeComputation:
    """Tests for basic fold change computation (T6.1-T6.3)."""

    def test_primary_fc_mutant_vs_wt(self):
        """T6.1: Primary FC (mutant vs WT) computed correctly."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=1000.0,
            test_fmax_se=50.0,
            control_fmax=500.0,
            control_fmax_se=25.0,
            test_construct_id=1,
            control_construct_id=2,
            comparison_type=ComparisonType.PRIMARY
        )

        assert result.is_valid
        assert result.fc_fmax == pytest.approx(2.0)
        assert result.log_fc_fmax == pytest.approx(np.log(2.0))
        assert result.comparison_type == ComparisonType.PRIMARY

    def test_fc_with_kobs(self):
        """Test fold change with k_obs values."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=1000.0,
            test_fmax_se=50.0,
            control_fmax=500.0,
            control_fmax_se=25.0,
            test_kobs=0.12,
            test_kobs_se=0.01,
            control_kobs=0.10,
            control_kobs_se=0.01
        )

        assert result.fc_kobs == pytest.approx(1.2)
        assert result.log_fc_kobs == pytest.approx(np.log(1.2))

    def test_fc_with_tlag(self):
        """Test fold change with t_lag difference."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=1000.0,
            test_fmax_se=50.0,
            control_fmax=500.0,
            control_fmax_se=25.0,
            test_tlag=5.0,
            test_tlag_se=0.5,
            control_tlag=10.0,
            control_tlag_se=0.5
        )

        assert result.delta_tlag == pytest.approx(-5.0)
        assert result.delta_tlag_se == pytest.approx(np.sqrt(0.5**2 + 0.5**2))

    def test_uncertainty_propagation(self):
        """T6.3: Derived FC propagates uncertainty correctly."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=1000.0,
            test_fmax_se=100.0,  # 10% relative SE
            control_fmax=500.0,
            control_fmax_se=50.0  # 10% relative SE
        )

        # SE(log_FC) = sqrt[(0.1)² + (0.1)²] = sqrt(0.02) ≈ 0.1414
        expected_log_se = np.sqrt((100/1000)**2 + (50/500)**2)
        assert result.log_fc_fmax_se == pytest.approx(expected_log_se)

    def test_invalid_negative_fmax(self):
        """Test handling of invalid (negative) F_max values."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=-100.0,
            test_fmax_se=10.0,
            control_fmax=500.0,
            control_fmax_se=25.0
        )

        assert not result.is_valid
        assert "Invalid F_max" in result.warning_message

    def test_invalid_zero_control(self):
        """Test handling of zero control value."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=100.0,
            test_fmax_se=10.0,
            control_fmax=0.0,
            control_fmax_se=0.0
        )

        assert not result.is_valid


class TestDerivedComparisons:
    """Tests for derived fold change calculations (T6.2-T6.4)."""

    def test_secondary_fc_wt_vs_unreg(self):
        """T6.2: Secondary FC (WT vs unreg) computed correctly."""
        analyzer = PairedAnalysis()

        result = analyzer.compute_fold_change(
            test_fmax=500.0,
            test_fmax_se=25.0,
            control_fmax=100.0,
            control_fmax_se=10.0,
            comparison_type=ComparisonType.SECONDARY
        )

        assert result.is_valid
        assert result.fc_fmax == pytest.approx(5.0)
        assert result.comparison_type == ComparisonType.SECONDARY

    def test_tertiary_derived_fc(self):
        """T6.3: Tertiary FC (mutant vs unreg) via primary + secondary."""
        analyzer = PairedAnalysis()

        # Primary: mutant vs WT (FC = 2)
        primary = FoldChangeResult(
            fc_fmax=2.0,
            log_fc_fmax=np.log(2.0),
            log_fc_fmax_se=0.1,
            is_valid=True
        )

        # Secondary: WT vs unreg (FC = 5)
        secondary = FoldChangeResult(
            fc_fmax=5.0,
            log_fc_fmax=np.log(5.0),
            log_fc_fmax_se=0.15,
            is_valid=True
        )

        derived = analyzer.compute_derived_fc(primary, secondary)

        # Mutant vs unreg = 2 × 5 = 10
        assert derived.fc_fmax == pytest.approx(10.0)
        assert derived.log_fc_fmax == pytest.approx(np.log(10.0))
        assert derived.comparison_type == ComparisonType.TERTIARY
        assert derived.path_type == PathType.TWO_HOP

        # SE should be sqrt(0.1² + 0.15²)
        expected_se = np.sqrt(0.1**2 + 0.15**2)
        assert derived.log_fc_fmax_se == pytest.approx(expected_se)

    def test_mutant_to_mutant_fc(self):
        """T6.4: Mutant-to-mutant FC through shared WT."""
        analyzer = PairedAnalysis()

        # Mutant A vs WT (FC = 2)
        fc_a_wt = FoldChangeResult(
            fc_fmax=2.0,
            log_fc_fmax=np.log(2.0),
            log_fc_fmax_se=0.1,
            test_construct_id=1,
            is_valid=True
        )

        # Mutant B vs WT (FC = 4)
        fc_b_wt = FoldChangeResult(
            fc_fmax=4.0,
            log_fc_fmax=np.log(4.0),
            log_fc_fmax_se=0.12,
            test_construct_id=2,
            is_valid=True
        )

        result = analyzer.compute_mutant_to_mutant_fc(fc_a_wt, fc_b_wt)

        # Mutant A vs B = 2/4 = 0.5
        assert result.fc_fmax == pytest.approx(0.5)
        assert result.log_fc_fmax == pytest.approx(np.log(0.5))
        assert result.comparison_type == ComparisonType.MUTANT_MUTANT
        assert result.path_type == PathType.ONE_HOP

        # VIF should be sqrt(2)
        assert result.variance_inflation_factor == pytest.approx(np.sqrt(2))


class TestVarianceInflationFactors:
    """Tests for VIF calculations (T6.5-T6.7)."""

    def test_vif_direct_equals_one(self):
        """T6.5: VIF = 1.0 for direct (same plate) comparisons."""
        analyzer = PairedAnalysis()
        vif = analyzer.get_variance_inflation_factor(PathType.DIRECT)
        assert vif == pytest.approx(1.0)

    def test_vif_one_hop(self):
        """T6.4: VIF = sqrt(2) for one-hop (mutant-mutant via WT)."""
        analyzer = PairedAnalysis()
        vif = analyzer.get_variance_inflation_factor(PathType.ONE_HOP)
        assert vif == pytest.approx(np.sqrt(2))

    def test_vif_two_hop(self):
        """T6.6: VIF = 2.0 for two-hop (mutant → WT → unreg)."""
        analyzer = PairedAnalysis()
        vif = analyzer.get_variance_inflation_factor(PathType.TWO_HOP)
        assert vif == pytest.approx(2.0)

    def test_vif_four_hop(self):
        """T6.7: VIF = 4.0 for cross-family comparisons."""
        analyzer = PairedAnalysis()
        vif = analyzer.get_variance_inflation_factor(PathType.FOUR_HOP)
        assert vif == pytest.approx(4.0)

    def test_apply_vif_to_se(self):
        """Test VIF application to standard error."""
        analyzer = PairedAnalysis()

        se = 0.1
        inflated = analyzer.apply_vif_to_se(se, PathType.TWO_HOP)

        # SE_inflated = SE * sqrt(VIF) = 0.1 * sqrt(2) ≈ 0.1414
        expected = se * np.sqrt(2.0)
        assert inflated == pytest.approx(expected)


class TestComparisonGraph:
    """Tests for comparison graph construction (T6.8-T6.11)."""

    def test_graph_includes_all_constructs(self):
        """T6.8: Comparison graph includes all constructs."""
        graph = ComparisonGraph()

        # Add constructs
        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox1")
        graph.add_construct(4, "Tbox2", is_wildtype=True)
        graph.add_construct(5, "Tbox2")
        graph.add_construct(6, "Unregulated", is_unregulated=True)

        assert len(graph.nodes) == 6
        assert len(graph.families) == 3  # Tbox1, Tbox2, Unregulated
        assert graph.unregulated_id == 6

    def test_disconnected_graph_detected(self):
        """T6.9: Disconnected graph detected correctly."""
        graph = ComparisonGraph()

        # Create two disconnected families
        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox2", is_wildtype=True)
        graph.add_construct(4, "Tbox2")

        # Only add edges within families, not between
        graph.add_direct_comparison(1, 2)
        graph.add_direct_comparison(3, 4)

        assert not graph.is_connected()

        components = graph.get_disconnected_components()
        assert len(components) == 2

    def test_connected_graph_with_unregulated(self):
        """Test connected graph through unregulated reference."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox2", is_wildtype=True)
        graph.add_construct(4, "Tbox2")
        graph.add_construct(5, "Unregulated", is_unregulated=True)

        # Connect within families
        graph.add_direct_comparison(1, 2)
        graph.add_direct_comparison(3, 4)

        # Connect families through unregulated
        graph.add_direct_comparison(1, 5)
        graph.add_direct_comparison(3, 5)

        assert graph.is_connected()

    def test_missing_unreg_allows_within_family(self):
        """T6.10: Missing unreg allows within-family comparisons only."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox1")

        graph.add_direct_comparison(1, 2)
        graph.add_direct_comparison(1, 3)

        scope = graph.determine_analysis_scope()

        assert scope.can_analyze
        assert "unregulated" in scope.missing_anchors
        assert scope.scope == "within_family_only"

    def test_missing_wt_excludes_family(self):
        """T6.11: Missing WT for family excludes that family."""
        graph = ComparisonGraph()

        # Family 1 has WT
        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")

        # Family 2 has NO WT
        graph.add_construct(3, "Tbox2")
        graph.add_construct(4, "Tbox2")

        graph.add_direct_comparison(1, 2)

        scope = graph.determine_analysis_scope()

        assert "Tbox2" in scope.affected_families
        assert any("Tbox2" in w for w in scope.warnings)

    def test_build_derived_paths(self):
        """Test building derived comparison paths."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox1")
        graph.add_construct(4, "Unregulated", is_unregulated=True)

        # Direct comparisons
        graph.add_direct_comparison(2, 1)  # Mutant2 vs WT
        graph.add_direct_comparison(3, 1)  # Mutant3 vs WT
        graph.add_direct_comparison(1, 4)  # WT vs Unreg

        graph.build_derived_paths()

        # Should create mutant-to-mutant path
        path_2_3 = graph.get_comparison_path(2, 3)
        assert path_2_3 is not None
        assert path_2_3.path_type == PathType.ONE_HOP

        # Should create tertiary paths
        path_2_unreg = graph.get_comparison_path(2, 4)
        assert path_2_unreg is not None
        assert path_2_unreg.path_type == PathType.TWO_HOP


class TestAnalysisScope:
    """Tests for analysis scope determination (T6.12)."""

    def test_full_scope(self):
        """Full analysis scope with all anchors."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Unregulated", is_unregulated=True)

        graph.add_direct_comparison(1, 2)
        graph.add_direct_comparison(1, 3)

        scope = graph.determine_analysis_scope()

        assert scope.can_analyze
        assert scope.scope == "full"
        assert len(scope.missing_anchors) == 0

    def test_partial_scope(self):
        """Partial scope when some families lack WT."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1", is_wildtype=True)
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox2")  # No WT for Tbox2

        scope = graph.determine_analysis_scope()

        assert scope.can_analyze
        assert scope.scope == "partial"
        assert "Tbox2" in scope.affected_families

    def test_no_analysis_possible(self):
        """No analysis possible when no family has WT."""
        graph = ComparisonGraph()

        graph.add_construct(1, "Tbox1")  # No WT
        graph.add_construct(2, "Tbox1")
        graph.add_construct(3, "Tbox2")  # No WT

        scope = graph.determine_analysis_scope()

        assert not scope.can_analyze
        assert scope.scope == "none"


class TestCrossFamily:
    """Tests for cross-family comparisons (T6.17)."""

    def test_cross_family_computation(self):
        """Test cross-family comparison with VIF=4."""
        analyzer = PairedAnalysis()

        # M1 vs WT1
        fc_m1_wt1 = FoldChangeResult(
            fc_fmax=2.0,
            log_fc_fmax=np.log(2.0),
            log_fc_fmax_se=0.1,
            is_valid=True
        )

        # WT1 vs Unreg
        fc_wt1_unreg = FoldChangeResult(
            fc_fmax=5.0,
            log_fc_fmax=np.log(5.0),
            log_fc_fmax_se=0.12,
            is_valid=True
        )

        # WT2 vs Unreg
        fc_wt2_unreg = FoldChangeResult(
            fc_fmax=4.0,
            log_fc_fmax=np.log(4.0),
            log_fc_fmax_se=0.11,
            is_valid=True
        )

        # M2 vs WT2
        fc_m2_wt2 = FoldChangeResult(
            fc_fmax=3.0,
            log_fc_fmax=np.log(3.0),
            log_fc_fmax_se=0.09,
            is_valid=True
        )

        result = analyzer.compute_cross_family_fc(
            fc_m1_wt1, fc_wt1_unreg, fc_wt2_unreg, fc_m2_wt2
        )

        assert result.comparison_type == ComparisonType.CROSS_FAMILY
        assert result.path_type == PathType.FOUR_HOP
        assert result.variance_inflation_factor == pytest.approx(4.0)
        assert result.low_precision_warning  # Should warn about exploratory


class TestLowPrecisionFlags:
    """Tests for low precision detection (T6.8)."""

    def test_flag_low_precision_intermediate(self):
        """Test flagging low precision intermediate comparisons."""
        analyzer = PairedAnalysis(low_precision_threshold=0.5)

        # High precision (narrow CI)
        high_precision = FoldChangeResult(
            log_fc_fmax=0.5,
            log_fc_fmax_se=0.1  # CI width = 2 * 1.96 * 0.1 ≈ 0.39
        )
        assert not analyzer.flag_low_precision_intermediate(high_precision)

        # Low precision (wide CI)
        low_precision = FoldChangeResult(
            log_fc_fmax=0.5,
            log_fc_fmax_se=0.2  # CI width = 2 * 1.96 * 0.2 ≈ 0.78
        )
        assert analyzer.flag_low_precision_intermediate(low_precision)

    def test_derived_fc_propagates_warning(self):
        """Test that derived FC gets warning from low precision intermediate."""
        analyzer = PairedAnalysis(low_precision_threshold=0.3)

        primary = FoldChangeResult(
            fc_fmax=2.0,
            log_fc_fmax=np.log(2.0),
            log_fc_fmax_se=0.1,
            is_valid=True
        )

        # Low precision secondary
        secondary = FoldChangeResult(
            fc_fmax=5.0,
            log_fc_fmax=np.log(5.0),
            log_fc_fmax_se=0.2,  # Wide CI
            is_valid=True
        )

        derived = analyzer.compute_derived_fc(primary, secondary)

        assert derived.low_precision_warning
        assert "low precision" in derived.warning_message.lower()


class TestEffectiveSampleSize:
    """Tests for effective sample size calculation."""

    def test_effective_sample_size_direct(self):
        """Effective n equals actual n for direct comparisons."""
        n_eff = compute_effective_sample_size(10, 1.0)
        assert n_eff == 10

    def test_effective_sample_size_one_hop(self):
        """Effective n reduced for one-hop comparisons."""
        vif = np.sqrt(2)
        n_eff = compute_effective_sample_size(10, vif)
        # n_eff = 10 / 2 = 5
        assert n_eff == pytest.approx(5.0)

    def test_effective_sample_size_two_hop(self):
        """Effective n reduced for two-hop comparisons."""
        n_eff = compute_effective_sample_size(10, 2.0)
        # n_eff = 10 / 4 = 2.5
        assert n_eff == pytest.approx(2.5)


class TestComparisonService:
    """Integration tests for ComparisonService."""

    @pytest.fixture
    def setup_comparison_data(self, db_session):
        """Create test data for comparison tests."""
        # Create project
        project = ProjectService.create_project(
            name="Comparison Test Project",
            username="testuser",
            plate_format=PlateFormat.PLATE_384
        )

        # Create constructs
        wt = ConstructService.create_construct(
            project_id=project.id,
            identifier="WT",
            family="Tbox1",
            username="testuser",
            is_wildtype=True
        )
        ConstructService.publish_construct(wt.id, "testuser")

        mutant1 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Mutant1",
            family="Tbox1",
            username="testuser"
        )
        ConstructService.publish_construct(mutant1.id, "testuser")

        mutant2 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Mutant2",
            family="Tbox1",
            username="testuser"
        )
        ConstructService.publish_construct(mutant2.id, "testuser")

        # Create layout
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="testuser",
            plate_format="384"
        )

        # Create session and plate
        session = ExperimentalSession(
            project_id=project.id,
            date=date(2024, 1, 15),
            batch_identifier="Batch_001"
        )
        db.session.add(session)
        db.session.flush()

        plate = Plate(
            session_id=session.id,
            layout_id=layout.id,
            plate_number=1
        )
        db.session.add(plate)
        db.session.flush()

        # Create wells with fit results
        wells = {}
        for i, (construct, pos) in enumerate([
            (wt, "A1"), (mutant1, "A2"), (mutant2, "A3")
        ]):
            well = Well(
                plate_id=plate.id,
                position=pos,
                construct_id=construct.id,
                well_type=WellType.SAMPLE,
                fit_status=FitStatus.SUCCESS
            )
            db.session.add(well)
            db.session.flush()

            fit = FitResult(
                well_id=well.id,
                model_type="delayed_exponential",
                f_baseline=100.0,
                f_max=500.0 * (i + 1),
                f_max_se=25.0 * (i + 1),
                k_obs=0.1,
                k_obs_se=0.01,
                t_lag=5.0 + i,
                t_lag_se=0.5,
                r_squared=0.98,
                converged=True
            )
            db.session.add(fit)
            wells[construct.identifier] = well

        db.session.commit()

        return {
            'project_id': project.id,
            'plate_id': plate.id,
            'wt_id': wt.id,
            'mutant1_id': mutant1.id,
            'mutant2_id': mutant2.id,
            'wells': wells
        }

    def test_compute_plate_fold_changes(self, db_session, setup_comparison_data):
        """Test computing fold changes for a plate."""
        from app.services.comparison_service import ComparisonService

        fold_changes = ComparisonService.compute_plate_fold_changes(
            setup_comparison_data['plate_id']
        )

        # Should have fold changes for mutant1 vs WT and mutant2 vs WT
        assert len(fold_changes) >= 2

    def test_build_comparison_graph(self, db_session, setup_comparison_data):
        """Test building comparison graph."""
        from app.services.comparison_service import ComparisonService

        # First compute fold changes
        ComparisonService.compute_plate_fold_changes(
            setup_comparison_data['plate_id']
        )

        graph = ComparisonService.build_comparison_graph(
            setup_comparison_data['project_id']
        )

        assert len(graph.nodes) == 3  # WT + 2 mutants
        assert "Tbox1" in graph.families

    def test_validate_graph_connectivity(self, db_session, setup_comparison_data):
        """Test graph connectivity validation."""
        from app.services.comparison_service import ComparisonService

        # First compute fold changes
        ComparisonService.compute_plate_fold_changes(
            setup_comparison_data['plate_id']
        )

        scope = ComparisonService.validate_graph_connectivity(
            setup_comparison_data['project_id']
        )

        assert scope.can_analyze
        # No unregulated, so within_family_only
        assert scope.scope == "within_family_only"

    def test_comparison_summary(self, db_session, setup_comparison_data):
        """Test getting comparison summary."""
        from app.services.comparison_service import ComparisonService

        # First compute fold changes
        ComparisonService.compute_plate_fold_changes(
            setup_comparison_data['plate_id']
        )

        summary = ComparisonService.get_comparison_summary(
            setup_comparison_data['project_id']
        )

        assert summary.primary_count >= 0
        assert summary.scope is not None


class TestCIWidthProperty:
    """Tests for CI width calculations."""

    def test_ci_width_fmax(self):
        """Test 95% CI width calculation for log_fc_fmax."""
        result = FoldChangeResult(
            log_fc_fmax=0.5,
            log_fc_fmax_se=0.1
        )

        # 95% CI width = 2 * 1.96 * SE
        expected = 2 * 1.96 * 0.1
        assert result.ci_width_fmax == pytest.approx(expected)

    def test_ci_width_none_when_no_se(self):
        """CI width is None when SE is not available."""
        result = FoldChangeResult(
            log_fc_fmax=0.5
        )

        assert result.ci_width_fmax is None
