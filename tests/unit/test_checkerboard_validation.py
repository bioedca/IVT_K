"""
Tests for 384-well checkerboard validation.

Phase 2: Plate Layout Editor - Checkerboard Validation

Tests checkerboard pattern validation for 384-well plates including:
- Valid well position identification
- Selection validation
- Visual feedback generation
- Integration with plate layout service
"""
import pytest

from app.components.plate_grid import (
    is_checkerboard_valid_well,
    validate_checkerboard_selection,
    get_checkerboard_blocked_wells,
    get_checkerboard_valid_wells,
)


class TestIsCheckerboardValidWell:
    """Tests for individual well validation in checkerboard pattern."""

    def test_a1_is_valid(self):
        """Test A1 (0,0) is valid - even sum."""
        assert is_checkerboard_valid_well("A1", 384) == True

    def test_a2_is_invalid(self):
        """Test A2 (0,1) is invalid - odd sum."""
        assert is_checkerboard_valid_well("A2", 384) == False

    def test_b1_is_invalid(self):
        """Test B1 (1,0) is invalid - odd sum."""
        assert is_checkerboard_valid_well("B1", 384) == False

    def test_b2_is_valid(self):
        """Test B2 (1,1) is valid - even sum."""
        assert is_checkerboard_valid_well("B2", 384) == True

    def test_p24_is_valid(self):
        """Test P24 (15,23) is valid - even sum (15+23=38)."""
        assert is_checkerboard_valid_well("P24", 384) == True

    def test_p23_is_invalid(self):
        """Test P23 (15,22) is invalid - odd sum (15+22=37)."""
        assert is_checkerboard_valid_well("P23", 384) == False

    def test_case_insensitive(self):
        """Test well position is case-insensitive."""
        assert is_checkerboard_valid_well("a1", 384) == True
        assert is_checkerboard_valid_well("A1", 384) == True

    def test_96_well_always_valid(self):
        """Test 96-well plates don't enforce checkerboard."""
        # All positions should be valid for 96-well
        for row in "ABCDEFGH":
            for col in range(1, 13):
                well = f"{row}{col}"
                assert is_checkerboard_valid_well(well, 96) == True

    def test_alternating_pattern(self):
        """Test entire row follows checkerboard pattern."""
        # Row A: A1 valid, A2 invalid, A3 valid, etc.
        for col in range(1, 25):
            well = f"A{col}"
            expected = (col - 1) % 2 == 0  # A1=valid, A2=invalid...
            assert is_checkerboard_valid_well(well, 384) == expected, f"Failed for {well}"


class TestValidateCheckerboardSelection:
    """Tests for selection validation against checkerboard pattern."""

    def test_all_valid_selection(self):
        """Test selection with all valid wells passes."""
        wells = ["A1", "A3", "A5", "B2", "B4"]
        is_valid, invalid_wells = validate_checkerboard_selection(wells, 384)
        assert is_valid == True
        assert len(invalid_wells) == 0

    def test_mixed_selection(self):
        """Test selection with some invalid wells fails."""
        wells = ["A1", "A2", "A3"]  # A2 is invalid
        is_valid, invalid_wells = validate_checkerboard_selection(wells, 384)
        assert is_valid == False
        assert "A2" in invalid_wells
        assert len(invalid_wells) == 1

    def test_all_invalid_selection(self):
        """Test selection with all invalid wells fails."""
        wells = ["A2", "A4", "B1", "B3"]
        is_valid, invalid_wells = validate_checkerboard_selection(wells, 384)
        assert is_valid == False
        assert len(invalid_wells) == 4

    def test_empty_selection(self):
        """Test empty selection passes."""
        wells = []
        is_valid, invalid_wells = validate_checkerboard_selection(wells, 384)
        assert is_valid == True
        assert len(invalid_wells) == 0

    def test_96_well_always_valid(self):
        """Test 96-well selection always valid."""
        wells = ["A1", "A2", "B1", "B2"]
        is_valid, invalid_wells = validate_checkerboard_selection(wells, 96)
        assert is_valid == True
        assert len(invalid_wells) == 0


class TestGetCheckerboardBlockedWells:
    """Tests for getting blocked wells in checkerboard pattern."""

    def test_384_blocked_wells_count(self):
        """Test 384-well plate has 192 blocked wells."""
        blocked = get_checkerboard_blocked_wells(384)
        assert len(blocked) == 192  # Half of 384

    def test_blocked_wells_content(self):
        """Test blocked wells are correct positions."""
        blocked = get_checkerboard_blocked_wells(384)
        # A2, A4, etc. should be blocked
        assert "A2" in blocked
        assert "A4" in blocked
        assert "B1" in blocked
        assert "B3" in blocked
        # A1, A3 should not be blocked
        assert "A1" not in blocked
        assert "A3" not in blocked
        assert "B2" not in blocked
        assert "B4" not in blocked

    def test_96_well_no_blocked(self):
        """Test 96-well plate has no blocked wells."""
        blocked = get_checkerboard_blocked_wells(96)
        assert len(blocked) == 0


class TestGetCheckerboardValidWells:
    """Tests for getting valid wells in checkerboard pattern."""

    def test_384_valid_wells_count(self):
        """Test 384-well plate has 192 valid wells."""
        valid = get_checkerboard_valid_wells(384)
        assert len(valid) == 192  # Half of 384

    def test_valid_wells_content(self):
        """Test valid wells are correct positions."""
        valid = get_checkerboard_valid_wells(384)
        # A1, A3, etc. should be valid
        assert "A1" in valid
        assert "A3" in valid
        assert "B2" in valid
        assert "B4" in valid
        # A2, A4 should not be in valid
        assert "A2" not in valid
        assert "A4" not in valid
        assert "B1" not in valid
        assert "B3" not in valid

    def test_96_well_all_valid(self):
        """Test 96-well plate has all wells valid."""
        valid = get_checkerboard_valid_wells(96)
        assert len(valid) == 96


class TestCheckerboardPatternSymmetry:
    """Tests for checkerboard pattern symmetry."""

    def test_valid_and_blocked_complement(self):
        """Test valid and blocked wells are complements."""
        valid = set(get_checkerboard_valid_wells(384))
        blocked = set(get_checkerboard_blocked_wells(384))

        # Should be disjoint
        assert len(valid.intersection(blocked)) == 0

        # Should cover all wells
        all_wells = set()
        for row in "ABCDEFGHIJKLMNOP":
            for col in range(1, 25):
                all_wells.add(f"{row}{col}")

        assert valid.union(blocked) == all_wells

    def test_each_row_alternates(self):
        """Test each row has alternating valid/blocked pattern."""
        for row_idx, row in enumerate("ABCDEFGHIJKLMNOP"):
            for col in range(1, 25):
                well = f"{row}{col}"
                col_idx = col - 1
                # Sum of indices determines validity
                expected_valid = (row_idx + col_idx) % 2 == 0
                actual_valid = is_checkerboard_valid_well(well, 384)
                assert actual_valid == expected_valid, f"Mismatch at {well}"


class TestCheckerboardEdgeCases:
    """Tests for edge cases in checkerboard validation."""

    def test_corner_wells(self):
        """Test all four corners of 384-well plate."""
        # A1 (0,0) - valid
        assert is_checkerboard_valid_well("A1", 384) == True
        # A24 (0,23) - invalid (0+23=odd)
        assert is_checkerboard_valid_well("A24", 384) == False
        # P1 (15,0) - invalid (15+0=odd)
        assert is_checkerboard_valid_well("P1", 384) == False
        # P24 (15,23) - valid (15+23=even)
        assert is_checkerboard_valid_well("P24", 384) == True

    def test_invalid_well_format(self):
        """Test handling of invalid well format."""
        # Should handle gracefully or raise appropriate error
        with pytest.raises((ValueError, KeyError, IndexError)):
            is_checkerboard_valid_well("Z99", 384)

    def test_single_digit_columns(self):
        """Test single-digit column numbers."""
        assert is_checkerboard_valid_well("A1", 384) == True
        assert is_checkerboard_valid_well("A9", 384) == True

    def test_double_digit_columns(self):
        """Test double-digit column numbers."""
        assert is_checkerboard_valid_well("A10", 384) == False
        assert is_checkerboard_valid_well("A11", 384) == True
        assert is_checkerboard_valid_well("A12", 384) == False


class TestIntegration:
    """Integration tests for checkerboard validation."""

    def test_full_row_selection_validation(self):
        """Test validating an entire row selection."""
        # Row A: odd columns valid, even columns invalid
        row_a = [f"A{col}" for col in range(1, 25)]
        is_valid, invalid = validate_checkerboard_selection(row_a, 384)

        assert is_valid == False
        assert len(invalid) == 12  # Half are invalid

        # Verify the invalid ones are even columns
        for well in invalid:
            col = int(well[1:])
            assert col % 2 == 0  # Even columns are invalid in row A

    def test_checkerboard_compliant_selection(self):
        """Test a checkerboard-compliant selection."""
        # Select only valid wells from a 4x4 block
        wells = [
            "A1", "A3",
            "B2", "B4",
            "C1", "C3",
            "D2", "D4",
        ]
        is_valid, invalid = validate_checkerboard_selection(wells, 384)
        assert is_valid == True
        assert len(invalid) == 0

    def test_non_compliant_selection_message(self):
        """Test that non-compliant selection identifies all violations."""
        # Mix of valid and invalid
        wells = ["A1", "A2", "B1", "B2"]
        is_valid, invalid = validate_checkerboard_selection(wells, 384)

        assert is_valid == False
        # A2 and B1 should be invalid
        assert "A2" in invalid
        assert "B1" in invalid
        assert len(invalid) == 2
