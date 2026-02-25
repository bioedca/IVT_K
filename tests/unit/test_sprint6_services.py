"""
Tests for Sprint 6 services.

Tests:
- Audit service (logging, queries, export)
- Backup manager
- Project archiver
- Audit log layout
"""
import pytest
import json
import tempfile
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

from app.services.audit_service import (
    AuditService,
    AuditQueryFilter,
)


# ========== Audit Service Tests ==========

class TestAuditQueryFilter:
    """Tests for AuditQueryFilter dataclass."""

    def test_default_values(self):
        """Test default filter values."""
        filters = AuditQueryFilter()

        assert filters.project_id is None
        assert filters.username is None
        assert filters.action_type is None
        assert filters.limit == 100
        assert filters.offset == 0

    def test_custom_values(self):
        """Test custom filter values."""
        filters = AuditQueryFilter(
            project_id=1,
            username="test_user",
            action_type="create",
            limit=50,
        )

        assert filters.project_id == 1
        assert filters.username == "test_user"
        assert filters.action_type == "create"
        assert filters.limit == 50


class TestAuditServiceConstants:
    """Tests for AuditService constants."""

    def test_action_types(self):
        """Test action type constants are defined."""
        assert AuditService.ACTION_CREATE == "create"
        assert AuditService.ACTION_UPDATE == "update"
        assert AuditService.ACTION_DELETE == "delete"
        assert AuditService.ACTION_UPLOAD == "upload"
        assert AuditService.ACTION_EXPORT == "export"
        assert AuditService.ACTION_ANALYZE == "analyze"

    def test_entity_types(self):
        """Test entity type constants are defined."""
        assert AuditService.ENTITY_PROJECT == "project"
        assert AuditService.ENTITY_CONSTRUCT == "construct"
        assert AuditService.ENTITY_WELL == "well"
        assert AuditService.ENTITY_ANALYSIS == "analysis"


class TestAuditServiceFieldDiff:
    """Tests for field-level diff computation."""

    def test_compute_field_diff_no_changes(self):
        """Test diff with identical states."""
        old = {"name": "Test", "value": 100}
        new = {"name": "Test", "value": 100}

        changes = AuditService.compute_field_diff(old, new)

        assert len(changes) == 0

    def test_compute_field_diff_single_change(self):
        """Test diff with single field change."""
        old = {"name": "Test", "value": 100}
        new = {"name": "Test", "value": 200}

        changes = AuditService.compute_field_diff(old, new)

        assert len(changes) == 1
        assert changes[0]["field"] == "value"
        assert changes[0]["old"] == 100
        assert changes[0]["new"] == 200

    def test_compute_field_diff_multiple_changes(self):
        """Test diff with multiple field changes."""
        old = {"name": "Old Name", "value": 100, "status": "active"}
        new = {"name": "New Name", "value": 200, "status": "active"}

        changes = AuditService.compute_field_diff(old, new)

        assert len(changes) == 2
        field_names = [c["field"] for c in changes]
        assert "name" in field_names
        assert "value" in field_names

    def test_compute_field_diff_new_field(self):
        """Test diff with new field added."""
        old = {"name": "Test"}
        new = {"name": "Test", "value": 100}

        changes = AuditService.compute_field_diff(old, new)

        assert len(changes) == 1
        assert changes[0]["field"] == "value"
        assert changes[0]["old"] is None
        assert changes[0]["new"] == 100

    def test_compute_field_diff_removed_field(self):
        """Test diff with field removed."""
        old = {"name": "Test", "value": 100}
        new = {"name": "Test"}

        changes = AuditService.compute_field_diff(old, new)

        assert len(changes) == 1
        assert changes[0]["field"] == "value"
        assert changes[0]["old"] == 100
        assert changes[0]["new"] is None

    def test_compute_field_diff_specific_fields(self):
        """Test diff with specific fields specified."""
        old = {"name": "Old", "value": 100, "status": "old_status"}
        new = {"name": "New", "value": 200, "status": "new_status"}

        changes = AuditService.compute_field_diff(old, new, fields=["name", "value"])

        assert len(changes) == 2
        field_names = [c["field"] for c in changes]
        assert "name" in field_names
        assert "value" in field_names
        assert "status" not in field_names

    def test_compute_field_diff_empty_string_normalization(self):
        """Test that empty strings are normalized to None."""
        old = {"name": ""}
        new = {"name": None}

        changes = AuditService.compute_field_diff(old, new)

        # Both normalize to None, so no change
        assert len(changes) == 0


class TestAuditServiceExport:
    """Tests for audit export functionality."""

    def test_export_to_json_empty(self):
        """Test JSON export with empty logs."""
        json_str = AuditService.export_to_json([])

        data = json.loads(json_str)
        assert data["total_entries"] == 0
        assert data["entries"] == []
        assert "export_date" in data

    def test_export_to_json_with_logs(self):
        """Test JSON export with mock logs."""
        mock_log = Mock()
        mock_log.id = 1
        mock_log.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_log.username = "test_user"
        mock_log.action_type = "create"
        mock_log.entity_type = "project"
        mock_log.entity_id = 42
        mock_log.project_id = 1
        mock_log.changes = [{"field": "name", "old": None, "new": "Test"}]
        mock_log.details = {"key": "value"}

        json_str = AuditService.export_to_json([mock_log])

        data = json.loads(json_str)
        assert data["total_entries"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["username"] == "test_user"
        assert data["entries"][0]["action_type"] == "create"

    def test_export_to_json_without_details(self):
        """Test JSON export without details."""
        mock_log = Mock()
        mock_log.id = 1
        mock_log.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_log.username = "test_user"
        mock_log.action_type = "update"
        mock_log.entity_type = "construct"
        mock_log.entity_id = 5
        mock_log.project_id = 1
        mock_log.changes = None
        mock_log.details = {"secret": "data"}

        json_str = AuditService.export_to_json([mock_log], include_details=False)

        data = json.loads(json_str)
        assert "details" not in data["entries"][0]

    def test_export_to_markdown_empty(self):
        """Test Markdown export with empty logs."""
        md_str = AuditService.export_to_markdown([])

        assert "# Audit Log" in md_str
        assert "Total entries: 0" in md_str

    def test_export_to_markdown_with_logs(self):
        """Test Markdown export with mock logs."""
        mock_log = Mock()
        mock_log.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_log.username = "test_user"
        mock_log.action_type = "update"
        mock_log.entity_type = "project"
        mock_log.entity_id = 1
        mock_log.project_id = 1
        mock_log.changes = [
            {"field": "name", "old": "Old", "new": "New"},
        ]
        mock_log.details = None

        md_str = AuditService.export_to_markdown([mock_log])

        assert "# Audit Log" in md_str
        assert "UPDATE" in md_str
        assert "test_user" in md_str
        assert "| Field | Old Value | New Value |" in md_str
        assert "name" in md_str

    def test_export_to_markdown_custom_title(self):
        """Test Markdown export with custom title."""
        md_str = AuditService.export_to_markdown([], title="Project History")

        assert "# Project History" in md_str


# ========== Backup Manager Tests ==========

class TestBackupManager:
    """Tests for backup manager functionality."""

    def test_checkpoint_database_file_not_found(self):
        """Test checkpoint with missing database."""
        # Import here to avoid issues during collection
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts.backup import BackupManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BackupManager(
                base_dir=Path(tmpdir),
                db_path=Path(tmpdir) / "nonexistent.db",
            )

            result = manager.checkpoint_database()
            assert result is False

    def test_create_backup_structure(self):
        """Test backup creates proper archive structure."""
        from scripts.backup import BackupManager

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Create test database (valid SQLite header)
            db_path = base_dir / "ivt_kinetics.db"
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.close()

            # Create test data directory
            data_dir = base_dir / "data" / "1"
            data_dir.mkdir(parents=True)
            (data_dir / "test.json").write_text('{"key": "value"}')

            manager = BackupManager(base_dir=base_dir)
            backup_path, metadata = manager.create_backup()

            assert backup_path is not None
            assert backup_path.exists()
            assert len(metadata["files"]) >= 2

            # Verify archive contents
            with tarfile.open(backup_path, "r:gz") as tar:
                names = tar.getnames()
                assert "ivt_kinetics.db" in names

    def test_list_backups(self):
        """Test listing existing backups."""
        from scripts.backup import BackupManager

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            backup_dir = base_dir / "backups"
            backup_dir.mkdir()

            # Create fake backup files
            for i in range(3):
                (backup_dir / f"backup_2024-01-0{i+1}_00-00-00.tar.gz").write_bytes(b"test")

            manager = BackupManager(base_dir=base_dir)
            backups = manager.list_backups()

            assert len(backups) == 3

    def test_cleanup_old_backups(self):
        """Test cleanup removes old backups."""
        from scripts.backup import BackupManager
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            backup_dir = base_dir / "backups"
            backup_dir.mkdir()

            # Create old backup (modify time to 60 days ago)
            old_backup = backup_dir / "backup_old.tar.gz"
            old_backup.write_bytes(b"old")
            old_time = (datetime.now() - timedelta(days=60)).timestamp()
            os.utime(old_backup, (old_time, old_time))

            # Create recent backup
            new_backup = backup_dir / "backup_new.tar.gz"
            new_backup.write_bytes(b"new")

            manager = BackupManager(base_dir=base_dir, retention_days=30)
            deleted = manager.cleanup_old_backups()

            assert len(deleted) == 1
            assert not old_backup.exists()
            assert new_backup.exists()


# ========== Project Archiver Tests ==========

class TestProjectArchiver:
    """Tests for project archiver functionality."""

    def test_archive_project(self):
        """Test archiving a project."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Create test project data
            project_dir = base_dir / "data" / "1"
            project_dir.mkdir(parents=True)
            (project_dir / "data.json").write_text('{"key": "value"}')
            (project_dir / "results.csv").write_text("a,b,c\n1,2,3")

            archiver = ProjectArchiver(base_dir=base_dir)
            result = archiver.archive_project(
                project_id=1,
                project_name="Test Project",
                username="test_user",
            )

            assert result["success"] is True
            assert not project_dir.exists()  # Original deleted
            assert len(list((base_dir / "archives").glob("*.tar.gz"))) == 1

    def test_archive_project_not_found(self):
        """Test archiving non-existent project."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            archiver = ProjectArchiver(base_dir=Path(tmpdir))
            result = archiver.archive_project(
                project_id=999,
                project_name="Nonexistent",
                username="test_user",
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    def test_restore_project(self):
        """Test restoring an archived project."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Create and archive project
            project_dir = base_dir / "data" / "1"
            project_dir.mkdir(parents=True)
            (project_dir / "data.json").write_text('{"key": "value"}')

            archiver = ProjectArchiver(base_dir=base_dir)
            archiver.archive_project(
                project_id=1,
                project_name="Test",
                username="test_user",
            )

            # Verify archived
            assert not project_dir.exists()

            # Restore
            result = archiver.restore_project(project_id=1, username="test_user")

            assert result["success"] is True
            assert project_dir.exists()
            assert (project_dir / "data.json").exists()

    def test_get_archive_status_active(self):
        """Test status for active (non-archived) project."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            project_dir = base_dir / "data" / "1"
            project_dir.mkdir(parents=True)
            (project_dir / "data.json").write_text('{"key": "value"}')

            archiver = ProjectArchiver(base_dir=base_dir)
            status = archiver.get_archive_status(1)

            assert status["is_archived"] is False
            assert "data_dir" in status

    def test_get_archive_status_archived(self):
        """Test status for archived project."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            project_dir = base_dir / "data" / "1"
            project_dir.mkdir(parents=True)
            (project_dir / "data.json").write_text('{"key": "value"}')

            archiver = ProjectArchiver(base_dir=base_dir)
            archiver.archive_project(
                project_id=1,
                project_name="Test",
                username="test_user",
            )

            status = archiver.get_archive_status(1)

            assert status["is_archived"] is True
            assert "archive_path" in status

    def test_list_archives(self):
        """Test listing archived projects."""
        from scripts.archive_project import ProjectArchiver

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Create and archive multiple projects
            for i in range(3):
                project_dir = base_dir / "data" / str(i + 1)
                project_dir.mkdir(parents=True)
                (project_dir / "data.json").write_text(f'{{"id": {i+1}}}')

            archiver = ProjectArchiver(base_dir=base_dir)
            for i in range(3):
                archiver.archive_project(
                    project_id=i + 1,
                    project_name=f"Project {i+1}",
                    username="test_user",
                )

            archives = archiver.list_archives()

            assert len(archives) == 3


# ========== Audit Log Layout Tests ==========

class TestAuditLogLayout:
    """Tests for audit log layout components."""

    def test_create_audit_log_layout(self):
        """Test audit log layout creation."""
        from app.layouts.audit_log import create_audit_log_layout

        layout = create_audit_log_layout()

        # Should be a Stack component
        assert layout is not None
        assert hasattr(layout, 'children')

    def test_create_audit_log_layout_with_project(self):
        """Test audit log layout with project filter."""
        from app.layouts.audit_log import create_audit_log_layout

        layout = create_audit_log_layout(project_id=1)

        assert layout is not None

    def test_create_audit_entry_card(self):
        """Test audit entry card creation."""
        from app.layouts.audit_log import create_audit_entry_card

        card = create_audit_entry_card(
            log_id=1,
            timestamp=datetime.now(),
            username="test_user",
            action_type="create",
            entity_type="project",
            entity_id=1,
            changes=[{"field": "name", "old": None, "new": "Test"}],
        )

        assert card is not None

    def test_create_audit_entry_card_all_actions(self):
        """Test card creation for different action types."""
        from app.layouts.audit_log import create_audit_entry_card

        actions = ["create", "update", "delete", "upload", "analyze", "export"]

        for action in actions:
            card = create_audit_entry_card(
                log_id=1,
                timestamp=datetime.now(),
                username="user",
                action_type=action,
                entity_type="project",
                entity_id=1,
            )
            assert card is not None

    def test_create_empty_state(self):
        """Test empty state creation."""
        from app.layouts.audit_log import create_empty_state

        empty = create_empty_state()

        assert empty is not None

    def test_relative_time_formatting(self):
        """Test relative time formatting."""
        from app.layouts.audit_log import _get_relative_time

        # Just now
        assert _get_relative_time(datetime.now(timezone.utc)) == "just now"

        # Minutes ago
        assert "minute" in _get_relative_time(datetime.now(timezone.utc) - timedelta(minutes=5))

        # Hours ago
        assert "hour" in _get_relative_time(datetime.now(timezone.utc) - timedelta(hours=3))

        # Days ago
        assert "day" in _get_relative_time(datetime.now(timezone.utc) - timedelta(days=2))

        # Weeks ago
        assert "week" in _get_relative_time(datetime.now(timezone.utc) - timedelta(days=14))


# ========== Integration Tests ==========

class TestAuditServiceIntegration:
    """Integration tests requiring database fixtures."""

    def test_log_action_creates_entry(self, db_session):
        """Test that log_action creates database entry."""
        from app.extensions import db
        from app.models import AuditLog

        # Create test log (don't commit to avoid side effects)
        log = AuditService.log_action(
            username="test_user",
            action_type="create",
            entity_type="project",
            entity_id=1,
            project_id=None,
            commit=False,
        )

        assert log is not None
        assert log.username == "test_user"
        assert log.action_type == "create"

        # Rollback to avoid persisting test data
        db.session.rollback()

    def test_log_entity_create(self, db_session):
        """Test log_entity_create convenience method."""
        from app.extensions import db

        log = AuditService.log_entity_create(
            username="test_user",
            entity_type="construct",
            entity_id=1,
            entity_data={"name": "Test Construct"},
            commit=False,
        )

        assert log.action_type == "create"
        assert log.details["created_data"]["name"] == "Test Construct"

        db.session.rollback()

    def test_log_entity_update_with_diff(self, db_session):
        """Test log_entity_update computes diff."""
        from app.extensions import db

        old_state = {"name": "Old Name", "value": 100}
        new_state = {"name": "New Name", "value": 100}

        log = AuditService.log_entity_update(
            username="test_user",
            entity_type="construct",
            entity_id=1,
            old_state=old_state,
            new_state=new_state,
            commit=False,
        )

        assert log.action_type == "update"
        assert len(log.changes) == 1
        assert log.changes[0]["field"] == "name"

        db.session.rollback()
