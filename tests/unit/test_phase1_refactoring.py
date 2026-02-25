"""
Tests for Phase 1 Refactoring — Security & Correctness.

Tests for:
- 2.1: Error message sanitization (str(e) removal)
- 2.2: Division-by-zero guards and numerical utilities
- 2.3: datetime.utcnow() replacement verification
- 2.4: Database index verification
"""
import math
import pytest
from datetime import datetime, timezone, timedelta

from app.error_handler import (
    get_user_friendly_message,
    APP_ERROR_MESSAGES,
    create_error_alert,
    create_error_notification,
)
from app.utils.numerical import safe_divide, safe_log_ratio


class TestNumericalUtilities:
    """Tests for app/utils/numerical.py (Phase 1, Section 2.2)."""

    def test_safe_divide_normal(self):
        """Normal division works correctly."""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(1, 3) == pytest.approx(1 / 3)
        assert safe_divide(-6, 3) == -2.0

    def test_safe_divide_zero_denominator(self):
        """Division by zero returns default."""
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=float("inf")) == float("inf")
        assert safe_divide(0, 0) == 0.0

    def test_safe_divide_near_zero_denominator(self):
        """Very small denominators are treated as zero."""
        assert safe_divide(10, 1e-15) == 0.0
        assert safe_divide(10, 1e-11) == 0.0
        # Just above threshold should divide normally
        assert safe_divide(10, 1e-9) == pytest.approx(10 / 1e-9)

    def test_safe_divide_custom_threshold(self):
        """Custom min_denominator threshold works."""
        assert safe_divide(10, 0.5, min_denominator=1.0) == 0.0
        assert safe_divide(10, 1.5, min_denominator=1.0) == pytest.approx(10 / 1.5)

    def test_safe_divide_negative_denominator(self):
        """Negative denominators work correctly."""
        assert safe_divide(10, -2) == -5.0
        assert safe_divide(10, -1e-15) == 0.0  # Near-zero negative

    def test_safe_log_ratio_normal(self):
        """Normal log ratio computation works."""
        # log2(4/2) = log2(2) = 1.0
        assert safe_log_ratio(4, 2) == pytest.approx(1.0)
        # log2(1/1) = 0
        assert safe_log_ratio(1, 1) == 0.0
        # log2(8/1) = 3.0
        assert safe_log_ratio(8, 1) == pytest.approx(3.0)

    def test_safe_log_ratio_zero_inputs(self):
        """Zero inputs return default."""
        assert safe_log_ratio(0, 5) == 0.0
        assert safe_log_ratio(5, 0) == 0.0
        assert safe_log_ratio(0, 0) == 0.0

    def test_safe_log_ratio_negative_inputs(self):
        """Negative inputs return default."""
        assert safe_log_ratio(-1, 5) == 0.0
        assert safe_log_ratio(5, -1) == 0.0

    def test_safe_log_ratio_custom_base(self):
        """Custom log base works."""
        # log10(100/10) = log10(10) = 1.0
        result = safe_log_ratio(100, 10, base=10.0)
        assert result == pytest.approx(1.0)

    def test_safe_log_ratio_custom_default(self):
        """Custom default value works."""
        assert safe_log_ratio(0, 5, default=-999) == -999


class TestErrorMessageSanitization:
    """Tests for error message handling (Phase 1, Section 2.1)."""

    def test_known_app_errors_have_safe_messages(self):
        """All known app error types are mapped to safe messages."""
        expected_types = [
            "ProjectValidationError",
            "PlateLayoutValidationError",
            "ConstructValidationError",
            "SmartPlannerError",
            "FittingError",
            "ComparisonError",
            "HierarchicalAnalysisError",
            "UploadValidationError",
            "UploadProcessingError",
            "BioTekParseError",
        ]
        for error_type in expected_types:
            assert error_type in APP_ERROR_MESSAGES, (
                f"{error_type} should be in APP_ERROR_MESSAGES"
            )

    def test_generic_exception_gets_safe_message(self):
        """Generic exceptions get a safe fallback message."""
        exc = Exception("SQL integrity error: column users.id violated FK constraint")
        message = get_user_friendly_message(exc)
        # The safe message should NOT contain the SQL details
        assert "SQL" not in message
        assert "integrity" not in message
        assert "constraint" not in message
        assert "unexpected error" in message.lower() or "try again" in message.lower()

    def test_value_error_gets_safe_message(self):
        """ValueError gets a relevant safe message."""
        exc = ValueError("invalid literal for int(): 'abc'")
        message = get_user_friendly_message(exc)
        assert "invalid literal" not in message
        assert "input" in message.lower() or "data" in message.lower()

    def test_safe_message_no_internal_details(self):
        """Safe messages never contain stack traces or internal paths."""
        test_cases = [
            RuntimeError("/home/user/app/models/project.py line 42: AttributeError"),
            TypeError("unsupported operand type(s) for +: 'NoneType' and 'int'"),
            KeyError("some_internal_key"),
        ]
        for exc in test_cases:
            message = get_user_friendly_message(exc)
            assert "/home/" not in message
            assert "line " not in message
            assert "NoneType" not in message
            assert "some_internal_key" not in message

    def test_create_error_alert_component(self):
        """Error alert component is created correctly."""
        alert = create_error_alert("Something went wrong", title="Error")
        assert alert is not None

    def test_create_error_notification_component(self):
        """Error notification component is created correctly."""
        notification = create_error_notification("Something went wrong")
        assert notification is not None


class TestDatetimeReplacement:
    """Tests for datetime.utcnow() removal (Phase 1, Section 2.3)."""

    def test_no_utcnow_in_production_code(self):
        """Verify no datetime.utcnow() calls remain in production code."""
        import pathlib

        app_dir = pathlib.Path(__file__).parent.parent.parent / "app"
        scripts_dir = pathlib.Path(__file__).parent.parent.parent / "scripts"

        violations = []
        for directory in [app_dir, scripts_dir]:
            for py_file in directory.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8")
                if "datetime.utcnow()" in content:
                    violations.append(str(py_file))

        assert violations == [], (
            f"datetime.utcnow() found in production files: {violations}"
        )

    def test_timezone_aware_datetime_creation(self):
        """datetime.now(timezone.utc) creates timezone-aware datetimes."""
        now = datetime.now(timezone.utc)
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc


class TestDivisionByZeroGuards:
    """Tests for division-by-zero guards (Phase 1, Section 2.2)."""

    def test_comparison_ratio_uncertainty_zero_denominator(self):
        """_propagate_ratio_uncertainty handles zero denominator."""
        from app.analysis.comparison import PairedAnalysis

        calc = PairedAnalysis.__new__(PairedAnalysis)
        # Zero denominator should not raise
        ratio_se, log_ratio_se = calc._propagate_ratio_uncertainty(
            numerator=1.0,
            numerator_se=0.1,
            denominator=0.0,
            denominator_se=0.1,
        )
        assert ratio_se == 0.0
        assert log_ratio_se == 0.0

    def test_comparison_ratio_uncertainty_normal(self):
        """_propagate_ratio_uncertainty works with normal values."""
        from app.analysis.comparison import PairedAnalysis

        calc = PairedAnalysis.__new__(PairedAnalysis)
        ratio_se, log_ratio_se = calc._propagate_ratio_uncertainty(
            numerator=10.0,
            numerator_se=1.0,
            denominator=5.0,
            denominator_se=0.5,
        )
        assert ratio_se > 0
        assert log_ratio_se > 0


class TestDatabaseIndexes:
    """Tests for database index additions (Phase 1, Section 2.4)."""

    def test_model_columns_have_index_flag(self):
        """Verify index=True is set on model column definitions."""
        from app.models.plate_layout import WellAssignment
        from app.models.experiment import Well
        from app.models.analysis_version import HierarchicalResult
        from app.models.fit_result import FoldChange

        # Check WellAssignment.construct_id
        wa_col = WellAssignment.__table__.c.construct_id
        assert any(
            wa_col.name in [c.name for c in idx.columns]
            for idx in WellAssignment.__table__.indexes
        ) or wa_col.index, "WellAssignment.construct_id should be indexed"

        # Check Well.construct_id and Well.plate_id
        well_cols = Well.__table__.c
        assert well_cols.construct_id.index or any(
            "construct_id" in [c.name for c in idx.columns]
            for idx in Well.__table__.indexes
        ), "Well.construct_id should be indexed"
        assert well_cols.plate_id.index or any(
            "plate_id" in [c.name for c in idx.columns]
            for idx in Well.__table__.indexes
        ), "Well.plate_id should be indexed"

        # Check HierarchicalResult.construct_id
        hr_col = HierarchicalResult.__table__.c.construct_id
        assert hr_col.index or any(
            "construct_id" in [c.name for c in idx.columns]
            for idx in HierarchicalResult.__table__.indexes
        ), "HierarchicalResult.construct_id should be indexed"

        # Check FoldChange.test_well_id and control_well_id
        fc_cols = FoldChange.__table__.c
        assert fc_cols.test_well_id.index or any(
            "test_well_id" in [c.name for c in idx.columns]
            for idx in FoldChange.__table__.indexes
        ), "FoldChange.test_well_id should be indexed"
        assert fc_cols.control_well_id.index or any(
            "control_well_id" in [c.name for c in idx.columns]
            for idx in FoldChange.__table__.indexes
        ), "FoldChange.control_well_id should be indexed"

    def test_migration_file_exists(self):
        """Verify the index migration file exists."""
        import pathlib

        migration_dir = (
            pathlib.Path(__file__).parent.parent.parent / "alembic" / "versions"
        )
        migration_files = list(migration_dir.glob("b4f2a8c91d03_*.py"))
        assert len(migration_files) == 1, "Index migration file should exist"
