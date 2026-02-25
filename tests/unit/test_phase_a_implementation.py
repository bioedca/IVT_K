"""
Tests for Phase A: Foundation Alignment implementation.

Phase A Tasks:
1. Create help/ directory structure at project root
2. Create app/parsers/base_parser.py (abstract base class)
3. Create re-export modules:
   - app/analysis/mixed_effects.py
   - app/analysis/statistics.py
   - app/analysis/power_analysis.py
"""
import pytest
import json
import os
from pathlib import Path
from abc import ABC


# ============================================================================
# Task 1: Help Directory Structure Tests
# ============================================================================

class TestHelpDirectoryStructure:
    """Tests for help/ directory at project root (PRD Section 0.5)."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        # Navigate from tests/unit/ to project root
        return Path(__file__).parent.parent.parent

    def test_help_directory_exists(self, project_root):
        """T-A1.1: help/ directory exists at project root."""
        help_dir = project_root / "help"
        assert help_dir.exists(), "help/ directory should exist at project root"
        assert help_dir.is_dir(), "help/ should be a directory"

    def test_tooltips_json_exists(self, project_root):
        """T-A1.2: help/tooltips.json exists."""
        tooltips_path = project_root / "help" / "tooltips.json"
        assert tooltips_path.exists(), "help/tooltips.json should exist"

    def test_tooltips_json_is_valid(self, project_root):
        """T-A1.3: help/tooltips.json is valid JSON with correct structure."""
        tooltips_path = project_root / "help" / "tooltips.json"
        with open(tooltips_path) as f:
            data = json.load(f)

        # Should have tooltips key with definitions
        assert "tooltips" in data, "tooltips.json should have 'tooltips' key"
        assert isinstance(data["tooltips"], dict), "tooltips should be a dictionary"

        # Should contain key scientific terms
        expected_terms = ["cv_threshold", "vif", "bsi", "snr", "lod", "loq"]
        for term in expected_terms:
            assert term in data["tooltips"], f"tooltips should include '{term}'"

    def test_glossary_json_exists(self, project_root):
        """T-A1.4: help/glossary.json exists."""
        glossary_path = project_root / "help" / "glossary.json"
        assert glossary_path.exists(), "help/glossary.json should exist"

    def test_glossary_json_is_valid(self, project_root):
        """T-A1.5: help/glossary.json is valid JSON with correct structure."""
        glossary_path = project_root / "help" / "glossary.json"
        with open(glossary_path) as f:
            data = json.load(f)

        # Should have glossary entries
        assert "entries" in data or "glossary" in data, \
            "glossary.json should have 'entries' or 'glossary' key"

    def test_panels_directory_exists(self, project_root):
        """T-A1.6: help/panels/ directory exists."""
        panels_dir = project_root / "help" / "panels"
        assert panels_dir.exists(), "help/panels/ directory should exist"
        assert panels_dir.is_dir(), "help/panels/ should be a directory"

    def test_panel_files_exist(self, project_root):
        """T-A1.7: All required panel JSON files exist."""
        panels_dir = project_root / "help" / "panels"
        required_panels = [
            "plate_layout.json",
            "curve_fitting.json",
            "hierarchical_model.json",
            "power_analysis.json",
            "comparison_hierarchy.json"
        ]

        for panel_file in required_panels:
            panel_path = panels_dir / panel_file
            assert panel_path.exists(), f"help/panels/{panel_file} should exist"

    def test_panel_files_are_valid_json(self, project_root):
        """T-A1.8: All panel files are valid JSON."""
        panels_dir = project_root / "help" / "panels"

        for panel_file in panels_dir.glob("*.json"):
            with open(panel_file) as f:
                data = json.load(f)  # Should not raise
            assert isinstance(data, dict), f"{panel_file.name} should be a JSON object"


# ============================================================================
# Task 2: Base Parser Tests
# ============================================================================

class TestBaseParser:
    """Tests for app/parsers/base_parser.py (PRD Section 1.2)."""

    def test_base_parser_module_exists(self):
        """T-A2.1: base_parser.py module can be imported."""
        from app.parsers import base_parser
        assert base_parser is not None

    def test_base_parser_class_exists(self):
        """T-A2.2: BaseParser class exists and is abstract."""
        from app.parsers.base_parser import BaseParser
        assert BaseParser is not None
        assert issubclass(BaseParser, ABC), "BaseParser should be an ABC"

    def test_base_parser_has_required_abstract_methods(self):
        """T-A2.3: BaseParser has required abstract methods."""
        from app.parsers.base_parser import BaseParser

        # Check abstract methods exist
        abstract_methods = ['parse', 'validate', 'extract_metadata']
        for method_name in abstract_methods:
            assert hasattr(BaseParser, method_name), \
                f"BaseParser should have '{method_name}' method"

    def test_base_parser_has_required_properties(self):
        """T-A2.4: BaseParser has required abstract properties."""
        from app.parsers.base_parser import BaseParser

        # Check abstract properties
        required_properties = ['name', 'supported_extensions']
        for prop_name in required_properties:
            assert hasattr(BaseParser, prop_name), \
                f"BaseParser should have '{prop_name}' property"

    def test_base_parser_cannot_be_instantiated(self):
        """T-A2.5: BaseParser cannot be instantiated directly."""
        from app.parsers.base_parser import BaseParser

        with pytest.raises(TypeError):
            BaseParser()

    def test_biotek_parser_inherits_base_parser(self):
        """T-A2.6: BioTekParser inherits from BaseParser."""
        from app.parsers.base_parser import BaseParser
        from app.parsers.biotek_parser import BioTekParser

        assert issubclass(BioTekParser, BaseParser), \
            "BioTekParser should inherit from BaseParser"

    def test_base_parser_exported_from_package(self):
        """T-A2.7: BaseParser is exported from app.parsers package."""
        from app.parsers import BaseParser
        assert BaseParser is not None


# ============================================================================
# Task 3: Re-export Modules Tests
# ============================================================================

class TestMixedEffectsModule:
    """Tests for app/analysis/mixed_effects.py (PRD Section 1.2)."""

    def test_mixed_effects_module_exists(self):
        """T-A3.1: mixed_effects.py module can be imported."""
        from app.analysis import mixed_effects
        assert mixed_effects is not None

    def test_hierarchical_model_class_exists(self):
        """T-A3.2: HierarchicalModel factory class exists."""
        from app.analysis.mixed_effects import HierarchicalModel
        assert HierarchicalModel is not None

    def test_hierarchical_model_create_bayesian(self):
        """T-A3.3: HierarchicalModel.create() returns BayesianHierarchical."""
        from app.analysis.mixed_effects import HierarchicalModel
        from app.analysis.bayesian import BayesianHierarchical, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not available")

        model = HierarchicalModel.create(analysis_type="bayesian")
        assert isinstance(model, BayesianHierarchical)

    def test_hierarchical_model_create_frequentist(self):
        """T-A3.4: HierarchicalModel.create() returns FrequentistHierarchical."""
        from app.analysis.mixed_effects import HierarchicalModel
        from app.analysis.frequentist import FrequentistHierarchical, STATSMODELS_AVAILABLE

        if not STATSMODELS_AVAILABLE:
            pytest.skip("statsmodels not available")

        model = HierarchicalModel.create(analysis_type="frequentist")
        assert isinstance(model, FrequentistHierarchical)

    def test_hierarchical_model_invalid_type_raises(self):
        """T-A3.5: HierarchicalModel.create() raises for invalid type."""
        from app.analysis.mixed_effects import HierarchicalModel

        with pytest.raises(ValueError, match="Unknown analysis type"):
            HierarchicalModel.create(analysis_type="invalid")

    def test_mixed_effects_exports_bayesian_classes(self):
        """T-A3.6: mixed_effects exports BayesianHierarchical."""
        from app.analysis.mixed_effects import BayesianHierarchicalModel
        assert BayesianHierarchicalModel is not None

    def test_mixed_effects_exports_frequentist_classes(self):
        """T-A3.7: mixed_effects exports FrequentistMixedEffects."""
        from app.analysis.mixed_effects import FrequentistMixedEffects
        assert FrequentistMixedEffects is not None

    def test_mixed_effects_exported_from_analysis_package(self):
        """T-A3.8: mixed_effects classes exported from app.analysis."""
        from app.analysis import HierarchicalModel
        assert HierarchicalModel is not None


class TestStatisticsModule:
    """Tests for app/analysis/statistics.py (PRD Section 1.2)."""

    def test_statistics_module_exists(self):
        """T-A3.9: statistics.py module can be imported."""
        from app.analysis import statistics
        assert statistics is not None

    def test_statistics_exports_normality_tests(self):
        """T-A3.10: statistics exports normality test functions."""
        from app.analysis.statistics import shapiro_wilk_test, NormalityTestResult
        assert shapiro_wilk_test is not None
        assert NormalityTestResult is not None

    def test_statistics_exports_homoscedasticity_tests(self):
        """T-A3.11: statistics exports homoscedasticity test functions."""
        from app.analysis.statistics import breusch_pagan_test, levene_test
        assert breusch_pagan_test is not None
        assert levene_test is not None

    def test_statistics_exports_effect_size(self):
        """T-A3.12: statistics exports effect size functions."""
        from app.analysis.statistics import cohens_d, hedges_g, EffectSizeResult
        assert cohens_d is not None
        assert hedges_g is not None
        assert EffectSizeResult is not None

    def test_statistics_exports_multiple_comparisons(self):
        """T-A3.13: statistics exports multiple comparison corrections."""
        from app.analysis.statistics import (
            bonferroni_correction,
            benjamini_hochberg_correction,
            apply_multiple_comparison_correction
        )
        assert bonferroni_correction is not None
        assert benjamini_hochberg_correction is not None
        assert apply_multiple_comparison_correction is not None

    def test_statistics_exports_validation(self):
        """T-A3.14: statistics exports coverage/bias validation."""
        from app.analysis.statistics import (
            validate_coverage,
            validate_bias,
            CoverageValidationResult,
            BiasValidationResult
        )
        assert validate_coverage is not None
        assert validate_bias is not None
        assert CoverageValidationResult is not None
        assert BiasValidationResult is not None


class TestPowerAnalysisModule:
    """Tests for app/analysis/power_analysis.py (PRD Section 1.2)."""

    def test_power_analysis_module_exists(self):
        """T-A3.15: power_analysis.py module can be imported from analysis."""
        from app.analysis import power_analysis
        assert power_analysis is not None

    def test_power_analysis_exports_power_result(self):
        """T-A3.16: power_analysis exports PowerResult."""
        from app.analysis.power_analysis import PowerResult
        assert PowerResult is not None

    def test_power_analysis_exports_sample_size_result(self):
        """T-A3.17: power_analysis exports SampleSizeResult."""
        from app.analysis.power_analysis import SampleSizeResult
        assert SampleSizeResult is not None

    def test_power_analysis_exports_calculation_functions(self):
        """T-A3.18: power_analysis exports calculation functions."""
        from app.analysis.power_analysis import (
            calculate_power_for_fold_change,
            calculate_sample_size_for_power,
            calculate_sample_size_for_precision
        )
        assert calculate_power_for_fold_change is not None
        assert calculate_sample_size_for_power is not None
        assert calculate_sample_size_for_precision is not None

    def test_power_analysis_same_as_calculator(self):
        """T-A3.19: analysis.power_analysis has same exports as calculator."""
        from app.analysis import power_analysis as analysis_pa
        from app.calculator import power_analysis as calc_pa

        # Key exports should be available from both
        assert analysis_pa.PowerResult is calc_pa.PowerResult
        assert analysis_pa.calculate_power_for_fold_change is calc_pa.calculate_power_for_fold_change

    def test_power_analysis_exported_from_analysis_package(self):
        """T-A3.20: power_analysis classes exported from app.analysis."""
        from app.analysis import PowerResult, SampleSizeResult
        assert PowerResult is not None
        assert SampleSizeResult is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhaseAIntegration:
    """Integration tests verifying Phase A components work together."""

    def test_all_phase_a_imports_work(self):
        """T-A4.1: All Phase A modules can be imported together."""
        # Help system (directory check - not import)
        from pathlib import Path
        help_dir = Path(__file__).parent.parent.parent / "help"
        assert help_dir.exists()

        # Base parser
        from app.parsers import BaseParser

        # Mixed effects
        from app.analysis.mixed_effects import HierarchicalModel

        # Statistics
        from app.analysis.statistics import shapiro_wilk_test

        # Power analysis
        from app.analysis.power_analysis import calculate_power_for_fold_change

        # All imports successful
        assert True

    def test_biotek_parser_uses_base_parser(self):
        """T-A4.2: BioTekParser properly implements BaseParser interface."""
        from app.parsers import BioTekParser, BaseParser

        parser = BioTekParser()

        # Check it's a BaseParser
        assert isinstance(parser, BaseParser)

        # Check required properties are accessible
        assert hasattr(parser, 'name')
        assert hasattr(parser, 'supported_extensions')

        # Check property values
        assert parser.name == "BioTek Synergy HTX"
        assert '.txt' in parser.supported_extensions or '.xlsx' in parser.supported_extensions
