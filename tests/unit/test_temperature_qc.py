"""
Tests for temperature QC warnings.

Phase 3: Data Upload Flow - Temperature QC

Tests temperature quality control validation that:
- Detects temperature deviations from setpoint
- Generates warnings when threshold exceeded (±1°C default)
- Provides detailed deviation information
- Integrates with upload validation
"""
import pytest
from unittest.mock import Mock, patch


class TestTemperatureDeviationDetection:
    """Tests for temperature deviation detection."""

    def test_detect_deviation_within_threshold(self):
        """Test detection when temperatures within threshold."""
        from app.callbacks.upload_callbacks import detect_temperature_deviation

        setpoint = 37.0
        temperatures = [36.8, 37.0, 37.2, 36.9, 37.1]
        threshold = 1.0

        result = detect_temperature_deviation(setpoint, temperatures, threshold)

        assert result["has_deviation"] is False
        assert result["max_deviation"] <= threshold

    def test_detect_deviation_exceeds_threshold(self):
        """Test detection when temperatures exceed threshold."""
        from app.callbacks.upload_callbacks import detect_temperature_deviation

        setpoint = 37.0
        temperatures = [36.8, 37.0, 38.5, 36.5, 37.1]  # 38.5 exceeds by 1.5
        threshold = 1.0

        result = detect_temperature_deviation(setpoint, temperatures, threshold)

        assert result["has_deviation"] is True
        assert result["max_deviation"] > threshold

    def test_detect_deviation_returns_extremes(self):
        """Test detection returns min and max temperatures."""
        from app.callbacks.upload_callbacks import detect_temperature_deviation

        setpoint = 37.0
        temperatures = [35.0, 37.0, 39.0, 37.5]
        threshold = 1.0

        result = detect_temperature_deviation(setpoint, temperatures, threshold)

        assert result["min_temp"] == 35.0
        assert result["max_temp"] == 39.0

    def test_detect_deviation_empty_list(self):
        """Test detection with empty temperature list."""
        from app.callbacks.upload_callbacks import detect_temperature_deviation

        result = detect_temperature_deviation(37.0, [], 1.0)

        assert result["has_deviation"] is False
        assert result.get("min_temp") is None
        assert result.get("max_temp") is None

    def test_detect_deviation_none_setpoint(self):
        """Test detection with None setpoint."""
        from app.callbacks.upload_callbacks import detect_temperature_deviation

        result = detect_temperature_deviation(None, [36.5, 37.0, 37.5], 1.0)

        # Should handle gracefully - no comparison possible
        assert result["has_deviation"] is False


class TestTemperatureQCWarningGeneration:
    """Tests for temperature QC warning generation."""

    def test_generate_warning_message_above_threshold(self):
        """Test warning message when temp above threshold."""
        from app.callbacks.upload_callbacks import generate_temperature_warning_message

        message = generate_temperature_warning_message(
            setpoint=37.0,
            actual_temp=38.5,
            threshold=1.0,
        )

        assert "temperature" in message.lower()
        assert "38.5" in message or "38.5" in str(message)
        assert "37" in message

    def test_generate_warning_message_below_threshold(self):
        """Test warning message when temp below threshold."""
        from app.callbacks.upload_callbacks import generate_temperature_warning_message

        message = generate_temperature_warning_message(
            setpoint=37.0,
            actual_temp=35.5,
            threshold=1.0,
        )

        assert "temperature" in message.lower()
        assert "35.5" in message or "35.5" in str(message)

    def test_generate_warning_includes_deviation(self):
        """Test warning includes deviation amount."""
        from app.callbacks.upload_callbacks import generate_temperature_warning_message

        message = generate_temperature_warning_message(
            setpoint=37.0,
            actual_temp=39.0,
            threshold=1.0,
        )

        # Should mention the 2.0°C deviation or the values
        assert "2" in message or ("39" in message and "37" in message)


class TestTemperatureQCThresholds:
    """Tests for temperature QC threshold handling."""

    def test_default_threshold_is_one_degree(self):
        """Test default threshold is ±1°C per PRD."""
        from app.callbacks.upload_callbacks import TEMPERATURE_QC_THRESHOLD

        assert TEMPERATURE_QC_THRESHOLD == 1.0

    def test_custom_threshold_respected(self):
        """Test custom threshold is respected."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        # With 2.0 threshold, 38.5 should pass
        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[38.5],  # 1.5 deviation
            threshold=2.0,
        )

        assert result["passed"] is True

    def test_strict_threshold_catches_small_deviations(self):
        """Test strict threshold catches small deviations."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        # With 0.5 threshold, 37.6 should fail
        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[37.6],  # 0.6 deviation
            threshold=0.5,
        )

        assert result["passed"] is False


class TestTemperatureQCIntegration:
    """Tests for temperature QC integration with upload."""

    def test_validation_includes_temperature_check(self):
        """Test upload validation includes temperature QC."""
        from app.callbacks.upload_callbacks import validate_upload_file

        with patch("app.callbacks.upload_utils.UploadService") as mock_service:
            # Mock validation result with temperature data
            mock_result = Mock()
            mock_result.is_valid = True
            mock_result.parsed_data = Mock()
            mock_result.parsed_data.temperature_setpoint = 37.0
            mock_result.parsed_data.temperatures = [38.5, 39.0]  # Above threshold
            mock_result.warnings = []

            mock_service.validate_upload.return_value = mock_result

            result = validate_upload_file(
                project_id=1,
                layout_id=1,
                file_content="test content",
                filename="test.txt",
            )

            # Temperature QC should be checked during validation
            assert result is not None

    def test_temperature_warning_in_validation_result(self):
        """Test temperature warning appears in validation result."""
        from app.callbacks.upload_callbacks import add_temperature_qc_warnings

        validation_result = {
            "is_valid": True,
            "warnings": [],
            "metadata": {
                "temperature_setpoint": 37.0,
            },
        }
        temperatures = [38.5, 39.0]

        updated = add_temperature_qc_warnings(validation_result, temperatures)

        # Should have added temperature warning
        temp_warnings = [w for w in updated.get("warnings", [])
                        if "TEMP" in w.get("code", "").upper()]
        assert len(temp_warnings) > 0


class TestTemperatureQCReporting:
    """Tests for temperature QC reporting."""

    def test_temperature_qc_summary_format(self):
        """Test temperature QC summary format."""
        from app.callbacks.upload_callbacks import create_temperature_qc_summary

        summary = create_temperature_qc_summary(
            setpoint=37.0,
            temperatures=[36.5, 37.0, 37.5, 38.5],
            threshold=1.0,
        )

        assert "setpoint" in summary
        assert "min" in summary or "min_temp" in summary
        assert "max" in summary or "max_temp" in summary
        assert "passed" in summary or "status" in summary

    def test_temperature_qc_affected_timepoints(self):
        """Test identifying affected timepoints."""
        from app.callbacks.upload_callbacks import get_affected_temperature_timepoints

        temperatures = [37.0, 37.0, 38.5, 39.0, 37.2]
        setpoint = 37.0
        threshold = 1.0

        affected = get_affected_temperature_timepoints(
            temperatures, setpoint, threshold
        )

        # Timepoints 2 and 3 (0-indexed) exceed threshold
        assert 2 in affected or len(affected) >= 2


class TestTemperatureQCEdgeCases:
    """Tests for temperature QC edge cases."""

    def test_single_temperature_reading(self):
        """Test QC with single temperature reading."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[38.5],
            threshold=1.0,
        )

        assert result["passed"] is False
        assert result["max_deviation"] >= 1.5

    def test_all_temperatures_identical(self):
        """Test QC when all temperatures identical."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[37.0, 37.0, 37.0, 37.0],
            threshold=1.0,
        )

        assert result["passed"] is True
        assert result["max_deviation"] == 0.0

    def test_temperatures_with_none_values(self):
        """Test QC with None values in temperature list."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=37.0,
            temperatures=[36.5, None, 37.5, None, 38.5],
            threshold=1.0,
        )

        # Should filter out None values and check remaining
        assert result is not None
        assert result.get("max_deviation") is not None

    def test_negative_temperatures(self):
        """Test QC with negative temperatures (edge case)."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=0.0,  # Freezing point experiment
            temperatures=[-1.0, 0.0, 0.5],
            threshold=1.0,
        )

        assert result["passed"] is True

    def test_very_high_temperatures(self):
        """Test QC with very high temperatures."""
        from app.callbacks.upload_callbacks import check_temperature_qc

        result = check_temperature_qc(
            setpoint=65.0,  # High-temp experiment
            temperatures=[64.5, 65.0, 67.5],  # 2.5 deviation
            threshold=1.0,
        )

        assert result["passed"] is False
        assert result["max_deviation"] >= 2.0


class TestTemperatureWarningDisplay:
    """Tests for temperature warning display components."""

    def test_create_temperature_alert_warning(self):
        """Test creating temperature alert for warning."""
        from app.layouts.data_upload import create_temperature_warning

        alert = create_temperature_warning(
            setpoint=37.0,
            actual_temps=[38.5, 39.0],
            threshold=1.0,
        )

        # Should create an alert component
        assert alert is not None
        alert_str = str(alert)
        assert "temperature" in alert_str.lower() or "°" in alert_str

    def test_create_temperature_alert_no_warning(self):
        """Test no alert when temperatures are fine."""
        from app.layouts.data_upload import create_temperature_warning

        alert = create_temperature_warning(
            setpoint=37.0,
            actual_temps=[36.8, 37.0, 37.2],
            threshold=1.0,
        )

        # Should return None or empty when no warning needed
        assert alert is None or str(alert) == ""
