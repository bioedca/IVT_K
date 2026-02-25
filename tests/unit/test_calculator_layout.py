"""
Tests for the Calculator UI layout and callbacks.

Phase 2.5.34: Calculator UI tests
"""
import pytest
from datetime import date

from app.layouts.calculator import (
    create_calculator_layout,
    create_recommendation_card,
    create_selected_construct_item,
)


class TestCalculatorLayout:
    """Tests for calculator layout functions."""

    def test_create_calculator_layout_without_project(self):
        """Test creating calculator layout without project ID."""
        layout = create_calculator_layout()
        assert layout is not None

    def test_create_calculator_layout_with_project(self):
        """Test creating calculator layout with project ID."""
        layout = create_calculator_layout(project_id=1)
        assert layout is not None

    def test_layout_contains_required_stores(self):
        """Test that layout contains required dcc.Store components."""
        layout = create_calculator_layout(project_id=1)

        # Convert to string to check for store IDs
        layout_str = str(layout)
        assert "calc-project-store" in layout_str
        assert "calc-selected-constructs" in layout_str
        assert "calc-plan-store" in layout_str
        assert "calc-mode-store" in layout_str

    def test_layout_contains_main_sections(self):
        """Test that layout contains main UI sections."""
        layout = create_calculator_layout(project_id=1)
        layout_str = str(layout)

        # Check for main sections
        assert "calc-first-experiment-wizard" in layout_str
        assert "calc-main-content" in layout_str
        assert "calc-results-section" in layout_str

    def test_layout_contains_control_buttons(self):
        """Test that layout contains control buttons."""
        layout = create_calculator_layout(project_id=1)
        layout_str = str(layout)

        assert "calc-reset-btn" in layout_str
        assert "calc-generate-btn" in layout_str


class TestRecommendationCard:
    """Tests for recommendation card component."""

    def test_create_recommendation_card_basic(self):
        """Test creating a basic recommendation card."""
        card = create_recommendation_card(
            construct_id=1,
            name="Tbox1_M1",
            score=75.0,
            brief_reason="Untested construct",
            detailed_reason="This construct has not been tested yet.",
            is_selected=False,
        )
        assert card is not None

    def test_create_recommendation_card_with_ci(self):
        """Test creating a recommendation card with CI data."""
        card = create_recommendation_card(
            construct_id=1,
            name="Tbox1_M1",
            score=65.0,
            brief_reason="45% precision gap",
            detailed_reason="Needs more replicates to reach target.",
            current_ci=0.52,
            target_ci=0.30,
            replicates_needed=8,
            is_selected=False,
        )
        assert card is not None

    def test_create_recommendation_card_selected(self):
        """Test creating a selected recommendation card."""
        card = create_recommendation_card(
            construct_id=1,
            name="Tbox1_M1",
            score=75.0,
            brief_reason="Untested",
            detailed_reason="Details here",
            is_selected=True,
        )
        # Selected cards have different styling
        assert card is not None


class TestSelectedConstructItem:
    """Tests for selected construct item component."""

    def test_create_selected_construct_item_basic(self):
        """Test creating a basic selected construct item."""
        item = create_selected_construct_item(
            construct_id=1,
            name="Tbox1_M1",
        )
        assert item is not None

    def test_create_selected_construct_item_with_family(self):
        """Test creating a selected construct item with family."""
        item = create_selected_construct_item(
            construct_id=1,
            name="Tbox1_M1",
            family="Tbox1",
        )
        assert item is not None

    def test_create_selected_construct_item_anchor(self):
        """Test creating an anchor construct item."""
        item = create_selected_construct_item(
            construct_id=1,
            name="Reporter-only",
            is_anchor=True,
        )
        # Anchors shouldn't have remove button
        assert item is not None


class TestCalculatorCallbacksIntegration:
    """Integration tests for calculator callbacks with database."""

    def test_detect_planner_mode_first_experiment(self, db_session, test_project):
        """Test detecting first experiment mode for new project."""
        from app.services import SmartPlannerService
        from app.models import Construct
        from app.extensions import db
        from app.calculator import PlannerMode

        project = test_project()

        # Add constructs without data
        construct = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        db.session.add(construct)
        db.session.commit()

        mode = SmartPlannerService.detect_planner_mode(project.id)
        assert mode == PlannerMode.FIRST_EXPERIMENT

    def test_get_recommendations_for_calculator(self, db_session, test_project):
        """Test getting recommendations for calculator display."""
        from app.services import SmartPlannerService
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        constructs = [
            Construct(
                project_id=project.id,
                identifier="Reporter-only",
                family="control",
                is_unregulated=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_WT",
                family="Tbox1",
                is_wildtype=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_M1",
                family="Tbox1",
            ),
        ]
        db.session.add_all(constructs)
        db.session.commit()

        recs = SmartPlannerService.get_recommendations(project.id, max_recommendations=10)
        assert len(recs) > 0

    def test_create_experiment_plan_for_calculator(self, db_session, test_project):
        """Test creating experiment plan through service."""
        from app.services import SmartPlannerService
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        reporter = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        wt = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
        )
        mutant = Construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
        )
        db.session.add_all([reporter, wt, mutant])
        db.session.commit()

        plan = SmartPlannerService.create_experiment_plan(
            project.id,
            [mutant.id],
            replicates=4,
        )

        assert plan is not None
        assert len(plan.constructs) >= 1
        assert plan.total_wells > 0
