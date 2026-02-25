"""
Upload callbacks - facade module for backwards compatibility.

Phase 4 refactoring: Split into focused modules:
- upload_utils.py: Utility functions (parsing, validation, temperature QC)
- upload_form_callbacks.py: File handling and form control callbacks
- upload_processing_callbacks.py: Validation, preview, submission callbacks
"""
from app.callbacks.upload_form_callbacks import register_upload_form_callbacks
from app.callbacks.upload_processing_callbacks import register_upload_processing_callbacks

# Re-export utility functions for backwards compatibility
from app.callbacks.upload_utils import (  # noqa: F401
    TEMPERATURE_QC_THRESHOLD,
    FILENAME_DATE_PATTERNS,
    IDENTIFIER_DATE_PATTERNS,
    extract_identifier_from_filename,
    extract_date_from_content,
    parse_uploaded_file,
    parse_biotek_content_safe,
    validate_upload_file,
    _get_format_from_filename,
    _check_temperature_qc_for_validation,
    check_temperature_qc,
    detect_temperature_deviation,
    generate_temperature_warning_message,
    create_temperature_qc_summary,
    get_affected_temperature_timepoints,
    add_temperature_qc_warnings,
    prepare_upload_preview,
    create_preview_panel,
    handle_file_upload,
    handle_layout_selection,
    process_upload,
    validate_layout_match,
    get_suppressible_warnings,
    filter_suppressed_warnings,
    validate_upload_form,
    get_available_layouts,
    get_available_sessions,
)


def register_upload_callbacks(app):
    """Register all upload-related callbacks."""
    register_upload_form_callbacks(app)
    register_upload_processing_callbacks(app)
