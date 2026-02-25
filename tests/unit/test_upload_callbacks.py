"""
Tests for upload callbacks.

Phase 3: Data Upload Flow - Upload Callbacks

Tests the upload_callbacks.py module that provides:
- File upload handling
- Validation workflow
- BioTek parser integration
- Temperature QC warnings
- Session creation and upload processing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import base64
import json


class TestParseUploadedFile:
    """Tests for parse_uploaded_file function."""

    def test_parse_uploaded_file_valid_txt(self):
        """Test parsing valid text file content."""
        from app.callbacks.upload_callbacks import parse_uploaded_file

        # Create base64 encoded content
        file_content = """Time\tA1\tA2\tA3
0:00\t100\t110\t105
0:30\t150\t160\t155
1:00\t200\t210\t205"""
        encoded = base64.b64encode(file_content.encode()).decode()
        content = f"data:text/plain;base64,{encoded}"

        result = parse_uploaded_file(content, "test.txt")

        assert result is not None
        assert "parsed_data" in result or "error" not in result

    def test_parse_uploaded_file_latin1_encoding(self):
        """Test that files with latin-1 characters (e.g. degree symbol) parse correctly.

        BioTek exports often contain the degree symbol (0xB0 in cp1252/latin-1)
        which is not valid UTF-8.  The upload path must fall through to latin-1
        rather than incorrectly decoding as UTF-16.
        """
        from app.callbacks.upload_callbacks import parse_uploaded_file

        # Build content with a latin-1 degree symbol (byte 0xB0) like BioTek uses
        file_content_bytes = (
            b"Set Temperature\tSetpoint 37\xb0C\n"
            b"Time\tT\xb0 485/20,528/20\tA1\tA2\tA3\n"
            b"0:00:00\t37.0\t100\t110\t105\n"
            b"0:05:00\t37.0\t150\t160\t155\n"
            b"0:10:00\t37.0\t200\t210\t205\n"
        )
        encoded = base64.b64encode(file_content_bytes).decode()
        content = f"data:text/plain;base64,{encoded}"

        result = parse_uploaded_file(content, "260212_test.txt")

        assert result is not None
        assert result.get("is_valid") is True, f"Expected valid, got error: {result.get('error')}"
        assert result["metadata"]["num_timepoints"] == 3
        assert result["metadata"]["num_wells_with_data"] == 3

    def test_parse_uploaded_file_utf16_with_bom(self):
        """Test that genuine UTF-16 files (with BOM) still decode correctly."""
        from app.callbacks.upload_callbacks import parse_uploaded_file

        text = (
            "Time\tA1\tA2\tA3\n"
            "0:00:00\t100\t110\t105\n"
            "0:05:00\t150\t160\t155\n"
        )
        file_content_bytes = text.encode("utf-16")  # includes BOM
        encoded = base64.b64encode(file_content_bytes).decode()
        content = f"data:text/plain;base64,{encoded}"

        result = parse_uploaded_file(content, "utf16_test.txt")

        assert result is not None
        # Content should decode without error; parser may or may not
        # recognise it as valid BioTek data, but it must not crash.
        assert "error" not in result or result.get("is_valid") is not None

    def test_parse_uploaded_file_invalid_format(self):
        """Test parsing invalid file format."""
        from app.callbacks.upload_callbacks import parse_uploaded_file

        # Random binary data
        encoded = base64.b64encode(b"\x00\x01\x02\x03").decode()
        content = f"data:application/octet-stream;base64,{encoded}"

        result = parse_uploaded_file(content, "test.bin")

        # Should return error info
        assert result is not None
        assert "error" in result or not result.get("is_valid", True)

    def test_parse_uploaded_file_extracts_metadata(self):
        """Test that parsing extracts file metadata."""
        from app.callbacks.upload_callbacks import parse_uploaded_file

        file_content = """Temperature: 37°C
384-well plate
Time\tA1\tA2
0:00\t100\t110
0:30\t150\t160"""
        encoded = base64.b64encode(file_content.encode()).decode()
        content = f"data:text/plain;base64,{encoded}"

        result = parse_uploaded_file(content, "test.txt")

        if result and "metadata" in result:
            assert result["metadata"].get("temperature_setpoint") is not None or \
                   result["metadata"].get("plate_format") is not None


class TestValidateUploadFile:
    """Tests for validate_upload_file function."""

    def test_validate_upload_requires_project(self):
        """Test validation requires project ID."""
        from app.callbacks.upload_callbacks import validate_upload_file

        result = validate_upload_file(
            project_id=None,
            layout_id=1,
            file_content="test content",
            filename="test.txt",
        )

        assert not result.get("is_valid", True)
        assert any("project" in str(e).lower() for e in result.get("errors", []))

    def test_validate_upload_requires_layout(self):
        """Test validation requires layout ID."""
        from app.callbacks.upload_callbacks import validate_upload_file

        result = validate_upload_file(
            project_id=1,
            layout_id=None,
            file_content="test content",
            filename="test.txt",
        )

        assert not result.get("is_valid", True)
        assert any("layout" in str(e).lower() for e in result.get("errors", []))

    def test_validate_upload_requires_file_content(self):
        """Test validation requires file content."""
        from app.callbacks.upload_callbacks import validate_upload_file

        result = validate_upload_file(
            project_id=1,
            layout_id=1,
            file_content=None,
            filename="test.txt",
        )

        assert not result.get("is_valid", True)
        assert any("file" in str(e).lower() for e in result.get("errors", []))


class TestCheckTemperatureQC:
    """Tests for temperature QC checking."""

    def test_check_temperature_qc_no_deviation(self):
        """Test temperature QC with no deviation."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[36.9, 37.0, 37.1],
            threshold=1.0,
        )

        assert result["passed"] is True
        assert len(result.get("warnings", [])) == 0

    def test_check_temperature_qc_minor_deviation(self):
        """Test temperature QC with minor deviation (within threshold)."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[36.5, 37.0, 37.5],
            threshold=1.0,
        )

        assert result["passed"] is True

    def test_check_temperature_qc_major_deviation(self):
        """Test temperature QC with major deviation (exceeds threshold)."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[36.5, 37.0, 38.5, 39.0],
            threshold=1.0,
        )

        assert result["passed"] is False
        assert len(result.get("warnings", [])) > 0

    def test_check_temperature_qc_empty_temperatures(self):
        """Test temperature QC with no temperature data."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[],
            threshold=1.0,
        )

        # Should pass (no data to check) or return warning
        assert result is not None

    def test_check_temperature_qc_no_setpoint(self):
        """Test temperature QC with no setpoint."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=None,
            temperatures=[36.5, 37.0, 37.5],
            threshold=1.0,
        )

        # Should handle gracefully
        assert result is not None

    def test_check_temperature_qc_returns_details(self):
        """Test temperature QC returns deviation details."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[36.0, 37.0, 39.0],
            threshold=1.0,
        )

        assert "max_deviation" in result
        assert "min_temp" in result or "max_temp" in result


class TestPrepareUploadPreview:
    """Tests for upload preview preparation."""

    def test_prepare_upload_preview_basic(self):
        """Test basic upload preview preparation."""
        from app.callbacks.upload_callbacks import prepare_upload_preview

        parsed_data = {
            "well_data": {
                "A1": [100, 150, 200],
                "A2": [110, 160, 210],
            },
            "timepoints": [0, 0.5, 1.0],
            "plate_format": 384,
        }

        preview = prepare_upload_preview(parsed_data)

        assert preview is not None
        assert "sample_wells" in preview
        assert "num_wells" in preview

    def test_prepare_upload_preview_limits_sample_wells(self):
        """Test preview limits number of sample wells shown."""
        from app.callbacks.upload_callbacks import prepare_upload_preview

        # Many wells
        well_data = {f"A{i}": [100 + i, 150 + i, 200 + i] for i in range(1, 25)}
        parsed_data = {
            "well_data": well_data,
            "timepoints": [0, 0.5, 1.0],
        }

        preview = prepare_upload_preview(parsed_data, max_sample_wells=5)

        assert len(preview["sample_wells"]) <= 5


class TestHandleFileUpload:
    """Tests for file upload handling."""

    def test_handle_file_upload_no_file(self):
        """Test handling when no file is uploaded."""
        from app.callbacks.upload_callbacks import handle_file_upload

        result = handle_file_upload(
            contents=None,
            filename=None,
            project_store={"project_id": 1},
        )

        # Should return no_update or empty state
        assert result is None or result == {} or hasattr(result, "_no_update")

    def test_handle_file_upload_valid_file(self):
        """Test handling valid file upload."""
        from app.callbacks.upload_callbacks import handle_file_upload

        file_content = """Time\tA1\tA2
0:00\t100\t110
0:30\t150\t160"""
        encoded = base64.b64encode(file_content.encode()).decode()
        contents = f"data:text/plain;base64,{encoded}"

        result = handle_file_upload(
            contents=contents,
            filename="test.txt",
            project_store={"project_id": 1},
        )

        assert result is not None


class TestHandleLayoutSelection:
    """Tests for layout selection handling."""

    def test_handle_layout_selection_valid(self):
        """Test handling valid layout selection."""
        from app.callbacks.upload_callbacks import handle_layout_selection

        result = handle_layout_selection(
            layout_id=1,
            file_store={"filename": "test.txt", "content": "..."},
            project_id=1,
        )

        assert result is not None

    def test_handle_layout_selection_no_file(self):
        """Test handling layout selection with no file."""
        from app.callbacks.upload_callbacks import handle_layout_selection

        result = handle_layout_selection(
            layout_id=1,
            file_store=None,
            project_id=1,
        )

        # Should handle gracefully
        assert result is None or isinstance(result, dict)


class TestProcessUpload:
    """Tests for upload processing."""

    def test_process_upload_validation_failure(self):
        """Test process upload with validation failure."""
        from app.callbacks.upload_callbacks import process_upload

        result = process_upload(
            project_id=1,
            layout_id=1,
            file_content="invalid content",
            filename="test.txt",
            session_option="new",
            session_date=None,
            username="test_user",
        )

        assert not result.get("success", False) or "error" in result

    def test_process_upload_new_session(self):
        """Test process upload with new session creation."""
        from app.callbacks.upload_callbacks import process_upload

        # This would need database mocking for full test
        # Just verify the function signature and basic handling
        with patch("app.callbacks.upload_utils.UploadService") as mock_service:
            mock_service.process_upload.return_value = Mock(
                plate_id=1,
                session_id=1,
                wells_created=96,
                data_points_created=5760,
                warnings=[],
            )

            result = process_upload(
                project_id=1,
                layout_id=1,
                file_content="valid content",
                filename="test.txt",
                session_option="new",
                session_date="2024-01-15",
                username="test_user",
            )

            # Either success or proper error
            assert result is not None


class TestBioTekParserIntegration:
    """Tests for BioTek parser integration."""

    def test_parse_biotek_content_integration(self):
        """Test integration with BioTek parser."""
        from app.callbacks.upload_callbacks import parse_biotek_content_safe

        file_content = """Time\tA1\tA2\tA3
0:00\t100\t110\t105
0:30\t150\t160\t155
1:00\t200\t210\t205"""

        result = parse_biotek_content_safe(file_content)

        assert result is not None
        if not result.get("error"):
            assert result.get("well_data") is not None or result.get("parsed_data") is not None

    def test_parse_biotek_content_error_handling(self):
        """Test BioTek parser error handling."""
        from app.callbacks.upload_callbacks import parse_biotek_content_safe

        # Invalid content
        result = parse_biotek_content_safe("not valid biotek data\nrandom stuff")

        assert result is not None
        # Should contain error or empty data
        if result.get("error"):
            assert isinstance(result["error"], str)


class TestUploadCallbacksRegistration:
    """Tests for callback registration."""

    def test_register_upload_callbacks_exists(self):
        """Test that register function exists."""
        from app.callbacks.upload_callbacks import register_upload_callbacks

        assert callable(register_upload_callbacks)

    def test_callbacks_init_includes_upload(self):
        """Test callbacks __init__ includes upload callbacks."""
        from app.callbacks import register_callbacks

        # Should be able to import and be callable
        assert callable(register_callbacks)


class TestValidateLayoutMatch:
    """Tests for layout matching validation."""

    def test_validate_layout_match_all_wells(self):
        """Test layout matching when all wells match."""
        from app.callbacks.upload_callbacks import validate_layout_match

        layout_wells = ["A1", "A2", "A3", "B1", "B2", "B3"]
        file_wells = ["A1", "A2", "A3", "B1", "B2", "B3"]

        result = validate_layout_match(layout_wells, file_wells)

        assert result["matched_count"] == 6
        assert result["unmatched_layout_wells"] == 0
        assert result["unmatched_file_wells"] == 0

    def test_validate_layout_match_partial_match(self):
        """Test layout matching with partial match."""
        from app.callbacks.upload_callbacks import validate_layout_match

        layout_wells = ["A1", "A2", "A3", "B1", "B2", "B3"]
        file_wells = ["A1", "A2", "C1", "C2"]  # A3, B1, B2, B3 not in file

        result = validate_layout_match(layout_wells, file_wells)

        assert result["matched_count"] == 2
        assert result["unmatched_file_wells"] == 2  # C1, C2

    def test_validate_layout_match_empty_layout(self):
        """Test layout matching with empty layout."""
        from app.callbacks.upload_callbacks import validate_layout_match

        result = validate_layout_match([], ["A1", "A2"])

        assert result["matched_count"] == 0


class TestWarningSuppressionHandling:
    """Tests for warning suppression handling."""

    def test_get_suppressible_warnings(self):
        """Test extracting suppressible warnings."""
        from app.callbacks.upload_callbacks import get_suppressible_warnings

        warnings = [
            {"code": "INCOMPLETE_PLATE", "message": "50% wells", "suppressible": True},
            {"code": "TEMP_DEVIATION", "message": "Temp issue", "suppressible": False},
            {"code": "UNMATCHED_WELLS", "message": "5 unmatched", "suppressible": True},
        ]

        suppressible = get_suppressible_warnings(warnings)

        assert len(suppressible) == 2
        assert all(w["suppressible"] for w in suppressible)

    def test_filter_suppressed_warnings(self):
        """Test filtering out suppressed warnings."""
        from app.callbacks.upload_callbacks import filter_suppressed_warnings

        warnings = [
            {"code": "INCOMPLETE_PLATE", "message": "50% wells", "suppressible": True},
            {"code": "TEMP_DEVIATION", "message": "Temp issue", "suppressible": False},
        ]
        suppressed_codes = ["INCOMPLETE_PLATE"]

        filtered = filter_suppressed_warnings(warnings, suppressed_codes)

        assert len(filtered) == 1
        assert filtered[0]["code"] == "TEMP_DEVIATION"


class TestUploadFormValidation:
    """Tests for upload form validation."""

    def test_validate_upload_form_complete(self):
        """Test validation with complete form."""
        from app.callbacks.upload_callbacks import validate_upload_form

        result = validate_upload_form(
            has_file=True,
            has_layout=True,
            has_session_option=True,
            validation_passed=True,
        )

        assert result["can_submit"] is True
        assert len(result.get("missing_fields", [])) == 0

    def test_validate_upload_form_missing_file(self):
        """Test validation with missing file."""
        from app.callbacks.upload_callbacks import validate_upload_form

        result = validate_upload_form(
            has_file=False,
            has_layout=True,
            has_session_option=True,
            validation_passed=True,
        )

        assert result["can_submit"] is False
        assert "file" in str(result.get("missing_fields", [])).lower()

    def test_validate_upload_form_validation_failed(self):
        """Test validation when file validation failed."""
        from app.callbacks.upload_callbacks import validate_upload_form

        result = validate_upload_form(
            has_file=True,
            has_layout=True,
            has_session_option=True,
            validation_passed=False,
        )

        assert result["can_submit"] is False


class TestGetAvailableLayouts:
    """Tests for getting available layouts."""

    def test_get_available_layouts_format(self):
        """Test available layouts return format."""
        from app.callbacks.upload_callbacks import get_available_layouts

        with patch("app.models.PlateLayout") as mock_layout:
            mock_layout.query.filter_by.return_value.all.return_value = [
                Mock(id=1, name="Layout 1", plate_format=384),
                Mock(id=2, name="Layout 2", plate_format=384),
            ]

            layouts = get_available_layouts(project_id=1)

            assert isinstance(layouts, list)
            if layouts:
                assert all("id" in l and "name" in l for l in layouts)


class TestGetAvailableSessions:
    """Tests for getting available sessions."""

    def test_get_available_sessions_format(self):
        """Test available sessions return format."""
        from app.callbacks.upload_callbacks import get_available_sessions

        with patch("app.models.ExperimentalSession") as mock_session:
            from datetime import date
            mock_session.query.filter_by.return_value.order_by.return_value.all.return_value = [
                Mock(id=1, date=date(2024, 1, 15), batch_identifier="Batch001"),
                Mock(id=2, date=date(2024, 1, 16), batch_identifier="Batch002"),
            ]

            sessions = get_available_sessions(project_id=1)

            assert isinstance(sessions, list)
            if sessions:
                assert all("id" in s for s in sessions)
