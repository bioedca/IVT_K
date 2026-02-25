"""
Tests for ComparisonService facade and sub-services.

Tests the service-layer with database integration:
- FoldChangeService - fold change computation with DB records
- ComparisonGraphService - comparison graph construction and validation
- PrecisionWeightService - precision weights and VIF computation
- ComparisonService facade - delegation verification

These tests complement test_comparison.py which tests the PairedAnalysis math
and ComparisonGraph data structure. This file focuses on service-layer behavior
that touches the database.
"""
import pytest
import numpy as np
from datetime import date

from app.extensions import db
from app.models import Project, Construct
from app.models.project import PlateFormat
from app.models.experiment import ExperimentalSession, Plate, Well, FitStatus, QCStatus
from app.models.plate_layout import PlateLayout, WellType
from app.models.fit_result import FitResult, FoldChange
from app.models.enums import FoldChangeCategory, LigandCondition
from app.services.fold_change_service import FoldChangeService
from app.services.comparison_graph_service import (
    ComparisonGraphService,
    ComparisonError,
    ComparisonSummary,
    ExclusionImpact,
)
from app.services.precision_weight_service import PrecisionWeightService
from app.services.comparison_service import ComparisonService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_project(name="Test Project"):
    """Create and flush a project."""
    project = Project(name=name, plate_format=PlateFormat.PLATE_384, precision_target=0.2)
    db.session.add(project)
    db.session.flush()
    return project


def _make_constructs(project, n_mutants=1, with_unregulated=False):
    """Create WT + mutants (+ optionally unregulated) for a single family.

    Returns (wt, [mutants], unreg_or_None).
    """
    wt = Construct(
        project_id=project.id, identifier="WT", family="Fam",
        is_wildtype=True, is_draft=False,
    )
    db.session.add(wt)
    db.session.flush()

    mutants = []
    for i in range(n_mutants):
        m = Construct(
            project_id=project.id, identifier=f"MUT{i+1}", family="Fam",
            is_wildtype=False, is_draft=False,
        )
        db.session.add(m)
        db.session.flush()
        mutants.append(m)

    unreg = None
    if with_unregulated:
        unreg = Construct(
            project_id=project.id, identifier="UNREG", family="Unregulated",
            is_unregulated=True, is_draft=False,
        )
        db.session.add(unreg)
        db.session.flush()

    return wt, mutants, unreg


def _make_plate(project, session=None):
    """Create an ExperimentalSession + PlateLayout + Plate and flush."""
    if session is None:
        session = ExperimentalSession(
            project_id=project.id, date=date.today(), batch_identifier="B1",
            qc_status=QCStatus.APPROVED,
        )
        db.session.add(session)
        db.session.flush()

    layout = PlateLayout(project_id=project.id, name="L1", plate_format="384")
    db.session.add(layout)
    db.session.flush()

    plate = Plate(session_id=session.id, layout_id=layout.id, plate_number=1)
    db.session.add(plate)
    db.session.flush()
    return session, plate


def _add_well(plate, construct, position, fmax=500.0, kobs=0.10,
              ligand_condition=None, excluded=False, exclude_from_fc=False,
              fit_status=FitStatus.SUCCESS, add_fit=True):
    """Add a well with an optional fit result. Returns (well, fit_result_or_None)."""
    w = Well(
        plate_id=plate.id, position=position, construct_id=construct.id,
        well_type=WellType.SAMPLE, fit_status=fit_status,
        ligand_condition=ligand_condition,
        is_excluded=excluded, exclude_from_fc=exclude_from_fc,
    )
    db.session.add(w)
    db.session.flush()

    fr = None
    if add_fit and fit_status == FitStatus.SUCCESS:
        fr = FitResult(
            well_id=w.id, model_type="delayed_exponential",
            f_max=fmax, f_max_se=fmax * 0.05,
            k_obs=kobs, k_obs_se=kobs * 0.1,
            f_baseline=100.0, f_baseline_se=10.0,
            r_squared=0.98, rmse=15.0, converged=True,
        )
        db.session.add(fr)
        db.session.flush()

    return w, fr


# ===========================================================================
# TestFoldChangeServiceComputation
# ===========================================================================


class TestFoldChangeServiceComputation:
    """Service-layer tests for FoldChangeService.compute_plate_fold_changes."""

    def test_compute_plate_fold_changes_basic(self, db_session):
        """Basic plate with WT + mutant wells creates FC records."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        # 2 WT wells, 2 mutant wells
        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, wt, "A2", fmax=520.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        _add_well(plate, mut, "B2", fmax=1050.0)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)

        # 2 mutant wells x 2 WT wells = 4 primary FCs
        assert len(result) == 4
        # All should be in DB
        fcs = FoldChange.query.all()
        assert len(fcs) == 4
        # Verify FC values are positive (mutant fmax > wt fmax)
        for fc in fcs:
            assert fc.fc_fmax > 1.0
            assert fc.log_fc_fmax > 0.0
            assert fc.comparison_type == str(FoldChangeCategory.WITHIN_CONDITION)

    def test_compute_plate_fold_changes_no_wells(self, db_session):
        """Plate with no valid wells returns empty list."""
        project = _make_project()
        _, plate = _make_plate(project)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert result == []

    def test_compute_plate_fold_changes_invalid_plate(self, db_session):
        """Nonexistent plate raises ComparisonError."""
        with pytest.raises(ComparisonError, match="not found"):
            FoldChangeService.compute_plate_fold_changes(99999)

    def test_compute_plate_fold_changes_overwrite(self, db_session):
        """overwrite=True recalculates existing fold changes."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        w_mut, fr_mut = _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        # First run
        fcs1 = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert len(fcs1) == 1
        original_fc = fcs1[0].fc_fmax

        # Modify the mutant fit result so a recalculation would differ
        fr_mut.f_max = 2000.0
        db.session.commit()

        # Without overwrite — returns existing
        fcs2 = FoldChangeService.compute_plate_fold_changes(plate.id, overwrite=False)
        assert len(fcs2) == 1
        assert fcs2[0].fc_fmax == pytest.approx(original_fc)

        # With overwrite — recalculated
        fcs3 = FoldChangeService.compute_plate_fold_changes(plate.id, overwrite=True)
        assert len(fcs3) == 1
        assert fcs3[0].fc_fmax == pytest.approx(2000.0 / 500.0)
        assert fcs3[0].fc_fmax != pytest.approx(original_fc)

    def test_compute_plate_fold_changes_excluded_wells(self, db_session):
        """Excluded wells (is_excluded or exclude_from_fc) are skipped."""
        project = _make_project()
        wt, [mut1], _ = _make_constructs(project, n_mutants=1)
        # Create a second mutant
        mut2 = Construct(
            project_id=project.id, identifier="MUT2", family="Fam",
            is_wildtype=False, is_draft=False,
        )
        db.session.add(mut2)
        db.session.flush()

        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut1, "B1", fmax=1000.0, excluded=True)        # is_excluded
        _add_well(plate, mut2, "C1", fmax=1000.0, exclude_from_fc=True)  # exclude_from_fc
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert result == []

    def test_compute_plate_fold_changes_with_ligand(self, db_session):
        """Ligand conditions create within-condition FCs per condition."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        # +Lig wells
        _add_well(plate, wt, "A1", fmax=500.0, ligand_condition=LigandCondition.PLUS_LIG)
        _add_well(plate, mut, "B1", fmax=1000.0, ligand_condition=LigandCondition.PLUS_LIG)

        # -Lig wells
        _add_well(plate, wt, "A2", fmax=480.0, ligand_condition=LigandCondition.MINUS_LIG)
        _add_well(plate, mut, "B2", fmax=960.0, ligand_condition=LigandCondition.MINUS_LIG)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)

        # Within-condition: 1 mut x 1 wt per condition = 2
        # Ligand effect: 2 constructs x (1 +Lig x 1 -Lig) = 2
        # Total = 4
        within_cond = [fc for fc in result if fc.comparison_type == str(FoldChangeCategory.WITHIN_CONDITION)]
        ligand_eff = [fc for fc in result if fc.comparison_type == str(FoldChangeCategory.LIGAND_EFFECT)]
        assert len(within_cond) == 2
        assert len(ligand_eff) == 2

    def test_compute_plate_fold_changes_ligand_effect(self, db_session):
        """Same construct +Lig vs -Lig creates ligand_effect FC with correct direction."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        # WT in both conditions
        _add_well(plate, wt, "A1", fmax=500.0, ligand_condition=LigandCondition.PLUS_LIG)
        _add_well(plate, wt, "A2", fmax=250.0, ligand_condition=LigandCondition.MINUS_LIG)

        # Mutant in both conditions
        _add_well(plate, mut, "B1", fmax=1200.0, ligand_condition=LigandCondition.PLUS_LIG)
        _add_well(plate, mut, "B2", fmax=600.0, ligand_condition=LigandCondition.MINUS_LIG)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)

        ligand_fcs = [fc for fc in result if fc.comparison_type == str(FoldChangeCategory.LIGAND_EFFECT)]
        assert len(ligand_fcs) == 2  # one for WT, one for mutant

        # +Lig / -Lig ratio should be ~2 for both constructs
        for fc in ligand_fcs:
            assert fc.fc_fmax == pytest.approx(2.0, rel=0.05)
            assert fc.ligand_condition == "+Lig/-Lig"

    def test_compute_plate_fold_changes_no_wt(self, db_session):
        """No WT wells on plate yields no primary FCs."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        # Only mutant wells (no WT)
        _add_well(plate, mut, "B1", fmax=1000.0)
        _add_well(plate, mut, "B2", fmax=1050.0)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert result == []


# ===========================================================================
# TestComparisonGraphServiceDB
# ===========================================================================


class TestComparisonGraphServiceDB:
    """Service-layer tests for ComparisonGraphService with DB integration."""

    def test_build_comparison_graph_basic(self, db_session):
        """Builds graph from project with fold changes."""
        project = _make_project()
        wt, [mut1], _ = _make_constructs(project, n_mutants=1)
        mut2 = Construct(
            project_id=project.id, identifier="MUT2", family="Fam",
            is_wildtype=False, is_draft=False,
        )
        db.session.add(mut2)
        db.session.flush()

        _, plate = _make_plate(project)
        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut1, "B1", fmax=1000.0)
        _add_well(plate, mut2, "C1", fmax=800.0)
        db.session.commit()

        # Compute FCs first
        FoldChangeService.compute_plate_fold_changes(plate.id)

        graph = ComparisonGraphService.build_comparison_graph(project.id)

        assert len(graph.nodes) == 3
        assert "Fam" in graph.families
        assert wt.id in graph.wildtypes.values()

    def test_build_comparison_graph_empty_project(self, db_session):
        """Project with no FCs produces graph with nodes but no edges."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        db.session.commit()

        graph = ComparisonGraphService.build_comparison_graph(project.id)

        assert len(graph.nodes) == 2
        assert len(graph.edges) == 0

    def test_get_comparison_summary(self, db_session):
        """Returns ComparisonSummary with correct counts."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)
        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        FoldChangeService.compute_plate_fold_changes(plate.id)

        summary = ComparisonGraphService.get_comparison_summary(project.id)

        assert isinstance(summary, ComparisonSummary)
        assert summary.primary_count >= 1
        assert summary.scope is not None
        assert summary.scope.can_analyze

    def test_detect_orphaned_wells(self, db_session):
        """Mutant wells with no FC partner are orphaned."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        # Create a second family with a mutant but no WT
        orphan_mut = Construct(
            project_id=project.id, identifier="ORPHAN", family="Fam2",
            is_wildtype=False, is_draft=False,
        )
        db.session.add(orphan_mut)
        db.session.flush()

        _, plate = _make_plate(project)
        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        _add_well(plate, orphan_mut, "C1", fmax=900.0)
        db.session.commit()

        # Compute FCs — orphan_mut has no WT in its family
        FoldChangeService.compute_plate_fold_changes(plate.id)

        orphaned = ComparisonGraphService.get_orphaned_wells(project.id)
        orphaned_construct_ids = [w.construct_id for w in orphaned]
        assert orphan_mut.id in orphaned_construct_ids

    def test_propagate_wt_exclusion(self, db_session):
        """Excluding a WT well reports impact on downstream FCs."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        wt_well, _ = _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        # Compute FCs so there are records referencing the WT well
        FoldChangeService.compute_plate_fold_changes(plate.id)

        impact = ComparisonGraphService.propagate_wt_exclusion(wt_well.id)

        assert isinstance(impact, ExclusionImpact)
        # Only one WT well => complete exclusion
        assert impact.is_complete_exclusion is True
        assert impact.remaining_wt_count == 0
        assert len(impact.affected_mutant_wells) >= 1
        assert impact.ci_widening_estimate == float("inf")
        assert "orphaned" in impact.warning_message.lower()

    def test_propagate_wt_exclusion_partial(self, db_session):
        """Excluding one of two WT wells is a partial exclusion."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        wt_well1, _ = _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, wt, "A2", fmax=510.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        FoldChangeService.compute_plate_fold_changes(plate.id)

        impact = ComparisonGraphService.propagate_wt_exclusion(wt_well1.id)

        assert impact.is_complete_exclusion is False
        assert impact.remaining_wt_count == 1
        assert impact.orphaned_mutant_count == 0
        # CI widening should be a finite percentage
        assert 0 < impact.ci_widening_estimate < float("inf")


# ===========================================================================
# TestPrecisionWeightServiceDB
# ===========================================================================


class TestPrecisionWeightServiceDB:
    """Service-layer tests for PrecisionWeightService with DB integration."""

    def _setup_with_graph_records(self, db_session):
        """Create project, constructs, FCs, and persisted graph records.

        Returns (project, analysis_version, graph).
        """
        from app.models.analysis_version import AnalysisVersion, AnalysisStatus

        project = _make_project()
        wt, [mut], unreg = _make_constructs(project, n_mutants=1, with_unregulated=True)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        _add_well(plate, unreg, "C1", fmax=100.0)
        db.session.commit()

        FoldChangeService.compute_plate_fold_changes(plate.id)

        graph = ComparisonGraphService.build_comparison_graph(project.id)
        ComparisonGraphService.save_comparison_graph(project.id, graph)

        av = AnalysisVersion(
            project_id=project.id, name="v1", model_type="delayed_exponential",
            status=AnalysisStatus.COMPLETED,
        )
        db.session.add(av)
        db.session.commit()

        return project, av, graph

    def test_compute_precision_weights(self, db_session):
        """Stores VIF-based precision weights for graph records."""
        from app.models.comparison import PrecisionWeight

        project, av, graph = self._setup_with_graph_records(db_session)

        PrecisionWeightService.store_precision_weights(project.id, av.id, graph)

        weights = PrecisionWeight.query.filter_by(analysis_version_id=av.id).all()
        # Should have at least one weight record
        assert len(weights) > 0
        for pw in weights:
            assert pw.variance_inflation_factor > 0
            assert pw.precision_weight > 0
            # weight = 1 / vif^2
            assert pw.precision_weight == pytest.approx(
                1.0 / (pw.variance_inflation_factor ** 2)
            )

    def test_precision_weights_single_plate(self, db_session):
        """Single plate direct comparison gives VIF = 1.0."""
        from app.models.comparison import PrecisionWeight

        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        FoldChangeService.compute_plate_fold_changes(plate.id)
        graph = ComparisonGraphService.build_comparison_graph(project.id)
        ComparisonGraphService.save_comparison_graph(project.id, graph)

        from app.models.analysis_version import AnalysisVersion, AnalysisStatus
        av = AnalysisVersion(
            project_id=project.id, name="v1", model_type="delayed_exponential",
            status=AnalysisStatus.COMPLETED,
        )
        db.session.add(av)
        db.session.commit()

        PrecisionWeightService.store_precision_weights(project.id, av.id, graph)

        weights = PrecisionWeight.query.filter_by(analysis_version_id=av.id).all()
        # Direct comparisons have VIF = 1.0
        for pw in weights:
            assert pw.variance_inflation_factor == pytest.approx(1.0)
            assert pw.precision_weight == pytest.approx(1.0)

    def test_store_precision_weights_updates_existing(self, db_session):
        """Calling store_precision_weights twice updates existing records."""
        from app.models.comparison import PrecisionWeight

        project, av, graph = self._setup_with_graph_records(db_session)

        PrecisionWeightService.store_precision_weights(project.id, av.id, graph)
        count1 = PrecisionWeight.query.filter_by(analysis_version_id=av.id).count()

        # Store again — should update, not duplicate
        PrecisionWeightService.store_precision_weights(project.id, av.id, graph)
        count2 = PrecisionWeight.query.filter_by(analysis_version_id=av.id).count()

        assert count2 == count1

    def test_precision_weights_no_graph_records(self, db_session):
        """Calling store on project with no graph records is a no-op."""
        from app.models.comparison import PrecisionWeight
        from app.models.analysis_version import AnalysisVersion, AnalysisStatus
        from app.analysis.comparison import ComparisonGraph as AnalysisGraph

        project = _make_project()
        db.session.commit()

        av = AnalysisVersion(
            project_id=project.id, name="v1", model_type="delayed_exponential",
            status=AnalysisStatus.COMPLETED,
        )
        db.session.add(av)
        db.session.commit()

        empty_graph = AnalysisGraph()

        # Should not raise
        PrecisionWeightService.store_precision_weights(project.id, av.id, empty_graph)

        weights = PrecisionWeight.query.filter_by(analysis_version_id=av.id).all()
        assert len(weights) == 0


# ===========================================================================
# TestComparisonServiceFacade
# ===========================================================================


class TestComparisonServiceFacade:
    """Tests that the ComparisonService facade delegates correctly."""

    def test_facade_delegates_compute(self, db_session):
        """Facade compute_plate_fold_changes delegates to FoldChangeService."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        # Call through facade
        fcs_facade = ComparisonService.compute_plate_fold_changes(plate.id)
        assert len(fcs_facade) >= 1

        # Verify DB records match
        fcs_db = FoldChange.query.all()
        assert len(fcs_db) == len(fcs_facade)

    def test_facade_delegates_graph(self, db_session):
        """Facade build_comparison_graph delegates to ComparisonGraphService."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        db.session.commit()

        FoldChangeService.compute_plate_fold_changes(plate.id)

        graph_facade = ComparisonService.build_comparison_graph(project.id)
        graph_direct = ComparisonGraphService.build_comparison_graph(project.id)

        # Both should produce graphs with same node set
        assert set(graph_facade.nodes.keys()) == set(graph_direct.nodes.keys())

    def test_facade_has_all_methods(self):
        """Verify ComparisonService exposes all expected delegate methods."""
        expected_methods = [
            "compute_plate_fold_changes",
            "build_comparison_graph",
            "save_comparison_graph",
            "validate_graph_connectivity",
            "propagate_wt_exclusion",
            "get_orphaned_wells",
            "compute_derived_comparisons",
            "get_comparison_summary",
        ]
        for method_name in expected_methods:
            assert hasattr(ComparisonService, method_name), (
                f"ComparisonService missing method: {method_name}"
            )
            assert callable(getattr(ComparisonService, method_name))


# ===========================================================================
# TestFoldChangeServiceEdgeCases
# ===========================================================================


class TestFoldChangeServiceEdgeCases:
    """Additional edge-case tests for fold change computation."""

    def test_wells_with_failed_fits_skipped(self, db_session):
        """Wells with fit_status != SUCCESS are excluded."""
        project = _make_project()
        wt, [mut], _ = _make_constructs(project, n_mutants=1)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0, fit_status=FitStatus.FAILED, add_fit=False)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert result == []

    def test_wells_without_construct_skipped(self, db_session):
        """Wells with construct_id=None are excluded."""
        project = _make_project()
        wt, _, _ = _make_constructs(project, n_mutants=0)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        # Add a well with no construct
        w = Well(
            plate_id=plate.id, position="B1", construct_id=None,
            well_type=WellType.BLANK, fit_status=FitStatus.SUCCESS,
        )
        db.session.add(w)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)
        assert result == []

    def test_secondary_fc_wt_vs_unregulated(self, db_session):
        """Computes secondary FCs when unregulated construct is present."""
        project = _make_project()
        wt, [mut], unreg = _make_constructs(project, n_mutants=1, with_unregulated=True)
        _, plate = _make_plate(project)

        _add_well(plate, wt, "A1", fmax=500.0)
        _add_well(plate, mut, "B1", fmax=1000.0)
        _add_well(plate, unreg, "C1", fmax=100.0)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)

        # Primary: mut vs wt = 1
        # Secondary: wt vs unreg = 1
        # Total >= 2
        assert len(result) >= 2

        fcs = FoldChange.query.all()
        # Check that at least one FC involves unreg as control
        unreg_control_ids = [fc.control_well_id for fc in fcs]
        unreg_wells = Well.query.filter_by(construct_id=unreg.id).all()
        unreg_well_ids = [w.id for w in unreg_wells]
        assert any(cid in unreg_well_ids for cid in unreg_control_ids)

    def test_multiple_families(self, db_session):
        """Fold changes computed independently per family."""
        project = _make_project()

        # Family 1
        wt1 = Construct(
            project_id=project.id, identifier="WT1", family="Fam1",
            is_wildtype=True, is_draft=False,
        )
        mut1 = Construct(
            project_id=project.id, identifier="MUT1", family="Fam1",
            is_wildtype=False, is_draft=False,
        )
        # Family 2
        wt2 = Construct(
            project_id=project.id, identifier="WT2", family="Fam2",
            is_wildtype=True, is_draft=False,
        )
        mut2 = Construct(
            project_id=project.id, identifier="MUT2", family="Fam2",
            is_wildtype=False, is_draft=False,
        )
        db.session.add_all([wt1, mut1, wt2, mut2])
        db.session.flush()

        _, plate = _make_plate(project)
        _add_well(plate, wt1, "A1", fmax=500.0)
        _add_well(plate, mut1, "A2", fmax=1000.0)
        _add_well(plate, wt2, "B1", fmax=600.0)
        _add_well(plate, mut2, "B2", fmax=1200.0)
        db.session.commit()

        result = FoldChangeService.compute_plate_fold_changes(plate.id)

        # 1 FC per family = 2 total
        assert len(result) == 2

        # Verify cross-family pairings did NOT occur
        for fc in result:
            test_well = Well.query.get(fc.test_well_id)
            control_well = Well.query.get(fc.control_well_id)
            test_construct = Construct.query.get(test_well.construct_id)
            control_construct = Construct.query.get(control_well.construct_id)
            assert test_construct.family == control_construct.family
