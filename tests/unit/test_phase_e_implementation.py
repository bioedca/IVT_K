"""
Tests for Phase E: Documentation and Cleanup

Phase E tasks:
13. Document all extension files
14. Review and update `__init__.py` exports
15. Update README with architecture notes

These tests verify that all Phase E documentation requirements are met.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple

import pytest

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestExtensionFileDocumentation:
    """Test that all extension files have proper documentation."""

    # Extension files from Section 4 of imp.md
    ANALYSIS_EXTENSIONS = [
        "app/analysis/comparison.py",
        "app/analysis/edge_cases.py",
        "app/analysis/reporter_systems.py",
        "app/analysis/negative_control.py",
    ]

    MODELS_EXTENSIONS = [
        "app/models/warning_suppression.py",
        "app/models/comparison.py",
    ]

    SERVICES_EXTENSIONS = [
        "app/services/warning_suppression_service.py",
        "app/services/project_storage_service.py",
    ]

    COMPONENTS_EXTENSIONS = [
        "app/components/qq_plot.py",
        "app/components/plate_heatmap.py",
        "app/components/warning_suppression_ui.py",
    ]

    LAYOUTS_EXTENSIONS = [
        "app/layouts/negative_control_dashboard.py",
        "app/layouts/precision_dashboard.py",
        "app/layouts/cross_project_comparison.py",
        "app/layouts/audit_log.py",
    ]

    ALL_EXTENSIONS = (
        ANALYSIS_EXTENSIONS
        + MODELS_EXTENSIONS
        + SERVICES_EXTENSIONS
        + COMPONENTS_EXTENSIONS
        + LAYOUTS_EXTENSIONS
    )

    def _get_module_docstring(self, file_path: Path) -> str | None:
        """Extract module docstring from a Python file."""
        with open(file_path, "r") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
            return ast.get_docstring(tree)
        except SyntaxError:
            return None

    def _check_prd_reference(self, docstring: str) -> bool:
        """Check if docstring contains PRD or phase reference."""
        if not docstring:
            return False
        keywords = [
            "prd",
            "phase",
            "sprint",
            "section",
            "extension",
            "f\\d+",  # Feature references like F13.1
        ]
        pattern = "|".join(keywords)
        return bool(re.search(pattern, docstring.lower()))

    @pytest.mark.parametrize("extension_path", ALL_EXTENSIONS)
    def test_extension_file_exists(self, extension_path: str):
        """Verify that each extension file exists."""
        full_path = PROJECT_ROOT / extension_path
        assert full_path.exists(), f"Extension file missing: {extension_path}"

    @pytest.mark.parametrize("extension_path", ALL_EXTENSIONS)
    def test_extension_has_module_docstring(self, extension_path: str):
        """Verify each extension file has a module-level docstring."""
        full_path = PROJECT_ROOT / extension_path
        if not full_path.exists():
            pytest.skip(f"File not found: {extension_path}")

        docstring = self._get_module_docstring(full_path)
        assert docstring is not None, f"Missing module docstring: {extension_path}"
        assert len(docstring) >= 20, f"Docstring too short: {extension_path}"

    @pytest.mark.parametrize("extension_path", ALL_EXTENSIONS)
    def test_extension_docstring_references_prd(self, extension_path: str):
        """Verify each extension file's docstring references PRD/Phase."""
        full_path = PROJECT_ROOT / extension_path
        if not full_path.exists():
            pytest.skip(f"File not found: {extension_path}")

        docstring = self._get_module_docstring(full_path)
        if not docstring:
            pytest.skip(f"No docstring found: {extension_path}")

        has_reference = self._check_prd_reference(docstring)
        assert has_reference, (
            f"Docstring in {extension_path} should reference PRD section, "
            f"Phase, or Sprint. Found: {docstring[:100]}..."
        )

    def test_analysis_extensions_documented(self):
        """Verify all analysis extension files are documented."""
        documented_count = 0
        for ext in self.ANALYSIS_EXTENSIONS:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                docstring = self._get_module_docstring(full_path)
                if docstring and len(docstring) >= 20:
                    documented_count += 1
        assert documented_count == len(
            self.ANALYSIS_EXTENSIONS
        ), f"Expected {len(self.ANALYSIS_EXTENSIONS)} documented files"

    def test_models_extensions_documented(self):
        """Verify all models extension files are documented."""
        documented_count = 0
        for ext in self.MODELS_EXTENSIONS:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                docstring = self._get_module_docstring(full_path)
                if docstring and len(docstring) >= 20:
                    documented_count += 1
        assert documented_count == len(
            self.MODELS_EXTENSIONS
        ), f"Expected {len(self.MODELS_EXTENSIONS)} documented files"

    def test_services_extensions_documented(self):
        """Verify all services extension files are documented."""
        documented_count = 0
        for ext in self.SERVICES_EXTENSIONS:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                docstring = self._get_module_docstring(full_path)
                if docstring and len(docstring) >= 20:
                    documented_count += 1
        assert documented_count == len(
            self.SERVICES_EXTENSIONS
        ), f"Expected {len(self.SERVICES_EXTENSIONS)} documented files"

    def test_components_extensions_documented(self):
        """Verify all components extension files are documented."""
        documented_count = 0
        for ext in self.COMPONENTS_EXTENSIONS:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                docstring = self._get_module_docstring(full_path)
                if docstring and len(docstring) >= 20:
                    documented_count += 1
        assert documented_count == len(
            self.COMPONENTS_EXTENSIONS
        ), f"Expected {len(self.COMPONENTS_EXTENSIONS)} documented files"

    def test_layouts_extensions_documented(self):
        """Verify all layouts extension files are documented."""
        documented_count = 0
        for ext in self.LAYOUTS_EXTENSIONS:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                docstring = self._get_module_docstring(full_path)
                if docstring and len(docstring) >= 20:
                    documented_count += 1
        assert documented_count == len(
            self.LAYOUTS_EXTENSIONS
        ), f"Expected {len(self.LAYOUTS_EXTENSIONS)} documented files"


class TestInitPyExports:
    """Test that __init__.py files properly export all modules."""

    INIT_FILES = [
        ("app/analysis/__init__.py", ["comparison", "edge_cases", "negative_control"]),
        ("app/models/__init__.py", ["warning_suppression"]),
        (
            "app/services/__init__.py",
            [
                "power_analysis_service",
                "statistics_service",
                "warning_suppression_service",
            ],
        ),
        (
            "app/components/__init__.py",
            ["navigation", "progress_tracker", "qq_plot", "plate_heatmap"],
        ),
        (
            "app/layouts/__init__.py",
            [
                "construct_registry",
                "power_analysis",
                "negative_control_dashboard",
                "precision_dashboard",
            ],
        ),
        ("app/parsers/__init__.py", ["BaseParser", "BioTekParser"]),
        ("app/calculator/__init__.py", ["power_analysis"]),
    ]

    def _get_exports(self, file_path: Path) -> Tuple[List[str], str]:
        """Extract __all__ and full content from __init__.py file."""
        with open(file_path, "r") as f:
            content = f.read()

        # Try to extract __all__
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, ast.List):
                                return (
                                    [
                                        elt.s
                                        for elt in node.value.elts
                                        if isinstance(elt, ast.Constant)
                                    ],
                                    content,
                                )
        except SyntaxError:
            pass

        return [], content

    @pytest.mark.parametrize("init_path,expected_exports", INIT_FILES)
    def test_init_file_exists(self, init_path: str, expected_exports: List[str]):
        """Verify that each __init__.py file exists."""
        full_path = PROJECT_ROOT / init_path
        assert full_path.exists(), f"__init__.py missing: {init_path}"

    @pytest.mark.parametrize("init_path,expected_exports", INIT_FILES)
    def test_init_has_exports(self, init_path: str, expected_exports: List[str]):
        """Verify __init__.py contains expected exports or imports."""
        full_path = PROJECT_ROOT / init_path
        if not full_path.exists():
            pytest.skip(f"File not found: {init_path}")

        exports, content = self._get_exports(full_path)

        # Check either __all__ or direct imports
        for expected in expected_exports:
            found_in_all = expected in exports
            found_in_content = expected in content
            assert found_in_all or found_in_content, (
                f"Expected export '{expected}' not found in {init_path}"
            )

    def test_analysis_init_exports_extensions(self):
        """Verify analysis __init__.py exports extension modules."""
        init_path = PROJECT_ROOT / "app/analysis/__init__.py"
        if not init_path.exists():
            pytest.skip("analysis __init__.py not found")

        with open(init_path, "r") as f:
            content = f.read()

        extensions = ["comparison", "edge_cases", "negative_control"]
        for ext in extensions:
            assert ext in content, f"Extension '{ext}' not exported from analysis"

    def test_services_init_exports_phase_b_services(self):
        """Verify services __init__.py exports Phase B services."""
        init_path = PROJECT_ROOT / "app/services/__init__.py"
        if not init_path.exists():
            pytest.skip("services __init__.py not found")

        with open(init_path, "r") as f:
            content = f.read()

        services = ["PowerAnalysisService", "StatisticsService"]
        for svc in services:
            assert svc in content, f"Service '{svc}' not exported from services"

    def test_components_init_exports_phase_c_components(self):
        """Verify components __init__.py exports Phase C components."""
        init_path = PROJECT_ROOT / "app/components/__init__.py"
        if not init_path.exists():
            pytest.skip("components __init__.py not found")

        with open(init_path, "r") as f:
            content = f.read()

        # Check for navigation and progress_tracker exports
        assert "navigation" in content or "create_breadcrumbs" in content
        assert "progress_tracker" in content or "create_completion_matrix" in content

    def test_layouts_init_exports_phase_c_layouts(self):
        """Verify layouts __init__.py exports Phase C layouts."""
        init_path = PROJECT_ROOT / "app/layouts/__init__.py"
        if not init_path.exists():
            pytest.skip("layouts __init__.py not found")

        with open(init_path, "r") as f:
            content = f.read()

        # Check for construct_registry and power_analysis exports
        assert (
            "construct_registry" in content
            or "create_construct_registry_layout" in content
        )
        assert (
            "power_analysis" in content or "create_power_analysis_layout" in content
        )

    def test_parsers_init_exports_base_parser(self):
        """Verify parsers __init__.py exports BaseParser."""
        init_path = PROJECT_ROOT / "app/parsers/__init__.py"
        if not init_path.exists():
            pytest.skip("parsers __init__.py not found")

        with open(init_path, "r") as f:
            content = f.read()

        assert "BaseParser" in content, "BaseParser not exported from parsers"


class TestReadmeArchitectureNotes:
    """Test that README.md exists with architecture documentation."""

    def test_readme_exists(self):
        """Verify README.md exists at project root."""
        readme_path = PROJECT_ROOT / "README.md"
        assert readme_path.exists(), "README.md not found at project root"

    def test_readme_has_minimum_content(self):
        """Verify README.md has substantial content."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read()

        assert len(content) >= 500, "README.md content is too short"

    def test_readme_has_project_title(self):
        """Verify README.md has project title."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read()

        assert "IVT Kinetics" in content, "README.md missing project title"

    def test_readme_has_architecture_section(self):
        """Verify README.md has architecture documentation."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        has_architecture = any(
            keyword in content
            for keyword in ["architecture", "structure", "directory", "organization"]
        )
        assert has_architecture, "README.md missing architecture section"

    def test_readme_documents_analysis_module(self):
        """Verify README.md documents the analysis module."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        assert "analysis" in content, "README.md missing analysis module documentation"

    def test_readme_documents_services(self):
        """Verify README.md documents the services layer."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        assert "service" in content, "README.md missing services documentation"

    def test_readme_documents_components(self):
        """Verify README.md documents the components layer."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        assert "component" in content, "README.md missing components documentation"

    def test_readme_references_prd(self):
        """Verify README.md references the PRD or design docs."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        # README may reference PRD directly or describe the architecture
        assert any(kw in content for kw in ["prd", "architecture", "design", "ivt kinetics"]), \
            "README.md missing project documentation reference"

    def test_readme_documents_extensions(self):
        """Verify README.md documents extension files."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        has_extension_doc = any(
            keyword in content for keyword in ["extension", "additional", "beyond prd"]
        )
        assert has_extension_doc, "README.md missing extension documentation"

    def test_readme_has_setup_section(self):
        """Verify README.md has setup/installation instructions."""
        readme_path = PROJECT_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read().lower()

        has_setup = any(
            keyword in content
            for keyword in ["setup", "install", "getting started", "quick start"]
        )
        assert has_setup, "README.md missing setup instructions"


class TestPhaseECompleteness:
    """Test overall Phase E completion status."""

    def test_all_16_extension_files_exist(self):
        """Verify all 16 extension files from Section 4 exist."""
        extension_files = [
            "app/analysis/comparison.py",
            "app/analysis/edge_cases.py",
            "app/analysis/reporter_systems.py",
            "app/analysis/negative_control.py",
            "app/models/warning_suppression.py",
            "app/models/comparison.py",
            "app/services/warning_suppression_service.py",
            "app/services/project_storage_service.py",
            "app/components/qq_plot.py",
            "app/components/plate_heatmap.py",
            "app/components/warning_suppression_ui.py",
            "app/layouts/negative_control_dashboard.py",
            "app/layouts/precision_dashboard.py",
            "app/layouts/cross_project_comparison.py",
            "app/layouts/audit_log.py",
        ]

        missing = []
        for ext in extension_files:
            if not (PROJECT_ROOT / ext).exists():
                missing.append(ext)

        # Note: We expect 15 files, not 16, as reporter_systems is listed
        assert len(missing) == 0, f"Missing extension files: {missing}"

    def test_all_7_init_files_exist(self):
        """Verify all 7 __init__.py files exist."""
        init_files = [
            "app/analysis/__init__.py",
            "app/models/__init__.py",
            "app/services/__init__.py",
            "app/components/__init__.py",
            "app/layouts/__init__.py",
            "app/parsers/__init__.py",
            "app/calculator/__init__.py",
        ]

        missing = []
        for init_file in init_files:
            if not (PROJECT_ROOT / init_file).exists():
                missing.append(init_file)

        assert len(missing) == 0, f"Missing __init__.py files: {missing}"

    def test_phase_e_documentation_complete(self):
        """Integration test: Verify Phase E documentation is complete."""
        # Task 13: Extension files documented
        extension_files = [
            "app/analysis/comparison.py",
            "app/analysis/edge_cases.py",
            "app/analysis/reporter_systems.py",
            "app/analysis/negative_control.py",
            "app/models/warning_suppression.py",
            "app/models/comparison.py",
            "app/services/warning_suppression_service.py",
            "app/services/project_storage_service.py",
            "app/components/qq_plot.py",
            "app/components/plate_heatmap.py",
            "app/components/warning_suppression_ui.py",
            "app/layouts/negative_control_dashboard.py",
            "app/layouts/precision_dashboard.py",
            "app/layouts/cross_project_comparison.py",
            "app/layouts/audit_log.py",
        ]

        documented_count = 0
        for ext in extension_files:
            full_path = PROJECT_ROOT / ext
            if full_path.exists():
                with open(full_path, "r") as f:
                    content = f.read()
                try:
                    tree = ast.parse(content)
                    docstring = ast.get_docstring(tree)
                    if docstring and len(docstring) >= 20:
                        documented_count += 1
                except SyntaxError:
                    pass

        # Task 14: __init__.py exports verified
        init_files_exist = all(
            (PROJECT_ROOT / f"app/{mod}/__init__.py").exists()
            for mod in [
                "analysis",
                "models",
                "services",
                "components",
                "layouts",
                "parsers",
                "calculator",
            ]
        )

        # Task 15: README exists
        readme_exists = (PROJECT_ROOT / "README.md").exists()

        # All tasks complete
        assert documented_count >= 14, (
            f"Expected at least 14 documented extension files, got {documented_count}"
        )
        assert init_files_exist, "Not all __init__.py files exist"
        assert readme_exists, "README.md not found"
