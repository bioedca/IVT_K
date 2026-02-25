"""
Quality control module for IVT Kinetics Analyzer.

Phase 3.8-3.9: QC Enhancement
- F7.2: Baseline drift detection
- F7.3: MAD-based outlier detection
- F7.4: Saturation detection
- F7.5: Pairing verification
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import numpy as np


class QCFlag(Enum):
    """Quality control flag types."""
    DRIFT = "drift"
    SATURATION = "saturation"
    OUTLIER = "outlier"
    LOW_SIGNAL = "low_signal"
    HIGH_CV = "high_cv"
    TEMPERATURE_DRIFT = "temperature_drift"
    MISSING_CONTROL = "missing_control"


class QCSeverity(Enum):
    """Severity level for QC issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class QCSettings:
    """Configurable QC settings per project."""
    # Outlier detection
    cv_threshold: float = 0.20  # Flag CV > 20%
    outlier_threshold: float = 3.0  # MAD multiplier

    # Signal quality
    saturation_threshold: float = 0.95  # 95% of detector max
    drift_threshold: float = 0.1  # Relative slope threshold
    min_baseline_points: int = 3  # Points for baseline estimate

    # Detector limits
    detector_max: float = 65535.0  # 16-bit detector max
    empty_well_threshold: float = 100.0  # RFU for empty well

    # Temperature
    temperature_drift_threshold: float = 1.0  # Celsius

    # Negative control
    neg_control_cv_threshold: float = 0.15  # Flag neg control CV > 15%
    snr_threshold: float = 10.0  # Signal-to-noise ratio threshold
    bsi_threshold: float = 0.15  # Background stability index threshold

    @classmethod
    def from_project(cls, project) -> "QCSettings":
        """Create QCSettings from a Project model instance."""
        return cls(
            cv_threshold=project.qc_cv_threshold,
            outlier_threshold=project.qc_outlier_threshold,
            saturation_threshold=project.qc_saturation_threshold,
            drift_threshold=project.qc_drift_threshold,
            empty_well_threshold=project.qc_empty_well_threshold,
            snr_threshold=project.qc_snr_threshold,
            neg_control_cv_threshold=getattr(project, 'qc_neg_cv_threshold', 0.15),
            bsi_threshold=project.qc_bsi_threshold,
        )


@dataclass
class QCIssue:
    """A single QC issue detected."""
    flag: QCFlag
    severity: QCSeverity
    message: str
    well_position: Optional[str] = None
    timepoint: Optional[float] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftResult:
    """Result of baseline drift detection."""
    has_drift: bool
    slope: float
    relative_slope: float  # Normalized by initial value
    intercept: float
    r_squared: float
    baseline_points: int


@dataclass
class SaturationResult:
    """Result of saturation detection."""
    is_saturated: bool
    max_value: float
    saturation_ratio: float
    saturated_timepoints: List[int]


@dataclass
class OutlierResult:
    """Result of outlier detection."""
    outlier_indices: List[int]
    outlier_values: List[float]
    median: float
    mad: float
    threshold_value: float


@dataclass
class WellQCReport:
    """QC report for a single well."""
    position: str
    issues: List[QCIssue] = field(default_factory=list)
    drift_result: Optional[DriftResult] = None
    saturation_result: Optional[SaturationResult] = None
    outlier_result: Optional[OutlierResult] = None

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def max_severity(self) -> Optional[QCSeverity]:
        if not self.issues:
            return None
        severity_order = [QCSeverity.ERROR, QCSeverity.WARNING, QCSeverity.INFO]
        for sev in severity_order:
            if any(issue.severity == sev for issue in self.issues):
                return sev
        return None


@dataclass
class PlateQCReport:
    """QC report for an entire plate."""
    plate_id: Optional[int] = None
    well_reports: Dict[str, WellQCReport] = field(default_factory=dict)
    plate_issues: List[QCIssue] = field(default_factory=list)
    settings: Optional[QCSettings] = None

    @property
    def total_issues(self) -> int:
        count = len(self.plate_issues)
        for report in self.well_reports.values():
            count += len(report.issues)
        return count

    @property
    def error_count(self) -> int:
        count = sum(1 for i in self.plate_issues if i.severity == QCSeverity.ERROR)
        for report in self.well_reports.values():
            count += sum(1 for i in report.issues if i.severity == QCSeverity.ERROR)
        return count

    @property
    def warning_count(self) -> int:
        count = sum(1 for i in self.plate_issues if i.severity == QCSeverity.WARNING)
        for report in self.well_reports.values():
            count += sum(1 for i in report.issues if i.severity == QCSeverity.WARNING)
        return count

    def get_flagged_wells(self, severity: Optional[QCSeverity] = None) -> List[str]:
        """Get list of wells with issues."""
        flagged = []
        for pos, report in self.well_reports.items():
            if report.has_issues:
                if severity is None or report.max_severity == severity:
                    flagged.append(pos)
        return flagged


class QualityControl:
    """
    Quality control engine for plate reader data.

    Implements QC checks as specified in PRD F7.2-F7.5:
    - Baseline drift detection
    - MAD-based outlier detection
    - Saturation detection
    - Control pairing verification
    """

    def __init__(self, settings: Optional[QCSettings] = None):
        self.settings = settings or QCSettings()

    def detect_baseline_drift(
        self,
        values: List[float],
        timepoints: Optional[List[float]] = None
    ) -> DriftResult:
        """
        Detect baseline drift in early timepoints (F7.2).

        Fits a line to the first N timepoints and checks if slope
        exceeds threshold relative to initial value.

        Args:
            values: Fluorescence values
            timepoints: Time values (optional, uses indices if None)

        Returns:
            DriftResult with drift analysis
        """
        n_points = min(self.settings.min_baseline_points, len(values))

        if n_points < 2:
            return DriftResult(
                has_drift=False,
                slope=0.0,
                relative_slope=0.0,
                intercept=values[0] if values else 0.0,
                r_squared=0.0,
                baseline_points=n_points
            )

        # Use first N points for baseline
        baseline_values = np.array(values[:n_points])

        if timepoints:
            baseline_time = np.array(timepoints[:n_points])
        else:
            baseline_time = np.arange(n_points, dtype=float)

        # Fit linear regression
        if np.std(baseline_time) == 0:
            return DriftResult(
                has_drift=False,
                slope=0.0,
                relative_slope=0.0,
                intercept=np.mean(baseline_values),
                r_squared=0.0,
                baseline_points=n_points
            )

        # Simple linear regression
        mean_x = np.mean(baseline_time)
        mean_y = np.mean(baseline_values)

        numerator = np.sum((baseline_time - mean_x) * (baseline_values - mean_y))
        denominator = np.sum((baseline_time - mean_x) ** 2)

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        intercept = mean_y - slope * mean_x

        # Calculate R-squared
        predicted = slope * baseline_time + intercept
        ss_res = np.sum((baseline_values - predicted) ** 2)
        ss_tot = np.sum((baseline_values - mean_y) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Calculate relative slope (normalized by initial value)
        initial_value = baseline_values[0] if baseline_values[0] != 0 else 1.0
        relative_slope = abs(slope * (baseline_time[-1] - baseline_time[0]) / initial_value)

        has_drift = relative_slope > self.settings.drift_threshold

        return DriftResult(
            has_drift=has_drift,
            slope=float(slope),
            relative_slope=float(relative_slope),
            intercept=float(intercept),
            r_squared=float(r_squared),
            baseline_points=n_points
        )

    def detect_saturation(
        self,
        values: List[float],
        detector_max: Optional[float] = None
    ) -> SaturationResult:
        """
        Detect signal saturation (F7.4).

        Checks if any values exceed threshold of detector maximum.
        Default threshold is 95% of 16-bit max (65535).

        Args:
            values: Fluorescence values
            detector_max: Maximum detector value (optional)

        Returns:
            SaturationResult with saturation analysis
        """
        if not values:
            return SaturationResult(
                is_saturated=False,
                max_value=0.0,
                saturation_ratio=0.0,
                saturated_timepoints=[]
            )

        det_max = detector_max or self.settings.detector_max
        threshold = det_max * self.settings.saturation_threshold

        max_value = max(values)
        saturation_ratio = max_value / det_max if det_max > 0 else 0.0

        saturated_timepoints = [
            i for i, v in enumerate(values)
            if v >= threshold
        ]

        is_saturated = len(saturated_timepoints) > 0

        return SaturationResult(
            is_saturated=is_saturated,
            max_value=max_value,
            saturation_ratio=saturation_ratio,
            saturated_timepoints=saturated_timepoints
        )

    def detect_outliers_mad(
        self,
        values: List[float]
    ) -> OutlierResult:
        """
        Detect outliers using Median Absolute Deviation (F7.3).

        MAD-based detection is robust to outliers unlike mean/SD.
        Flags values where |value - median| > threshold * 1.4826 * MAD

        The constant 1.4826 makes MAD consistent with SD for normal distributions.

        Args:
            values: Values to check for outliers (e.g., fit parameters)

        Returns:
            OutlierResult with outlier indices and statistics
        """
        if len(values) < 3:
            return OutlierResult(
                outlier_indices=[],
                outlier_values=[],
                median=np.median(values) if values else 0.0,
                mad=0.0,
                threshold_value=float('inf')
            )

        arr = np.array(values)
        median = np.median(arr)

        # Compute MAD (Median Absolute Deviation)
        mad = np.median(np.abs(arr - median))

        # MAD can be 0 if all values are the same
        if mad == 0:
            return OutlierResult(
                outlier_indices=[],
                outlier_values=[],
                median=float(median),
                mad=0.0,
                threshold_value=float('inf')
            )

        # Calculate threshold: k * 1.4826 * MAD
        # 1.4826 is the scale factor for consistency with SD
        robust_sd = 1.4826 * mad
        threshold_value = self.settings.outlier_threshold * robust_sd

        # Find outliers
        deviations = np.abs(arr - median)
        outlier_mask = deviations > threshold_value
        outlier_indices = np.where(outlier_mask)[0].tolist()
        outlier_values = arr[outlier_mask].tolist()

        return OutlierResult(
            outlier_indices=outlier_indices,
            outlier_values=outlier_values,
            median=float(median),
            mad=float(mad),
            threshold_value=float(threshold_value)
        )

    def detect_temperature_drift(
        self,
        temperatures: List[float],
        setpoint: Optional[float] = None
    ) -> Tuple[bool, List[int], float]:
        """
        Detect temperature drift during experiment.

        Args:
            temperatures: Temperature readings at each timepoint
            setpoint: Expected temperature setpoint

        Returns:
            Tuple of (has_drift, flagged_indices, max_deviation)
        """
        if not temperatures:
            return False, [], 0.0

        if setpoint is None:
            # Use first temperature as setpoint
            setpoint = temperatures[0]

        threshold = self.settings.temperature_drift_threshold
        flagged_indices = []
        max_deviation = 0.0

        for i, temp in enumerate(temperatures):
            deviation = abs(temp - setpoint)
            max_deviation = max(max_deviation, deviation)
            if deviation > threshold:
                flagged_indices.append(i)

        has_drift = len(flagged_indices) > 0

        return has_drift, flagged_indices, max_deviation

    def compute_cv(self, values: List[float]) -> float:
        """
        Compute coefficient of variation.

        Args:
            values: Replicate values

        Returns:
            CV as a decimal (not percentage)
        """
        if len(values) < 2:
            return 0.0

        arr = np.array(values)
        mean = np.mean(arr)

        if mean == 0:
            return 0.0

        std = np.std(arr, ddof=1)  # Sample standard deviation
        return float(std / abs(mean))

    def check_replicate_cv(
        self,
        replicate_values: Dict[str, float]
    ) -> Tuple[bool, float]:
        """
        Check if replicate CV exceeds threshold.

        Args:
            replicate_values: Dict mapping well position to parameter value

        Returns:
            Tuple of (exceeds_threshold, cv_value)
        """
        values = list(replicate_values.values())

        if len(values) < 2:
            return False, 0.0

        cv = self.compute_cv(values)
        exceeds = cv > self.settings.cv_threshold

        return exceeds, cv

    def verify_control_pairing(
        self,
        construct_wells: Dict[str, List[str]],
        control_wells: Dict[str, List[str]]
    ) -> List[QCIssue]:
        """
        Verify that control data exists for sample comparisons (F7.5).

        Args:
            construct_wells: Dict mapping construct ID to list of well positions
            control_wells: Dict mapping control type to list of well positions

        Returns:
            List of QC issues for missing controls
        """
        issues = []

        # Check for required control types
        required_controls = ["negative_control", "wildtype"]

        for control_type in required_controls:
            if control_type not in control_wells or not control_wells[control_type]:
                issues.append(QCIssue(
                    flag=QCFlag.MISSING_CONTROL,
                    severity=QCSeverity.ERROR,
                    message=f"Missing {control_type.replace('_', ' ')} wells",
                    details={"control_type": control_type}
                ))

        return issues

    def run_well_qc(
        self,
        position: str,
        values: List[float],
        timepoints: Optional[List[float]] = None,
        temperatures: Optional[List[float]] = None,
        temperature_setpoint: Optional[float] = None
    ) -> WellQCReport:
        """
        Run all QC checks on a single well.

        Args:
            position: Well position (e.g., "A1")
            values: Fluorescence values
            timepoints: Time values
            temperatures: Temperature readings
            temperature_setpoint: Expected temperature

        Returns:
            WellQCReport with all issues found
        """
        report = WellQCReport(position=position)

        if not values:
            report.issues.append(QCIssue(
                flag=QCFlag.LOW_SIGNAL,
                severity=QCSeverity.WARNING,
                message="No data values",
                well_position=position
            ))
            return report

        # Check baseline drift
        drift_result = self.detect_baseline_drift(values, timepoints)
        report.drift_result = drift_result

        if drift_result.has_drift:
            report.issues.append(QCIssue(
                flag=QCFlag.DRIFT,
                severity=QCSeverity.WARNING,
                message=f"Baseline drift detected (relative slope: {drift_result.relative_slope:.3f})",
                well_position=position,
                value=drift_result.relative_slope,
                threshold=self.settings.drift_threshold,
                details={"slope": drift_result.slope, "r_squared": drift_result.r_squared}
            ))

        # Check saturation
        saturation_result = self.detect_saturation(values)
        report.saturation_result = saturation_result

        if saturation_result.is_saturated:
            report.issues.append(QCIssue(
                flag=QCFlag.SATURATION,
                severity=QCSeverity.ERROR,
                message=f"Signal saturation detected ({saturation_result.saturation_ratio:.1%} of max)",
                well_position=position,
                value=saturation_result.max_value,
                threshold=self.settings.detector_max * self.settings.saturation_threshold,
                details={
                    "saturated_timepoints": saturation_result.saturated_timepoints,
                    "saturation_ratio": saturation_result.saturation_ratio
                }
            ))

        # Check for low signal (empty well)
        mean_signal = np.mean(values)
        if mean_signal < self.settings.empty_well_threshold:
            report.issues.append(QCIssue(
                flag=QCFlag.LOW_SIGNAL,
                severity=QCSeverity.INFO,
                message=f"Low signal (mean: {mean_signal:.1f} RFU)",
                well_position=position,
                value=mean_signal,
                threshold=self.settings.empty_well_threshold
            ))

        # Check temperature drift if data available
        if temperatures and len(temperatures) > 1:
            has_temp_drift, flagged_temps, max_deviation = self.detect_temperature_drift(
                temperatures, temperature_setpoint
            )

            if has_temp_drift:
                report.issues.append(QCIssue(
                    flag=QCFlag.TEMPERATURE_DRIFT,
                    severity=QCSeverity.WARNING,
                    message=f"Temperature drift detected (max deviation: {max_deviation:.2f}C)",
                    well_position=position,
                    value=max_deviation,
                    threshold=self.settings.temperature_drift_threshold,
                    details={"flagged_timepoints": flagged_temps}
                ))

        return report

    def run_plate_qc(
        self,
        well_data: Dict[str, List[float]],
        timepoints: Optional[List[float]] = None,
        temperatures: Optional[List[float]] = None,
        temperature_setpoint: Optional[float] = None,
        control_mapping: Optional[Dict[str, List[str]]] = None
    ) -> PlateQCReport:
        """
        Run QC checks on an entire plate.

        Args:
            well_data: Dict mapping well position to fluorescence values
            timepoints: Time values (same for all wells)
            temperatures: Temperature readings
            temperature_setpoint: Expected temperature
            control_mapping: Dict mapping control type to well positions

        Returns:
            PlateQCReport with all issues
        """
        report = PlateQCReport(settings=self.settings)

        # Run per-well QC
        for position, values in well_data.items():
            well_report = self.run_well_qc(
                position=position,
                values=values,
                timepoints=timepoints,
                temperatures=temperatures,
                temperature_setpoint=temperature_setpoint
            )
            report.well_reports[position] = well_report

        # Verify control pairing if mapping provided
        if control_mapping:
            construct_wells = {
                pos: [pos] for pos in well_data.keys()
                if pos not in sum(control_mapping.values(), [])
            }
            pairing_issues = self.verify_control_pairing(construct_wells, control_mapping)
            report.plate_issues.extend(pairing_issues)

        return report

    def check_replicate_outliers(
        self,
        replicate_values: Dict[str, float],
        parameter_name: str = "value"
    ) -> Tuple[OutlierResult, List[QCIssue]]:
        """
        Check for outliers among replicates of the same construct.

        Args:
            replicate_values: Dict mapping well position to parameter value
            parameter_name: Name of parameter being checked (for messages)

        Returns:
            Tuple of (OutlierResult, list of QC issues)
        """
        values = list(replicate_values.values())
        positions = list(replicate_values.keys())

        outlier_result = self.detect_outliers_mad(values)
        issues = []

        for idx in outlier_result.outlier_indices:
            pos = positions[idx]
            val = values[idx]
            issues.append(QCIssue(
                flag=QCFlag.OUTLIER,
                severity=QCSeverity.WARNING,
                message=f"Outlier {parameter_name} detected: {val:.4g} (median: {outlier_result.median:.4g})",
                well_position=pos,
                value=val,
                threshold=outlier_result.threshold_value,
                details={
                    "median": outlier_result.median,
                    "mad": outlier_result.mad,
                    "deviation": abs(val - outlier_result.median)
                }
            ))

        return outlier_result, issues
