"""Regression tests for excluded-well fold change persistence and readers."""
from datetime import date

from app.extensions import db
from app.models import Construct, Project
from app.models.experiment import ExperimentalSession, FitStatus, Plate, Well
from app.models.fit_result import FitResult, FoldChange
from app.models.plate_layout import PlateLayout, WellType
from app.models.project import PlateFormat
from app.services.comparison_graph_service import ComparisonGraphService
from app.services.data_export_service import DataExportService
from app.services.fit_management_service import FitManagementService
from app.services.fold_change_calculation_service import FoldChangeCalculationService
from app.services.fold_change_service import FoldChangeService
from app.services.hierarchical_service import HierarchicalService
from app.services.publication_package_service import (
    PublicationPackageConfig,
    PublicationPackageService,
)
from app.services.fold_change_query_helpers import visible_fold_change_count, visible_fold_change_query


def _make_project_with_plate():
    project = Project(
        name="FC Exclusion Regression",
        plate_format=PlateFormat.PLATE_384,
        precision_target=0.2,
    )
    db.session.add(project)
    db.session.flush()

    wt = Construct(
        project_id=project.id,
        identifier="WT",
        family="Fam",
        is_wildtype=True,
        is_draft=False,
    )
    mut_valid = Construct(
        project_id=project.id,
        identifier="MUT-VALID",
        family="Fam",
        is_wildtype=False,
        is_draft=False,
    )
    mut_excluded = Construct(
        project_id=project.id,
        identifier="MUT-EXCLUDED",
        family="Fam",
        is_wildtype=False,
        is_draft=False,
    )
    db.session.add_all([wt, mut_valid, mut_excluded])
    db.session.flush()

    session = ExperimentalSession(
        project_id=project.id,
        date=date.today(),
        batch_identifier="B1",
    )
    db.session.add(session)
    db.session.flush()

    layout = PlateLayout(project_id=project.id, name="L1", plate_format="384")
    db.session.add(layout)
    db.session.flush()

    plate = Plate(session_id=session.id, layout_id=layout.id, plate_number=1)
    db.session.add(plate)
    db.session.flush()

    return project, plate, wt, mut_valid, mut_excluded


def _add_fitted_well(
    plate,
    construct,
    position,
    fmax,
    *,
    is_excluded=False,
    exclude_from_fc=False,
):
    well = Well(
        plate_id=plate.id,
        position=position,
        construct_id=construct.id,
        well_type=WellType.SAMPLE,
        fit_status=FitStatus.SUCCESS,
        is_excluded=is_excluded,
        exclude_from_fc=exclude_from_fc,
    )
    db.session.add(well)
    db.session.flush()

    fit = FitResult(
        well_id=well.id,
        model_type="delayed_exponential",
        f_max=fmax,
        f_max_se=fmax * 0.05,
        k_obs=0.10,
        k_obs_se=0.01,
        f_baseline=100.0,
        f_baseline_se=10.0,
        r_squared=0.98,
        rmse=15.0,
        converged=True,
    )
    db.session.add(fit)
    db.session.flush()
    return well


def _add_fold_change(test_well, control_well, fmax=2.0):
    fc = FoldChange(
        test_well_id=test_well.id,
        control_well_id=control_well.id,
        fc_fmax=fmax,
        fc_fmax_se=0.2,
        log_fc_fmax=0.6931471805599453,
        log_fc_fmax_se=0.1,
        comparison_type="within_condition",
    )
    db.session.add(fc)
    db.session.flush()
    return fc


def _text_content(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(_text_content(child) for child in component)
    return _text_content(getattr(component, "children", None))


def _make_project_with_valid_and_stale_fold_changes():
    project, plate, wt, mut_valid, mut_excluded = _make_project_with_plate()

    wt_well = _add_fitted_well(plate, wt, "A1", 500.0)
    valid_well = _add_fitted_well(plate, mut_valid, "B1", 1000.0)
    excluded_well = _add_fitted_well(
        plate,
        mut_excluded,
        "C1",
        900.0,
        exclude_from_fc=True,
    )

    valid_fc = _add_fold_change(valid_well, wt_well, fmax=2.0)
    stale_fc = _add_fold_change(excluded_well, wt_well, fmax=1.8)
    db.session.commit()
    return project, valid_fc, stale_fc


def test_all_wells_excluded_recompute_persists_fold_change_deletion(db_session):
    """Early-return orphan deletion must be committed, not just session-local."""
    project, plate, wt, mut_valid, _ = _make_project_with_plate()
    wt_well = _add_fitted_well(plate, wt, "A1", 500.0)
    mut_well = _add_fitted_well(plate, mut_valid, "B1", 1000.0)
    db.session.commit()

    FoldChangeService.compute_plate_fold_changes(plate.id)
    assert FoldChange.query.count() == 1

    wt_well.exclude_from_fc = True
    mut_well.exclude_from_fc = True
    db.session.commit()

    assert FoldChangeService.compute_plate_fold_changes(plate.id) == []
    db.session.rollback()

    assert FoldChange.query.count() == 0


def test_fold_change_summary_ignores_test_and_control_exclusions(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()

    rows = FoldChangeCalculationService.get_fold_change_summary(project.id)

    assert [row["id"] for row in rows] == [valid_fc.id]


def test_can_publish_fitting_requires_non_excluded_fold_changes(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()
    valid_fc.test_well.exclude_from_fc = True
    db.session.commit()

    can_publish, blockers = FitManagementService.can_publish_fitting(project.id)

    assert can_publish is False
    assert "No fold changes computed" in blockers


def test_step4_counts_ignore_excluded_fold_changes(db_session):
    from app.layouts.analysis_results.workflow import create_step4_fold_changes

    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()

    component = create_step4_fold_changes(project_id=project.id)
    text = _text_content(component)

    assert "1 Records" in text
    assert "2 Records" not in text


def test_callback_fold_change_counts_ignore_excluded_test_and_control_wells(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()
    stale_control_fc = _add_fold_change(valid_fc.test_well, stale_fc.test_well, fmax=1.5)
    db.session.commit()

    visible_query, _, _ = visible_fold_change_query(project.id)

    assert visible_fold_change_count(project.id) == 1
    assert [fc.id for fc in visible_query.order_by(FoldChange.id).all()] == [valid_fc.id]


def test_export_results_ignore_excluded_fold_changes(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()

    results = DataExportService.get_results_for_export(project.id)

    exported_ids = {row["test_well_id"] for row in results["fold_changes"]}
    assert exported_ids == {valid_fc.test_well_id}
    assert results["data_summary"]["n_fold_changes"] == 1


def test_publication_package_preview_ignores_excluded_fold_changes(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()
    valid_fc.test_well.exclude_from_fc = True
    db.session.commit()

    preview = PublicationPackageService.get_package_preview(
        project.id,
        PublicationPackageConfig(),
    )
    processed = next(d for d in preview["directories"] if d["name"] == "processed_data")

    assert all(file_info["name"] != "fold_changes.csv" for file_info in processed["files"])


def test_hierarchical_data_ignores_excluded_fold_changes(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()

    df = HierarchicalService.get_fold_change_data(project.id)

    assert list(df["construct_id"]) == [valid_fc.test_well.construct_id]


def test_comparison_graph_ignores_excluded_fold_changes(db_session):
    project, valid_fc, stale_fc = _make_project_with_valid_and_stale_fold_changes()

    graph = ComparisonGraphService.build_comparison_graph(project.id)

    assert (valid_fc.test_well.construct_id, valid_fc.control_well.construct_id) in graph.edges
    assert (stale_fc.test_well.construct_id, stale_fc.control_well.construct_id) not in graph.edges
