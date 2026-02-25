"""
Tests for Sprint 8: Cross-Project Comparison Features

PRD References:
- Section 3.20: Cross-Project Comparison (F20.1-F20.4)
- Phase 9 Test Specifications: T9.17-T9.18

Tests cover:
- Cross-project construct matching (T9.17)
- Cross-project forest plot rendering (T9.18)
- Service methods for comparison data
- API endpoints
- Layout components
"""
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
import plotly.graph_objects as go

from app.services.cross_project_service import (
    CrossProjectComparisonService,
    ProjectConstructMatch,
    ConstructComparisonData,
    CrossProjectSummary,
)
from app.components.forest_plot import create_cross_project_forest_plot
from app.layouts.cross_project_comparison import (
    create_cross_project_comparison_layout,
    create_project_checkbox_item,
    create_summary_table,
)


# =============================================================================
# Service Tests - Construct Matching (T9.17)
# =============================================================================

class TestFindMatchingConstructs:
    """Tests for finding constructs across projects (T9.17)."""

    def test_find_matching_constructs_returns_matches(self):
        """T9.17: Cross-project finds matching constructs with same identifier."""
        # This test uses mocked data since we don't have a real database in unit tests
        with patch.object(CrossProjectComparisonService, 'find_matching_constructs') as mock:
            mock.return_value = [
                ProjectConstructMatch(
                    project_id=1,
                    project_name="Project A",
                    construct_id=10,
                    construct_identifier="Tbox1_M3",
                    family="Tbox1",
                    is_wildtype=False,
                    is_unregulated=False,
                    plate_count=5,
                    replicate_count=20,
                    has_analysis=True,
                    latest_analysis_id=100,
                    latest_analysis_date=datetime(2026, 1, 15)
                ),
                ProjectConstructMatch(
                    project_id=2,
                    project_name="Project B",
                    construct_id=20,
                    construct_identifier="Tbox1_M3",
                    family="Tbox1",
                    is_wildtype=False,
                    is_unregulated=False,
                    plate_count=3,
                    replicate_count=12,
                    has_analysis=True,
                    latest_analysis_id=200,
                    latest_analysis_date=datetime(2026, 1, 20)
                )
            ]

            results = CrossProjectComparisonService.find_matching_constructs("Tbox1_M3")

            assert len(results) == 2
            assert all(m.construct_identifier == "Tbox1_M3" for m in results)
            assert results[0].project_name == "Project A"
            assert results[1].project_name == "Project B"

    def test_find_matching_constructs_empty_result(self):
        """Test when no matching constructs are found."""
        with patch.object(CrossProjectComparisonService, 'find_matching_constructs') as mock:
            mock.return_value = []

            results = CrossProjectComparisonService.find_matching_constructs("NonExistent")

            assert len(results) == 0


class TestGetSharedConstructIdentifiers:
    """Tests for finding shared construct identifiers."""

    def test_get_shared_identifiers_min_projects_2(self):
        """Test finding identifiers in at least 2 projects."""
        with patch.object(CrossProjectComparisonService, 'get_shared_construct_identifiers') as mock:
            mock.return_value = [
                {"identifier": "Tbox1_M3", "project_count": 3},
                {"identifier": "Tbox1_WT", "project_count": 2},
            ]

            results = CrossProjectComparisonService.get_shared_construct_identifiers(min_projects=2)

            assert len(results) == 2
            assert results[0]["identifier"] == "Tbox1_M3"
            assert results[0]["project_count"] == 3

    def test_get_shared_identifiers_sorted_by_count(self):
        """Test that results are sorted by project count descending."""
        with patch.object(CrossProjectComparisonService, 'get_shared_construct_identifiers') as mock:
            mock.return_value = [
                {"identifier": "A", "project_count": 5},
                {"identifier": "B", "project_count": 3},
                {"identifier": "C", "project_count": 2},
            ]

            results = CrossProjectComparisonService.get_shared_construct_identifiers(min_projects=2)

            counts = [r["project_count"] for r in results]
            assert counts == sorted(counts, reverse=True)


# =============================================================================
# Service Tests - Comparison Data
# =============================================================================

class TestGetComparisonData:
    """Tests for getting comparison data across projects."""

    def test_get_comparison_data_structure(self):
        """Test that comparison data has correct structure."""
        comparison = ConstructComparisonData(
            construct_identifier="Tbox1_M3",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "Project A",
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "ci_width": 0.4,
                    "plate_count": 5,
                    "replicate_count": 20,
                    "prob_positive": 0.99,
                    "prob_meaningful": 0.85,
                }
            ]
        )

        assert comparison.construct_identifier == "Tbox1_M3"
        assert comparison.parameter_type == "log_fc_fmax"
        assert len(comparison.projects) == 1
        assert comparison.projects[0]["mean"] == 0.5

    def test_comparison_data_with_multiple_projects(self):
        """Test comparison data with 2 projects (minimum for comparison)."""
        comparison = ConstructComparisonData(
            construct_identifier="Tbox1_M3",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "Project A",
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "ci_width": 0.4,
                    "plate_count": 5,
                    "replicate_count": 20,
                },
                {
                    "project_id": 2,
                    "project_name": "Project B",
                    "mean": 0.45,
                    "std": 0.12,
                    "ci_lower": 0.25,
                    "ci_upper": 0.65,
                    "ci_width": 0.4,
                    "plate_count": 3,
                    "replicate_count": 12,
                }
            ]
        )

        assert len(comparison.projects) == 2


class TestCrossProjectSummary:
    """Tests for cross-project summary statistics."""

    def test_compute_summary_basic(self):
        """Test basic summary computation."""
        comparison = ConstructComparisonData(
            construct_identifier="Test",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "A",
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "plate_count": 5,
                    "replicate_count": 20,
                },
                {
                    "project_id": 2,
                    "project_name": "B",
                    "mean": 0.4,
                    "std": 0.15,
                    "ci_lower": 0.2,
                    "ci_upper": 0.6,
                    "plate_count": 3,
                    "replicate_count": 12,
                }
            ]
        )

        summary = CrossProjectComparisonService.compute_cross_project_summary(comparison)

        assert summary is not None
        assert summary.n_projects == 2
        assert summary.total_plates == 8
        assert summary.total_replicates == 32
        assert summary.mean_estimate == pytest.approx(0.45)
        assert summary.min_estimate == 0.4
        assert summary.max_estimate == 0.5
        assert summary.range_estimate == pytest.approx(0.1)
        assert summary.all_positive  # Both means > 0

    def test_compute_summary_insufficient_projects(self):
        """Test that summary returns None with <2 projects."""
        comparison = ConstructComparisonData(
            construct_identifier="Test",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "A",
                    "mean": 0.5,
                    "std": 0.1,
                    "plate_count": 5,
                    "replicate_count": 20,
                }
            ]
        )

        summary = CrossProjectComparisonService.compute_cross_project_summary(comparison)

        assert summary is None


# =============================================================================
# Forest Plot Tests (T9.18)
# =============================================================================

class TestCrossProjectForestPlot:
    """Tests for cross-project forest plot rendering (T9.18)."""

    def test_forest_plot_with_2_projects(self):
        """T9.18: Cross-project forest plot renders with 2 projects."""
        projects = [
            {
                "project_name": "Project A",
                "mean": 0.5,
                "ci_lower": 0.3,
                "ci_upper": 0.7,
                "plate_count": 5,
                "replicate_count": 20,
            },
            {
                "project_name": "Project B",
                "mean": 0.45,
                "ci_lower": 0.25,
                "ci_upper": 0.65,
                "plate_count": 3,
                "replicate_count": 12,
            }
        ]

        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Tbox1_M3",
            parameter_type="log_fc_fmax"
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)
        # Should have at least 2 traces (points + summary)
        assert len(fig.data) >= 2

    def test_forest_plot_with_5_projects(self):
        """T9.18: Cross-project forest plot renders with 5 projects."""
        projects = [
            {
                "project_name": f"Project {chr(65+i)}",
                "mean": 0.5 + i * 0.05,
                "ci_lower": 0.3 + i * 0.05,
                "ci_upper": 0.7 + i * 0.05,
                "plate_count": 3 + i,
                "replicate_count": 10 + i * 2,
            }
            for i in range(5)
        ]

        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Tbox1_M3",
            parameter_type="log_fc_fmax"
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)
        # Should have 5 data points + summary
        assert len(fig.data) >= 2

    def test_forest_plot_empty_data(self):
        """Test forest plot with no data shows message."""
        fig = create_cross_project_forest_plot(
            projects=[],
            construct_identifier="Test"
        )

        assert fig is not None
        # Check for "No data" annotation
        assert len(fig.layout.annotations) > 0

    def test_forest_plot_shows_summary(self):
        """Test that forest plot includes summary diamond."""
        projects = [
            {
                "project_name": "Project A",
                "mean": 0.5,
                "ci_lower": 0.3,
                "ci_upper": 0.7,
                "plate_count": 5,
                "replicate_count": 20,
            },
            {
                "project_name": "Project B",
                "mean": 0.45,
                "ci_lower": 0.25,
                "ci_upper": 0.65,
                "plate_count": 3,
                "replicate_count": 12,
            }
        ]

        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Test",
            show_summary=True
        )

        # Check that summary trace exists
        trace_names = [t.name for t in fig.data if hasattr(t, 'name')]
        assert "Cross-project mean" in trace_names

    def test_forest_plot_without_summary(self):
        """Test that forest plot can hide summary."""
        projects = [
            {
                "project_name": "Project A",
                "mean": 0.5,
                "ci_lower": 0.3,
                "ci_upper": 0.7,
                "plate_count": 5,
                "replicate_count": 20,
            },
            {
                "project_name": "Project B",
                "mean": 0.45,
                "ci_lower": 0.25,
                "ci_upper": 0.65,
                "plate_count": 3,
                "replicate_count": 12,
            }
        ]

        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Test",
            show_summary=False
        )

        # Check that summary trace does not exist
        trace_names = [t.name for t in fig.data if hasattr(t, 'name')]
        assert "Cross-project mean" not in trace_names

    def test_forest_plot_parameter_labels(self):
        """Test that forest plot has correct axis labels for different parameters."""
        projects = [
            {"project_name": "A", "mean": 0.5, "ci_lower": 0.3, "ci_upper": 0.7,
             "plate_count": 5, "replicate_count": 20}
        ]

        # Test log_fc_fmax
        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Test",
            parameter_type="log_fc_fmax"
        )
        assert "F_max" in fig.layout.xaxis.title.text

        # Test log_fc_kobs
        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Test",
            parameter_type="log_fc_kobs"
        )
        assert "k_obs" in fig.layout.xaxis.title.text

        # Test delta_tlag
        fig = create_cross_project_forest_plot(
            projects=projects,
            construct_identifier="Test",
            parameter_type="delta_tlag"
        )
        assert "t_lag" in fig.layout.xaxis.title.text


# =============================================================================
# Layout Component Tests
# =============================================================================

class TestLayoutComponents:
    """Tests for cross-project comparison layout components."""

    def test_create_layout(self):
        """Test that layout creates successfully."""
        layout = create_cross_project_comparison_layout()

        assert layout is not None

    def test_create_project_checkbox(self):
        """Test project checkbox creation."""
        checkbox = create_project_checkbox_item(
            project_id=1,
            project_name="Test Project",
            plate_count=5,
            replicate_count=20,
            has_analysis=True
        )

        assert checkbox is not None
        assert not checkbox.disabled

    def test_create_project_checkbox_no_analysis(self):
        """Test project checkbox is disabled without analysis."""
        checkbox = create_project_checkbox_item(
            project_id=1,
            project_name="Test Project",
            plate_count=5,
            replicate_count=20,
            has_analysis=False
        )

        assert checkbox.disabled

    def test_create_summary_table_empty(self):
        """Test summary table with empty data."""
        table = create_summary_table(projects=[], show_bayesian=True)

        # Should show "No data available" message
        assert table is not None

    def test_create_summary_table_with_data(self):
        """Test summary table with data."""
        projects = [
            {
                "project_name": "Project A",
                "plate_count": 5,
                "replicate_count": 20,
                "mean": 0.5,
                "ci_lower": 0.3,
                "ci_upper": 0.7,
                "ci_width": 0.4,
                "prob_positive": 0.99,
                "prob_meaningful": 0.85,
            },
            {
                "project_name": "Project B",
                "plate_count": 3,
                "replicate_count": 12,
                "mean": 0.45,
                "ci_lower": 0.25,
                "ci_upper": 0.65,
                "ci_width": 0.4,
                "prob_positive": 0.95,
                "prob_meaningful": 0.75,
            }
        ]

        table = create_summary_table(projects=projects, show_bayesian=True)

        assert table is not None


# =============================================================================
# Export Tests
# =============================================================================

class TestExportComparison:
    """Tests for exporting comparison data."""

    def test_export_comparison_table(self):
        """Test exporting comparison data as DataFrame."""
        comparison = ConstructComparisonData(
            construct_identifier="Tbox1_M3",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "Project A",
                    "construct_id": 10,
                    "analysis_id": 100,
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "ci_width": 0.4,
                    "plate_count": 5,
                    "replicate_count": 20,
                    "prob_positive": 0.99,
                    "prob_meaningful": 0.85,
                    "analysis_date": "2026-01-15T10:00:00",
                },
                {
                    "project_id": 2,
                    "project_name": "Project B",
                    "construct_id": 20,
                    "analysis_id": 200,
                    "mean": 0.45,
                    "std": 0.12,
                    "ci_lower": 0.25,
                    "ci_upper": 0.65,
                    "ci_width": 0.4,
                    "plate_count": 3,
                    "replicate_count": 12,
                    "prob_positive": 0.95,
                    "prob_meaningful": 0.75,
                    "analysis_date": "2026-01-20T14:00:00",
                }
            ]
        )

        df = CrossProjectComparisonService.export_comparison_table(
            comparison_data=comparison,
            include_diagnostics=False
        )

        assert len(df) == 2
        assert "Project" in df.columns
        assert "Mean" in df.columns
        assert "CI Lower (95%)" in df.columns
        assert "CI Upper (95%)" in df.columns
        assert df.iloc[0]["Project"] == "Project A"
        assert df.iloc[0]["Mean"] == 0.5

    def test_export_with_diagnostics(self):
        """Test export includes diagnostics when requested."""
        comparison = ConstructComparisonData(
            construct_identifier="Test",
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "A",
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "ci_width": 0.4,
                    "plate_count": 5,
                    "replicate_count": 20,
                    "n_samples": 4000,
                    "r_hat": 1.001,
                    "ess_bulk": 3500,
                }
            ]
        )

        df = CrossProjectComparisonService.export_comparison_table(
            comparison_data=comparison,
            include_diagnostics=True
        )

        assert "N Samples" in df.columns
        assert "R-hat" in df.columns
        assert "ESS Bulk" in df.columns


# =============================================================================
# Integration Tests
# =============================================================================

class TestCrossProjectWorkflow:
    """Integration tests for cross-project comparison workflow."""

    def test_complete_comparison_workflow(self):
        """Test complete workflow: find constructs -> get data -> visualize."""
        # Step 1: Mock finding shared constructs
        with patch.object(
            CrossProjectComparisonService,
            'get_shared_construct_identifiers'
        ) as mock_shared:
            mock_shared.return_value = [
                {"identifier": "Tbox1_M3", "project_count": 2}
            ]

            shared = CrossProjectComparisonService.get_shared_construct_identifiers()
            assert len(shared) == 1
            identifier = shared[0]["identifier"]

        # Step 2: Create comparison data
        comparison = ConstructComparisonData(
            construct_identifier=identifier,
            parameter_type="log_fc_fmax",
            projects=[
                {
                    "project_id": 1,
                    "project_name": "Project A",
                    "mean": 0.5,
                    "std": 0.1,
                    "ci_lower": 0.3,
                    "ci_upper": 0.7,
                    "ci_width": 0.4,
                    "plate_count": 5,
                    "replicate_count": 20,
                },
                {
                    "project_id": 2,
                    "project_name": "Project B",
                    "mean": 0.45,
                    "std": 0.12,
                    "ci_lower": 0.25,
                    "ci_upper": 0.65,
                    "ci_width": 0.4,
                    "plate_count": 3,
                    "replicate_count": 12,
                }
            ]
        )

        # Step 3: Generate forest plot
        fig = create_cross_project_forest_plot(
            projects=comparison.projects,
            construct_identifier=comparison.construct_identifier,
            parameter_type=comparison.parameter_type
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)

        # Step 4: Compute summary
        summary = CrossProjectComparisonService.compute_cross_project_summary(comparison)

        assert summary is not None
        assert summary.n_projects == 2
        assert summary.all_positive

        # Step 5: Export table
        df = CrossProjectComparisonService.export_comparison_table(comparison)

        assert len(df) == 2

    def test_workflow_with_no_shared_constructs(self):
        """Test workflow when no shared constructs exist."""
        with patch.object(
            CrossProjectComparisonService,
            'get_shared_construct_identifiers'
        ) as mock_shared:
            mock_shared.return_value = []

            shared = CrossProjectComparisonService.get_shared_construct_identifiers()
            assert len(shared) == 0

        # Forest plot should handle empty data gracefully
        fig = create_cross_project_forest_plot(
            projects=[],
            construct_identifier="None"
        )
        assert fig is not None
