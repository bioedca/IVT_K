"""
Tests for fitting service.

Phase 4.3: Nonlinear fitting engine (database integration)
Phase 4.6: Split well handling
Phase 4.10: Paired fold change calculation
Phase 4.13: Signal quality metrics
"""
import pytest
import numpy as np
from datetime import date

from app.extensions import db
from app.models import (
    Project, Construct, PlateLayout, WellAssignment,
    ExperimentalSession, Plate, Well, RawDataPoint
)
from app.models.project import PlateFormat
from app.models.plate_layout import WellType
from app.models.experiment import FitStatus
from app.models.fit_result import FitResult, FoldChange, SignalQualityMetrics
from app.services import (
    ProjectService, ConstructService, PlateLayoutService, FittingService, FittingError
)
from app.analysis.kinetic_models import DelayedExponential, ModelParameters


@pytest.fixture
def setup_plate_with_data(db_session):
    """Create a project with plate and raw data."""
    # Create project
    project = ProjectService.create_project(
        name="Fitting Test Project",
        username="testuser",
        plate_format=PlateFormat.PLATE_384
    )

    # Create constructs
    wt = ConstructService.create_construct(
        project_id=project.id,
        identifier="WT Tbox",
        family="Tbox1",
        username="testuser",
        is_wildtype=True
    )
    ConstructService.publish_construct(wt.id, "testuser")

    mutant = ConstructService.create_construct(
        project_id=project.id,
        identifier="Mutant A",
        family="Tbox1",
        username="testuser"
    )
    ConstructService.publish_construct(mutant.id, "testuser")

    # Create layout
    layout = PlateLayoutService.create_layout(
        project_id=project.id,
        name="Test Layout",
        username="testuser"
    )

    # Assign wells
    PlateLayoutService.assign_well(
        layout.id, "A1", "testuser",
        construct_id=wt.id,
        well_type=WellType.SAMPLE
    )
    PlateLayoutService.assign_well(
        layout.id, "A2", "testuser",
        construct_id=mutant.id,
        well_type=WellType.SAMPLE
    )
    PlateLayoutService.assign_well(
        layout.id, "A3", "testuser",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
    )
    PlateLayoutService.assign_well(
        layout.id, "A4", "testuser",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
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

    # Create wells and add synthetic data
    model = DelayedExponential()
    t = np.linspace(0, 60, 30)

    wells_data = {}

    # WT well (A1) with specific parameters
    wt_params = ModelParameters()
    wt_params.set("F_baseline", 100.0)
    wt_params.set("F_max", 500.0)
    wt_params.set("k_obs", 0.1)
    wt_params.set("t_lag", 5.0)
    wt_F = model.evaluate(t, wt_params) + np.random.normal(0, 5, len(t))

    well_wt = Well(
        plate_id=plate.id,
        position="A1",
        construct_id=wt.id,
        well_type=WellType.SAMPLE,
        fit_status=FitStatus.PENDING
    )
    db.session.add(well_wt)
    db.session.flush()

    for i, (time, fluor) in enumerate(zip(t, wt_F)):
        dp = RawDataPoint(well_id=well_wt.id, timepoint=time, fluorescence_raw=fluor)
        db.session.add(dp)

    wells_data["wt"] = {"well": well_wt, "params": wt_params}

    # Mutant well (A2) with 2x F_max
    mutant_params = ModelParameters()
    mutant_params.set("F_baseline", 100.0)
    mutant_params.set("F_max", 1000.0)  # 2x WT
    mutant_params.set("k_obs", 0.12)
    mutant_params.set("t_lag", 4.0)
    mutant_F = model.evaluate(t, mutant_params) + np.random.normal(0, 5, len(t))

    well_mutant = Well(
        plate_id=plate.id,
        position="A2",
        construct_id=mutant.id,
        well_type=WellType.SAMPLE,
        fit_status=FitStatus.PENDING
    )
    db.session.add(well_mutant)
    db.session.flush()

    for i, (time, fluor) in enumerate(zip(t, mutant_F)):
        dp = RawDataPoint(well_id=well_mutant.id, timepoint=time, fluorescence_raw=fluor)
        db.session.add(dp)

    wells_data["mutant"] = {"well": well_mutant, "params": mutant_params}

    # Negative control wells (flat, low signal)
    neg_params = ModelParameters()
    neg_params.set("F_baseline", 50.0)
    neg_params.set("F_max", 0.0)
    neg_params.set("k_obs", 0.1)
    neg_params.set("t_lag", 0.0)
    neg_F = model.evaluate(t, neg_params) + np.random.normal(0, 10, len(t))

    well_neg1 = Well(
        plate_id=plate.id,
        position="A3",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
        fit_status=FitStatus.PENDING
    )
    db.session.add(well_neg1)
    db.session.flush()

    for i, (time, fluor) in enumerate(zip(t, neg_F)):
        dp = RawDataPoint(well_id=well_neg1.id, timepoint=time, fluorescence_raw=max(0, fluor))
        db.session.add(dp)

    wells_data["neg1"] = {"well": well_neg1, "params": neg_params}

    # Second negative control
    neg_F2 = model.evaluate(t, neg_params) + np.random.normal(0, 10, len(t))
    well_neg2 = Well(
        plate_id=plate.id,
        position="A4",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
        fit_status=FitStatus.PENDING
    )
    db.session.add(well_neg2)
    db.session.flush()

    for i, (time, fluor) in enumerate(zip(t, neg_F2)):
        dp = RawDataPoint(well_id=well_neg2.id, timepoint=time, fluorescence_raw=max(0, fluor))
        db.session.add(dp)

    wells_data["neg2"] = {"well": well_neg2, "params": neg_params}

    db.session.commit()

    return {
        "project_id": project.id,
        "plate_id": plate.id,
        "session_id": session.id,
        "layout_id": layout.id,
        "wt_id": wt.id,
        "mutant_id": mutant.id,
        "wells": wells_data
    }


class TestFittingService:
    """Tests for FittingService."""

    def test_fit_well_success(self, db_session, setup_plate_with_data):
        """T4.3: Fit single well successfully."""
        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        result = FittingService.fit_well(well_id)

        assert result.converged
        assert result.r_squared > 0.9
        assert result.f_max is not None
        assert result.k_obs is not None

        # Check well status updated
        well = Well.query.get(well_id)
        assert well.fit_status == FitStatus.SUCCESS

    def test_fit_well_not_found(self, db_session):
        """Test error for non-existent well."""
        with pytest.raises(FittingError, match="not found"):
            FittingService.fit_well(999999)

    def test_fit_well_insufficient_data(self, db_session, setup_plate_with_data):
        """T4.24: Handle insufficient data points."""
        # Create a well with only 3 data points
        plate_id = setup_plate_with_data["plate_id"]

        well = Well(
            plate_id=plate_id,
            position="B1",
            well_type=WellType.SAMPLE,
            fit_status=FitStatus.PENDING
        )
        db.session.add(well)
        db.session.flush()

        # Add only 3 data points (below minimum)
        for t in [0, 30, 60]:
            dp = RawDataPoint(well_id=well.id, timepoint=t, fluorescence_raw=100 + t)
            db.session.add(dp)
        db.session.commit()

        with pytest.raises(FittingError, match="Insufficient data"):
            FittingService.fit_well(well.id)

    def test_fit_well_refit(self, db_session, setup_plate_with_data):
        """T4.12: Refit overwrites existing result."""
        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # First fit
        result1 = FittingService.fit_well(well_id)
        original_fitted_at = result1.fitted_at

        # Force refit
        result2 = FittingService.fit_well(well_id, force_refit=True)

        assert result2.id == result1.id  # Same record updated
        assert result2.fitted_at >= original_fitted_at


class TestBatchFitting:
    """Tests for batch fitting operations."""

    def test_fit_plate(self, db_session, setup_plate_with_data):
        """T4.10: Batch fitting with continue-always policy."""
        plate_id = setup_plate_with_data["plate_id"]

        result = FittingService.fit_plate(plate_id)

        # Should process all wells
        assert result.total_wells == 4
        assert result.successful_fits >= 2  # At least sample wells
        assert result.failed_fits >= 0  # Negative controls may fail
        # No critical failures
        assert isinstance(result.fit_results, list)

    def test_fit_plate_progress_callback(self, db_session, setup_plate_with_data):
        """T4.17: Progress callback updates."""
        plate_id = setup_plate_with_data["plate_id"]
        progress_updates = []

        def callback(progress):
            progress_updates.append({
                "completed": progress.completed_wells,
                "total": progress.total_wells,
                "current": progress.current_well
            })

        FittingService.fit_plate(plate_id, progress_callback=callback)

        # Should have received updates (one per sample well)
        assert len(progress_updates) >= 2
        # Final progress should be complete
        assert progress_updates[-1]["completed"] == progress_updates[-1]["total"]


class TestFoldChangeCalculation:
    """Tests for fold change calculations."""

    def test_compute_fold_change(self, db_session, setup_plate_with_data):
        """T4.14: Fold change computed correctly."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]
        mutant_well = setup_plate_with_data["wells"]["mutant"]["well"]

        # Fit both wells first
        FittingService.fit_well(wt_well.id)
        FittingService.fit_well(mutant_well.id)

        # Compute fold change
        fc = FittingService.compute_fold_change(mutant_well.id, wt_well.id)

        # Mutant has 2x F_max, so FC should be ~2
        assert fc.fc_fmax is not None
        assert fc.fc_fmax == pytest.approx(2.0, rel=0.3)

    def test_log_fold_change(self, db_session, setup_plate_with_data):
        """T4.15: Log fold change computed."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]
        mutant_well = setup_plate_with_data["wells"]["mutant"]["well"]

        FittingService.fit_well(wt_well.id)
        FittingService.fit_well(mutant_well.id)

        fc = FittingService.compute_fold_change(mutant_well.id, wt_well.id)

        # log2(2) = 1
        assert fc.log_fc_fmax is not None
        assert fc.log_fc_fmax == pytest.approx(1.0, rel=0.3)

    def test_fold_change_requires_fit(self, db_session, setup_plate_with_data):
        """Fold change requires both wells to have fits."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]
        mutant_well = setup_plate_with_data["wells"]["mutant"]["well"]

        # Only fit one well
        FittingService.fit_well(wt_well.id)

        with pytest.raises(FittingError, match="no valid fit"):
            FittingService.compute_fold_change(mutant_well.id, wt_well.id)

    def test_fold_change_uncertainty_propagation(self, db_session, setup_plate_with_data):
        """T4.6: Uncertainty propagated through fold change."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]
        mutant_well = setup_plate_with_data["wells"]["mutant"]["well"]

        FittingService.fit_well(wt_well.id)
        FittingService.fit_well(mutant_well.id)

        fc = FittingService.compute_fold_change(mutant_well.id, wt_well.id)

        # Should have standard errors
        assert fc.fc_fmax_se is not None
        assert fc.fc_fmax_se > 0


class TestSignalQualityMetrics:
    """Tests for signal quality metrics."""

    def test_snr_computed(self, db_session, setup_plate_with_data):
        """T4.18: SNR computed correctly."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]

        fit_result = FittingService.fit_well(wt_well.id)

        # Check signal quality was computed
        sq = SignalQualityMetrics.query.filter_by(fit_result_id=fit_result.id).first()

        # SNR should be computed using negative controls
        # If available, should be > 1 for signal well
        assert sq is not None
        if sq.snr is not None:
            assert sq.snr > 0

    def test_detection_limits(self, db_session, setup_plate_with_data):
        """T4.19: LOD/LOQ computed."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]

        fit_result = FittingService.fit_well(wt_well.id)

        sq = SignalQualityMetrics.query.filter_by(fit_result_id=fit_result.id).first()

        # Should have detection limits if negative controls present
        assert sq is not None
        if sq.lod_value is not None:
            assert sq.loq_value is not None
            assert sq.loq_value > sq.lod_value  # LOQ > LOD


class TestWellFitData:
    """Tests for retrieving fit data for visualization."""

    def test_get_well_fit_data(self, db_session, setup_plate_with_data):
        """T4.12: Curve browser data retrieval."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]

        FittingService.fit_well(wt_well.id)

        data = FittingService.get_well_fit_data(wt_well.id)

        assert "timepoints" in data
        assert "fluorescence_raw" in data
        assert "fit_curve" in data
        assert "parameters" in data
        assert "statistics" in data

        assert len(data["timepoints"]) == 30
        assert data["parameters"]["F_max"]["value"] is not None
        assert data["statistics"]["r_squared"] > 0.9

    def test_get_well_fit_data_no_fit(self, db_session, setup_plate_with_data):
        """Data retrieval when no fit exists."""
        wt_well = setup_plate_with_data["wells"]["wt"]["well"]

        # Don't fit the well
        data = FittingService.get_well_fit_data(wt_well.id)

        assert "timepoints" in data
        assert "fluorescence_raw" in data
        assert data["fit_curve"] is None
        assert data["parameters"] is None


class TestFitResultArchival:
    """Tests for Fit Result Archival feature (PRD F8.7)."""

    def test_archive_created_on_refit(self, db_session, setup_plate_with_data):
        """T4.9.1: Archival on refit creates archive record."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initial fit
        first_fit = FittingService.fit_well(well_id)
        first_fit_id = first_fit.id
        first_r_squared = first_fit.r_squared
        first_f_max = first_fit.f_max

        # Refit with force
        second_fit = FittingService.fit_well(
            well_id,
            force_refit=True,
            refit_by="testuser",
            refit_reason="Testing refit functionality"
        )

        # Check archive was created
        archives = FitResultArchive.query.filter_by(well_id=well_id).all()
        assert len(archives) == 1

        archive = archives[0]
        assert archive.original_fit_id == first_fit_id
        assert archive.r_squared == first_r_squared
        assert archive.f_max == first_f_max
        assert archive.superseded_by == "testuser"
        assert archive.superseded_reason == "Testing refit functionality"
        assert archive.superseded_at is not None

    def test_multiple_refits_create_multiple_archives(self, db_session, setup_plate_with_data):
        """T4.9.2: Multiple refits accumulate archives."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initial fit
        FittingService.fit_well(well_id)

        # Multiple refits
        for i in range(3):
            FittingService.fit_well(
                well_id,
                force_refit=True,
                refit_by=f"user{i}",
                refit_reason=f"Refit {i+1}"
            )

        # Should have 3 archive records
        archives = FitResultArchive.query.filter_by(well_id=well_id).all()
        assert len(archives) == 3

        # Verify each has unique superseded_by
        superseded_users = {a.superseded_by for a in archives}
        assert superseded_users == {"user0", "user1", "user2"}

    def test_archive_preserves_all_parameters(self, db_session, setup_plate_with_data):
        """T4.9.3: Archive preserves all fit parameters."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initial fit
        first_fit = FittingService.fit_well(well_id)

        # Store original values
        original_values = {
            'f_baseline': first_fit.f_baseline,
            'f_baseline_se': first_fit.f_baseline_se,
            'f_max': first_fit.f_max,
            'f_max_se': first_fit.f_max_se,
            'k_obs': first_fit.k_obs,
            'k_obs_se': first_fit.k_obs_se,
            't_lag': first_fit.t_lag,
            't_lag_se': first_fit.t_lag_se,
            'r_squared': first_fit.r_squared,
            'rmse': first_fit.rmse,
            'aic': first_fit.aic,
            'converged': first_fit.converged,
            'model_type': first_fit.model_type,
        }

        # Refit
        FittingService.fit_well(well_id, force_refit=True)

        # Verify archive preserves all values
        archive = FitResultArchive.query.filter_by(well_id=well_id).first()

        assert archive.f_baseline == original_values['f_baseline']
        assert archive.f_max == original_values['f_max']
        assert archive.k_obs == original_values['k_obs']
        assert archive.t_lag == original_values['t_lag']
        assert archive.r_squared == original_values['r_squared']
        assert archive.rmse == original_values['rmse']
        assert archive.aic == original_values['aic']
        assert archive.converged == original_values['converged']
        assert archive.model_type == original_values['model_type']

    def test_no_archive_without_force_refit(self, db_session, setup_plate_with_data):
        """T4.9.4: No archive created when not refitting."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initial fit
        FittingService.fit_well(well_id)

        # Try to fit again without force (should return existing)
        FittingService.fit_well(well_id, force_refit=False)

        # No archives should exist
        archives = FitResultArchive.query.filter_by(well_id=well_id).all()
        assert len(archives) == 0

    def test_archive_disabled_option(self, db_session, setup_plate_with_data):
        """T4.9.5: Archive can be disabled with parameter."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initial fit
        FittingService.fit_well(well_id)

        # Refit with archiving disabled
        FittingService.fit_well(well_id, force_refit=True, archive_existing=False)

        # No archive should exist
        archives = FitResultArchive.query.filter_by(well_id=well_id).all()
        assert len(archives) == 0

    def test_get_well_fit_history(self, db_session, setup_plate_with_data):
        """T4.9.6: Get complete fit history for a well."""
        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Create multiple fits
        FittingService.fit_well(well_id)
        FittingService.fit_well(well_id, force_refit=True, refit_by="user1")
        FittingService.fit_well(well_id, force_refit=True, refit_by="user2")

        # Get history
        history = FittingService.get_well_fit_history(well_id)

        # Should have current fit + 2 archives
        assert len(history) == 3

        # Current fit should be first
        assert history[0]['is_current'] is True
        assert history[0]['is_archived'] is False

        # Archives should follow
        assert history[1]['is_archived'] is True
        assert history[2]['is_archived'] is True

    def test_get_well_fit_history_without_current(self, db_session, setup_plate_with_data):
        """T4.9.7: Get archived history only."""
        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Create multiple fits
        FittingService.fit_well(well_id)
        FittingService.fit_well(well_id, force_refit=True)

        # Get history without current
        history = FittingService.get_well_fit_history(well_id, include_current=False)

        # Should have only archived fits
        assert len(history) == 1
        assert all(h['is_archived'] for h in history)

    def test_get_archive_count(self, db_session, setup_plate_with_data):
        """T4.9.8: Count archived fits for a well."""
        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Initially no archives
        assert FittingService.get_archive_count(well_id) == 0

        # Create fits
        FittingService.fit_well(well_id)
        assert FittingService.get_archive_count(well_id) == 0

        FittingService.fit_well(well_id, force_refit=True)
        assert FittingService.get_archive_count(well_id) == 1

        FittingService.fit_well(well_id, force_refit=True)
        assert FittingService.get_archive_count(well_id) == 2

    def test_archive_from_fit_result_method(self, db_session, setup_plate_with_data):
        """T4.9.9: FitResultArchive.from_fit_result class method."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Create a fit
        fit_result = FittingService.fit_well(well_id)

        # Use class method to create archive
        archive = FitResultArchive.from_fit_result(
            fit_result,
            superseded_by="manual_test",
            superseded_reason="Testing class method"
        )

        assert archive.well_id == fit_result.well_id
        assert archive.original_fit_id == fit_result.id
        assert archive.f_max == fit_result.f_max
        assert archive.r_squared == fit_result.r_squared
        assert archive.superseded_by == "manual_test"
        assert archive.superseded_reason == "Testing class method"

    def test_archive_is_good_fit_property(self, db_session, setup_plate_with_data):
        """T4.9.10: Archive is_good_fit property works."""
        from app.models.fit_result import FitResultArchive

        well_id = setup_plate_with_data["wells"]["wt"]["well"].id

        # Create and archive a good fit
        FittingService.fit_well(well_id)
        FittingService.fit_well(well_id, force_refit=True)

        archive = FitResultArchive.query.filter_by(well_id=well_id).first()

        # The WT fit should be a good fit (converged, R² > 0.9)
        assert archive.converged is True
        assert archive.r_squared > 0.9
        assert archive.is_good_fit is True
