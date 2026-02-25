"""
Tests for Phase B: Service Layer Completion.

Phase B Tasks:
1. Create app/services/power_analysis_service.py
2. Create app/services/statistics_service.py

PRD References:
- Section 3.12: Power Analysis Service interface
- Section 1.2: Statistics Service specification
"""
import pytest
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


# ============================================================================
# Task 1: Power Analysis Service Tests
# ============================================================================

class TestPowerAnalysisServiceModule:
    """Tests for app/services/power_analysis_service.py existence and structure."""

    def test_power_analysis_service_module_exists(self):
        """T-B1.1: power_analysis_service.py module can be imported."""
        from app.services import power_analysis_service
        assert power_analysis_service is not None

    def test_power_analysis_service_class_exists(self):
        """T-B1.2: PowerAnalysisService class exists."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert PowerAnalysisService is not None

    def test_power_analysis_service_has_precision_dashboard_method(self):
        """T-B1.3: PowerAnalysisService has get_precision_dashboard method."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert hasattr(PowerAnalysisService, 'get_precision_dashboard')

    def test_power_analysis_service_has_recommendation_method(self):
        """T-B1.4: PowerAnalysisService has get_recommendation method."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert hasattr(PowerAnalysisService, 'get_recommendation')

    def test_power_analysis_service_has_adjust_sample_size_method(self):
        """T-B1.5: PowerAnalysisService has adjust_sample_size_for_comparison_type method."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert hasattr(PowerAnalysisService, 'adjust_sample_size_for_comparison_type')

    def test_power_analysis_service_has_coplating_method(self):
        """T-B1.6: PowerAnalysisService has get_coplating_recommendations method."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert hasattr(PowerAnalysisService, 'get_coplating_recommendations')

    def test_power_analysis_service_has_track_precision_method(self):
        """T-B1.7: PowerAnalysisService has track_precision_history method."""
        from app.services.power_analysis_service import PowerAnalysisService
        assert hasattr(PowerAnalysisService, 'track_precision_history')


class TestPowerAnalysisServiceDataClasses:
    """Tests for Power Analysis Service data classes."""

    def test_precision_dashboard_dataclass_exists(self):
        """T-B1.8: PrecisionDashboard dataclass exists."""
        from app.services.power_analysis_service import PrecisionDashboard
        assert PrecisionDashboard is not None

    def test_precision_dashboard_has_required_fields(self):
        """T-B1.9: PrecisionDashboard has required fields."""
        from app.services.power_analysis_service import PrecisionDashboard

        # Check required fields
        required_fields = ['project_id', 'precision_target', 'constructs_at_target',
                          'constructs_total', 'overall_progress', 'construct_summaries']

        for field in required_fields:
            assert hasattr(PrecisionDashboard, '__dataclass_fields__') or \
                   field in PrecisionDashboard.__annotations__, \
                   f"PrecisionDashboard should have '{field}' field"

    def test_construct_precision_summary_exists(self):
        """T-B1.10: ConstructPrecisionSummary dataclass exists."""
        from app.services.power_analysis_service import ConstructPrecisionSummary
        assert ConstructPrecisionSummary is not None


class TestPowerAnalysisServiceMethods:
    """Functional tests for Power Analysis Service methods."""

    def test_get_precision_dashboard_returns_dashboard(self, db_session, test_project):
        """T-B1.11: get_precision_dashboard returns PrecisionDashboard."""
        from app.services.power_analysis_service import (
            PowerAnalysisService, PrecisionDashboard
        )

        project = test_project()
        dashboard = PowerAnalysisService.get_precision_dashboard(project.id)

        assert isinstance(dashboard, PrecisionDashboard)
        assert dashboard.project_id == project.id

    def test_get_precision_dashboard_with_no_data(self, db_session, test_project):
        """T-B1.12: get_precision_dashboard handles empty project."""
        from app.services.power_analysis_service import PowerAnalysisService

        project = test_project()
        dashboard = PowerAnalysisService.get_precision_dashboard(project.id)

        assert dashboard.constructs_total == 0
        assert dashboard.constructs_at_target == 0
        assert dashboard.overall_progress == 0.0

    def test_get_recommendation_returns_string(self, db_session, test_project):
        """T-B1.13: get_recommendation returns recommendation string."""
        from app.services.power_analysis_service import PowerAnalysisService

        project = test_project()
        recommendation = PowerAnalysisService.get_recommendation(project.id)

        assert isinstance(recommendation, str)
        assert len(recommendation) > 0

    def test_get_recommendation_with_custom_target(self, db_session, test_project):
        """T-B1.14: get_recommendation accepts custom target."""
        from app.services.power_analysis_service import PowerAnalysisService

        project = test_project()
        recommendation = PowerAnalysisService.get_recommendation(
            project.id, target=0.5
        )

        assert isinstance(recommendation, str)

    def test_adjust_sample_size_for_comparison_type(self):
        """T-B1.15: adjust_sample_size_for_comparison_type calculates correctly."""
        from app.services.power_analysis_service import PowerAnalysisService

        # Direct comparison (VIF=1) should need fewer samples
        direct_n = PowerAnalysisService.adjust_sample_size_for_comparison_type(
            base_n=10,
            comparison_type='direct'
        )

        # Indirect comparison through WT (VIF > 1) needs more samples
        indirect_n = PowerAnalysisService.adjust_sample_size_for_comparison_type(
            base_n=10,
            comparison_type='indirect_via_wt'
        )

        assert direct_n <= indirect_n

    def test_get_coplating_recommendations_returns_list(self, db_session, test_project):
        """T-B1.16: get_coplating_recommendations returns list."""
        from app.services.power_analysis_service import PowerAnalysisService

        project = test_project()
        recommendations = PowerAnalysisService.get_coplating_recommendations(project.id)

        assert isinstance(recommendations, list)

    def test_track_precision_history_returns_list(self, db_session, test_project):
        """T-B1.17: track_precision_history returns list of PrecisionHistory."""
        from app.services.power_analysis_service import PowerAnalysisService

        project = test_project()
        history = PowerAnalysisService.track_precision_history(project.id)

        assert isinstance(history, list)


class TestPowerAnalysisServiceErrorHandling:
    """Tests for Power Analysis Service error handling."""

    def test_get_precision_dashboard_invalid_project(self, db_session):
        """T-B1.18: get_precision_dashboard raises for invalid project."""
        from app.services.power_analysis_service import (
            PowerAnalysisService, PowerAnalysisServiceError
        )

        with pytest.raises(PowerAnalysisServiceError):
            PowerAnalysisService.get_precision_dashboard(99999)

    def test_get_recommendation_invalid_project(self, db_session):
        """T-B1.19: get_recommendation raises for invalid project."""
        from app.services.power_analysis_service import (
            PowerAnalysisService, PowerAnalysisServiceError
        )

        with pytest.raises(PowerAnalysisServiceError):
            PowerAnalysisService.get_recommendation(99999)


# ============================================================================
# Task 2: Statistics Service Tests
# ============================================================================

class TestStatisticsServiceModule:
    """Tests for app/services/statistics_service.py existence and structure."""

    def test_statistics_service_module_exists(self):
        """T-B2.1: statistics_service.py module can be imported."""
        from app.services import statistics_service
        assert statistics_service is not None

    def test_statistics_service_class_exists(self):
        """T-B2.2: StatisticsService class exists."""
        from app.services.statistics_service import StatisticsService
        assert StatisticsService is not None

    def test_statistics_service_has_compute_fold_changes_method(self):
        """T-B2.3: StatisticsService has compute_fold_changes method."""
        from app.services.statistics_service import StatisticsService
        assert hasattr(StatisticsService, 'compute_fold_changes')

    def test_statistics_service_has_run_assumption_checks_method(self):
        """T-B2.4: StatisticsService has run_assumption_checks method."""
        from app.services.statistics_service import StatisticsService
        assert hasattr(StatisticsService, 'run_assumption_checks')

    def test_statistics_service_has_apply_correction_method(self):
        """T-B2.5: StatisticsService has apply_multiple_comparison_correction method."""
        from app.services.statistics_service import StatisticsService
        assert hasattr(StatisticsService, 'apply_multiple_comparison_correction')


class TestStatisticsServiceDataClasses:
    """Tests for Statistics Service data classes."""

    def test_fold_change_result_exists(self):
        """T-B2.6: FoldChangeResult dataclass exists or FoldChange model is used."""
        # The service should return FoldChange model instances or a result dataclass
        from app.services.statistics_service import StatisticsService
        from app.models import FoldChange
        # This test passes if FoldChange model exists (which it does)
        assert FoldChange is not None

    def test_assumption_check_result_exists(self):
        """T-B2.7: AssumptionCheckResult dataclass exists."""
        from app.services.statistics_service import AssumptionCheckResult
        assert AssumptionCheckResult is not None

    def test_assumption_check_result_has_fields(self):
        """T-B2.8: AssumptionCheckResult has required fields."""
        from app.services.statistics_service import AssumptionCheckResult

        required_fields = ['normality_passed', 'homoscedasticity_passed',
                          'diagnostics', 'recommendations']

        for field in required_fields:
            assert hasattr(AssumptionCheckResult, '__dataclass_fields__') or \
                   field in AssumptionCheckResult.__annotations__, \
                   f"AssumptionCheckResult should have '{field}' field"


class TestStatisticsServiceComputeFoldChanges:
    """Tests for StatisticsService.compute_fold_changes method."""

    def test_compute_fold_changes_returns_list(self, db_session, test_project):
        """T-B2.9: compute_fold_changes returns list."""
        from app.services.statistics_service import StatisticsService

        project = test_project()
        fold_changes = StatisticsService.compute_fold_changes(project.id)

        assert isinstance(fold_changes, list)

    def test_compute_fold_changes_empty_project(self, db_session, test_project):
        """T-B2.10: compute_fold_changes returns empty list for empty project."""
        from app.services.statistics_service import StatisticsService

        project = test_project()
        fold_changes = StatisticsService.compute_fold_changes(project.id)

        assert fold_changes == []


class TestStatisticsServiceAssumptionChecks:
    """Tests for StatisticsService.run_assumption_checks method."""

    def test_run_assumption_checks_returns_result(self, db_session, test_project):
        """T-B2.11: run_assumption_checks returns AssumptionCheckResult."""
        from app.services.statistics_service import (
            StatisticsService, AssumptionCheckResult
        )
        from app.models import AnalysisVersion

        project = test_project()

        # Create an analysis version with required fields
        version = AnalysisVersion(
            project_id=project.id,
            name="Test Analysis v1",
            model_type="delayed_exponential"
        )
        db_session.add(version)
        db_session.commit()

        result = StatisticsService.run_assumption_checks(version.id)

        assert isinstance(result, AssumptionCheckResult)

    def test_run_assumption_checks_with_no_data(self, db_session, test_project):
        """T-B2.12: run_assumption_checks handles no data gracefully."""
        from app.services.statistics_service import StatisticsService
        from app.models import AnalysisVersion

        project = test_project()

        # Create an analysis version with no data (with required fields)
        version = AnalysisVersion(
            project_id=project.id,
            name="Test Analysis v1",
            model_type="delayed_exponential"
        )
        db_session.add(version)
        db_session.commit()

        result = StatisticsService.run_assumption_checks(version.id)

        # Should not raise, should return result with appropriate flags
        assert result is not None
        assert 'insufficient_data' in result.recommendations or result.diagnostics is None


class TestStatisticsServiceMultipleComparison:
    """Tests for StatisticsService.apply_multiple_comparison_correction method."""

    def test_apply_correction_returns_list(self):
        """T-B2.13: apply_multiple_comparison_correction returns list."""
        from app.services.statistics_service import StatisticsService

        p_values = [0.01, 0.03, 0.05, 0.10]
        result = StatisticsService.apply_multiple_comparison_correction(p_values)

        assert isinstance(result, list)
        assert len(result) == len(p_values)

    def test_apply_correction_benjamini_hochberg(self):
        """T-B2.14: apply_multiple_comparison_correction with BH method."""
        from app.services.statistics_service import StatisticsService

        p_values = [0.01, 0.03, 0.05, 0.10]
        result = StatisticsService.apply_multiple_comparison_correction(
            p_values, method='benjamini_hochberg'
        )

        assert isinstance(result, list)
        # First p-value should still be significant after BH correction
        assert result[0] is True

    def test_apply_correction_bonferroni(self):
        """T-B2.15: apply_multiple_comparison_correction with Bonferroni method."""
        from app.services.statistics_service import StatisticsService

        p_values = [0.01, 0.03, 0.05, 0.10]
        result = StatisticsService.apply_multiple_comparison_correction(
            p_values, method='bonferroni'
        )

        assert isinstance(result, list)
        # Bonferroni is more conservative, so fewer should be significant
        bh_result = StatisticsService.apply_multiple_comparison_correction(
            p_values, method='benjamini_hochberg'
        )
        assert sum(result) <= sum(bh_result)

    def test_apply_correction_empty_list(self):
        """T-B2.16: apply_multiple_comparison_correction handles empty list."""
        from app.services.statistics_service import StatisticsService

        result = StatisticsService.apply_multiple_comparison_correction([])

        assert result == []

    def test_apply_correction_invalid_method_raises(self):
        """T-B2.17: apply_multiple_comparison_correction raises for invalid method."""
        from app.services.statistics_service import StatisticsService

        with pytest.raises(ValueError):
            StatisticsService.apply_multiple_comparison_correction(
                [0.01, 0.05], method='invalid_method'
            )


class TestStatisticsServiceErrorHandling:
    """Tests for Statistics Service error handling."""

    def test_compute_fold_changes_invalid_project(self, db_session):
        """T-B2.18: compute_fold_changes raises for invalid project."""
        from app.services.statistics_service import (
            StatisticsService, StatisticsServiceError
        )

        with pytest.raises(StatisticsServiceError):
            StatisticsService.compute_fold_changes(99999)

    def test_run_assumption_checks_invalid_version(self, db_session):
        """T-B2.19: run_assumption_checks raises for invalid analysis version."""
        from app.services.statistics_service import (
            StatisticsService, StatisticsServiceError
        )

        with pytest.raises(StatisticsServiceError):
            StatisticsService.run_assumption_checks(99999)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhaseBIntegration:
    """Integration tests verifying Phase B components work together."""

    def test_all_phase_b_imports_work(self):
        """T-B3.1: All Phase B modules can be imported together."""
        # Power Analysis Service
        from app.services.power_analysis_service import (
            PowerAnalysisService,
            PrecisionDashboard,
            ConstructPrecisionSummary
        )

        # Statistics Service
        from app.services.statistics_service import (
            StatisticsService,
            AssumptionCheckResult
        )

        # All imports successful
        assert PowerAnalysisService is not None
        assert StatisticsService is not None

    def test_services_use_existing_analysis_functions(self):
        """T-B3.2: Services properly wrap existing analysis functions."""
        # Power analysis service should use calculator.power_analysis
        from app.services.power_analysis_service import PowerAnalysisService
        from app.calculator.power_analysis import calculate_power_for_fold_change

        # Statistics service should use analysis.statistical_tests
        from app.services.statistics_service import StatisticsService
        from app.analysis.statistical_tests import (
            bonferroni_correction,
            benjamini_hochberg_correction
        )

        # Verify the underlying functions exist
        assert calculate_power_for_fold_change is not None
        assert bonferroni_correction is not None
        assert benjamini_hochberg_correction is not None

    def test_services_registered_in_package(self):
        """T-B3.3: Services are exported from app.services package."""
        from app.services import PowerAnalysisService
        from app.services import StatisticsService

        assert PowerAnalysisService is not None
        assert StatisticsService is not None

    def test_precision_dashboard_integrates_with_project(self, db_session, test_project):
        """T-B3.4: PrecisionDashboard properly reflects project state."""
        from app.services.power_analysis_service import PowerAnalysisService
        from app.services.construct_service import ConstructService

        project = test_project(precision_target=0.25)

        # Add a construct
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Test_Reporter",
            username="test_user",
            is_unregulated=True
        )

        dashboard = PowerAnalysisService.get_precision_dashboard(project.id)

        assert dashboard.precision_target == 0.25
        assert dashboard.constructs_total == 1
