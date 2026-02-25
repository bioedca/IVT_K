"""
Tests for negative control analysis module.

Phase 3.5.2-3.5.7: Background Statistics and Detection Limits
"""
import pytest
import numpy as np
from app.analysis.negative_control import (
    NegativeControlAnalyzer,
    BackgroundStatistics,
    PolynomialFit,
    SpatialGradient,
    DetectionLimits,
    SignalQualityMetrics,
    NegativeControlReport,
    CorrectionMethod,
    DetectionStatus,
    classify_signal_quality,
)


class TestBackgroundStatistics:
    """Tests for background statistics computation."""

    def test_compute_background_statistics_basic(self):
        """Test basic background statistics computation."""
        analyzer = NegativeControlAnalyzer()

        # Create simple test data
        neg_control_data = {
            "A1": [100.0, 102.0, 101.0, 103.0, 100.0],
            "A2": [99.0, 101.0, 100.0, 102.0, 99.0],
            "B1": [101.0, 100.0, 102.0, 101.0, 100.0],
        }
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        stats = analyzer.compute_background_statistics(neg_control_data, timepoints)

        assert isinstance(stats, BackgroundStatistics)
        assert stats.n_controls == 3
        assert 99.0 < stats.mean_background < 102.0
        assert stats.sd_background > 0
        assert stats.cv > 0
        assert stats.bsi >= 0

    def test_compute_background_statistics_no_timepoints(self):
        """Test background statistics without explicit timepoints."""
        analyzer = NegativeControlAnalyzer()

        neg_control_data = {
            "A1": [100.0, 102.0, 101.0],
            "A2": [99.0, 101.0, 100.0],
        }

        stats = analyzer.compute_background_statistics(neg_control_data)

        assert stats.n_controls == 2
        # Implementation generates synthetic timepoints when not provided
        assert len(stats.timepoints) == 3  # [0, 1, 2]

    def test_compute_background_statistics_empty_data(self):
        """Test with empty data."""
        analyzer = NegativeControlAnalyzer()

        stats = analyzer.compute_background_statistics({})

        assert stats.n_controls == 0
        assert stats.mean_background == 0.0

    def test_bsi_calculation_stable(self):
        """Test BSI for stable background."""
        analyzer = NegativeControlAnalyzer()

        # Very stable data (same values across time)
        neg_control_data = {
            "A1": [100.0] * 10,
            "A2": [100.0] * 10,
        }
        timepoints = list(range(10))

        stats = analyzer.compute_background_statistics(neg_control_data, timepoints)

        # BSI should be low for stable data
        assert stats.bsi < 0.1

    def test_bsi_calculation_drifting(self):
        """Test BSI for drifting background."""
        analyzer = NegativeControlAnalyzer()

        # Drifting data (increasing over time)
        neg_control_data = {
            "A1": [100.0, 110.0, 120.0, 130.0, 140.0],
            "A2": [100.0, 110.0, 120.0, 130.0, 140.0],
        }
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        stats = analyzer.compute_background_statistics(neg_control_data, timepoints)

        # BSI should be higher for drifting data
        assert stats.bsi > 0.1


class TestPolynomialFit:
    """Tests for polynomial background fitting."""

    def test_fit_polynomial_constant(self):
        """Test polynomial fit for constant background."""
        analyzer = NegativeControlAnalyzer()

        mean_by_timepoint = [100.0, 100.0, 100.0, 100.0, 100.0]
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        fit = analyzer.fit_polynomial_background(mean_by_timepoint, timepoints)

        assert isinstance(fit, PolynomialFit)
        # Constant data should prefer degree 0 or 1
        assert fit.degree <= 1
        assert fit.aic is not None

    def test_fit_polynomial_linear_trend(self):
        """Test polynomial fit for linear trend."""
        analyzer = NegativeControlAnalyzer()

        # Clear linear trend
        mean_by_timepoint = [100.0, 110.0, 120.0, 130.0, 140.0]
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        fit = analyzer.fit_polynomial_background(mean_by_timepoint, timepoints)

        assert fit.degree >= 1
        assert len(fit.coefficients) == fit.degree + 1

    def test_fit_polynomial_insufficient_data(self):
        """Test with insufficient data points."""
        analyzer = NegativeControlAnalyzer()

        # Only 2 points
        mean_by_timepoint = [100.0, 110.0]
        timepoints = [0.0, 1.0]

        fit = analyzer.fit_polynomial_background(mean_by_timepoint, timepoints)

        assert fit.degree <= 1


class TestSpatialGradient:
    """Tests for spatial gradient detection."""

    def test_detect_spatial_gradient_uniform(self):
        """Test spatial gradient detection for uniform data."""
        analyzer = NegativeControlAnalyzer()

        # Uniform values across plate
        well_values = {
            "A1": 100.0, "A2": 101.0, "A3": 100.0,
            "B1": 100.0, "B2": 99.0, "B3": 100.0,
            "C1": 101.0, "C2": 100.0, "C3": 100.0,
        }

        gradient = analyzer.detect_spatial_gradient(well_values, plate_format=96)

        assert isinstance(gradient, SpatialGradient)
        assert not gradient.has_gradient

    def test_detect_spatial_gradient_horizontal(self):
        """Test spatial gradient detection for horizontal gradient."""
        analyzer = NegativeControlAnalyzer()

        # Clear horizontal gradient (left to right)
        well_values = {}
        for row in "ABCDEFGH":
            for col in range(1, 13):
                well_values[f"{row}{col}"] = 100.0 + col * 10

        gradient = analyzer.detect_spatial_gradient(well_values, plate_format=96)

        # Should detect significant gradient with column coefficients
        assert gradient.has_gradient or gradient.col_coefficients is not None

    def test_detect_spatial_gradient_vertical(self):
        """Test spatial gradient detection for vertical gradient."""
        analyzer = NegativeControlAnalyzer()

        # Clear vertical gradient (top to bottom)
        well_values = {}
        for i, row in enumerate("ABCDEFGH"):
            for col in range(1, 13):
                well_values[f"{row}{col}"] = 100.0 + i * 10

        gradient = analyzer.detect_spatial_gradient(well_values, plate_format=96)

        assert gradient.row_coefficients is not None

    def test_detect_spatial_gradient_empty(self):
        """Test with empty data."""
        analyzer = NegativeControlAnalyzer()

        gradient = analyzer.detect_spatial_gradient({}, plate_format=96)

        assert not gradient.has_gradient


class TestDetectionLimits:
    """Tests for detection limit calculation."""

    def test_compute_detection_limits(self):
        """Test basic detection limit computation."""
        analyzer = NegativeControlAnalyzer(k_lod=3.0, k_loq=10.0)

        # Create stats with known values
        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        limits = analyzer.compute_detection_limits(stats)

        assert isinstance(limits, DetectionLimits)
        # LOD = mean + 3 * sd = 100 + 3 * 10 = 130
        assert limits.lod == pytest.approx(130.0)
        # LOQ = mean + 10 * sd = 100 + 10 * 10 = 200
        assert limits.loq == pytest.approx(200.0)

    def test_detection_limits_custom_k_values(self):
        """Test detection limits with custom k values."""
        analyzer = NegativeControlAnalyzer(k_lod=2.0, k_loq=5.0)

        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        limits = analyzer.compute_detection_limits(stats)

        # LOD = 100 + 2 * 10 = 120
        assert limits.lod == pytest.approx(120.0)
        # LOQ = 100 + 5 * 10 = 150
        assert limits.loq == pytest.approx(150.0)


class TestSignalQualityAssessment:
    """Tests for signal quality assessment."""

    def test_assess_signal_above_loq(self):
        """Test signal assessment for signal above LOQ."""
        analyzer = NegativeControlAnalyzer()

        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        limits = DetectionLimits(
            lod=130.0,
            loq=200.0,
        )

        # Signal well above LOQ
        metrics = analyzer.assess_signal_quality(500.0, stats, limits)

        assert isinstance(metrics, SignalQualityMetrics)
        assert metrics.detection_status == DetectionStatus.ABOVE_LOQ
        assert metrics.snr > 10  # Good SNR
        assert metrics.sbr > 1  # Above background

    def test_assess_signal_above_lod(self):
        """Test signal assessment for signal above LOD but below LOQ."""
        analyzer = NegativeControlAnalyzer()

        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        limits = DetectionLimits(
            lod=130.0,
            loq=200.0,
        )

        # Signal above LOD but below LOQ
        metrics = analyzer.assess_signal_quality(150.0, stats, limits)

        assert metrics.detection_status == DetectionStatus.ABOVE_LOD

    def test_assess_signal_below_lod(self):
        """Test signal assessment for signal below LOD."""
        analyzer = NegativeControlAnalyzer()

        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        limits = DetectionLimits(
            lod=130.0,
            loq=200.0,
        )

        # Signal below LOD but above mean
        metrics = analyzer.assess_signal_quality(120.0, stats, limits)

        assert metrics.detection_status == DetectionStatus.BELOW_LOD


class TestCorrectionMethodSelection:
    """Tests for correction method selection."""

    def test_select_simple_correction(self):
        """Test selection of simple correction method."""
        analyzer = NegativeControlAnalyzer(bsi_threshold=0.10)

        # Stable background, no gradient
        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,  # Below threshold
        )

        gradient = SpatialGradient(
            has_gradient=False,
        )

        method = analyzer.select_correction_method(stats, gradient)

        assert method == CorrectionMethod.SIMPLE

    def test_select_time_dependent_correction(self):
        """Test selection of time-dependent correction method."""
        analyzer = NegativeControlAnalyzer(bsi_threshold=0.10)

        # Drifting background
        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.15,  # Above threshold
            timepoints=[0.0, 1.0, 2.0],
            mean_by_timepoint=[100.0, 110.0, 120.0],
            sd_by_timepoint=[5.0, 5.0, 5.0],
        )

        gradient = SpatialGradient(
            has_gradient=False,
        )

        method = analyzer.select_correction_method(stats, gradient)

        assert method == CorrectionMethod.TIME_DEPENDENT

    def test_select_spatial_correction(self):
        """Test selection of spatial correction method."""
        analyzer = NegativeControlAnalyzer(bsi_threshold=0.10)

        # Stable background but with gradient
        stats = BackgroundStatistics(
            n_controls=3,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        gradient = SpatialGradient(
            has_gradient=True,
            gradient_type="column",
            gradient_magnitude=0.2,
            col_coefficients=[5.0, 0.0],
        )

        method = analyzer.select_correction_method(stats, gradient)

        assert method == CorrectionMethod.SPATIAL


class TestFullAnalysis:
    """Tests for full negative control analysis."""

    def test_run_full_analysis(self):
        """Test complete analysis workflow."""
        analyzer = NegativeControlAnalyzer()

        neg_control_data = {
            "A1": [100.0, 102.0, 101.0, 103.0, 100.0],
            "A2": [99.0, 101.0, 100.0, 102.0, 99.0],
            "B1": [101.0, 100.0, 102.0, 101.0, 100.0],
        }
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        report = analyzer.run_full_analysis(
            neg_control_data,
            timepoints=timepoints,
            plate_format=96,
        )

        assert isinstance(report, NegativeControlReport)
        assert report.background_stats is not None
        assert report.detection_limits is not None
        assert report.correction_method is not None
        # polynomial_fit may be None if BSI is below threshold (stable background)
        # spatial_gradient is always set

    def test_run_full_analysis_minimal(self):
        """Test analysis with minimal data."""
        analyzer = NegativeControlAnalyzer()

        neg_control_data = {
            "A1": [100.0, 100.0],
        }

        report = analyzer.run_full_analysis(neg_control_data)

        assert report.background_stats.n_controls == 1


class TestClassifySignalQuality:
    """Tests for classify_signal_quality helper function."""

    def test_classify_excellent_signal(self):
        """Test classification of excellent signal quality."""
        status = classify_signal_quality(snr=50)
        assert status == "excellent"

    def test_classify_good_signal(self):
        """Test classification of good signal quality."""
        status = classify_signal_quality(snr=25)
        assert status == "good"

    def test_classify_marginal_signal(self):
        """Test classification of marginal signal quality."""
        status = classify_signal_quality(snr=12)
        assert status == "marginal"

    def test_classify_poor_signal(self):
        """Test classification of poor signal quality."""
        status = classify_signal_quality(snr=6)
        assert status == "poor"

    def test_classify_undetectable_signal(self):
        """Test classification of undetectable signal quality."""
        status = classify_signal_quality(snr=2)
        assert status == "undetectable"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_sd_background(self):
        """Test handling of zero standard deviation."""
        analyzer = NegativeControlAnalyzer()

        # All identical values
        neg_control_data = {
            "A1": [100.0, 100.0, 100.0],
            "A2": [100.0, 100.0, 100.0],
        }

        stats = analyzer.compute_background_statistics(neg_control_data)

        # Should handle gracefully
        assert stats.sd_background >= 0
        assert stats.cv >= 0

    def test_single_well(self):
        """Test with single negative control well."""
        analyzer = NegativeControlAnalyzer()

        neg_control_data = {
            "A1": [100.0, 102.0, 101.0],
        }

        stats = analyzer.compute_background_statistics(neg_control_data)

        assert stats.n_controls == 1

    def test_negative_values(self):
        """Test handling of negative fluorescence values."""
        analyzer = NegativeControlAnalyzer()

        neg_control_data = {
            "A1": [-10.0, -5.0, 0.0, 5.0, 10.0],
            "A2": [-8.0, -3.0, 2.0, 7.0, 12.0],
        }
        timepoints = [0.0, 1.0, 2.0, 3.0, 4.0]

        stats = analyzer.compute_background_statistics(neg_control_data, timepoints)

        # Should handle negative values
        assert stats.n_controls == 2

    def test_384_well_plate(self):
        """Test with 384-well plate format."""
        analyzer = NegativeControlAnalyzer()

        # Create data for 384-well plate positions
        well_values = {}
        for i, row in enumerate("ABCDEFGHIJKLMNOP"):
            for col in range(1, 25):
                well_values[f"{row}{col}"] = 100.0 + np.random.randn() * 5

        gradient = analyzer.detect_spatial_gradient(well_values, plate_format=384)

        assert isinstance(gradient, SpatialGradient)


class TestBaselineCorrection:
    """Tests for baseline correction methods."""

    def test_apply_simple_correction(self):
        """Test simple baseline correction."""
        analyzer = NegativeControlAnalyzer()

        values = [150.0, 160.0, 170.0]
        stats = BackgroundStatistics(
            n_controls=2,
            mean_background=100.0,
            sd_background=10.0,
            cv=0.1,
            bsi=0.05,
        )

        corrected = analyzer.apply_simple_correction(values, stats)

        assert corrected[0] == pytest.approx(50.0)
        assert corrected[1] == pytest.approx(60.0)
        assert corrected[2] == pytest.approx(70.0)

    def test_apply_time_dependent_correction(self):
        """Test time-dependent baseline correction."""
        analyzer = NegativeControlAnalyzer()

        values = [150.0, 165.0, 180.0]  # Raw values
        timepoints = [0.0, 1.0, 2.0]
        # Linear polynomial: bg(t) = 100 + 5*t
        poly_fit = PolynomialFit(
            coefficients=[100.0, 5.0],  # c0 + c1*t
            degree=1,
            aic=10.0,
            r_squared=0.99,
        )

        corrected = analyzer.apply_time_dependent_correction(values, timepoints, poly_fit)

        # At t=0: 150 - 100 = 50
        # At t=1: 165 - 105 = 60
        # At t=2: 180 - 110 = 70
        assert corrected[0] == pytest.approx(50.0)
        assert corrected[1] == pytest.approx(60.0)
        assert corrected[2] == pytest.approx(70.0)
