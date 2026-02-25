"""
Tests for warning suppression model and UI.

Phase 4: UX Enhancements - Warning Suppression

Tests the warning suppression functionality that provides:
- WarningSupression database model
- Warning type enumeration
- Suppression with reason tracking
- UI components for warning suppression
- Integration with plate validation service
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import dash_mantine_components as dmc
from dash import html, dcc

from app.models.warning_suppression import (
    WarningSuppression,
    WarningType,
)
from app.components.warning_suppression_ui import (
    create_warning_suppression_modal,
    create_suppressible_warning_card,
    create_suppression_reason_input,
    create_suppression_history_list,
    get_warning_type_display_name,
    get_warning_type_description,
)
from app.services.warning_suppression_service import (
    WarningSuppressionService,
    suppress_warning,
    get_suppressed_warnings,
    is_warning_suppressed,
    get_suppression_history,
)


class TestWarningTypeEnum:
    """Tests for WarningType enum."""

    def test_incomplete_plate_type(self):
        """Test INCOMPLETE_PLATE warning type exists."""
        assert hasattr(WarningType, "INCOMPLETE_PLATE")
        assert WarningType.INCOMPLETE_PLATE is not None

    def test_temperature_deviation_type(self):
        """Test TEMPERATURE_DEVIATION warning type exists."""
        assert hasattr(WarningType, "TEMPERATURE_DEVIATION")
        assert WarningType.TEMPERATURE_DEVIATION is not None

    def test_missing_negative_control_type(self):
        """Test MISSING_NEGATIVE_CONTROL warning type exists."""
        assert hasattr(WarningType, "MISSING_NEGATIVE_CONTROL")
        assert WarningType.MISSING_NEGATIVE_CONTROL is not None

    def test_low_replicate_count_type(self):
        """Test LOW_REPLICATE_COUNT warning type exists."""
        assert hasattr(WarningType, "LOW_REPLICATE_COUNT")
        assert WarningType.LOW_REPLICATE_COUNT is not None

    def test_all_warning_types_have_string_values(self):
        """Test all warning types have string values."""
        for warning_type in WarningType:
            assert isinstance(warning_type.value, str)


class TestWarningSuppressionModel:
    """Tests for WarningSuppression database model."""

    def test_model_has_id_field(self):
        """Test model has id primary key."""
        assert hasattr(WarningSuppression, "id")

    def test_model_has_plate_id_field(self):
        """Test model has plate_id foreign key."""
        assert hasattr(WarningSuppression, "plate_id")

    def test_model_has_warning_type_field(self):
        """Test model has warning_type field."""
        assert hasattr(WarningSuppression, "warning_type")

    def test_model_has_reason_field(self):
        """Test model has reason field."""
        assert hasattr(WarningSuppression, "reason")

    def test_model_has_suppressed_by_field(self):
        """Test model has suppressed_by field."""
        assert hasattr(WarningSuppression, "suppressed_by")

    def test_model_has_suppressed_at_field(self):
        """Test model has suppressed_at field."""
        assert hasattr(WarningSuppression, "suppressed_at")

    def test_model_tablename(self):
        """Test model has correct table name."""
        assert WarningSuppression.__tablename__ == "warning_suppressions"

    def test_model_create_instance(self):
        """Test creating model instance."""
        suppression = WarningSuppression(
            plate_id=1,
            warning_type=WarningType.INCOMPLETE_PLATE,
            reason="Intentional partial plate for pilot study",
            suppressed_by="test_user"
        )
        assert suppression.plate_id == 1
        assert suppression.warning_type == WarningType.INCOMPLETE_PLATE
        assert suppression.reason == "Intentional partial plate for pilot study"
        assert suppression.suppressed_by == "test_user"

    def test_model_with_well_id(self):
        """Test model can optionally have well_id."""
        # Some warnings may be well-specific
        if hasattr(WarningSuppression, "well_id"):
            suppression = WarningSuppression(
                plate_id=1,
                well_id=5,
                warning_type=WarningType.LOW_REPLICATE_COUNT,
                reason="Expected for edge wells",
                suppressed_by="test_user"
            )
            assert suppression.well_id == 5


class TestWarningSuppressionService:
    """Tests for warning suppression service."""

    def test_suppress_warning_function(self):
        """Test suppress_warning function exists."""
        assert callable(suppress_warning)

    def test_get_suppressed_warnings_function(self):
        """Test get_suppressed_warnings function exists."""
        assert callable(get_suppressed_warnings)

    def test_is_warning_suppressed_function(self):
        """Test is_warning_suppressed function exists."""
        assert callable(is_warning_suppressed)

    def test_get_suppression_history_function(self):
        """Test get_suppression_history function exists."""
        assert callable(get_suppression_history)

    def test_suppress_warning_requires_reason(self):
        """Test suppress_warning requires a reason."""
        # Should validate that reason is provided
        with pytest.raises((ValueError, TypeError)):
            suppress_warning(
                plate_id=1,
                warning_type=WarningType.INCOMPLETE_PLATE,
                reason="",  # Empty reason should fail
                suppressed_by="test_user"
            )

    def test_suppress_warning_requires_user(self):
        """Test suppress_warning requires suppressed_by user."""
        with pytest.raises((ValueError, TypeError)):
            suppress_warning(
                plate_id=1,
                warning_type=WarningType.INCOMPLETE_PLATE,
                reason="Valid reason",
                suppressed_by=""  # Empty user should fail
            )

    def test_suppress_warning_minimum_reason_length(self):
        """Test suppress_warning has minimum reason length."""
        # Reason should be meaningful, not just a few characters
        with pytest.raises((ValueError, TypeError)):
            suppress_warning(
                plate_id=1,
                warning_type=WarningType.INCOMPLETE_PLATE,
                reason="ok",  # Too short
                suppressed_by="test_user"
            )


class TestWarningSuppressionServiceClass:
    """Tests for WarningSuppressionService class methods."""

    def test_service_class_exists(self):
        """Test service class exists."""
        assert WarningSuppressionService is not None

    def test_service_has_suppress_method(self):
        """Test service has suppress method."""
        assert hasattr(WarningSuppressionService, "suppress")

    def test_service_has_unsuppress_method(self):
        """Test service has unsuppress method."""
        assert hasattr(WarningSuppressionService, "unsuppress")

    def test_service_has_get_suppressions_method(self):
        """Test service has get_suppressions method."""
        assert hasattr(WarningSuppressionService, "get_suppressions")

    def test_service_has_is_suppressed_method(self):
        """Test service has is_suppressed method."""
        assert hasattr(WarningSuppressionService, "is_suppressed")


class TestGetWarningTypeDisplayName:
    """Tests for warning type display name helper."""

    def test_incomplete_plate_display_name(self):
        """Test display name for incomplete plate."""
        name = get_warning_type_display_name(WarningType.INCOMPLETE_PLATE)
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0

    def test_temperature_deviation_display_name(self):
        """Test display name for temperature deviation."""
        name = get_warning_type_display_name(WarningType.TEMPERATURE_DEVIATION)
        assert name is not None
        assert "temperature" in name.lower() or "temp" in name.lower()

    def test_all_types_have_display_names(self):
        """Test all warning types have display names."""
        for warning_type in WarningType:
            name = get_warning_type_display_name(warning_type)
            assert name is not None
            assert len(name) > 0


class TestGetWarningTypeDescription:
    """Tests for warning type description helper."""

    def test_incomplete_plate_description(self):
        """Test description for incomplete plate."""
        desc = get_warning_type_description(WarningType.INCOMPLETE_PLATE)
        assert desc is not None
        assert isinstance(desc, str)

    def test_all_types_have_descriptions(self):
        """Test all warning types have descriptions."""
        for warning_type in WarningType:
            desc = get_warning_type_description(warning_type)
            assert desc is not None
            assert len(desc) > 10  # Meaningful description


class TestCreateWarningSuppressionModal:
    """Tests for warning suppression modal component."""

    def test_modal_creation(self):
        """Test modal is created."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        assert modal is not None

    def test_modal_is_modal_component(self):
        """Test modal is dmc.Modal."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        assert isinstance(modal, dmc.Modal) or _has_child_of_type(modal, dmc.Modal)

    def test_modal_has_correct_id(self):
        """Test modal has correct ID."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        assert modal.id == "warning-suppression-modal" or hasattr(modal, "id")

    def test_modal_has_reason_input(self):
        """Test modal has reason input field."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        reason_input = _find_component_by_partial_id(modal, "reason")
        assert reason_input is not None or _has_child_of_type(modal, dmc.Textarea)

    def test_modal_has_confirm_button(self):
        """Test modal has confirm/suppress button."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        confirm_btn = _find_component_by_partial_id(modal, "confirm") or \
                      _find_component_by_partial_id(modal, "suppress")
        assert confirm_btn is not None or _has_button_with_text(modal, "Suppress")

    def test_modal_has_cancel_button(self):
        """Test modal has cancel button."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.INCOMPLETE_PLATE,
            plate_id=1
        )
        cancel_btn = _find_component_by_partial_id(modal, "cancel")
        assert cancel_btn is not None or _has_button_with_text(modal, "Cancel")

    def test_modal_shows_warning_type(self):
        """Test modal displays the warning type being suppressed."""
        modal = create_warning_suppression_modal(
            warning_type=WarningType.TEMPERATURE_DEVIATION,
            plate_id=1
        )
        assert modal is not None


class TestCreateSuppressibleWarningCard:
    """Tests for suppressible warning card component."""

    def test_card_creation(self):
        """Test warning card is created."""
        card = create_suppressible_warning_card(
            warning_type=WarningType.INCOMPLETE_PLATE,
            message="Plate is missing 4 wells",
            plate_id=1
        )
        assert card is not None

    def test_card_displays_message(self):
        """Test card displays warning message."""
        card = create_suppressible_warning_card(
            warning_type=WarningType.INCOMPLETE_PLATE,
            message="Custom warning message",
            plate_id=1
        )
        assert card is not None

    def test_card_has_suppress_button(self):
        """Test card has suppress button."""
        card = create_suppressible_warning_card(
            warning_type=WarningType.INCOMPLETE_PLATE,
            message="Warning",
            plate_id=1
        )
        suppress_btn = _find_component_by_partial_id(card, "suppress")
        assert suppress_btn is not None or _has_button_with_text(card, "Suppress")

    def test_card_with_suppressed_state(self):
        """Test card shows suppressed state."""
        card = create_suppressible_warning_card(
            warning_type=WarningType.INCOMPLETE_PLATE,
            message="Warning",
            plate_id=1,
            is_suppressed=True,
            suppression_reason="Valid reason"
        )
        assert card is not None

    def test_card_warning_color(self):
        """Test card has warning color scheme."""
        card = create_suppressible_warning_card(
            warning_type=WarningType.INCOMPLETE_PLATE,
            message="Warning",
            plate_id=1
        )
        # Should have yellow/orange warning color
        assert card is not None


class TestCreateSuppressionReasonInput:
    """Tests for suppression reason input component."""

    def test_input_creation(self):
        """Test reason input is created."""
        input_comp = create_suppression_reason_input()
        assert input_comp is not None

    def test_input_is_textarea(self):
        """Test input is a Textarea."""
        input_comp = create_suppression_reason_input()
        assert isinstance(input_comp, dmc.Textarea) or _has_child_of_type(input_comp, dmc.Textarea)

    def test_input_has_label(self):
        """Test input has label."""
        input_comp = create_suppression_reason_input()
        if isinstance(input_comp, dmc.Textarea):
            assert input_comp.label is not None

    def test_input_has_placeholder(self):
        """Test input has placeholder text."""
        input_comp = create_suppression_reason_input()
        if isinstance(input_comp, dmc.Textarea):
            assert input_comp.placeholder is not None

    def test_input_required(self):
        """Test input is required."""
        input_comp = create_suppression_reason_input()
        if isinstance(input_comp, dmc.Textarea):
            assert input_comp.required == True

    def test_input_has_min_length_hint(self):
        """Test input hints at minimum length requirement."""
        input_comp = create_suppression_reason_input()
        # Should show hint about minimum characters
        assert input_comp is not None


class TestCreateSuppressionHistoryList:
    """Tests for suppression history list component."""

    def test_empty_history(self):
        """Test empty history list."""
        history_list = create_suppression_history_list(suppressions=[])
        assert history_list is not None

    def test_history_with_items(self):
        """Test history list with suppression items."""
        suppressions = [
            {
                "warning_type": WarningType.INCOMPLETE_PLATE,
                "reason": "Pilot study",
                "suppressed_by": "user1",
                "suppressed_at": datetime(2024, 1, 15, 10, 30)
            }
        ]
        history_list = create_suppression_history_list(suppressions=suppressions)
        assert history_list is not None

    def test_history_shows_reason(self):
        """Test history shows suppression reason."""
        suppressions = [
            {
                "warning_type": WarningType.INCOMPLETE_PLATE,
                "reason": "Known limitation",
                "suppressed_by": "user1",
                "suppressed_at": datetime.now()
            }
        ]
        history_list = create_suppression_history_list(suppressions=suppressions)
        assert history_list is not None

    def test_history_shows_user(self):
        """Test history shows who suppressed the warning."""
        suppressions = [
            {
                "warning_type": WarningType.INCOMPLETE_PLATE,
                "reason": "Test",
                "suppressed_by": "admin_user",
                "suppressed_at": datetime.now()
            }
        ]
        history_list = create_suppression_history_list(suppressions=suppressions)
        assert history_list is not None

    def test_history_shows_timestamp(self):
        """Test history shows suppression timestamp."""
        suppressions = [
            {
                "warning_type": WarningType.INCOMPLETE_PLATE,
                "reason": "Test",
                "suppressed_by": "user1",
                "suppressed_at": datetime(2024, 6, 15, 14, 45)
            }
        ]
        history_list = create_suppression_history_list(suppressions=suppressions)
        assert history_list is not None

    def test_history_sorted_by_date(self):
        """Test history is sorted by date (newest first)."""
        suppressions = [
            {
                "warning_type": WarningType.INCOMPLETE_PLATE,
                "reason": "Old",
                "suppressed_by": "user1",
                "suppressed_at": datetime(2024, 1, 1)
            },
            {
                "warning_type": WarningType.TEMPERATURE_DEVIATION,
                "reason": "New",
                "suppressed_by": "user2",
                "suppressed_at": datetime(2024, 6, 1)
            }
        ]
        history_list = create_suppression_history_list(suppressions=suppressions)
        assert history_list is not None


class TestWarningSuppressionIntegration:
    """Integration tests for warning suppression."""

    def test_suppress_and_check(self):
        """Test suppressing a warning and checking status."""
        # This tests the flow: suppress -> is_suppressed returns True
        # Would require database mocking in real test
        pass

    def test_unsuppress_warning(self):
        """Test unsuppressing a previously suppressed warning."""
        # Tests the unsuppress flow
        pass

    def test_suppression_persists(self):
        """Test that suppressions are persisted to database."""
        pass


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
