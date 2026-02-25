"""
Tests for R² threshold filtering for fold change calculation.

Tests the ability to exclude wells with low R² from FC calculations
and the associated service methods.
"""
import pytest
import numpy as np
from datetime import date

from app.extensions import db
from app.models import (
    Project, Construct, PlateLayout,
    ExperimentalSession, Plate, Well, RawDataPoint
)
from app.models.project import PlateFormat
from app.models.plate_layout import WellType
from app.models.experiment import FitStatus
from app.models.fit_result import FitResult, FoldChange
from app.services import (
    ProjectService, ConstructService, PlateLayoutService
)
from app.services.fitting_service import FittingService, FittingError
from app.services.comparison_service import ComparisonService


def _generate_kinetic_data(
    t_lag: float = 5.0,
    k_obs: float = 0.02,
    f_max: float = 50000.0,
    f_baseline: float = 1000.0,
    noise_std: float = 500.0,
    n_points: int = 60
) -> tuple:
    """Generate synthetic kinetic data with delayed exponential model."""
    t = np.linspace(0, 180, n_points)
    np.random.seed(42)  # For reproducibility

    # Delayed exponential model
    F = np.where(
        t < t_lag,
        f_baseline,
        f_baseline + f_max * (1 - np.exp(-k_obs * (t - t_lag)))
    )
    F_noisy = F + np.random.normal(0, noise_std, len(t))

    return t, F_noisy


def _generate_poor_data(n_points: int = 60) -> tuple:
    """Generate poor quality data that will have low R²."""
    t = np.linspace(0, 180, n_points)
    np.random.seed(123)
    # Generate noisy data with no clear trend
    F = 5000 + np.random.normal(0, 3000, len(t))
    return t, F


@pytest.fixture
def setup_project_with_varied_fits(db_session):
    """Create a project with plates containing wells with varying R² values."""
    # Create project
    project = ProjectService.create_project(
        name="R² Filtering Test Project",
        username="testuser",
        plate_format=PlateFormat.PLATE_384
    )

    # Create constructs
    wt = ConstructService.create_construct(
        project_id=project.id,
        identifier="WT",
        family="Family1",
        username="testuser",
        is_wildtype=True
    )
    ConstructService.publish_construct(wt.id, "testuser")

    mutant = ConstructService.create_construct(
        project_id=project.id,
        identifier="Mutant",
        family="Family1",
        username="testuser"
    )
    ConstructService.publish_construct(mutant.id, "testuser")

    # Create layout
    layout = PlateLayoutService.create_layout(
        project_id=project.id,
        name="Test Layout",
        username="testuser"
    )

    # Assign wells: A1-A3 will have good fits, A4-A5 will have poor fits
    for pos in ["A1", "A2", "A3", "A4", "A5"]:
        PlateLayoutService.assign_well(
            layout.id, pos, "testuser",
            construct_id=wt.id if pos in ["A1", "A4"] else mutant.id,
            well_type=WellType.SAMPLE
        )

    db.session.commit()

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

    # Create wells and add data
    wells = {}
    for pos in ["A1", "A2", "A3", "A4", "A5"]:
        well = Well(
            plate_id=plate.id,
            position=pos,
            construct_id=wt.id if pos in ["A1", "A4"] else mutant.id,
            well_type=WellType.SAMPLE
        )
        db.session.add(well)
        db.session.flush()
        wells[pos] = well

        # Add raw data - good data for A1-A3, poor for A4-A5
        if pos in ["A1", "A2", "A3"]:
            t, F = _generate_kinetic_data()
        else:
            t, F = _generate_poor_data()

        for i, (time, fluor) in enumerate(zip(t, F)):
            dp = RawDataPoint(
                well_id=well.id,
                timepoint=float(time),
                fluorescence_raw=float(fluor)
            )
            db.session.add(dp)

    db.session.commit()

    # Fit all wells
    for pos, well in wells.items():
        try:
            FittingService.fit_well(well.id)
        except Exception:
            pass  # Some fits may fail, which is expected

    return {
        "project": project,
        "plate": plate,
        "wells": wells,
        "wt": wt,
        "mutant": mutant,
    }


class TestR2ExclusionPreview:
    """Tests for get_r2_exclusion_preview method."""

    def test_preview_returns_expected_structure(self, setup_project_with_varied_fits):
        """Preview should return dict with expected keys."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        preview = FittingService.get_r2_exclusion_preview(project_id, 0.8)

        assert "total_wells" in preview
        assert "below_threshold" in preview
        assert "well_ids" in preview
        assert "by_plate" in preview
        assert "threshold" in preview

    def test_preview_threshold_affects_count(self, setup_project_with_varied_fits):
        """Lower threshold should result in fewer excluded wells."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        high_threshold = FittingService.get_r2_exclusion_preview(project_id, 0.95)
        low_threshold = FittingService.get_r2_exclusion_preview(project_id, 0.5)

        # Higher threshold should exclude more wells
        assert high_threshold["below_threshold"] >= low_threshold["below_threshold"]

    def test_preview_does_not_modify_database(self, setup_project_with_varied_fits):
        """Preview should not change any exclude_from_fc flags."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        # Get initial state
        wells = Well.query.join(Plate).join(Plate.session).filter(
            Plate.session.has(project_id=project_id)
        ).all()
        initial_states = {w.id: w.exclude_from_fc for w in wells}

        # Run preview
        FittingService.get_r2_exclusion_preview(project_id, 0.8)

        # Check state hasn't changed
        db.session.expire_all()
        for well in wells:
            assert well.exclude_from_fc == initial_states[well.id]


class TestR2ExclusionApply:
    """Tests for apply_r2_exclusion method."""

    def test_apply_excludes_low_r2_wells(self, setup_project_with_varied_fits):
        """Apply should mark wells with R² < threshold as excluded."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        result = FittingService.apply_r2_exclusion(project_id, 0.8)

        # Check that some wells were excluded
        assert "excluded_count" in result
        assert "excluded_well_ids" in result

        # Verify excluded wells have exclude_from_fc = True
        for well_id in result["excluded_well_ids"]:
            well = Well.query.get(well_id)
            assert well.exclude_from_fc is True

    def test_apply_resets_previous_exclusions(self, setup_project_with_varied_fits):
        """Apply should reset all exclude_from_fc flags before applying new threshold."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        # First apply a high threshold
        FittingService.apply_r2_exclusion(project_id, 0.95)

        # Then apply a low threshold
        result = FittingService.apply_r2_exclusion(project_id, 0.5)

        # Wells that were excluded by high threshold but not by low should be included
        wells = Well.query.join(Plate).join(Plate.session).filter(
            Plate.session.has(project_id=project_id),
            Well.well_type == WellType.SAMPLE,
        ).all()

        excluded_count = sum(1 for w in wells if w.exclude_from_fc)
        assert excluded_count == result["excluded_count"]


class TestClearR2Exclusions:
    """Tests for clear_r2_exclusions method."""

    def test_clear_removes_all_exclusions(self, setup_project_with_varied_fits):
        """Clear should set exclude_from_fc=False for all wells."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        # First apply some exclusions
        FittingService.apply_r2_exclusion(project_id, 0.8)

        # Clear exclusions
        count = FittingService.clear_r2_exclusions(project_id)

        # Verify all wells are included
        wells = Well.query.join(Plate).join(Plate.session).filter(
            Plate.session.has(project_id=project_id),
            Well.well_type == WellType.SAMPLE,
        ).all()

        for well in wells:
            assert well.exclude_from_fc is False


class TestSetWellFcInclusion:
    """Tests for set_well_fc_inclusion method."""

    def test_toggle_individual_well(self, setup_project_with_varied_fits):
        """Should be able to toggle individual well inclusion."""
        data = setup_project_with_varied_fits
        well = data["wells"]["A1"]

        # Initially included
        assert well.exclude_from_fc is False

        # Exclude
        FittingService.set_well_fc_inclusion(well.id, include=False)
        db.session.expire(well)
        assert well.exclude_from_fc is True

        # Include again
        FittingService.set_well_fc_inclusion(well.id, include=True)
        db.session.expire(well)
        assert well.exclude_from_fc is False

    def test_invalid_well_raises_error(self, db_session):
        """Should raise error for invalid well ID."""
        with pytest.raises(FittingError):
            FittingService.set_well_fc_inclusion(999999, include=True)


class TestComparisonServiceWithExclusions:
    """Tests that ComparisonService respects exclude_from_fc flag."""

    def test_excluded_wells_not_in_fold_changes(self, setup_project_with_varied_fits):
        """Excluded wells should not be included in fold change calculations."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id
        plate_id = data["plate"].id
        wt_well = data["wells"]["A1"]

        # Exclude the WT well
        FittingService.set_well_fc_inclusion(wt_well.id, include=False)

        # Compute fold changes
        fold_changes = ComparisonService.compute_plate_fold_changes(plate_id)

        # Excluded WT well should not be a control in any FC
        for fc in fold_changes:
            assert fc.control_well_id != wt_well.id


class TestGetFcExclusionStatus:
    """Tests for get_fc_exclusion_status method."""

    def test_status_returns_expected_structure(self, setup_project_with_varied_fits):
        """Status should return dict with expected keys."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        status = FittingService.get_fc_exclusion_status(project_id)

        assert "total_fitted_wells" in status
        assert "included_in_fc" in status
        assert "excluded_from_fc" in status
        assert "excluded_r2_range" in status

    def test_status_counts_match(self, setup_project_with_varied_fits):
        """Included + excluded should equal total."""
        data = setup_project_with_varied_fits
        project_id = data["project"].id

        # Apply some exclusions
        FittingService.apply_r2_exclusion(project_id, 0.8)

        status = FittingService.get_fc_exclusion_status(project_id)

        assert status["included_in_fc"] + status["excluded_from_fc"] == status["total_fitted_wells"]
