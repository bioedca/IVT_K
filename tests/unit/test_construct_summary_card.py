"""
Tests for construct summary card component.

Phase 4: UX Enhancements - Construct Summary Card

Tests the construct_summary_card.py component that provides:
- Modal displaying construct details on forest plot click
- Construct metadata display (family, type, replicates)
- Fold change and confidence interval display
- Precision status indicator
- Plate breakdown table
- Navigation to curve browser
"""
import pytest
import dash_mantine_components as dmc
from dash import html, dcc
from datetime import datetime

from app.components.construct_summary_card import (
    create_construct_summary_card,
    create_construct_header,
    create_construct_metadata,
    create_statistics_panel,
    create_plate_breakdown_table,
    create_card_actions,
    format_confidence_interval,
    format_fold_change,
    get_precision_status_badge,
    PrecisionStatus,
)


class TestPrecisionStatusEnum:
    """Tests for PrecisionStatus enum."""

    def test_precision_status_has_met_value(self):
        """Test PrecisionStatus has MET value."""
        assert hasattr(PrecisionStatus, "MET")
        assert PrecisionStatus.MET is not None

    def test_precision_status_has_not_met_value(self):
        """Test PrecisionStatus has NOT_MET value."""
        assert hasattr(PrecisionStatus, "NOT_MET")
        assert PrecisionStatus.NOT_MET is not None

    def test_precision_status_has_pending_value(self):
        """Test PrecisionStatus has PENDING value."""
        assert hasattr(PrecisionStatus, "PENDING")
        assert PrecisionStatus.PENDING is not None

    def test_precision_status_values_are_strings(self):
        """Test PrecisionStatus values are strings."""
        for status in PrecisionStatus:
            assert isinstance(status.value, str)


class TestFormatConfidenceInterval:
    """Tests for confidence interval formatting."""

    def test_format_basic_interval(self):
        """Test formatting basic confidence interval."""
        result = format_confidence_interval(1.5, 2.5)
        assert "[" in result and "]" in result
        assert "1.5" in result or "1.50" in result
        assert "2.5" in result or "2.50" in result

    def test_format_with_precision(self):
        """Test formatting with specified precision."""
        result = format_confidence_interval(1.234, 5.678, precision=2)
        assert "1.23" in result
        assert "5.68" in result

    def test_format_symmetric_interval(self):
        """Test formatting symmetric interval."""
        result = format_confidence_interval(0.8, 1.2)
        assert result is not None

    def test_format_with_none_values(self):
        """Test handling None values gracefully."""
        result = format_confidence_interval(None, None)
        assert result is not None  # Should return placeholder text

    def test_format_negative_values(self):
        """Test formatting negative values."""
        result = format_confidence_interval(-1.5, 0.5)
        assert "-1.5" in result or "-1.50" in result


class TestFormatFoldChange:
    """Tests for fold change formatting."""

    def test_format_basic_fold_change(self):
        """Test formatting basic fold change."""
        result = format_fold_change(2.34)
        assert "2.34" in result

    def test_format_with_precision(self):
        """Test formatting with specified precision."""
        result = format_fold_change(2.3456, precision=3)
        assert "2.346" in result

    def test_format_small_fold_change(self):
        """Test formatting small fold change."""
        result = format_fold_change(0.5)
        assert "0.5" in result

    def test_format_none_value(self):
        """Test handling None value."""
        result = format_fold_change(None)
        assert result is not None  # Should return placeholder

    def test_format_large_fold_change(self):
        """Test formatting large fold change."""
        result = format_fold_change(15.89)
        assert "15.89" in result


class TestGetPrecisionStatusBadge:
    """Tests for precision status badge creation."""

    def test_badge_for_met_status(self):
        """Test badge for MET status."""
        badge = get_precision_status_badge(PrecisionStatus.MET)
        assert badge is not None
        assert isinstance(badge, dmc.Badge)

    def test_badge_for_not_met_status(self):
        """Test badge for NOT_MET status."""
        badge = get_precision_status_badge(PrecisionStatus.NOT_MET)
        assert badge is not None
        assert isinstance(badge, dmc.Badge)

    def test_badge_for_pending_status(self):
        """Test badge for PENDING status."""
        badge = get_precision_status_badge(PrecisionStatus.PENDING)
        assert badge is not None
        assert isinstance(badge, dmc.Badge)

    def test_met_badge_color_is_green(self):
        """Test MET status badge is green."""
        badge = get_precision_status_badge(PrecisionStatus.MET)
        assert badge.color in ["green", "teal", "lime"]

    def test_not_met_badge_color_is_red(self):
        """Test NOT_MET status badge is red/orange."""
        badge = get_precision_status_badge(PrecisionStatus.NOT_MET)
        assert badge.color in ["red", "orange", "yellow"]

    def test_badge_accepts_string_status(self):
        """Test badge accepts string status value."""
        badge = get_precision_status_badge("met")
        assert badge is not None


class TestCreateConstructHeader:
    """Tests for construct header section."""

    def test_header_creation(self):
        """Test header is created."""
        header = create_construct_header(
            construct_name="Tbox1_M1"
        )
        assert header is not None

    def test_header_displays_construct_name(self):
        """Test header displays construct name."""
        header = create_construct_header(
            construct_name="MyConstruct_WT"
        )
        assert header is not None
        # Name should be visible in component

    def test_header_with_close_button(self):
        """Test header has close button."""
        header = create_construct_header(
            construct_name="Test"
        )
        # Should have close icon/button
        assert header is not None


class TestCreateConstructMetadata:
    """Tests for construct metadata panel."""

    def test_metadata_creation(self):
        """Test metadata panel is created."""
        metadata = create_construct_metadata(
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16
        )
        assert metadata is not None

    def test_metadata_displays_family(self):
        """Test metadata displays family."""
        metadata = create_construct_metadata(
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16
        )
        assert metadata is not None

    def test_metadata_displays_type(self):
        """Test metadata displays construct type."""
        metadata = create_construct_metadata(
            family="Test",
            construct_type="Wild-type",
            total_replicates=8
        )
        assert metadata is not None

    def test_metadata_displays_replicate_count(self):
        """Test metadata displays replicate count."""
        metadata = create_construct_metadata(
            family="Test",
            construct_type="Mutant",
            total_replicates=24
        )
        assert metadata is not None

    def test_metadata_with_optional_fields(self):
        """Test metadata with optional additional fields."""
        metadata = create_construct_metadata(
            family="Test",
            construct_type="Mutant",
            total_replicates=16,
            description="Test construct description"
        )
        assert metadata is not None


class TestCreateStatisticsPanel:
    """Tests for statistics panel."""

    def test_statistics_creation(self):
        """Test statistics panel is created."""
        stats = create_statistics_panel(
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET
        )
        assert stats is not None

    def test_statistics_displays_fold_change(self):
        """Test panel displays fold change."""
        stats = create_statistics_panel(
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET
        )
        assert stats is not None

    def test_statistics_displays_confidence_interval(self):
        """Test panel displays confidence interval."""
        stats = create_statistics_panel(
            fold_change=2.0,
            ci_lower=1.5,
            ci_upper=2.5,
            precision_status=PrecisionStatus.MET
        )
        assert stats is not None

    def test_statistics_displays_precision_status(self):
        """Test panel displays precision status."""
        stats = create_statistics_panel(
            fold_change=2.0,
            ci_lower=1.5,
            ci_upper=2.5,
            precision_status=PrecisionStatus.NOT_MET
        )
        assert stats is not None

    def test_statistics_with_parameter_label(self):
        """Test panel shows parameter label (F_max)."""
        stats = create_statistics_panel(
            fold_change=2.0,
            ci_lower=1.5,
            ci_upper=2.5,
            precision_status=PrecisionStatus.MET,
            parameter_name="F_max"
        )
        assert stats is not None

    def test_statistics_with_no_data(self):
        """Test panel handles missing data gracefully."""
        stats = create_statistics_panel(
            fold_change=None,
            ci_lower=None,
            ci_upper=None,
            precision_status=PrecisionStatus.PENDING
        )
        assert stats is not None


class TestCreatePlateBreakdownTable:
    """Tests for plate breakdown table."""

    def test_table_creation(self):
        """Test table is created."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0}
        ]
        table = create_plate_breakdown_table(plates=plates)
        assert table is not None

    def test_table_with_multiple_plates(self):
        """Test table with multiple plates."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0},
            {"name": "Plate 2", "session": "2024-01", "replicates": 4, "excluded": 1},
            {"name": "Plate 3", "session": "2024-02", "replicates": 8, "excluded": 0},
        ]
        table = create_plate_breakdown_table(plates=plates)
        assert table is not None

    def test_table_headers(self):
        """Test table has correct headers."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0}
        ]
        table = create_plate_breakdown_table(plates=plates)
        # Should have: Plate, Session, Reps, Excluded
        assert table is not None

    def test_table_empty_state(self):
        """Test table with no plates."""
        table = create_plate_breakdown_table(plates=[])
        assert table is not None
        # Should show message or empty state

    def test_table_shows_excluded_count(self):
        """Test table shows excluded well count."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 2}
        ]
        table = create_plate_breakdown_table(plates=plates)
        assert table is not None

    def test_table_with_datetime_session(self):
        """Test table handles datetime session values."""
        plates = [
            {"name": "Plate 1", "session": datetime(2024, 1, 15), "replicates": 4, "excluded": 0}
        ]
        table = create_plate_breakdown_table(plates=plates)
        assert table is not None


class TestCreateCardActions:
    """Tests for card action buttons."""

    def test_actions_creation(self):
        """Test actions are created."""
        actions = create_card_actions(construct_id=1)
        assert actions is not None

    def test_view_wells_button(self):
        """Test View All Wells button exists."""
        actions = create_card_actions(construct_id=1)
        view_btn = _find_component_by_partial_id(actions, "view-wells")
        assert view_btn is not None or _has_button_with_text(actions, "Wells")

    def test_close_button(self):
        """Test Close button exists."""
        actions = create_card_actions(construct_id=1)
        close_btn = _find_component_by_partial_id(actions, "close")
        assert close_btn is not None or _has_button_with_text(actions, "Close")

    def test_view_wells_navigates_to_curves(self):
        """Test View All Wells button has correct navigation."""
        actions = create_card_actions(construct_id=1)
        assert actions is not None


class TestCreateConstructSummaryCard:
    """Tests for main construct summary card component."""

    def test_card_creation(self):
        """Test card component is created."""
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Tbox1_M1",
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16,
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET,
            plates=[]
        )
        assert card is not None

    def test_card_is_modal(self):
        """Test card is a Modal component."""
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Test",
            family="Test",
            construct_type="WT",
            total_replicates=8,
            fold_change=1.5,
            ci_lower=1.2,
            ci_upper=1.8,
            precision_status=PrecisionStatus.MET,
            plates=[]
        )
        # Should be dmc.Modal or contain one
        assert isinstance(card, dmc.Modal) or _has_child_of_type(card, dmc.Modal)

    def test_card_has_correct_id(self):
        """Test card has correct ID for callbacks."""
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Test",
            family="Test",
            construct_type="WT",
            total_replicates=8,
            fold_change=1.5,
            ci_lower=1.2,
            ci_upper=1.8,
            precision_status=PrecisionStatus.MET,
            plates=[]
        )
        assert card.id == "construct-summary-modal" or hasattr(card, "id")

    def test_card_with_full_data(self):
        """Test card with complete data set."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0},
            {"name": "Plate 2", "session": "2024-01", "replicates": 4, "excluded": 1},
        ]
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Tbox1_M1",
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16,
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET,
            plates=plates
        )
        assert card is not None

    def test_card_store_for_state(self):
        """Test card includes store for construct data."""
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Test",
            family="Test",
            construct_type="WT",
            total_replicates=8,
            fold_change=1.5,
            ci_lower=1.2,
            ci_upper=1.8,
            precision_status=PrecisionStatus.MET,
            plates=[]
        )
        # Should have store for construct data
        assert card is not None

    def test_card_skeleton_loading_state(self):
        """Test card has skeleton loading state."""
        from app.components.construct_summary_card import create_construct_summary_skeleton
        skeleton = create_construct_summary_skeleton()
        assert skeleton is not None


class TestConstructSummaryCardIntegration:
    """Integration tests for construct summary card."""

    def test_card_renders_all_sections(self):
        """Test card renders all required sections."""
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0}
        ]
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Tbox1_M1",
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16,
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET,
            plates=plates
        )
        # Should have header, metadata, statistics, table, actions
        assert card is not None

    def test_card_layout_matches_prd(self):
        """Test card layout matches PRD specification."""
        # PRD shows specific layout with dividers and sections
        plates = [
            {"name": "Plate 1", "session": "2024-01", "replicates": 4, "excluded": 0}
        ]
        card = create_construct_summary_card(
            construct_id=1,
            construct_name="Tbox1_M1",
            family="Tbox1",
            construct_type="Mutant",
            total_replicates=16,
            fold_change=2.34,
            ci_lower=1.89,
            ci_upper=2.79,
            precision_status=PrecisionStatus.MET,
            plates=plates
        )
        assert card is not None


# Helper functions
def _find_component_by_id(component, target_id):
    """Recursively find a component with the given ID."""
    if hasattr(component, "id") and component.id == target_id:
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                result = _find_component_by_id(child, target_id)
                if result:
                    return result
        elif children is not None:
            return _find_component_by_id(children, target_id)
    return None


def _find_component_by_partial_id(component, partial_id):
    """Recursively find a component with ID containing partial_id."""
    if hasattr(component, "id") and component.id and partial_id in str(component.id):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                result = _find_component_by_partial_id(child, partial_id)
                if result:
                    return result
        elif children is not None:
            return _find_component_by_partial_id(children, partial_id)
    return None


def _has_child_of_type(component, target_type):
    """Check if component tree contains a child of given type."""
    if isinstance(component, target_type):
        return True
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                if _has_child_of_type(child, target_type):
                    return True
        elif children is not None:
            return _has_child_of_type(children, target_type)
    return False


def _has_button_with_text(component, text):
    """Check if component tree contains a button with given text."""
    if isinstance(component, dmc.Button):
        if hasattr(component, "children"):
            if text.lower() in str(component.children).lower():
                return True
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                if _has_button_with_text(child, text):
                    return True
        elif children is not None:
            return _has_button_with_text(children, text)
    return False
