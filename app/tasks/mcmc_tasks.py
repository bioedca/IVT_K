"""
MCMC sampling background tasks with checkpoint support.

PRD Reference: Phase 5, Section 0.2, F11.2-F11.6
Implements MCMC sampling with periodic checkpointing for crash recovery.
"""
import traceback
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.tasks.huey_config import huey
from app.extensions import db
from app.models.task_progress import TaskProgress, TaskType
from app.models.analysis_version import (
    AnalysisVersion, AnalysisStatus, MCMCCheckpoint, CheckpointStatus
)

# Note: TaskService is imported lazily inside functions to avoid circular import


# Default MCMC parameters from PRD Section 2.2
DEFAULT_MCMC_CHAINS = 4
DEFAULT_MCMC_DRAWS = 2000
DEFAULT_MCMC_TUNE = 1000
DEFAULT_MCMC_THIN = 5  # Store every 5th sample = 400 stored samples
DEFAULT_CHECKPOINT_INTERVAL = 500  # Save checkpoint every 500 samples


def enqueue_mcmc_sampling(
    project_id: int,
    analysis_version_id: int,
    username: str = None,
    num_samples: int = DEFAULT_MCMC_DRAWS,
    num_chains: int = DEFAULT_MCMC_CHAINS,
    tune: int = DEFAULT_MCMC_TUNE,
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL
) -> str:
    """
    Enqueue an MCMC sampling task for hierarchical analysis.

    PRD Reference: F11.2-F11.4 - MCMC with checkpointing.

    Args:
        project_id: Project for analysis
        analysis_version_id: Analysis version to run
        username: User who initiated
        num_samples: Number of MCMC draws (default: 2000)
        num_chains: Number of chains (default: 4)
        tune: Tuning samples (default: 1000)
        checkpoint_interval: Save checkpoint every N samples (default: 500)

    Returns:
        task_id: ID for tracking progress
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"MCMC sampling: {num_samples} samples x {num_chains} chains"

    progress = TaskService.create_task_progress(
        task_type=TaskType.MCMC_SAMPLING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=num_samples * num_chains,
        extra_data={
            "analysis_version_id": analysis_version_id,
            "num_samples": num_samples,
            "num_chains": num_chains,
            "tune": tune,
            "checkpoint_interval": checkpoint_interval
        }
    )

    # Queue the actual task
    _mcmc_sampling_task(
        progress.task_id,
        project_id,
        analysis_version_id,
        num_samples,
        num_chains,
        tune,
        checkpoint_interval
    )

    return progress.task_id


def enqueue_mcmc_resume(
    project_id: int,
    analysis_version_id: int,
    username: str = None
) -> str:
    """
    Resume MCMC sampling from the latest checkpoint.

    PRD Reference: F11.5 - Resume from checkpoint on worker restart.

    Args:
        project_id: Project ID
        analysis_version_id: Analysis version to resume
        username: User who initiated

    Returns:
        task_id: ID for progress tracking

    Raises:
        ValueError: If no resumable checkpoint exists
    """
    # Find latest resumable checkpoint
    checkpoint = MCMCCheckpoint.get_resumable_checkpoint(analysis_version_id)
    if checkpoint is None:
        raise ValueError(f"No resumable checkpoint found for analysis version {analysis_version_id}")

    # Get analysis version for parameters
    analysis = AnalysisVersion.query.get(analysis_version_id)
    if analysis is None:
        raise ValueError(f"Analysis version {analysis_version_id} not found")

    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    remaining_draws = analysis.mcmc_draws - checkpoint.draw_idx
    name = f"MCMC resume: {remaining_draws} remaining draws"

    progress = TaskService.create_task_progress(
        task_type=TaskType.MCMC_SAMPLING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=remaining_draws,
        extra_data={
            "analysis_version_id": analysis_version_id,
            "checkpoint_id": checkpoint.id,
            "is_resume": True,
            "start_draw": checkpoint.draw_idx
        }
    )

    # Queue the resume task
    _mcmc_resume_task(
        progress.task_id,
        project_id,
        analysis_version_id,
        checkpoint.id
    )

    return progress.task_id


def enqueue_hierarchical_analysis(
    project_id: int,
    version_name: str,
    description: str = None,
    username: str = None,
) -> str:
    """
    Enqueue a complete hierarchical analysis task.

    This uses HierarchicalService.run_analysis which handles both
    Bayesian and Frequentist analysis with proper checkpointing.

    Args:
        project_id: Project for analysis
        version_name: Name for this analysis version
        description: Optional description
        username: User who initiated

    Returns:
        task_id: ID for tracking progress
    """
    import logging
    logger = logging.getLogger(__name__)

    from app.services.task_service import TaskService

    name = f"Hierarchical analysis: {version_name}"

    progress = TaskService.create_task_progress(
        task_type=TaskType.MCMC_SAMPLING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=100,  # Progress will be 0-100%
        extra_data={
            "version_name": version_name,
            "description": description,
        }
    )

    # Guard: Huey must enqueue, not execute in the web process
    if huey.immediate:
        logger.error("huey.immediate is True — task will run in web process!")

    # Queue the task
    result = _hierarchical_analysis_task(
        progress.task_id,
        project_id,
        version_name,
        description
    )
    logger.info(
        "Enqueued hierarchical analysis task_id=%s huey_id=%s immediate=%s",
        progress.task_id, getattr(result, 'id', '?'), huey.immediate,
    )

    return progress.task_id


@huey.task()
def _hierarchical_analysis_task(
    task_id: str,
    project_id: int,
    version_name: str,
    description: str = None
):
    """
    Background task for complete hierarchical analysis.

    Uses HierarchicalService.run_analysis which handles everything.
    """
    # Use lightweight worker app — only Flask + SQLAlchemy, no Dash/callbacks
    from app import create_worker_app
    server = create_worker_app()

    with server.app_context():
        return _hierarchical_analysis_task_impl(
            task_id, project_id, version_name, description
        )


def _hierarchical_analysis_task_impl(
    task_id: str,
    project_id: int,
    version_name: str,
    description: str = None
):
    """Implementation of hierarchical analysis task (runs within app context)."""
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        from app.models.project import Project
        from app.services.hierarchical_service import HierarchicalService, AnalysisConfig

        # Build AnalysisConfig from project settings
        project = Project.query.get(project_id)
        config = AnalysisConfig.from_project(project) if project else None

        # Progress callback to update TaskProgress
        def update_progress(stage: str, prog: float):
            progress.update_progress(
                progress=prog,
                current_step=stage,
                completed_steps=int(prog * 100)
            )

        # Run the complete analysis
        version = HierarchicalService.run_analysis(
            project_id=project_id,
            version_name=version_name,
            description=description,
            config=config,
            progress_callback=update_progress
        )

        summary = f"Analysis complete: {version_name}"
        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "analysis_version_id": version.id,
            "version_name": version_name
        }

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


@huey.task()
def _mcmc_sampling_task(
    task_id: str,
    project_id: int,
    analysis_version_id: int,
    num_samples: int,
    num_chains: int,
    tune: int,
    checkpoint_interval: int
):
    """
    Background task for MCMC sampling with checkpointing.

    PRD Reference: Section 0.2 - MCMC Crash Recovery & Checkpointing

    Args:
        task_id: TaskProgress ID
        project_id: Project being analyzed
        analysis_version_id: Analysis version ID
        num_samples: Number of draws
        num_chains: Number of chains
        tune: Tuning samples
        checkpoint_interval: Checkpoint every N samples
    """
    # Use lightweight worker app — only Flask + SQLAlchemy, no Dash/callbacks
    from app import create_worker_app
    server = create_worker_app()

    with server.app_context():
        return _mcmc_sampling_task_impl(
            task_id, project_id, analysis_version_id,
            num_samples, num_chains, tune, checkpoint_interval
        )


def _mcmc_sampling_task_impl(
    task_id: str,
    project_id: int,
    analysis_version_id: int,
    num_samples: int,
    num_chains: int,
    tune: int,
    checkpoint_interval: int
):
    """Implementation of MCMC sampling task (runs within app context)."""
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    # Get or update analysis version
    analysis = AnalysisVersion.query.get(analysis_version_id)
    if analysis is None:
        progress.fail(f"Analysis version {analysis_version_id} not found")
        return {"error": "Analysis version not found"}

    try:
        progress.start()

        # Update analysis version status
        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Import here to avoid circular imports
        from app.services.hierarchical_service import HierarchicalService
        from app.models.project import Project

        project = Project.query.get(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        # Set up checkpoint directory
        checkpoint_dir = Path(f"data/projects/{project.name_slug}/traces/checkpoints")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        hierarchical_service = HierarchicalService()

        # Create checkpoint callback for MCMC
        def checkpoint_callback(draw_idx: int, trace_data: Any, is_final: bool = False):
            """Callback to save MCMC checkpoint."""
            checkpoint_path = checkpoint_dir / f"checkpoint_{draw_idx}.nc"

            # Save trace to NetCDF
            if trace_data is not None:
                try:
                    import arviz as az
                    az.to_netcdf(trace_data, str(checkpoint_path))
                except Exception as e:
                    # Log but don't fail on checkpoint save error
                    import logging
                    logging.warning(f"Failed to save checkpoint: {e}")
                    return

            # Create checkpoint record
            checkpoint = MCMCCheckpoint.create_checkpoint(
                analysis_version_id=analysis_version_id,
                draw_idx=draw_idx,
                total_draws=num_samples,
                checkpoint_path=str(checkpoint_path),
                total_chains=num_chains,
                is_final=is_final,
                status=CheckpointStatus.COMPLETED if is_final else CheckpointStatus.IN_PROGRESS
            )
            db.session.add(checkpoint)
            db.session.commit()

            # Update progress
            progress.update_progress(
                progress=draw_idx / num_samples,
                current_step=f"MCMC sampling: {draw_idx}/{num_samples} draws",
                completed_steps=draw_idx
            )

        # Create progress callback
        def mcmc_progress_callback(draw_idx: int, total_draws: int):
            """Update task progress during MCMC."""
            progress.update_progress(
                progress=draw_idx / total_draws,
                current_step=f"Sampling: {draw_idx}/{total_draws}",
                completed_steps=draw_idx
            )

            # Save checkpoint at intervals
            if draw_idx > 0 and draw_idx % checkpoint_interval == 0:
                # Checkpoint will be saved by the hierarchical service
                pass

        # Run the hierarchical model
        result = hierarchical_service.run_bayesian_analysis(
            project_id=project_id,
            analysis_version_id=analysis_version_id,
            num_samples=num_samples,
            num_chains=num_chains,
            tune=tune,
            progress_callback=mcmc_progress_callback,
            checkpoint_callback=checkpoint_callback,
            checkpoint_interval=checkpoint_interval
        )

        # Update analysis version
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.duration_seconds = (analysis.completed_at - analysis.started_at).total_seconds()

        # Store trace file path
        if result.get('trace_path'):
            analysis.trace_file_path = result['trace_path']
            analysis.trace_thin_factor = DEFAULT_MCMC_THIN

        db.session.commit()

        # Clean up intermediate checkpoints
        MCMCCheckpoint.cleanup_for_version(analysis_version_id)

        summary = f"Completed {num_samples} samples on {num_chains} chains"
        if result.get('r_hat_max'):
            summary += f" (max R-hat: {result['r_hat_max']:.3f})"

        progress.complete(result_summary=summary)

        return {
            "task_id": task_id,
            "analysis_version_id": analysis_version_id,
            "samples": num_samples,
            "chains": num_chains
        }

    except Exception as e:
        # Create error checkpoint for debugging
        try:
            error_checkpoint = MCMCCheckpoint.create_error_checkpoint(
                analysis_version_id=analysis_version_id,
                draw_idx=0,  # Will be updated if we know actual position
                total_draws=num_samples,
                checkpoint_path="",
                error_message=str(e),
                error_traceback=traceback.format_exc()
            )
            db.session.add(error_checkpoint)

            # Update analysis version to failed
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            analysis.error_traceback = traceback.format_exc()
            analysis.completed_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception:
            pass  # Don't fail on error checkpoint

        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


@huey.task()
def _mcmc_resume_task(
    task_id: str,
    project_id: int,
    analysis_version_id: int,
    checkpoint_id: int
):
    """
    Background task to resume MCMC from a checkpoint.

    PRD Reference: F11.5 - Resume from checkpoint.

    Args:
        task_id: TaskProgress ID
        project_id: Project ID
        analysis_version_id: Analysis version to resume
        checkpoint_id: Checkpoint to resume from
    """
    # Use lightweight worker app — only Flask + SQLAlchemy, no Dash/callbacks
    from app import create_worker_app
    server = create_worker_app()

    with server.app_context():
        return _mcmc_resume_task_impl(task_id, project_id, analysis_version_id, checkpoint_id)


def _mcmc_resume_task_impl(
    task_id: str,
    project_id: int,
    analysis_version_id: int,
    checkpoint_id: int
):
    """Implementation of MCMC resume task (runs within app context)."""
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return {"error": f"TaskProgress not found for {task_id}"}

    try:
        progress.start()

        checkpoint = MCMCCheckpoint.query.get(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        analysis = AnalysisVersion.query.get(analysis_version_id)
        if analysis is None:
            raise ValueError(f"Analysis version {analysis_version_id} not found")

        # Import and load checkpoint
        from app.services.hierarchical_service import HierarchicalService
        import arviz as az

        hierarchical_service = HierarchicalService()

        # Load existing trace
        existing_trace = az.from_netcdf(checkpoint.checkpoint_path)

        # Resume sampling
        result = hierarchical_service.resume_bayesian_analysis(
            project_id=project_id,
            analysis_version_id=analysis_version_id,
            existing_trace=existing_trace,
            start_draw=checkpoint.draw_idx,
            progress_callback=lambda d, t: progress.update_progress(
                progress=(d - checkpoint.draw_idx) / (analysis.mcmc_draws - checkpoint.draw_idx),
                current_step=f"Resuming: {d}/{analysis.mcmc_draws}"
            )
        )

        # Update analysis
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(timezone.utc)
        if result.get('trace_path'):
            analysis.trace_file_path = result['trace_path']
        db.session.commit()

        summary = f"Resumed and completed MCMC sampling"
        progress.complete(result_summary=summary)

        return {"task_id": task_id, "resumed_from": checkpoint.draw_idx}

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
        return {"task_id": task_id, "error": str(e)}


def get_incomplete_analyses(project_id: int = None) -> list:
    """
    Find analysis versions that can be resumed.

    PRD Reference: F11.5 - Detect incomplete tasks on restart.

    Args:
        project_id: Optional filter by project

    Returns:
        List of (AnalysisVersion, MCMCCheckpoint) tuples
    """
    query = AnalysisVersion.query.filter(
        AnalysisVersion.status == AnalysisStatus.RUNNING
    )

    if project_id:
        query = query.filter_by(project_id=project_id)

    incomplete = []
    for analysis in query.all():
        checkpoint = MCMCCheckpoint.get_resumable_checkpoint(analysis.id)
        if checkpoint:
            incomplete.append((analysis, checkpoint))

    return incomplete
