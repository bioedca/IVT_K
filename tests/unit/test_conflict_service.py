"""Unit tests for ConflictDetectionService."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.models import Project, AuditLog
from app.services.conflict_service import (
    ConflictDetectionService,
    ConflictResolution,
    ConflictInfo,
    check_and_save_with_conflict_detection
)


class TestConflictDetectionService:
    """Tests for conflict detection (Phase 1.12)."""

    def test_track_entity_load(self, db_session):
        """T1.16: updated_at timestamp set on create."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        # Track the load
        loaded_at = project.updated_at
        ConflictDetectionService.track_entity_load(
            entity_type="projects",
            entity_id=project.id,
            updated_at=loaded_at,
            session_id="test-session"
        )

        # Verify tracking
        tracked = ConflictDetectionService.get_loaded_timestamp(
            entity_type="projects",
            entity_id=project.id,
            session_id="test-session"
        )
        assert tracked == loaded_at

    def test_updated_at_set_on_create(self, db_session):
        """T1.16: updated_at timestamp set on create."""
        project = Project(name="New Project")
        db_session.add(project)
        db_session.commit()

        assert project.updated_at is not None
        assert project.created_at is not None
        # updated_at should be close to created_at
        delta = abs((project.updated_at - project.created_at).total_seconds())
        assert delta < 1  # Within 1 second

    def test_updated_at_updates_on_modify(self, db_session):
        """T1.17: updated_at timestamp updates on modify."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        original_updated_at = project.updated_at

        # Wait a tiny bit and modify
        import time
        time.sleep(0.01)
        project.name = "Modified Project"
        db_session.commit()

        # Refresh to get updated timestamp
        db_session.refresh(project)

        assert project.updated_at > original_updated_at

    def test_no_conflict_when_unchanged(self, db_session):
        """Test no conflict detected when entity unchanged."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at

        # Check for conflict - should be None
        conflict = ConflictDetectionService.check_for_conflict(
            project, loaded_at
        )

        assert conflict is None

    def test_conflict_detected_when_changed(self, db_session):
        """T1.18: Conflict detection when updated_at changed."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        # Simulate loading the entity
        loaded_at = project.updated_at

        # Simulate another user making changes
        import time
        time.sleep(0.01)
        project.name = "Changed by other user"
        project.updated_at = datetime.utcnow()
        db_session.commit()

        # Now check for conflict with the original loaded_at
        original_state = {"name": "Test Project"}
        conflict = ConflictDetectionService.check_for_conflict(
            project, loaded_at, original_state
        )

        assert conflict is not None
        assert conflict.has_conflict is True
        assert conflict.entity_type == "projects"
        assert conflict.entity_id == project.id
        assert conflict.current_updated_at > loaded_at

    def test_conflict_info_field_changes(self, db_session):
        """Test field changes are captured in conflict info."""
        project = Project(name="Original Name", description="Original Desc")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at
        original_state = {
            "name": "Original Name",
            "description": "Original Desc"
        }

        # Modify the project
        import time
        time.sleep(0.01)
        project.name = "New Name"
        project.updated_at = datetime.utcnow()
        db_session.commit()

        conflict = ConflictDetectionService.check_for_conflict(
            project, loaded_at, original_state
        )

        assert conflict is not None
        assert "name" in conflict.field_changes
        old_name, new_name = conflict.field_changes["name"]
        assert old_name == "Original Name"
        assert new_name == "New Name"

    def test_conflict_info_to_dict(self, db_session):
        """Test ConflictInfo serialization."""
        loaded_at = datetime(2024, 1, 1, 12, 0, 0)
        current_at = datetime(2024, 1, 1, 12, 5, 0)

        conflict = ConflictInfo(
            entity_type="projects",
            entity_id=1,
            loaded_at=loaded_at,
            current_updated_at=current_at,
            other_user="other_user",
            field_changes={"name": ("Old", "New")}
        )

        data = conflict.to_dict()

        assert data["entity_type"] == "projects"
        assert data["entity_id"] == 1
        assert data["other_user"] == "other_user"
        assert data["has_conflict"] is True
        assert "name" in data["field_changes"]

    def test_clear_entity_tracking(self, db_session):
        """Test clearing tracking for specific entity."""
        ConflictDetectionService.track_entity_load(
            entity_type="projects",
            entity_id=1,
            updated_at=datetime.utcnow(),
            session_id="test"
        )

        # Verify tracked
        assert ConflictDetectionService.get_loaded_timestamp(
            "projects", 1, "test"
        ) is not None

        # Clear tracking
        ConflictDetectionService.clear_entity_tracking(
            "projects", 1, "test"
        )

        # Verify cleared
        assert ConflictDetectionService.get_loaded_timestamp(
            "projects", 1, "test"
        ) is None

    def test_clear_all_tracking(self, db_session):
        """Test clearing all tracking for a session."""
        session_id = "test-clear-all"

        ConflictDetectionService.track_entity_load(
            "projects", 1, datetime.utcnow(), session_id
        )
        ConflictDetectionService.track_entity_load(
            "constructs", 2, datetime.utcnow(), session_id
        )

        # Clear all
        ConflictDetectionService.clear_tracking(session_id)

        # Verify all cleared
        assert ConflictDetectionService.get_loaded_timestamp(
            "projects", 1, session_id
        ) is None
        assert ConflictDetectionService.get_loaded_timestamp(
            "constructs", 2, session_id
        ) is None


class TestConflictResolution:
    """Tests for conflict resolution options."""

    def test_resolution_enum_values(self):
        """Test ConflictResolution enum has expected values."""
        assert ConflictResolution.OVERWRITE.value == "overwrite"
        assert ConflictResolution.RELOAD.value == "reload"
        assert ConflictResolution.CANCEL.value == "cancel"

    def test_check_and_save_no_conflict(self, db_session):
        """Test saving when no conflict exists."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at
        changes = {"name": "Updated Name"}

        success, conflict = check_and_save_with_conflict_detection(
            entity=project,
            changes=changes,
            loaded_at=loaded_at,
            username="test_user"
        )

        assert success is True
        assert conflict is None
        assert project.name == "Updated Name"

    def test_check_and_save_with_conflict_returns_conflict(self, db_session):
        """Test that conflict is returned when detected."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at

        # Simulate another user's change
        import time
        time.sleep(0.01)
        project.name = "Changed by other"
        project.updated_at = datetime.utcnow()
        db_session.commit()

        changes = {"name": "My changes"}

        success, conflict = check_and_save_with_conflict_detection(
            entity=project,
            changes=changes,
            loaded_at=loaded_at,
            username="test_user"
        )

        assert success is False
        assert conflict is not None
        assert conflict.has_conflict is True

    def test_check_and_save_with_overwrite_resolution(self, db_session):
        """Test overwrite resolution saves despite conflict."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at

        # Simulate another user's change
        import time
        time.sleep(0.01)
        project.name = "Changed by other"
        project.updated_at = datetime.utcnow()
        db_session.commit()

        changes = {"name": "My changes"}

        success, conflict = check_and_save_with_conflict_detection(
            entity=project,
            changes=changes,
            loaded_at=loaded_at,
            username="test_user",
            resolution=ConflictResolution.OVERWRITE
        )

        assert success is True
        assert conflict is None
        assert project.name == "My changes"

    def test_check_and_save_with_cancel_resolution(self, db_session):
        """Test cancel resolution doesn't save."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        loaded_at = project.updated_at

        # Simulate another user's change
        import time
        time.sleep(0.01)
        original_other_name = "Changed by other"
        project.name = original_other_name
        project.updated_at = datetime.utcnow()
        db_session.commit()

        changes = {"name": "My changes"}

        success, conflict = check_and_save_with_conflict_detection(
            entity=project,
            changes=changes,
            loaded_at=loaded_at,
            username="test_user",
            resolution=ConflictResolution.CANCEL
        )

        assert success is False
        assert conflict is not None
        # Refresh and check name wasn't changed
        db_session.refresh(project)
        assert project.name == original_other_name
