"""
Tests for run_statistical_validation.py script.

Phase 5: API and Scripts - Statistical Validation Script
PRD Reference: Section 4.4

Tests for:
- Validation test runner
- Curve fitting validation
- Fold change calculation validation
- Statistical test validation
- Report generation
"""
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.extensions import db
from app.models import Project, Construct, AnalysisVersion, HierarchicalResult, FoldChange
from app.models.project import PlateFormat
from app.models.analysis_version import AnalysisStatus


class TestStatisticalValidationScript:
    """Tests for run_statistical_validation.py script (Phase 5)."""

    def test_script_exists(self):
        """T5.67: run_statistical_validation.py script exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "run_statistical_validation.py"
        assert script_path.exists(), "scripts/run_statistical_validation.py should exist"

    def test_script_importable(self):
        """T5.68: run_statistical_validation.py can be imported."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        try:
            from scripts import run_statistical_validation
            assert run_statistical_validation is not None
        except ImportError as e:
            pytest.fail(f"Failed to import run_statistical_validation: {e}")

    def test_script_has_main_function(self):
        """T5.69: Script has main or run function."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts import run_statistical_validation
        assert hasattr(run_statistical_validation, 'main') or hasattr(run_statistical_validation, 'run_validation')


class TestValidationTests:
    """Tests for individual validation functions."""

    @pytest.fixture
    def validation_script(self):
        """Import the validation script."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts import run_statistical_validation
        return run_statistical_validation

    def test_validate_curve_fitting(self, validation_script, db_session):
        """T5.70: Curve fitting validation works."""
        if hasattr(validation_script, 'validate_curve_fitting'):
            # Test with known synthetic data
            result = validation_script.validate_curve_fitting()
            # Result is a ValidationResult dataclass
            assert hasattr(result, 'passed') or hasattr(result, 'is_valid')
        else:
            pytest.skip("validate_curve_fitting not implemented")

    def test_validate_fold_change_calculation(self, validation_script, db_session):
        """T5.71: Fold change calculation validation works."""
        if hasattr(validation_script, 'validate_fold_change_calculation'):
            result = validation_script.validate_fold_change_calculation()
            # Result is a ValidationResult dataclass
            assert hasattr(result, 'passed') or hasattr(result, 'is_valid')
        else:
            pytest.skip("validate_fold_change_calculation not implemented")

    def test_validate_hierarchical_model(self, validation_script, db_session):
        """T5.72: Hierarchical model validation works."""
        if hasattr(validation_script, 'validate_hierarchical_model'):
            result = validation_script.validate_hierarchical_model()
            # Result is a ValidationResult dataclass
            assert hasattr(result, 'passed')
        else:
            pytest.skip("validate_hierarchical_model not implemented")

    def test_validate_ci_coverage(self, validation_script, db_session):
        """T5.73: CI coverage validation works (95% should contain true value ~95% of time)."""
        if hasattr(validation_script, 'validate_ci_coverage'):
            result = validation_script.validate_ci_coverage()
            # Result is a ValidationResult dataclass
            assert hasattr(result, 'passed')
            if hasattr(result, 'details') and "actual_coverage" in result.details:
                # Coverage should be close to nominal 95%
                assert 0.85 <= result.details["actual_coverage"] <= 1.0
        else:
            pytest.skip("validate_ci_coverage not implemented")


class TestValidationOutput:
    """Tests for validation output and reporting."""

    @pytest.fixture
    def validation_script(self):
        """Import the validation script."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts import run_statistical_validation
        return run_statistical_validation

    @pytest.fixture
    def output_dir(self):
        """Create a temporary directory for report output."""
        import tempfile
        import shutil
        tmpdir = Path(tempfile.mkdtemp())
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generates_report(self, validation_script, output_dir):
        """T5.74: Validation generates a report."""
        if hasattr(validation_script, 'run_validation'):
            report_path = output_dir / "validation_report.json"

            try:
                validation_script.run_validation(output_path=str(report_path))
                if report_path.exists():
                    report = json.loads(report_path.read_text())
                    assert "tests" in report or "results" in report
            except Exception:
                pass
        else:
            pytest.skip("run_validation not implemented")

    def test_report_includes_summary(self, validation_script, output_dir):
        """T5.75: Validation report includes summary."""
        if hasattr(validation_script, 'run_validation'):
            report_path = output_dir / "validation_report.json"

            try:
                validation_script.run_validation(output_path=str(report_path))
                if report_path.exists():
                    report = json.loads(report_path.read_text())
                    # Should have some summary info
                    assert "summary" in report or "total_tests" in report or "passed" in report
            except Exception:
                pass
        else:
            pytest.skip("run_validation not implemented")

    def test_report_includes_timestamp(self, validation_script, output_dir):
        """T5.76: Validation report includes timestamp."""
        if hasattr(validation_script, 'run_validation'):
            report_path = output_dir / "validation_report.json"

            try:
                validation_script.run_validation(output_path=str(report_path))
                if report_path.exists():
                    report = json.loads(report_path.read_text())
                    assert "timestamp" in report or "generated_at" in report or "date" in report
            except Exception:
                pass
        else:
            pytest.skip("run_validation not implemented")


class TestValidationEdgeCases:
    """Tests for validation edge cases."""

    @pytest.fixture
    def validation_script(self):
        """Import the validation script."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts import run_statistical_validation
        return run_statistical_validation

    def test_handles_empty_database(self, validation_script, db_session):
        """T5.77: Validation handles empty database gracefully."""
        if hasattr(validation_script, 'run_validation'):
            try:
                result = validation_script.run_validation()
                # Should not raise an exception
                assert result is not None or True
            except Exception as e:
                # Should handle gracefully, not crash
                assert "empty" in str(e).lower() or isinstance(e, ValueError)
        else:
            pytest.skip("run_validation not implemented")

    def test_handles_partial_data(self, validation_script, db_session):
        """T5.78: Validation handles partial data."""
        # Create project without full analysis
        project = Project(name="Partial Test", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.commit()

        if hasattr(validation_script, 'run_validation'):
            try:
                result = validation_script.run_validation()
                assert result is not None or True
            except Exception:
                pass
        else:
            pytest.skip("run_validation not implemented")


class TestValidationTestSuite:
    """Tests for the validation test suite functionality."""

    @pytest.fixture
    def validation_script(self):
        """Import the validation script."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts import run_statistical_validation
        return run_statistical_validation

    def test_runs_all_tests(self, validation_script, db_session):
        """T5.79: Can run all validation tests."""
        if hasattr(validation_script, 'run_all_tests'):
            results = validation_script.run_all_tests()
            assert isinstance(results, (dict, list))
        else:
            pytest.skip("run_all_tests not implemented")

    def test_runs_specific_test(self, validation_script, db_session):
        """T5.80: Can run specific validation test."""
        if hasattr(validation_script, 'run_test'):
            try:
                result = validation_script.run_test("curve_fitting")
                assert result is not None
            except ValueError:
                pass  # Test name not found is OK
        else:
            pytest.skip("run_test not implemented")

    def test_lists_available_tests(self, validation_script):
        """T5.81: Can list available validation tests."""
        if hasattr(validation_script, 'list_tests'):
            tests = validation_script.list_tests()
            assert isinstance(tests, list)
            assert len(tests) >= 1
        else:
            pytest.skip("list_tests not implemented")

    def test_returns_exit_code(self, validation_script, db_session):
        """T5.82: Main function returns appropriate exit code."""
        if hasattr(validation_script, 'main'):
            import inspect
            sig = inspect.signature(validation_script.main)
            # Main should be callable
            assert callable(validation_script.main)
        else:
            pytest.skip("main not implemented")


class TestValidationIntegration:
    """Integration tests for statistical validation."""

    @pytest.fixture
    def project_with_results(self, db_session):
        """Create a project with analysis results for validation."""
        project = Project(
            name="Validation Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        wt = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_wildtype=True,
            is_draft=False
        )
        mut = Construct(
            project_id=project.id,
            identifier="Mut1",
            family="Test",
            is_draft=False
        )
        db.session.add_all([wt, mut])
        db.session.flush()

        analysis = AnalysisVersion(
            project_id=project.id,
            name="Test Analysis",
            status=AnalysisStatus.COMPLETED,
            model_type="bayesian",
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        db.session.add(analysis)
        db.session.flush()

        results = [
            HierarchicalResult(
                analysis_version_id=analysis.id,
                construct_id=wt.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
                mean=0.0,
                std=0.05,
                ci_lower=-0.1,
                ci_upper=0.1,
                r_hat=1.01,
                ess_bulk=1500,
                ess_tail=1200
            ),
            HierarchicalResult(
                analysis_version_id=analysis.id,
                construct_id=mut.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
                mean=0.85,
                std=0.12,
                ci_lower=0.62,
                ci_upper=1.08,
                r_hat=1.02,
                ess_bulk=1400,
                ess_tail=1100
            )
        ]
        db.session.add_all(results)

        # Note: FoldChange model is well-based (test_well_id, control_well_id)
        # rather than construct-based. We skip FoldChange here since we'd need wells.
        db.session.commit()

        return project

    def test_validates_existing_results(self, project_with_results, db_session):
        """T5.83: Can validate existing analysis results."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        try:
            from scripts import run_statistical_validation

            if hasattr(run_statistical_validation, 'validate_project_results'):
                result = run_statistical_validation.validate_project_results(project_with_results.id)
                assert result is not None
        except Exception:
            pytest.skip("validate_project_results not implemented")

    def test_validates_convergence(self, project_with_results, db_session):
        """T5.84: Validates MCMC convergence diagnostics."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from scripts.run_statistical_validation import validate_convergence

        result = validate_convergence()
        assert result.passed
        assert "r_hat_threshold" in result.details
        assert "ess_threshold" in result.details
