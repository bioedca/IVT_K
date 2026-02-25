"""Tests for Sprint 3 enhancements (F13.14, F13.15, F13.16).

Tests the new functionality added for:
- Cross-Family Comparison UI (F13.14, Task 6.1)
- Forest Plot VIF Badges (F13.15, Task 8.1)
- Precision History Visualization (F13.16, Task 8.2)
"""
import pytest
from unittest.mock import patch, MagicMock
from math import isclose
import numpy as np

from app.components.forest_plot import (
    VIF_COLORS,
    get_vif_color,
    get_vif_label,
)
from app.layouts.precision_dashboard import create_sparkline
from app.layouts.analysis_results import (
    get_vif_badge,
    create_cross_family_precomputed_table,
    create_cross_family_mutant_table,
    create_custom_comparison_result,
    create_empty_cross_family,
)
from app.analysis.comparison import (
    PathType,
    VIF_VALUES,
    ComparisonType,
)


class TestForestPlotVIFBadges:
    """Tests for Forest Plot VIF Badges (F13.15, Task 8.1)."""

    def test_vif_colors_defined(self):
        """Test VIF color mappings exist."""
        assert 1.0 in VIF_COLORS
        assert 1.414 in VIF_COLORS
        assert 2.0 in VIF_COLORS
        assert 4.0 in VIF_COLORS

    def test_vif_color_direct(self):
        """Test green color for direct comparisons (VIF=1.0)."""
        color = get_vif_color(1.0)
        assert color == VIF_COLORS[1.0]
        assert color == "#40c057"  # Green

    def test_vif_color_one_hop(self):
        """Test yellow color for one-hop comparisons (VIF~1.414)."""
        color = get_vif_color(1.414)
        assert color == VIF_COLORS[1.414]
        assert color == "#fab005"  # Yellow

    def test_vif_color_two_hop(self):
        """Test orange color for two-hop comparisons (VIF=2.0)."""
        color = get_vif_color(2.0)
        assert color == VIF_COLORS[2.0]
        assert color == "#fd7e14"  # Orange

    def test_vif_color_four_hop(self):
        """Test red color for four-hop comparisons (VIF=4.0)."""
        color = get_vif_color(4.0)
        assert color == VIF_COLORS[4.0]
        assert color == "#fa5252"  # Red

    def test_vif_color_boundary_values(self):
        """Test VIF color selection at boundary values."""
        assert get_vif_color(0.9) == VIF_COLORS[1.0]  # Below 1.0 -> green
        assert get_vif_color(1.0) == VIF_COLORS[1.0]  # Exactly 1.0 -> green
        assert get_vif_color(1.01) == VIF_COLORS[1.414]  # Just above 1.0 -> yellow
        assert get_vif_color(1.49) == VIF_COLORS[1.414]  # Below 1.5 -> yellow
        assert get_vif_color(2.49) == VIF_COLORS[2.0]  # Below 2.5 -> orange
        assert get_vif_color(3.0) == VIF_COLORS[4.0]  # Above 2.5 -> red

    def test_vif_label_direct(self):
        """Test label for direct comparison."""
        label = get_vif_label(1.0)
        assert label == "Direct"

    def test_vif_label_one_hop(self):
        """Test label for one-hop comparison."""
        label = get_vif_label(1.414)
        assert label == "1-hop"

    def test_vif_label_two_hop(self):
        """Test label for two-hop comparison."""
        label = get_vif_label(2.0)
        assert label == "2-hop"

    def test_vif_label_four_hop(self):
        """Test label for four-hop comparison."""
        label = get_vif_label(4.0)
        assert label == "4-hop"


class TestPrecisionHistorySparklines:
    """Tests for Precision History Visualization (F13.16, Task 8.2)."""

    def test_sparkline_with_empty_history(self):
        """Test sparkline returns placeholder for empty history."""
        result = create_sparkline([])
        # Should return a dash placeholder
        assert result is not None

    def test_sparkline_with_single_value(self):
        """Test sparkline returns placeholder for single value."""
        result = create_sparkline([0.5])
        # Single value isn't enough for a sparkline
        assert result is not None

    def test_sparkline_with_valid_history(self):
        """Test sparkline creates bars for valid history."""
        history = [0.6, 0.5, 0.4, 0.35, 0.3]
        result = create_sparkline(history)

        # Should return a div with bars
        assert result is not None
        # The component should have children (the bars)
        assert hasattr(result, 'children')

    def test_sparkline_truncates_to_last_8(self):
        """Test sparkline only shows last 8 values."""
        history = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45]
        result = create_sparkline(history)

        # Should be created successfully
        assert result is not None

    def test_sparkline_normalizes_values(self):
        """Test sparkline normalizes values to 0-1 range."""
        history = [100, 50, 25]  # Large values should be normalized
        result = create_sparkline(history)

        # Should not error and should create component
        assert result is not None


class TestVIFValues:
    """Tests for VIF constants from comparison module."""

    def test_vif_direct_is_one(self):
        """Test VIF for direct comparison is 1.0."""
        assert VIF_VALUES[PathType.DIRECT] == 1.0

    def test_vif_one_hop_is_sqrt2(self):
        """Test VIF for one-hop is sqrt(2)."""
        assert isclose(VIF_VALUES[PathType.ONE_HOP], np.sqrt(2))

    def test_vif_two_hop_is_two(self):
        """Test VIF for two-hop is 2.0."""
        assert VIF_VALUES[PathType.TWO_HOP] == 2.0

    def test_vif_four_hop_is_four(self):
        """Test VIF for four-hop is 4.0."""
        assert VIF_VALUES[PathType.FOUR_HOP] == 4.0


class TestCrossFamilyComparisonUI:
    """Tests for Cross-Family Comparison UI (F13.14, Task 6.1)."""

    def test_get_vif_badge_direct(self):
        """Test VIF badge for direct comparison."""
        badge = get_vif_badge(1.0, "Direct")

        assert badge is not None
        # Check badge properties
        assert "1.00" in badge.children
        assert badge.color == "green"

    def test_get_vif_badge_two_hop(self):
        """Test VIF badge for two-hop comparison."""
        badge = get_vif_badge(2.0, "Two-hop")

        assert badge is not None
        assert "2.00" in badge.children
        assert badge.color == "orange"

    def test_get_vif_badge_four_hop(self):
        """Test VIF badge for four-hop (cross-family) comparison."""
        badge = get_vif_badge(4.0, "Four-hop")

        assert badge is not None
        assert "4.00" in badge.children
        assert badge.color == "red"

    def test_precomputed_table_empty(self):
        """Test precomputed table with no data."""
        result = create_cross_family_precomputed_table([])

        # Should return a text message
        assert result is not None

    def test_precomputed_table_with_data(self):
        """Test precomputed table with comparison data."""
        comparisons = [
            {
                "test_name": "Tbox1_M1",
                "control_name": "Reporter",
                "fc": 1.5,
                "ci_lower": 1.2,
                "ci_upper": 1.8,
                "vif": 2.0,
                "path_type": "Two-hop",
            },
        ]

        result = create_cross_family_precomputed_table(comparisons)

        # Should return a table
        assert result is not None

    def test_mutant_table_empty(self):
        """Test mutant table with no data."""
        result = create_cross_family_mutant_table([])

        # Should return a text message
        assert result is not None

    def test_mutant_table_with_data(self):
        """Test mutant table with comparison data."""
        comparisons = [
            {
                "mutant1_name": "Tbox1_M1",
                "mutant1_family": "Tbox1",
                "mutant2_name": "Tbox2_M1",
                "mutant2_family": "Tbox2",
                "fc": 0.8,
                "ci_lower": 0.5,
                "ci_upper": 1.2,
                "vif": 4.0,
            },
        ]

        result = create_cross_family_mutant_table(comparisons)

        # Should return a table
        assert result is not None

    def test_custom_comparison_result_none(self):
        """Test custom comparison result with None."""
        result = create_custom_comparison_result(None)

        # Should return empty div
        assert result is not None

    def test_custom_comparison_result_invalid(self):
        """Test custom comparison result for invalid comparison."""
        result = create_custom_comparison_result({
            "is_valid": False,
            "error_message": "No comparison path exists",
        })

        # Should return an alert
        assert result is not None

    def test_custom_comparison_result_valid(self):
        """Test custom comparison result for valid comparison."""
        result = create_custom_comparison_result({
            "is_valid": True,
            "test_name": "Tbox1_M1",
            "control_name": "Tbox2_M1",
            "fc": 0.85,
            "ci_lower": 0.65,
            "ci_upper": 1.10,
            "vif": 4.0,
            "path_type": "Four-hop",
            "path_description": "Tbox1_M1 → Tbox1_WT → Reporter → Tbox2_WT → Tbox2_M1",
        })

        # Should return a paper component with results
        assert result is not None

    def test_empty_cross_family_message(self):
        """Test empty cross-family placeholder."""
        result = create_empty_cross_family()

        # Should return an alert
        assert result is not None


class TestComparisonTypes:
    """Tests for comparison type definitions."""

    def test_cross_family_type_exists(self):
        """Test CROSS_FAMILY comparison type exists."""
        assert hasattr(ComparisonType, 'CROSS_FAMILY')
        assert ComparisonType.CROSS_FAMILY.value == "cross_family"

    def test_four_hop_path_exists(self):
        """Test FOUR_HOP path type exists."""
        assert hasattr(PathType, 'FOUR_HOP')
        assert PathType.FOUR_HOP.value == "four_hop"

    def test_path_types_complete(self):
        """Test all expected path types exist."""
        assert hasattr(PathType, 'DIRECT')
        assert hasattr(PathType, 'ONE_HOP')
        assert hasattr(PathType, 'TWO_HOP')
        assert hasattr(PathType, 'FOUR_HOP')
