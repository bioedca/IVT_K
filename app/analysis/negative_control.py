"""
Negative Control Analysis module.

Phase 3.5: Negative Control Processing
- F19.1: Background statistics (mean, SD, BSI)
- F19.2: Polynomial background fitting with AIC selection
- F19.3: Spatial gradient detection
- F19.4-F19.5: Signal quality metrics (SNR, SBR)
- F19.6-F19.9: Detection limits (LOD, LOQ)
- F19.10-F19.11: Baseline correction methods
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import numpy as np


class CorrectionMethod(Enum):
    """Baseline correction method types."""
    SIMPLE = "simple"
    TIME_DEPENDENT = "time_dependent"
    SPATIAL = "spatial"


class DetectionStatus(Enum):
    """Signal detection status relative to limits."""
    ABOVE_LOQ = "above_loq"
    ABOVE_LOD = "above_lod"
    BELOW_LOD = "below_lod"
    UNDETECTED = "undetected"


@dataclass
class BackgroundStatistics:
    """Background statistics from negative control wells."""
    mean_background: float
    sd_background: float
    n_controls: int
    cv: float  # Coefficient of variation
    bsi: float  # Background Stability Index
    timepoints: List[float] = field(default_factory=list)
    mean_by_timepoint: List[float] = field(default_factory=list)
    sd_by_timepoint: List[float] = field(default_factory=list)


@dataclass
class PolynomialFit:
    """Polynomial fit result for time-dependent correction."""
    coefficients: List[float]  # [c0, c1, c2, ...] for c0 + c1*t + c2*t^2 + ...
    degree: int
    aic: float
    r_squared: float
    residuals: List[float] = field(default_factory=list)


@dataclass
class SpatialGradient:
    """Spatial gradient analysis result."""
    has_gradient: bool
    gradient_type: Optional[str] = None  # "row", "column", "radial", "edge"
    gradient_magnitude: float = 0.0
    row_coefficients: Optional[List[float]] = None
    col_coefficients: Optional[List[float]] = None


@dataclass
class DetectionLimits:
    """Detection limit calculations."""
    lod: float  # Limit of Detection (mean + k_lod * sigma)
    loq: float  # Limit of Quantification (mean + k_loq * sigma)
    k_lod: float = 3.0
    k_loq: float = 10.0
    mean_background: float = 0.0
    sd_background: float = 0.0
    min_detectable_fold_change: float = 1.0


@dataclass
class SignalQualityMetrics:
    """Signal quality metrics for a well."""
    snr: float  # Signal-to-Noise Ratio
    sbr: float  # Signal-to-Background Ratio
    above_lod: bool
    above_loq: bool
    detection_status: DetectionStatus
    signal_level: float
    background_level: float


@dataclass
class NegativeControlReport:
    """Complete report for negative control analysis."""
    plate_id: Optional[int] = None
    background_stats: Optional[BackgroundStatistics] = None
    polynomial_fit: Optional[PolynomialFit] = None
    spatial_gradient: Optional[SpatialGradient] = None
    detection_limits: Optional[DetectionLimits] = None
    correction_method: CorrectionMethod = CorrectionMethod.SIMPLE
    warnings: List[str] = field(default_factory=list)


class NegativeControlAnalyzer:
    """
    Analyzer for negative control wells.

    Provides methods for:
    - Background statistics computation
    - Polynomial fitting for time-dependent correction
    - Spatial gradient detection
    - Detection limit calculation
    - Baseline correction
    """

    def __init__(
        self,
        k_lod: float = 3.0,
        k_loq: float = 10.0,
        bsi_threshold: float = 0.10,
        cv_threshold: float = 0.15,
        gradient_threshold: float = 0.10,
    ):
        """
        Initialize analyzer with configurable thresholds.

        Args:
            k_lod: Coverage factor for LOD (default 3.0)
            k_loq: Coverage factor for LOQ (default 10.0)
            bsi_threshold: BSI threshold for time-dependent correction
            cv_threshold: CV threshold for flagging high variability
            gradient_threshold: Threshold for spatial gradient detection
        """
        self.k_lod = k_lod
        self.k_loq = k_loq
        self.bsi_threshold = bsi_threshold
        self.cv_threshold = cv_threshold
        self.gradient_threshold = gradient_threshold

    def compute_background_statistics(
        self,
        negative_control_data: Dict[str, List[float]],
        timepoints: Optional[List[float]] = None,
    ) -> BackgroundStatistics:
        """
        Compute background statistics from negative control wells.

        Args:
            negative_control_data: Dict mapping well position to fluorescence values
            timepoints: Optional list of timepoints

        Returns:
            BackgroundStatistics with mean, SD, CV, and BSI
        """
        if not negative_control_data:
            return BackgroundStatistics(
                mean_background=0.0,
                sd_background=0.0,
                n_controls=0,
                cv=0.0,
                bsi=0.0,
            )

        n_controls = len(negative_control_data)
        all_values = list(negative_control_data.values())

        # Determine number of timepoints
        n_timepoints = max(len(v) for v in all_values) if all_values else 0

        if n_timepoints == 0:
            return BackgroundStatistics(
                mean_background=0.0,
                sd_background=0.0,
                n_controls=n_controls,
                cv=0.0,
                bsi=0.0,
            )

        # Compute mean and SD at each timepoint
        mean_by_timepoint = []
        sd_by_timepoint = []

        for t_idx in range(n_timepoints):
            values_at_t = []
            for well_values in all_values:
                if t_idx < len(well_values) and well_values[t_idx] is not None:
                    values_at_t.append(well_values[t_idx])

            if values_at_t:
                mean_by_timepoint.append(float(np.mean(values_at_t)))
                sd_by_timepoint.append(float(np.std(values_at_t, ddof=1)) if len(values_at_t) > 1 else 0.0)
            else:
                mean_by_timepoint.append(0.0)
                sd_by_timepoint.append(0.0)

        # Overall statistics
        overall_mean = float(np.mean(mean_by_timepoint))
        overall_sd = float(np.mean(sd_by_timepoint)) if sd_by_timepoint else 0.0

        # CV (Coefficient of Variation)
        cv = overall_sd / overall_mean if overall_mean > 0 else 0.0

        # BSI (Background Stability Index)
        # BSI measures temporal variation relative to mean
        if len(mean_by_timepoint) > 1:
            temporal_sd = float(np.std(mean_by_timepoint, ddof=1))
            bsi = temporal_sd / overall_mean if overall_mean > 0 else 0.0
        else:
            bsi = 0.0

        return BackgroundStatistics(
            mean_background=overall_mean,
            sd_background=overall_sd,
            n_controls=n_controls,
            cv=cv,
            bsi=bsi,
            timepoints=timepoints or list(range(n_timepoints)),
            mean_by_timepoint=mean_by_timepoint,
            sd_by_timepoint=sd_by_timepoint,
        )

    def fit_polynomial_background(
        self,
        mean_by_timepoint: List[float],
        timepoints: List[float],
        max_degree: int = 3,
    ) -> PolynomialFit:
        """
        Fit polynomial to background time series with AIC selection.

        Args:
            mean_by_timepoint: Mean background at each timepoint
            timepoints: Time values
            max_degree: Maximum polynomial degree to try

        Returns:
            PolynomialFit with best model by AIC
        """
        if len(mean_by_timepoint) < 3:
            # Not enough points for polynomial fit
            return PolynomialFit(
                coefficients=[np.mean(mean_by_timepoint) if mean_by_timepoint else 0.0],
                degree=0,
                aic=float('inf'),
                r_squared=0.0,
            )

        t = np.array(timepoints)
        y = np.array(mean_by_timepoint)
        n = len(y)

        best_fit = None
        best_aic = float('inf')

        for degree in range(max_degree + 1):
            if degree >= n:
                break

            # Fit polynomial
            try:
                coeffs = np.polyfit(t, y, degree)
                predicted = np.polyval(coeffs, t)
                residuals = y - predicted

                # Calculate metrics
                ss_res = np.sum(residuals ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

                # AIC calculation: AIC = n * ln(RSS/n) + 2k
                # where k = degree + 1 (number of parameters)
                k = degree + 1
                if ss_res > 0:
                    aic = n * np.log(ss_res / n) + 2 * k
                else:
                    aic = -float('inf')  # Perfect fit

                if aic < best_aic:
                    best_aic = aic
                    best_fit = PolynomialFit(
                        coefficients=coeffs.tolist()[::-1],  # Reverse to [c0, c1, c2...]
                        degree=degree,
                        aic=float(aic),
                        r_squared=float(r_squared),
                        residuals=residuals.tolist(),
                    )
            except np.linalg.LinAlgError:
                continue

        if best_fit is None:
            return PolynomialFit(
                coefficients=[np.mean(y)],
                degree=0,
                aic=float('inf'),
                r_squared=0.0,
            )

        return best_fit

    def detect_spatial_gradient(
        self,
        well_values: Dict[str, float],
        plate_format: int = 96,
    ) -> SpatialGradient:
        """
        Detect spatial gradients in negative control distribution.

        Args:
            well_values: Dict mapping well position (e.g., "A1") to mean value
            plate_format: Plate format (96 or 384)

        Returns:
            SpatialGradient analysis result
        """
        if len(well_values) < 3:
            return SpatialGradient(has_gradient=False)

        # Parse well positions
        rows = []
        cols = []
        values = []

        for pos, val in well_values.items():
            if val is None:
                continue
            row_letter = pos[0].upper()
            col_num = int(pos[1:])

            row_idx = ord(row_letter) - ord('A')
            col_idx = col_num - 1

            rows.append(row_idx)
            cols.append(col_idx)
            values.append(val)

        if len(values) < 3:
            return SpatialGradient(has_gradient=False)

        rows = np.array(rows)
        cols = np.array(cols)
        values = np.array(values)

        mean_val = np.mean(values)
        if mean_val == 0:
            return SpatialGradient(has_gradient=False)

        # Check row gradient
        try:
            row_coeffs = np.polyfit(rows, values, 1)
            row_slope = row_coeffs[0]
            row_gradient_magnitude = abs(row_slope * (rows.max() - rows.min())) / mean_val
        except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
            row_gradient_magnitude = 0.0
            row_coeffs = None

        # Check column gradient
        try:
            col_coeffs = np.polyfit(cols, values, 1)
            col_slope = col_coeffs[0]
            col_gradient_magnitude = abs(col_slope * (cols.max() - cols.min())) / mean_val
        except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
            col_gradient_magnitude = 0.0
            col_coeffs = None

        # Determine if gradient is significant
        max_gradient = max(row_gradient_magnitude, col_gradient_magnitude)
        has_gradient = max_gradient > self.gradient_threshold

        gradient_type = None
        if has_gradient:
            if row_gradient_magnitude > col_gradient_magnitude:
                gradient_type = "row"
            else:
                gradient_type = "column"

        return SpatialGradient(
            has_gradient=has_gradient,
            gradient_type=gradient_type,
            gradient_magnitude=max_gradient,
            row_coefficients=row_coeffs.tolist() if row_coeffs is not None else None,
            col_coefficients=col_coeffs.tolist() if col_coeffs is not None else None,
        )

    def compute_detection_limits(
        self,
        background_stats: BackgroundStatistics,
    ) -> DetectionLimits:
        """
        Compute LOD and LOQ from background statistics.

        LOD = mean + k_lod * sigma
        LOQ = mean + k_loq * sigma

        Args:
            background_stats: Background statistics

        Returns:
            DetectionLimits with LOD, LOQ, and min detectable FC
        """
        mean_bg = background_stats.mean_background
        sd_bg = background_stats.sd_background

        lod = mean_bg + self.k_lod * sd_bg
        loq = mean_bg + self.k_loq * sd_bg

        # Minimum detectable fold change (signal at LOD vs mean background)
        min_detectable_fc = lod / mean_bg if mean_bg > 0 else 1.0

        return DetectionLimits(
            lod=lod,
            loq=loq,
            k_lod=self.k_lod,
            k_loq=self.k_loq,
            mean_background=mean_bg,
            sd_background=sd_bg,
            min_detectable_fold_change=min_detectable_fc,
        )

    def assess_signal_quality(
        self,
        signal_value: float,
        background_stats: BackgroundStatistics,
        detection_limits: DetectionLimits,
    ) -> SignalQualityMetrics:
        """
        Assess signal quality relative to background.

        Args:
            signal_value: Signal value (e.g., F_max from curve fit)
            background_stats: Background statistics
            detection_limits: Detection limits

        Returns:
            SignalQualityMetrics with SNR, SBR, and detection status
        """
        mean_bg = background_stats.mean_background
        sd_bg = background_stats.sd_background

        # SNR: Signal-to-Noise Ratio
        snr = signal_value / sd_bg if sd_bg > 0 else float('inf')

        # SBR: Signal-to-Background Ratio
        sbr = signal_value / mean_bg if mean_bg > 0 else float('inf')

        # Detection status
        above_lod = signal_value > detection_limits.lod
        above_loq = signal_value > detection_limits.loq

        if above_loq:
            status = DetectionStatus.ABOVE_LOQ
        elif above_lod:
            status = DetectionStatus.ABOVE_LOD
        elif signal_value > mean_bg:
            status = DetectionStatus.BELOW_LOD
        else:
            status = DetectionStatus.UNDETECTED

        return SignalQualityMetrics(
            snr=snr,
            sbr=sbr,
            above_lod=above_lod,
            above_loq=above_loq,
            detection_status=status,
            signal_level=signal_value,
            background_level=mean_bg,
        )

    def select_correction_method(
        self,
        background_stats: BackgroundStatistics,
        spatial_gradient: SpatialGradient,
    ) -> CorrectionMethod:
        """
        Select appropriate baseline correction method.

        Args:
            background_stats: Background statistics
            spatial_gradient: Spatial gradient analysis

        Returns:
            Recommended CorrectionMethod
        """
        # Priority: Spatial > Time-dependent > Simple
        if spatial_gradient.has_gradient:
            return CorrectionMethod.SPATIAL

        if background_stats.bsi > self.bsi_threshold:
            return CorrectionMethod.TIME_DEPENDENT

        return CorrectionMethod.SIMPLE

    def apply_simple_correction(
        self,
        values: List[float],
        background_stats: BackgroundStatistics,
    ) -> List[float]:
        """
        Apply simple baseline correction (subtract mean background).

        Args:
            values: Raw fluorescence values
            background_stats: Background statistics

        Returns:
            Corrected values
        """
        mean_bg = background_stats.mean_background
        return [v - mean_bg if v is not None else None for v in values]

    def apply_time_dependent_correction(
        self,
        values: List[float],
        timepoints: List[float],
        polynomial_fit: PolynomialFit,
    ) -> List[float]:
        """
        Apply time-dependent baseline correction using polynomial fit.

        Args:
            values: Raw fluorescence values
            timepoints: Time values
            polynomial_fit: Polynomial fit for background

        Returns:
            Corrected values
        """
        corrected = []
        coeffs = polynomial_fit.coefficients[::-1]  # Reverse for np.polyval

        for i, (val, t) in enumerate(zip(values, timepoints)):
            if val is None:
                corrected.append(None)
            else:
                bg_at_t = np.polyval(coeffs, t)
                corrected.append(val - bg_at_t)

        return corrected

    def run_full_analysis(
        self,
        negative_control_data: Dict[str, List[float]],
        timepoints: Optional[List[float]] = None,
        well_positions: Optional[Dict[str, float]] = None,
        plate_format: int = 96,
    ) -> NegativeControlReport:
        """
        Run complete negative control analysis.

        Args:
            negative_control_data: Dict mapping well position to fluorescence values
            timepoints: Optional list of timepoints
            well_positions: Optional dict mapping well to mean value for spatial analysis
            plate_format: Plate format (96 or 384)

        Returns:
            Complete NegativeControlReport
        """
        report = NegativeControlReport()
        warnings = []

        # 1. Compute background statistics
        stats = self.compute_background_statistics(negative_control_data, timepoints)
        report.background_stats = stats

        if stats.n_controls < 2:
            warnings.append(f"Insufficient negative controls: {stats.n_controls} (minimum 2 required)")

        if stats.cv > self.cv_threshold:
            warnings.append(f"High CV in negative controls: {stats.cv:.1%} (threshold: {self.cv_threshold:.1%})")

        # 2. Fit polynomial if needed
        if stats.bsi > self.bsi_threshold and len(stats.mean_by_timepoint) >= 3:
            poly_fit = self.fit_polynomial_background(
                stats.mean_by_timepoint,
                stats.timepoints,
            )
            report.polynomial_fit = poly_fit

        # 3. Detect spatial gradient
        if well_positions:
            spatial = self.detect_spatial_gradient(well_positions, plate_format)
            report.spatial_gradient = spatial
            if spatial.has_gradient:
                warnings.append(f"Spatial gradient detected ({spatial.gradient_type}): {spatial.gradient_magnitude:.1%}")
        else:
            report.spatial_gradient = SpatialGradient(has_gradient=False)

        # 4. Compute detection limits
        detection_limits = self.compute_detection_limits(stats)
        report.detection_limits = detection_limits

        # 5. Select correction method
        report.correction_method = self.select_correction_method(stats, report.spatial_gradient)

        report.warnings = warnings

        return report


def classify_signal_quality(snr: float) -> str:
    """
    Classify signal quality based on SNR.

    Args:
        snr: Signal-to-noise ratio

    Returns:
        Quality classification string
    """
    if snr >= 50:
        return "excellent"
    elif snr >= 20:
        return "good"
    elif snr >= 10:
        return "marginal"
    elif snr >= 5:
        return "poor"
    else:
        return "undetectable"
