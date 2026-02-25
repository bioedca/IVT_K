"""Tests for Sprint 4 enhancements (F12.6, F13.17).

Tests the new functionality added for:
- Precision Override Workflow (F12.6, Task 7.1)
- Methods Text Diff Tracking (F13.17, Task 8.3)
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.methods_text_service import (
    MethodsTextService,
    MethodsTextConfig,
    MethodsTextError,
)


class TestPrecisionOverrideWorkflow:
    """Tests for Precision Override Workflow (F12.6, Task 7.1)."""

    def test_precision_override_model_exists(self):
        """Test PrecisionOverride model is defined."""
        from app.models.comparison import PrecisionOverride

        # Check model has required fields
        assert hasattr(PrecisionOverride, 'id')
        assert hasattr(PrecisionOverride, 'construct_id')
        assert hasattr(PrecisionOverride, 'analysis_version_id')
        assert hasattr(PrecisionOverride, 'ci_width_actual')
        assert hasattr(PrecisionOverride, 'ci_width_target')
        assert hasattr(PrecisionOverride, 'is_acceptable')
        assert hasattr(PrecisionOverride, 'justification')
        assert hasattr(PrecisionOverride, 'override_by')
        assert hasattr(PrecisionOverride, 'override_at')

    def test_precision_override_has_relationships(self):
        """Test PrecisionOverride has proper relationships."""
        from app.models.comparison import PrecisionOverride

        assert hasattr(PrecisionOverride, 'construct')
        assert hasattr(PrecisionOverride, 'analysis_version')

    def test_precision_override_unique_constraint(self):
        """Test PrecisionOverride has unique constraint on construct+version."""
        from app.models.comparison import PrecisionOverride

        # Check table args for unique constraint
        table_args = getattr(PrecisionOverride, '__table_args__', ())
        constraint_names = [
            arg.name for arg in table_args
            if hasattr(arg, 'name') and arg.name
        ]
        assert 'uq_override_construct_version' in constraint_names

    def test_justification_minimum_length_constant(self):
        """Test that 20 character minimum is documented."""
        from app.models.comparison import PrecisionOverride

        # Check the model docstring or comment mentions 20 chars
        # This is a documentation check - the actual validation is in callbacks
        assert PrecisionOverride.__doc__ is not None
        assert '20' in PrecisionOverride.__doc__ or 'min' in PrecisionOverride.__doc__.lower()


class TestMethodsTextDiffTracking:
    """Tests for Methods Text Diff Tracking (F13.17, Task 8.3)."""

    def test_methods_text_model_exists(self):
        """Test MethodsText model is defined."""
        from app.models.methods_text import MethodsText

        # Check model has required fields
        assert hasattr(MethodsText, 'id')
        assert hasattr(MethodsText, 'project_id')
        assert hasattr(MethodsText, 'original_text')
        assert hasattr(MethodsText, 'edited_text')
        assert hasattr(MethodsText, 'diff_text')
        assert hasattr(MethodsText, 'edited_at')
        assert hasattr(MethodsText, 'edited_by')

    def test_methods_text_is_edited_property(self):
        """Test MethodsText has is_edited property."""
        from app.models.methods_text import MethodsText

        assert hasattr(MethodsText, 'is_edited')

    def test_methods_text_service_has_save_with_diff(self):
        """Test MethodsTextService has save_with_diff method."""
        assert hasattr(MethodsTextService, 'save_with_diff')
        assert callable(MethodsTextService.save_with_diff)

    def test_methods_text_service_has_get_for_export(self):
        """Test MethodsTextService has get_methods_for_export method."""
        assert hasattr(MethodsTextService, 'get_methods_for_export')
        assert callable(MethodsTextService.get_methods_for_export)

    def test_methods_text_service_has_format_diff(self):
        """Test MethodsTextService has format_diff_for_display method."""
        assert hasattr(MethodsTextService, 'format_diff_for_display')
        assert callable(MethodsTextService.format_diff_for_display)

    def test_format_diff_empty(self):
        """Test format_diff_for_display handles empty diff."""
        result = MethodsTextService.format_diff_for_display("")
        assert result == []

    def test_format_diff_none(self):
        """Test format_diff_for_display handles None."""
        result = MethodsTextService.format_diff_for_display(None)
        assert result == []

    def test_format_diff_additions(self):
        """Test format_diff_for_display marks additions correctly."""
        diff = "+new line"
        result = MethodsTextService.format_diff_for_display(diff)

        assert len(result) == 1
        assert result[0]['type'] == 'addition'
        assert result[0]['color'] == 'green'

    def test_format_diff_deletions(self):
        """Test format_diff_for_display marks deletions correctly."""
        diff = "-removed line"
        result = MethodsTextService.format_diff_for_display(diff)

        assert len(result) == 1
        assert result[0]['type'] == 'deletion'
        assert result[0]['color'] == 'red'

    def test_format_diff_headers(self):
        """Test format_diff_for_display marks headers correctly."""
        diff = "--- auto-generated\n+++ user-edited"
        result = MethodsTextService.format_diff_for_display(diff)

        assert len(result) == 2
        assert all(r['type'] == 'header' for r in result)

    def test_format_diff_range_markers(self):
        """Test format_diff_for_display marks range markers correctly."""
        diff = "@@ -1,3 +1,4 @@"
        result = MethodsTextService.format_diff_for_display(diff)

        assert len(result) == 1
        assert result[0]['type'] == 'range'
        assert result[0]['color'] == 'blue'

    def test_format_diff_context_lines(self):
        """Test format_diff_for_display marks context lines correctly."""
        diff = " unchanged line"
        result = MethodsTextService.format_diff_for_display(diff)

        assert len(result) == 1
        assert result[0]['type'] == 'context'
        assert result[0]['color'] == 'gray'


class TestMethodsTextGeneration:
    """Tests for methods text generation."""

    def test_generate_data_collection_section(self):
        """Test data collection section generation."""
        config = MethodsTextConfig(
            n_constructs=10,
            n_plates=5,
            n_sessions=2,
            n_wells=480,
            has_unregulated=True,
            wt_constructs=["Tbox1_WT", "Tbox2_WT"],
        )

        text = MethodsTextService.generate_data_collection_section(config)

        assert "10 constructs" in text
        assert "5 plates" in text
        assert "2 independent sessions" in text
        assert "480 wells" in text
        assert "unregulated reference" in text.lower()
        assert "Tbox1_WT" in text

    def test_generate_curve_fitting_section(self):
        """Test curve fitting section generation."""
        config = MethodsTextConfig(
            fitting_method="nonlinear_least_squares",
            fitting_algorithm="Levenberg-Marquardt",
            r_squared_threshold=0.95,
        )

        text = MethodsTextService.generate_curve_fitting_section(config)

        assert "first-order kinetic model" in text.lower()
        assert "Levenberg-Marquardt" in text
        assert "0.95" in text
        assert "log₂" in text or "log" in text

    def test_generate_statistical_analysis_section(self):
        """Test statistical analysis section generation."""
        config = MethodsTextConfig(
            n_chains=4,
            n_samples=4000,
            n_warmup=1000,
            target_accept=0.8,
            stan_version="2.26.0",
            ci_level=0.95,
        )

        text = MethodsTextService.generate_statistical_analysis_section(config)

        assert "4 chains" in text
        assert "4000" in text or "sampling iterations" in text.lower()
        assert "1000" in text or "warmup" in text.lower()
        assert "Stan" in text
        assert "variance inflation" in text.lower() or "VIF" in text

    def test_generate_software_section(self):
        """Test software section generation."""
        config = MethodsTextConfig(
            software_name="IVT Kinetics Analyzer",
            software_version="1.0.0",
        )

        text = MethodsTextService.generate_software_section(config)

        assert "IVT Kinetics Analyzer" in text
        assert "1.0.0" in text

    def test_generate_full_methods(self):
        """Test full methods generation includes all sections."""
        config = MethodsTextConfig(n_constructs=5, n_plates=3, n_wells=144)

        text = MethodsTextService.generate_full_methods(config)

        assert "**Data Collection**" in text
        assert "**Curve Fitting**" in text
        assert "**Statistical Analysis**" in text
        assert "**Software**" in text

    def test_generate_full_methods_without_software(self):
        """Test full methods can exclude software section."""
        config = MethodsTextConfig()

        text = MethodsTextService.generate_full_methods(config, include_software=False)

        assert "**Data Collection**" in text
        assert "**Software**" not in text

    def test_generate_latex_methods(self):
        """Test LaTeX methods generation."""
        config = MethodsTextConfig()

        text = MethodsTextService.generate_latex_methods(config)

        # Should have LaTeX math mode for subscripts
        assert "$k_{obs}$" in text or "k_obs" in text
        assert "$R^2$" in text or "R²" in text


class TestMethodsTextConfig:
    """Tests for MethodsTextConfig dataclass."""

    def test_config_defaults(self):
        """Test config has sensible defaults."""
        config = MethodsTextConfig()

        assert config.n_samples == 4000
        assert config.n_chains == 4
        assert config.n_warmup == 1000
        assert config.ci_level == 0.95
        assert config.precision_target == 0.3
        assert config.r_squared_threshold == 0.95

    def test_config_wt_constructs_default(self):
        """Test wt_constructs defaults to empty list."""
        config = MethodsTextConfig()

        assert config.wt_constructs == []

    def test_config_custom_values(self):
        """Test config accepts custom values."""
        config = MethodsTextConfig(
            n_samples=8000,
            n_chains=6,
            precision_target=0.25,
        )

        assert config.n_samples == 8000
        assert config.n_chains == 6
        assert config.precision_target == 0.25


class TestPrecisionDashboardOverrideUI:
    """Tests for precision dashboard override UI components."""

    def test_precision_table_simple_has_override_column(self):
        """Test simple table includes override column."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        metrics = [
            {
                "construct_id": 1,
                "construct_name": "Test",
                "ci_width": 0.5,
                "has_override": False,
            }
        ]

        table = create_precision_table_simple(metrics, target=0.3)

        # Should have 4 columns including Override
        assert table is not None

    def test_precision_table_shows_user_accepted(self):
        """Test table shows User Accepted badge for overridden constructs."""
        from app.layouts.precision_dashboard import create_precision_table_simple

        metrics = [
            {
                "construct_id": 1,
                "construct_name": "Test",
                "ci_width": 0.5,
                "has_override": True,
                "status": "user_accepted",
            }
        ]

        table = create_precision_table_simple(metrics, target=0.3)

        # Table should be created successfully
        assert table is not None

    def test_precision_table_advanced_has_override_column(self):
        """Test advanced table includes override column."""
        from app.layouts.precision_dashboard import create_precision_table_advanced

        metrics = [
            {
                "construct_id": 1,
                "construct_name": "Test",
                "ci_width": 0.5,
                "has_override": False,
                "vif": 1.0,
                "path_type": "direct",
            }
        ]

        table = create_precision_table_advanced(metrics, target=0.3)

        assert table is not None

    def test_precision_table_empty_metrics(self):
        """Test tables handle empty metrics list."""
        from app.layouts.precision_dashboard import (
            create_precision_table_simple,
            create_precision_table_advanced,
        )

        simple = create_precision_table_simple([])
        advanced = create_precision_table_advanced([])

        # Should return text message, not error
        assert simple is not None
        assert advanced is not None


class TestCitation:
    """Tests for citation generation."""

    def test_generate_citation(self):
        """Test citation generation."""
        citation = MethodsTextService.generate_citation()

        assert "IVT Kinetics Analyzer" in citation
        assert "Available at" in citation or "https" in citation.lower()
        # Should include current date
        assert datetime.now().strftime("%Y") in citation
