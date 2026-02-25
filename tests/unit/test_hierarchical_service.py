"""
Tests for HierarchicalService — service-layer methods.

Covers gaps not tested in test_hierarchical.py:
- AnalysisVersion creation (edge cases)
- get_fold_change_data (filtering, family, ligand conditions)
- get_available_families / get_available_ligand_conditions
- run_analysis (mocked MCMC/Frequentist)
- _store_bayesian_results / _store_frequentist_results
- MCMC checkpoint management via the service layer
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import Project, Construct
from app.models.project import PlateFormat
from app.models.plate_layout import PlateLayout
from app.models.experiment import (
    ExperimentalSession, Plate, Well, FitStatus, QCStatus,
)
from app.models.fit_result import FitResult, FoldChange
from app.models.analysis_version import (
    AnalysisVersion, AnalysisStatus,
    HierarchicalResult, ParameterCorrelation,
    MCMCCheckpoint, CheckpointStatus,
)
from app.services.hierarchical_service import (
    HierarchicalService, HierarchicalAnalysisError, AnalysisConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_layout(project_id: int) -> PlateLayout:
    """Create a minimal PlateLayout for Plate FK satisfaction."""
    layout = PlateLayout(
        project_id=project_id,
        name="helper-layout",
        plate_format="384",
        rows=16,
        cols=24,
    )
    db.session.add(layout)
    db.session.flush()
    return layout


def _create_project_with_fold_changes(
    n_mutants: int = 2,
    n_fc_per_mutant: int = 3,
    with_ligand: bool = False,
    family: str = "TestFamily",
    qc_status: QCStatus = QCStatus.APPROVED,
):
    """
    Build a project populated with constructs, sessions, plates, wells,
    fit results, and fold changes suitable for hierarchical analysis.

    Returns (project, wt, mutants, session, plate).
    """
    project = Project(
        name="Test Project",
        plate_format=PlateFormat.PLATE_384,
        precision_target=0.2,
    )
    db.session.add(project)
    db.session.flush()

    layout = _make_layout(project.id)

    wt = Construct(
        project_id=project.id,
        identifier="WT-1",
        family=family,
        is_wildtype=True,
    )
    db.session.add(wt)
    db.session.flush()

    mutants = []
    for i in range(n_mutants):
        mut = Construct(
            project_id=project.id,
            identifier=f"MUT-{i + 1}",
            family=family,
        )
        db.session.add(mut)
        db.session.flush()
        mutants.append(mut)

    session = ExperimentalSession(
        project_id=project.id,
        date=date.today(),
        batch_identifier="Batch-001",
        qc_status=qc_status,
    )
    db.session.add(session)
    db.session.flush()

    plate = Plate(
        session_id=session.id,
        layout_id=layout.id,
        plate_number=1,
    )
    db.session.add(plate)
    db.session.flush()

    # WT wells with fit results
    wt_wells = []
    for i in range(n_fc_per_mutant):
        w = Well(
            plate_id=plate.id,
            position=f"A{i + 1}",
            construct_id=wt.id,
            fit_status=FitStatus.SUCCESS,
        )
        db.session.add(w)
        db.session.flush()
        fr = FitResult(
            well_id=w.id,
            f_max=500.0, f_max_se=25.0,
            k_obs=0.10, k_obs_se=0.01,
            f_baseline=100.0, f_baseline_se=10.0,
            r_squared=0.98, converged=True,
            model_type="delayed_exponential",
        )
        db.session.add(fr)
        wt_wells.append(w)

    # Mutant wells with fits and fold changes
    for mut_idx, mut in enumerate(mutants):
        for i in range(n_fc_per_mutant):
            fmax = 1000.0 + mut_idx * 100
            w = Well(
                plate_id=plate.id,
                position=f"{chr(66 + mut_idx)}{i + 1}",
                construct_id=mut.id,
                fit_status=FitStatus.SUCCESS,
            )
            db.session.add(w)
            db.session.flush()
            fr = FitResult(
                well_id=w.id,
                f_max=fmax, f_max_se=50.0,
                k_obs=0.12, k_obs_se=0.01,
                f_baseline=100.0, f_baseline_se=10.0,
                r_squared=0.97, converged=True,
                model_type="delayed_exponential",
            )
            db.session.add(fr)

            fc_val = fmax / 500.0
            ligand_cond = None
            comp_type = "within_condition"
            if with_ligand:
                ligand_cond = "+Lig" if i % 2 == 0 else "-Lig"

            fc = FoldChange(
                test_well_id=w.id,
                control_well_id=wt_wells[i % len(wt_wells)].id,
                fc_fmax=fc_val,
                log_fc_fmax=float(np.log(fc_val)),
                fc_fmax_se=0.2,
                comparison_type=comp_type,
                ligand_condition=ligand_cond,
            )
            db.session.add(fc)

    db.session.commit()
    return project, wt, mutants, session, plate


# ===========================================================================
# TestAnalysisVersionCreation
# ===========================================================================

class TestAnalysisVersionCreation:
    """Tests for HierarchicalService.create_analysis_version edge cases."""

    def test_create_analysis_version_fields(self, db_session):
        """Version record has correct fields from config."""
        project = Project(name="P1", plate_format=PlateFormat.PLATE_384, precision_target=0.2)
        db.session.add(project)
        db.session.commit()

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=500, mcmc_tune=250, mcmc_thin=3, random_seed=42
        )
        version = HierarchicalService.create_analysis_version(
            project_id=project.id, name="v1", config=config, description="first run"
        )

        assert version.id is not None
        assert version.project_id == project.id
        assert version.name == "v1"
        assert version.description == "first run"
        assert version.mcmc_chains == 2
        assert version.mcmc_draws == 500
        assert version.mcmc_tune == 250
        assert version.mcmc_thin == 3
        assert version.random_seed == 42
        assert version.model_type == "delayed_exponential"

    def test_create_version_duplicate_name(self, db_session):
        """Duplicate names within a project are rejected."""
        project = Project(name="P2", plate_format=PlateFormat.PLATE_384, precision_target=0.2)
        db.session.add(project)
        db.session.commit()

        config = AnalysisConfig()
        HierarchicalService.create_analysis_version(project.id, "dup", config)

        with pytest.raises(HierarchicalAnalysisError, match="already exists"):
            HierarchicalService.create_analysis_version(project.id, "dup", config)

    def test_create_version_invalid_project(self, db_session):
        """Nonexistent project raises error."""
        with pytest.raises(HierarchicalAnalysisError, match="not found"):
            HierarchicalService.create_analysis_version(
                project_id=999999, name="nope", config=AnalysisConfig()
            )

    def test_version_initial_status(self, db_session):
        """Newly created version has RUNNING status."""
        project = Project(name="P3", plate_format=PlateFormat.PLATE_384, precision_target=0.2)
        db.session.add(project)
        db.session.commit()

        version = HierarchicalService.create_analysis_version(
            project.id, "run", AnalysisConfig()
        )
        assert version.status == AnalysisStatus.RUNNING
        assert version.started_at is not None
        assert version.completed_at is None

    def test_version_config_from_project(self, db_session):
        """AnalysisConfig.from_project() picks up meaningful_fc_threshold."""
        project = Project(
            name="P4", plate_format=PlateFormat.PLATE_384, precision_target=0.2
        )
        project.meaningful_fc_threshold = 1.5
        db.session.add(project)
        db.session.commit()

        config = AnalysisConfig.from_project(project)
        assert config.meaningful_threshold == pytest.approx(np.log(1.5), rel=1e-6)


# ===========================================================================
# TestGetFoldChangeData
# ===========================================================================

class TestGetFoldChangeData:
    """Tests for HierarchicalService.get_fold_change_data."""

    def test_get_fold_change_data_basic(self, db_session):
        """Returns DataFrame with required columns."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()

        df = HierarchicalService.get_fold_change_data(project.id)

        assert isinstance(df, pd.DataFrame)
        for col in (
            "construct_id", "session_id", "plate_id",
            "log_fc_fmax", "ligand_condition", "comparison_type", "family",
        ):
            assert col in df.columns, f"Missing column: {col}"

        # Should have n_mutants * n_fc_per_mutant rows
        assert len(df) == 2 * 3

    def test_get_fold_change_data_empty(self, db_session):
        """Raises error when no fold change data exists."""
        project = Project(name="empty", plate_format=PlateFormat.PLATE_384, precision_target=0.2)
        db.session.add(project)
        db.session.commit()

        with pytest.raises(HierarchicalAnalysisError, match="No fold change data"):
            HierarchicalService.get_fold_change_data(project.id)

    def test_get_fold_change_data_filters_rejected_sessions(self, db_session):
        """Data from QC-rejected sessions is excluded."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            qc_status=QCStatus.REJECTED,
        )

        with pytest.raises(HierarchicalAnalysisError, match="No fold change data"):
            HierarchicalService.get_fold_change_data(project.id)

    def test_get_fold_change_data_ligand_filter(self, db_session):
        """Filters by ligand_condition."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            with_ligand=True,
        )

        df_plus = HierarchicalService.get_fold_change_data(
            project.id, ligand_condition="+Lig"
        )
        df_minus = HierarchicalService.get_fold_change_data(
            project.id, ligand_condition="-Lig"
        )

        assert all(df_plus["ligand_condition"] == "+Lig")
        assert all(df_minus["ligand_condition"] == "-Lig")
        assert len(df_plus) + len(df_minus) == 2 * 3

    def test_get_fold_change_data_comparison_type_filter(self, db_session):
        """Filters by comparison_type."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()

        df = HierarchicalService.get_fold_change_data(
            project.id, comparison_type="within_condition"
        )
        assert all(df["comparison_type"] == "within_condition")

        # Non-matching comparison_type should raise
        with pytest.raises(HierarchicalAnalysisError):
            HierarchicalService.get_fold_change_data(
                project.id, comparison_type="ligand_effect"
            )

    def test_get_fold_change_data_includes_family(self, db_session):
        """Family column populated from Construct."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            family="MyFamily",
        )

        df = HierarchicalService.get_fold_change_data(project.id)
        assert all(df["family"] == "MyFamily")


# ===========================================================================
# TestGetAvailableFamilies
# ===========================================================================

class TestGetAvailableFamilies:
    """Tests for HierarchicalService.get_available_families."""

    def test_get_available_families(self, db_session):
        """Returns family names for constructs in the project."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            family="FamilyA",
        )
        families = HierarchicalService.get_available_families(project.id)
        assert "FamilyA" in families

    def test_get_available_families_excludes_universal(self, db_session):
        """The 'universal' family is excluded."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            family="universal",
        )
        # Mark construct as unregulated so the filter works
        for mut in mutants:
            mut.is_unregulated = True
        db.session.commit()

        families = HierarchicalService.get_available_families(project.id)
        assert "universal" not in families

    def test_get_available_families_empty(self, db_session):
        """Returns empty list when no fold change data exists."""
        project = Project(name="nofams", plate_format=PlateFormat.PLATE_384, precision_target=0.2)
        db.session.add(project)
        db.session.commit()

        families = HierarchicalService.get_available_families(project.id)
        assert families == []


# ===========================================================================
# TestGetAvailableLigandConditions
# ===========================================================================

class TestGetAvailableLigandConditions:
    """Tests for HierarchicalService.get_available_ligand_conditions."""

    def test_get_ligand_conditions(self, db_session):
        """Returns unique ligand conditions present in fold changes."""
        project, *_ = _create_project_with_fold_changes(with_ligand=True)

        conditions = HierarchicalService.get_available_ligand_conditions(project.id)
        assert set(conditions) == {"+Lig", "-Lig"}

    def test_get_ligand_conditions_empty(self, db_session):
        """Returns empty list when no ligand conditions are set."""
        project, *_ = _create_project_with_fold_changes(with_ligand=False)

        conditions = HierarchicalService.get_available_ligand_conditions(project.id)
        assert conditions == []


# ===========================================================================
# TestRunAnalysis (mocked MCMC / frequentist)
# ===========================================================================

def _build_mock_bayesian_result(construct_ids):
    """Build a minimal BayesianResult-like mock for store tests."""
    from app.analysis.bayesian import BayesianResult, PosteriorSummary
    from app.analysis.variance_components import VarianceComponents
    from app.analysis.data_structure import ModelMetadata, ModelTier

    result = BayesianResult()
    for cid in construct_ids:
        result.posteriors[cid] = {
            "log_fc_fmax": PosteriorSummary(
                mean=0.5, std=0.1, ci_lower=0.3, ci_upper=0.7,
                n_samples=1000, r_hat=1.01, ess_bulk=800, ess_tail=700,
                prob_positive=0.95, prob_meaningful=0.80,
            ),
        }
        result.correlations[cid] = {("log_fc_fmax", "log_fc_kobs"): 0.45}

    result.variance_components["log_fc_fmax"] = VarianceComponents(
        var_session=0.01, var_plate=0.005, var_residual=0.02, var_total=0.035,
    )
    result.model_metadata = ModelMetadata(
        tier=ModelTier.TIER_1_RESIDUAL_ONLY,
        n_sessions=1, n_plates=1, max_plates_per_session=1,
        estimates_session_variance=False, estimates_plate_variance=False,
    )
    result.model_residuals = {"log_fc_fmax": [0.01, -0.02, 0.005]}
    result.trace_path = "/tmp/mock_trace.nc"
    return result


def _build_mock_frequentist_result(construct_ids):
    """Build a minimal FrequentistResult-like mock for store tests."""
    from app.analysis.frequentist import FrequentistResult, FrequentistEstimate
    from app.analysis.variance_components import FrequentistVarianceComponents

    result = FrequentistResult()
    for cid in construct_ids:
        result.estimates[cid] = {
            "log_fc_fmax": FrequentistEstimate(
                mean=0.48, std=0.12, ci_lower=0.25, ci_upper=0.71,
            ),
        }

    result.variance_components["log_fc_fmax"] = FrequentistVarianceComponents(
        var_session=0.01, var_plate=0.005, var_residual=0.02, var_total=0.035,
    )
    result.warnings = ["Singular fit warning"]
    return result


def _naive_utcnow(*args, **kwargs):
    """Return a naive UTC datetime, avoiding SQLite timezone round-trip issues.

    SQLite strips timezone info on storage.  When ``started_at`` (written with
    ``datetime.now(timezone.utc)``) round-trips through SQLite it comes back
    timezone-naive, while a freshly-created ``completed_at`` is timezone-aware.
    Subtracting the two raises ``TypeError``.  In production this is harmless
    because the worker keeps the version object in-session, but in tests the
    commit in ``create_analysis_version`` causes SQLAlchemy to expire/re-load
    the attribute from SQLite.  We patch ``datetime`` in the service module to
    use naive UTC datetimes so all timestamps are consistent.
    """
    return datetime.utcnow()


class _NaiveDatetime(datetime):
    """datetime subclass whose ``now()`` always returns naive UTC."""

    @classmethod
    def now(cls, tz=None):
        return datetime.utcnow()


class TestRunAnalysis:
    """Tests for HierarchicalService.run_analysis with mocked analysis engines."""

    @pytest.fixture(autouse=True)
    def _patch_datetime(self):
        """Ensure all timestamps produced by hierarchical_service are naive UTC."""
        with patch("app.services.hierarchical_service.datetime", _NaiveDatetime):
            yield

    @patch("app.services.hierarchical_service.PYMC_AVAILABLE", True)
    @patch("app.services.hierarchical_service.STATSMODELS_AVAILABLE", True)
    @patch("app.services.hierarchical_service.BayesianHierarchical")
    @patch("app.services.hierarchical_service.FrequentistHierarchical")
    @patch("app.services.hierarchical_service.compare_bayesian_frequentist")
    @patch("app.services.hierarchical_service.ComparisonService", create=True)
    def test_run_analysis_creates_version(
        self, mock_comp_svc, mock_compare, mock_freq_cls, mock_bayes_cls, db_session
    ):
        """run_analysis creates a version record and marks COMPLETED on success."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        mut_ids = [m.id for m in mutants]

        # Wire up bayesian mock
        bayesian_result = _build_mock_bayesian_result(mut_ids)
        mock_bayes_instance = MagicMock()
        mock_bayes_instance.run_analysis.return_value = bayesian_result
        mock_bayes_cls.return_value = mock_bayes_instance

        # Wire up frequentist mock
        freq_result = _build_mock_frequentist_result(mut_ids)
        mock_freq_instance = MagicMock()
        mock_freq_instance.run_analysis.return_value = freq_result
        mock_freq_cls.return_value = mock_freq_instance

        mock_compare.return_value = {
            "overall_agreement": True,
            "max_relative_difference": 0.04,
            "warnings": [],
        }

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=100, mcmc_tune=50,
            run_bayesian=True, run_frequentist=True,
        )
        version = HierarchicalService.run_analysis(
            project_id=project.id,
            version_name="auto-test",
            config=config,
        )

        assert version.status == AnalysisStatus.COMPLETED
        assert version.name == "auto-test"
        assert version.completed_at is not None

    @patch("app.services.hierarchical_service.PYMC_AVAILABLE", True)
    @patch("app.services.hierarchical_service.STATSMODELS_AVAILABLE", False)
    @patch("app.services.hierarchical_service.BayesianHierarchical")
    def test_run_analysis_calls_bayesian(
        self, mock_bayes_cls, db_session
    ):
        """Bayesian module is called when run_bayesian=True."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        mut_ids = [m.id for m in mutants]

        bayesian_result = _build_mock_bayesian_result(mut_ids)
        mock_bayes_instance = MagicMock()
        mock_bayes_instance.run_analysis.return_value = bayesian_result
        mock_bayes_cls.return_value = mock_bayes_instance

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=100, mcmc_tune=50,
            run_bayesian=True, run_frequentist=False,
        )
        version = HierarchicalService.run_analysis(
            project.id, "bayes-only", config=config,
        )

        mock_bayes_instance.run_analysis.assert_called_once()
        assert version.status == AnalysisStatus.COMPLETED

    @patch("app.services.hierarchical_service.PYMC_AVAILABLE", False)
    @patch("app.services.hierarchical_service.STATSMODELS_AVAILABLE", True)
    @patch("app.services.hierarchical_service.FrequentistHierarchical")
    def test_run_analysis_calls_frequentist(
        self, mock_freq_cls, db_session
    ):
        """Frequentist module is called when run_frequentist=True."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        mut_ids = [m.id for m in mutants]

        freq_result = _build_mock_frequentist_result(mut_ids)
        mock_freq_instance = MagicMock()
        mock_freq_instance.run_analysis.return_value = freq_result
        mock_freq_cls.return_value = mock_freq_instance

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=100, mcmc_tune=50,
            run_bayesian=False, run_frequentist=True,
        )
        version = HierarchicalService.run_analysis(
            project.id, "freq-only", config=config,
        )

        mock_freq_instance.run_analysis.assert_called_once()
        assert version.status == AnalysisStatus.COMPLETED

    @patch("app.services.hierarchical_service.PYMC_AVAILABLE", True)
    @patch("app.services.hierarchical_service.STATSMODELS_AVAILABLE", False)
    @patch("app.services.hierarchical_service.BayesianHierarchical")
    def test_run_analysis_handles_failure(
        self, mock_bayes_cls, db_session
    ):
        """Version is marked FAILED when all analysis engines fail."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()

        mock_bayes_instance = MagicMock()
        mock_bayes_instance.run_analysis.side_effect = RuntimeError("MCMC diverged")
        mock_bayes_cls.return_value = mock_bayes_instance

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=100, mcmc_tune=50,
            run_bayesian=True, run_frequentist=False,
        )
        version = HierarchicalService.run_analysis(
            project.id, "fail-test", config=config,
        )

        assert version.status == AnalysisStatus.FAILED
        assert version.error_message is not None

    @patch("app.services.hierarchical_service.PYMC_AVAILABLE", True)
    @patch("app.services.hierarchical_service.STATSMODELS_AVAILABLE", False)
    @patch("app.services.hierarchical_service.BayesianHierarchical")
    def test_run_analysis_progress_callback(
        self, mock_bayes_cls, db_session
    ):
        """Progress callback is invoked at expected stages."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        mut_ids = [m.id for m in mutants]

        bayesian_result = _build_mock_bayesian_result(mut_ids)
        mock_bayes_instance = MagicMock()
        mock_bayes_instance.run_analysis.return_value = bayesian_result
        mock_bayes_cls.return_value = mock_bayes_instance

        progress_calls = []

        def on_progress(stage, prog):
            progress_calls.append((stage, prog))

        config = AnalysisConfig(
            mcmc_chains=2, mcmc_draws=100, mcmc_tune=50,
            run_bayesian=True, run_frequentist=False,
        )
        HierarchicalService.run_analysis(
            project.id, "progress-test", config=config,
            progress_callback=on_progress,
        )

        # Should have at least "Gathering data", a Bayesian stage, "Finalizing", "Complete"
        stages = [s for s, _ in progress_calls]
        assert any("Gathering" in s for s in stages)
        assert any("Bayesian" in s for s in stages)
        assert any("Complete" in s for s in stages)
        # Final progress should be 1.0
        assert progress_calls[-1][1] == pytest.approx(1.0)


# ===========================================================================
# TestResultStorage (_store_bayesian_results / _store_frequentist_results)
# ===========================================================================

class TestResultStorage:
    """Tests for _store_bayesian_results and _store_frequentist_results."""

    def _make_version(self, project_id):
        """Create an AnalysisVersion for storage tests."""
        config = AnalysisConfig()
        return HierarchicalService.create_analysis_version(
            project_id, f"storage-{datetime.now().isoformat()}", config
        )

    def test_store_bayesian_results(self, db_session):
        """Bayesian results stored as HierarchicalResult rows."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        version = self._make_version(project.id)
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(version, result)
        db.session.commit()

        rows = HierarchicalResult.query.filter_by(
            analysis_version_id=version.id, analysis_type="bayesian"
        ).all()

        assert len(rows) == len(mut_ids)  # one per construct per param
        for row in rows:
            assert row.mean == pytest.approx(0.5)
            assert row.parameter_type == "log_fc_fmax"

    def test_store_frequentist_results(self, db_session):
        """Frequentist results stored as HierarchicalResult rows with method='frequentist'."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        version = self._make_version(project.id)
        mut_ids = [m.id for m in mutants]
        result = _build_mock_frequentist_result(mut_ids)

        HierarchicalService._store_frequentist_results(version, result)
        db.session.commit()

        rows = HierarchicalResult.query.filter_by(
            analysis_version_id=version.id, analysis_type="frequentist"
        ).all()

        assert len(rows) == len(mut_ids)
        for row in rows:
            assert row.mean == pytest.approx(0.48)

    def test_stored_results_have_correct_fields(self, db_session):
        """Verify all fields are populated on stored Bayesian results."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            n_mutants=1, n_fc_per_mutant=2,
        )
        version = self._make_version(project.id)
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(version, result)
        db.session.commit()

        row = HierarchicalResult.query.filter_by(
            analysis_version_id=version.id, analysis_type="bayesian"
        ).first()

        assert row.construct_id == mut_ids[0]
        assert row.std == pytest.approx(0.1)
        assert row.ci_lower == pytest.approx(0.3)
        assert row.ci_upper == pytest.approx(0.7)
        assert row.prob_positive == pytest.approx(0.95)
        assert row.prob_meaningful == pytest.approx(0.80)
        assert row.n_samples == 1000
        assert row.r_hat == pytest.approx(1.01)
        assert row.ess_bulk == pytest.approx(800)
        assert row.ess_tail == pytest.approx(700)
        # Variance components
        assert row.var_session == pytest.approx(0.01)
        assert row.var_plate == pytest.approx(0.005)
        assert row.var_residual == pytest.approx(0.02)

    def test_store_bayesian_correlations(self, db_session):
        """Parameter correlations are stored alongside Bayesian results."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            n_mutants=1, n_fc_per_mutant=2,
        )
        version = self._make_version(project.id)
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(version, result)
        db.session.commit()

        corrs = ParameterCorrelation.query.filter_by(
            analysis_version_id=version.id,
        ).all()

        assert len(corrs) == len(mut_ids)
        assert corrs[0].correlation == pytest.approx(0.45)
        assert corrs[0].parameter_1 == "log_fc_fmax"
        assert corrs[0].parameter_2 == "log_fc_kobs"

    def test_store_results_with_ligand_condition(self, db_session):
        """Ligand condition propagated to HierarchicalResult rows."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes()
        version = self._make_version(project.id)
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(
            version, result, ligand_condition="+Lig"
        )
        db.session.commit()

        rows = HierarchicalResult.query.filter_by(
            analysis_version_id=version.id
        ).all()
        assert all(r.ligand_condition == "+Lig" for r in rows)


# ===========================================================================
# TestCheckpointManagement
# ===========================================================================

class TestCheckpointManagement:
    """Tests for MCMC checkpoint service methods."""

    def _make_project_and_version(self):
        """Helper: project + AnalysisVersion."""
        project = Project(
            name="ckpt-proj", plate_format=PlateFormat.PLATE_384, precision_target=0.2
        )
        db.session.add(project)
        db.session.commit()

        config = AnalysisConfig(mcmc_chains=4, mcmc_draws=2000)
        version = HierarchicalService.create_analysis_version(
            project.id, f"ckpt-{datetime.now().isoformat()}", config
        )
        return project, version

    def test_create_checkpoint(self, db_session):
        """create_mcmc_checkpoint persists a record."""
        project, version = self._make_project_and_version()

        cp = HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=500,
            total_draws=2000,
            checkpoint_path="/tmp/trace_500.nc",
        )

        assert cp.id is not None
        assert cp.draw_idx == 500
        assert cp.total_draws == 2000
        assert cp.status == CheckpointStatus.IN_PROGRESS
        assert cp.is_final is False

    def test_create_final_checkpoint(self, db_session):
        """Final checkpoint has COMPLETED status and is_resumable=True."""
        project, version = self._make_project_and_version()

        cp = HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=2000,
            total_draws=2000,
            checkpoint_path="/tmp/trace_final.nc",
            is_final=True,
        )

        assert cp.status == CheckpointStatus.COMPLETED
        assert cp.is_final is True
        assert cp.is_resumable is True

    def test_resume_from_checkpoint(self, db_session):
        """Checkpoint data is retrievable via get_resumable_checkpoint."""
        project, version = self._make_project_and_version()

        HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=2000,
            total_draws=2000,
            checkpoint_path="/tmp/resume_trace.nc",
            is_final=True,
        )
        db.session.commit()

        cp = HierarchicalService.get_resumable_checkpoint(version.id)
        assert cp is not None
        assert cp.checkpoint_path == "/tmp/resume_trace.nc"
        assert cp.is_resumable is True

    def test_cleanup_old_checkpoints(self, db_session):
        """cleanup_checkpoints removes non-final checkpoint DB records."""
        project, version = self._make_project_and_version()

        # Intermediate checkpoint
        HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=500,
            total_draws=2000,
            checkpoint_path="/tmp/ckpt_500.nc",
        )
        # Final checkpoint
        HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=2000,
            total_draws=2000,
            checkpoint_path="/tmp/ckpt_final.nc",
            is_final=True,
        )
        db.session.commit()

        before = MCMCCheckpoint.query.filter_by(
            analysis_version_id=version.id
        ).count()
        assert before == 2

        deleted = MCMCCheckpoint.cleanup_for_version(version.id)
        db.session.commit()

        assert deleted == 1  # only the non-final one removed
        remaining = MCMCCheckpoint.query.filter_by(
            analysis_version_id=version.id
        ).all()
        assert len(remaining) == 1
        assert remaining[0].is_final is True

    def test_checkpoint_status_transitions(self, db_session):
        """Checkpoint statuses tracked correctly across the lifecycle."""
        project, version = self._make_project_and_version()

        # Create error checkpoint via service
        err_cp = HierarchicalService.create_error_checkpoint(
            version=version,
            draw_idx=150,
            error_message="Sampling diverged",
            error_traceback="Traceback...",
        )
        db.session.commit()

        assert err_cp.status == CheckpointStatus.ERROR
        assert err_cp.error_message == "Sampling diverged"
        assert err_cp.is_resumable is False

        status = HierarchicalService.get_checkpoint_status(version.id)
        assert status["has_error"] is True
        assert status["error_message"] == "Sampling diverged"


# ===========================================================================
# TestAnalysisSummary
# ===========================================================================

class TestAnalysisSummary:
    """Tests for get_analysis_summary and get_construct_results."""

    def test_get_analysis_summary(self, db_session):
        """Summary includes correct counts and structure."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            n_mutants=1, n_fc_per_mutant=2,
        )
        config = AnalysisConfig()
        version = HierarchicalService.create_analysis_version(
            project.id, "summary-test", config,
        )
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(version, result)
        version.status = AnalysisStatus.COMPLETED
        db.session.commit()

        summary = HierarchicalService.get_analysis_summary(version.id)

        assert summary["version_id"] == version.id
        assert summary["name"] == "summary-test"
        assert summary["status"] == "completed"
        assert summary["n_constructs"] == 1
        assert summary["bayesian"]["available"] is True
        assert summary["bayesian"]["n_results"] == 1
        assert summary["frequentist"]["available"] is False

    def test_get_construct_results(self, db_session):
        """Construct-level results returned with Bayesian data."""
        project, wt, mutants, session, plate = _create_project_with_fold_changes(
            n_mutants=1, n_fc_per_mutant=2,
        )
        config = AnalysisConfig()
        version = HierarchicalService.create_analysis_version(
            project.id, "construct-test", config,
        )
        mut_ids = [m.id for m in mutants]
        result = _build_mock_bayesian_result(mut_ids)

        HierarchicalService._store_bayesian_results(version, result)
        db.session.commit()

        cr = HierarchicalService.get_construct_results(version.id, mut_ids[0])

        assert cr["construct_id"] == mut_ids[0]
        assert "log_fc_fmax" in cr["bayesian"]
        assert cr["bayesian"]["log_fc_fmax"]["mean"] == pytest.approx(0.5)
        assert cr["bayesian"]["log_fc_fmax"]["prob_positive"] == pytest.approx(0.95)

    def test_get_analysis_summary_nonexistent(self, db_session):
        """Summary raises error for nonexistent version."""
        with pytest.raises(HierarchicalAnalysisError, match="not found"):
            HierarchicalService.get_analysis_summary(999999)
