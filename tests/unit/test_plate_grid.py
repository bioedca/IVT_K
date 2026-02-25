"""
Tests for plate grid interactive component.

Phase 2: Plate Layout Editor - Plate Grid Component

Tests the plate_grid.py component that provides:
- Interactive click-to-assign plate grid editor
- Well selection with click, shift-click, ctrl-click
- Row/column/all selection helpers
- Visual well states and assignment display
- Checkerboard pattern for 384-well plates
"""
import pytest
import dash_mantine_components as dmc
from dash import html

from app.components.plate_grid import (
    create_plate_grid,
    create_plate_grid_skeleton,
    create_well_cell,
    create_selection_helpers,
    create_assignment_panel,
    WellState,
    get_well_state_color,
    get_well_state_style,
    well_position_to_index,
    index_to_well_position,
    get_wells_in_range,
    get_wells_in_row,
    get_wells_in_column,
    is_checkerboard_valid_well,
    validate_checkerboard_selection,
    ROWS_96,
    COLS_96,
    ROWS_384,
    COLS_384,
)


class TestWellState:
    """Tests for WellState enumeration."""

    def test_state_values(self):
        """Test that all expected well state values exist."""
        assert WellState.EMPTY == "empty"
        assert WellState.ASSIGNED == "assigned"
        assert WellState.SELECTED == "selected"
        assert WellState.BLOCKED == "blocked"
        assert WellState.CONTROL == "control"

    def test_state_iteration(self):
        """Test that we can iterate over all states."""
        states = list(WellState)
        assert len(states) == 5


class TestPlateConstants:
    """Tests for plate format constants."""

    def test_96_well_dimensions(self):
        """Test 96-well plate dimensions."""
        assert len(ROWS_96) == 8
        assert len(COLS_96) == 12
        assert ROWS_96[0] == "A"
        assert ROWS_96[-1] == "H"
        assert COLS_96[0] == 1
        assert COLS_96[-1] == 12

    def test_384_well_dimensions(self):
        """Test 384-well plate dimensions."""
        assert len(ROWS_384) == 16
        assert len(COLS_384) == 24
        assert ROWS_384[0] == "A"
        assert ROWS_384[-1] == "P"
        assert COLS_384[0] == 1
        assert COLS_384[-1] == 24


class TestWellPositionConversion:
    """Tests for well position conversion functions."""

    def test_position_to_index_96(self):
        """Test converting well position to index for 96-well."""
        assert well_position_to_index("A1", 96) == (0, 0)
        assert well_position_to_index("H12", 96) == (7, 11)
        assert well_position_to_index("D6", 96) == (3, 5)

    def test_position_to_index_384(self):
        """Test converting well position to index for 384-well."""
        assert well_position_to_index("A1", 384) == (0, 0)
        assert well_position_to_index("P24", 384) == (15, 23)
        assert well_position_to_index("H12", 384) == (7, 11)

    def test_index_to_position_96(self):
        """Test converting index to well position for 96-well."""
        assert index_to_well_position(0, 0, 96) == "A1"
        assert index_to_well_position(7, 11, 96) == "H12"
        assert index_to_well_position(3, 5, 96) == "D6"

    def test_index_to_position_384(self):
        """Test converting index to well position for 384-well."""
        assert index_to_well_position(0, 0, 384) == "A1"
        assert index_to_well_position(15, 23, 384) == "P24"
        assert index_to_well_position(7, 11, 384) == "H12"

    def test_case_insensitive_position(self):
        """Test that well position parsing is case-insensitive."""
        assert well_position_to_index("a1", 96) == (0, 0)
        assert well_position_to_index("h12", 96) == (7, 11)


class TestGetWellsInRange:
    """Tests for range selection helper."""

    def test_single_well_range(self):
        """Test range with same start and end."""
        wells = get_wells_in_range("A1", "A1", 96)
        assert wells == ["A1"]

    def test_row_range(self):
        """Test selecting a row range."""
        wells = get_wells_in_range("A1", "A4", 96)
        assert wells == ["A1", "A2", "A3", "A4"]

    def test_column_range(self):
        """Test selecting a column range."""
        wells = get_wells_in_range("A1", "D1", 96)
        assert wells == ["A1", "B1", "C1", "D1"]

    def test_rectangular_range(self):
        """Test selecting a rectangular area."""
        wells = get_wells_in_range("A1", "B3", 96)
        expected = ["A1", "A2", "A3", "B1", "B2", "B3"]
        assert sorted(wells) == sorted(expected)

    def test_reversed_range(self):
        """Test that range works regardless of start/end order."""
        wells1 = get_wells_in_range("A1", "B3", 96)
        wells2 = get_wells_in_range("B3", "A1", 96)
        assert sorted(wells1) == sorted(wells2)


class TestGetWellsInRow:
    """Tests for row selection helper."""

    def test_row_a_96(self):
        """Test getting all wells in row A for 96-well."""
        wells = get_wells_in_row("A", 96)
        assert len(wells) == 12
        assert wells[0] == "A1"
        assert wells[-1] == "A12"

    def test_row_h_96(self):
        """Test getting all wells in row H for 96-well."""
        wells = get_wells_in_row("H", 96)
        assert len(wells) == 12
        assert wells[0] == "H1"
        assert wells[-1] == "H12"

    def test_row_p_384(self):
        """Test getting all wells in row P for 384-well."""
        wells = get_wells_in_row("P", 384)
        assert len(wells) == 24
        assert wells[0] == "P1"
        assert wells[-1] == "P24"


class TestGetWellsInColumn:
    """Tests for column selection helper."""

    def test_column_1_96(self):
        """Test getting all wells in column 1 for 96-well."""
        wells = get_wells_in_column(1, 96)
        assert len(wells) == 8
        assert wells[0] == "A1"
        assert wells[-1] == "H1"

    def test_column_12_96(self):
        """Test getting all wells in column 12 for 96-well."""
        wells = get_wells_in_column(12, 96)
        assert len(wells) == 8
        assert wells[0] == "A12"
        assert wells[-1] == "H12"

    def test_column_24_384(self):
        """Test getting all wells in column 24 for 384-well."""
        wells = get_wells_in_column(24, 384)
        assert len(wells) == 16
        assert wells[0] == "A24"
        assert wells[-1] == "P24"


class TestGetWellStateColor:
    """Tests for well state color helper."""

    def test_empty_color(self):
        """Test empty well color."""
        color = get_well_state_color(WellState.EMPTY)
        assert color is not None

    def test_assigned_color(self):
        """Test assigned well color."""
        color = get_well_state_color(WellState.ASSIGNED)
        assert color is not None

    def test_selected_color(self):
        """Test selected well color."""
        color = get_well_state_color(WellState.SELECTED)
        assert color is not None

    def test_blocked_color(self):
        """Test blocked well color."""
        color = get_well_state_color(WellState.BLOCKED)
        assert color is not None

    def test_control_color(self):
        """Test control well color."""
        color = get_well_state_color(WellState.CONTROL)
        assert color is not None


class TestGetWellStateStyle:
    """Tests for well state style helper."""

    def test_empty_style(self):
        """Test empty well style."""
        style = get_well_state_style(WellState.EMPTY)
        assert isinstance(style, dict)

    def test_selected_style_has_highlight(self):
        """Test selected well has highlight style."""
        style = get_well_state_style(WellState.SELECTED)
        assert isinstance(style, dict)
        # Selected wells should have visual distinction
        assert "border" in style or "boxShadow" in style or "outline" in style

    def test_blocked_style_has_indicator(self):
        """Test blocked well has visual indicator."""
        style = get_well_state_style(WellState.BLOCKED)
        assert isinstance(style, dict)


class TestCheckerboardValidation:
    """Tests for 384-well checkerboard pattern validation."""

    def test_valid_checkerboard_wells(self):
        """Test that valid checkerboard wells are identified."""
        # In checkerboard, A1 (0,0) should be valid (even+even = even)
        assert is_checkerboard_valid_well("A1", 384) == True
        # A2 (0,1) should be invalid (even+odd = odd)
        assert is_checkerboard_valid_well("A2", 384) == False
        # B1 (1,0) should be invalid (odd+even = odd)
        assert is_checkerboard_valid_well("B1", 384) == False
        # B2 (1,1) should be valid (odd+odd = even)
        assert is_checkerboard_valid_well("B2", 384) == True

    def test_96_well_no_checkerboard(self):
        """Test that 96-well plates don't enforce checkerboard."""
        # All wells should be valid for 96-well
        assert is_checkerboard_valid_well("A1", 96) == True
        assert is_checkerboard_valid_well("A2", 96) == True
        assert is_checkerboard_valid_well("B1", 96) == True
        assert is_checkerboard_valid_well("B2", 96) == True

    def test_validate_checkerboard_selection_valid(self):
        """Test validation passes for valid checkerboard selection."""
        valid_wells = ["A1", "A3", "B2", "B4"]
        is_valid, invalid_wells = validate_checkerboard_selection(valid_wells, 384)
        assert is_valid == True
        assert len(invalid_wells) == 0

    def test_validate_checkerboard_selection_invalid(self):
        """Test validation fails for invalid checkerboard selection."""
        invalid_wells = ["A1", "A2"]  # A2 is not valid in checkerboard
        is_valid, bad_wells = validate_checkerboard_selection(invalid_wells, 384)
        assert is_valid == False
        assert "A2" in bad_wells


class TestCreateWellCell:
    """Tests for individual well cell creation."""

    def test_basic_well_cell(self):
        """Test creating a basic well cell."""
        cell = create_well_cell(
            position="A1",
            state=WellState.EMPTY,
            plate_format=96,
        )
        assert cell is not None

    def test_well_cell_with_construct(self):
        """Test well cell with construct assignment."""
        cell = create_well_cell(
            position="A1",
            state=WellState.ASSIGNED,
            plate_format=96,
            construct_name="Test Construct",
        )
        assert cell is not None

    def test_well_cell_selected(self):
        """Test well cell in selected state."""
        cell = create_well_cell(
            position="A1",
            state=WellState.SELECTED,
            plate_format=96,
        )
        assert cell is not None

    def test_well_cell_blocked_384(self):
        """Test blocked well cell for 384-well checkerboard."""
        cell = create_well_cell(
            position="A2",  # Invalid in checkerboard
            state=WellState.BLOCKED,
            plate_format=384,
            enforce_checkerboard=True,
        )
        assert cell is not None

    def test_well_cell_with_ligand(self):
        """Test well cell with ligand indicator."""
        cell = create_well_cell(
            position="A1",
            state=WellState.ASSIGNED,
            plate_format=96,
            has_ligand=True,
        )
        assert cell is not None


class TestCreatePlateGrid:
    """Tests for plate grid component creation."""

    def test_create_96_well_grid(self):
        """Test creating a 96-well plate grid."""
        grid = create_plate_grid(
            plate_format=96,
            grid_id="test-grid",
        )
        assert grid is not None
        assert isinstance(grid, (dmc.Paper, dmc.Stack, html.Div))

    def test_create_384_well_grid(self):
        """Test creating a 384-well plate grid."""
        grid = create_plate_grid(
            plate_format=384,
            grid_id="test-grid",
        )
        assert grid is not None

    def test_grid_with_assignments(self):
        """Test grid with well assignments."""
        assignments = {
            "A1": {"construct_id": 1, "construct_name": "WT", "well_type": "sample"},
            "A2": {"construct_id": 2, "construct_name": "M1", "well_type": "sample"},
            "H12": {"well_type": "blank"},
        }
        grid = create_plate_grid(
            plate_format=96,
            grid_id="test-grid",
            assignments=assignments,
        )
        assert grid is not None

    def test_grid_with_selected_wells(self):
        """Test grid with selected wells."""
        grid = create_plate_grid(
            plate_format=96,
            grid_id="test-grid",
            selected_wells=["A1", "A2", "B1", "B2"],
        )
        assert grid is not None

    def test_grid_with_checkerboard_384(self):
        """Test 384-well grid with checkerboard enforcement."""
        grid = create_plate_grid(
            plate_format=384,
            grid_id="test-grid",
            enforce_checkerboard=True,
        )
        assert grid is not None

    def test_grid_readonly_mode(self):
        """Test grid in read-only mode."""
        grid = create_plate_grid(
            plate_format=96,
            grid_id="test-grid",
            readonly=True,
        )
        assert grid is not None


class TestCreatePlateGridSkeleton:
    """Tests for plate grid skeleton component."""

    def test_96_well_skeleton(self):
        """Test creating 96-well skeleton."""
        skeleton = create_plate_grid_skeleton(plate_format=96)
        assert skeleton is not None

    def test_384_well_skeleton(self):
        """Test creating 384-well skeleton."""
        skeleton = create_plate_grid_skeleton(plate_format=384)
        assert skeleton is not None


class TestCreateSelectionHelpers:
    """Tests for selection helper buttons."""

    def test_selection_helpers_96(self):
        """Test selection helpers for 96-well plate."""
        helpers = create_selection_helpers(
            plate_format=96,
            helpers_id="test-helpers",
        )
        assert helpers is not None

    def test_selection_helpers_384(self):
        """Test selection helpers for 384-well plate."""
        helpers = create_selection_helpers(
            plate_format=384,
            helpers_id="test-helpers",
        )
        assert helpers is not None


class TestCreateAssignmentPanel:
    """Tests for assignment panel component."""

    def test_basic_assignment_panel(self):
        """Test creating basic assignment panel."""
        panel = create_assignment_panel(
            panel_id="test-panel",
        )
        assert panel is not None

    def test_assignment_panel_with_constructs(self):
        """Test assignment panel with construct options."""
        constructs = [
            {"id": 1, "identifier": "WT", "family": "Tbox1"},
            {"id": 2, "identifier": "M1", "family": "Tbox1"},
        ]
        panel = create_assignment_panel(
            panel_id="test-panel",
            constructs=constructs,
        )
        assert panel is not None

    def test_assignment_panel_with_selection(self):
        """Test assignment panel with selected wells."""
        panel = create_assignment_panel(
            panel_id="test-panel",
            selected_count=4,
        )
        assert panel is not None


class TestIntegration:
    """Integration tests for plate grid component."""

    def test_full_96_well_editor(self):
        """Test complete 96-well plate editor setup."""
        grid = create_plate_grid(
            plate_format=96,
            grid_id="full-editor",
            assignments={
                "A1": {"construct_id": 1, "construct_name": "WT", "well_type": "sample"},
            },
            selected_wells=["B1", "B2"],
        )
        helpers = create_selection_helpers(
            plate_format=96,
            helpers_id="full-editor-helpers",
        )
        panel = create_assignment_panel(
            panel_id="full-editor-panel",
            selected_count=2,
        )

        assert grid is not None
        assert helpers is not None
        assert panel is not None

    def test_full_384_well_editor_with_checkerboard(self):
        """Test complete 384-well plate editor with checkerboard."""
        grid = create_plate_grid(
            plate_format=384,
            grid_id="full-editor-384",
            enforce_checkerboard=True,
        )
        helpers = create_selection_helpers(
            plate_format=384,
            helpers_id="full-editor-helpers-384",
        )

        assert grid is not None
        assert helpers is not None
