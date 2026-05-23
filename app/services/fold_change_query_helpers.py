"""Shared query helpers for user-visible fold-change rows."""
from sqlalchemy.orm import aliased

from app.models import ExperimentalSession, Plate, Well
from app.models.fit_result import FoldChange


def visible_fold_change_query(project_id):
    """Return fold changes whose test and control wells are visible for FC use."""
    test_well = aliased(Well, name="test_well")
    control_well = aliased(Well, name="control_well")

    query = (
        FoldChange.query
        .join(test_well, FoldChange.test_well_id == test_well.id)
        .join(control_well, FoldChange.control_well_id == control_well.id)
        .join(Plate, test_well.plate_id == Plate.id)
        .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
        .filter(
            ExperimentalSession.project_id == project_id,
            test_well.is_excluded == False,
            test_well.exclude_from_fc == False,
            control_well.is_excluded == False,
            control_well.exclude_from_fc == False,
        )
    )
    return query, test_well, control_well


def visible_fold_change_count(project_id):
    """Count user-visible fold changes for a project."""
    query, _, _ = visible_fold_change_query(project_id)
    return query.count()
