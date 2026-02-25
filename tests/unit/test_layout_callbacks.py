"""
Tests for layout callbacks.

Phase 2: Plate Layout Editor - Layout Callbacks

Tests the layout_callbacks.py module that provides:
- Well selection handling (click, shift-click, ctrl-click)
- Well assignment callbacks
- Checkerboard validation for 384-well
- Selection helpers (row, column, all)
- Layout save and publish callbacks
"""
import pytest
from unittest.mock import MagicMock, patch
from dash import callback_context

from app.callbacks.layout_callbacks import (
    register_layout_callbacks,
    handle_well_click,
    handle_selection_helper,
    handle_assignment,
    handle_clear_selection,
    handle_layout_save,
    handle_layout_publish,
    compute_selection_range,
    merge_selections,
    validate_assignment,
    get_layout_validation_status,
)


class TestHandleWellClick:
    """Tests for well click handling."""

    def test_single_click_empty_selection(self):
        """Test single click on well with no prior selection."""
        result = handle_well_click(
            clicked_well="A1",
            current_selection=[],
            shift_key=False,
            ctrl_key=False,
        )
        assert result == ["A1"]

    def test_single_click_replaces_selection(self):
        """Test single click replaces existing selection."""
        result = handle_well_click(
            clicked_well="B1",
            current_selection=["A1", "A2"],
            shift_key=False,
            ctrl_key=False,
        )
        assert result == ["B1"]

    def test_ctrl_click_adds_to_selection(self):
        """Test ctrl-click adds well to selection."""
        result = handle_well_click(
            clicked_well="B1",
            current_selection=["A1"],
            shift_key=False,
            ctrl_key=True,
        )
        assert "A1" in result
        assert "B1" in result
        assert len(result) == 2

    def test_ctrl_click_removes_from_selection(self):
        """Test ctrl-click on selected well removes it."""
        result = handle_well_click(
            clicked_well="A1",
            current_selection=["A1", "B1"],
            shift_key=False,
            ctrl_key=True,
        )
        assert "A1" not in result
        assert "B1" in result
        assert len(result) == 1

    def test_shift_click_range_selection(self):
        """Test shift-click creates range selection."""
        result = handle_well_click(
            clicked_well="A4",
            current_selection=["A1"],
            shift_key=True,
            ctrl_key=False,
            last_clicked="A1",
        )
        assert "A1" in result
        assert "A2" in result
        assert "A3" in result
        assert "A4" in result
        assert len(result) == 4

    def test_shift_click_rectangular_range(self):
        """Test shift-click creates rectangular range."""
        result = handle_well_click(
            clicked_well="B3",
            current_selection=["A1"],
            shift_key=True,
            ctrl_key=False,
            last_clicked="A1",
        )
        # Should include A1, A2, A3, B1, B2, B3
        expected_wells = ["A1", "A2", "A3", "B1", "B2", "B3"]
        for well in expected_wells:
            assert well in result


class TestComputeSelectionRange:
    """Tests for selection range computation."""

    def test_same_row_range(self):
        """Test range computation in same row."""
        result = compute_selection_range("A1", "A5", plate_format=96)
        assert len(result) == 5
        assert "A1" in result
        assert "A5" in result

    def test_same_column_range(self):
        """Test range computation in same column."""
        result = compute_selection_range("A1", "E1", plate_format=96)
        assert len(result) == 5
        assert "A1" in result
        assert "E1" in result

    def test_rectangular_range(self):
        """Test rectangular range computation."""
        result = compute_selection_range("A1", "C3", plate_format=96)
        # 3 rows x 3 cols = 9 wells
        assert len(result) == 9

    def test_reversed_range(self):
        """Test range works regardless of start/end order."""
        result1 = compute_selection_range("A1", "C3", plate_format=96)
        result2 = compute_selection_range("C3", "A1", plate_format=96)
        assert sorted(result1) == sorted(result2)


class TestMergeSelections:
    """Tests for selection merging."""

    def test_merge_disjoint(self):
        """Test merging disjoint selections."""
        result = merge_selections(["A1", "A2"], ["B1", "B2"])
        assert len(result) == 4
        assert all(w in result for w in ["A1", "A2", "B1", "B2"])

    def test_merge_overlapping(self):
        """Test merging overlapping selections removes duplicates."""
        result = merge_selections(["A1", "A2", "B1"], ["B1", "B2"])
        assert len(result) == 4
        assert result.count("B1") == 1

    def test_merge_empty(self):
        """Test merging with empty selection."""
        result = merge_selections(["A1", "A2"], [])
        assert result == ["A1", "A2"]


class TestHandleSelectionHelper:
    """Tests for selection helper handling."""

    def test_select_row_96(self):
        """Test selecting entire row for 96-well."""
        result = handle_selection_helper(
            helper_type="row",
            helper_value="A",
            plate_format=96,
        )
        assert len(result) == 12
        assert all(w.startswith("A") for w in result)

    def test_select_column_96(self):
        """Test selecting entire column for 96-well."""
        result = handle_selection_helper(
            helper_type="column",
            helper_value="1",
            plate_format=96,
        )
        assert len(result) == 8
        assert all(w.endswith("1") for w in result)

    def test_select_all_96(self):
        """Test selecting all wells for 96-well."""
        result = handle_selection_helper(
            helper_type="all",
            helper_value=None,
            plate_format=96,
        )
        assert len(result) == 96

    def test_select_row_384(self):
        """Test selecting entire row for 384-well."""
        result = handle_selection_helper(
            helper_type="row",
            helper_value="A",
            plate_format=384,
        )
        assert len(result) == 24

    def test_select_column_384(self):
        """Test selecting entire column for 384-well."""
        result = handle_selection_helper(
            helper_type="column",
            helper_value="1",
            plate_format=384,
        )
        assert len(result) == 16

    def test_select_all_384(self):
        """Test selecting all wells for 384-well."""
        result = handle_selection_helper(
            helper_type="all",
            helper_value=None,
            plate_format=384,
        )
        assert len(result) == 384


class TestHandleAssignment:
    """Tests for assignment handling."""

    def test_assign_construct_to_wells(self):
        """Test assigning construct to selected wells."""
        result = handle_assignment(
            selected_wells=["A1", "A2", "A3"],
            construct_id=1,
            well_type="sample",
        )
        assert result is not None
        assert len(result) == 3
        for assignment in result:
            assert assignment["construct_id"] == 1
            assert assignment["well_type"] == "sample"

    def test_assign_blank_wells(self):
        """Test assigning blank well type."""
        result = handle_assignment(
            selected_wells=["H12"],
            construct_id=None,
            well_type="blank",
        )
        assert len(result) == 1
        assert result[0]["well_type"] == "blank"
        assert result[0]["construct_id"] is None

    def test_assign_negative_control(self):
        """Test assigning negative control well type."""
        result = handle_assignment(
            selected_wells=["G12", "H12"],
            construct_id=None,
            well_type="negative_control_no_template",
        )
        assert len(result) == 2
        for assignment in result:
            assert assignment["well_type"] == "negative_control_no_template"

    def test_assign_with_ligand(self):
        """Test assigning with ligand concentration."""
        result = handle_assignment(
            selected_wells=["A1", "A2"],
            construct_id=1,
            well_type="sample",
            ligand_concentration=10.0,
        )
        assert len(result) == 2
        for assignment in result:
            assert assignment["ligand_concentration"] == 10.0


class TestValidateAssignment:
    """Tests for assignment validation."""

    def test_valid_sample_assignment(self):
        """Test valid sample assignment passes validation."""
        is_valid, errors = validate_assignment(
            construct_id=1,
            well_type="sample",
            wells=["A1"],
        )
        assert is_valid == True
        assert len(errors) == 0

    def test_sample_requires_construct(self):
        """Test sample wells require construct."""
        is_valid, errors = validate_assignment(
            construct_id=None,
            well_type="sample",
            wells=["A1"],
        )
        assert is_valid == False
        assert len(errors) > 0

    def test_blank_no_construct(self):
        """Test blank wells should not have construct."""
        is_valid, errors = validate_assignment(
            construct_id=None,
            well_type="blank",
            wells=["H12"],
        )
        assert is_valid == True

    def test_checkerboard_validation_384(self):
        """Test checkerboard validation for 384-well."""
        # A2 is invalid in checkerboard pattern
        is_valid, errors = validate_assignment(
            construct_id=1,
            well_type="sample",
            wells=["A1", "A2"],
            plate_format=384,
            enforce_checkerboard=True,
        )
        assert is_valid == False
        assert any("checkerboard" in err.lower() for err in errors)


class TestHandleClearSelection:
    """Tests for clear selection handling."""

    def test_clear_selection(self):
        """Test clearing selection returns empty list."""
        result = handle_clear_selection()
        assert result == []


class TestGetLayoutValidationStatus:
    """Tests for layout validation status."""

    def test_valid_layout(self):
        """Test valid layout returns passing status."""
        summary = {
            "assigned_wells": 48,
            "by_type": {
                "sample": 44,
                "negative_control_no_template": 2,
                "negative_control_no_dye": 2,
            },
            "by_role": {
                "unregulated": 4,  # Required anchor construct
                "wildtype": 4,
                "mutant": 36,
            },
            "families_mutant": set(),
            "families_wt": set(),
            "checkerboard_violations": [],
        }
        is_valid, issues = get_layout_validation_status(summary)
        assert is_valid == True
        assert len(issues) == 0

    def test_missing_negative_controls(self):
        """Test layout missing negative controls fails."""
        summary = {
            "assigned_wells": 48,
            "by_type": {
                "sample": 48,
            },
            "by_role": {
                "unregulated": 4,
            },
            "families_mutant": set(),
            "families_wt": set(),
            "checkerboard_violations": [],
        }
        is_valid, issues = get_layout_validation_status(summary)
        assert is_valid == False
        assert any("-template" in issue.lower() for issue in issues)

    def test_no_samples(self):
        """Test layout with no samples (no unregulated anchor) fails."""
        summary = {
            "assigned_wells": 4,
            "by_type": {
                "negative_control_no_template": 2,
                "negative_control_no_dye": 2,
            },
            "by_role": {},  # No samples, so no roles
            "families_mutant": set(),
            "families_wt": set(),
            "checkerboard_violations": [],
        }
        is_valid, issues = get_layout_validation_status(summary)
        assert is_valid == False
        # Validation now checks for unregulated anchor (Step 2) instead of generic "sample"
        assert any("aptamer anchor" in issue.lower() for issue in issues)


class TestCallbackRegistration:
    """Tests for callback registration."""

    def test_register_callbacks(self):
        """Test that callbacks can be registered."""
        mock_app = MagicMock()
        # Should not raise
        register_layout_callbacks(mock_app)
        # Verify callbacks were registered
        assert mock_app.callback.called


class TestIntegration:
    """Integration tests for layout callbacks."""

    def test_complete_assignment_workflow(self):
        """Test complete assignment workflow."""
        # Step 1: Click to select well
        selection1 = handle_well_click("A1", [], False, False)
        assert selection1 == ["A1"]

        # Step 2: Shift-click to extend selection
        selection2 = handle_well_click("A4", selection1, True, False, "A1")
        assert len(selection2) == 4

        # Step 3: Assign construct
        assignments = handle_assignment(selection2, construct_id=1, well_type="sample")
        assert len(assignments) == 4

    def test_row_selection_and_assignment(self):
        """Test row selection and assignment workflow."""
        # Select entire row
        selection = handle_selection_helper("row", "A", 96)
        assert len(selection) == 12

        # Assign construct to row
        assignments = handle_assignment(selection, construct_id=1, well_type="sample")
        assert len(assignments) == 12

    def test_384_checkerboard_workflow(self):
        """Test 384-well checkerboard assignment workflow."""
        # Select wells respecting checkerboard
        selection = ["A1", "A3", "A5"]  # Valid checkerboard positions

        # Validate checkerboard
        is_valid, errors = validate_assignment(
            construct_id=1,
            well_type="sample",
            wells=selection,
            plate_format=384,
            enforce_checkerboard=True,
        )
        assert is_valid == True
