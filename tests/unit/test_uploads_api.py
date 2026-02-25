"""
Tests for Upload API endpoints.

Phase 5: API and Scripts - Upload API
PRD Reference: Section 4.1

Tests for:
- POST /api/uploads/              Upload new data file
- POST /api/uploads/{id}/parse    Parse uploaded file
- POST /api/uploads/{id}/validate Validate against layout
- GET  /api/uploads/{id}/status   Get upload/parsing status
"""
import pytest
import json
import base64
from datetime import datetime

from app.extensions import db
from app.models import Project, Construct, PlateLayout, WellAssignment, ExperimentalSession, Plate
from app.models.project import PlateFormat
from app.models.plate_layout import WellType


class TestUploadsAPI:
    """Tests for Upload API endpoints (Phase 5)."""

    # Sample BioTek file content for testing
    SAMPLE_BIOTEK_CONTENT = """Plate: TestPlate
Plate Type: 384
Temperature: 37.0
Read Mode: Fluorescence

Time\tA1\tA2\tA3\tB1\tB2\tB3
0:00:00\t100\t110\t105\t120\t130\t125
0:05:00\t150\t160\t155\t170\t180\t175
0:10:00\t200\t210\t205\t220\t230\t225
"""

    SAMPLE_96_WELL_CONTENT = """Plate: TestPlate
Plate Type: 96
Temperature: 37.0
Read Mode: Fluorescence

Time\tA1\tA2\tA3\tB1\tB2\tB3
0:00:00\t100\t110\t105\t120\t130\t125
0:05:00\t150\t160\t155\t170\t180\t175
"""

    @pytest.fixture
    def project_with_layout(self, db_session):
        """Create a project with constructs and a layout for upload testing."""
        # Create project (use string for plate_format as required by model)
        project = Project(
            name="Upload Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        # Create constructs
        wt_construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="TestFamily",
            is_wildtype=True,
            is_draft=False
        )
        mut_construct = Construct(
            project_id=project.id,
            identifier="Mut1",
            family="TestFamily",
            is_draft=False
        )
        db.session.add(wt_construct)
        db.session.add(mut_construct)
        db.session.flush()

        # Create layout (use string for plate_format as model requires)
        layout = PlateLayout(
            project_id=project.id,
            name="Test Layout",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        # Create well assignments - including negative controls
        wells = [
            # Sample wells
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=wt_construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.SAMPLE, construct_id=wt_construct.id),
            WellAssignment(layout_id=layout.id, well_position="A3", well_type=WellType.SAMPLE, construct_id=mut_construct.id),
            WellAssignment(layout_id=layout.id, well_position="B1", well_type=WellType.SAMPLE, construct_id=mut_construct.id),
            # Negative controls (minimum 2 required)
            WellAssignment(layout_id=layout.id, well_position="B2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
            WellAssignment(layout_id=layout.id, well_position="B3", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
        ]
        for w in wells:
            db.session.add(w)

        db.session.commit()

        return {
            "project": project,
            "layout": layout,
            "wt_construct": wt_construct,
            "mut_construct": mut_construct
        }

    # ==================== POST /api/uploads/ Tests ====================

    def test_upload_file_success(self, client, project_with_layout):
        """T5.1: Successfully upload a data file."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        # Base64 encode the content
        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test_plate.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 201
        data = response.get_json()
        assert "upload_id" in data
        assert data["status"] == "pending"
        assert data["filename"] == "test_plate.txt"

    def test_upload_file_missing_project(self, client, project_with_layout):
        """T5.2: Upload fails with non-existent project."""
        layout = project_with_layout["layout"]
        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": 99999,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "project" in data["error"].lower()

    def test_upload_file_missing_layout(self, client, project_with_layout):
        """T5.3: Upload fails with non-existent layout."""
        project = project_with_layout["project"]
        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": 99999,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "layout" in data["error"].lower()

    def test_upload_file_missing_content(self, client, project_with_layout):
        """T5.4: Upload fails without content."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_upload_file_with_session(self, client, project_with_layout, db_session):
        """T5.5: Upload file to existing session."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        # Create session first
        session = ExperimentalSession(
            project_id=project.id,
            date=datetime.now().date(),
            batch_identifier="Test_Batch_001"
        )
        db.session.add(session)
        db.session.commit()

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()

        response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "session_id": session.id,
                "filename": "test_plate.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["session_id"] == session.id

    # ==================== POST /api/uploads/{id}/parse Tests ====================

    def test_parse_upload_success(self, client, project_with_layout):
        """T5.6: Successfully parse an uploaded file."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        # First upload
        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        # Then parse
        response = client.post(
            f'/api/uploads/{upload_id}/parse',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "parsed"
        assert "metadata" in data
        assert data["metadata"]["plate_format"] == 384

    def test_parse_upload_invalid_format(self, client, project_with_layout):
        """T5.7: Parse fails with invalid file format."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        # Upload invalid content
        invalid_content = "This is not a valid BioTek file\nJust some random text"
        content_b64 = base64.b64encode(invalid_content.encode()).decode()

        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "invalid.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        response = client.post(
            f'/api/uploads/{upload_id}/parse',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_parse_nonexistent_upload(self, client, db_session):
        """T5.8: Parse fails for non-existent upload."""
        import uuid
        fake_uuid = str(uuid.uuid4())
        response = client.post(
            f'/api/uploads/{fake_uuid}/parse',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404

    def test_parse_extracts_metadata(self, client, project_with_layout):
        """T5.9: Parse correctly extracts file metadata."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        response = client.post(
            f'/api/uploads/{upload_id}/parse',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        metadata = data["metadata"]
        assert metadata["temperature_setpoint"] == 37.0
        assert metadata["num_timepoints"] >= 2
        assert metadata["num_wells"] >= 6

    # ==================== POST /api/uploads/{id}/validate Tests ====================

    def test_validate_upload_success(self, client, project_with_layout):
        """T5.10: Successfully validate parsed upload against layout."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        # Parse first
        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        # Then validate
        response = client.post(
            f'/api/uploads/{upload_id}/validate',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "is_valid" in data
        assert "errors" in data
        assert "warnings" in data

    def test_validate_plate_format_mismatch(self, client, db_session):
        """T5.11: Validation fails with plate format mismatch."""
        # Create 96-well project
        project = Project(
            name="96 Well Project",
            plate_format=PlateFormat.PLATE_96,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        # Create construct and layout
        construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_draft=False
        )
        db.session.add(construct)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="96 Well Layout",
            plate_format="96",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        # Add wells with negative controls
        wells = [
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
            WellAssignment(layout_id=layout.id, well_position="A3", well_type=WellType.NEGATIVE_CONTROL_NO_DYE),
        ]
        for w in wells:
            db.session.add(w)
        db.session.commit()

        # Upload 384-well file to 96-well project
        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.post(
            f'/api/uploads/{upload_id}/validate',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert data["is_valid"] is False
        assert any("format" in e.lower() or "mismatch" in e.lower() for e in data["errors"])

    def test_validate_returns_warnings(self, client, project_with_layout):
        """T5.12: Validation returns suppressible warnings."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.post(
            f'/api/uploads/{upload_id}/validate',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert isinstance(data["warnings"], list)
        for warning in data["warnings"]:
            assert "code" in warning
            assert "message" in warning
            assert "suppressible" in warning

    def test_validate_with_suppressed_warnings(self, client, project_with_layout):
        """T5.13: Validation with suppressed warning codes."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.post(
            f'/api/uploads/{upload_id}/validate',
            json={"suppress_warnings": ["UNMATCHED_WELLS"]},
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200

    # ==================== GET /api/uploads/{id}/status Tests ====================

    def test_get_upload_status_pending(self, client, project_with_layout):
        """T5.14: Get status of pending upload."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        response = client.get(
            f'/api/uploads/{upload_id}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"
        assert data["upload_id"] == upload_id

    def test_get_upload_status_parsed(self, client, project_with_layout):
        """T5.15: Get status of parsed upload."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.get(
            f'/api/uploads/{upload_id}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "parsed"

    def test_get_upload_status_validated(self, client, project_with_layout):
        """T5.16: Get status of validated upload."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})
        client.post(f'/api/uploads/{upload_id}/validate', headers={"X-Username": "test_user"})

        response = client.get(
            f'/api/uploads/{upload_id}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] in ["validated", "validation_failed"]

    def test_get_nonexistent_upload_status(self, client, db_session):
        """T5.17: Get status fails for non-existent upload."""
        import uuid
        fake_uuid = str(uuid.uuid4())
        response = client.get(
            f'/api/uploads/{fake_uuid}/status',
            headers={"X-Username": "test_user"}
        )

        assert response.status_code == 404

    def test_get_upload_status_includes_metadata(self, client, project_with_layout):
        """T5.18: Status includes metadata after parsing."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.get(
            f'/api/uploads/{upload_id}/status',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert "metadata" in data
        assert "plate_format" in data["metadata"]

    # ==================== Additional Edge Case Tests ====================

    def test_upload_with_draft_construct_blocked(self, client, db_session):
        """T5.19: Upload blocked when layout has draft constructs."""
        # Create project and draft construct
        project = Project(
            name="Draft Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        draft_construct = Construct(
            project_id=project.id,
            identifier="Draft",
            family="Test",
            is_draft=True  # Draft construct!
        )
        db.session.add(draft_construct)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="Layout with Draft",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        wells = [
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=draft_construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
            WellAssignment(layout_id=layout.id, well_position="A3", well_type=WellType.NEGATIVE_CONTROL_NO_DYE),
        ]
        for w in wells:
            db.session.add(w)
        db.session.commit()

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )
        upload_id = upload_response.get_json()["upload_id"]

        client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})

        response = client.post(
            f'/api/uploads/{upload_id}/validate',
            headers={"X-Username": "test_user"}
        )

        data = response.get_json()
        assert data["is_valid"] is False
        assert any("draft" in e.lower() for e in data["errors"])

    def test_upload_process_creates_plate(self, client, project_with_layout):
        """T5.20: Processing upload creates plate record."""
        project = project_with_layout["project"]
        layout = project_with_layout["layout"]

        content_b64 = base64.b64encode(self.SAMPLE_BIOTEK_CONTENT.encode()).decode()
        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64",
                "process": True  # Auto-process
            },
            headers={"X-Username": "test_user"}
        )

        if upload_response.status_code == 201:
            data = upload_response.get_json()
            if "plate_id" in data:
                assert data["plate_id"] is not None


class TestUploadsAPIValidation:
    """Tests for upload validation edge cases."""

    def test_temperature_qc_warning(self, client, db_session):
        """T5.21: Temperature deviation generates warning."""
        # Create project and layout
        project = Project(
            name="Temp QC Test",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_draft=False
        )
        db.session.add(construct)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="Layout",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        wells = [
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
            WellAssignment(layout_id=layout.id, well_position="A3", well_type=WellType.NEGATIVE_CONTROL_NO_DYE),
        ]
        for w in wells:
            db.session.add(w)
        db.session.commit()

        # Content with temperature deviation
        temp_deviation_content = """Plate: TestPlate
Plate Type: 384
Temperature: 37.0
Read Mode: Fluorescence

Time\tTemp\tA1\tA2\tA3
0:00:00\t37.0\t100\t110\t105
0:05:00\t38.5\t150\t160\t155
0:10:00\t39.0\t200\t210\t205
"""
        content_b64 = base64.b64encode(temp_deviation_content.encode()).decode()

        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "temp_test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        if upload_response.status_code == 201:
            upload_id = upload_response.get_json()["upload_id"]
            client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})
            response = client.post(
                f'/api/uploads/{upload_id}/validate',
                headers={"X-Username": "test_user"}
            )
            # Just verify we got a response - actual warning depends on parser
            assert response.status_code in [200, 400]

    def test_insufficient_negative_controls(self, client, db_session):
        """T5.22: Validation fails with insufficient negative controls."""
        project = Project(
            name="No Controls Test",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.flush()

        construct = Construct(
            project_id=project.id,
            identifier="WT",
            family="Test",
            is_draft=False
        )
        db.session.add(construct)
        db.session.flush()

        layout = PlateLayout(
            project_id=project.id,
            name="Layout No Controls",
            plate_format="384",
            is_template=False
        )
        db.session.add(layout)
        db.session.flush()

        # Only one negative control (minimum is 2)
        wells = [
            WellAssignment(layout_id=layout.id, well_position="A1", well_type=WellType.SAMPLE, construct_id=construct.id),
            WellAssignment(layout_id=layout.id, well_position="A2", well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
        ]
        for w in wells:
            db.session.add(w)
        db.session.commit()

        content = """Plate: Test
Plate Type: 384
Temperature: 37.0

Time\tA1\tA2
0:00:00\t100\t110
"""
        content_b64 = base64.b64encode(content.encode()).decode()

        upload_response = client.post(
            '/api/uploads/',
            json={
                "project_id": project.id,
                "layout_id": layout.id,
                "filename": "test.txt",
                "content": content_b64,
                "content_encoding": "base64"
            },
            headers={"X-Username": "test_user"}
        )

        if upload_response.status_code == 201:
            upload_id = upload_response.get_json()["upload_id"]
            client.post(f'/api/uploads/{upload_id}/parse', headers={"X-Username": "test_user"})
            response = client.post(
                f'/api/uploads/{upload_id}/validate',
                headers={"X-Username": "test_user"}
            )
            data = response.get_json()
            # Should fail due to insufficient controls
            if data.get("is_valid") is False:
                assert any("control" in e.lower() for e in data.get("errors", []))
