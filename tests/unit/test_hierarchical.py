"""
Tests for hierarchical modeling.

Phase 5: Advanced Statistics (Hierarchical Modeling)
T5.1-T5.20: Bayesian and frequentist analysis tests
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import Project, Construct
from app.models.project import PlateFormat
from app.models.experiment import ExperimentalSession, Plate, Well, FitStatus
from app.models.plate_layout import WellType
from app.models.fit_result import FitResult, FoldChange
from app.models.analysis_version import AnalysisVersion, AnalysisStatus, HierarchicalResult
from app.services import (
    ProjectService, ConstructService, FittingService, PlateLayoutService
)


class TestBayesianModule:
    """Tests for Bayesian analysis module."""

    def test_pymc_availability_check(self):
        """Test PyMC availability check function."""
        from app.analysis.bayesian import check_pymc_available, PYMC_AVAILABLE
        result = check_pymc_available()
        assert result == PYMC_AVAILABLE

    def test_posterior_summary_dataclass(self):
        """T5.7: Posterior summary data structure."""
        from app.analysis.bayesian import PosteriorSummary

        summary = PosteriorSummary(
            mean=0.5,
            std=0.1,
            ci_lower=0.3,
            ci_upper=0.7,
            ci_level=0.95,
            n_samples=1000,
            r_hat=1.01,
            ess_bulk=800.0,
            ess_tail=750.0,
            prob_positive=0.95,
            prob_meaningful=0.85
        )

        assert summary.mean == 0.5
        assert summary.ci_level == 0.95
        assert summary.prob_positive == 0.95

    def test_variance_components_dataclass(self):
        """T5.10: Variance components structure."""
        from app.analysis.bayesian import VarianceComponents

        vc = VarianceComponents(
            var_session=0.05,
            var_plate=0.02,
            var_residual=0.03,
            var_total=0.10
        )

        assert vc.icc_session == pytest.approx(0.5)
        assert vc.icc_plate == pytest.approx(0.2)
        assert vc.fraction_residual == pytest.approx(0.3)

    def test_bayesian_result_dataclass(self):
        """Test BayesianResult data structure."""
        from app.analysis.bayesian import BayesianResult

        result = BayesianResult(
            n_chains=4,
            n_draws=2000,
            n_tune=1000,
            thin_factor=5
        )

        assert result.n_chains == 4
        assert result.n_draws == 2000
        assert len(result.posteriors) == 0
        assert len(result.warnings) == 0


class TestFrequentistModule:
    """Tests for frequentist analysis module."""

    def test_statsmodels_availability_check(self):
        """Test statsmodels availability check function."""
        from app.analysis.frequentist import check_statsmodels_available, STATSMODELS_AVAILABLE
        result = check_statsmodels_available()
        assert result == STATSMODELS_AVAILABLE

    def test_frequentist_estimate_dataclass(self):
        """T5.11: Frequentist estimate structure."""
        from app.analysis.frequentist import FrequentistEstimate

        estimate = FrequentistEstimate(
            mean=0.5,
            std=0.1,
            ci_lower=0.3,
            ci_upper=0.7,
            ci_level=0.95,
            p_value=0.001,
            t_statistic=3.5
        )

        assert estimate.mean == 0.5
        assert estimate.p_value == 0.001

    def test_frequentist_variance_components(self):
        """T5.10: Frequentist variance components."""
        from app.analysis.frequentist import FrequentistVarianceComponents

        vc = FrequentistVarianceComponents(
            var_session=0.04,
            var_plate=0.02,
            var_residual=0.04,
            var_total=0.10
        )

        assert vc.icc_session == pytest.approx(0.4)
        assert vc.icc_plate == pytest.approx(0.2)

    def test_frequentist_result_dataclass(self):
        """Test FrequentistResult structure."""
        from app.analysis.frequentist import FrequentistResult

        result = FrequentistResult()

        assert len(result.estimates) == 0
        assert len(result.variance_components) == 0
        assert len(result.warnings) == 0


class TestBayesianFrequentistComparison:
    """Tests for comparing Bayesian and frequentist results."""

    def test_comparison_function(self):
        """T5.12: Bayesian-Frequentist comparison."""
        from app.analysis.bayesian import BayesianResult, PosteriorSummary
        from app.analysis.frequentist import FrequentistResult, FrequentistEstimate, compare_bayesian_frequentist

        # Create mock Bayesian result
        bayesian = BayesianResult()
        bayesian.posteriors[1] = {
            'log_fc_fmax': PosteriorSummary(
                mean=0.5, std=0.1, ci_lower=0.3, ci_upper=0.7
            )
        }

        # Create mock frequentist result with similar values
        frequentist = FrequentistResult()
        frequentist.estimates[1] = {
            'log_fc_fmax': FrequentistEstimate(
                mean=0.52, std=0.11, ci_lower=0.31, ci_upper=0.73
            )
        }

        comparison = compare_bayesian_frequentist(bayesian, frequentist, tolerance=0.10)

        assert comparison['overall_agreement'] is True
        assert comparison['max_relative_difference'] < 0.10

    def test_comparison_detects_divergence(self):
        """T5.13: Divergence detection when >10% difference."""
        from app.analysis.bayesian import BayesianResult, PosteriorSummary
        from app.analysis.frequentist import FrequentistResult, FrequentistEstimate, compare_bayesian_frequentist

        # Create divergent results
        bayesian = BayesianResult()
        bayesian.posteriors[1] = {
            'log_fc_fmax': PosteriorSummary(
                mean=0.5, std=0.1, ci_lower=0.3, ci_upper=0.7
            )
        }

        frequentist = FrequentistResult()
        frequentist.estimates[1] = {
            'log_fc_fmax': FrequentistEstimate(
                mean=0.7, std=0.1, ci_lower=0.5, ci_upper=0.9
            )
        }

        comparison = compare_bayesian_frequentist(bayesian, frequentist, tolerance=0.10)

        assert comparison['overall_agreement'] is False
        assert comparison['max_relative_difference'] > 0.10
        assert len(comparison['warnings']) > 0


class TestFrequentistDataPreparation:
    """Tests for frequentist data preparation."""

    def test_prepare_data(self):
        """Test data preparation for REML."""
        from app.analysis.frequentist import FrequentistHierarchical, STATSMODELS_AVAILABLE

        if not STATSMODELS_AVAILABLE:
            pytest.skip("statsmodels not available")

        freq = FrequentistHierarchical()

        df = pd.DataFrame({
            'construct_id': [1, 1, 2, 2, 1, 2],
            'session_id': [1, 1, 1, 1, 2, 2],
            'plate_id': [1, 2, 1, 2, 3, 3],
            'log_fc_fmax': [0.5, 0.6, 1.0, 1.1, 0.55, 1.05],
            'log_fc_kobs': [0.1, 0.15, 0.2, 0.25, 0.12, 0.22]
        })

        data = freq.prepare_data(df)

        assert 'df' in data
        assert 'params' in data
        assert 'log_fc_fmax' in data['params']
        assert 'log_fc_kobs' in data['params']
        assert data['n_constructs'] == 2


class TestHierarchicalService:
    """Tests for hierarchical service with database."""

    @pytest.fixture
    def setup_analysis_data(self, db_session):
        """Create test data for hierarchical analysis."""
        # Create project
        project = ProjectService.create_project(
            name="Hierarchical Test Project",
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

        mutant = ConstructService.create_construct(
            project_id=project.id,
            identifier="Mutant",
            family="Tbox1",
            username="testuser"
        )
        ConstructService.publish_construct(mutant.id, "testuser")

        # Create plate layout
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
        wt_well = Well(
            plate_id=plate.id,
            position="A1",
            construct_id=wt.id,
            well_type=WellType.SAMPLE,
            fit_status=FitStatus.SUCCESS
        )
        db.session.add(wt_well)
        db.session.flush()

        wt_fit = FitResult(
            well_id=wt_well.id,
            model_type="delayed_exponential",
            f_baseline=100.0,
            f_max=500.0,
            k_obs=0.1,
            t_lag=5.0,
            r_squared=0.98,
            converged=True
        )
        db.session.add(wt_fit)

        mutant_well = Well(
            plate_id=plate.id,
            position="A2",
            construct_id=mutant.id,
            well_type=WellType.SAMPLE,
            fit_status=FitStatus.SUCCESS
        )
        db.session.add(mutant_well)
        db.session.flush()

        mutant_fit = FitResult(
            well_id=mutant_well.id,
            model_type="delayed_exponential",
            f_baseline=100.0,
            f_max=1000.0,  # 2x WT
            k_obs=0.12,
            t_lag=4.0,
            r_squared=0.97,
            converged=True
        )
        db.session.add(mutant_fit)

        # Create fold change
        fc = FoldChange(
            test_well_id=mutant_well.id,
            control_well_id=wt_well.id,
            fc_fmax=2.0,
            log_fc_fmax=1.0,
            fc_kobs=1.2,
            log_fc_kobs=0.26
        )
        db.session.add(fc)
        db.session.commit()

        return {
            'project_id': project.id,
            'wt_id': wt.id,
            'mutant_id': mutant.id,
            'plate_id': plate.id,
            'session_id': session.id
        }

    def test_create_analysis_version(self, db_session, setup_analysis_data):
        """Test creating analysis version."""
        from app.services.hierarchical_service import HierarchicalService, AnalysisConfig

        config = AnalysisConfig(
            mcmc_chains=2,
            mcmc_draws=100,
            mcmc_tune=50,
            run_bayesian=False,  # Skip for test
            run_frequentist=False
        )

        version = HierarchicalService.create_analysis_version(
            project_id=setup_analysis_data['project_id'],
            name="Test Analysis v1",
            config=config,
            description="Test analysis"
        )

        assert version.id is not None
        assert version.name == "Test Analysis v1"
        assert version.status == AnalysisStatus.RUNNING
        assert version.mcmc_chains == 2

    def test_duplicate_version_name_rejected(self, db_session, setup_analysis_data):
        """Test that duplicate version names are rejected."""
        from app.services.hierarchical_service import HierarchicalService, HierarchicalAnalysisError, AnalysisConfig

        config = AnalysisConfig(run_bayesian=False, run_frequentist=False)

        HierarchicalService.create_analysis_version(
            project_id=setup_analysis_data['project_id'],
            name="Duplicate Name",
            config=config
        )

        with pytest.raises(HierarchicalAnalysisError, match="already exists"):
            HierarchicalService.create_analysis_version(
                project_id=setup_analysis_data['project_id'],
                name="Duplicate Name",
                config=config
            )

    def test_list_versions(self, db_session, setup_analysis_data):
        """Test listing analysis versions."""
        from app.services.hierarchical_service import HierarchicalService, AnalysisConfig

        config = AnalysisConfig(run_bayesian=False, run_frequentist=False)

        HierarchicalService.create_analysis_version(
            setup_analysis_data['project_id'], "Version 1", config
        )
        HierarchicalService.create_analysis_version(
            setup_analysis_data['project_id'], "Version 2", config
        )

        versions = HierarchicalService.list_versions(setup_analysis_data['project_id'])

        assert len(versions) >= 2
        assert any(v['name'] == "Version 1" for v in versions)
        assert any(v['name'] == "Version 2" for v in versions)

    def test_delete_version(self, db_session, setup_analysis_data):
        """Test deleting analysis version."""
        from app.services.hierarchical_service import HierarchicalService, AnalysisConfig

        config = AnalysisConfig(run_bayesian=False, run_frequentist=False)

        version = HierarchicalService.create_analysis_version(
            setup_analysis_data['project_id'], "To Delete", config
        )
        version_id = version.id

        result = HierarchicalService.delete_version(version_id)
        assert result is True

        # Should be gone
        assert AnalysisVersion.query.get(version_id) is None

    def test_delete_nonexistent_version(self, db_session):
        """Test deleting nonexistent version returns False."""
        from app.services.hierarchical_service import HierarchicalService

        result = HierarchicalService.delete_version(999999)
        assert result is False


class TestAnalysisConfig:
    """Tests for AnalysisConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from app.services.hierarchical_service import AnalysisConfig

        config = AnalysisConfig()

        assert config.mcmc_chains == 4
        assert config.mcmc_draws == 2000
        assert config.mcmc_tune == 1000
        assert config.mcmc_thin == 5
        assert config.run_bayesian is True
        assert config.run_frequentist is True
        assert config.ci_level == 0.95

    def test_custom_config(self):
        """Test custom configuration."""
        from app.services.hierarchical_service import AnalysisConfig

        config = AnalysisConfig(
            mcmc_chains=2,
            mcmc_draws=500,
            run_bayesian=False,
            meaningful_threshold=0.2
        )

        assert config.mcmc_chains == 2
        assert config.mcmc_draws == 500
        assert config.run_bayesian is False
        assert config.meaningful_threshold == 0.2


class TestProbabilityCalculations:
    """Tests for probability calculations (T5.9)."""

    def test_probability_of_direction_high(self):
        """P(FC > 0) when effect is clearly positive."""
        from app.analysis.bayesian import PosteriorSummary

        # Simulate result where 95% of samples are positive
        summary = PosteriorSummary(
            mean=0.5,
            std=0.15,
            ci_lower=0.2,
            ci_upper=0.8,
            prob_positive=0.95
        )

        assert summary.prob_positive > 0.9

    def test_probability_of_direction_low(self):
        """P(FC > 0) when effect is clearly negative."""
        from app.analysis.bayesian import PosteriorSummary

        summary = PosteriorSummary(
            mean=-0.5,
            std=0.15,
            ci_lower=-0.8,
            ci_upper=-0.2,
            prob_positive=0.05
        )

        assert summary.prob_positive < 0.1

    def test_probability_of_direction_uncertain(self):
        """P(FC > 0) when effect is uncertain."""
        from app.analysis.bayesian import PosteriorSummary

        summary = PosteriorSummary(
            mean=0.05,
            std=0.2,
            ci_lower=-0.35,
            ci_upper=0.45,
            prob_positive=0.55
        )

        assert 0.4 < summary.prob_positive < 0.6


class TestEdgeCases:
    """Edge case tests (T5.16-T5.20)."""

    def test_zero_variance_components(self):
        """T5.17: Handle zero random effect variance."""
        from app.analysis.bayesian import VarianceComponents

        # All variance at residual level
        vc = VarianceComponents(
            var_session=0.0,
            var_plate=0.0,
            var_residual=0.1,
            var_total=0.1
        )

        assert vc.icc_session == 0.0
        assert vc.icc_plate == 0.0
        assert vc.fraction_residual == 1.0

    def test_variance_components_total_zero(self):
        """Handle edge case of zero total variance."""
        from app.analysis.bayesian import VarianceComponents

        vc = VarianceComponents(
            var_session=0.0,
            var_plate=0.0,
            var_residual=0.0,
            var_total=0.0
        )

        # Should not raise division by zero
        assert vc.icc_session is None
        assert vc.icc_plate is None
        assert vc.fraction_residual == 0.0


class TestMCMCCheckpoint:
    """Tests for MCMC Checkpoint functionality (PRD F11.4-F11.5)."""

    def test_checkpoint_model_creation(self, db_session):
        """T5.21: MCMCCheckpoint model creation."""
        from app.models.analysis_version import MCMCCheckpoint, CheckpointStatus

        checkpoint = MCMCCheckpoint.create_checkpoint(
            analysis_version_id=1,
            draw_idx=500,
            total_draws=2000,
            checkpoint_path="/tmp/trace.nc",
            config_path="/tmp/config.json",
            chain_idx=0,
            total_chains=4,
            is_final=False,
            status=CheckpointStatus.IN_PROGRESS
        )

        assert checkpoint.draw_idx == 500
        assert checkpoint.total_draws == 2000
        assert checkpoint.progress_fraction == 0.25
        assert checkpoint.is_resumable is False

    def test_checkpoint_final_status(self, db_session):
        """T5.22: Final checkpoint is resumable."""
        from app.models.analysis_version import MCMCCheckpoint, CheckpointStatus

        checkpoint = MCMCCheckpoint.create_checkpoint(
            analysis_version_id=1,
            draw_idx=2000,
            total_draws=2000,
            checkpoint_path="/tmp/trace.nc",
            is_final=True,
            status=CheckpointStatus.COMPLETED
        )

        assert checkpoint.progress_fraction == 1.0
        assert checkpoint.is_final is True
        assert checkpoint.is_resumable is True

    def test_error_checkpoint_creation(self, db_session):
        """T5.23: Error checkpoint for debugging (F11.4)."""
        from app.models.analysis_version import MCMCCheckpoint, CheckpointStatus

        checkpoint = MCMCCheckpoint.create_error_checkpoint(
            analysis_version_id=1,
            draw_idx=750,
            total_draws=2000,
            checkpoint_path="/tmp/error.json",
            error_message="Sampling diverged",
            error_traceback="Traceback..."
        )

        assert checkpoint.status == CheckpointStatus.ERROR
        assert checkpoint.error_message == "Sampling diverged"
        assert checkpoint.error_traceback == "Traceback..."
        assert checkpoint.is_resumable is False

    def test_checkpoint_status_enum(self):
        """T5.24: CheckpointStatus enum values."""
        from app.models.analysis_version import CheckpointStatus

        assert CheckpointStatus.IN_PROGRESS.value == "in_progress"
        assert CheckpointStatus.COMPLETED.value == "completed"
        assert CheckpointStatus.ERROR.value == "error"


class TestBayesianCheckpointing:
    """Tests for Bayesian analysis checkpointing."""

    def test_save_config(self, tmp_path):
        """T5.25: Save sampling config for resume."""
        from app.analysis.bayesian import BayesianHierarchical, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not available")

        bayesian = BayesianHierarchical(
            chains=4,
            draws=2000,
            tune=1000,
            thin=5,
            random_seed=42
        )

        config_path = tmp_path / "config.json"
        bayesian._save_config(config_path)

        assert config_path.exists()

        config = bayesian._load_config(config_path)
        assert config['chains'] == 4
        assert config['draws'] == 2000
        assert config['tune'] == 1000
        assert config['thin'] == 5
        assert config['random_seed'] == 42

    def test_load_config_missing(self, tmp_path):
        """T5.26: Handle missing config file."""
        from app.analysis.bayesian import BayesianHierarchical, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not available")

        bayesian = BayesianHierarchical()
        config = bayesian._load_config(tmp_path / "nonexistent.json")
        assert config is None

    def test_is_trace_complete_check(self):
        """T5.27: Check trace completeness."""
        from app.analysis.bayesian import BayesianHierarchical, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not available")

        bayesian = BayesianHierarchical(draws=1000, thin=5)

        # Mock a complete trace (200 draws after thinning by 5)
        mock_trace = MagicMock()
        mock_trace.posterior.dims = {'draw': 200, 'chain': 4}

        assert bayesian._is_trace_complete(mock_trace) is True

    def test_is_trace_incomplete(self):
        """T5.28: Detect incomplete trace."""
        from app.analysis.bayesian import BayesianHierarchical, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not available")

        bayesian = BayesianHierarchical(draws=1000, thin=5)

        # Mock an incomplete trace
        mock_trace = MagicMock()
        mock_trace.posterior.dims = {'draw': 50, 'chain': 4}

        assert bayesian._is_trace_complete(mock_trace) is False

    def test_cleanup_checkpoints(self, tmp_path):
        """T5.29: Cleanup checkpoint files."""
        from app.analysis.bayesian import BayesianHierarchical

        # Create some checkpoint files
        (tmp_path / "trace.nc").touch()
        (tmp_path / "config.json").touch()
        (tmp_path / "intermediate.nc").touch()

        deleted = BayesianHierarchical.cleanup_checkpoints(tmp_path, keep_final=True)

        # Should keep trace.nc, delete others
        assert (tmp_path / "trace.nc").exists()
        assert not (tmp_path / "config.json").exists()
        assert deleted == 2

    def test_cleanup_all_checkpoints(self, tmp_path):
        """T5.30: Cleanup all checkpoint files including final."""
        from app.analysis.bayesian import BayesianHierarchical

        # Create checkpoint files
        (tmp_path / "trace.nc").touch()
        (tmp_path / "config.json").touch()

        deleted = BayesianHierarchical.cleanup_checkpoints(tmp_path, keep_final=False)

        assert not (tmp_path / "trace.nc").exists()
        assert deleted == 2


class TestHierarchicalServiceCheckpoints:
    """Tests for HierarchicalService checkpoint management."""

    def test_get_checkpoint_status_no_checkpoints(self, db_session):
        """T5.31: Checkpoint status with no checkpoints."""
        from app.services.hierarchical_service import HierarchicalService

        status = HierarchicalService.get_checkpoint_status(version_id=999)

        assert status['version_id'] == 999
        assert status['total_checkpoints'] == 0
        assert status['latest'] is None
        assert status['has_error'] is False

    def test_create_mcmc_checkpoint(self, db_session):
        """T5.32: Create MCMC checkpoint via service."""
        from app.services.hierarchical_service import HierarchicalService, AnalysisConfig
        from app.models.analysis_version import MCMCCheckpoint
        from app.services import ProjectService
        from app.models.project import PlateFormat

        # Create a project and analysis version
        project = ProjectService.create_project(
            name="Checkpoint Test",
            username="testuser",
            plate_format=PlateFormat.PLATE_384
        )

        config = AnalysisConfig()
        version = HierarchicalService.create_analysis_version(
            project_id=project.id,
            name="Test Version",
            config=config
        )

        # Create checkpoint
        checkpoint = HierarchicalService.create_mcmc_checkpoint(
            version=version,
            draw_idx=2000,
            total_draws=2000,
            checkpoint_path="/tmp/trace.nc",
            is_final=True
        )

        assert checkpoint.analysis_version_id == version.id
        assert checkpoint.is_final is True

        # Verify it's in database
        found = MCMCCheckpoint.query.filter_by(
            analysis_version_id=version.id
        ).first()
        assert found is not None
        assert found.draw_idx == 2000
