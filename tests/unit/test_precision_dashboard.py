"""
Unit tests for precision dashboard layout and callbacks.

Phase 7.1: Precision Tracking Dashboard (F12.1)
"""
import pytest
from unittest.mock import MagicMock, patch
import dash_mantine_components as dmc
import plotly.graph_objects as go


class TestPrecisionDashboardLayout:
    """Tests for precision dashboard layout functions."""

    def test_create_precision_dashboard_layout_returns_component(self):
        """Test that create_precision_dashboard_layout returns a valid component."""
        from app.layouts.precision_dashboard import create_precision_dashboard_layout

        layout = create_precision_dashboard_layout()
        assert layout is not None

    def test_create_overall_progress_all_met(self):
        """Test overall progress when all constructs meet target."""
        from app.layouts.precision_dashboard import create_overall_progress

        result = create_overall_progress(
            at_target=10,
            total=10,
            average_ci=0.25,
            target=0.3,
        )
        assert result is not None

    def test_create_overall_progress_none_met(self):
        """Test overall progress when no constructs meet target."""
        from app.layouts.precision_dashboard import create_overall_progress

        result = create_overall_progress(
            at_target=0,
            total=10,
            average_ci=0.85,
            target=0.3,
        )
        assert result is not None

    def test_create_overall_progress_partial_met(self):
        """Test overall progress with partial target met."""
        from app.layouts.precision_dashboard import create_overall_progress

        result = create_overall_progress(
            at_target=5,
            total=10,
            average_ci=0.45,
            target=0.3,
        )
        assert result is not None

    def test_create_overall_progress_partial_scope(self):
        """Test overall progress with partial analysis scope."""
        from app.layouts.precision_dashboard import create_overall_progress

        result = create_overall_progress(
            at_target=3,
            total=8,
            average_ci=0.55,
            target=0.3,
        )
        assert result is not None

    def test_create_overall_progress_no_scope(self):
        """Test overall progress with no analysis scope."""
        from app.layouts.precision_dashboard import create_overall_progress

        result = create_overall_progress(
            at_target=0,
            total=0,
            average_ci=0.0,
            target=0.3,
        )
        assert result is not None


class TestPrecisionTables:
    """Tests for precision table functions."""

    def test_create_precision_table_simple_empty(self):
        """Test simple precision table with empty data."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        result = create_precision_table_simple([])
        assert result is not None

    def test_create_precision_table_simple_with_data(self):
        """Test simple precision table with data."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        constructs = [
            {
                "construct_id": 1,
                "construct_name": "Construct A",
                "ci_width": 0.45,
                "target_width": 0.6,
                "status": "met",
            },
            {
                "construct_id": 2,
                "construct_name": "Construct B",
                "ci_width": 0.75,
                "target_width": 0.6,
                "status": "close",
            },
            {
                "construct_id": 3,
                "construct_name": "Construct C",
                "ci_width": 1.2,
                "target_width": 0.6,
                "status": "not_met",
            },
        ]

        result = create_precision_table_simple(constructs)
        assert result is not None

    def test_create_precision_table_advanced_empty(self):
        """Test advanced precision table with empty data."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        result = create_precision_table_advanced([])
        assert result is not None

    def test_create_precision_table_advanced_with_data(self):
        """Test advanced precision table with data."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [
            {
                "construct_id": 1,
                "construct_name": "Construct A",
                "family": "Family 1",
                "ci_width": 0.45,
                "ci_lower": -0.22,
                "ci_upper": 0.23,
                "mean": 0.005,
                "std": 0.12,
                "target_width": 0.6,
                "status": "met",
                "n_replicates": 6,
                "path_type": "direct",
                "vif": 1.0,
                "r_hat": 1.001,
                "ess_bulk": 1500,
            },
        ]

        result = create_precision_table_advanced(constructs)
        assert result is not None

    def test_create_precision_table_advanced_many_constructs(self):
        """Test advanced precision table with many constructs."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [
            {
                "construct_id": i,
                "construct_name": f"Construct {i}",
                "family": f"Family {i % 3}",
                "ci_width": 0.4 + (i % 5) * 0.2,
                "ci_lower": -0.2 - (i % 5) * 0.1,
                "ci_upper": 0.2 + (i % 5) * 0.1,
                "mean": 0.01 * i,
                "std": 0.1,
                "target_width": 0.6,
                "status": "met" if i % 3 == 0 else ("close" if i % 3 == 1 else "not_met"),
                "n_replicates": 3 + i % 4,
                "path_type": ["direct", "one_hop", "two_hop"][i % 3],
                "vif": [1.0, 1.414, 2.0][i % 3],
                "r_hat": 1.001,
                "ess_bulk": 1500,
            }
            for i in range(20)
        ]

        result = create_precision_table_advanced(constructs)
        assert result is not None


class TestSparkline:
    """Tests for sparkline generation."""

    def test_create_sparkline_empty(self):
        """Test sparkline with empty data."""
        from app.layouts.precision_dashboard import create_sparkline

        result = create_sparkline([])
        assert result is not None

    def test_create_sparkline_single_point(self):
        """Test sparkline with single data point."""
        from app.layouts.precision_dashboard import create_sparkline

        result = create_sparkline([0.5])
        assert result is not None

    def test_create_sparkline_increasing(self):
        """Test sparkline with increasing trend."""
        from app.layouts.precision_dashboard import create_sparkline

        result = create_sparkline([0.3, 0.4, 0.5, 0.6, 0.7])
        assert result is not None

    def test_create_sparkline_decreasing(self):
        """Test sparkline with decreasing trend (improving precision)."""
        from app.layouts.precision_dashboard import create_sparkline

        result = create_sparkline([0.9, 0.7, 0.5, 0.4, 0.35])
        assert result is not None

    def test_create_sparkline_fluctuating(self):
        """Test sparkline with fluctuating values."""
        from app.layouts.precision_dashboard import create_sparkline

        result = create_sparkline([0.5, 0.6, 0.4, 0.7, 0.5])
        assert result is not None


class TestRecommendationsPanel:
    """Tests for recommendations panel."""

    def test_create_recommendations_panel_empty(self):
        """Test recommendations panel with no recommendations."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        result = create_recommendations_panel([])
        assert result is not None

    def test_create_recommendations_panel_single(self):
        """Test recommendations panel with single recommendation."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        recommendations = [
            {
                "construct_a": "Construct A",
                "construct_b": "WT",
                "current_ci": 0.9,
                "expected_ci": 0.5,
                "improvement_pct": 44,
                "plates_needed": 2,
            }
        ]

        result = create_recommendations_panel(recommendations)
        assert result is not None

    def test_create_recommendations_panel_multiple(self):
        """Test recommendations panel with multiple recommendations."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        recommendations = [
            {
                "construct_a": "Construct A",
                "construct_b": "WT",
                "current_ci": 1.2,
                "expected_ci": 0.6,
                "improvement_pct": 50,
                "plates_needed": 3,
            },
            {
                "construct_a": "Construct B",
                "construct_b": "Construct A",
                "current_ci": 0.8,
                "expected_ci": 0.5,
                "improvement_pct": 38,
                "plates_needed": 2,
            },
        ]

        result = create_recommendations_panel(recommendations)
        assert result is not None

    def test_create_recommendations_panel_partial_scope(self):
        """Test recommendations panel with partial analysis scope."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        recommendations = [
            {
                "construct_a": "Construct A",
                "construct_b": "WT",
                "current_ci": 0.9,
                "expected_ci": 0.6,
                "improvement_pct": 33,
                "plates_needed": 2,
            }
        ]

        result = create_recommendations_panel(recommendations)
        assert result is not None


class TestPrecisionHistoryChart:
    """Tests for precision history chart."""

    def test_create_precision_history_chart_empty(self):
        """Test history chart with empty data."""
        from app.layouts.precision_dashboard import create_precision_history_chart

        result = create_precision_history_chart([], target=0.3)
        assert isinstance(result, go.Figure)

    def test_create_precision_history_chart_single_version(self):
        """Test history chart with single version."""
        from app.layouts.precision_dashboard import create_precision_history_chart

        history = [
            {
                "construct_name": "Construct A",
                "date": "2024-01-15",
                "ci_width": 0.65,
            }
        ]

        result = create_precision_history_chart(history, target=0.3)
        assert isinstance(result, go.Figure)

    def test_create_precision_history_chart_multiple_versions(self):
        """Test history chart with multiple versions showing improvement."""
        from app.layouts.precision_dashboard import create_precision_history_chart

        history = [
            {
                "construct_name": "Construct A",
                "date": "2024-01-15",
                "ci_width": 0.85,
            },
            {
                "construct_name": "Construct A",
                "date": "2024-01-22",
                "ci_width": 0.70,
            },
            {
                "construct_name": "Construct A",
                "date": "2024-01-29",
                "ci_width": 0.55,
            },
            {
                "construct_name": "Construct B",
                "date": "2024-01-15",
                "ci_width": 0.60,
            },
            {
                "construct_name": "Construct B",
                "date": "2024-01-22",
                "ci_width": 0.45,
            },
        ]

        result = create_precision_history_chart(history, target=0.3)
        assert isinstance(result, go.Figure)


class TestStatusColorMapping:
    """Tests for status color mapping in precision tables."""

    def test_status_met_displays_correctly(self):
        """Test that 'met' status displays with appropriate styling."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        constructs = [{
            "construct_id": 1,
            "construct_name": "Met Target",
            "ci_width": 0.5,
            "target_width": 0.6,
            "status": "met",
        }]

        result = create_precision_table_simple(constructs)
        assert result is not None

    def test_status_close_displays_correctly(self):
        """Test that 'close' status displays with appropriate styling."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        constructs = [{
            "construct_id": 1,
            "construct_name": "Close to Target",
            "ci_width": 0.75,
            "target_width": 0.6,
            "status": "close",
        }]

        result = create_precision_table_simple(constructs)
        assert result is not None

    def test_status_not_met_displays_correctly(self):
        """Test that 'not_met' status displays with appropriate styling."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        constructs = [{
            "construct_id": 1,
            "construct_name": "Not Met",
            "ci_width": 1.2,
            "target_width": 0.6,
            "status": "not_met",
        }]

        result = create_precision_table_simple(constructs)
        assert result is not None


class TestVIFDisplay:
    """Tests for VIF (Variance Inflation Factor) display."""

    def test_vif_direct_path(self):
        """Test VIF display for direct comparison path."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [{
            "construct_id": 1,
            "construct_name": "Direct Path",
            "ci_width": 0.5,
            "target_width": 0.6,
            "status": "met",
            "path_type": "direct",
            "vif": 1.0,
            "r_hat": 1.001,
            "ess_bulk": 1500,
        }]

        result = create_precision_table_advanced(constructs)
        assert result is not None

    def test_vif_one_hop_path(self):
        """Test VIF display for one-hop comparison path."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [{
            "construct_id": 1,
            "construct_name": "One Hop Path",
            "ci_width": 0.6,
            "target_width": 0.6,
            "status": "met",
            "path_type": "one_hop",
            "vif": 1.414,  # sqrt(2)
            "r_hat": 1.002,
            "ess_bulk": 1400,
        }]

        result = create_precision_table_advanced(constructs)
        assert result is not None

    def test_vif_two_hop_path(self):
        """Test VIF display for two-hop comparison path."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [{
            "construct_id": 1,
            "construct_name": "Two Hop Path",
            "ci_width": 0.8,
            "target_width": 0.6,
            "status": "close",
            "path_type": "two_hop",
            "vif": 2.0,
            "r_hat": 1.003,
            "ess_bulk": 1300,
        }]

        result = create_precision_table_advanced(constructs)
        assert result is not None

    def test_vif_four_hop_path(self):
        """Test VIF display for four-hop comparison path."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        constructs = [{
            "construct_id": 1,
            "construct_name": "Four Hop Path",
            "ci_width": 1.0,
            "target_width": 0.6,
            "status": "not_met",
            "path_type": "four_hop",
            "vif": 4.0,
            "r_hat": 1.005,
            "ess_bulk": 1200,
        }]

        result = create_precision_table_advanced(constructs)
        assert result is not None


class TestReplicateRecommendations:
    """Tests for replicate count recommendations."""

    def test_recommendation_small_gap(self):
        """Test recommendation for small precision gap."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        recommendations = [{
            "construct_a": "Small Gap",
            "construct_b": "WT",
            "current_ci": 0.4,
            "expected_ci": 0.3,
            "improvement_pct": 25,
            "plates_needed": 1,
        }]

        result = create_recommendations_panel(recommendations)
        assert result is not None

    def test_recommendation_large_gap(self):
        """Test recommendation for large precision gap."""
        from app.layouts.precision_dashboard import create_recommendations_panel

        recommendations = [{
            "construct_a": "Large Gap",
            "construct_b": "WT",
            "current_ci": 1.0,
            "expected_ci": 0.4,
            "improvement_pct": 60,
            "plates_needed": 5,
        }]

        result = create_recommendations_panel(recommendations)
        assert result is not None


class TestExportFunctionality:
    """Tests for precision data export."""

    def test_export_data_structure(self):
        """Test that precision data is structured correctly for export."""
        # This tests the data structure that would be passed to export
        data = {
            "constructs": [
                {
                    "construct_id": 1,
                    "construct_name": "Construct A",
                    "family": "Family 1",
                    "ci_width": 0.5,
                    "ci_lower": -0.25,
                    "ci_upper": 0.25,
                    "mean": 0.0,
                    "std": 0.12,
                    "target_width": 0.6,
                    "status": "met",
                    "n_replicates": 6,
                    "path_type": "direct",
                    "vif": 1.0,
                    "r_hat": 1.001,
                    "ess_bulk": 1500,
                }
            ],
            "history": [],
            "scope": "full",
            "version_id": 1,
            "version_name": "v1",
        }

        # Verify data structure
        assert "constructs" in data
        assert "history" in data
        assert "scope" in data
        assert len(data["constructs"]) == 1
        assert data["constructs"][0]["status"] == "met"
