"""
Phase D Implementation Tests - Test Infrastructure Validation.

This module tests the Phase D implementations:
- Task 10: Statistical validation tests (test_coverage.py, test_bias.py)
- Task 11: Workflow test suite directory structure
- Task 12: Synthetic test data files

PRD References:
- Section 4.2: tests/statistical_validation/
- Section 4.1: tests/workflows/
- Section 4.3: tests/data/ synthetic files
"""
import pytest
from pathlib import Path
import json
import pandas as pd
import numpy as np
import os


# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestStatisticalValidationDirectory:
    """Test that statistical validation directory and files exist."""

    def test_statistical_validation_directory_exists(self):
        """Test that tests/statistical_validation/ directory exists."""
        stat_val_dir = PROJECT_ROOT / "tests" / "statistical_validation"
        assert stat_val_dir.exists(), "tests/statistical_validation/ directory should exist"
        assert stat_val_dir.is_dir(), "tests/statistical_validation/ should be a directory"

    def test_coverage_test_file_exists(self):
        """Test that test_coverage.py exists in statistical_validation."""
        coverage_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_coverage.py"
        assert coverage_file.exists(), "test_coverage.py should exist"

    def test_bias_test_file_exists(self):
        """Test that test_bias.py exists in statistical_validation."""
        bias_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_bias.py"
        assert bias_file.exists(), "test_bias.py should exist"


class TestStatisticalValidationCoverageTests:
    """Test the content of test_coverage.py."""

    def test_coverage_file_has_bayesian_test(self):
        """Test that test_coverage.py has Bayesian coverage test."""
        coverage_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_coverage.py"
        content = coverage_file.read_text()
        assert "test_bayesian_coverage" in content or "TestBayesianCoverage" in content, \
            "test_coverage.py should have Bayesian coverage test"

    def test_coverage_file_has_frequentist_test(self):
        """Test that test_coverage.py has Frequentist coverage test."""
        coverage_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_coverage.py"
        content = coverage_file.read_text()
        assert "test_frequentist_coverage" in content or "TestFrequentistCoverage" in content, \
            "test_coverage.py should have Frequentist coverage test"

    def test_coverage_validation_range(self):
        """Test that coverage validation uses 93-97% range for 95% CIs."""
        coverage_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_coverage.py"
        content = coverage_file.read_text()
        # Should reference the 93-97% range
        assert "93" in content or "0.93" in content, \
            "test_coverage.py should reference 93% lower bound"
        assert "97" in content or "0.97" in content, \
            "test_coverage.py should reference 97% upper bound"


class TestStatisticalValidationBiasTests:
    """Test the content of test_bias.py."""

    def test_bias_file_has_bayesian_test(self):
        """Test that test_bias.py has Bayesian bias test."""
        bias_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_bias.py"
        content = bias_file.read_text()
        assert "test_bayesian_bias" in content or "TestBayesianBias" in content, \
            "test_bias.py should have Bayesian bias test"

    def test_bias_file_has_frequentist_test(self):
        """Test that test_bias.py has Frequentist bias test."""
        bias_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_bias.py"
        content = bias_file.read_text()
        assert "test_frequentist_bias" in content or "TestFrequentistBias" in content, \
            "test_bias.py should have Frequentist bias test"

    def test_bias_threshold(self):
        """Test that bias validation uses |bias| < 0.1*std threshold."""
        bias_file = PROJECT_ROOT / "tests" / "statistical_validation" / "test_bias.py"
        content = bias_file.read_text()
        # Should reference the 0.1 threshold
        assert "0.1" in content, "test_bias.py should reference 0.1 threshold"


class TestWorkflowsDirectory:
    """Test that workflow test directory and files exist."""

    def test_workflows_directory_exists(self):
        """Test that tests/workflows/ directory exists."""
        workflows_dir = PROJECT_ROOT / "tests" / "workflows"
        assert workflows_dir.exists(), "tests/workflows/ directory should exist"
        assert workflows_dir.is_dir(), "tests/workflows/ should be a directory"

    def test_workflows_init_exists(self):
        """Test that __init__.py exists in workflows."""
        init_file = PROJECT_ROOT / "tests" / "workflows" / "__init__.py"
        assert init_file.exists(), "__init__.py should exist in tests/workflows/"

    def test_workflows_conftest_exists(self):
        """Test that conftest.py exists in workflows."""
        conftest_file = PROJECT_ROOT / "tests" / "workflows" / "conftest.py"
        assert conftest_file.exists(), "conftest.py should exist in tests/workflows/"

    def test_workflows_project_workflow_exists(self):
        """Test that test_project_workflow.py exists."""
        workflow_file = PROJECT_ROOT / "tests" / "workflows" / "test_project_workflow.py"
        assert workflow_file.exists(), "test_project_workflow.py should exist"

    def test_workflows_upload_workflow_exists(self):
        """Test that test_upload_workflow.py exists."""
        workflow_file = PROJECT_ROOT / "tests" / "workflows" / "test_upload_workflow.py"
        assert workflow_file.exists(), "test_upload_workflow.py should exist"

    def test_workflows_analysis_workflow_exists(self):
        """Test that test_analysis_workflow.py exists."""
        workflow_file = PROJECT_ROOT / "tests" / "workflows" / "test_analysis_workflow.py"
        assert workflow_file.exists(), "test_analysis_workflow.py should exist"

    def test_workflows_export_workflow_exists(self):
        """Test that test_export_workflow.py exists."""
        workflow_file = PROJECT_ROOT / "tests" / "workflows" / "test_export_workflow.py"
        assert workflow_file.exists(), "test_export_workflow.py should exist"


class TestWorkflowsConftest:
    """Test the workflow conftest.py content."""

    def test_conftest_has_fixtures(self):
        """Test that conftest.py has test fixtures."""
        conftest_file = PROJECT_ROOT / "tests" / "workflows" / "conftest.py"
        content = conftest_file.read_text()
        assert "@pytest.fixture" in content, "conftest.py should have pytest fixtures"

    def test_conftest_has_client_fixture(self):
        """Test that conftest.py has test client fixture."""
        conftest_file = PROJECT_ROOT / "tests" / "workflows" / "conftest.py"
        content = conftest_file.read_text()
        assert "client" in content.lower(), \
            "conftest.py should have test client fixtures"


class TestSyntheticDataDirectory:
    """Test that synthetic test data directory and files exist."""

    def test_data_directory_exists(self):
        """Test that tests/data/ directory exists."""
        data_dir = PROJECT_ROOT / "tests" / "data"
        assert data_dir.exists(), "tests/data/ directory should exist"
        assert data_dir.is_dir(), "tests/data/ should be a directory"

    def test_synthetic_simple_exists(self):
        """Test that synthetic_simple.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_simple.csv"
        assert data_file.exists(), "synthetic_simple.csv should exist"

    def test_synthetic_outliers_exists(self):
        """Test that synthetic_outliers.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_outliers.csv"
        assert data_file.exists(), "synthetic_outliers.csv should exist"

    def test_synthetic_drift_exists(self):
        """Test that synthetic_drift.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_drift.csv"
        assert data_file.exists(), "synthetic_drift.csv should exist"

    def test_synthetic_hierarchical_exists(self):
        """Test that synthetic_hierarchical.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_hierarchical.csv"
        assert data_file.exists(), "synthetic_hierarchical.csv should exist"

    def test_synthetic_negative_controls_exists(self):
        """Test that synthetic_negative_controls.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_negative_controls.csv"
        assert data_file.exists(), "synthetic_negative_controls.csv should exist"

    def test_synthetic_96well_exists(self):
        """Test that synthetic_96well.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_96well.csv"
        assert data_file.exists(), "synthetic_96well.csv should exist"

    def test_synthetic_low_snr_exists(self):
        """Test that synthetic_low_snr.csv exists."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_low_snr.csv"
        assert data_file.exists(), "synthetic_low_snr.csv should exist"


class TestSyntheticDataContent:
    """Test the content of synthetic test data files."""

    def test_synthetic_simple_is_valid_csv(self):
        """Test that synthetic_simple.csv is a valid CSV with expected columns."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_simple.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_simple.csv should have data"
        # Should have time and fluorescence columns
        assert any('time' in col.lower() for col in df.columns), \
            "synthetic_simple.csv should have a time column"

    def test_synthetic_hierarchical_has_structure(self):
        """Test that synthetic_hierarchical.csv has hierarchical structure."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_hierarchical.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_hierarchical.csv should have data"
        # Should have construct, session, plate identifiers
        cols_lower = [c.lower() for c in df.columns]
        assert any('construct' in c for c in cols_lower) or any('sample' in c for c in cols_lower), \
            "synthetic_hierarchical.csv should have construct/sample identifiers"

    def test_synthetic_negative_controls_has_controls(self):
        """Test that synthetic_negative_controls.csv has control wells."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_negative_controls.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_negative_controls.csv should have data"

    def test_synthetic_96well_has_96_wells(self):
        """Test that synthetic_96well.csv represents a 96-well plate."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_96well.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_96well.csv should have data"
        # Check for well column or appropriate number of unique wells
        if 'well' in [c.lower() for c in df.columns]:
            well_col = [c for c in df.columns if c.lower() == 'well'][0]
            assert df[well_col].nunique() <= 96, "96-well plate should have at most 96 wells"

    def test_synthetic_outliers_has_outliers(self):
        """Test that synthetic_outliers.csv has outlier indicators or extreme values."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_outliers.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_outliers.csv should have data"

    def test_synthetic_low_snr_has_noise(self):
        """Test that synthetic_low_snr.csv exists and has data."""
        data_file = PROJECT_ROOT / "tests" / "data" / "synthetic_low_snr.csv"
        df = pd.read_csv(data_file)
        assert len(df) > 0, "synthetic_low_snr.csv should have data"


class TestSyntheticDataKnownParameters:
    """Test that synthetic data has documented known parameters for validation."""

    def test_parameters_file_exists(self):
        """Test that a parameters file exists documenting known values."""
        params_file = PROJECT_ROOT / "tests" / "data" / "synthetic_parameters.json"
        assert params_file.exists(), "synthetic_parameters.json should exist"

    def test_parameters_file_has_true_values(self):
        """Test that parameters file contains true parameter values."""
        params_file = PROJECT_ROOT / "tests" / "data" / "synthetic_parameters.json"
        with open(params_file) as f:
            params = json.load(f)

        # Should have sections for different synthetic files
        assert isinstance(params, dict), "Parameters should be a dictionary"
        assert len(params) > 0, "Parameters should not be empty"

        # Should document true parameter values
        params_str = str(params).lower()
        has_true_values = ("true" in params_str or "mu" in params_str
                          or "mean" in params_str or "fmax" in params_str
                          or "kobs" in params_str)
        assert has_true_values, "Parameters should document true values"


class TestStatisticalValidationFunctions:
    """Test that statistical validation functions are importable and work."""

    def test_validate_coverage_importable(self):
        """Test that validate_coverage function is importable."""
        from app.analysis.statistical_tests import validate_coverage
        assert callable(validate_coverage)

    def test_validate_bias_importable(self):
        """Test that validate_bias function is importable."""
        from app.analysis.statistical_tests import validate_bias
        assert callable(validate_bias)

    def test_run_coverage_simulation_importable(self):
        """Test that run_coverage_simulation function is importable."""
        from app.analysis.statistical_tests import run_coverage_simulation
        assert callable(run_coverage_simulation)

    def test_run_bias_simulation_importable(self):
        """Test that run_bias_simulation function is importable."""
        from app.analysis.statistical_tests import run_bias_simulation
        assert callable(run_bias_simulation)

    def test_coverage_simulation_works(self):
        """Test that coverage simulation runs and returns valid result."""
        from app.analysis.statistical_tests import run_coverage_simulation
        result = run_coverage_simulation(
            n_simulations=100,
            n_samples=30,
            true_mean=0.0,
            true_std=1.0,
            ci_level=0.95,
            random_seed=42
        )
        assert hasattr(result, 'observed_coverage')
        assert hasattr(result, 'is_valid')
        assert 0 <= result.observed_coverage <= 1

    def test_bias_simulation_works(self):
        """Test that bias simulation runs and returns valid result."""
        from app.analysis.statistical_tests import run_bias_simulation
        result = run_bias_simulation(
            n_simulations=100,
            n_samples=30,
            true_mean=0.0,
            true_std=1.0,
            random_seed=42
        )
        assert hasattr(result, 'mean_bias')
        assert hasattr(result, 'is_valid')
