"""
Publication package service for IVT Kinetics Analyzer.

Phase 9.4-9.7: Publication package generation (F15.7-F15.16)

Creates complete, reproducible publication packages with:
- Raw data preservation (bit-for-bit)
- Processed results
- MCMC traces (NetCDF format)
- Audit logs
- Reproducibility manifests
- DataCite metadata
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import hashlib
import zipfile
import shutil
from io import BytesIO
import csv

from app.services.methods_text_service import MethodsTextService, MethodsTextConfig


@dataclass
class PublicationPackageConfig:
    """Configuration for publication package generation."""

    # Package metadata
    title: str = ""
    authors: List[str] = field(default_factory=list)
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    doi: Optional[str] = None
    license: str = "CC-BY-4.0"

    # Package options
    include_raw_data: bool = True
    include_mcmc_traces: bool = True
    include_figures: bool = True
    include_methods: bool = True
    include_audit_log: bool = True

    # Format options
    figure_format: str = "png"  # png, svg, pdf
    figure_dpi: int = 300

    # Reproducibility
    include_manifest: bool = True
    include_software_config: bool = True


@dataclass
class FileHash:
    """Hash information for a file."""
    filename: str
    sha256: str
    size_bytes: int
    content_type: str


class PublicationPackageService:
    """Service for generating publication packages."""

    PACKAGE_VERSION = "1.0"

    # Standard directory structure per PRD F15.4-F15.7
    DIRECTORIES = [
        "raw_data",
        "processed_data",
        "analysis_checkpoints",
        "figures",
        "mcmc_traces",
        "metadata",
        "audit",
    ]

    @staticmethod
    def generate_package_filename(
        project_name: str,
        version: int = 1,
    ) -> str:
        """
        Generate standardized package filename per PRD spec.

        Format: {project_slug}_{YYYYMMDD}_{version}.zip

        Args:
            project_name: Project name to slugify
            version: Package version number

        Returns:
            Standardized filename
        """
        import re
        from datetime import datetime

        # Create slug from project name
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', project_name.lower()).strip('_')
        if not slug:
            slug = "package"

        date_str = datetime.now().strftime("%Y%m%d")
        return f"{slug}_{date_str}_v{version}.zip"

    @staticmethod
    def compute_file_hash(data: bytes) -> str:
        """
        Compute SHA-256 hash of file data.

        Args:
            data: File bytes

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def create_package_structure(base_path: Path) -> Dict[str, Path]:
        """
        Create directory structure for publication package.

        Args:
            base_path: Base path for package

        Returns:
            Dict mapping directory names to paths
        """
        paths = {}
        for dir_name in PublicationPackageService.DIRECTORIES:
            dir_path = base_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            paths[dir_name] = dir_path

        return paths

    @staticmethod
    def generate_manifest(
        files: List[FileHash],
        config: PublicationPackageConfig,
        analysis_config: Dict[str, Any],
        software_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate reproducibility manifest.

        Args:
            files: List of FileHash objects for all package files
            config: Package configuration
            analysis_config: Analysis settings used
            software_info: Software version information

        Returns:
            Manifest dictionary
        """
        manifest = {
            "manifest_version": PublicationPackageService.PACKAGE_VERSION,
            "created_at": datetime.now().isoformat(),
            "package": {
                "title": config.title,
                "authors": config.authors,
                "description": config.description,
                "keywords": config.keywords,
                "license": config.license,
                "doi": config.doi,
            },
            "software": software_info,
            "analysis_config": analysis_config,
            "files": [
                {
                    "filename": f.filename,
                    "sha256": f.sha256,
                    "size_bytes": f.size_bytes,
                    "content_type": f.content_type,
                }
                for f in files
            ],
            "checksums": {
                "algorithm": "SHA-256",
                "total_files": len(files),
                "total_size_bytes": sum(f.size_bytes for f in files),
            },
        }

        return manifest

    @staticmethod
    def generate_datacite_metadata(
        config: PublicationPackageConfig,
        analysis_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate DataCite-compatible metadata for repository upload.

        Args:
            config: Package configuration
            analysis_summary: Summary of analysis results

        Returns:
            DataCite metadata dictionary
        """
        metadata = {
            "schemaVersion": "http://datacite.org/schema/kernel-4",
            "identifier": {
                "identifier": config.doi or "PENDING",
                "identifierType": "DOI",
            },
            "creators": [
                {"name": author}
                for author in config.authors
            ],
            "titles": [
                {"title": config.title}
            ],
            "publisher": "IVT Kinetics Analyzer Publication Package",
            "publicationYear": datetime.now().year,
            "resourceType": {
                "resourceTypeGeneral": "Dataset",
                "resourceType": "Kinetics Analysis Results",
            },
            "subjects": [
                {"subject": kw}
                for kw in config.keywords
            ],
            "descriptions": [
                {
                    "description": config.description,
                    "descriptionType": "Abstract",
                }
            ],
            "rightsList": [
                {
                    "rights": config.license,
                    "rightsURI": f"https://spdx.org/licenses/{config.license}.html",
                }
            ],
            "formats": ["application/json", "text/csv", "application/x-netcdf"],
            "sizes": [
                f"{analysis_summary.get('n_constructs', 0)} constructs",
                f"{analysis_summary.get('n_plates', 0)} plates",
                f"{analysis_summary.get('n_wells', 0)} wells",
            ],
        }

        return metadata

    @staticmethod
    def export_raw_data(
        raw_data: Dict[str, Any],
        output_path: Path,
    ) -> List[FileHash]:
        """
        Export raw data with bit-for-bit preservation.

        Args:
            raw_data: Raw measurement data
            output_path: Output directory

        Returns:
            List of FileHash objects for exported files
        """
        file_hashes = []

        # Export each plate's raw data
        if "plates" in raw_data:
            for plate_id, plate_data in raw_data["plates"].items():
                filename = f"plate_{plate_id}_raw.json"
                filepath = output_path / filename
                data_bytes = json.dumps(plate_data, indent=2).encode("utf-8")

                filepath.write_bytes(data_bytes)

                file_hashes.append(FileHash(
                    filename=f"raw_data/{filename}",
                    sha256=PublicationPackageService.compute_file_hash(data_bytes),
                    size_bytes=len(data_bytes),
                    content_type="application/json",
                ))

        # Export original uploaded files if available
        if "original_files" in raw_data:
            for orig_filename, file_content in raw_data["original_files"].items():
                safe_name = orig_filename.replace("/", "_").replace("\\", "_")
                filepath = output_path / f"original_{safe_name}"

                if isinstance(file_content, bytes):
                    filepath.write_bytes(file_content)
                    data_bytes = file_content
                else:
                    data_bytes = str(file_content).encode("utf-8")
                    filepath.write_bytes(data_bytes)

                file_hashes.append(FileHash(
                    filename=f"raw_data/original_{safe_name}",
                    sha256=PublicationPackageService.compute_file_hash(data_bytes),
                    size_bytes=len(data_bytes),
                    content_type="application/octet-stream",
                ))

        return file_hashes

    @staticmethod
    def export_processed_results(
        results: Dict[str, Any],
        output_path: Path,
    ) -> List[FileHash]:
        """
        Export processed analysis results.

        Args:
            results: Analysis results
            output_path: Output directory

        Returns:
            List of FileHash objects for exported files
        """
        file_hashes = []

        # Fitted parameters CSV
        if "fitted_params" in results:
            filename = "fitted_parameters.csv"
            filepath = output_path / filename

            params = results["fitted_params"]
            if params:
                fieldnames = list(params[0].keys())
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(params)

                data_bytes = filepath.read_bytes()
                file_hashes.append(FileHash(
                    filename=f"processed_data/{filename}",
                    sha256=PublicationPackageService.compute_file_hash(data_bytes),
                    size_bytes=len(data_bytes),
                    content_type="text/csv",
                ))

        # Fold changes CSV
        if "fold_changes" in results:
            filename = "fold_changes.csv"
            filepath = output_path / filename

            fc = results["fold_changes"]
            if fc:
                fieldnames = list(fc[0].keys())
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(fc)

                data_bytes = filepath.read_bytes()
                file_hashes.append(FileHash(
                    filename=f"processed_data/{filename}",
                    sha256=PublicationPackageService.compute_file_hash(data_bytes),
                    size_bytes=len(data_bytes),
                    content_type="text/csv",
                ))

        # Posterior summaries JSON
        if "posterior_summary" in results:
            filename = "posterior_summary.json"
            filepath = output_path / filename
            data_bytes = json.dumps(results["posterior_summary"], indent=2).encode("utf-8")
            filepath.write_bytes(data_bytes)

            file_hashes.append(FileHash(
                filename=f"processed_data/{filename}",
                sha256=PublicationPackageService.compute_file_hash(data_bytes),
                size_bytes=len(data_bytes),
                content_type="application/json",
            ))

        # Convergence diagnostics
        if "convergence" in results:
            filename = "convergence_diagnostics.json"
            filepath = output_path / filename
            data_bytes = json.dumps(results["convergence"], indent=2).encode("utf-8")
            filepath.write_bytes(data_bytes)

            file_hashes.append(FileHash(
                filename=f"processed_data/{filename}",
                sha256=PublicationPackageService.compute_file_hash(data_bytes),
                size_bytes=len(data_bytes),
                content_type="application/json",
            ))

        return file_hashes

    @staticmethod
    def export_mcmc_traces_netcdf(
        traces: Dict[str, Any],
        output_path: Path,
    ) -> List[FileHash]:
        """
        Export MCMC traces in NetCDF format.

        NetCDF is used instead of pickle for security and portability.

        Args:
            traces: MCMC trace data
            output_path: Output directory

        Returns:
            List of FileHash objects for exported files
        """
        file_hashes = []

        try:
            import xarray as xr
            import numpy as np

            # Convert traces to xarray Dataset
            data_vars = {}
            for param_name, param_traces in traces.items():
                if isinstance(param_traces, (list, tuple)):
                    arr = np.array(param_traces)
                    if arr.ndim == 1:
                        data_vars[param_name] = (["sample"], arr)
                    elif arr.ndim == 2:
                        data_vars[param_name] = (["chain", "sample"], arr)
                    else:
                        data_vars[param_name] = (["chain", "sample"] + [f"dim_{i}" for i in range(arr.ndim - 2)], arr)

            if data_vars:
                ds = xr.Dataset(data_vars)
                ds.attrs["created_at"] = datetime.now().isoformat()
                ds.attrs["format"] = "MCMC traces from IVT Kinetics Analyzer"

                filename = "mcmc_traces.nc"
                filepath = output_path / filename
                ds.to_netcdf(filepath)

                data_bytes = filepath.read_bytes()
                file_hashes.append(FileHash(
                    filename=f"mcmc_traces/{filename}",
                    sha256=PublicationPackageService.compute_file_hash(data_bytes),
                    size_bytes=len(data_bytes),
                    content_type="application/x-netcdf",
                ))

        except ImportError:
            # Fallback to JSON if xarray not available
            filename = "mcmc_traces.json"
            filepath = output_path / filename

            # Convert numpy arrays to lists for JSON serialization
            def convert_to_serializable(obj):
                try:
                    import numpy as np
                    if isinstance(obj, np.ndarray):
                        return obj.tolist()
                except ImportError:
                    pass
                if isinstance(obj, dict):
                    return {k: convert_to_serializable(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [convert_to_serializable(v) for v in obj]
                return obj

            serializable_traces = convert_to_serializable(traces)
            data_bytes = json.dumps(serializable_traces, indent=2).encode("utf-8")
            filepath.write_bytes(data_bytes)

            file_hashes.append(FileHash(
                filename=f"mcmc_traces/{filename}",
                sha256=PublicationPackageService.compute_file_hash(data_bytes),
                size_bytes=len(data_bytes),
                content_type="application/json",
            ))

        return file_hashes

    @staticmethod
    def generate_audit_log(
        events: List[Dict[str, Any]],
        output_path: Path,
    ) -> List[FileHash]:
        """
        Generate dual-format audit log (Markdown + JSON).

        Args:
            events: List of audit events
            output_path: Output directory

        Returns:
            List of FileHash objects for exported files
        """
        file_hashes = []

        # JSON format
        json_filename = "audit_log.json"
        json_path = output_path / json_filename
        json_data = json.dumps({
            "audit_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "events": events,
        }, indent=2).encode("utf-8")
        json_path.write_bytes(json_data)

        file_hashes.append(FileHash(
            filename=f"audit/{json_filename}",
            sha256=PublicationPackageService.compute_file_hash(json_data),
            size_bytes=len(json_data),
            content_type="application/json",
        ))

        # Markdown format
        md_filename = "audit_log.md"
        md_path = output_path / md_filename

        # Compute summary statistics
        from collections import Counter
        action_counts = Counter(e.get("action", "unknown") for e in events)
        user_counts = Counter(e.get("user", "System") for e in events)
        entity_counts = Counter()
        for e in events:
            details = e.get("details")
            if isinstance(details, dict) and "entity_type" in details:
                entity_counts[details["entity_type"]] += 1

        timestamps = [e.get("timestamp", "") for e in events if e.get("timestamp")]
        date_range = ""
        if timestamps:
            date_range = f"{min(timestamps)[:10]} to {max(timestamps)[:10]}"

        md_lines = [
            "# Audit Log",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- **Total events**: {len(events)}",
            f"- **Date range**: {date_range or 'N/A'}",
            f"- **Actions**: {', '.join(f'{a} ({c})' for a, c in action_counts.most_common())}",
            f"- **Users**: {', '.join(f'{u} ({c})' for u, c in user_counts.most_common())}",
        ]
        if entity_counts:
            md_lines.append(
                f"- **Entity types**: {', '.join(f'{et} ({c})' for et, c in entity_counts.most_common())}"
            )
        md_lines.extend(["", "## Event Timeline", ""])

        for event in events:
            timestamp = event.get("timestamp", "Unknown")
            action = event.get("action", "Unknown action")
            user = event.get("user", "System")
            details = event.get("details")

            md_lines.append(f"### {timestamp}")
            md_lines.append(f"- **Action**: {action}")
            md_lines.append(f"- **User**: {user}")

            if isinstance(details, dict):
                detail_items = [
                    f"{k}: {v}" for k, v in details.items()
                    if k != "changes"
                ]
                if detail_items:
                    md_lines.append(f"- **Details**: {', '.join(detail_items)}")
            elif details:
                md_lines.append(f"- **Details**: {details}")

            # Expand changes field with before/after diffs
            changes = event.get("changes", [])
            if changes and isinstance(changes, list):
                md_lines.append("- **Field changes**:")
                for change in changes:
                    field = change.get("field", "unknown")
                    old_val = change.get("old", "N/A")
                    new_val = change.get("new", "N/A")
                    md_lines.append(f"  - `{field}`: ~~{old_val}~~ → **{new_val}**")

            md_lines.append("")

        md_data = "\n".join(md_lines).encode("utf-8")
        md_path.write_bytes(md_data)

        file_hashes.append(FileHash(
            filename=f"audit/{md_filename}",
            sha256=PublicationPackageService.compute_file_hash(md_data),
            size_bytes=len(md_data),
            content_type="text/markdown",
        ))

        return file_hashes

    @staticmethod
    def create_publication_package(
        config: PublicationPackageConfig,
        raw_data: Dict[str, Any],
        results: Dict[str, Any],
        mcmc_traces: Optional[Dict[str, Any]] = None,
        figures: Optional[Dict[str, bytes]] = None,
        audit_events: Optional[List[Dict[str, Any]]] = None,
        analysis_config: Optional[Dict[str, Any]] = None,
        checkpoints: Optional[List[Dict[str, Any]]] = None,
        output_path: Optional[Path] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Create complete publication package.

        Args:
            config: Package configuration
            raw_data: Raw measurement data
            results: Analysis results
            mcmc_traces: Optional MCMC trace data
            figures: Optional dict mapping filename to figure bytes
            audit_events: Optional list of audit events
            analysis_config: Analysis configuration for manifest
            checkpoints: Optional list of analysis checkpoint data
            output_path: Optional path to save unzipped package

        Returns:
            Tuple of (zip bytes, manifest dict)
        """
        import tempfile

        all_file_hashes = []

        # Create temporary directory for package
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "publication_package"
            paths = PublicationPackageService.create_package_structure(base_path)

            # Export raw data
            if config.include_raw_data:
                hashes = PublicationPackageService.export_raw_data(
                    raw_data, paths["raw_data"]
                )
                all_file_hashes.extend(hashes)

            # Export processed results
            hashes = PublicationPackageService.export_processed_results(
                results, paths["processed_data"]
            )
            all_file_hashes.extend(hashes)

            # Export MCMC traces
            if config.include_mcmc_traces and mcmc_traces:
                hashes = PublicationPackageService.export_mcmc_traces_netcdf(
                    mcmc_traces, paths["mcmc_traces"]
                )
                all_file_hashes.extend(hashes)

            # Export analysis checkpoints
            if checkpoints:
                hashes = PublicationPackageService.export_analysis_checkpoints(
                    checkpoints, paths["analysis_checkpoints"]
                )
                all_file_hashes.extend(hashes)

            # Export figures
            if config.include_figures and figures:
                for fig_name, fig_bytes in figures.items():
                    filepath = paths["figures"] / fig_name
                    filepath.write_bytes(fig_bytes)

                    all_file_hashes.append(FileHash(
                        filename=f"figures/{fig_name}",
                        sha256=PublicationPackageService.compute_file_hash(fig_bytes),
                        size_bytes=len(fig_bytes),
                        content_type=f"image/{config.figure_format}",
                    ))

            # Generate audit log
            if config.include_audit_log:
                events = audit_events or []
                hashes = PublicationPackageService.generate_audit_log(
                    events, paths["audit"]
                )
                all_file_hashes.extend(hashes)

            # Generate methods text
            if config.include_methods:
                methods_config = MethodsTextConfig()
                if "data_summary" in results:
                    data = results["data_summary"]
                    methods_config.n_constructs = data.get("n_constructs", 0)
                    methods_config.n_plates = data.get("n_plates", 0)
                    methods_config.n_wells = data.get("n_wells", 0)
                    methods_config.n_sessions = data.get("n_sessions", 0)

                methods_text = MethodsTextService.generate_full_methods(methods_config)
                methods_path = paths["metadata"] / "methods.md"
                methods_data = methods_text.encode("utf-8")
                methods_path.write_bytes(methods_data)

                all_file_hashes.append(FileHash(
                    filename="metadata/methods.md",
                    sha256=PublicationPackageService.compute_file_hash(methods_data),
                    size_bytes=len(methods_data),
                    content_type="text/markdown",
                ))

            # Generate manifest
            software_info = {
                "name": "IVT Kinetics Analyzer",
                "version": "1.0.0",
            }

            manifest = PublicationPackageService.generate_manifest(
                all_file_hashes,
                config,
                analysis_config or {},
                software_info,
            )

            manifest_data = json.dumps(manifest, indent=2).encode("utf-8")
            manifest_path = base_path / "manifest.json"
            manifest_path.write_bytes(manifest_data)

            # Generate DataCite metadata
            datacite = PublicationPackageService.generate_datacite_metadata(
                config,
                results.get("data_summary", {}),
            )
            datacite_path = paths["metadata"] / "datacite.json"
            datacite_data = json.dumps(datacite, indent=2).encode("utf-8")
            datacite_path.write_bytes(datacite_data)

            # Generate README
            readme_lines = [
                f"# {config.title or 'IVT Kinetics Analysis Publication Package'}",
                "",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "## Contents",
                "",
                "- `raw_data/` - Original measurement data (bit-for-bit preserved)",
                "- `processed_data/` - Analysis results (CSV and JSON)",
                "- `analysis_checkpoints/` - Intermediate analysis states",
                "- `figures/` - Publication-ready figures",
                "- `mcmc_traces/` - MCMC trace data (NetCDF format, no pickle)",
                "- `metadata/` - Methods text and DataCite metadata",
                "- `audit/` - Audit log (JSON + Markdown)",
                "- `manifest.json` - Reproducibility manifest with SHA-256 checksums",
                "",
                "## Verification",
                "",
                "To verify file integrity, check SHA-256 hashes in `manifest.json`.",
                "All checksums use the SHA-256 algorithm.",
                "",
                "## Reproducibility",
                "",
                "This package can be validated by re-running the analysis with the",
                "same software version and comparing results within tolerance (1e-4).",
                "",
                "## License",
                "",
                f"This dataset is released under {config.license}.",
            ]
            readme_data = "\n".join(readme_lines).encode("utf-8")
            readme_path = base_path / "README.md"
            readme_path.write_bytes(readme_data)

            # Create ZIP archive
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in base_path.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(base_path)
                        zf.write(file_path, arcname)

            zip_buffer.seek(0)

            # Optionally copy to output path
            if output_path:
                output_path.mkdir(parents=True, exist_ok=True)
                shutil.copytree(base_path, output_path, dirs_exist_ok=True)

            return zip_buffer.read(), manifest

    @staticmethod
    def validate_package_integrity(
        package_path: Path,
        manifest: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate package integrity using manifest checksums.

        Args:
            package_path: Path to extracted package
            manifest: Manifest dictionary

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        for file_info in manifest.get("files", []):
            filename = file_info["filename"]
            expected_hash = file_info["sha256"]
            expected_size = file_info["size_bytes"]

            filepath = package_path / filename

            if not filepath.exists():
                errors.append(f"Missing file: {filename}")
                continue

            actual_data = filepath.read_bytes()
            actual_hash = PublicationPackageService.compute_file_hash(actual_data)
            actual_size = len(actual_data)

            if actual_hash != expected_hash:
                errors.append(
                    f"Hash mismatch for {filename}: "
                    f"expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
                )

            if actual_size != expected_size:
                errors.append(
                    f"Size mismatch for {filename}: "
                    f"expected {expected_size}, got {actual_size}"
                )

        return len(errors) == 0, errors

    @staticmethod
    def export_analysis_checkpoints(
        checkpoints: List[Dict[str, Any]],
        output_path: Path,
    ) -> List[FileHash]:
        """
        Export analysis checkpoints for intermediate states.

        Args:
            checkpoints: List of checkpoint data dicts
            output_path: Output directory

        Returns:
            List of FileHash objects for exported files
        """
        file_hashes = []

        for i, checkpoint in enumerate(checkpoints):
            checkpoint_name = checkpoint.get("name", f"checkpoint_{i}")
            filename = f"{checkpoint_name}.json"
            filepath = output_path / filename

            data_bytes = json.dumps(checkpoint, indent=2).encode("utf-8")
            filepath.write_bytes(data_bytes)

            file_hashes.append(FileHash(
                filename=f"analysis_checkpoints/{filename}",
                sha256=PublicationPackageService.compute_file_hash(data_bytes),
                size_bytes=len(data_bytes),
                content_type="application/json",
            ))

        return file_hashes

    @staticmethod
    def generate_figures_for_package(
        project_id: int,
        config: PublicationPackageConfig,
    ) -> Dict[str, bytes]:
        """
        Generate publication-ready figures for a project.

        Args:
            project_id: Project ID to generate figures for
            config: Package configuration with figure settings

        Returns:
            Dict mapping filename to figure bytes
        """
        figures = {}

        try:
            from app.components.forest_plot import create_forest_plot
            from app.components.curve_plot import create_curve_plot
            from app.models import (
                Project, Plate, Well, FitResult, ExperimentalSession,
            )
            from app.models.analysis_version import (
                AnalysisVersion, AnalysisStatus, HierarchicalResult,
            )
            from app.models.construct import Construct
            import plotly.io as pio

            project = Project.query.get(project_id)
            if not project:
                return figures

            format_ext = config.figure_format
            scale = 2 if config.figure_dpi >= 300 else 1

            # Generate forest plot from hierarchical results (one row per construct)
            latest_version = AnalysisVersion.query.filter_by(
                project_id=project_id, status=AnalysisStatus.COMPLETED
            ).order_by(AnalysisVersion.completed_at.desc()).first()

            if latest_version:
                # Get Bayesian log_fc_fmax results (the primary parameter)
                hier_results = HierarchicalResult.query.filter_by(
                    analysis_version_id=latest_version.id,
                    parameter_type="log_fc_fmax",
                    analysis_type="bayesian",
                ).all()

                if hier_results:
                    fc_data = []
                    for hr in hier_results:
                        construct = Construct.query.get(hr.construct_id)
                        construct_name = construct.identifier if construct else "Unknown"
                        family_name = (construct.family or "") if construct else ""
                        fc_data.append({
                            "name": construct_name,
                            "family": family_name,
                            "mean": hr.mean,
                            "ci_lower": hr.ci_lower,
                            "ci_upper": hr.ci_upper,
                            "vif": 1.0,
                            "is_wt": False,
                        })

                    try:
                        fig = create_forest_plot(
                            fc_data,
                            title="Fold Change Summary (Bayesian Posterior)",
                            group_by="family" if any(d["family"] for d in fc_data) else None,
                        )
                        # Scale height to number of constructs
                        fig_height = max(400, len(fc_data) * 45 + 150)
                        fig_bytes = pio.to_image(
                            fig,
                            format=format_ext,
                            scale=scale,
                            width=900,
                            height=fig_height,
                        )
                        figures[f"forest_plot.{format_ext}"] = fig_bytes
                    except Exception:
                        pass  # Skip if figure generation fails

            # Generate representative curve plots
            fit_results = FitResult.query.join(Well).join(Plate).join(
                ExperimentalSession
            ).filter(
                ExperimentalSession.project_id == project_id,
            ).limit(10).all()

            for i, fit in enumerate(fit_results):
                try:
                    well = fit.well
                    if well and well.raw_data:
                        times = [p.timepoint for p in well.raw_data]
                        fluor = [p.fluorescence_raw for p in well.raw_data]
                        fig = create_curve_plot(
                            timepoints=times,
                            raw_values=fluor,
                            fit_params={
                                "k_obs": fit.k_obs,
                                "f_max": fit.f_max,
                                "f_baseline": fit.f_baseline,
                                "t_lag": fit.t_lag or 0,
                            },
                            title=f"Well {well.position}",
                        )
                        fig_bytes = pio.to_image(
                            fig, format=format_ext, scale=scale,
                            width=600, height=400,
                        )
                        figures[f"curve_{well.position}.{format_ext}"] = fig_bytes
                except Exception:
                    pass

        except ImportError:
            pass  # Plotting libraries not available

        return figures

    @staticmethod
    def get_package_preview(
        project_id: int,
        config: PublicationPackageConfig,
    ) -> Dict[str, Any]:
        """
        Generate preview of package contents without creating the full package.

        Args:
            project_id: Project ID
            config: Package configuration

        Returns:
            Preview dict with structure, file list, and size estimates
        """
        from app.models import Project, Plate, Well, FitResult, FoldChange, AuditLog, ExperimentalSession

        preview = {
            "directories": [],
            "files": [],
            "total_estimated_size": 0,
            "warnings": [],
        }

        project = Project.query.get(project_id)
        if not project:
            preview["warnings"].append("Project not found")
            return preview

        # Build directory structure preview
        for dir_name in PublicationPackageService.DIRECTORIES:
            dir_info = {
                "name": dir_name,
                "files": [],
                "estimated_size": 0,
            }

            if dir_name == "raw_data" and config.include_raw_data:
                plates = Plate.query.join(ExperimentalSession).filter(
                    ExperimentalSession.project_id == project_id
                ).all()
                for plate in plates:
                    file_info = {
                        "name": f"plate_{plate.id}_raw.json",
                        "type": "application/json",
                        "estimated_size": 50000,  # ~50KB estimate per plate
                    }
                    dir_info["files"].append(file_info)
                    dir_info["estimated_size"] += file_info["estimated_size"]

            elif dir_name == "processed_data":
                # Fitted parameters CSV
                fit_count = FitResult.query.join(Well).join(Plate).join(
                    ExperimentalSession
                ).filter(ExperimentalSession.project_id == project_id).count()
                if fit_count > 0:
                    dir_info["files"].append({
                        "name": "fitted_parameters.csv",
                        "type": "text/csv",
                        "estimated_size": fit_count * 200,  # ~200 bytes per row
                    })

                # Fold changes CSV
                fc_count = FoldChange.query.join(
                    Well, FoldChange.test_well_id == Well.id
                ).join(Plate).join(ExperimentalSession).filter(
                    ExperimentalSession.project_id == project_id
                ).count()
                if fc_count > 0:
                    dir_info["files"].append({
                        "name": "fold_changes.csv",
                        "type": "text/csv",
                        "estimated_size": fc_count * 150,
                    })

                # Posterior summary
                dir_info["files"].append({
                    "name": "posterior_summary.json",
                    "type": "application/json",
                    "estimated_size": 5000,
                })

                dir_info["estimated_size"] = sum(f["estimated_size"] for f in dir_info["files"])

            elif dir_name == "figures" and config.include_figures:
                # Estimate figure files
                dir_info["files"].append({
                    "name": f"forest_plot.{config.figure_format}",
                    "type": f"image/{config.figure_format}",
                    "estimated_size": 200000 if config.figure_format == "png" else 50000,
                })
                dir_info["estimated_size"] = sum(f["estimated_size"] for f in dir_info["files"])

            elif dir_name == "mcmc_traces" and config.include_mcmc_traces:
                dir_info["files"].append({
                    "name": "mcmc_traces.nc",
                    "type": "application/x-netcdf",
                    "estimated_size": 5000000,  # ~5MB estimate
                })
                dir_info["estimated_size"] = 5000000

            elif dir_name == "audit" and config.include_audit_log:
                event_count = AuditLog.query.filter_by(project_id=project_id).count()
                dir_info["files"].extend([
                    {"name": "audit_log.json", "type": "application/json", "estimated_size": event_count * 500},
                    {"name": "audit_log.md", "type": "text/markdown", "estimated_size": event_count * 300},
                ])
                dir_info["estimated_size"] = sum(f["estimated_size"] for f in dir_info["files"])

            elif dir_name == "metadata":
                dir_info["files"].extend([
                    {"name": "methods.md", "type": "text/markdown", "estimated_size": 3000},
                    {"name": "datacite.json", "type": "application/json", "estimated_size": 2000},
                ])
                dir_info["estimated_size"] = 5000

            preview["directories"].append(dir_info)
            preview["total_estimated_size"] += dir_info["estimated_size"]

        # Add root files
        preview["files"].extend([
            {"name": "manifest.json", "type": "application/json", "estimated_size": 5000},
            {"name": "README.md", "type": "text/markdown", "estimated_size": 1000},
        ])
        preview["total_estimated_size"] += 6000

        return preview


class PublicationPackageError(Exception):
    """Exception raised for publication package errors."""
    pass
