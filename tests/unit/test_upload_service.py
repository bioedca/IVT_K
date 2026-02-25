"""
Tests for upload service.

Phase 3.3: Upload workflow with draft construct block
Phase 3.5: Local filesystem storage (hierarchical)
Phase 3.6: Blank subtraction
Phase 3.11: Empty well detection and classification
Phase 3.12: Negative control validation at upload
Phase 3.13: Incomplete plate warning (suppressible)
"""
import pytest
from datetime import date
from textwrap import dedent
from pathlib import Path

from app.extensions import db
from app.models import (
    Project, Construct, PlateLayout, WellAssignment,
    ExperimentalSession, Plate, Well, RawDataPoint
)
from app.models.project import PlateFormat
from app.models.plate_layout import WellType
from app.services import (
    UploadService,
    UploadValidationError,
    UploadProcessingError,
    ProjectService,
    ConstructService,
    PlateLayoutService
)
from app.parsers import ParsedPlateData


@pytest.fixture
def setup_project(db_session):
    """Create a project with constructs and layout."""
    # Create project
    project = ProjectService.create_project(
        name="Upload Test Project",
        username="testuser",
        plate_format=PlateFormat.PLATE_384
    )

    # Create unregulated construct
    unregulated = ConstructService.create_construct(
        project_id=project.id,
        identifier="Unregulated",
        family="Universal",
        username="testuser",
        is_unregulated=True
    )
    ConstructService.publish_construct(unregulated.id, "testuser")

    # Create WT construct
    wt = ConstructService.create_construct(
        project_id=project.id,
        identifier="WT Tbox",
        family="Tbox1",
        username="testuser",
        is_wildtype=True
    )
    ConstructService.publish_construct(wt.id, "testuser")

    # Create sample construct
    sample = ConstructService.create_construct(
        project_id=project.id,
        identifier="Mutant A",
        family="Tbox1",
        username="testuser"
    )
    ConstructService.publish_construct(sample.id, "testuser")

    # Create draft construct (for testing draft blocking)
    draft = ConstructService.create_construct(
        project_id=project.id,
        identifier="Draft Construct",
        family="Tbox1",
        username="testuser"
    )

    # Create plate layout
    layout = PlateLayoutService.create_layout(
        project_id=project.id,
        name="Test Layout",
        username="testuser"
    )

    # Assign wells
    # Negative controls (need at least 2)
    PlateLayoutService.assign_well(
        layout.id, "A1", "testuser",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
    )
    PlateLayoutService.assign_well(
        layout.id, "A2", "testuser",
        well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
    )

    # Blanks
    PlateLayoutService.assign_well(
        layout.id, "A3", "testuser",
        well_type=WellType.BLANK
    )

    # Unregulated
    PlateLayoutService.assign_well(
        layout.id, "B1", "testuser",
        construct_id=unregulated.id,
        well_type=WellType.SAMPLE
    )

    # WT
    PlateLayoutService.assign_well(
        layout.id, "B2", "testuser",
        construct_id=wt.id,
        well_type=WellType.SAMPLE
    )

    # Sample wells
    PlateLayoutService.assign_well(
        layout.id, "C1", "testuser",
        construct_id=sample.id,
        well_type=WellType.SAMPLE
    )
    PlateLayoutService.assign_well(
        layout.id, "C2", "testuser",
        construct_id=sample.id,
        well_type=WellType.SAMPLE
    )

    db.session.commit()

    return {
        "project_id": project.id,
        "layout_id": layout.id,
        "unregulated_id": unregulated.id,
        "wt_id": wt.id,
        "sample_id": sample.id,
        "draft_id": draft.id
    }


@pytest.fixture
def sample_file_content():
    """Sample BioTek file content."""
    return dedent("""\
        BioTek Synergy HTX
        Set Temperature: 37°C
        Plate Type: 384-well

        Time\tA1\tA2\tA3\tB1\tB2\tC1\tC2
        0:00\t50\t55\t10\t100\t110\t200\t210
        0:30\t52\t58\t12\t150\t160\t300\t310
        1:00\t55\t60\t15\t200\t210\t400\t410
    """)


class TestUploadValidation:
    """Tests for upload validation."""

    def test_validate_successful(self, db_session, setup_project, sample_file_content):
        """Basic validation succeeds."""
        result = UploadService.validate_upload(
            setup_project["project_id"],
            setup_project["layout_id"],
            sample_file_content,
            "txt"
        )

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.plate_format == 384
        assert result.temperature_setpoint == 37.0
        assert result.num_wells_with_data == 7

    def test_validate_project_not_found(self, db_session):
        """Validation fails for non-existent project."""
        result = UploadService.validate_upload(
            999999, 1, "data", "txt"
        )

        assert not result.is_valid
        assert "Project 999999 not found" in result.errors[0]

    def test_validate_layout_not_found(self, db_session, setup_project, sample_file_content):
        """Validation fails for non-existent layout."""
        result = UploadService.validate_upload(
            setup_project["project_id"],
            999999,
            sample_file_content,
            "txt"
        )

        assert not result.is_valid
        assert "Layout 999999 not found" in result.errors[0]

    def test_validate_draft_construct_blocks(self, db_session, setup_project, sample_file_content):
        """T3.5: Draft construct blocks upload."""
        # Assign draft construct to layout
        PlateLayoutService.assign_well(
            setup_project["layout_id"],
            "D1",
            "testuser",
            construct_id=setup_project["draft_id"],
            well_type=WellType.SAMPLE
        )
        db.session.commit()

        result = UploadService.validate_upload(
            setup_project["project_id"],
            setup_project["layout_id"],
            sample_file_content,
            "txt"
        )

        assert not result.is_valid
        assert "draft constructs" in result.errors[0].lower()
        assert "Draft Construct" in result.errors[0]

    def test_validate_plate_format_mismatch(self, db_session, setup_project):
        """Validation fails when file format doesn't match project."""
        # 96-well data for 384-well project
        content = dedent("""\
            Plate: 96-well
            Time\tA1\tH12
            0\t100\t110
        """)
        result = UploadService.validate_upload(
            setup_project["project_id"],
            setup_project["layout_id"],
            content,
            "txt"
        )

        assert not result.is_valid
        assert "format mismatch" in result.errors[0].lower()

    def test_validate_insufficient_negative_controls(self, db_session, setup_project, sample_file_content):
        """T3.14: Validation fails with insufficient negative controls."""
        # Create new layout with only 1 negative control
        layout = PlateLayoutService.create_layout(
            setup_project["project_id"],
            "Insufficient NC Layout",
            "testuser"
        )
        PlateLayoutService.assign_well(
            layout.id, "A1", "testuser",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        db.session.commit()

        result = UploadService.validate_upload(
            setup_project["project_id"],
            layout.id,
            sample_file_content,
            "txt"
        )

        assert not result.is_valid
        assert "Insufficient negative controls" in result.errors[0]

    def test_validate_incomplete_plate_warning(self, db_session, setup_project):
        """T3.15: Incomplete plate warning shown."""
        # File with minimal data (only 2 of 7 assigned wells have data)
        content = dedent("""\
            Plate Type: 384-well
            Set Temperature: 37°C
            Time\tA1\tA2
            0\t100\t110
            30\t150\t160
        """)
        result = UploadService.validate_upload(
            setup_project["project_id"],
            setup_project["layout_id"],
            content,
            "txt"
        )

        # Should still be valid but with warning
        assert result.is_valid
        assert any(w.code == "INCOMPLETE_PLATE" for w in result.warnings)


class TestUploadProcessing:
    """Tests for upload processing."""

    def test_process_upload_success(self, db_session, setup_project, sample_file_content, temp_data_dir):
        """T3.6: Upload creates records successfully."""
        # Temporarily override data directory
        original_raw_dir = UploadService.RAW_FILES_DIR
        UploadService.RAW_FILES_DIR = temp_data_dir / "raw_files"

        try:
            result = UploadService.process_upload(
                project_id=setup_project["project_id"],
                layout_id=setup_project["layout_id"],
                session_id=None,
                file_content=sample_file_content,
                file_format="txt",
                original_filename="test_data.txt",
                plate_number=1,
                username="testuser",
                session_date=date(2024, 1, 15),
                session_batch_id="Test_Session_001"
            )

            assert result.plate_id > 0
            assert result.session_id > 0
            assert result.wells_created > 0
            assert result.data_points_created > 0

            # Verify plate created
            plate = Plate.query.get(result.plate_id)
            assert plate is not None
            assert plate.plate_number == 1

            # Verify wells created
            wells = Well.query.filter_by(plate_id=plate.id).all()
            assert len(wells) == result.wells_created

            # Verify data points created
            for well in wells:
                data_points = RawDataPoint.query.filter_by(well_id=well.id).all()
                assert len(data_points) > 0

        finally:
            UploadService.RAW_FILES_DIR = original_raw_dir

    def test_process_upload_creates_session(self, db_session, setup_project, sample_file_content, temp_data_dir):
        """New session created when session_id is None."""
        original_raw_dir = UploadService.RAW_FILES_DIR
        UploadService.RAW_FILES_DIR = temp_data_dir / "raw_files"

        try:
            result = UploadService.process_upload(
                project_id=setup_project["project_id"],
                layout_id=setup_project["layout_id"],
                session_id=None,
                file_content=sample_file_content,
                file_format="txt",
                original_filename="test.txt",
                plate_number=1,
                username="testuser",
                session_date=date(2024, 1, 15),
                session_batch_id="Batch_001"
            )

            session = ExperimentalSession.query.get(result.session_id)
            assert session is not None
            assert session.date == date(2024, 1, 15)
            assert session.batch_identifier == "Batch_001"

        finally:
            UploadService.RAW_FILES_DIR = original_raw_dir

    def test_process_upload_uses_existing_session(self, db_session, setup_project, sample_file_content, temp_data_dir):
        """Upload can add to existing session."""
        original_raw_dir = UploadService.RAW_FILES_DIR
        UploadService.RAW_FILES_DIR = temp_data_dir / "raw_files"

        try:
            # Create session first
            session = ExperimentalSession(
                project_id=setup_project["project_id"],
                date=date(2024, 1, 15),
                batch_identifier="Existing_Session"
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

            result = UploadService.process_upload(
                project_id=setup_project["project_id"],
                layout_id=setup_project["layout_id"],
                session_id=session_id,
                file_content=sample_file_content,
                file_format="txt",
                original_filename="test.txt",
                plate_number=1,
                username="testuser"
            )

            assert result.session_id == session_id

        finally:
            UploadService.RAW_FILES_DIR = original_raw_dir

    def test_process_upload_stores_raw_file(self, db_session, setup_project, sample_file_content, temp_data_dir):
        """T3.6: Raw file stored in hierarchical structure."""
        # Temporarily override data directory
        original_raw_dir = UploadService.RAW_FILES_DIR
        UploadService.RAW_FILES_DIR = temp_data_dir / "raw_files"

        try:
            result = UploadService.process_upload(
                project_id=setup_project["project_id"],
                layout_id=setup_project["layout_id"],
                session_id=None,
                file_content=sample_file_content,
                file_format="txt",
                original_filename="original_data.txt",
                plate_number=1,
                username="testuser",
                session_date=date(2024, 1, 15)
            )

            # Verify file exists
            stored_path = Path(result.raw_file_path)
            assert stored_path.exists()

            # Verify content matches (bit-for-bit)
            with open(stored_path, 'r') as f:
                stored_content = f.read()
            assert stored_content == sample_file_content

            # Verify hierarchical structure
            assert f"/{setup_project['project_id']}/" in result.raw_file_path

        finally:
            UploadService.RAW_FILES_DIR = original_raw_dir

    def test_process_upload_validation_error(self, db_session, setup_project):
        """Processing raises error for invalid upload."""
        with pytest.raises(UploadValidationError):
            UploadService.process_upload(
                project_id=999999,
                layout_id=setup_project["layout_id"],
                session_id=None,
                file_content="invalid data",
                file_format="txt",
                original_filename="test.txt",
                plate_number=1,
                username="testuser"
            )


class TestBlankSubtraction:
    """Tests for blank subtraction functionality."""

    def test_blank_subtraction_applied(self, db_session):
        """T3.8: Blank subtraction applied correctly."""
        parsed = ParsedPlateData(
            timepoints=[0, 30, 60],
            well_data={
                "A1": [10.0, 12.0, 15.0],  # Blank
                "A2": [10.0, 12.0, 15.0],  # Blank
                "B1": [110.0, 162.0, 215.0],  # Sample
                "B2": [120.0, 172.0, 225.0],  # Sample
            }
        )

        corrected = UploadService.apply_blank_subtraction(
            parsed, ["A1", "A2"]
        )

        # Blank mean at each timepoint: [10, 12, 15]
        # B1 corrected: [100, 150, 200]
        # B2 corrected: [110, 160, 210]
        assert corrected["B1"] == [100.0, 150.0, 200.0]
        assert corrected["B2"] == [110.0, 160.0, 210.0]

    def test_blank_subtraction_no_blanks(self, db_session):
        """Blank subtraction with no blanks returns original data."""
        parsed = ParsedPlateData(
            timepoints=[0, 30],
            well_data={"A1": [100, 150]}
        )

        corrected = UploadService.apply_blank_subtraction(parsed, [])
        assert corrected["A1"] == [100, 150]

    def test_blank_subtraction_missing_blank_position(self, db_session):
        """Blank subtraction handles missing blank positions."""
        parsed = ParsedPlateData(
            timepoints=[0, 30],
            well_data={"A1": [100, 150]}
        )

        # Blank position not in data
        corrected = UploadService.apply_blank_subtraction(parsed, ["Z99"])
        assert corrected["A1"] == [100, 150]

    def test_blank_subtraction_negative_result(self, db_session):
        """T3.8: Blank subtraction can result in negative values."""
        parsed = ParsedPlateData(
            timepoints=[0, 30],
            well_data={
                "A1": [50.0, 50.0],  # Blank
                "B1": [40.0, 60.0],  # Sample below blank at t=0
            }
        )

        corrected = UploadService.apply_blank_subtraction(parsed, ["A1"])

        # B1 corrected: [-10, 10]
        assert corrected["B1"][0] == -10.0
        assert corrected["B1"][1] == 10.0


class TestEmptyWellDetection:
    """Tests for empty well detection."""

    def test_detect_empty_wells_default_threshold(self, db_session):
        """T3.13: Empty wells detected using default threshold (100 RFU)."""
        parsed = ParsedPlateData(
            timepoints=[0, 30, 60],
            well_data={
                "A1": [50.0, 55.0, 60.0],  # Mean ~55, empty
                "A2": [500.0, 600.0, 700.0],  # Mean ~600, not empty
                "A3": [95.0, 100.0, 105.0],  # Mean 100, borderline
            }
        )

        empty = UploadService.detect_empty_wells(parsed)

        assert "A1" in empty
        assert "A2" not in empty
        # A3 mean is exactly 100, which equals threshold, so not empty
        assert "A3" not in empty

    def test_detect_empty_wells_custom_threshold(self, db_session):
        """T3.13: Empty well threshold configurable."""
        parsed = ParsedPlateData(
            timepoints=[0, 30],
            well_data={
                "A1": [150.0, 160.0],  # Mean 155
                "A2": [300.0, 400.0],  # Mean 350
            }
        )

        # With threshold 200
        empty = UploadService.detect_empty_wells(parsed, threshold=200)
        assert "A1" in empty
        assert "A2" not in empty

        # With threshold 500
        empty = UploadService.detect_empty_wells(parsed, threshold=500)
        assert "A1" in empty
        assert "A2" in empty

    def test_detect_empty_wells_no_data(self, db_session):
        """Wells with no valid data are considered empty."""
        parsed = ParsedPlateData(
            timepoints=[0, 30],
            well_data={
                "A1": [None, None],  # No valid data
                "A2": [100.0, 200.0],  # Has data
            }
        )

        empty = UploadService.detect_empty_wells(parsed)
        assert "A1" in empty


class TestUploadPreview:
    """Tests for upload preview functionality."""

    def test_get_upload_preview(self, db_session, setup_project, sample_file_content):
        """T3.7: Data preview shows all timepoints."""
        preview = UploadService.get_upload_preview(
            setup_project["project_id"],
            setup_project["layout_id"],
            sample_file_content,
            "txt"
        )

        assert preview["is_valid"]
        assert preview["metadata"]["plate_format"] == 384
        assert preview["metadata"]["temperature_setpoint"] == 37.0
        assert preview["metadata"]["num_timepoints"] == 3
        assert preview["matching"]["negative_control_count"] >= 2
        assert "sample_data" in preview

    def test_preview_invalid_file(self, db_session, setup_project):
        """Preview shows errors for invalid files."""
        preview = UploadService.get_upload_preview(
            setup_project["project_id"],
            setup_project["layout_id"],
            "not valid data",
            "txt"
        )

        assert not preview["is_valid"]
        assert len(preview["errors"]) > 0


class TestWarningSuppression:
    """Tests for warning suppression functionality."""

    def test_suppress_incomplete_plate_warning(self, db_session, setup_project, temp_data_dir):
        """T3.16: Warning suppression works."""
        original_raw_dir = UploadService.RAW_FILES_DIR
        UploadService.RAW_FILES_DIR = temp_data_dir / "raw_files"

        try:
            # Minimal data to trigger incomplete plate warning (only 2 of 7 assigned wells)
            content = dedent("""\
                Plate Type: 384-well
                Set Temperature: 37°C
                Time\tA1\tA2
                0\t100\t110
                30\t150\t160
            """)
            # First, verify warning exists
            validation = UploadService.validate_upload(
                setup_project["project_id"],
                setup_project["layout_id"],
                content,
                "txt"
            )
            assert any(w.code == "INCOMPLETE_PLATE" for w in validation.warnings)

            # Process with suppression
            result = UploadService.process_upload(
                project_id=setup_project["project_id"],
                layout_id=setup_project["layout_id"],
                session_id=None,
                file_content=content,
                file_format="txt",
                original_filename="test.txt",
                plate_number=1,
                username="testuser",
                suppressed_warnings=["INCOMPLETE_PLATE"]
            )

            # Should succeed (warning was suppressed)
            assert result.plate_id > 0
            # Suppressed warning should not be in result warnings
            assert not any(w.code == "INCOMPLETE_PLATE" for w in result.warnings)

        finally:
            UploadService.RAW_FILES_DIR = original_raw_dir
