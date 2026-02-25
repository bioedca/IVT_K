"""
Tests for Package Validation Service.

Tests PRD Section 3.15.2 requirements (F15.11-F15.16):
- F15.11: Import package as new project (copy)
- F15.12: Re-run analysis with identical settings from manifest
- F15.13: Compare results within tolerance (relative 1e-4)
- F15.14: Generate comprehensive diff report on failure
- F15.15: Generate certificate of reproducibility on success
- F15.16: Strict version match required
"""
import pytest
import json
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.package_validation_service import (
    PackageValidationService,
    PackageValidationResult,
    PackageValidationError,
    VersionInfo,
    VersionCheck,
    ValidationProgress,
)
from app.services.validation_service import (
    ValidationService,
    ValidationResult,
    ValidationCertificate,
    DiffReport,
)
from app.services.publication_package_service import (
    PublicationPackageService,
    PublicationPackageConfig,
)


# ========== VersionInfo Tests ==========

class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_default_values(self):
        """Test default values for VersionInfo."""
        info = VersionInfo(version="1.0.0")

        assert info.version == "1.0.0"
        assert info.commit_hash is None
        assert info.python_version == ""
        assert info.platform_info == ""

    def test_to_dict(self):
        """Test VersionInfo to_dict method."""
        info = VersionInfo(
            version="1.0.0",
            commit_hash="abc123",
            python_version="3.11.5",
            platform_info="Linux x86_64",
        )

        d = info.to_dict()

        assert d["version"] == "1.0.0"
        assert d["commit_hash"] == "abc123"
        assert d["python_version"] == "3.11.5"
        assert d["platform"] == "Linux x86_64"


class TestVersionCheck:
    """Tests for VersionCheck dataclass."""

    def test_compatible_version(self):
        """Test compatible version check."""
        check = VersionCheck(
            compatible=True,
            expected_version="1.0.0",
            actual_version="1.0.0",
        )

        assert check.compatible is True
        assert check.error_message == ""

    def test_incompatible_version(self):
        """Test incompatible version check."""
        check = VersionCheck(
            compatible=False,
            error_message="Version mismatch",
            expected_version="1.0.0",
            actual_version="1.1.0",
        )

        assert check.compatible is False
        assert "mismatch" in check.error_message.lower()


class TestValidationProgress:
    """Tests for ValidationProgress dataclass."""

    def test_progress_fraction(self):
        """Test progress fraction calculation."""
        progress = ValidationProgress(
            stage="version_check",
            stage_number=2,
            total_stages=7,
            message="Checking version...",
            progress_percent=50.0,
        )

        assert progress.progress_fraction == 0.5

    def test_zero_progress(self):
        """Test zero progress."""
        progress = ValidationProgress(
            stage="extract_verify",
            stage_number=1,
            total_stages=7,
            message="Starting...",
            progress_percent=0.0,
        )

        assert progress.progress_fraction == 0.0


class TestPackageValidationResult:
    """Tests for PackageValidationResult dataclass."""

    def test_passed_result(self):
        """Test passed validation result."""
        result = PackageValidationResult(
            status="PASSED",
            imported_project_id=1,
            validation_duration_seconds=45.5,
        )

        assert result.status == "PASSED"
        assert result.error is None
        assert result.imported_project_id == 1

    def test_failed_result(self):
        """Test failed validation result."""
        result = PackageValidationResult(
            status="FAILED",
            error="Results do not match",
        )

        assert result.status == "FAILED"
        assert "not match" in result.error

    def test_to_dict(self):
        """Test PackageValidationResult to_dict method."""
        result = PackageValidationResult(
            status="PASSED",
            imported_project_id=1,
            validation_duration_seconds=45.5,
            comparison_summary={
                "total_parameters": 100,
                "matching_parameters": 100,
            },
        )

        d = result.to_dict()

        assert d["status"] == "PASSED"
        assert d["imported_project_id"] == 1
        assert d["validation_duration_seconds"] == 45.5
        assert d["comparison_summary"]["total_parameters"] == 100


# ========== PackageValidationService Tests ==========

class TestPackageValidationServiceVersionCheck:
    """Tests for version compatibility checking (F15.16)."""

    def test_get_software_version(self):
        """Test getting software version info."""
        info = PackageValidationService.get_software_version()

        assert info.version is not None
        assert info.python_version != ""
        assert info.platform_info != ""

    def test_version_compatibility_exact_match(self):
        """Test version check with exact match (F15.16)."""
        # Get current version
        current = PackageValidationService.get_software_version()

        manifest = {
            "software": {
                "version": current.version,
                "commit_hash": current.commit_hash or "",
            }
        }

        check = PackageValidationService._check_version_compatibility(manifest)

        assert check.compatible is True

    def test_version_compatibility_version_mismatch(self):
        """Test version check with version mismatch (F15.16)."""
        manifest = {
            "software": {
                "version": "99.99.99",  # Non-existent version
                "commit_hash": "",
            }
        }

        check = PackageValidationService._check_version_compatibility(manifest)

        assert check.compatible is False
        assert "VERSION MISMATCH" in check.error_message
        assert "99.99.99" in check.error_message

    def test_version_compatibility_commit_mismatch(self):
        """Test version check with commit hash mismatch (F15.16)."""
        current = PackageValidationService.get_software_version()

        manifest = {
            "software": {
                "version": current.version,
                "commit_hash": "abc123fake",
            }
        }

        # Only fails if we have a current commit hash
        check = PackageValidationService._check_version_compatibility(manifest)

        if current.commit_hash:
            assert check.compatible is False
        else:
            # If no current commit hash, version match is sufficient
            pass


class TestPackageValidationServiceExtraction:
    """Tests for package extraction and verification."""

    def test_extract_verify_missing_file(self):
        """Test extraction fails for missing file."""
        fake_path = Path("/nonexistent/package.zip")

        with pytest.raises(PackageValidationError, match="not found"):
            PackageValidationService._extract_and_verify(fake_path)

    def test_extract_verify_non_zip(self, tmp_path):
        """Test extraction fails for non-ZIP file."""
        # Create a non-ZIP file
        fake_file = tmp_path / "not_a_zip.zip"
        fake_file.write_text("This is not a ZIP file")

        with pytest.raises(PackageValidationError, match="Invalid ZIP"):
            PackageValidationService._extract_and_verify(fake_file)

    def test_extract_verify_missing_manifest(self, tmp_path):
        """Test extraction fails for missing manifest."""
        # Create a ZIP without manifest
        zip_path = tmp_path / "no_manifest.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("raw_data/test.txt", "test data")

        with pytest.raises(PackageValidationError, match="manifest.json"):
            PackageValidationService._extract_and_verify(zip_path)

    def test_extract_verify_valid_package(self):
        """Test extraction succeeds for valid package."""
        # Create a valid package structure using manual tempdir
        import shutil
        tmp_path = Path(tempfile.mkdtemp(prefix="test_pkg_"))

        try:
            zip_path = tmp_path / "valid_package.zip"

            manifest = {
                "manifest_version": "1.0",
                "software": {"version": "1.0.0"},
                "files": [],
            }

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(manifest))
                zf.writestr("raw_data/.gitkeep", "")
                zf.writestr("processed/.gitkeep", "")
                zf.writestr("metadata/.gitkeep", "")

            package_dir, loaded_manifest = PackageValidationService._extract_and_verify(zip_path)

            assert package_dir.exists()
            assert loaded_manifest["manifest_version"] == "1.0"

            # Cleanup extracted dir
            shutil.rmtree(package_dir.parent if "ivt_validation_" in str(package_dir) else package_dir, ignore_errors=True)
        finally:
            # Cleanup temp dir
            shutil.rmtree(tmp_path, ignore_errors=True)


class TestPackageValidationServiceComparison:
    """Tests for result comparison (F15.13)."""

    def test_tolerance_constant(self):
        """Test tolerance is 1e-4 as specified in PRD."""
        assert PackageValidationService.TOLERANCE == 1e-4

    def test_enhance_diff_report_with_failures(self):
        """Test diff report enhancement with failures (F15.14)."""
        # Create a diff report with failures
        failures = [
            ValidationResult(
                parameter="param1",
                expected=1.0,
                actual=1.01,
                relative_error=0.01,
                is_valid=False,
                tolerance=1e-4,
            ),
            ValidationResult(
                parameter="param2",
                expected=2.0,
                actual=2.001,
                relative_error=0.0005,
                is_valid=False,
                tolerance=1e-4,
            ),
        ]

        diff_report = DiffReport(
            generated_at=datetime.now(),
            package_id="test123",
            failed_validations=failures,
            summary="2 failures found",
        )

        # Enhance the report
        PackageValidationService._enhance_diff_report(
            diff_report,
            expected={},
            actual={},
        )

        # Check enhancement
        assert "Error Statistics" in diff_report.summary
        assert "Possible causes" in diff_report.summary


class TestPackageValidationServiceCertificate:
    """Tests for certificate generation (F15.15)."""

    def test_generate_certificate_json_structure(self):
        """Test certificate JSON has correct structure."""
        import shutil
        tmp_path = Path(tempfile.mkdtemp(prefix="test_cert_"))

        try:
            # Create a mock validation result
            certificate = ValidationCertificate(
                package_id="test123",
                validated_at=datetime.now(),
                is_valid=True,
                total_checks=100,
                passed_checks=100,
                failed_checks=0,
                results=[],
                software_version="1.0.0",
                validator_hash="abc123",
            )

            result = PackageValidationResult(
                status="PASSED",
                certificate=certificate,
            )

            # Create a mock package file
            package_path = tmp_path / "test_package.zip"
            with zipfile.ZipFile(package_path, "w") as zf:
                zf.writestr("manifest.json", "{}")

            # Generate certificate JSON
            cert_json = PackageValidationService.generate_certificate_json(
                result,
                package_path,
            )

            # Verify structure matches PRD spec
            assert cert_json["certificate_version"] == "1.0"
            assert cert_json["validation_status"] == "PASSED"
            assert "validated_at" in cert_json
            assert "package_info" in cert_json
            assert "validation_environment" in cert_json
            assert "validation_results" in cert_json
            assert "signature" in cert_json

            # Check validation_results structure
            vr = cert_json["validation_results"]
            assert vr["total_parameters_compared"] == 100
            assert vr["parameters_matching"] == 100
            assert vr["tolerance_used"] == 1e-4
            assert vr["data_hash_verified"] is True
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


# ========== ValidationService Integration Tests ==========

class TestValidationServiceScalarComparison:
    """Tests for scalar value validation."""

    def test_validate_scalar_within_tolerance(self):
        """Test scalar validation within 1e-4 tolerance."""
        result = ValidationService.validate_scalar(
            "test_param",
            expected=1.0,
            actual=1.00005,  # Within 1e-4
            tolerance=1e-4,
        )

        assert result.is_valid is True
        assert result.relative_error < 1e-4

    def test_validate_scalar_outside_tolerance(self):
        """Test scalar validation outside 1e-4 tolerance."""
        result = ValidationService.validate_scalar(
            "test_param",
            expected=1.0,
            actual=1.001,  # Outside 1e-4
            tolerance=1e-4,
        )

        assert result.is_valid is False
        assert result.relative_error > 1e-4

    def test_validate_scalar_zero_expected(self):
        """Test scalar validation with zero expected value."""
        # When expected is 0, we check absolute value
        result = ValidationService.validate_scalar(
            "test_param",
            expected=0.0,
            actual=1e-12,  # Very small
            tolerance=1e-4,
        )

        assert result.is_valid is True

    def test_validate_scalar_nan_values(self):
        """Test scalar validation with NaN values."""
        import math

        # Both NaN should be considered equal
        result = ValidationService.validate_scalar(
            "test_param",
            expected=float("nan"),
            actual=float("nan"),
            tolerance=1e-4,
        )

        assert result.is_valid is True

        # One NaN should fail
        result = ValidationService.validate_scalar(
            "test_param",
            expected=1.0,
            actual=float("nan"),
            tolerance=1e-4,
        )

        assert result.is_valid is False


class TestValidationServiceFittedParams:
    """Tests for fitted parameter validation."""

    def test_validate_fitted_parameters_match(self):
        """Test fitted parameter validation with matching values."""
        expected = [
            {"well_id": "A1", "k_obs": 0.1, "f_max": 100.0, "r_squared": 0.99},
            {"well_id": "A2", "k_obs": 0.2, "f_max": 200.0, "r_squared": 0.98},
        ]
        actual = [
            {"well_id": "A1", "k_obs": 0.1, "f_max": 100.0, "r_squared": 0.99},
            {"well_id": "A2", "k_obs": 0.2, "f_max": 200.0, "r_squared": 0.98},
        ]

        results = ValidationService.validate_fitted_parameters(
            expected, actual, tolerance=1e-4
        )

        # All should be valid
        assert all(r.is_valid for r in results)

    def test_validate_fitted_parameters_mismatch(self):
        """Test fitted parameter validation with mismatched values."""
        expected = [
            {"well_id": "A1", "k_obs": 0.1, "f_max": 100.0, "r_squared": 0.99},
        ]
        actual = [
            {"well_id": "A1", "k_obs": 0.11, "f_max": 100.0, "r_squared": 0.99},  # k_obs differs by 10%
        ]

        results = ValidationService.validate_fitted_parameters(
            expected, actual, tolerance=1e-4
        )

        # k_obs should fail
        k_obs_results = [r for r in results if "k_obs" in r.parameter]
        assert any(not r.is_valid for r in k_obs_results)


class TestValidationServiceCertificatePDF:
    """Tests for PDF certificate generation."""

    def test_generate_certificate_pdf_valid(self):
        """Test PDF generation for valid certificate."""
        certificate = ValidationCertificate(
            package_id="test123",
            validated_at=datetime.now(),
            is_valid=True,
            total_checks=100,
            passed_checks=100,
            failed_checks=0,
            results=[],
            software_version="1.0.0",
            validator_hash="abc123",
        )

        pdf_bytes = ValidationService.generate_certificate_pdf(certificate)

        # Should return bytes (either PDF or fallback text)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_generate_certificate_pdf_invalid(self):
        """Test PDF generation for invalid certificate."""
        failures = [
            ValidationResult(
                parameter="param1",
                expected=1.0,
                actual=1.1,
                relative_error=0.1,
                is_valid=False,
                tolerance=1e-4,
            ),
        ]

        certificate = ValidationCertificate(
            package_id="test123",
            validated_at=datetime.now(),
            is_valid=False,
            total_checks=100,
            passed_checks=99,
            failed_checks=1,
            results=failures,
            software_version="1.0.0",
            validator_hash="abc123",
        )

        pdf_bytes = ValidationService.generate_certificate_pdf(certificate)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


class TestValidationServiceDiffReport:
    """Tests for diff report generation (F15.14)."""

    def test_generate_diff_report_markdown(self):
        """Test diff report Markdown generation."""
        failures = [
            ValidationResult(
                parameter="param1",
                expected=1.0,
                actual=1.1,
                relative_error=0.1,
                is_valid=False,
                tolerance=1e-4,
                details="Error exceeds tolerance",
            ),
        ]

        certificate = ValidationCertificate(
            package_id="test123",
            validated_at=datetime.now(),
            is_valid=False,
            total_checks=100,
            passed_checks=99,
            failed_checks=1,
            results=failures,
            software_version="1.0.0",
            validator_hash="abc123",
        )

        diff_report = ValidationService.generate_diff_report(certificate)
        markdown = diff_report.to_markdown()

        assert "# Validation Diff Report" in markdown
        assert "param1" in markdown
        assert "1.0" in markdown or "1.00" in markdown
        assert "1.1" in markdown or "1.10" in markdown


# ========== Integration Test with Mock Database ==========

class TestPackageValidationIntegration:
    """Integration tests for package validation workflow."""

    def _create_mock_package(self):
        """Create a mock publication package for testing."""
        import shutil
        tmp_path = Path(tempfile.mkdtemp(prefix="test_integ_"))

        # Create package directory structure
        package_dir = tmp_path / "test_package"
        package_dir.mkdir()
        (package_dir / "raw_data").mkdir()
        (package_dir / "processed").mkdir()
        (package_dir / "metadata").mkdir()
        (package_dir / "mcmc_traces").mkdir()
        (package_dir / "audit").mkdir()

        # Create manifest
        current_version = PackageValidationService.get_software_version()
        manifest = {
            "manifest_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "package": {
                "title": "Test Package",
                "authors": ["Test Author"],
            },
            "software": {
                "version": current_version.version,
                "commit_hash": current_version.commit_hash or "",
            },
            "analysis_config": {
                "kinetic_model_type": "delayed_exponential",
                "meaningful_fc_threshold": 1.5,
            },
            "files": [],
        }
        (package_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create fitted parameters CSV
        params_csv = "well_id,k_obs,f_max,r_squared\nA1,0.1,100.0,0.99\nA2,0.2,200.0,0.98\n"
        (package_dir / "processed" / "fitted_parameters.csv").write_text(params_csv)

        # Add placeholder files to ensure directories are in ZIP
        (package_dir / "raw_data" / ".gitkeep").write_text("")
        (package_dir / "metadata" / ".gitkeep").write_text("")
        (package_dir / "mcmc_traces" / ".gitkeep").write_text("")
        (package_dir / "audit" / ".gitkeep").write_text("")

        # Create ZIP file
        zip_path = tmp_path / "test_package.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file_path in package_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(package_dir)
                    zf.write(file_path, arcname)

        return zip_path, tmp_path

    def test_validation_stages_constant(self):
        """Test that validation stages are defined correctly."""
        stages = PackageValidationService.STAGES

        assert "extract_verify" in stages
        assert "version_check" in stages
        assert "hash_verify" in stages
        assert "import_project" in stages
        assert "rerun_analysis" in stages
        assert "compare_results" in stages
        assert "generate_output" in stages
        assert len(stages) == 7

    def test_progress_callback_called(self):
        """Test that progress callback is called during validation."""
        import shutil
        mock_package, tmp_path = self._create_mock_package()

        try:
            progress_updates = []

            def progress_callback(progress: ValidationProgress):
                progress_updates.append(progress)

            # Mock the database-dependent parts and hash verification
            with patch.object(PublicationPackageService, 'validate_package_integrity') as mock_hash:
                with patch.object(PackageValidationService, '_import_publication_package') as mock_import:
                    with patch.object(PackageValidationService, '_rerun_analysis') as mock_rerun:
                        with patch.object(ValidationService, 'validate_package') as mock_validate:
                            # Setup mocks
                            mock_hash.return_value = (True, [])  # Hash verification passes

                            mock_project = MagicMock()
                            mock_project.id = 1
                            mock_project.name = "Test Project"
                            mock_import.return_value = mock_project

                            mock_rerun.return_value = {"fitted_params": [], "fold_changes": [], "convergence": {}}

                            mock_cert = ValidationCertificate(
                                package_id="test",
                                validated_at=datetime.now(),
                                is_valid=True,
                                total_checks=10,
                                passed_checks=10,
                                failed_checks=0,
                                results=[],
                                software_version="1.0.0",
                                validator_hash="abc",
                            )
                            mock_validate.return_value = mock_cert

                            # Run validation
                            result = PackageValidationService.validate_package(
                                mock_package,
                                username="test_user",
                                progress_callback=progress_callback,
                            )

            # Progress callback should have been called multiple times
            assert len(progress_updates) > 0

            # Check stage progression
            stages_seen = [p.stage for p in progress_updates]
            assert "extract_verify" in stages_seen
            assert "version_check" in stages_seen
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
