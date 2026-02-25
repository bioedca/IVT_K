"""Layout callbacks - facade module for backwards compatibility.

Phase 4 refactoring: split into focused modules:
- layout_utils.py: Utility functions (well click, selection, assignment, validation, save/publish)
- layout_grid_callbacks.py: Grid interaction callbacks (well clicks, selection helpers, grid visuals)
- layout_assignment_callbacks.py: Assignment management callbacks (assign/clear, save, publish, import)
"""
from app.callbacks.layout_grid_callbacks import register_layout_grid_callbacks
from app.callbacks.layout_assignment_callbacks import register_layout_assignment_callbacks

# Re-export utility functions for backwards compatibility
from app.callbacks.layout_utils import (  # noqa: F401
    handle_well_click,
    compute_selection_range,
    merge_selections,
    handle_selection_helper,
    handle_assignment,
    handle_clear_selection,
    validate_assignment,
    get_layout_validation_status,
    handle_layout_save,
    handle_layout_publish,
)


def register_layout_callbacks(app):
    """Register all layout editor callbacks."""
    register_layout_grid_callbacks(app)
    register_layout_assignment_callbacks(app)
