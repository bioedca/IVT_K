"""
Tests for the Quality Control module.

Phase 3.8-3.9: QC Enhancement Tests
"""
import pytest
import numpy as np

from app.analysis.quality_control import (
    QualityControl,
    QCSettings,
    QCFlag,
    QCSeverity,
    QCIssue,
    DriftResult,
    SaturationResult,
    OutlierResult,
    WellQCReport,
    PlateQCReport,
)


class TestQCSettings:
    """Tests for QC settings dataclass."""

    def test_default_settings(self):
        """Test default QC settings values."""
        settings = QCSettings()

        assert settings.cv_threshold == 0.20
        assert settings.outlier_threshold == 3.0
        assert settings.saturation_threshold == 0.95
        assert settings.drift_threshold == 0.1
        assert settings.min_baseline_points == 3
        assert settings.detector_max == 65535.0
        assert settings.temperature_drift_threshold == 1.0

    def test_custom_settings(self):
        """Test creating custom QC settings."""
        settings = QCSettings(
            cv_threshold=0.15,
            outlier_threshold=2.5,
            saturation_threshold=0.90,
        )

        assert settings.cv_threshold == 0.15
        assert settings.outlier_threshold == 2.5
        assert settings.saturation_threshold == 0.90


class TestBaselineDriftDetection:
    """Tests for baseline drift detection (F7.2)."""

    def test_no_drift_flat_signal(self):
        """Test no drift detected for flat signal."""
        qc = QualityControl()
        values = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]

        result = qc.detect_baseline_drift(values)

        assert not result.has_drift
        assert abs(result.slope) < 0.01
        assert result.relative_slope < 0.1

    def test_drift_detected_rising_signal(self):
        """Test drift detected for rising baseline."""
        qc = QualityControl(QCSettings(drift_threshold=0.1))
        # 50% increase over baseline - should trigger drift
        values = [1000.0, 1500.0, 2000.0, 2500.0, 3000.0]
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        result = qc.detect_baseline_drift(values, timepoints)

        assert result.has_drift
        assert result.slope > 0

    def test_drift_with_timepoints(self):
        """Test drift detection with explicit timepoints."""
        qc = QualityControl()
        values = [100.0, 150.0, 200.0]
        timepoints = [0.0, 60.0, 120.0]

        result = qc.detect_baseline_drift(values, timepoints)

        assert result.baseline_points == 3
        assert result.r_squared > 0.9

    def test_drift_insufficient_points(self):
        """Test drift detection with insufficient points."""
        qc = QualityControl()
        values = [1000.0]

        result = qc.detect_baseline_drift(values)

        assert not result.has_drift
        assert result.baseline_points == 1


class TestSaturationDetection:
    """Tests for saturation detection (F7.4)."""

    def test_no_saturation(self):
        """Test no saturation for normal signal."""
        qc = QualityControl()
        values = [1000.0, 2000.0, 3000.0, 4000.0]

        result = qc.detect_saturation(values)

        assert not result.is_saturated
        assert result.max_value == 4000.0
        assert result.saturation_ratio < 0.1

    def test_saturation_detected(self):
        """Test saturation detected at detector max."""
        qc = QualityControl()
        # 96% of 65535 = 62913, above 95% threshold
        values = [1000.0, 30000.0, 62913.0, 64000.0]

        result = qc.detect_saturation(values)

        assert result.is_saturated
        assert len(result.saturated_timepoints) >= 1

    def test_saturation_custom_max(self):
        """Test saturation with custom detector max."""
        qc = QualityControl()
        values = [100.0, 9000.0, 9800.0]  # 98% of 10000

        result = qc.detect_saturation(values, detector_max=10000.0)

        assert result.is_saturated
        assert 2 in result.saturated_timepoints

    def test_saturation_empty_values(self):
        """Test saturation with empty values."""
        qc = QualityControl()
        values = []

        result = qc.detect_saturation(values)

        assert not result.is_saturated
        assert result.max_value == 0.0


class TestOutlierDetection:
    """Tests for MAD-based outlier detection (F7.3)."""

    def test_no_outliers(self):
        """Test no outliers in uniform data."""
        qc = QualityControl()
        values = [100.0, 102.0, 98.0, 101.0, 99.0]

        result = qc.detect_outliers_mad(values)

        assert len(result.outlier_indices) == 0
        assert result.median == pytest.approx(100.0, rel=0.01)

    def test_outlier_detected(self):
        """Test outlier detected in data."""
        qc = QualityControl()
        # One clear outlier (500) among similar values
        values = [100.0, 102.0, 98.0, 101.0, 500.0]

        result = qc.detect_outliers_mad(values)

        assert len(result.outlier_indices) >= 1
        assert 4 in result.outlier_indices  # Index of 500.0
        assert 500.0 in result.outlier_values

    def test_mad_calculation(self):
        """Test MAD calculation accuracy."""
        qc = QualityControl()
        # For [1, 2, 3, 4, 5], median=3, deviations=[2,1,0,1,2], MAD=1
        values = [1.0, 2.0, 3.0, 4.0, 5.0]

        result = qc.detect_outliers_mad(values)

        assert result.median == 3.0
        assert result.mad == 1.0

    def test_insufficient_values(self):
        """Test outlier detection with insufficient values."""
        qc = QualityControl()
        values = [100.0, 200.0]

        result = qc.detect_outliers_mad(values)

        assert len(result.outlier_indices) == 0

    def test_identical_values(self):
        """Test outlier detection when all values are identical."""
        qc = QualityControl()
        values = [100.0, 100.0, 100.0, 100.0]

        result = qc.detect_outliers_mad(values)

        assert result.mad == 0.0
        assert len(result.outlier_indices) == 0


class TestTemperatureDrift:
    """Tests for temperature drift detection."""

    def test_no_temperature_drift(self):
        """Test no drift when temperature is stable."""
        qc = QualityControl()
        temperatures = [37.0, 37.1, 36.9, 37.0, 37.1]

        has_drift, flagged, max_dev = qc.detect_temperature_drift(temperatures, setpoint=37.0)

        assert not has_drift
        assert len(flagged) == 0
        assert max_dev < 1.0

    def test_temperature_drift_detected(self):
        """Test drift detected when temperature varies."""
        qc = QualityControl(QCSettings(temperature_drift_threshold=1.0))
        temperatures = [37.0, 37.5, 38.5, 39.0]  # Exceeds 1C threshold

        has_drift, flagged, max_dev = qc.detect_temperature_drift(temperatures, setpoint=37.0)

        assert has_drift
        assert len(flagged) >= 1
        assert max_dev >= 1.5

    def test_temperature_drift_no_setpoint(self):
        """Test drift detection without explicit setpoint."""
        qc = QualityControl()
        temperatures = [37.0, 39.0, 40.0]

        has_drift, flagged, max_dev = qc.detect_temperature_drift(temperatures)

        # Uses first temperature as setpoint
        assert has_drift
        assert max_dev >= 2.0


class TestCVCalculation:
    """Tests for coefficient of variation calculation."""

    def test_cv_calculation(self):
        """Test CV calculation."""
        qc = QualityControl()
        # Mean = 100, SD = 10, CV = 0.10
        values = [90.0, 100.0, 110.0]

        cv = qc.compute_cv(values)

        # SD of [90, 100, 110] with ddof=1 is 10.0, mean is 100, CV = 0.10
        assert cv == pytest.approx(0.10, rel=0.01)

    def test_cv_single_value(self):
        """Test CV with single value."""
        qc = QualityControl()
        values = [100.0]

        cv = qc.compute_cv(values)

        assert cv == 0.0

    def test_cv_threshold_check(self):
        """Test CV threshold checking."""
        qc = QualityControl(QCSettings(cv_threshold=0.20))

        # Low CV (should pass)
        low_cv_values = {"A1": 100.0, "A2": 102.0, "A3": 98.0}
        exceeds, cv = qc.check_replicate_cv(low_cv_values)
        assert not exceeds

        # High CV (should flag)
        high_cv_values = {"A1": 100.0, "A2": 150.0, "A3": 50.0}
        exceeds, cv = qc.check_replicate_cv(high_cv_values)
        assert exceeds


class TestWellQC:
    """Tests for per-well QC reports."""

    def test_well_qc_clean_data(self):
        """Test well QC with clean data."""
        qc = QualityControl()
        values = [1000.0 + i * 100 for i in range(50)]

        report = qc.run_well_qc("A1", values)

        assert report.position == "A1"
        # May have some issues depending on data characteristics

    def test_well_qc_saturated(self):
        """Test well QC detects saturation."""
        qc = QualityControl()
        values = [1000.0, 30000.0, 65000.0]  # Near detector max

        report = qc.run_well_qc("A1", values)

        assert report.saturation_result.is_saturated
        assert any(i.flag == QCFlag.SATURATION for i in report.issues)

    def test_well_qc_empty(self):
        """Test well QC with no data."""
        qc = QualityControl()

        report = qc.run_well_qc("A1", [])

        assert report.has_issues
        assert any(i.flag == QCFlag.LOW_SIGNAL for i in report.issues)


class TestPlateQC:
    """Tests for plate-level QC reports."""

    def test_plate_qc_report(self):
        """Test plate QC report generation."""
        qc = QualityControl()
        well_data = {
            "A1": [1000.0 + i * 10 for i in range(50)],
            "A2": [1100.0 + i * 10 for i in range(50)],
            "B1": [900.0 + i * 10 for i in range(50)],
        }

        report = qc.run_plate_qc(well_data)

        assert len(report.well_reports) == 3
        assert "A1" in report.well_reports
        assert "A2" in report.well_reports
        assert "B1" in report.well_reports

    def test_plate_qc_flagged_wells(self):
        """Test getting flagged wells from plate report."""
        qc = QualityControl()
        well_data = {
            "A1": [1000.0] * 50,  # Clean
            "A2": [65000.0] * 50,  # Saturated
        }

        report = qc.run_plate_qc(well_data)

        flagged = report.get_flagged_wells()
        assert "A2" in flagged

    def test_plate_qc_control_verification(self):
        """Test control pairing verification."""
        qc = QualityControl()
        well_data = {
            "A1": [1000.0] * 50,
            "A2": [1100.0] * 50,
        }
        # Provide partial control mapping missing required controls
        control_mapping = {
            "negative_control": [],  # Empty - missing
            # Missing wildtype entirely
        }

        report = qc.run_plate_qc(well_data, control_mapping=control_mapping)

        # Should flag missing controls
        assert any(
            i.flag == QCFlag.MISSING_CONTROL
            for i in report.plate_issues
        )


class TestReplicateOutliers:
    """Tests for replicate outlier detection."""

    def test_replicate_outliers(self):
        """Test outlier detection among replicates."""
        qc = QualityControl()
        replicate_values = {
            "A1": 0.05,
            "A2": 0.048,
            "A3": 0.052,
            "A4": 0.15,  # Outlier
        }

        result, issues = qc.check_replicate_outliers(replicate_values, "k_obs")

        assert len(result.outlier_indices) >= 1
        assert any("A4" == i.well_position for i in issues)

    def test_no_replicate_outliers(self):
        """Test no outliers among similar replicates."""
        qc = QualityControl()
        replicate_values = {
            "A1": 0.050,
            "A2": 0.048,
            "A3": 0.052,
            "A4": 0.049,
        }

        result, issues = qc.check_replicate_outliers(replicate_values, "k_obs")

        assert len(result.outlier_indices) == 0
        assert len(issues) == 0


class TestQCIssue:
    """Tests for QC issue dataclass."""

    def test_qc_issue_creation(self):
        """Test creating QC issues."""
        issue = QCIssue(
            flag=QCFlag.SATURATION,
            severity=QCSeverity.ERROR,
            message="Signal saturation detected",
            well_position="A1",
            value=65000.0,
            threshold=62258.0,
        )

        assert issue.flag == QCFlag.SATURATION
        assert issue.severity == QCSeverity.ERROR
        assert issue.well_position == "A1"


class TestQCReport:
    """Tests for QC report properties."""

    def test_well_report_properties(self):
        """Test well report properties."""
        report = WellQCReport(position="A1")

        assert not report.has_issues
        assert report.max_severity is None

        # Add an issue
        report.issues.append(QCIssue(
            flag=QCFlag.DRIFT,
            severity=QCSeverity.WARNING,
            message="Drift detected",
        ))

        assert report.has_issues
        assert report.max_severity == QCSeverity.WARNING

    def test_plate_report_counts(self):
        """Test plate report issue counts."""
        report = PlateQCReport()

        report.plate_issues.append(QCIssue(
            flag=QCFlag.MISSING_CONTROL,
            severity=QCSeverity.ERROR,
            message="Missing control",
        ))

        well_report = WellQCReport(position="A1")
        well_report.issues.append(QCIssue(
            flag=QCFlag.SATURATION,
            severity=QCSeverity.ERROR,
            message="Saturated",
        ))
        well_report.issues.append(QCIssue(
            flag=QCFlag.DRIFT,
            severity=QCSeverity.WARNING,
            message="Drift",
        ))
        report.well_reports["A1"] = well_report

        assert report.total_issues == 3
        assert report.error_count == 2
        assert report.warning_count == 1
