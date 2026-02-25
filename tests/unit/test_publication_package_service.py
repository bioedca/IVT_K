"""
Tests for Publication Package Service.

Tests the PublicationPackageService which handles generation of reproducible
publication packages with raw data preservation, processed results,
MCMC traces, audit logs, reproducibility manifests, and DataCite metadata.
"""
import hashlib
import json
import shutil
import tempfile
import pytest
from datetime import datetime
from pathlib import Path

from app.services.publication_package_service import (
    PublicationPackageService,
    PublicationPackageConfig,
    FileHash,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for tests that need filesystem access."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ========== PublicationPackageConfig Tests ==========


class TestPublicationPackageConfig:
    """Tests for PublicationPackageConfig dataclass."""

    def test_default_values(self):
        """Test all default values are correct."""
        config = PublicationPackageConfig()

        assert config.title == ""
        assert config.authors == []
        assert config.description == ""
        assert config.keywords == []
        assert config.doi is None
        assert config.license == "CC-BY-4.0"
        assert config.include_raw_data is True
        assert config.include_mcmc_traces is True
        assert config.include_figures is True
        assert config.include_methods is True
        assert config.include_audit_log is True
        assert config.figure_format == "png"
        assert config.figure_dpi == 300
        assert config.include_manifest is True
        assert config.include_software_config is True

    def test_custom_values(self):
        """Test custom configuration values are stored correctly."""
        config = PublicationPackageConfig(
            title="My Study",
            authors=["Alice", "Bob"],
            description="A kinetics study",
            keywords=["IVT", "kinetics"],
            doi="10.1234/example",
            license="MIT",
        )

        assert config.title == "My Study"
        assert config.authors == ["Alice", "Bob"]
        assert config.description == "A kinetics study"
        assert config.keywords == ["IVT", "kinetics"]
        assert config.doi == "10.1234/example"
        assert config.license == "MIT"

    def test_include_flags(self):
        """Test all include flags can be toggled."""
        config = PublicationPackageConfig(
            include_raw_data=False,
            include_mcmc_traces=False,
            include_figures=False,
            include_methods=False,
            include_audit_log=False,
            include_manifest=False,
            include_software_config=False,
        )

        assert config.include_raw_data is False
        assert config.include_mcmc_traces is False
        assert config.include_figures is False
        assert config.include_methods is False
        assert config.include_audit_log is False
        assert config.include_manifest is False
        assert config.include_software_config is False

    def test_figure_format_options(self):
        """Test figure format and dpi fields accept custom values."""
        config = PublicationPackageConfig(
            figure_format="svg",
            figure_dpi=600,
        )

        assert config.figure_format == "svg"
        assert config.figure_dpi == 600


# ========== FileHash Tests ==========


class TestFileHash:
    """Tests for FileHash dataclass."""

    def test_file_hash_creation(self):
        """Test basic FileHash creation."""
        fh = FileHash(
            filename="data.csv",
            sha256="abc123def456",
            size_bytes=1024,
            content_type="text/csv",
        )

        assert fh.filename == "data.csv"
        assert fh.sha256 == "abc123def456"
        assert fh.size_bytes == 1024
        assert fh.content_type == "text/csv"

    def test_file_hash_fields(self):
        """Test all FileHash fields are accessible and independent."""
        fh1 = FileHash(
            filename="a.json",
            sha256="hash_a",
            size_bytes=100,
            content_type="application/json",
        )
        fh2 = FileHash(
            filename="b.png",
            sha256="hash_b",
            size_bytes=200,
            content_type="image/png",
        )

        assert fh1.filename != fh2.filename
        assert fh1.sha256 != fh2.sha256
        assert fh1.size_bytes != fh2.size_bytes
        assert fh1.content_type != fh2.content_type


# ========== generate_package_filename Tests ==========


class TestGeneratePackageFilename:
    """Tests for PublicationPackageService.generate_package_filename."""

    def test_basic_filename(self):
        """Test standard filename format: {slug}_{YYYYMMDD}_v{version}.zip."""
        filename = PublicationPackageService.generate_package_filename(
            "My Project", version=1
        )

        date_str = datetime.now().strftime("%Y%m%d")
        assert filename == f"my_project_{date_str}_v1.zip"

    def test_special_characters(self):
        """Test special characters in project name are replaced with underscores."""
        filename = PublicationPackageService.generate_package_filename(
            "Project #1 (test) & more!", version=1
        )

        date_str = datetime.now().strftime("%Y%m%d")
        # Special chars become underscores, consecutive underscores merged by regex,
        # leading/trailing underscores stripped
        assert filename.endswith(".zip")
        assert "#" not in filename
        assert "(" not in filename
        assert "&" not in filename
        assert "!" not in filename
        # The slug should be lowercase alphanumeric with underscores
        slug_part = filename.split(f"_{date_str}")[0]
        assert all(c.isalnum() or c == "_" for c in slug_part)

    def test_empty_project_name(self):
        """Test empty project name falls back to 'package'."""
        filename = PublicationPackageService.generate_package_filename(
            "", version=1
        )

        date_str = datetime.now().strftime("%Y%m%d")
        assert filename == f"package_{date_str}_v1.zip"

    def test_version_number(self):
        """Test different version numbers appear in filename."""
        filename_v1 = PublicationPackageService.generate_package_filename(
            "Test", version=1
        )
        filename_v5 = PublicationPackageService.generate_package_filename(
            "Test", version=5
        )

        assert "_v1.zip" in filename_v1
        assert "_v5.zip" in filename_v5

    def test_filename_has_date(self):
        """Test filename contains current date in YYYYMMDD format."""
        filename = PublicationPackageService.generate_package_filename(
            "Test", version=1
        )

        date_str = datetime.now().strftime("%Y%m%d")
        assert date_str in filename


# ========== compute_file_hash Tests ==========


class TestComputeFileHash:
    """Tests for PublicationPackageService.compute_file_hash."""

    def test_hash_basic(self):
        """Test known SHA-256 hash for known input."""
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()

        result = PublicationPackageService.compute_file_hash(data)

        assert result == expected

    def test_hash_empty_bytes(self):
        """Test SHA-256 hash of empty bytes."""
        data = b""
        expected = hashlib.sha256(b"").hexdigest()

        result = PublicationPackageService.compute_file_hash(data)

        assert result == expected
        # Known hash for empty input
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_deterministic(self):
        """Test same input always produces same hash."""
        data = b"reproducible science matters"

        hash1 = PublicationPackageService.compute_file_hash(data)
        hash2 = PublicationPackageService.compute_file_hash(data)

        assert hash1 == hash2

    def test_hash_different_inputs(self):
        """Test different inputs produce different hashes."""
        hash1 = PublicationPackageService.compute_file_hash(b"input A")
        hash2 = PublicationPackageService.compute_file_hash(b"input B")

        assert hash1 != hash2


# ========== create_package_structure Tests ==========


class TestCreatePackageStructure:
    """Tests for PublicationPackageService.create_package_structure."""

    def test_creates_all_directories(self, tmp_dir):
        """Test all 7 standard directories are created."""
        paths = PublicationPackageService.create_package_structure(tmp_dir)

        for dir_name in PublicationPackageService.DIRECTORIES:
            dir_path = tmp_dir / dir_name
            assert dir_path.exists(), f"Directory {dir_name} was not created"
            assert dir_path.is_dir()

    def test_directory_names(self, tmp_dir):
        """Test correct directory names match the DIRECTORIES constant."""
        paths = PublicationPackageService.create_package_structure(tmp_dir)

        expected = {
            "raw_data",
            "processed_data",
            "analysis_checkpoints",
            "figures",
            "mcmc_traces",
            "metadata",
            "audit",
        }
        assert set(paths.keys()) == expected

    def test_returns_path_dict(self, tmp_dir):
        """Test returns dict mapping directory names to Path objects."""
        paths = PublicationPackageService.create_package_structure(tmp_dir)

        assert isinstance(paths, dict)
        for name, path in paths.items():
            assert isinstance(path, Path)
            assert path == tmp_dir / name

    def test_idempotent(self, tmp_dir):
        """Test calling twice does not error (exist_ok=True)."""
        paths1 = PublicationPackageService.create_package_structure(tmp_dir)
        paths2 = PublicationPackageService.create_package_structure(tmp_dir)

        assert set(paths1.keys()) == set(paths2.keys())
        for name in paths1:
            assert paths1[name] == paths2[name]
            assert paths1[name].exists()


# ========== generate_manifest Tests ==========


class TestGenerateManifest:
    """Tests for PublicationPackageService.generate_manifest."""

    def _make_config(self, **kwargs):
        """Helper to create a PublicationPackageConfig with defaults."""
        defaults = {
            "title": "Test Package",
            "authors": ["Author A"],
            "description": "Test description",
            "keywords": ["test"],
            "license": "CC-BY-4.0",
        }
        defaults.update(kwargs)
        return PublicationPackageConfig(**defaults)

    def _make_file_hashes(self):
        """Helper to create sample FileHash instances."""
        return [
            FileHash(
                filename="raw_data/plate_1.json",
                sha256="aaa111",
                size_bytes=500,
                content_type="application/json",
            ),
            FileHash(
                filename="processed_data/results.csv",
                sha256="bbb222",
                size_bytes=300,
                content_type="text/csv",
            ),
        ]

    def test_manifest_structure(self):
        """Test manifest has all required top-level keys."""
        config = self._make_config()
        files = self._make_file_hashes()

        manifest = PublicationPackageService.generate_manifest(
            files=files,
            config=config,
            analysis_config={"method": "bayesian"},
            software_info={"name": "IVT Analyzer", "version": "1.0.0"},
        )

        assert "manifest_version" in manifest
        assert "created_at" in manifest
        assert "package" in manifest
        assert "software" in manifest
        assert "analysis_config" in manifest
        assert "files" in manifest
        assert "checksums" in manifest

    def test_manifest_package_info(self):
        """Test package metadata comes from config."""
        config = self._make_config(
            title="My Analysis",
            authors=["Alice", "Bob"],
            description="An IVT study",
            keywords=["IVT", "aptamer"],
            doi="10.1234/test",
        )

        manifest = PublicationPackageService.generate_manifest(
            files=[],
            config=config,
            analysis_config={},
            software_info={},
        )

        pkg = manifest["package"]
        assert pkg["title"] == "My Analysis"
        assert pkg["authors"] == ["Alice", "Bob"]
        assert pkg["description"] == "An IVT study"
        assert pkg["keywords"] == ["IVT", "aptamer"]
        assert pkg["license"] == "CC-BY-4.0"
        assert pkg["doi"] == "10.1234/test"

    def test_manifest_files(self):
        """Test file list with hashes is properly serialized."""
        config = self._make_config()
        files = self._make_file_hashes()

        manifest = PublicationPackageService.generate_manifest(
            files=files,
            config=config,
            analysis_config={},
            software_info={},
        )

        assert len(manifest["files"]) == 2
        assert manifest["files"][0]["filename"] == "raw_data/plate_1.json"
        assert manifest["files"][0]["sha256"] == "aaa111"
        assert manifest["files"][0]["size_bytes"] == 500
        assert manifest["files"][0]["content_type"] == "application/json"
        assert manifest["files"][1]["filename"] == "processed_data/results.csv"

    def test_manifest_checksums(self):
        """Test total files and total size are computed correctly."""
        config = self._make_config()
        files = self._make_file_hashes()

        manifest = PublicationPackageService.generate_manifest(
            files=files,
            config=config,
            analysis_config={},
            software_info={},
        )

        checksums = manifest["checksums"]
        assert checksums["algorithm"] == "SHA-256"
        assert checksums["total_files"] == 2
        assert checksums["total_size_bytes"] == 800  # 500 + 300

    def test_manifest_empty_files(self):
        """Test empty file list is handled gracefully."""
        config = self._make_config()

        manifest = PublicationPackageService.generate_manifest(
            files=[],
            config=config,
            analysis_config={},
            software_info={},
        )

        assert manifest["files"] == []
        assert manifest["checksums"]["total_files"] == 0
        assert manifest["checksums"]["total_size_bytes"] == 0


# ========== generate_datacite_metadata Tests ==========


class TestGenerateDataciteMetadata:
    """Tests for PublicationPackageService.generate_datacite_metadata."""

    def _make_config(self, **kwargs):
        """Helper to create a PublicationPackageConfig."""
        defaults = {
            "title": "Test Package",
            "authors": ["Author A", "Author B"],
            "description": "A test description",
            "keywords": ["kinetics", "IVT"],
            "license": "CC-BY-4.0",
        }
        defaults.update(kwargs)
        return PublicationPackageConfig(**defaults)

    def test_datacite_structure(self):
        """Test required DataCite fields are present."""
        config = self._make_config()
        summary = {"n_constructs": 5, "n_plates": 3, "n_wells": 96}

        metadata = PublicationPackageService.generate_datacite_metadata(
            config, summary
        )

        assert "schemaVersion" in metadata
        assert "identifier" in metadata
        assert "creators" in metadata
        assert "titles" in metadata
        assert "publisher" in metadata
        assert "publicationYear" in metadata
        assert "resourceType" in metadata
        assert "subjects" in metadata
        assert "descriptions" in metadata
        assert "rightsList" in metadata
        assert "formats" in metadata
        assert "sizes" in metadata

    def test_datacite_creators(self):
        """Test authors are mapped to DataCite creators."""
        config = self._make_config(authors=["Alice Smith", "Bob Jones"])

        metadata = PublicationPackageService.generate_datacite_metadata(
            config, {}
        )

        creators = metadata["creators"]
        assert len(creators) == 2
        assert creators[0]["name"] == "Alice Smith"
        assert creators[1]["name"] == "Bob Jones"

    def test_datacite_subjects(self):
        """Test keywords are mapped to DataCite subjects."""
        config = self._make_config(keywords=["aptamer", "fluorescence", "kinetics"])

        metadata = PublicationPackageService.generate_datacite_metadata(
            config, {}
        )

        subjects = metadata["subjects"]
        assert len(subjects) == 3
        assert subjects[0]["subject"] == "aptamer"
        assert subjects[1]["subject"] == "fluorescence"
        assert subjects[2]["subject"] == "kinetics"

    def test_datacite_no_doi(self):
        """Test DOI defaults to PENDING when not set."""
        config = self._make_config(doi=None)

        metadata = PublicationPackageService.generate_datacite_metadata(
            config, {}
        )

        assert metadata["identifier"]["identifier"] == "PENDING"
        assert metadata["identifier"]["identifierType"] == "DOI"


# ========== export_raw_data Tests ==========


class TestExportRawData:
    """Tests for PublicationPackageService.export_raw_data."""

    def test_export_creates_files(self, tmp_dir):
        """Test plate data files are created in output directory."""
        raw_data = {
            "plates": {
                "1": {"wells": ["A1", "A2"], "values": [100, 200]},
                "2": {"wells": ["B1", "B2"], "values": [300, 400]},
            }
        }

        hashes = PublicationPackageService.export_raw_data(raw_data, tmp_dir)

        assert len(hashes) == 2
        assert (tmp_dir / "plate_1_raw.json").exists()
        assert (tmp_dir / "plate_2_raw.json").exists()

        # Check FileHash fields
        assert hashes[0].filename == "raw_data/plate_1_raw.json"
        assert hashes[0].content_type == "application/json"
        assert hashes[0].size_bytes > 0
        assert len(hashes[0].sha256) == 64  # SHA-256 hex digest length

    def test_export_empty_data(self, tmp_dir):
        """Test empty raw_data dict is handled without errors."""
        hashes = PublicationPackageService.export_raw_data({}, tmp_dir)

        assert hashes == []

    def test_export_preserves_content(self, tmp_dir):
        """Test exported data integrity matches original input."""
        plate_data = {"wells": ["A1"], "values": [42.5]}
        raw_data = {"plates": {"99": plate_data}}

        hashes = PublicationPackageService.export_raw_data(raw_data, tmp_dir)

        # Read the file back and verify content
        written_data = json.loads((tmp_dir / "plate_99_raw.json").read_text())
        assert written_data == plate_data

        # Verify hash matches actual file content
        actual_bytes = (tmp_dir / "plate_99_raw.json").read_bytes()
        expected_hash = hashlib.sha256(actual_bytes).hexdigest()
        assert hashes[0].sha256 == expected_hash


# ========== export_processed_results Tests ==========


class TestExportProcessedResults:
    """Tests for PublicationPackageService.export_processed_results."""

    def test_export_fitted_params_csv(self, tmp_dir):
        """Test fitted parameters are exported as CSV."""
        results = {
            "fitted_params": [
                {"well": "A1", "k_obs": 0.05, "f_max": 1000.0},
                {"well": "A2", "k_obs": 0.03, "f_max": 800.0},
            ]
        }

        hashes = PublicationPackageService.export_processed_results(results, tmp_dir)

        assert any(fh.filename == "processed_data/fitted_parameters.csv" for fh in hashes)
        assert (tmp_dir / "fitted_parameters.csv").exists()

    def test_export_fold_changes_csv(self, tmp_dir):
        """Test fold changes are exported as CSV."""
        results = {
            "fold_changes": [
                {"construct": "WT", "fold_change": 1.0},
                {"construct": "Mut1", "fold_change": 2.5},
            ]
        }

        hashes = PublicationPackageService.export_processed_results(results, tmp_dir)

        assert any(fh.filename == "processed_data/fold_changes.csv" for fh in hashes)

    def test_export_posterior_summary(self, tmp_dir):
        """Test posterior summary is exported as JSON."""
        results = {
            "posterior_summary": {"mean": 0.5, "sd": 0.1, "hdi_low": 0.3, "hdi_high": 0.7}
        }

        hashes = PublicationPackageService.export_processed_results(results, tmp_dir)

        assert any(fh.filename == "processed_data/posterior_summary.json" for fh in hashes)
        written = json.loads((tmp_dir / "posterior_summary.json").read_text())
        assert written["mean"] == 0.5

    def test_export_convergence_diagnostics(self, tmp_dir):
        """Test convergence diagnostics are exported as JSON."""
        results = {
            "convergence": {"r_hat": 1.01, "ess": 2000}
        }

        hashes = PublicationPackageService.export_processed_results(results, tmp_dir)

        assert any(fh.filename == "processed_data/convergence_diagnostics.json" for fh in hashes)

    def test_export_empty_results(self, tmp_dir):
        """Test empty results dict produces no files."""
        hashes = PublicationPackageService.export_processed_results({}, tmp_dir)

        assert hashes == []


# ========== export_analysis_checkpoints Tests ==========


class TestExportAnalysisCheckpoints:
    """Tests for PublicationPackageService.export_analysis_checkpoints."""

    def test_export_named_checkpoint(self, tmp_dir):
        """Test checkpoint with a name field uses that name as filename."""
        checkpoints = [
            {"name": "pre_fitting", "stage": "initial", "data": [1, 2, 3]},
        ]

        hashes = PublicationPackageService.export_analysis_checkpoints(checkpoints, tmp_dir)

        assert len(hashes) == 1
        assert hashes[0].filename == "analysis_checkpoints/pre_fitting.json"
        assert (tmp_dir / "pre_fitting.json").exists()

    def test_export_unnamed_checkpoint(self, tmp_dir):
        """Test checkpoint without a name field falls back to index-based name."""
        checkpoints = [
            {"stage": "initial", "data": [1, 2, 3]},
        ]

        hashes = PublicationPackageService.export_analysis_checkpoints(checkpoints, tmp_dir)

        assert hashes[0].filename == "analysis_checkpoints/checkpoint_0.json"

    def test_export_multiple_checkpoints(self, tmp_dir):
        """Test exporting multiple checkpoints."""
        checkpoints = [
            {"name": "step_1", "x": 1},
            {"name": "step_2", "x": 2},
            {"name": "step_3", "x": 3},
        ]

        hashes = PublicationPackageService.export_analysis_checkpoints(checkpoints, tmp_dir)

        assert len(hashes) == 3
        for fh in hashes:
            assert fh.content_type == "application/json"
            assert fh.size_bytes > 0


# ========== generate_audit_log Tests ==========


class TestGenerateAuditLog:
    """Tests for PublicationPackageService.generate_audit_log."""

    def test_generates_dual_format(self, tmp_dir):
        """Test audit log generates both JSON and Markdown files."""
        events = [
            {
                "timestamp": "2026-01-15T10:00:00",
                "action": "create",
                "user": "alice",
                "details": {"entity_type": "project"},
            },
        ]

        hashes = PublicationPackageService.generate_audit_log(events, tmp_dir)

        filenames = [fh.filename for fh in hashes]
        assert "audit/audit_log.json" in filenames
        assert "audit/audit_log.md" in filenames
        assert (tmp_dir / "audit_log.json").exists()
        assert (tmp_dir / "audit_log.md").exists()

    def test_json_format_structure(self, tmp_dir):
        """Test JSON audit log has correct structure."""
        events = [{"action": "update", "user": "bob"}]

        PublicationPackageService.generate_audit_log(events, tmp_dir)

        data = json.loads((tmp_dir / "audit_log.json").read_text())
        assert "audit_version" in data
        assert "generated_at" in data
        assert "events" in data
        assert data["events"] == events

    def test_empty_events(self, tmp_dir):
        """Test empty event list produces valid output files."""
        hashes = PublicationPackageService.generate_audit_log([], tmp_dir)

        assert len(hashes) == 2  # JSON + Markdown always generated
        data = json.loads((tmp_dir / "audit_log.json").read_text())
        assert data["events"] == []


# ========== validate_package_integrity Tests ==========


class TestValidatePackageIntegrity:
    """Tests for PublicationPackageService.validate_package_integrity."""

    def test_valid_package(self, tmp_dir):
        """Test integrity validation passes for correct files."""
        # Create a file with known content
        content = b"test data for validation"
        file_path = tmp_dir / "raw_data"
        file_path.mkdir()
        (file_path / "data.json").write_bytes(content)

        manifest = {
            "files": [
                {
                    "filename": "raw_data/data.json",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            ]
        }

        is_valid, errors = PublicationPackageService.validate_package_integrity(
            tmp_dir, manifest
        )

        assert is_valid is True
        assert errors == []

    def test_missing_file(self, tmp_dir):
        """Test validation detects missing files."""
        manifest = {
            "files": [
                {
                    "filename": "raw_data/missing.json",
                    "sha256": "abc",
                    "size_bytes": 100,
                }
            ]
        }

        is_valid, errors = PublicationPackageService.validate_package_integrity(
            tmp_dir, manifest
        )

        assert is_valid is False
        assert len(errors) == 1
        assert "Missing file" in errors[0]

    def test_hash_mismatch(self, tmp_dir):
        """Test validation detects hash mismatches."""
        content = b"original content"
        (tmp_dir / "data.json").write_bytes(content)

        manifest = {
            "files": [
                {
                    "filename": "data.json",
                    "sha256": "wrong_hash_value_that_does_not_match",
                    "size_bytes": len(content),
                }
            ]
        }

        is_valid, errors = PublicationPackageService.validate_package_integrity(
            tmp_dir, manifest
        )

        assert is_valid is False
        assert any("Hash mismatch" in e for e in errors)

    def test_size_mismatch(self, tmp_dir):
        """Test validation detects size mismatches."""
        content = b"some data"
        (tmp_dir / "data.json").write_bytes(content)

        manifest = {
            "files": [
                {
                    "filename": "data.json",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": 99999,  # Wrong size
                }
            ]
        }

        is_valid, errors = PublicationPackageService.validate_package_integrity(
            tmp_dir, manifest
        )

        assert is_valid is False
        assert any("Size mismatch" in e for e in errors)
