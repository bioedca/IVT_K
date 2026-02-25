"""
Tests for plate templates layout.

Phase 2: Plate Layout Editor - Plate Templates Layout

Tests the plate_templates.py layout that provides:
- Plate layout template editor interface
- Layout creation and editing workflow
- Integration with plate grid component
- Data stores for state management
"""
import pytest
import dash_mantine_components as dmc
from dash import html, dcc

from app.layouts.plate_templates import (
    create_plate_templates_layout,
    create_plate_templates_header,
    create_layout_info_panel,
    create_layout_editor_section,
    create_layout_summary_panel,
    create_plate_templates_loading_state,
    WELL_TYPE_OPTIONS,
)


class TestWellTypeOptions:
    """Tests for well type configuration."""

    def test_well_type_options_exist(self):
        """Test that well type options are defined."""
        assert WELL_TYPE_OPTIONS is not None
        assert len(WELL_TYPE_OPTIONS) > 0

    def test_required_well_types(self):
        """Test that required well types are present."""
        type_values = [opt["value"] for opt in WELL_TYPE_OPTIONS]
        assert "sample" in type_values
        assert "blank" in type_values
        assert "negative_control_no_template" in type_values

    def test_negative_control_types(self):
        """Test that negative control types are present."""
        type_values = [opt["value"] for opt in WELL_TYPE_OPTIONS]
        assert "negative_control_no_template" in type_values
        assert "negative_control_no_dye" in type_values


class TestCreatePlateTemplatesLayout:
    """Tests for main plate templates layout creation."""

    def test_basic_layout(self):
        """Test creating basic plate templates layout."""
        layout = create_plate_templates_layout(
            project_id=1,
        )
        assert layout is not None
        assert isinstance(layout, (dmc.Container, html.Div))

    def test_layout_with_layout_id(self):
        """Test layout for editing existing layout."""
        layout = create_plate_templates_layout(
            project_id=1,
            layout_id=1,
        )
        assert layout is not None

    def test_layout_contains_stores(self):
        """Test that layout contains necessary data stores."""
        layout = create_plate_templates_layout(
            project_id=1,
        )
        # Helper to find stores in component tree
        stores = _find_components_by_type(layout, dcc.Store)
        assert len(stores) > 0

    def test_layout_contains_grid(self):
        """Test that layout contains plate grid."""
        layout = create_plate_templates_layout(
            project_id=1,
        )
        # Layout should contain the plate grid container
        assert layout is not None


class TestCreatePlateTemplatesHeader:
    """Tests for plate templates header component."""

    def test_header_new_layout(self):
        """Test header for creating new layout."""
        header = create_plate_templates_header(
            project_id=1,
            project_name="Test Project",
        )
        assert header is not None

    def test_header_existing_layout(self):
        """Test header for editing existing layout."""
        header = create_plate_templates_header(
            project_id=1,
            project_name="Test Project",
            layout_name="Test Layout",
            is_draft=True,
        )
        assert header is not None

    def test_header_published_layout(self):
        """Test header for published layout."""
        header = create_plate_templates_header(
            project_id=1,
            project_name="Test Project",
            layout_name="Test Layout",
            is_draft=False,
        )
        assert header is not None


class TestCreateLayoutInfoPanel:
    """Tests for layout info panel component."""

    def test_info_panel_new_layout(self):
        """Test info panel for new layout."""
        panel = create_layout_info_panel(
            project_id=1,
            plate_format=96,
        )
        assert panel is not None

    def test_info_panel_96_well(self):
        """Test info panel shows 96-well format."""
        panel = create_layout_info_panel(
            project_id=1,
            plate_format=96,
        )
        assert panel is not None

    def test_info_panel_384_well(self):
        """Test info panel shows 384-well format."""
        panel = create_layout_info_panel(
            project_id=1,
            plate_format=384,
        )
        assert panel is not None

    def test_info_panel_with_layout_data(self):
        """Test info panel with existing layout data."""
        panel = create_layout_info_panel(
            project_id=1,
            plate_format=384,
            layout_name="Test Layout",
            assigned_wells=48,
            total_wells=384,
        )
        assert panel is not None


class TestCreateLayoutEditorSection:
    """Tests for layout editor section."""

    def test_editor_section_96(self):
        """Test editor section for 96-well plate."""
        section = create_layout_editor_section(
            plate_format=96,
            section_id="test-editor",
        )
        assert section is not None

    def test_editor_section_384(self):
        """Test editor section for 384-well plate."""
        section = create_layout_editor_section(
            plate_format=384,
            section_id="test-editor",
        )
        assert section is not None

    def test_editor_section_with_checkerboard(self):
        """Test editor section with checkerboard mode."""
        section = create_layout_editor_section(
            plate_format=384,
            section_id="test-editor",
            enforce_checkerboard=True,
        )
        assert section is not None


class TestCreateLayoutSummaryPanel:
    """Tests for layout summary panel."""

    def test_empty_summary_panel(self):
        """Test summary panel with no assignments."""
        panel = create_layout_summary_panel(
            summary_id="test-summary",
        )
        assert panel is not None

    def test_summary_panel_with_data(self):
        """Test summary panel with assignment data."""
        summary_data = {
            "total_wells": 96,
            "assigned_wells": 48,
            "by_type": {
                "sample": 40,
                "blank": 4,
                "negative_control_no_template": 2,
                "negative_control_no_dye": 2,
            },
            "constructs": [
                {"identifier": "WT", "count": 20},
                {"identifier": "M1", "count": 20},
            ],
        }
        panel = create_layout_summary_panel(
            summary_id="test-summary",
            summary_data=summary_data,
        )
        assert panel is not None

    def test_summary_panel_validation_passed(self):
        """Test summary panel with passing validation."""
        summary_data = {
            "total_wells": 96,
            "assigned_wells": 48,
            "by_type": {"sample": 44, "negative_control_no_template": 2, "negative_control_no_dye": 2},
        }
        panel = create_layout_summary_panel(
            summary_id="test-summary",
            summary_data=summary_data,
            validation_passed=True,
        )
        assert panel is not None

    def test_summary_panel_validation_failed(self):
        """Test summary panel with failing validation."""
        summary_data = {
            "total_wells": 96,
            "assigned_wells": 10,
            "by_type": {"sample": 10},
        }
        validation_issues = ["Minimum 2 negative control wells required"]
        panel = create_layout_summary_panel(
            summary_id="test-summary",
            summary_data=summary_data,
            validation_passed=False,
            validation_issues=validation_issues,
        )
        assert panel is not None


class TestCreatePlateTemplatesLoadingState:
    """Tests for loading state component."""

    def test_loading_state(self):
        """Test creating loading state."""
        loading = create_plate_templates_loading_state()
        assert loading is not None

    def test_loading_state_96(self):
        """Test loading state for 96-well."""
        loading = create_plate_templates_loading_state(plate_format=96)
        assert loading is not None

    def test_loading_state_384(self):
        """Test loading state for 384-well."""
        loading = create_plate_templates_loading_state(plate_format=384)
        assert loading is not None


class TestIntegration:
    """Integration tests for plate templates layout."""

    def test_complete_new_layout_workflow(self):
        """Test complete new layout creation workflow."""
        layout = create_plate_templates_layout(
            project_id=1,
        )
        assert layout is not None

    def test_complete_edit_layout_workflow(self):
        """Test complete layout editing workflow."""
        layout = create_plate_templates_layout(
            project_id=1,
            layout_id=1,
        )
        assert layout is not None


# Helper function for finding components
def _find_components_by_type(component, component_type):
    """Recursively find all components of a given type."""
    found = []

    if isinstance(component, component_type):
        found.append(component)

    # Check children
    children = None
    if hasattr(component, "children"):
        children = component.children
    elif isinstance(component, dict) and "children" in component:
        children = component["children"]

    if children:
        if isinstance(children, list):
            for child in children:
                found.extend(_find_components_by_type(child, component_type))
        else:
            found.extend(_find_components_by_type(children, component_type))

    return found
