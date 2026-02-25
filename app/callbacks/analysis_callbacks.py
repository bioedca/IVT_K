"""
Analysis callbacks - facade module for backwards compatibility.

Phase 4 refactoring: Split from a single 3,480-line file into 5 focused
callback modules plus a shared utilities module:

- analysis_version_callbacks: Version selection and results loading
- analysis_visualization_callbacks: Tables, charts, diagnostics display
- analysis_execution_callbacks: Run modal, progress polling, version refresh
- analysis_comparison_callbacks: Cross-family comparison features
- analysis_fitting_callbacks: Curve fitting workflow (plate selection, fitting, results)
- analysis_utils: Shared helper functions (_extract_tier_info, fold-change computation, etc.)
"""
from app.callbacks.analysis_version_callbacks import register_analysis_version_callbacks
from app.callbacks.analysis_visualization_callbacks import register_analysis_visualization_callbacks
from app.callbacks.analysis_execution_callbacks import register_analysis_execution_callbacks
from app.callbacks.analysis_comparison_callbacks import register_analysis_comparison_callbacks
from app.callbacks.analysis_fitting_callbacks import register_analysis_fitting_callbacks

# Re-export utility functions for any external code that imports them from here
from app.callbacks.analysis_utils import (  # noqa: F401
    _extract_tier_info,
    _get_pooled_fc,
    _fc_dict_from_log,
    _compute_derived_fc_from_db,
    _compute_cross_family_fc_from_db,
    _compute_custom_fc,
    dmc_text_dimmed,
)


def register_analysis_callbacks(app):
    """Register all analysis results callbacks."""
    register_analysis_version_callbacks(app)
    register_analysis_visualization_callbacks(app)
    register_analysis_execution_callbacks(app)
    register_analysis_comparison_callbacks(app)
    register_analysis_fitting_callbacks(app)
