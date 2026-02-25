"""
Huey background tasks for long-running computations.

PRD Reference: Phase 1.5-1.9, Phase 4.11, Phase 5.2, Phase 6

Task modules:
- fitting_tasks: Batch curve fitting with parallelization (Phase 4)
- mcmc_tasks: MCMC sampling with checkpointing (Phase 5)
- export_tasks: Publication package and data export generation (Phase 6)

All tasks use the TaskProgress model for progress tracking and ETA calculation.
"""

from app.tasks.huey_config import huey

# Import task functions for registration with Huey
from app.tasks.fitting_tasks import (
    enqueue_curve_fitting,
    enqueue_single_plate_fitting,
    enqueue_refit_failed_wells,
)

from app.tasks.mcmc_tasks import (
    enqueue_mcmc_sampling,
    enqueue_mcmc_resume,
    get_incomplete_analyses,
)

from app.tasks.export_tasks import (
    enqueue_publication_package,
    enqueue_data_export,
    enqueue_figure_export,
    enqueue_package_validation,
)

__all__ = [
    # Huey instance
    'huey',

    # Fitting tasks
    'enqueue_curve_fitting',
    'enqueue_single_plate_fitting',
    'enqueue_refit_failed_wells',

    # MCMC tasks
    'enqueue_mcmc_sampling',
    'enqueue_mcmc_resume',
    'get_incomplete_analyses',

    # Export tasks
    'enqueue_publication_package',
    'enqueue_data_export',
    'enqueue_figure_export',
    'enqueue_package_validation',
]
