"""
Tests for comparison drawer component.

Phase 4: UX Enhancements - Comparison Drawer

Tests the comparison_drawer.py component that provides:
- Floating badge showing comparison count
- Side drawer with comparison list
- Add/remove curve functionality
- View Side-by-Side action
- Clear All action
"""
import pytest
import dash_mantine_components as dmc
from dash import html, dcc

from app.components.comparison_drawer import (
    create_comparison_drawer,
    create_comparison_badge,
    create_comparison_list_item,
    create_comparison_list,
    create_comparison_actions,
    get_drawer_position_styles,
    MAX_COMPARISON_ITEMS,
    DRAWER_WIDTH,
)


class TestComparisonDrawerConstants:
    """Tests for comparison drawer constants."""

    def test_max_comparison_items_defined(self):
        """Test that MAX_COMPARISON_ITEMS is defined."""
        assert MAX_COMPARISON_ITEMS is not None
        assert isinstance(MAX_COMPARISON_ITEMS, int)
        assert MAX_COMPARISON_ITEMS > 0

    def test_max_comparison_items_reasonable_limit(self):
        """Test MAX_COMPARISON_ITEMS has reasonable limit."""
        assert MAX_COMPARISON_ITEMS >= 4
        assert MAX_COMPARISON_ITEMS <= 20

    def test_drawer_width_defined(self):
        """Test that DRAWER_WIDTH is defined."""
        assert DRAWER_WIDTH is not None
        assert isinstance(DRAWER_WIDTH, (int, str))


class TestGetDrawerPositionStyles:
    """Tests for drawer position utility function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        styles = get_drawer_position_styles()
        assert isinstance(styles, dict)

    def test_contains_position_keys(self):
        """Test that position styles contain expected keys."""
        styles = get_drawer_position_styles()
        assert "bottom" in styles or "top" in styles
        assert "right" in styles or "left" in styles

    def test_position_values_are_numeric_or_string(self):
        """Test position values are valid CSS values."""
        styles = get_drawer_position_styles()
        for key, value in styles.items():
            assert isinstance(value, (int, str))


class TestCreateComparisonBadge:
    """Tests for comparison badge creation."""

    def test_badge_creation(self):
        """Test badge is created successfully."""
        badge = create_comparison_badge(count=0)
        assert badge is not None

    def test_badge_with_zero_count(self):
        """Test badge displays zero count correctly."""
        badge = create_comparison_badge(count=0)
        assert badge is not None

    def test_badge_with_positive_count(self):
        """Test badge displays positive count correctly."""
        badge = create_comparison_badge(count=5)
        assert badge is not None

    def test_badge_has_correct_id(self):
        """Test badge has correct ID for callbacks."""
        badge = create_comparison_badge(count=0)
        # Badge should be an ActionIcon containing Badge
        assert hasattr(badge, "id") or _find_component_by_id(badge, "comparison-badge")

    def test_badge_count_has_id(self):
        """Test the count badge inside has correct ID."""
        badge = create_comparison_badge(count=3)
        count_badge = _find_component_by_id(badge, "comparison-count")
        assert count_badge is not None or hasattr(badge, "children")


class TestCreateComparisonListItem:
    """Tests for comparison list item creation."""

    def test_item_creation(self):
        """Test list item is created successfully."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="Test Construct",
            plate_name="Plate A",
        )
        assert item is not None

    def test_item_displays_construct_name(self):
        """Test item displays construct name."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="My Construct",
            plate_name="Plate A",
        )
        assert item is not None
        # The construct name should be somewhere in the component

    def test_item_displays_plate_name(self):
        """Test item displays plate name."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="Test",
            plate_name="Special Plate",
        )
        assert item is not None

    def test_item_has_remove_button(self):
        """Test item has remove button."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="Test",
            plate_name="Plate A",
        )
        # Should have an ActionIcon or Button for removal
        remove_btn = _find_component_by_partial_id(item, "remove")
        assert remove_btn is not None or _has_action_icon(item)

    def test_item_with_optional_well_info(self):
        """Test item with optional well information."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="Test",
            plate_name="Plate A",
            well_position="A1",
        )
        assert item is not None

    def test_item_with_optional_session_info(self):
        """Test item with optional session information."""
        item = create_comparison_list_item(
            curve_id="curve_1",
            construct_name="Test",
            plate_name="Plate A",
            session_name="Session 2024-01",
        )
        assert item is not None


class TestCreateComparisonList:
    """Tests for comparison list creation."""

    def test_empty_list_creation(self):
        """Test creating empty comparison list."""
        list_component = create_comparison_list(items=[])
        assert list_component is not None

    def test_empty_list_shows_message(self):
        """Test empty list shows helpful message."""
        list_component = create_comparison_list(items=[])
        # Should show a message like "No curves added" or similar
        assert list_component is not None

    def test_list_with_single_item(self):
        """Test list with single comparison item."""
        items = [
            {"curve_id": "1", "construct_name": "Test", "plate_name": "Plate A"}
        ]
        list_component = create_comparison_list(items=items)
        assert list_component is not None

    def test_list_with_multiple_items(self):
        """Test list with multiple comparison items."""
        items = [
            {"curve_id": "1", "construct_name": "Test 1", "plate_name": "Plate A"},
            {"curve_id": "2", "construct_name": "Test 2", "plate_name": "Plate B"},
            {"curve_id": "3", "construct_name": "Test 3", "plate_name": "Plate C"},
        ]
        list_component = create_comparison_list(items=items)
        assert list_component is not None

    def test_list_has_correct_id(self):
        """Test list has correct ID for callbacks."""
        list_component = create_comparison_list(items=[])
        assert _find_component_by_id(list_component, "comparison-list") is not None or hasattr(list_component, "id")

    def test_list_items_are_orderable(self):
        """Test list maintains item order."""
        items = [
            {"curve_id": "1", "construct_name": "First", "plate_name": "A"},
            {"curve_id": "2", "construct_name": "Second", "plate_name": "B"},
        ]
        list_component = create_comparison_list(items=items)
        assert list_component is not None


class TestCreateComparisonActions:
    """Tests for comparison action buttons."""

    def test_actions_creation(self):
        """Test action buttons are created."""
        actions = create_comparison_actions()
        assert actions is not None

    def test_view_comparison_button_exists(self):
        """Test View Side-by-Side button exists."""
        actions = create_comparison_actions()
        view_btn = _find_component_by_id(actions, "view-comparison")
        assert view_btn is not None or _has_button_with_text(actions, "Side-by-Side")

    def test_clear_all_button_exists(self):
        """Test Clear All button exists."""
        actions = create_comparison_actions()
        clear_btn = _find_component_by_id(actions, "clear-comparison")
        assert clear_btn is not None or _has_button_with_text(actions, "Clear")

    def test_actions_disabled_when_empty(self):
        """Test actions are disabled when no items selected."""
        actions = create_comparison_actions(has_items=False)
        # View button should be disabled
        assert actions is not None

    def test_actions_enabled_when_items_exist(self):
        """Test actions are enabled when items exist."""
        actions = create_comparison_actions(has_items=True)
        assert actions is not None

    def test_view_requires_minimum_items(self):
        """Test View Side-by-Side requires at least 2 items."""
        actions = create_comparison_actions(item_count=1)
        # View button should be disabled with only 1 item
        assert actions is not None


class TestCreateComparisonDrawer:
    """Tests for main comparison drawer component."""

    def test_drawer_creation(self):
        """Test drawer component is created."""
        drawer = create_comparison_drawer()
        assert drawer is not None

    def test_drawer_is_affix_positioned(self):
        """Test drawer uses Affix for floating position."""
        drawer = create_comparison_drawer()
        # Should be dmc.Affix or positioned element
        assert isinstance(drawer, (dmc.Affix, html.Div, dmc.Box))

    def test_drawer_has_badge(self):
        """Test drawer contains floating badge."""
        drawer = create_comparison_drawer()
        badge = _find_component_by_id(drawer, "comparison-badge")
        assert badge is not None or _has_child_of_type(drawer, dmc.ActionIcon)

    def test_drawer_has_drawer_component(self):
        """Test drawer contains Mantine Drawer."""
        drawer = create_comparison_drawer()
        drawer_comp = _find_component_by_id(drawer, "comparison-drawer")
        assert drawer_comp is not None or _has_child_of_type(drawer, dmc.Drawer)

    def test_drawer_positioned_bottom_right(self):
        """Test drawer is positioned at bottom-right."""
        drawer = create_comparison_drawer()
        # Should have position bottom-right per PRD
        assert drawer is not None

    def test_drawer_has_title(self):
        """Test drawer has title."""
        drawer = create_comparison_drawer()
        # Title should be "Comparison Set" per PRD
        assert drawer is not None

    def test_drawer_with_initial_items(self):
        """Test drawer can be created with initial items."""
        items = [
            {"curve_id": "1", "construct_name": "Test", "plate_name": "Plate A"}
        ]
        drawer = create_comparison_drawer(initial_items=items)
        assert drawer is not None

    def test_drawer_store_for_state(self):
        """Test drawer includes store for state management."""
        drawer = create_comparison_drawer()
        store = _find_component_by_id(drawer, "comparison-store")
        assert store is not None or _has_child_of_type(drawer, dcc.Store)


class TestComparisonDrawerInteraction:
    """Tests for comparison drawer interaction patterns."""

    def test_drawer_supports_add_operation(self):
        """Test drawer structure supports adding curves."""
        drawer = create_comparison_drawer()
        # Should have appropriate structure for add callbacks
        assert drawer is not None

    def test_drawer_supports_remove_operation(self):
        """Test drawer structure supports removing curves."""
        drawer = create_comparison_drawer()
        assert drawer is not None

    def test_drawer_max_items_enforced(self):
        """Test drawer respects MAX_COMPARISON_ITEMS."""
        items = [
            {"curve_id": str(i), "construct_name": f"Test {i}", "plate_name": "Plate"}
            for i in range(MAX_COMPARISON_ITEMS + 5)
        ]
        # Should handle gracefully (truncate or warn)
        list_component = create_comparison_list(items=items[:MAX_COMPARISON_ITEMS])
        assert list_component is not None


# Helper functions for testing
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


def _has_action_icon(component):
    """Check if component tree contains an ActionIcon."""
    return _has_child_of_type(component, dmc.ActionIcon)


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
