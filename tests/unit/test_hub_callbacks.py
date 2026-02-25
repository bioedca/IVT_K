"""
Tests for hub callbacks.

Phase 1: Hub and Navigation Foundation - Hub Callbacks

Tests the hub_callbacks.py module that provides:
- Step unlock logic based on project state
- Step status computation
- Navigation callbacks
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.callbacks.hub_callbacks import (
    compute_step_statuses,
    check_step_unlock,
    get_step_blockers,
    StepDependencies,
)


class TestStepDependencies:
    """Tests for StepDependencies class."""

    def test_step_1_dependencies(self):
        """Test Step 1 (Define Constructs) dependencies."""
        # Step 1 requires: Project created
        deps = StepDependencies.get_dependencies(1)

        assert deps is not None
        assert "project_exists" in deps

    def test_step_2_dependencies(self):
        """Test Step 2 (Plan IVT) dependencies."""
        # Step 2 requires: Project created (optional step)
        deps = StepDependencies.get_dependencies(2)

        assert deps is not None
        assert "project_exists" in deps

    def test_step_3_dependencies(self):
        """Test Step 3 (Create Layout) dependencies."""
        # Step 3 requires: At least one construct defined
        deps = StepDependencies.get_dependencies(3)

        assert deps is not None
        assert "has_constructs" in deps

    def test_step_4_dependencies(self):
        """Test Step 4 (Upload Data) dependencies."""
        # Step 4 requires: Layout exists
        deps = StepDependencies.get_dependencies(4)

        assert deps is not None
        assert "has_layouts" in deps

    def test_step_5_dependencies(self):
        """Test Step 5 (Review QC) dependencies."""
        # Step 5 requires: Data uploaded
        deps = StepDependencies.get_dependencies(5)

        assert deps is not None
        assert "has_data" in deps

    def test_step_6_dependencies(self):
        """Test Step 6 (Run Analysis) dependencies."""
        # Step 6 requires: All QC issues addressed
        deps = StepDependencies.get_dependencies(6)

        assert deps is not None
        assert "qc_passed" in deps

    def test_step_7_dependencies(self):
        """Test Step 7 (Export Results) dependencies."""
        # Step 7 requires: Analysis completed
        deps = StepDependencies.get_dependencies(7)

        assert deps is not None
        assert "has_analysis" in deps


class TestCheckStepUnlock:
    """Tests for check_step_unlock function."""

    def test_step_1_unlocked_with_project(self):
        """Test Step 1 unlocks when project exists."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=1, project_state=project_state)
        assert is_unlocked is True

    def test_step_1_locked_without_project(self):
        """Test Step 1 locked when no project."""
        project_state = None

        is_unlocked = check_step_unlock(step_number=1, project_state=project_state)
        assert is_unlocked is False

    def test_step_3_unlocked_with_constructs(self):
        """Test Step 3 unlocks when constructs exist."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=3, project_state=project_state)
        assert is_unlocked is True

    def test_step_3_locked_without_constructs(self):
        """Test Step 3 locked when no constructs."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=3, project_state=project_state)
        assert is_unlocked is False

    def test_step_4_unlocked_with_layouts(self):
        """Test Step 4 unlocks when layouts exist."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=4, project_state=project_state)
        assert is_unlocked is True

    def test_step_4_locked_without_layouts(self):
        """Test Step 4 locked when no layouts."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=4, project_state=project_state)
        assert is_unlocked is False

    def test_step_5_unlocked_with_data(self):
        """Test Step 5 unlocks when data uploaded."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=5, project_state=project_state)
        assert is_unlocked is True

    def test_step_6_unlocked_with_qc_passed(self):
        """Test Step 6 unlocks when QC passed."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": True,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=6, project_state=project_state)
        assert is_unlocked is True

    def test_step_6_locked_without_qc(self):
        """Test Step 6 locked when QC not passed."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": False,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=6, project_state=project_state)
        assert is_unlocked is False

    def test_step_7_unlocked_with_analysis(self):
        """Test Step 7 unlocks when analysis completed."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": True,
            "analysis_count": 1,
        }

        is_unlocked = check_step_unlock(step_number=7, project_state=project_state)
        assert is_unlocked is True

    def test_step_7_locked_without_analysis(self):
        """Test Step 7 locked when no analysis."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": True,
            "analysis_count": 0,
        }

        is_unlocked = check_step_unlock(step_number=7, project_state=project_state)
        assert is_unlocked is False


class TestGetStepBlockers:
    """Tests for get_step_blockers function."""

    def test_step_1_no_blockers(self):
        """Test Step 1 has no blockers when project exists."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
        }

        blockers = get_step_blockers(step_number=1, project_state=project_state)
        assert blockers == []

    def test_step_3_blocker_no_constructs(self):
        """Test Step 3 blocker when no constructs."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
        }

        blockers = get_step_blockers(step_number=3, project_state=project_state)
        assert len(blockers) > 0
        assert any("construct" in b.lower() for b in blockers)

    def test_step_4_blocker_no_layouts(self):
        """Test Step 4 blocker when no layouts."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 0,
        }

        blockers = get_step_blockers(step_number=4, project_state=project_state)
        assert len(blockers) > 0
        assert any("layout" in b.lower() for b in blockers)

    def test_step_6_blocker_qc_not_passed(self):
        """Test Step 6 blocker when QC not passed."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 10,
            "qc_passed": False,
            "qc_issues_count": 3,
        }

        blockers = get_step_blockers(step_number=6, project_state=project_state)
        assert len(blockers) > 0
        assert any("qc" in b.lower() for b in blockers)

    def test_multiple_blockers(self):
        """Test step with multiple blockers."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
            "layout_count": 0,
        }

        # Step 4 blocked by both constructs and layouts
        blockers = get_step_blockers(step_number=4, project_state=project_state)
        # Should have at least one blocker
        assert len(blockers) >= 1


class TestComputeStepStatuses:
    """Tests for compute_step_statuses function."""

    def test_new_project_statuses(self):
        """Test statuses for a new project."""
        project_state = {
            "project_id": 1,
            "construct_count": 0,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        statuses = compute_step_statuses(project_state)

        assert statuses[1] in ["pending", "in_progress"]  # Define constructs
        assert statuses[2] in ["pending", "in_progress"]  # Plan IVT (optional)
        assert statuses[3] == "locked"  # Create layout (needs constructs)
        assert statuses[4] == "locked"  # Upload data (needs layouts)
        assert statuses[5] == "locked"  # Review QC (needs data)
        assert statuses[6] == "locked"  # Run analysis (needs QC)
        assert statuses[7] == "locked"  # Export (needs analysis)

    def test_partial_progress_statuses(self):
        """Test statuses for partial progress."""
        project_state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 2,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }

        statuses = compute_step_statuses(project_state)

        assert statuses[1] == "completed"  # Has constructs
        assert statuses[3] == "completed"  # Has layouts
        assert statuses[4] in ["pending", "in_progress"]  # Ready for data
        assert statuses[5] == "locked"  # Needs data
        assert statuses[6] == "locked"  # Needs QC
        assert statuses[7] == "locked"  # Needs analysis

    def test_complete_project_statuses(self):
        """Test statuses for complete project."""
        project_state = {
            "project_id": 1,
            "construct_count": 10,
            "layout_count": 3,
            "data_count": 50,
            "qc_passed": True,
            "analysis_count": 2,
        }

        statuses = compute_step_statuses(project_state)

        assert statuses[1] == "completed"
        assert statuses[3] == "completed"
        assert statuses[4] == "completed"
        assert statuses[5] == "completed"
        assert statuses[6] == "completed"
        # Step 7 might be pending or completed depending on exports
        assert statuses[7] in ["pending", "in_progress", "completed"]

    def test_no_project_statuses(self):
        """Test statuses when no project."""
        project_state = None

        statuses = compute_step_statuses(project_state)

        # All steps should be locked
        for step_num in range(1, 8):
            assert statuses[step_num] == "locked"


class TestHubCallbacksIntegration:
    """Integration tests for hub callbacks."""

    def test_exports_available(self):
        """Test that all expected exports are available."""
        from app.callbacks.hub_callbacks import (
            compute_step_statuses,
            check_step_unlock,
            get_step_blockers,
            StepDependencies,
            register_hub_callbacks,
        )

        assert callable(compute_step_statuses)
        assert callable(check_step_unlock)
        assert callable(get_step_blockers)
        assert StepDependencies is not None
        assert callable(register_hub_callbacks)

    def test_callbacks_init_registers_hub(self):
        """Test that callbacks __init__ includes hub callbacks."""
        # This test verifies the import works
        from app.callbacks import register_callbacks

        assert callable(register_callbacks)


class TestStepStatusTransitions:
    """Tests for step status transitions."""

    def test_status_progression(self):
        """Test that statuses progress correctly."""
        # Start with new project
        state1 = {
            "project_id": 1,
            "construct_count": 0,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
        }
        statuses1 = compute_step_statuses(state1)

        # Add constructs
        state2 = dict(state1, construct_count=5)
        statuses2 = compute_step_statuses(state2)

        # Step 1 should progress from pending to completed
        assert statuses1[1] in ["pending", "in_progress"]
        assert statuses2[1] == "completed"

        # Step 3 should unlock
        assert statuses1[3] == "locked"
        assert statuses2[3] in ["pending", "in_progress"]

    def test_step_2_optional(self):
        """Test that Step 2 (Plan IVT) is optional."""
        # Project with constructs but no IVT plan
        state = {
            "project_id": 1,
            "construct_count": 5,
            "layout_count": 0,
            "data_count": 0,
            "qc_passed": False,
            "analysis_count": 0,
            "ivt_plan_count": 0,
        }

        statuses = compute_step_statuses(state)

        # Step 3 should still be unlocked even without Step 2 complete
        assert statuses[3] in ["pending", "in_progress"]
