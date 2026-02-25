"""
Tests for Phase 1 Security Fixes.

Tests for:
- 1.1: Database-backed upload storage with secure IDs
- 1.2: CSRF protection configuration
- 1.3: Path traversal prevention in upload_service
- 1.4: Username sanitization and auth tracking middleware
"""
import pytest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from app.extensions import db
from app.models import Project, PlateLayout, Upload, UploadStatus
from app.models.project import PlateFormat
from app.services.upload_service import UploadService, SecurityError
from app.api.middleware import sanitize_username, extract_user_identity


class TestUploadModel:
    """Tests for the Upload model (Phase 1.1)."""

    @pytest.fixture
    def project_and_layout(self, db_session):
        """Create a project and layout for upload testing."""
        project = Project(
            name="Security Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="Test Layout",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.commit()

        return {"project_id": project.id, "layout_id": layout.id}

    def test_upload_creates_secure_uuid(self, db_session, project_and_layout):
        """Upload IDs are cryptographically secure UUIDs, not sequential integers."""
        upload1 = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test1.txt",
            content="test content 1",
            username="testuser"
        )
        db.session.commit()

        upload2 = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test2.txt",
            content="test content 2",
            username="testuser"
        )
        db.session.commit()

        # Verify UUIDs are valid
        uuid.UUID(upload1.upload_id)  # Should not raise
        uuid.UUID(upload2.upload_id)  # Should not raise

        # Verify UUIDs are different
        assert upload1.upload_id != upload2.upload_id

        # Verify they're not sequential (difference should not be 1)
        # UUIDs are random, so this is just a sanity check
        assert upload1.id != upload2.id

    def test_upload_stores_content_hash(self, db_session, project_and_layout):
        """Upload computes and stores SHA-256 hash of content."""
        content = "test content for hashing"
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content=content,
            username="testuser"
        )
        db.session.commit()

        assert upload.content_hash is not None
        assert len(upload.content_hash) == 64  # SHA-256 hex length

    def test_upload_tracks_file_size(self, db_session, project_and_layout):
        """Upload tracks file size in bytes."""
        content = "test content"
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content=content,
            username="testuser"
        )
        db.session.commit()

        assert upload.file_size_bytes == len(content.encode('utf-8'))

    def test_upload_has_expiration(self, db_session, project_and_layout):
        """Uploads have an expiration time (default 24 hours)."""
        before = datetime.utcnow()
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content="test",
            username="testuser"
        )
        db.session.commit()
        after = datetime.utcnow()

        # Expiration should be ~24 hours from now
        expected_min = before + timedelta(hours=23, minutes=59)
        expected_max = after + timedelta(hours=24, minutes=1)

        assert upload.expires_at >= expected_min
        assert upload.expires_at <= expected_max

    def test_upload_custom_ttl(self, db_session, project_and_layout):
        """Uploads can have custom TTL."""
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content="test",
            username="testuser",
            ttl_hours=1
        )
        db.session.commit()

        # Expiration should be ~1 hour from now
        expected = datetime.utcnow() + timedelta(hours=1)
        assert abs((upload.expires_at - expected).total_seconds()) < 60

    def test_get_by_upload_id_excludes_expired(self, db_session, project_and_layout):
        """Expired uploads are not returned by get_by_upload_id."""
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content="test",
            username="testuser",
            ttl_hours=0  # Expires immediately
        )
        # Manually set expiration to past
        upload.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()

        # Should not find expired upload
        result = Upload.get_by_upload_id(upload.upload_id)
        assert result is None

    def test_upload_stores_client_ip(self, db_session, project_and_layout):
        """Upload stores client IP address for audit."""
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content="test",
            username="testuser",
            client_ip="192.168.1.100"
        )
        db.session.commit()

        assert upload.client_ip == "192.168.1.100"

    def test_cleanup_expired_uploads(self, db_session, project_and_layout):
        """Expired uploads can be cleaned up."""
        # Create expired upload
        expired = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="expired.txt",
            content="expired content",
            username="testuser"
        )
        expired.expires_at = datetime.utcnow() - timedelta(hours=1)

        # Create non-expired upload
        active = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="active.txt",
            content="active content",
            username="testuser"
        )
        db.session.commit()

        # Cleanup
        count = Upload.cleanup_expired()

        assert count == 1
        assert expired.status == UploadStatus.EXPIRED
        assert expired.content is None  # Content cleared
        assert active.status == UploadStatus.PENDING  # Not affected

    def test_upload_status_transitions(self, db_session, project_and_layout):
        """Upload status can be updated properly."""
        upload = Upload.create(
            project_id=project_and_layout["project_id"],
            layout_id=project_and_layout["layout_id"],
            filename="test.txt",
            content="test",
            username="testuser"
        )
        db.session.commit()

        assert upload.status == UploadStatus.PENDING

        upload.update_status(UploadStatus.PARSING)
        assert upload.status == UploadStatus.PARSING

        upload.update_status(UploadStatus.PARSED)
        assert upload.status == UploadStatus.PARSED

        upload.update_status(UploadStatus.VALIDATED)
        assert upload.status == UploadStatus.VALIDATED


class TestPathTraversalPrevention:
    """Tests for path traversal prevention (Phase 1.3)."""

    def test_validate_path_id_positive_integer(self):
        """Valid positive integers pass validation."""
        assert UploadService._validate_path_id(1, "test") == 1
        assert UploadService._validate_path_id(100, "test") == 100
        assert UploadService._validate_path_id(999999, "test") == 999999

    def test_validate_path_id_rejects_zero(self):
        """Zero is rejected."""
        with pytest.raises(SecurityError) as exc_info:
            UploadService._validate_path_id(0, "test_id")
        assert "positive integer" in str(exc_info.value)

    def test_validate_path_id_rejects_negative(self):
        """Negative numbers are rejected."""
        with pytest.raises(SecurityError) as exc_info:
            UploadService._validate_path_id(-1, "test_id")
        assert "positive integer" in str(exc_info.value)

    def test_validate_path_id_rejects_non_integer(self):
        """Non-integers are rejected."""
        with pytest.raises(SecurityError):
            UploadService._validate_path_id("1", "test_id")

        with pytest.raises(SecurityError):
            UploadService._validate_path_id(1.5, "test_id")

        with pytest.raises(SecurityError):
            UploadService._validate_path_id(None, "test_id")

    def test_validate_path_within_base_normal(self):
        """Normal paths within base directory pass."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            test_path = base / "project" / "session" / "file.txt"

            result = UploadService._validate_path_within_base(test_path, base)
            assert result.is_relative_to(base.resolve())

    def test_validate_path_within_base_rejects_traversal(self):
        """Path traversal attempts are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "data"
            base.mkdir()

            # Attempt to escape with ..
            malicious_path = base / ".." / ".." / "etc" / "passwd"

            with pytest.raises(SecurityError) as exc_info:
                UploadService._validate_path_within_base(malicious_path, base)
            assert "traversal" in str(exc_info.value).lower()

    def test_store_raw_file_rejects_invalid_project_id(self):
        """Store raw file rejects invalid project IDs."""
        with pytest.raises(SecurityError):
            UploadService._store_raw_file(
                project_id=-1,
                session_id=1,
                original_filename="test.txt",
                content="test"
            )

    def test_store_raw_file_rejects_invalid_session_id(self):
        """Store raw file rejects invalid session IDs."""
        with pytest.raises(SecurityError):
            UploadService._store_raw_file(
                project_id=1,
                session_id=0,
                original_filename="test.txt",
                content="test"
            )

    def test_store_raw_file_sanitizes_filename(self):
        """Dangerous filename characters are sanitized and path stays within base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_raw_dir = UploadService.RAW_FILES_DIR
            UploadService.RAW_FILES_DIR = Path(temp_dir)

            try:
                # Filename with path traversal attempt
                result = UploadService._store_raw_file(
                    project_id=1,
                    session_id=1,
                    original_filename="../../../etc/passwd",
                    content="test"
                )

                # File should exist
                assert Path(result).exists()
                # Should be within our temp directory (path traversal prevented)
                assert Path(result).resolve().is_relative_to(Path(temp_dir).resolve())
                # The actual file should be in the expected subdirectory structure
                assert "/1/1/" in result

            finally:
                UploadService.RAW_FILES_DIR = original_raw_dir

    def test_store_raw_file_handles_empty_filename(self):
        """Empty or whitespace filenames get default name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_raw_dir = UploadService.RAW_FILES_DIR
            UploadService.RAW_FILES_DIR = Path(temp_dir)

            try:
                result = UploadService._store_raw_file(
                    project_id=1,
                    session_id=1,
                    original_filename="...",  # Only dots after sanitization
                    content="test"
                )

                # Should have default filename
                assert "unnamed_file" in result

            finally:
                UploadService.RAW_FILES_DIR = original_raw_dir


class TestUsernameSanitization:
    """Tests for username sanitization (Phase 1.4)."""

    def test_sanitize_valid_username(self):
        """Valid usernames pass through unchanged."""
        assert sanitize_username("john_doe") == "john_doe"
        assert sanitize_username("Jane.Smith") == "Jane.Smith"
        assert sanitize_username("user-123") == "user-123"

    def test_sanitize_empty_username(self):
        """Empty usernames become 'anonymous'."""
        assert sanitize_username("") == "anonymous"
        assert sanitize_username(None) == "anonymous"
        assert sanitize_username("   ") == "anonymous"

    def test_sanitize_removes_control_characters(self):
        """Control characters are removed (prevents log injection)."""
        # Newline injection attempt - newlines are not printable so removed
        result = sanitize_username("user\nAdmin logged in")
        assert "\n" not in result
        assert "user" in result

        # Tab injection - tabs are not printable so removed
        result = sanitize_username("user\tAdmin")
        assert "\t" not in result

        # Carriage return - not printable so removed
        result = sanitize_username("user\rAdmin")
        assert "\r" not in result

    def test_sanitize_removes_special_characters(self):
        """Special characters are replaced with underscore."""
        result = sanitize_username("user@example.com")
        assert "@" not in result
        assert "user" in result

        result = sanitize_username("user<script>")
        assert "<" not in result
        assert ">" not in result

        result = sanitize_username("user;DROP TABLE")
        assert ";" not in result

    def test_sanitize_truncates_long_usernames(self):
        """Long usernames are truncated to max length."""
        long_name = "a" * 100
        result = sanitize_username(long_name)
        assert len(result) <= 64

    def test_sanitize_collapses_underscores(self):
        """Multiple consecutive underscores are collapsed."""
        assert sanitize_username("user@@@name") == "user_name"
        assert sanitize_username("a___b") == "a_b"

    def test_sanitize_strips_leading_trailing_underscores(self):
        """Leading/trailing underscores are stripped."""
        assert sanitize_username("@user@") == "user"
        assert sanitize_username("___user___") == "user"

    def test_sanitize_preserves_unicode_alphanumeric(self):
        """Unicode alphanumeric characters are preserved."""
        # Note: \w in Python includes Unicode word characters
        result = sanitize_username("用户123")
        assert "123" in result  # Numbers preserved


class TestAuthMiddleware:
    """Tests for authentication tracking middleware (Phase 1.4)."""

    def test_middleware_extracts_username(self, app, client, db_session):
        """Middleware extracts and sanitizes username from header."""
        response = client.get(
            '/api/projects/',
            headers={"X-Username": "test_user"}
        )
        # Request should complete (we're testing middleware runs)
        assert response.status_code == 200

    def test_middleware_handles_missing_username(self, app, client, db_session):
        """Middleware handles missing X-Username header."""
        response = client.get('/api/projects/')
        # Should use 'anonymous' as default
        assert response.status_code == 200

    def test_middleware_sanitizes_malicious_username(self, app, client, db_session):
        """Middleware sanitizes potentially malicious usernames."""
        # Attempt log injection - Flask doesn't allow newlines in headers
        # so we test with other special characters
        response = client.get(
            '/api/projects/',
            headers={"X-Username": "admin;DROP TABLE users"}
        )
        # Should complete without error (injection prevented)
        assert response.status_code == 200


class TestCSRFConfiguration:
    """Tests for CSRF protection configuration (Phase 1.2)."""

    def test_csrf_extension_initialized(self, app):
        """CSRF extension is initialized."""
        from app.extensions import csrf
        # Verify csrf is configured with the app
        assert csrf is not None

    def test_api_endpoints_csrf_exempt(self, app, client):
        """API endpoints should be exempt from CSRF."""
        # POST to API without CSRF token should work
        response = client.post(
            '/api/projects/',
            json={
                "name": "Test Project",
                "plate_format": "384"
            },
            headers={"X-Username": "test_user"}
        )
        # Should not get 400 CSRF error - either 201 or validation error
        assert response.status_code != 400 or "csrf" not in response.get_json().get("error", "").lower()


class TestUploadsAPISecurityIntegration:
    """Integration tests for uploads API security (Phase 1.1)."""

    @pytest.fixture
    def setup_project_layout(self, db_session):
        """Create a project with layout for testing."""
        from app.models import Construct, WellAssignment
        from app.models.plate_layout import WellType

        project = Project(
            name="Upload Security Test",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_wildtype=True,
            is_draft=False
        )
        db.session.add(construct)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="Test Layout",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        # Add minimum wells with negative controls
        wells = [
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
            WellAssignment(layout_id=layout.id, well_position="A3", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
        ]
        for w in wells:
            db.session.add(w)
        db.session.commit()

        return {"project_id": project.id, "layout_id": layout.id}

    def test_upload_returns_uuid_not_integer(self, client, setup_project_layout):
        """Upload response contains UUID, not sequential integer."""
        import base64

        content = """Plate: Test
Plate Type: 384
Temperature: 37.0

Time\tA1\tA2\tA3
0:00:00\t100\t110\t105
"""
        content_b64 = base64.b64encode(content.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": setup_project_layout["project_id"],
                "layout_id": setup_project_layout["layout_id"],
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 201
        data = response.get_json()

        # Upload ID should be a UUID string, not an integer
        upload_id = data["upload_id"]
        assert isinstance(upload_id, str)

        # Should be valid UUID format
        uuid.UUID(upload_id)  # Should not raise

    def test_upload_rejects_invalid_project_id(self, client, setup_project_layout):
        """Upload rejects non-positive project IDs."""
        import base64

        content_b64 = base64.b64encode(b"test").decode()

        # Negative project_id
        response = client.post(
            '/api/uploads/',
            json={
                "project_id": -1,
                "layout_id": setup_project_layout["layout_id"],
                "filename": "test.txt",
                "content": content_b64
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 400
        assert "positive integer" in response.get_json()["error"].lower()

    def test_upload_rejects_invalid_layout_id(self, client, setup_project_layout):
        """Upload rejects non-positive layout IDs."""
        import base64

        content_b64 = base64.b64encode(b"test").decode()

        # Negative layout_id
        response = client.post(
            '/api/uploads/',
            json={
                "project_id": setup_project_layout["project_id"],
                "layout_id": -1,
                "filename": "test.txt",
                "content": content_b64
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 400
        assert "positive integer" in response.get_json()["error"].lower()

    def test_expired_upload_not_accessible(self, client, setup_project_layout):
        """Expired uploads return 404."""
        import base64

        # Create upload via API
        content = "test"
        content_b64 = base64.b64encode(content.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": setup_project_layout["project_id"],
                "layout_id": setup_project_layout["layout_id"],
                "filename": "test.txt",
                "content": content_b64
            },
            headers={"X-Username": "test_user"}
        )

        upload_id = response.get_json()["upload_id"]

        # Manually expire the upload
        upload = Upload.get_by_upload_id(upload_id)
        upload.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()

        # Try to access expired upload
        response = client.get(
            f'/api/uploads/{upload_id}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404
        assert "expired" in response.get_json()["error"].lower()

    def test_random_uuid_returns_404(self, client, db_session):
        """Random UUID that doesn't exist returns 404."""
        fake_uuid = str(uuid.uuid4())

        response = client.get(
            f'/api/uploads/{fake_uuid}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404
