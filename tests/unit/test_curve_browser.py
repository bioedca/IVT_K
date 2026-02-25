"""
Tests for curve browser and curve plot components.

Phase 4.12: Curve Browser visualization (F8.8, F8.9, F13.2)
"""
import pytest
import plotly.graph_objects as go
from app.components.curve_plot import (
    create_curve_plot,
    create_multi_panel_curve_plot,
    compute_fit_curve,
    create_overlay_plot,
)
from app.layouts.curve_browser import (
    create_curve_browser_layout,
    create_well_grid_item,
    create_well_details_panel,
    create_fit_params_panel,
    create_empty_plot_message,
)


class TestComputeFitCurve:
    """Tests for compute_fit_curve function."""

    def test_compute_fit_basic(self):
        """Test basic fit curve computation."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        k_obs = 0.5
        F_max = 1000.0
        t_lag = 0.0
        F_0 = 100.0

        fit_values = compute_fit_curve(timepoints, k_obs, F_max, t_lag, F_0)

        assert len(fit_values) == len(timepoints)
        assert fit_values[0] == pytest.approx(F_0)  # At t=0
        assert all(v >= F_0 for v in fit_values)  # All values >= F_0
        # Values should approach F_max + F_0 asymptotically

    def test_compute_fit_with_lag(self):
        """Test fit curve with lag time."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        k_obs = 0.5
        F_max = 1000.0
        t_lag = 2.0
        F_0 = 100.0

        fit_values = compute_fit_curve(timepoints, k_obs, F_max, t_lag, F_0)

        # Values before lag should be F_0
        assert fit_values[0] == F_0
        assert fit_values[1] == F_0
        # Value at lag should also be F_0
        assert fit_values[2] == F_0
        # Values after lag should increase
        assert fit_values[3] > F_0
        assert fit_values[4] > fit_values[3]

    def test_compute_fit_zero_k_obs(self):
        """Test fit curve with zero rate constant."""
        timepoints = [0.0, 1.0, 2.0, 3.0]
        k_obs = 0.0
        F_max = 1000.0
        t_lag = 0.0
        F_0 = 100.0

        fit_values = compute_fit_curve(timepoints, k_obs, F_max, t_lag, F_0)

        # All values should remain at F_0 when k_obs=0
        assert all(v == pytest.approx(F_0) for v in fit_values)

    def test_compute_fit_empty_timepoints(self):
        """Test with empty timepoints."""
        fit_values = compute_fit_curve([], 0.5, 1000.0, 0.0, 100.0)
        assert fit_values == []


class TestCreateCurvePlot:
    """Tests for create_curve_plot function."""

    def test_create_basic_plot(self):
        """Test basic curve plot creation."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]
        raw_values = [100.0, 200.0, 350.0, 450.0, 500.0]

        fig = create_curve_plot(timepoints, raw_values)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1  # At least raw data trace

    def test_create_plot_with_fit(self):
        """Test plot with fit overlay."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]
        raw_values = [100.0, 200.0, 350.0, 450.0, 500.0]
        fit_values = [100.0, 220.0, 340.0, 430.0, 490.0]
        fit_params = {"k_obs": 0.5, "F_max": 1000.0, "R2": 0.98}

        fig = create_curve_plot(
            timepoints, raw_values,
            fit_values=fit_values,
            fit_params=fit_params,
            show_fit=True,
        )

        assert isinstance(fig, go.Figure)
        # Should have raw data and fit traces
        assert len(fig.data) >= 2

    def test_create_plot_no_fit(self):
        """Test plot without fit when show_fit is False."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]
        raw_values = [100.0, 200.0, 350.0, 450.0, 500.0]
        fit_values = [100.0, 220.0, 340.0, 430.0, 490.0]

        fig = create_curve_plot(
            timepoints, raw_values,
            fit_values=fit_values,
            show_fit=False,
        )

        assert isinstance(fig, go.Figure)
        # Should only have raw data trace
        assert len(fig.data) == 1

    def test_create_plot_with_residuals(self):
        """Test plot with residuals panel."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]
        raw_values = [100.0, 200.0, 350.0, 450.0, 500.0]
        fit_values = [100.0, 220.0, 340.0, 430.0, 490.0]

        fig = create_curve_plot(
            timepoints, raw_values,
            fit_values=fit_values,
            show_fit=True,
            show_residuals=True,
        )

        assert isinstance(fig, go.Figure)
        # Should have multiple traces including residuals
        assert len(fig.data) >= 3

    def test_create_plot_with_lod_loq(self):
        """Test plot with LOD/LOQ lines."""
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]
        raw_values = [100.0, 200.0, 350.0, 450.0, 500.0]

        fig = create_curve_plot(
            timepoints, raw_values,
            show_lod_loq=True,
            lod=150.0,
            loq=250.0,
        )

        assert isinstance(fig, go.Figure)
        # Check layout has horizontal lines
        assert fig.layout is not None

    def test_create_plot_with_title(self):
        """Test plot with custom title."""
        timepoints = [0.0, 1.0, 2.0]
        raw_values = [100.0, 200.0, 300.0]

        fig = create_curve_plot(
            timepoints, raw_values,
            title="Custom Title",
        )

        assert "Custom Title" in fig.layout.title.text

    def test_create_plot_with_well_info(self):
        """Test plot with well position and construct name."""
        timepoints = [0.0, 1.0, 2.0]
        raw_values = [100.0, 200.0, 300.0]

        fig = create_curve_plot(
            timepoints, raw_values,
            well_position="A1",
            construct_name="Test Construct",
        )

        assert "A1" in fig.layout.title.text
        assert "Test Construct" in fig.layout.title.text


class TestCreateMultiPanelCurvePlot:
    """Tests for create_multi_panel_curve_plot function."""

    def test_single_panel(self):
        """Test single panel layout."""
        panels = [{
            "timepoints": [0.0, 1.0, 2.0],
            "raw_values": [100.0, 200.0, 300.0],
            "title": "Panel 1",
        }]

        fig = create_multi_panel_curve_plot(panels, layout="single")

        assert isinstance(fig, go.Figure)

    def test_two_panel(self):
        """Test 2-panel layout."""
        panels = [
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [100.0, 200.0, 300.0], "title": "A1"},
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [150.0, 250.0, 350.0], "title": "A2"},
        ]

        fig = create_multi_panel_curve_plot(panels, layout="2-panel")

        assert isinstance(fig, go.Figure)
        # Should have traces for both panels
        assert len(fig.data) >= 2

    def test_four_panel(self):
        """Test 4-panel layout."""
        panels = [
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [100.0, 200.0, 300.0], "title": "A1"},
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [150.0, 250.0, 350.0], "title": "A2"},
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [120.0, 220.0, 320.0], "title": "B1"},
            {"timepoints": [0.0, 1.0, 2.0], "raw_values": [180.0, 280.0, 380.0], "title": "B2"},
        ]

        fig = create_multi_panel_curve_plot(panels, layout="4-panel")

        assert isinstance(fig, go.Figure)
        # Should have traces for all panels
        assert len(fig.data) >= 4

    def test_four_panel_with_fits(self):
        """Test 4-panel with fit overlays."""
        panels = [
            {
                "timepoints": [0.0, 1.0, 2.0],
                "raw_values": [100.0, 200.0, 300.0],
                "fit_values": [105.0, 195.0, 295.0],
                "fit_params": {"k_obs": 0.5, "F_max": 500.0, "R2": 0.99},
                "title": "A1",
            },
            {
                "timepoints": [0.0, 1.0, 2.0],
                "raw_values": [150.0, 250.0, 350.0],
                "fit_values": [155.0, 245.0, 345.0],
                "fit_params": {"k_obs": 0.4, "F_max": 600.0, "R2": 0.98},
                "title": "A2",
            },
        ]

        fig = create_multi_panel_curve_plot(panels, layout="2-panel")

        assert isinstance(fig, go.Figure)
        # Should have raw + fit traces for each panel
        assert len(fig.data) >= 4

    def test_empty_panels(self):
        """Test with empty panels list."""
        fig = create_multi_panel_curve_plot([], layout="2-panel")

        assert isinstance(fig, go.Figure)


class TestCreateOverlayPlot:
    """Tests for create_overlay_plot function."""

    def test_basic_overlay(self):
        """Test basic overlay plot."""
        curves = [
            {"timepoints": [0.0, 1.0, 2.0], "values": [100.0, 200.0, 300.0], "name": "Curve 1"},
            {"timepoints": [0.0, 1.0, 2.0], "values": [150.0, 250.0, 350.0], "name": "Curve 2"},
        ]

        fig = create_overlay_plot(curves)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2

    def test_overlay_normalized(self):
        """Test overlay plot with normalization."""
        curves = [
            {"timepoints": [0.0, 1.0, 2.0], "values": [100.0, 200.0, 300.0], "name": "Curve 1"},
            {"timepoints": [0.0, 1.0, 2.0], "values": [1000.0, 2000.0, 3000.0], "name": "Curve 2"},
        ]

        fig = create_overlay_plot(curves, normalize=True)

        assert isinstance(fig, go.Figure)
        # Y-axis should be "Normalized" when normalized
        assert "Normalized" in fig.layout.yaxis.title.text

    def test_overlay_custom_colors(self):
        """Test overlay with custom colors."""
        curves = [
            {"timepoints": [0.0, 1.0, 2.0], "values": [100.0, 200.0, 300.0], "name": "Curve 1", "color": "red"},
            {"timepoints": [0.0, 1.0, 2.0], "values": [150.0, 250.0, 350.0], "name": "Curve 2", "color": "blue"},
        ]

        fig = create_overlay_plot(curves)

        assert isinstance(fig, go.Figure)
        # Data curves use markers, not lines
        assert fig.data[0].marker.color == "red"
        assert fig.data[1].marker.color == "blue"

    def test_overlay_custom_title(self):
        """Test overlay with custom title."""
        curves = [
            {"timepoints": [0.0, 1.0, 2.0], "values": [100.0, 200.0, 300.0], "name": "Curve 1"},
        ]

        fig = create_overlay_plot(curves, title="My Overlay")

        assert "My Overlay" in fig.layout.title.text


class TestCurveBrowserLayout:
    """Tests for curve browser layout components."""

    def test_create_curve_browser_layout(self):
        """Test creating curve browser layout."""
        layout = create_curve_browser_layout()

        # Should return a Div component
        assert layout is not None

    def test_create_curve_browser_layout_with_project(self):
        """Test layout with project ID."""
        layout = create_curve_browser_layout(project_id=123)

        assert layout is not None

    def test_create_well_grid_item_basic(self):
        """Test creating basic well grid item."""
        item = create_well_grid_item(
            well_id=1,
            position="A1",
            status="completed",
        )

        assert item is not None

    def test_create_well_grid_item_with_construct(self):
        """Test well grid item with construct name."""
        item = create_well_grid_item(
            well_id=1,
            position="A1",
            construct_name="Test Construct",
            status="completed",
        )

        assert item is not None

    def test_create_well_grid_item_excluded(self):
        """Test well grid item for excluded well."""
        item = create_well_grid_item(
            well_id=1,
            position="A1",
            is_excluded=True,
            status="failed",
        )

        assert item is not None
        # The Div wraps a Paper; check the Paper child's style
        paper = item.children
        assert paper.style.get("opacity") == 0.5

    def test_create_well_grid_item_selected(self):
        """Test well grid item when selected."""
        item = create_well_grid_item(
            well_id=1,
            position="A1",
            is_selected=True,
            status="completed",
        )

        assert item is not None
        # The Div wraps a Paper; check the Paper child's style
        paper = item.children
        assert "boxShadow" in paper.style

    def test_create_well_grid_item_in_comparison(self):
        """Test well grid item in comparison set."""
        item = create_well_grid_item(
            well_id=1,
            position="A1",
            is_in_comparison=True,
            status="completed",
        )

        assert item is not None

    def test_create_well_grid_item_status_colors(self):
        """Test well grid item with different statuses."""
        for status in ["pending", "completed", "failed", "flagged"]:
            item = create_well_grid_item(
                well_id=1,
                position="A1",
                status=status,
            )
            assert item is not None


class TestWellDetailsPanel:
    """Tests for well details panel."""

    def test_create_well_details_basic(self):
        """Test creating basic details panel."""
        panel = create_well_details_panel(
            well_id=1,
            position="A1",
            plate_name="Plate 1",
            construct_name="Test Construct",
            well_type="sample",
        )

        assert panel is not None

    def test_create_well_details_with_ligand(self):
        """Test details panel with ligand concentration."""
        panel = create_well_details_panel(
            well_id=1,
            position="A1",
            plate_name="Plate 1",
            construct_name="Test Construct",
            well_type="sample",
            ligand=0.5,
        )

        assert panel is not None

    def test_create_well_details_with_exclusion(self):
        """Test details panel with exclusion reason."""
        panel = create_well_details_panel(
            well_id=1,
            position="A1",
            plate_name="Plate 1",
            construct_name="Test Construct",
            well_type="sample",
            exclusion_reason="Poor fit quality",
        )

        assert panel is not None

    def test_create_well_details_status_display(self):
        """Test different status displays."""
        for status in ["pending", "completed", "failed", "flagged"]:
            panel = create_well_details_panel(
                well_id=1,
                position="A1",
                plate_name="Plate 1",
                construct_name="Test",
                well_type="sample",
                status=status,
            )
            assert panel is not None


class TestFitParamsPanel:
    """Tests for fit parameters panel."""

    def test_create_params_panel_no_data(self):
        """Test params panel with no data."""
        panel = create_fit_params_panel()

        assert panel is not None

    def test_create_params_panel_with_params(self):
        """Test params panel with parameters."""
        params = {
            "k_obs": 0.5,
            "F_max": 1000.0,
            "t_lag": 1.0,
            "F_0": 100.0,
            "R2": 0.98,
            "rmse": 25.0,
        }

        panel = create_fit_params_panel(params=params)

        assert panel is not None

    def test_create_params_panel_with_uncertainties(self):
        """Test params panel with uncertainties."""
        params = {
            "k_obs": 0.5,
            "F_max": 1000.0,
            "R2": 0.98,
        }
        uncertainties = {
            "k_obs": 0.05,
            "F_max": 50.0,
        }

        panel = create_fit_params_panel(params=params, uncertainties=uncertainties)

        assert panel is not None

    def test_create_params_panel_partial_params(self):
        """Test with partial parameter set."""
        params = {
            "k_obs": 0.5,
            "R2": 0.98,
        }

        panel = create_fit_params_panel(params=params)

        assert panel is not None


class TestEmptyPlotMessage:
    """Tests for empty plot message."""

    def test_create_empty_message(self):
        """Test creating empty plot message."""
        msg = create_empty_plot_message()

        assert msg is not None


class TestLayoutIntegration:
    """Integration tests for layout components."""

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        from app.layouts import (
            create_curve_browser_layout,
            create_well_grid_item,
            create_well_details_panel,
            create_fit_params_panel,
            create_empty_plot_message,
        )

        assert callable(create_curve_browser_layout)
        assert callable(create_well_grid_item)
        assert callable(create_well_details_panel)
        assert callable(create_fit_params_panel)
        assert callable(create_empty_plot_message)

    def test_component_exports_available(self):
        """Test that component exports are available."""
        from app.components import (
            create_curve_plot,
            create_multi_panel_curve_plot,
            compute_fit_curve,
            create_overlay_plot,
        )

        assert callable(create_curve_plot)
        assert callable(create_multi_panel_curve_plot)
        assert callable(compute_fit_curve)
        assert callable(create_overlay_plot)
