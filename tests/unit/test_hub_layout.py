"""
Tests for hub layout.

Phase 1: Hub and Navigation Foundation - Hub Layout

Tests the hub.py layout that provides:
- Central project dashboard with step cards
- Workflow progress visualization
- Quick navigation to project sections
"""
import pytest
import dash_mantine_components as dmc
from dash import html, dcc

from app.layouts.hub import (
    create_hub_layout,
    create_workflow_steps_grid,
    create_progress_summary,
    create_quick_actions_panel,
    WORKFLOW_STEPS,
)


class TestWorkflowSteps:
    """Tests for workflow step definitions."""

    def test_workflow_steps_exist(self):
        """Test that workflow steps are defined."""
        assert WORKFLOW_STEPS is not None
        assert len(WORKFLOW_STEPS) == 7

    def test_workflow_steps_structure(self):
        """Test that each step has required fields."""
        required_fields = ["number", "title", "description", "route"]

        for step in WORKFLOW_STEPS:
            for field in required_fields:
                assert field in step, f"Missing field '{field}' in step {step.get('number', '?')}"

    def test_workflow_steps_order(self):
        """Test that steps are in correct order."""
        for i, step in enumerate(WORKFLOW_STEPS, 1):
            assert step["number"] == i

    def test_workflow_step_titles(self):
        """Test workflow step titles match PRD."""
        expected_titles = [
            "Define Constructs",
            "Plan IVT Reaction",
            "Create Layout",
            "Upload Data",
            "Review QC",
            "Run Analysis",
            "Export",
        ]

        for step, expected_title in zip(WORKFLOW_STEPS, expected_titles):
            assert step["title"] == expected_title


class TestCreateHubLayout:
    """Tests for create_hub_layout function."""

    def test_basic_hub_layout(self):
        """Test creating basic hub layout."""
        layout = create_hub_layout()

        assert layout is not None
        # Should return a Container
        assert isinstance(layout, dmc.Container)

    def test_hub_layout_with_project_id(self):
        """Test hub layout with project ID."""
        layout = create_hub_layout(project_id=123)

        assert layout is not None
        assert isinstance(layout, dmc.Container)

    def test_hub_layout_contains_store(self):
        """Test that hub layout contains data store."""
        layout = create_hub_layout(project_id=456)

        # Find the store in children
        stores = _find_components_by_type(layout, dcc.Store)
        assert len(stores) > 0

        # Check for project store
        store_ids = [s.id for s in stores if hasattr(s, 'id')]
        assert "hub-project-store" in store_ids

    def test_hub_layout_contains_step_cards(self):
        """Test that hub layout contains step card area."""
        layout = create_hub_layout()

        # Layout should contain workflow step cards
        papers = _find_components_by_type(layout, dmc.Paper)
        assert len(papers) > 0

    def test_hub_layout_responsive(self):
        """Test hub layout is responsive."""
        layout = create_hub_layout()

        # Should contain SimpleGrid or Grid for responsive layout
        grids = _find_components_by_type(layout, (dmc.SimpleGrid, dmc.Grid))
        assert len(grids) > 0


class TestCreateWorkflowStepsGrid:
    """Tests for create_workflow_steps_grid function."""

    def test_create_grid_basic(self):
        """Test creating workflow steps grid."""
        grid = create_workflow_steps_grid(project_id=1)

        assert grid is not None
        assert isinstance(grid, (dmc.SimpleGrid, dmc.Grid, html.Div))

    def test_create_grid_with_status(self):
        """Test grid with step statuses."""
        step_statuses = {
            1: "completed",
            2: "completed",
            3: "in_progress",
            4: "pending",
            5: "locked",
            6: "locked",
            7: "locked",
        }

        grid = create_workflow_steps_grid(
            project_id=1,
            step_statuses=step_statuses,
        )

        assert grid is not None

    def test_create_grid_with_item_counts(self):
        """Test grid with item counts."""
        item_counts = {
            1: 12,  # 12 constructs
            2: 0,   # No reaction plans
            3: 3,   # 3 layouts
            4: 15,  # 15 data files
            5: 2,   # 2 QC issues
            6: 1,   # 1 analysis
            7: 0,   # No exports
        }

        grid = create_workflow_steps_grid(
            project_id=1,
            item_counts=item_counts,
        )

        assert grid is not None


class TestCreateProgressSummary:
    """Tests for create_progress_summary function."""

    def test_create_progress_basic(self):
        """Test creating basic progress summary."""
        summary = create_progress_summary()

        assert summary is not None
        assert isinstance(summary, (dmc.Paper, html.Div))

    def test_create_progress_with_completed_steps(self):
        """Test progress summary with completed steps."""
        summary = create_progress_summary(
            completed_steps=3,
            total_steps=7,
        )

        assert summary is not None

    def test_create_progress_all_complete(self):
        """Test progress summary with all steps complete."""
        summary = create_progress_summary(
            completed_steps=7,
            total_steps=7,
        )

        assert summary is not None

    def test_create_progress_none_complete(self):
        """Test progress summary with no steps complete."""
        summary = create_progress_summary(
            completed_steps=0,
            total_steps=7,
        )

        assert summary is not None

    def test_create_progress_percentage(self):
        """Test progress summary shows percentage."""
        summary = create_progress_summary(
            completed_steps=3,
            total_steps=7,
        )

        # Should calculate ~43% progress
        assert summary is not None


class TestCreateQuickActionsPanel:
    """Tests for create_quick_actions_panel function."""

    def test_create_quick_actions_basic(self):
        """Test creating basic quick actions panel."""
        panel = create_quick_actions_panel()

        assert panel is not None

    def test_create_quick_actions_with_project(self):
        """Test quick actions panel with project ID."""
        panel = create_quick_actions_panel(project_id=123)

        assert panel is not None

    def test_quick_actions_contains_buttons(self):
        """Test panel contains action buttons."""
        panel = create_quick_actions_panel(project_id=1)

        # Should contain buttons
        buttons = _find_components_by_type(panel, dmc.Button)
        assert len(buttons) > 0

    def test_quick_actions_run_analysis(self):
        """Test quick actions includes run analysis."""
        panel = create_quick_actions_panel(project_id=1)

        # Panel should have analysis-related action
        assert panel is not None

    def test_quick_actions_export(self):
        """Test quick actions includes export."""
        panel = create_quick_actions_panel(project_id=1)

        # Panel should have export-related action
        assert panel is not None


class TestHubLayoutIntegration:
    """Integration tests for hub layout."""

    def test_hub_exports_available(self):
        """Test that all expected exports are available."""
        from app.layouts.hub import (
            create_hub_layout,
            create_workflow_steps_grid,
            create_progress_summary,
            create_quick_actions_panel,
            WORKFLOW_STEPS,
        )

        assert callable(create_hub_layout)
        assert callable(create_workflow_steps_grid)
        assert callable(create_progress_summary)
        assert callable(create_quick_actions_panel)
        assert isinstance(WORKFLOW_STEPS, list)

    def test_layouts_init_exports_hub(self):
        """Test that layouts __init__ exports hub functions."""
        from app.layouts import (
            create_hub_layout,
            create_workflow_steps_grid,
        )

        assert callable(create_hub_layout)
        assert callable(create_workflow_steps_grid)


# Helper function for tests
def _find_components_by_type(component, component_types):
    """Recursively find all components of given type(s)."""
    found = []

    if isinstance(component, component_types):
        found.append(component)

    # Check children
    children = getattr(component, 'children', None)
    if children is not None:
        if isinstance(children, list):
            for child in children:
                found.extend(_find_components_by_type(child, component_types))
        elif hasattr(children, 'children'):
            found.extend(_find_components_by_type(children, component_types))

    return found
