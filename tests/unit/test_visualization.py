"""
Unit tests for visualization components.

Phase 8.1-8.4: Plate Heatmaps, Forest & Violin Plots
"""
import pytest
import numpy as np
import plotly.graph_objects as go


class TestPlateHeatmap:
    """Tests for plate heatmap components."""

    def test_create_plate_heatmap_96_well(self):
        """Test 96-well plate heatmap creation."""
        from app.components.plate_heatmap import create_plate_heatmap

        data = {f"{chr(65+r)}{c+1}": r * 12 + c for r in range(8) for c in range(12)}
        fig = create_plate_heatmap(data, plate_format=96)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_create_plate_heatmap_384_well(self):
        """Test 384-well plate heatmap creation."""
        from app.components.plate_heatmap import create_plate_heatmap

        data = {f"{chr(65+r)}{c+1}": r * 24 + c for r in range(16) for c in range(24)}
        fig = create_plate_heatmap(data, plate_format=384)

        assert isinstance(fig, go.Figure)

    def test_create_plate_heatmap_sparse(self):
        """Test heatmap with sparse data."""
        from app.components.plate_heatmap import create_plate_heatmap

        data = {"A1": 1.0, "H12": 2.0}
        fig = create_plate_heatmap(data, plate_format=96)

        assert isinstance(fig, go.Figure)

    def test_create_plate_heatmap_empty(self):
        """Test heatmap with empty data."""
        from app.components.plate_heatmap import create_plate_heatmap

        fig = create_plate_heatmap({}, plate_format=96)
        assert isinstance(fig, go.Figure)

    def test_create_completion_heatmap(self):
        """Test completion status heatmap."""
        from app.components.plate_heatmap import create_completion_heatmap

        data = {
            "A1": "complete",
            "A2": "near",
            "A3": "far",
            "A4": "pending",
        }
        fig = create_completion_heatmap(data, plate_format=96)

        assert isinstance(fig, go.Figure)

    def test_create_checkerboard_heatmap(self):
        """Test 384-well checkerboard heatmap."""
        from app.components.plate_heatmap import create_checkerboard_heatmap

        data = {f"{chr(65+r)}{c+1}": np.random.random()
                for r in range(16) for c in range(24)}
        fig = create_checkerboard_heatmap(data, plate_format=384)

        assert isinstance(fig, go.Figure)

    def test_well_to_coords(self):
        """Test well position to coordinates conversion."""
        from app.components.plate_heatmap import well_to_coords

        assert well_to_coords("A1", 96) == (0, 0)
        assert well_to_coords("H12", 96) == (7, 11)
        assert well_to_coords("P24", 384) == (15, 23)

    def test_kobs_heatmap(self):
        """Test k_obs heatmap creation."""
        from app.components.plate_heatmap import create_kobs_heatmap

        data = {"A1": 0.1, "A2": 0.2, "B1": 0.15}
        fig = create_kobs_heatmap(data)

        assert isinstance(fig, go.Figure)

    def test_fmax_heatmap(self):
        """Test F_max heatmap creation."""
        from app.components.plate_heatmap import create_fmax_heatmap

        data = {"A1": 50000, "A2": 45000, "B1": 48000}
        fig = create_fmax_heatmap(data)

        assert isinstance(fig, go.Figure)

    def test_rsquared_heatmap(self):
        """Test R-squared heatmap creation."""
        from app.components.plate_heatmap import create_rsquared_heatmap

        data = {"A1": 0.99, "A2": 0.85, "B1": 0.95}
        fig = create_rsquared_heatmap(data)

        assert isinstance(fig, go.Figure)


class TestForestPlot:
    """Tests for forest plot components."""

    def test_create_forest_plot_basic(self):
        """Test basic forest plot creation."""
        from app.components.forest_plot import create_forest_plot

        constructs = [
            {"name": "Mutant A", "mean": 1.5, "ci_lower": 1.0, "ci_upper": 2.0, "vif": 1.0},
            {"name": "Mutant B", "mean": -0.5, "ci_lower": -1.0, "ci_upper": 0.0, "vif": 1.414},
        ]
        fig = create_forest_plot(constructs)

        assert isinstance(fig, go.Figure)

    def test_create_forest_plot_empty(self):
        """Test forest plot with no data."""
        from app.components.forest_plot import create_forest_plot

        fig = create_forest_plot([])
        assert isinstance(fig, go.Figure)

    def test_create_forest_plot_with_family_grouping(self):
        """Test forest plot grouped by family."""
        from app.components.forest_plot import create_forest_plot

        constructs = [
            {"name": "Family1 WT", "family": "Family1", "mean": 0, "ci_lower": -0.2, "ci_upper": 0.2, "vif": 1.0, "is_wt": True},
            {"name": "Family1 Mut", "family": "Family1", "mean": 1.0, "ci_lower": 0.5, "ci_upper": 1.5, "vif": 1.0, "is_wt": False},
            {"name": "Family2 WT", "family": "Family2", "mean": 0.1, "ci_lower": -0.1, "ci_upper": 0.3, "vif": 1.0, "is_wt": True},
        ]
        fig = create_forest_plot(constructs, group_by="family")

        assert isinstance(fig, go.Figure)

    def test_create_forest_plot_sort_options(self):
        """Test forest plot sort options."""
        from app.components.forest_plot import create_forest_plot

        constructs = [
            {"name": "Z Mutant", "mean": 0.5, "ci_lower": 0, "ci_upper": 1.0, "vif": 1.0},
            {"name": "A Mutant", "mean": 1.5, "ci_lower": 1.0, "ci_upper": 2.0, "vif": 1.0},
        ]

        # Sort by effect size
        fig = create_forest_plot(constructs, sort_by="effect_size")
        assert isinstance(fig, go.Figure)

        # Sort alphabetically
        fig = create_forest_plot(constructs, sort_by="alphabetical")
        assert isinstance(fig, go.Figure)

    def test_create_forest_plot_vif_badges(self):
        """Test forest plot VIF badge display."""
        from app.components.forest_plot import create_forest_plot

        constructs = [
            {"name": "Direct", "mean": 1.0, "ci_lower": 0.5, "ci_upper": 1.5, "vif": 1.0},
            {"name": "One Hop", "mean": 0.8, "ci_lower": 0.2, "ci_upper": 1.4, "vif": 1.414},
            {"name": "Two Hop", "mean": 0.6, "ci_lower": 0.0, "ci_upper": 1.2, "vif": 2.0},
            {"name": "Four Hop", "mean": 0.4, "ci_lower": -0.4, "ci_upper": 1.2, "vif": 4.0},
        ]
        fig = create_forest_plot(constructs, show_vif_badges=True)

        assert isinstance(fig, go.Figure)

    def test_get_vif_color(self):
        """Test VIF color mapping."""
        from app.components.forest_plot import get_vif_color

        assert get_vif_color(1.0) == "#40c057"  # Green
        assert get_vif_color(1.5) == "#fab005"  # Yellow
        assert get_vif_color(2.0) == "#fd7e14"  # Orange
        assert get_vif_color(4.0) == "#fa5252"  # Red

    def test_get_vif_label(self):
        """Test VIF label mapping."""
        from app.components.forest_plot import get_vif_label

        assert get_vif_label(1.0) == "Direct"
        assert get_vif_label(1.414) == "1-hop"
        assert get_vif_label(2.0) == "2-hop"
        assert get_vif_label(4.0) == "4-hop"

    def test_create_snr_forest_plot(self):
        """Test SNR forest plot creation."""
        from app.components.forest_plot import create_snr_forest_plot

        constructs = [
            {"name": "High SNR", "snr": 25},
            {"name": "Good SNR", "snr": 15},
            {"name": "Marginal SNR", "snr": 7},
            {"name": "Poor SNR", "snr": 3},
        ]
        fig = create_snr_forest_plot(constructs)

        assert isinstance(fig, go.Figure)

    def test_create_dual_forest_plot(self):
        """Test dual forest plot (FC + SNR)."""
        from app.components.forest_plot import create_dual_forest_plot

        constructs = [
            {"name": "Construct A", "mean": 1.0, "ci_lower": 0.5, "ci_upper": 1.5, "vif": 1.0, "snr": 20},
            {"name": "Construct B", "mean": 0.5, "ci_lower": 0.0, "ci_upper": 1.0, "vif": 1.414, "snr": 12},
        ]
        fig = create_dual_forest_plot(constructs)

        assert isinstance(fig, go.Figure)

    def test_create_progress_forest_plot(self):
        """Test precision progress forest plot."""
        from app.components.forest_plot import create_progress_forest_plot

        history = [
            {"date": "2024-01-01", "mean": 1.0, "ci_lower": 0.2, "ci_upper": 1.8},
            {"date": "2024-01-15", "mean": 1.0, "ci_lower": 0.4, "ci_upper": 1.6},
            {"date": "2024-01-29", "mean": 1.0, "ci_lower": 0.6, "ci_upper": 1.4},
        ]
        fig = create_progress_forest_plot(history, "Construct A")

        assert isinstance(fig, go.Figure)


class TestViolinPlot:
    """Tests for violin plot components."""

    def test_create_violin_plot_basic(self):
        """Test basic violin plot creation."""
        from app.components.violin_plot import create_violin_plot

        distributions = [
            {"name": "Group A", "samples": np.random.normal(0, 1, 1000).tolist()},
            {"name": "Group B", "samples": np.random.normal(1, 1, 1000).tolist()},
        ]
        fig = create_violin_plot(distributions)

        assert isinstance(fig, go.Figure)

    def test_create_violin_plot_empty(self):
        """Test violin plot with no data."""
        from app.components.violin_plot import create_violin_plot

        fig = create_violin_plot([])
        assert isinstance(fig, go.Figure)

    def test_create_violin_plot_with_box(self):
        """Test violin plot with box plot inside."""
        from app.components.violin_plot import create_violin_plot

        distributions = [
            {"name": "Group A", "samples": np.random.normal(0, 1, 500).tolist()},
        ]
        fig = create_violin_plot(distributions, show_box=True)

        assert isinstance(fig, go.Figure)

    def test_create_paired_violin_plot(self):
        """Test paired violin plot."""
        from app.components.violin_plot import create_paired_violin_plot

        groups = [
            {
                "name": "Construct A",
                "condition_a": {"name": "Before", "samples": np.random.normal(0, 1, 500).tolist()},
                "condition_b": {"name": "After", "samples": np.random.normal(1, 1, 500).tolist()},
            },
        ]
        fig = create_paired_violin_plot(groups)

        assert isinstance(fig, go.Figure)

    def test_create_completion_matrix(self):
        """Test completion matrix creation."""
        from app.components.violin_plot import create_completion_matrix

        constructs = [
            {"name": "Construct A", "sessions": {"Session 1": "complete", "Session 2": "near"}},
            {"name": "Construct B", "sessions": {"Session 1": "far", "Session 2": "pending"}},
        ]
        sessions = ["Session 1", "Session 2"]
        fig = create_completion_matrix(constructs, sessions)

        assert isinstance(fig, go.Figure)

    def test_create_distribution_comparison(self):
        """Test distribution comparison plot."""
        from app.components.violin_plot import create_distribution_comparison

        construct_a = {
            "name": "Mutant",
            "samples": np.random.normal(1, 0.3, 1000).tolist(),
            "mean": 1.0,
            "ci_lower": 0.4,
            "ci_upper": 1.6,
        }
        construct_b = {
            "name": "Wild-type",
            "samples": np.random.normal(0, 0.3, 1000).tolist(),
            "mean": 0.0,
            "ci_lower": -0.6,
            "ci_upper": 0.6,
        }
        fig = create_distribution_comparison(construct_a, construct_b)

        assert isinstance(fig, go.Figure)

    def test_create_qq_plot(self):
        """Test Q-Q plot creation."""
        from app.components.violin_plot import create_qq_plot

        samples = np.random.normal(0, 1, 500).tolist()
        fig = create_qq_plot(samples)

        assert isinstance(fig, go.Figure)

    def test_create_qq_plot_insufficient_samples(self):
        """Test Q-Q plot with too few samples."""
        from app.components.violin_plot import create_qq_plot

        fig = create_qq_plot([1, 2])
        assert isinstance(fig, go.Figure)

    def test_create_residual_distribution(self):
        """Test residual distribution plot."""
        from app.components.violin_plot import create_residual_distribution

        residuals = np.random.normal(0, 0.1, 500).tolist()
        fig = create_residual_distribution(residuals)

        assert isinstance(fig, go.Figure)


class TestFigureExport:
    """Tests for figure export functionality."""

    def test_export_figure_png(self):
        """Test PNG export."""
        from app.services.export_service import ExportService

        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        try:
            png_bytes = ExportService.export_figure_png(fig)
            assert isinstance(png_bytes, bytes)
            assert len(png_bytes) > 0
            # Check PNG magic bytes
            assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'
        except RuntimeError:
            # Kaleido not installed - skip
            pytest.skip("Kaleido not installed")

    def test_export_figure_svg(self):
        """Test SVG export."""
        from app.services.export_service import ExportService

        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        try:
            svg_str = ExportService.export_figure_svg(fig)
            assert isinstance(svg_str, str)
            assert "<svg" in svg_str
        except RuntimeError:
            pytest.skip("Kaleido not installed")

    def test_export_figure_pdf(self):
        """Test PDF export."""
        from app.services.export_service import ExportService

        fig = go.Figure(data=go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        try:
            pdf_bytes = ExportService.export_figure_pdf(fig)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 0
            # Check PDF magic bytes
            assert pdf_bytes[:4] == b'%PDF'
        except RuntimeError:
            pytest.skip("Kaleido not installed")

    def test_get_figure_dimensions(self):
        """Test getting figure dimensions."""
        from app.services.export_service import ExportService

        fig = go.Figure()
        fig.update_layout(width=800, height=600)

        dims = ExportService.get_figure_dimensions(fig)
        assert dims["width"] == 800
        assert dims["height"] == 600


class TestHelpPanel:
    """Tests for help panel components."""

    def test_create_help_panel(self):
        """Test help panel creation."""
        from app.components.help_panel import create_help_panel

        panel = create_help_panel("plate_layout")
        assert panel is not None

    def test_create_help_panel_unknown(self):
        """Test help panel for unknown topic."""
        from app.components.help_panel import create_help_panel

        panel = create_help_panel("unknown_topic")
        assert panel is not None  # Should return placeholder

    def test_load_tooltips(self):
        """Test tooltip loading."""
        from app.components.help_panel import load_tooltips

        tooltips = load_tooltips()
        assert isinstance(tooltips, dict)
        # Check for some expected tooltips
        assert "vif" in tooltips
        assert "lod" in tooltips

    def test_load_glossary(self):
        """Test glossary loading."""
        from app.components.help_panel import load_glossary

        glossary = load_glossary()
        assert isinstance(glossary, dict)

    def test_create_tooltip(self):
        """Test tooltip creation."""
        from app.components.help_panel import create_tooltip
        import dash_mantine_components as dmc

        tooltip = create_tooltip("vif", dmc.Text("VIF"))
        assert tooltip is not None

    def test_create_info_icon_with_tooltip(self):
        """Test info icon with tooltip."""
        from app.components.help_panel import create_info_icon_with_tooltip

        icon = create_info_icon_with_tooltip("vif")
        assert icon is not None

    def test_create_quick_help(self):
        """Test quick help creation."""
        from app.components.help_panel import create_quick_help

        items = [
            {"icon": "mdi:information", "title": "Tip 1", "description": "First tip"},
            {"icon": "mdi:lightbulb", "title": "Tip 2", "description": "Second tip"},
        ]
        help_section = create_quick_help(items)
        assert help_section is not None

    def test_create_getting_started_layout(self):
        """Test getting started help page renders."""
        from app.layouts.help_pages import create_getting_started_layout

        layout = create_getting_started_layout()
        assert layout is not None

    def test_create_workflow_overview_layout(self):
        """Test workflow overview help page renders."""
        from app.layouts.help_pages import create_workflow_overview_layout

        layout = create_workflow_overview_layout()
        assert layout is not None
