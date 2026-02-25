"""
Tests for step card component.

Phase 1: Hub and Navigation Foundation - Step Card Component

Tests the step_card.py component that provides:
- Visual workflow step cards with status indicators
- Lock/unlock state management
- Step dependency visualization
"""
import pytest
import dash_mantine_components as dmc
from dash import html

from app.components.step_card import (
    create_step_card,
    StepStatus,
    get_status_color,
    get_status_icon,
)


class TestStepStatus:
    """Tests for StepStatus enumeration."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert StepStatus.LOCKED == "locked"
        assert StepStatus.PENDING == "pending"
        assert StepStatus.IN_PROGRESS == "in_progress"
        assert StepStatus.COMPLETED == "completed"

    def test_status_iteration(self):
        """Test that we can iterate over all statuses."""
        statuses = list(StepStatus)
        assert len(statuses) == 4


class TestGetStatusColor:
    """Tests for get_status_color helper function."""

    def test_locked_color(self):
        """Test locked status returns gray color."""
        assert get_status_color(StepStatus.LOCKED) == "gray"

    def test_pending_color(self):
        """Test pending status returns yellow color."""
        assert get_status_color(StepStatus.PENDING) == "yellow"

    def test_in_progress_color(self):
        """Test in_progress status returns blue color."""
        assert get_status_color(StepStatus.IN_PROGRESS) == "blue"

    def test_completed_color(self):
        """Test completed status returns green color."""
        assert get_status_color(StepStatus.COMPLETED) == "green"

    def test_string_status(self):
        """Test that string values also work."""
        assert get_status_color("locked") == "gray"
        assert get_status_color("pending") == "yellow"
        assert get_status_color("in_progress") == "blue"
        assert get_status_color("completed") == "green"

    def test_unknown_status_default(self):
        """Test unknown status returns default gray."""
        assert get_status_color("unknown") == "gray"


class TestGetStatusIcon:
    """Tests for get_status_icon helper function."""

    def test_locked_icon(self):
        """Test locked status returns lock icon."""
        assert "lock" in get_status_icon(StepStatus.LOCKED)

    def test_pending_icon(self):
        """Test pending status returns circle icon."""
        assert "circle" in get_status_icon(StepStatus.PENDING)

    def test_in_progress_icon(self):
        """Test in_progress status returns clock/progress icon."""
        icon = get_status_icon(StepStatus.IN_PROGRESS)
        assert "progress" in icon or "clock" in icon

    def test_completed_icon(self):
        """Test completed status returns check icon."""
        assert "check" in get_status_icon(StepStatus.COMPLETED)


class TestCreateStepCard:
    """Tests for create_step_card function."""

    def test_basic_step_card(self):
        """Test creating a basic step card."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add your T-box constructs",
        )

        assert card is not None
        # Should return a Paper component
        assert isinstance(card, dmc.Paper)

    def test_step_card_with_all_parameters(self):
        """Test step card with all parameters."""
        card = create_step_card(
            step_number=3,
            title="Create Layout",
            description="Define plate layout",
            status=StepStatus.PENDING,
            item_count=5,
            item_label="constructs",
            href="/project/1/layouts",
            blockers=["At least one construct required"],
        )

        assert card is not None
        assert isinstance(card, dmc.Paper)

    def test_step_card_locked(self):
        """Test step card in locked state."""
        card = create_step_card(
            step_number=4,
            title="Upload Data",
            description="Upload experimental data",
            status=StepStatus.LOCKED,
        )

        assert card is not None
        # Card should indicate locked state visually
        assert isinstance(card, dmc.Paper)

    def test_step_card_completed(self):
        """Test step card in completed state."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add constructs",
            status=StepStatus.COMPLETED,
            item_count=12,
            item_label="constructs",
        )

        assert card is not None
        assert isinstance(card, dmc.Paper)

    def test_step_card_in_progress(self):
        """Test step card in progress state."""
        card = create_step_card(
            step_number=2,
            title="Plan IVT Reaction",
            description="Plan your experiment",
            status=StepStatus.IN_PROGRESS,
        )

        assert card is not None
        assert isinstance(card, dmc.Paper)

    def test_step_card_with_blockers(self):
        """Test step card displays blockers."""
        blockers = [
            "Project must be created",
            "At least one construct required",
        ]
        card = create_step_card(
            step_number=3,
            title="Create Layout",
            description="Define plate layout",
            status=StepStatus.LOCKED,
            blockers=blockers,
        )

        assert card is not None

    def test_step_card_zero_items(self):
        """Test step card with zero item count."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add constructs",
            status=StepStatus.PENDING,
            item_count=0,
            item_label="constructs",
        )

        assert card is not None

    def test_step_card_large_item_count(self):
        """Test step card with large item count."""
        card = create_step_card(
            step_number=4,
            title="Upload Data",
            description="Upload data files",
            status=StepStatus.COMPLETED,
            item_count=1000,
            item_label="files",
        )

        assert card is not None

    def test_step_card_custom_id(self):
        """Test step card with custom ID."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add constructs",
            card_id="custom-step-card-1",
        )

        assert card is not None
        assert card.id == "custom-step-card-1"

    def test_step_card_optional_href(self):
        """Test step card without href."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add constructs",
            href=None,
        )

        assert card is not None

    def test_step_card_with_href(self):
        """Test step card with navigation href."""
        card = create_step_card(
            step_number=1,
            title="Define Constructs",
            description="Add constructs",
            href="/project/123/constructs",
        )

        assert card is not None


class TestStepCardIntegration:
    """Integration tests for step card component."""

    def test_all_workflow_steps(self):
        """Test creating cards for all workflow steps."""
        steps = [
            (1, "Define Constructs", "Add T-box constructs"),
            (2, "Plan IVT Reaction", "Plan your experiment"),
            (3, "Create Layout", "Define plate layout"),
            (4, "Upload Data", "Upload experimental data"),
            (5, "Review QC", "Review quality control"),
            (6, "Run Analysis", "Run statistical analysis"),
            (7, "Export Results", "Export and publish"),
        ]

        for step_num, title, desc in steps:
            card = create_step_card(
                step_number=step_num,
                title=title,
                description=desc,
            )
            assert card is not None
            assert isinstance(card, dmc.Paper)

    def test_mixed_status_cards(self):
        """Test creating cards with mixed statuses."""
        statuses = [
            StepStatus.COMPLETED,
            StepStatus.COMPLETED,
            StepStatus.IN_PROGRESS,
            StepStatus.PENDING,
            StepStatus.LOCKED,
            StepStatus.LOCKED,
            StepStatus.LOCKED,
        ]

        for i, status in enumerate(statuses, 1):
            card = create_step_card(
                step_number=i,
                title=f"Step {i}",
                description=f"Description for step {i}",
                status=status,
            )
            assert card is not None


class TestStepCardAccessibility:
    """Accessibility tests for step card component."""

    def test_card_has_clickable_indicator(self):
        """Test that unlocked cards indicate clickability."""
        card = create_step_card(
            step_number=1,
            title="Test Step",
            description="Test description",
            status=StepStatus.PENDING,
            href="/test",
        )

        assert card is not None
        # Card should have cursor pointer style when clickable
        assert card.style is not None
        assert card.style.get("cursor") == "pointer"

    def test_locked_card_not_clickable(self):
        """Test that locked cards indicate non-clickability."""
        card = create_step_card(
            step_number=1,
            title="Test Step",
            description="Test description",
            status=StepStatus.LOCKED,
        )

        assert card is not None
        # Locked cards should have default or not-allowed cursor
        if card.style:
            cursor = card.style.get("cursor")
            assert cursor in [None, "default", "not-allowed"]
