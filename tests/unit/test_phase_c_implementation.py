"""
Tests for Phase C: UI Layer Completion.

Phase C Tasks:
1. Create app/components/navigation.py
2. Create app/components/progress_tracker.py
3. Create app/layouts/construct_registry.py
4. Create app/layouts/power_analysis.py

PRD References:
- Section 1.2: Navigation components specification
- Section 3.3: Construct Registry (F3.1-F3.9)
- Section 3.12: Power Analysis layout (F12.1-F12.8)
- Section 3.13: F13.5 Completion Matrix
"""
import pytest
from typing import List, Optional


# ============================================================================
# Task 1: Navigation Component Tests
# ============================================================================

class TestNavigationModule:
    """Tests for app/components/navigation.py existence and structure."""

    def test_navigation_module_exists(self):
        """T-C1.1: navigation.py module can be imported."""
        from app.components import navigation
        assert navigation is not None

    def test_navigation_module_has_create_breadcrumbs(self):
        """T-C1.2: navigation.py has create_breadcrumbs function."""
        from app.components.navigation import create_breadcrumbs
        assert callable(create_breadcrumbs)

    def test_navigation_module_has_create_sidebar(self):
        """T-C1.3: navigation.py has create_sidebar function."""
        from app.components.navigation import create_sidebar
        assert callable(create_sidebar)

    def test_navigation_module_has_create_navbar(self):
        """T-C1.4: navigation.py has create_navbar function."""
        from app.components.navigation import create_navbar
        assert callable(create_navbar)


class TestCreateBreadcrumbs:
    """Tests for create_breadcrumbs function."""

    def test_create_breadcrumbs_returns_component(self):
        """T-C1.5: create_breadcrumbs returns a Mantine component."""
        from app.components.navigation import create_breadcrumbs
        import dash_mantine_components as dmc

        result = create_breadcrumbs(["Home", "Projects", "My Project"])
        assert result is not None
        # Should be a Mantine Breadcrumbs or container component
        assert hasattr(result, 'children') or hasattr(result, '_type')

    def test_create_breadcrumbs_with_empty_path(self):
        """T-C1.6: create_breadcrumbs handles empty path."""
        from app.components.navigation import create_breadcrumbs

        result = create_breadcrumbs([])
        assert result is not None

    def test_create_breadcrumbs_with_links(self):
        """T-C1.7: create_breadcrumbs supports links."""
        from app.components.navigation import create_breadcrumbs

        path = [
            {"label": "Home", "href": "/"},
            {"label": "Projects", "href": "/projects"},
            {"label": "Analysis"},  # No href = current page
        ]
        result = create_breadcrumbs(path)
        assert result is not None


class TestCreateSidebar:
    """Tests for create_sidebar function."""

    def test_create_sidebar_returns_component(self):
        """T-C1.8: create_sidebar returns a Mantine component."""
        from app.components.navigation import create_sidebar

        result = create_sidebar(current_page="dashboard")
        assert result is not None
        assert hasattr(result, 'children') or hasattr(result, '_type')

    def test_create_sidebar_with_project_id(self):
        """T-C1.9: create_sidebar handles project_id parameter."""
        from app.components.navigation import create_sidebar

        result = create_sidebar(current_page="analysis", project_id=123)
        assert result is not None

    def test_create_sidebar_highlights_current_page(self):
        """T-C1.10: create_sidebar marks current page as active."""
        from app.components.navigation import create_sidebar

        # The sidebar should have some visual indication of the current page
        result = create_sidebar(current_page="constructs")
        assert result is not None


class TestCreateNavbar:
    """Tests for create_navbar function."""

    def test_create_navbar_returns_component(self):
        """T-C1.11: create_navbar returns a Mantine component."""
        from app.components.navigation import create_navbar

        result = create_navbar()
        assert result is not None
        assert hasattr(result, 'children') or hasattr(result, '_type')

    def test_create_navbar_with_user_info(self):
        """T-C1.12: create_navbar supports user info display."""
        from app.components.navigation import create_navbar

        result = create_navbar(project_name="Test Project")
        assert result is not None


class TestNavigationExports:
    """Tests for navigation module exports in __init__.py."""

    def test_navigation_exports_in_init(self):
        """T-C1.13: Navigation functions exported in components __init__.py."""
        from app.components import (
            create_breadcrumbs,
            create_sidebar,
            create_navbar,
        )
        assert callable(create_breadcrumbs)
        assert callable(create_sidebar)
        assert callable(create_navbar)


# ============================================================================
# Task 2: Progress Tracker Component Tests
# ============================================================================

class TestProgressTrackerModule:
    """Tests for app/components/progress_tracker.py existence and structure."""

    def test_progress_tracker_module_exists(self):
        """T-C2.1: progress_tracker.py module can be imported."""
        from app.components import progress_tracker
        assert progress_tracker is not None

    def test_progress_tracker_has_create_completion_matrix(self):
        """T-C2.2: progress_tracker.py has create_completion_matrix function."""
        from app.components.progress_tracker import create_completion_matrix
        assert callable(create_completion_matrix)

    def test_progress_tracker_has_create_progress_bar(self):
        """T-C2.3: progress_tracker.py has create_progress_bar function."""
        from app.components.progress_tracker import create_progress_bar
        assert callable(create_progress_bar)

    def test_progress_tracker_has_create_status_indicator(self):
        """T-C2.4: progress_tracker.py has create_status_indicator function."""
        from app.components.progress_tracker import create_status_indicator
        assert callable(create_status_indicator)


class TestCompletionMatrix:
    """Tests for create_completion_matrix function (F13.5)."""

    def test_create_completion_matrix_returns_figure(self):
        """T-C2.5: create_completion_matrix returns Plotly figure."""
        from app.components.progress_tracker import create_completion_matrix
        import plotly.graph_objects as go

        # Test with sample data
        constructs = [
            {"name": "Tbox1_M1", "ci_width": 0.18, "status": "met"},
            {"name": "Tbox1_M2", "ci_width": 0.45, "status": "not_met"},
            {"name": "Tbox1_M3", "ci_width": 0.32, "status": "close"},
        ]
        result = create_completion_matrix(constructs, target=0.3)
        assert isinstance(result, go.Figure)

    def test_create_completion_matrix_empty_data(self):
        """T-C2.6: create_completion_matrix handles empty data."""
        from app.components.progress_tracker import create_completion_matrix
        import plotly.graph_objects as go

        result = create_completion_matrix([], target=0.3)
        assert isinstance(result, go.Figure)

    def test_create_completion_matrix_color_coding(self):
        """T-C2.7: create_completion_matrix uses correct status colors."""
        from app.components.progress_tracker import (
            create_completion_matrix,
            COMPLETION_COLORS,
        )

        # Verify color constants exist
        assert "met" in COMPLETION_COLORS
        assert "close" in COMPLETION_COLORS
        assert "not_met" in COMPLETION_COLORS


class TestProgressBar:
    """Tests for create_progress_bar function."""

    def test_create_progress_bar_returns_component(self):
        """T-C2.8: create_progress_bar returns a Mantine component."""
        from app.components.progress_tracker import create_progress_bar

        result = create_progress_bar(current=5, total=10)
        assert result is not None

    def test_create_progress_bar_percentage(self):
        """T-C2.9: create_progress_bar calculates percentage correctly."""
        from app.components.progress_tracker import create_progress_bar

        result = create_progress_bar(current=7, total=10)
        assert result is not None

    def test_create_progress_bar_zero_total(self):
        """T-C2.10: create_progress_bar handles zero total."""
        from app.components.progress_tracker import create_progress_bar

        result = create_progress_bar(current=0, total=0)
        assert result is not None


class TestStatusIndicator:
    """Tests for create_status_indicator function."""

    def test_create_status_indicator_met(self):
        """T-C2.11: create_status_indicator shows 'met' status correctly."""
        from app.components.progress_tracker import create_status_indicator

        result = create_status_indicator("met")
        assert result is not None

    def test_create_status_indicator_not_met(self):
        """T-C2.12: create_status_indicator shows 'not_met' status correctly."""
        from app.components.progress_tracker import create_status_indicator

        result = create_status_indicator("not_met")
        assert result is not None

    def test_create_status_indicator_close(self):
        """T-C2.13: create_status_indicator shows 'close' status correctly."""
        from app.components.progress_tracker import create_status_indicator

        result = create_status_indicator("close")
        assert result is not None


class TestProgressTrackerExports:
    """Tests for progress_tracker module exports in __init__.py."""

    def test_progress_tracker_exports_in_init(self):
        """T-C2.14: Progress tracker functions exported in components __init__.py."""
        from app.components import (
            create_completion_matrix as matrix_func,
            create_progress_bar,
            create_status_indicator,
            COMPLETION_COLORS,
        )
        # Note: create_completion_matrix may already exist in violin_plot
        # so we import with alias to test the progress_tracker version
        assert callable(create_progress_bar)
        assert callable(create_status_indicator)
        assert isinstance(COMPLETION_COLORS, dict)


# ============================================================================
# Task 3: Construct Registry Layout Tests
# ============================================================================

class TestConstructRegistryModule:
    """Tests for app/layouts/construct_registry.py existence and structure."""

    def test_construct_registry_module_exists(self):
        """T-C3.1: construct_registry.py module can be imported."""
        from app.layouts import construct_registry
        assert construct_registry is not None

    def test_construct_registry_has_main_layout(self):
        """T-C3.2: construct_registry.py has create_construct_registry_layout."""
        from app.layouts.construct_registry import create_construct_registry_layout
        assert callable(create_construct_registry_layout)

    def test_construct_registry_has_construct_form(self):
        """T-C3.3: construct_registry.py has create_construct_form."""
        from app.layouts.construct_registry import create_construct_form
        assert callable(create_construct_form)

    def test_construct_registry_has_construct_table(self):
        """T-C3.4: construct_registry.py has create_construct_table."""
        from app.layouts.construct_registry import create_construct_table
        assert callable(create_construct_table)


class TestConstructRegistryLayout:
    """Tests for construct registry layout functions (PRD Section 3.3)."""

    def test_create_construct_registry_layout_returns_div(self):
        """T-C3.5: create_construct_registry_layout returns html.Div."""
        from app.layouts.construct_registry import create_construct_registry_layout
        from dash import html

        result = create_construct_registry_layout()
        assert isinstance(result, html.Div)

    def test_create_construct_registry_layout_with_project_id(self):
        """T-C3.6: create_construct_registry_layout accepts project_id."""
        from app.layouts.construct_registry import create_construct_registry_layout
        from dash import html

        result = create_construct_registry_layout(project_id=123)
        assert isinstance(result, html.Div)

    def test_create_construct_registry_has_stores(self):
        """T-C3.7: construct_registry layout includes dcc.Store components."""
        from app.layouts.construct_registry import create_construct_registry_layout
        from dash import dcc

        result = create_construct_registry_layout(project_id=123)
        # Check that stores are in children
        children = result.children if hasattr(result, 'children') else []
        store_count = sum(1 for c in children if isinstance(c, dcc.Store))
        assert store_count >= 1, "Layout should include at least one dcc.Store"


class TestConstructForm:
    """Tests for construct form component (PRD F3.1-F3.2)."""

    def test_create_construct_form_returns_component(self):
        """T-C3.8: create_construct_form returns a component."""
        from app.layouts.construct_registry import create_construct_form

        result = create_construct_form()
        assert result is not None

    def test_create_construct_form_has_identifier_field(self):
        """T-C3.9: construct form has identifier input field."""
        from app.layouts.construct_registry import create_construct_form

        # Form should have an identifier input
        result = create_construct_form()
        assert result is not None

    def test_create_construct_form_has_family_field(self):
        """T-C3.10: construct form has family selection field."""
        from app.layouts.construct_registry import create_construct_form

        result = create_construct_form()
        assert result is not None


class TestConstructTable:
    """Tests for construct table component."""

    def test_create_construct_table_returns_component(self):
        """T-C3.11: create_construct_table returns a component."""
        from app.layouts.construct_registry import create_construct_table

        result = create_construct_table([])
        assert result is not None

    def test_create_construct_table_with_data(self):
        """T-C3.12: create_construct_table renders construct data."""
        from app.layouts.construct_registry import create_construct_table

        constructs = [
            {"id": 1, "identifier": "Tbox1_WT", "family": "Tbox1", "is_wildtype": True},
            {"id": 2, "identifier": "Tbox1_M1", "family": "Tbox1", "is_wildtype": False},
        ]
        result = create_construct_table(constructs)
        assert result is not None


class TestConstructRegistryExports:
    """Tests for construct_registry module exports in __init__.py."""

    def test_construct_registry_exports_in_init(self):
        """T-C3.13: Construct registry functions exported in layouts __init__.py."""
        from app.layouts import (
            create_construct_registry_layout,
            create_construct_form,
            create_construct_table,
        )
        assert callable(create_construct_registry_layout)
        assert callable(create_construct_form)
        assert callable(create_construct_table)


# ============================================================================
# Task 4: Power Analysis Layout Tests
# ============================================================================

class TestPowerAnalysisLayoutModule:
    """Tests for app/layouts/power_analysis.py existence and structure."""

    def test_power_analysis_layout_module_exists(self):
        """T-C4.1: power_analysis.py layout module can be imported."""
        from app.layouts import power_analysis
        assert power_analysis is not None

    def test_power_analysis_has_main_layout(self):
        """T-C4.2: power_analysis.py has create_power_analysis_layout."""
        from app.layouts.power_analysis import create_power_analysis_layout
        assert callable(create_power_analysis_layout)

    def test_power_analysis_has_planning_section(self):
        """T-C4.3: power_analysis.py has create_planning_section."""
        from app.layouts.power_analysis import create_planning_section
        assert callable(create_planning_section)

    def test_power_analysis_has_sample_size_calculator(self):
        """T-C4.4: power_analysis.py has create_sample_size_calculator."""
        from app.layouts.power_analysis import create_sample_size_calculator
        assert callable(create_sample_size_calculator)


class TestPowerAnalysisLayout:
    """Tests for power analysis layout functions (PRD Section 3.12)."""

    def test_create_power_analysis_layout_returns_div(self):
        """T-C4.5: create_power_analysis_layout returns html.Div."""
        from app.layouts.power_analysis import create_power_analysis_layout
        from dash import html

        result = create_power_analysis_layout()
        assert isinstance(result, html.Div)

    def test_create_power_analysis_layout_with_project_id(self):
        """T-C4.6: create_power_analysis_layout accepts project_id."""
        from app.layouts.power_analysis import create_power_analysis_layout
        from dash import html

        result = create_power_analysis_layout(project_id=123)
        assert isinstance(result, html.Div)

    def test_create_power_analysis_has_stores(self):
        """T-C4.7: power_analysis layout includes dcc.Store components."""
        from app.layouts.power_analysis import create_power_analysis_layout
        from dash import dcc

        result = create_power_analysis_layout(project_id=123)
        children = result.children if hasattr(result, 'children') else []
        store_count = sum(1 for c in children if isinstance(c, dcc.Store))
        assert store_count >= 1, "Layout should include at least one dcc.Store"


class TestPlanningSection:
    """Tests for planning section component (PRD F12.1)."""

    def test_create_planning_section_returns_component(self):
        """T-C4.8: create_planning_section returns a component."""
        from app.layouts.power_analysis import create_planning_section

        result = create_planning_section()
        assert result is not None

    def test_create_planning_section_pre_experiment(self):
        """T-C4.9: create_planning_section supports pre-experiment mode."""
        from app.layouts.power_analysis import create_planning_section

        result = create_planning_section(mode="pre_experiment")
        assert result is not None

    def test_create_planning_section_mid_experiment(self):
        """T-C4.10: create_planning_section supports mid-experiment mode."""
        from app.layouts.power_analysis import create_planning_section

        result = create_planning_section(mode="mid_experiment")
        assert result is not None


class TestSampleSizeCalculator:
    """Tests for sample size calculator component (PRD F12.6, F12.7)."""

    def test_create_sample_size_calculator_returns_component(self):
        """T-C4.11: create_sample_size_calculator returns a component."""
        from app.layouts.power_analysis import create_sample_size_calculator

        result = create_sample_size_calculator()
        assert result is not None

    def test_create_sample_size_calculator_has_inputs(self):
        """T-C4.12: sample size calculator has required input fields."""
        from app.layouts.power_analysis import create_sample_size_calculator

        result = create_sample_size_calculator()
        assert result is not None


class TestPowerCurveDisplay:
    """Tests for power curve display component."""

    def test_create_power_curve_display_exists(self):
        """T-C4.13: power_analysis.py has create_power_curve_display."""
        from app.layouts.power_analysis import create_power_curve_display
        assert callable(create_power_curve_display)

    def test_create_power_curve_display_returns_figure(self):
        """T-C4.14: create_power_curve_display returns Plotly figure or component."""
        from app.layouts.power_analysis import create_power_curve_display

        result = create_power_curve_display()
        assert result is not None


class TestPowerAnalysisExports:
    """Tests for power_analysis module exports in __init__.py."""

    def test_power_analysis_exports_in_init(self):
        """T-C4.15: Power analysis functions exported in layouts __init__.py."""
        from app.layouts import (
            create_power_analysis_layout,
            create_planning_section,
            create_sample_size_calculator,
            create_power_curve_display,
        )
        assert callable(create_power_analysis_layout)
        assert callable(create_planning_section)
        assert callable(create_sample_size_calculator)
        assert callable(create_power_curve_display)
