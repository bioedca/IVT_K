"""
Export generation background tasks.

PRD Reference: Phase 6, Section 0.11, F10.1-F10.7
Implements background tasks for generating publication packages and exports.
"""
import traceback
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.tasks.huey_config import huey
from app.extensions import db
from app.models.task_progress import TaskProgress, TaskType

# Note: TaskService is imported lazily inside functions to avoid circular import


def enqueue_publication_package(
    project_id: int,
    analysis_version_id: int,
    username: str = None,
    include_raw_data: bool = True,
    include_traces: bool = True,
    include_figures: bool = True,
    exclude_constructs: List[int] = None
) -> str:
    """
    Enqueue generation of a publication-ready package.

    PRD Reference: Section 0.11 - Publication Package Architecture

    Args:
        project_id: Project to export
        analysis_version_id: Analysis version to include
        username: User who initiated export
        include_raw_data: Include raw BioTek files (bit-for-bit)
        include_traces: Include MCMC traces (NetCDF)
        include_figures: Include all generated figures
        exclude_constructs: Optional list of construct IDs to exclude

    Returns:
        task_id: ID for progress tracking
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Publication package generation"

    progress = TaskService.create_task_progress(
        task_type=TaskType.DATA_EXPORT,
        name=name,
        project_id=project_id,
        username=username,
        extra_data={
            "analysis_version_id": analysis_version_id,
            "include_raw_data": include_raw_data,
            "include_traces": include_traces,
            "include_figures": include_figures,
            "exclude_constructs": exclude_constructs or [],
            "export_type": "publication_package"
        }
    )

    # Queue the task
    _publication_package_task(
        progress.task_id,
        project_id,
        analysis_version_id,
        include_raw_data,
        include_traces,
        include_figures,
        exclude_constructs or []
    )

    return progress.task_id


def enqueue_data_export(
    project_id: int,
    export_format: str = "csv",
    username: str = None,
    include_raw: bool = True,
    include_fitted: bool = True,
    include_hierarchical: bool = True
) -> str:
    """
    Enqueue a data export task.

    PRD Reference: F10.1-F10.3 - Export formats.

    Args:
        project_id: Project to export
        export_format: Format ("csv", "json", "excel")
        username: User who initiated
        include_raw: Include raw data
        include_fitted: Include fitted parameters
        include_hierarchical: Include hierarchical results

    Returns:
        task_id: ID for progress tracking
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Data export ({export_format.upper()})"

    progress = TaskService.create_task_progress(
        task_type=TaskType.DATA_EXPORT,
        name=name,
        project_id=project_id,
        username=username,
        extra_data={
            "export_format": export_format,
            "include_raw": include_raw,
            "include_fitted": include_fitted,
            "include_hierarchical": include_hierarchical,
            "export_type": "data_export"
        }
    )

    # Queue the task
    _data_export_task(
        progress.task_id,
        project_id,
        export_format,
        include_raw,
        include_fitted,
        include_hierarchical
    )

    return progress.task_id


def enqueue_figure_export(
    project_id: int,
    figure_types: List[str],
    export_format: str = "png",
    username: str = None,
    combined_pdf: bool = False
) -> str:
    """
    Enqueue figure export task.

    PRD Reference: F10.5-F10.6 - Figure export (PNG, SVG, PDF).

    Args:
        project_id: Project to export figures from
        figure_types: Types of figures ("forest", "violin", "curves", "heatmap")
        export_format: Image format ("png", "svg", "pdf")
        username: User who initiated
        combined_pdf: Combine all figures into single PDF

    Returns:
        task_id: ID for progress tracking
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Figure export ({len(figure_types)} figures)"

    progress = TaskService.create_task_progress(
        task_type=TaskType.DATA_EXPORT,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=len(figure_types),
        extra_data={
            "figure_types": figure_types,
            "export_format": export_format,
            "combined_pdf": combined_pdf,
            "export_type": "figure_export"
        }
    )

    # Queue the task
    _figure_export_task(
        progress.task_id,
        project_id,
        figure_types,
        export_format,
        combined_pdf
    )

    return progress.task_id


@huey.task()
def _publication_package_task(
    task_id: str,
    project_id: int,
    analysis_version_id: int,
    include_raw_data: bool,
    include_traces: bool,
    include_figures: bool,
    exclude_constructs: List[int]
):
    """
    Background task for publication package generation.

    PRD Reference: Section 0.11 - Package structure and contents.

    Package structure:
    - raw_data/           (bit-for-bit copies)
    - processed_data/     (CSV exports)
    - analysis_checkpoints/ (NetCDF/JSON)
    - figures/            (all included)
    - audit_log/          (MD + JSON)
    - methods_summary/    (structured)
    - reproducibility_manifest.json
    - datacite_metadata.json
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        # Import service
        from app.services.publication_package_service import PublicationPackageService
        from app.models.project import Project

        project = Project.query.get(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        package_service = PublicationPackageService()

        # Define progress steps
        steps = []
        if include_raw_data:
            steps.append(("raw_data", "Copying raw data files"))
        steps.append(("processed", "Exporting processed data"))
        if include_traces:
            steps.append(("traces", "Exporting MCMC traces"))
        if include_figures:
            steps.append(("figures", "Generating figures"))
        steps.append(("audit", "Generating audit log"))
        steps.append(("methods", "Generating methods summary"))
        steps.append(("manifest", "Creating manifest"))
        steps.append(("package", "Creating package archive"))

        total_steps = len(steps)

        # Create output directory
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        package_name = f"{project.name_slug}_{timestamp}"
        output_dir = Path(f"data/projects/{project.name_slug}/exports/{package_name}")
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, (step_name, step_desc) in enumerate(steps):
            progress.update_progress(
                progress=i / total_steps,
                current_step=step_desc,
                completed_steps=i
            )

            if step_name == "raw_data":
                package_service.export_raw_data(
                    project_id=project_id,
                    output_dir=output_dir / "raw_data"
                )
            elif step_name == "processed":
                package_service.export_processed_results(
                    project_id=project_id,
                    analysis_version_id=analysis_version_id,
                    output_dir=output_dir / "processed_data",
                    exclude_constructs=exclude_constructs
                )
            elif step_name == "traces":
                package_service.export_mcmc_traces_netcdf(
                    analysis_version_id=analysis_version_id,
                    output_dir=output_dir / "analysis_checkpoints"
                )
            elif step_name == "figures":
                package_service.export_all_figures(
                    project_id=project_id,
                    analysis_version_id=analysis_version_id,
                    output_dir=output_dir / "figures"
                )
            elif step_name == "audit":
                package_service.export_audit_log(
                    project_id=project_id,
                    output_dir=output_dir / "audit_log"
                )
            elif step_name == "methods":
                package_service.export_methods_summary(
                    project_id=project_id,
                    analysis_version_id=analysis_version_id,
                    output_dir=output_dir / "methods_summary"
                )
            elif step_name == "manifest":
                package_service.create_reproducibility_manifest(
                    project_id=project_id,
                    analysis_version_id=analysis_version_id,
                    output_dir=output_dir
                )
            elif step_name == "package":
                # Create final zip archive
                archive_path = package_service.create_package_archive(
                    source_dir=output_dir,
                    output_path=output_dir.parent / f"{package_name}.zip"
                )

        # Final update
        progress.update_progress(
            progress=1.0,
            current_step="Package complete",
            completed_steps=total_steps
        )

        archive_path = output_dir.parent / f"{package_name}.zip"
        summary = f"Created publication package: {archive_path.name}"

        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "package_path": str(archive_path),
            "package_name": package_name
        }

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


@huey.task()
def _data_export_task(
    task_id: str,
    project_id: int,
    export_format: str,
    include_raw: bool,
    include_fitted: bool,
    include_hierarchical: bool
):
    """
    Background task for data export.

    PRD Reference: F10.1-F10.3 - Data export formats.
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        from app.services.export_service import ExportService
        from app.models.project import Project

        project = Project.query.get(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        export_service = ExportService()

        # Create output directory
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"data/projects/{project.name_slug}/exports/data_{timestamp}")
        output_dir.mkdir(parents=True, exist_ok=True)

        files_created = []

        if export_format == "csv":
            progress.update_progress(0.2, "Exporting CSV files")

            if include_raw:
                path = export_service.export_data_csv(
                    project_id=project_id,
                    data_type="raw",
                    output_path=output_dir / "raw_data.csv"
                )
                files_created.append(path)

            if include_fitted:
                progress.update_progress(0.5, "Exporting fitted parameters")
                path = export_service.export_data_csv(
                    project_id=project_id,
                    data_type="fitted",
                    output_path=output_dir / "fitted_parameters.csv"
                )
                files_created.append(path)

            if include_hierarchical:
                progress.update_progress(0.8, "Exporting hierarchical results")
                path = export_service.export_data_csv(
                    project_id=project_id,
                    data_type="hierarchical",
                    output_path=output_dir / "hierarchical_results.csv"
                )
                files_created.append(path)

        elif export_format == "json":
            progress.update_progress(0.3, "Generating JSON export")
            path = export_service.export_data_json(
                project_id=project_id,
                output_path=output_dir / "project_data.json",
                include_raw=include_raw,
                include_fitted=include_fitted,
                include_hierarchical=include_hierarchical
            )
            files_created.append(path)

        elif export_format == "excel":
            progress.update_progress(0.3, "Generating Excel workbook")
            path = export_service.export_analysis_excel(
                project_id=project_id,
                output_path=output_dir / "analysis_results.xlsx",
                include_raw=include_raw,
                include_fitted=include_fitted,
                include_hierarchical=include_hierarchical
            )
            files_created.append(path)

        progress.update_progress(1.0, "Export complete")

        summary = f"Exported {len(files_created)} file(s) in {export_format.upper()} format"
        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "output_dir": str(output_dir),
            "files": [str(f) for f in files_created]
        }

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


@huey.task()
def _figure_export_task(
    task_id: str,
    project_id: int,
    figure_types: List[str],
    export_format: str,
    combined_pdf: bool
):
    """
    Background task for figure export.

    PRD Reference: F10.5-F10.6 - Figure exports.
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        from app.services.export_service import ExportService
        from app.models.project import Project

        project = Project.query.get(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        export_service = ExportService()

        # Create output directory
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"data/projects/{project.name_slug}/exports/figures_{timestamp}")
        output_dir.mkdir(parents=True, exist_ok=True)

        total = len(figure_types)
        exported_figures = []

        for i, fig_type in enumerate(figure_types):
            progress.update_progress(
                progress=i / total,
                current_step=f"Generating {fig_type} figure",
                completed_steps=i
            )

            # Generate figure based on type
            if export_format == "png":
                path = export_service.export_figure_png(
                    project_id=project_id,
                    figure_type=fig_type,
                    output_path=output_dir / f"{fig_type}.png"
                )
            elif export_format == "svg":
                path = export_service.export_figure_svg(
                    project_id=project_id,
                    figure_type=fig_type,
                    output_path=output_dir / f"{fig_type}.svg"
                )
            elif export_format == "pdf":
                path = export_service.export_figure_pdf(
                    project_id=project_id,
                    figure_type=fig_type,
                    output_path=output_dir / f"{fig_type}.pdf"
                )
            else:
                continue

            exported_figures.append(path)

        # Optionally combine into single PDF
        if combined_pdf and export_format != "pdf":
            progress.update_progress(0.95, "Combining figures into PDF")
            combined_path = export_service.export_figures_combined_pdf(
                figure_paths=exported_figures,
                output_path=output_dir / "all_figures.pdf"
            )
            exported_figures.append(combined_path)

        progress.update_progress(1.0, "Export complete")

        summary = f"Exported {len(exported_figures)} figure(s)"
        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "output_dir": str(output_dir),
            "figures": [str(f) for f in exported_figures]
        }

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


def enqueue_package_validation(
    package_path: str,
    username: str = None
) -> str:
    """
    Enqueue validation of a publication package.

    PRD Reference: Section 0.11 - Package validation (strict version match + 1e-4 tolerance).

    Args:
        package_path: Path to package to validate
        username: User who initiated

    Returns:
        task_id: ID for progress tracking
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Package validation"

    progress = TaskService.create_task_progress(
        task_type=TaskType.PACKAGE_VALIDATION,
        name=name,
        username=username,
        extra_data={
            "package_path": package_path,
            "export_type": "package_validation"
        }
    )

    _package_validation_task(progress.task_id, package_path)

    return progress.task_id


@huey.task()
def _package_validation_task(task_id: str, package_path: str):
    """
    Background task for package validation.

    PRD Reference: Section 0.11 - Validation with 1e-4 tolerance.
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        from app.services.package_validation_service import PackageValidationService

        validation_service = PackageValidationService()

        progress.update_progress(0.2, "Loading package")

        # Validate package
        result = validation_service.validate_package(
            package_path=package_path,
            tolerance=1e-4,
            progress_callback=lambda p, msg: progress.update_progress(
                0.2 + p * 0.7,
                msg
            )
        )

        progress.update_progress(0.95, "Generating validation report")

        if result.get('valid'):
            summary = "Package validation PASSED"
        else:
            summary = f"Package validation FAILED: {result.get('error_summary', 'Unknown error')}"

        progress.update_progress(1.0, "Validation complete")
        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "valid": result.get('valid', False),
            "details": result
        }

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}
