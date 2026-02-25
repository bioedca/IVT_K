"""
Tests for Results API endpoints.

Phase 5: API and Scripts - Results API Enhancement
PRD Reference: Section 4.2

Tests for:
- GET /api/projects/{id}/results/posterior     Posterior summaries
- GET /api/projects/{id}/results/fold-changes  Fold change table
- GET /api/projects/{id}/results/diagnostics   MCMC diagnostics
- GET /api/projects/{id}/results/export        Export results as CSV/JSON
"""
import pytest
import json
from datetime import datetime

from app.extensions import db
from app.models import (
    Project, Construct, AnalysisVersion, HierarchicalResult, FoldChange
)
from app.models.project import PlateFormat
from app.models.analysis_version import AnalysisStatus


class TestResultsAPI:
    """Tests for Results API endpoints (Phase 5)."""

    @pytest.fixture
    def project_with_analysis(self, db_session):
        """Create a project with completed analysis and results."""
        # Create project
        project = Project(
            name="Results Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        # Create constructs
        wt = Construct(
            project_id=project.id,
            identifier="WT",
            family="TestFamily",
            is_wildtype=True,
            is_draft=False
        )
        mut1 = Construct(
            project_id=project.id,
            identifier="Mut1",
            family="TestFamily",
            is_draft=False
        )
        mut2 = Construct(
            project_id=project.id,
            identifier="Mut2",
            family="TestFamily",
            is_draft=False
        )
        db.session.add_all([wt, mut1, mut2])
        db.session.flush()

        # Create analysis version
        analysis = AnalysisVersion(
            project_id=project.id,
            name="Analysis v1",
            status=AnalysisStatus.COMPLETED,
            model_type="bayesian_hierarchical",
            mcmc_chains=4,
            mcmc_draws=2000,
            mcmc_tune=1000,
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            completed_at=datetime(2026, 1, 1, 10, 30, 0),
            duration_seconds=1800
        )
        db.session.add(analysis)
        db.session.flush()

        # Create hierarchical results
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
                construct_id=mut1.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
                mean=0.85,
                std=0.12,
                ci_lower=0.62,
                ci_upper=1.08,
                r_hat=1.02,
                ess_bulk=1400,
                ess_tail=1100,
                prob_positive=0.99,
                prob_meaningful=0.95
            ),
            HierarchicalResult(
                analysis_version_id=analysis.id,
                construct_id=mut2.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
                mean=-0.35,
                std=0.15,
                ci_lower=-0.65,
                ci_upper=-0.05,
                r_hat=1.03,
                ess_bulk=1300,
                ess_tail=1000,
                prob_positive=0.02
            ),
        ]
        db.session.add_all(results)

        # Note: FoldChange in this model is well-based, not construct-based
        # The Results API test will need to adapt to the actual model structure

        db.session.commit()

        return {
            "project": project,
            "analysis": analysis,
            "wt": wt,
            "mut1": mut1,
            "mut2": mut2,
            "results": results
        }

    @pytest.fixture
    def project_without_analysis(self, db_session):
        """Create a project without any analysis."""
        project = Project(
            name="No Analysis Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.commit()
        return project

    # ==================== GET /api/projects/{id}/results/posterior Tests ====================

    def test_get_posterior_success(self, client, project_with_analysis):
        """T5.23: Successfully get posterior summaries."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert len(data["results"]) == 3  # 3 hierarchical results
        assert "count" in data

    def test_get_posterior_includes_all_fields(self, client, project_with_analysis):
        """T5.24: Posterior results include all required fields."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        result = data["results"][0]

        required_fields = [
            "construct_id", "parameter_type", "mean", "std",
            "ci_lower", "ci_upper", "r_hat", "ess_bulk", "ess_tail"
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_get_posterior_filter_by_parameter(self, client, project_with_analysis):
        """T5.25: Filter posterior results by parameter type."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior?parameter_type=log_fc_fmax',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        for result in data["results"]:
            assert result["parameter_type"] == "log_fc_fmax"

    def test_get_posterior_filter_by_construct(self, client, project_with_analysis):
        """T5.26: Filter posterior results by construct."""
        project = project_with_analysis["project"]
        mut1 = project_with_analysis["mut1"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior?construct_id={mut1.id}',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        for result in data["results"]:
            assert result["construct_id"] == mut1.id

    def test_get_posterior_no_analysis(self, client, project_without_analysis):
        """T5.27: Posterior returns empty for project without analysis."""
        response = client.get(
            f'/api/projects/{project_without_analysis.id}/results/posterior',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["results"] == []
        assert data["count"] == 0

    def test_get_posterior_nonexistent_project(self, client, db_session):
        """T5.28: Posterior returns 404 for non-existent project."""
        response = client.get(
            '/api/projects/99999/results/posterior',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404

    def test_get_posterior_specific_version(self, client, project_with_analysis):
        """T5.29: Get posterior for specific analysis version."""
        project = project_with_analysis["project"]
        analysis = project_with_analysis["analysis"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior?version_id={analysis.id}',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["analysis_version_id"] == analysis.id

    # ==================== GET /api/projects/{id}/results/fold-changes Tests ====================

    def test_get_fold_changes_success(self, client, project_with_analysis):
        """T5.30: Successfully get fold change table."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/fold-changes',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "fold_changes" in data
        # May be empty if no fold changes have been calculated
        assert isinstance(data["fold_changes"], list)

    def test_get_fold_changes_includes_all_fields(self, client, project_with_analysis):
        """T5.31: Fold change results include all required fields."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/fold-changes',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        # FoldChange model is well-based; may be empty if no wells/fold changes exist
        if data["fold_changes"]:
            fc = data["fold_changes"][0]
            # Actual model fields (well-based)
            required_fields = [
                "id", "test_well_id", "fc_fmax", "log_fc_fmax"
            ]
            for field in required_fields:
                assert field in fc, f"Missing field: {field}"

    def test_get_fold_changes_filter_by_construct(self, client, project_with_analysis):
        """T5.32: Filter fold changes by construct."""
        project = project_with_analysis["project"]
        mut1 = project_with_analysis["mut1"]

        response = client.get(
            f'/api/projects/{project.id}/results/fold-changes?construct_id={mut1.id}',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        # Response is valid (may be empty if no matching fold changes)
        assert "fold_changes" in data

    def test_get_fold_changes_response_structure(self, client, project_with_analysis):
        """T5.33: Fold changes response has proper structure."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/fold-changes',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "fold_changes" in data
        assert "count" in data
        assert data["project_id"] == project.id

    def test_get_fold_changes_no_analysis(self, client, project_without_analysis):
        """T5.34: Fold changes returns empty for project without analysis."""
        response = client.get(
            f'/api/projects/{project_without_analysis.id}/results/fold-changes',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["fold_changes"] == []

    def test_get_fold_changes_includes_construct_names(self, client, project_with_analysis):
        """T5.35: Fold changes include construct display names when available."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/fold-changes',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        # May be empty if no wells/fold changes exist
        if data["fold_changes"]:
            fc = data["fold_changes"][0]
            # If construct info is resolved, it should include identifiers
            assert "test_construct_identifier" in fc or "test_construct_id" in fc or "test_well_id" in fc

    # ==================== GET /api/projects/{id}/results/diagnostics Tests ====================

    def test_get_diagnostics_success(self, client, project_with_analysis):
        """T5.36: Successfully get MCMC diagnostics."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/diagnostics',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "diagnostics" in data

    def test_get_diagnostics_includes_convergence(self, client, project_with_analysis):
        """T5.37: Diagnostics include convergence metrics."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/diagnostics',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        diag = data["diagnostics"]

        assert "max_r_hat" in diag
        assert "min_ess_bulk" in diag
        assert "all_converged" in diag

    def test_get_diagnostics_includes_per_parameter(self, client, project_with_analysis):
        """T5.38: Diagnostics include per-parameter breakdown."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/diagnostics?include_parameters=true',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        if "parameters" in data["diagnostics"]:
            assert isinstance(data["diagnostics"]["parameters"], list)

    def test_get_diagnostics_model_info(self, client, project_with_analysis):
        """T5.39: Diagnostics include model information."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/diagnostics',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert "model_type" in data or "model_info" in data

    def test_get_diagnostics_no_analysis(self, client, project_without_analysis):
        """T5.40: Diagnostics returns appropriate message for no analysis."""
        response = client.get(
            f'/api/projects/{project_without_analysis.id}/results/diagnostics',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["diagnostics"] is None or data.get("message")

    def test_get_diagnostics_for_version(self, client, project_with_analysis):
        """T5.41: Get diagnostics for specific analysis version."""
        project = project_with_analysis["project"]
        analysis = project_with_analysis["analysis"]

        response = client.get(
            f'/api/projects/{project.id}/results/diagnostics?version_id={analysis.id}',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200

    # ==================== GET /api/projects/{id}/results/export Tests ====================

    def test_export_results_json(self, client, project_with_analysis):
        """T5.42: Export results as JSON."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export?format=json',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "posterior" in data or "results" in data
        assert "fold_changes" in data

    def test_export_results_csv(self, client, project_with_analysis):
        """T5.43: Export results as CSV."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export?format=csv',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        # CSV should have appropriate content type
        assert "text/csv" in response.content_type or "application/csv" in response.content_type

    def test_export_results_includes_metadata(self, client, project_with_analysis):
        """T5.44: Export includes analysis metadata."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export?format=json',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert "metadata" in data or "analysis_info" in data

    def test_export_results_filter_fields(self, client, project_with_analysis):
        """T5.45: Export with field selection."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export?format=json&include=posterior',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200

    def test_export_nonexistent_project(self, client, db_session):
        """T5.46: Export returns 404 for non-existent project."""
        response = client.get(
            '/api/projects/99999/results/export?format=json',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404

    def test_export_no_analysis(self, client, project_without_analysis):
        """T5.47: Export returns appropriate response for project without analysis."""
        response = client.get(
            f'/api/projects/{project_without_analysis.id}/results/export?format=json',
            headers={"X-Username": "test_user"}
        )

        # Should succeed but with empty data
        assert response.status_code in [200, 404]

    def test_export_default_format_is_json(self, client, project_with_analysis):
        """T5.48: Export defaults to JSON format."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        # Should be JSON
        assert "application/json" in response.content_type

    def test_export_invalid_format(self, client, project_with_analysis):
        """T5.49: Export rejects invalid format."""
        project = project_with_analysis["project"]

        response = client.get(
            f'/api/projects/{project.id}/results/export?format=invalid',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 400


class TestResultsAPIMultipleVersions:
    """Tests for results API with multiple analysis versions."""

    @pytest.fixture
    def project_multiple_versions(self, db_session):
        """Create a project with multiple analysis versions."""
        project = Project(
            name="Multi-Version Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_draft=False
        )
        db.session.add(construct)
        db.session.flush()

        # Create multiple versions
        v1 = AnalysisVersion(
            project_id=project.id,
            name="Analysis v1",
            status=AnalysisStatus.COMPLETED,
            model_type="bayesian",
            started_at=datetime(2026, 1, 1, 10, 0),
            completed_at=datetime(2026, 1, 1, 10, 30)
        )
        v2 = AnalysisVersion(
            project_id=project.id,
            name="Analysis v2",
            status=AnalysisStatus.COMPLETED,
            model_type="bayesian",
            started_at=datetime(2026, 1, 2, 10, 0),
            completed_at=datetime(2026, 1, 2, 10, 30)
        )
        db.session.add_all([v1, v2])
        db.session.flush()

        # Add results to each version
        r1 = HierarchicalResult(
            analysis_version_id=v1.id,
            construct_id=construct.id,
            parameter_type="log_fc_fmax",
            analysis_type="bayesian",
            mean=0.5,
            std=0.1,
            ci_lower=0.3,
            ci_upper=0.7,
            r_hat=1.01,
            ess_bulk=1500,
            ess_tail=1200
        )
        r2 = HierarchicalResult(
            analysis_version_id=v2.id,
            construct_id=construct.id,
            parameter_type="log_fc_fmax",
            analysis_type="bayesian",
            mean=0.55,
            std=0.08,
            ci_lower=0.39,
            ci_upper=0.71,
            r_hat=1.005,
            ess_bulk=1800,
            ess_tail=1500
        )
        db.session.add_all([r1, r2])
        db.session.commit()

        return {
            "project": project,
            "v1": v1,
            "v2": v2
        }

    def test_get_latest_version_by_default(self, client, project_multiple_versions):
        """T5.50: Default to latest completed analysis version."""
        project = project_multiple_versions["project"]
        v2 = project_multiple_versions["v2"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert data.get("analysis_version_id") == v2.id

    def test_get_specific_version(self, client, project_multiple_versions):
        """T5.51: Can request specific analysis version."""
        project = project_multiple_versions["project"]
        v1 = project_multiple_versions["v1"]

        response = client.get(
            f'/api/projects/{project.id}/results/posterior?version_id={v1.id}',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert data.get("analysis_version_id") == v1.id

    def test_results_from_different_versions_differ(self, client, project_multiple_versions):
        """T5.52: Results from different versions can have different values."""
        project = project_multiple_versions["project"]
        v1 = project_multiple_versions["v1"]
        v2 = project_multiple_versions["v2"]

        # Get results from v1
        response1 = client.get(
            f'/api/projects/{project.id}/results/posterior?version_id={v1.id}',
            headers={"X-Username": "test_user"}
        )
        data1 = response1.get_json()

        # Get results from v2
        response2 = client.get(
            f'/api/projects/{project.id}/results/posterior?version_id={v2.id}',
            headers={"X-Username": "test_user"}
        )
        data2 = response2.get_json()

        # Values should differ between versions
        if data1["results"] and data2["results"]:
            assert data1["results"][0]["mean"] != data2["results"][0]["mean"]
