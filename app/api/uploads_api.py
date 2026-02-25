"""
Upload API endpoints for IVT Kinetics Analyzer.

Phase 5: API and Scripts
PRD Reference: Section 4.1

Phase 1 Security Fix: Database-backed upload storage with secure IDs.
Phase 3.3: Rate limiting applied consistently.

Endpoints:
- POST /api/uploads/              Upload new data file
- POST /api/uploads/{id}/parse    Parse uploaded file
- POST /api/uploads/{id}/validate Validate against layout
- GET  /api/uploads/{id}/status   Get upload/parsing status
"""
import base64
from typing import Dict, Any, List

from flask import Blueprint, jsonify, request, g

from app.extensions import db
from app.models import Project, PlateLayout, AuditLog, Upload, UploadStatus
from app.services.upload_service import (
    UploadService, UploadValidationError, UploadProcessingError
)
from app.parsers import parse_biotek_content, BioTekParseError
from app.api.middleware import api_protection
from app.utils.validation import validate_positive_id
from app.logging_config import get_logger

logger = get_logger(__name__)

# Create Blueprint
uploads_api = Blueprint('uploads_api', __name__, url_prefix='/api/uploads')


# Maximum file size for uploads (10 MB)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _get_username() -> str:
    """Get sanitized username from request context or header."""
    if hasattr(g, 'username'):
        return g.username
    return request.headers.get('X-Username', 'anonymous')


def _get_client_ip() -> str:
    """Get client IP address from request."""
    if hasattr(g, 'client_ip'):
        return g.client_ip
    return request.remote_addr or 'unknown'


# ==================== POST /api/uploads/ ====================

@uploads_api.route('/', methods=['POST'])
@api_protection(limiter_type="upload")
def upload_file():
    """
    Upload a new data file.

    Request body:
        - project_id: Project ID (required)
        - layout_id: Layout ID (required)
        - filename: Original filename (required)
        - content: File content as base64 or plain text (required)
        - content_encoding: "base64" or "text" (default: "base64")
        - session_id: Optional existing session ID
        - process: If true, auto-process after validation (default: false)

    Headers:
        - X-Username: User uploading the file

    Returns:
        Upload ID (UUID) and status
    """
    data = request.get_json() or {}
    username = _get_username()
    client_ip = _get_client_ip()

    # Validate required fields
    project_id = data.get('project_id')
    layout_id = data.get('layout_id')
    filename = data.get('filename')
    content = data.get('content')

    if not project_id:
        return jsonify({"error": "project_id is required"}), 400
    if not layout_id:
        return jsonify({"error": "layout_id is required"}), 400
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not content:
        return jsonify({"error": "content is required"}), 400

    # Validate project_id and layout_id are positive integers
    project_id, error = validate_positive_id(project_id, "project_id")
    if error:
        return jsonify({"error": error}), 400
    layout_id, error = validate_positive_id(layout_id, "layout_id")
    if error:
        return jsonify({"error": error}), 400

    # Check project exists
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": f"Project {project_id} not found"}), 404

    if project.is_archived:
        return jsonify({"error": "Cannot upload to archived project"}), 400

    # Check layout exists
    layout = PlateLayout.query.get(layout_id)
    if not layout:
        return jsonify({"error": f"Layout {layout_id} not found"}), 404

    if layout.project_id != project_id:
        return jsonify({"error": "Layout does not belong to this project"}), 400

    # Decode content if base64
    content_encoding = data.get('content_encoding', 'base64')
    try:
        if content_encoding == 'base64':
            # Check encoded size before decoding to prevent OOM
            # Base64 encodes 3 bytes as 4 chars, so decoded ≈ 3/4 of encoded
            encoded_size = len(content)
            estimated_decoded_size = (encoded_size * 3) // 4
            if estimated_decoded_size > MAX_UPLOAD_SIZE_BYTES:
                max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
                return jsonify({
                    "error": f"File too large. Maximum allowed: {max_mb:.0f} MB"
                }), 413
            file_content = base64.b64decode(content).decode('utf-8')
        else:
            file_content = content
    except (ValueError, UnicodeDecodeError):
        return jsonify({"error": "Failed to decode content"}), 400

    # Check file size
    content_size = len(file_content.encode('utf-8'))
    if content_size > MAX_UPLOAD_SIZE_BYTES:
        size_mb = content_size / (1024 * 1024)
        max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        return jsonify({
            "error": f"File too large ({size_mb:.1f} MB). Maximum allowed: {max_mb:.0f} MB"
        }), 413

    # Determine file format from filename
    file_format = 'txt'
    if filename.endswith('.csv'):
        file_format = 'csv'
    elif filename.endswith('.xlsx') or filename.endswith('.xls'):
        file_format = 'xlsx'
    elif filename.endswith('.tsv'):
        file_format = 'tsv'

    # Validate session_id if provided
    session_id = data.get('session_id')
    if session_id is not None:
        session_id, error = validate_positive_id(session_id, "session_id")
        if error:
            return jsonify({"error": error}), 400

    # Create upload record in database
    try:
        upload = Upload.create(
            project_id=project_id,
            layout_id=layout_id,
            filename=filename,
            content=file_content,
            username=username,
            client_ip=client_ip,
            session_id=session_id,
            file_format=file_format
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create upload"}), 500

    # Log the upload
    AuditLog.log_action(
        username=username,
        action_type="upload_started",
        entity_type="upload",
        entity_id=upload.id,
        project_id=project_id,
        changes=[{"field": "filename", "old": None, "new": filename}],
        details={"client_ip": client_ip, "upload_id": upload.upload_id}
    )
    db.session.commit()

    response = {
        "upload_id": upload.upload_id,
        "status": upload.status.value,
        "filename": filename,
        "project_id": project_id,
        "layout_id": layout_id,
        "session_id": session_id,
        "message": "File uploaded successfully. Use /parse to parse the file."
    }

    # Auto-process if requested
    if data.get('process'):
        # Parse and validate in one go
        parse_result = _do_parse(upload)
        if parse_result.get('status') == 'parsed':
            validate_result = _do_validate(upload, [])
            if validate_result.get('is_valid'):
                try:
                    process_result = _do_process(upload, username)
                    response.update(process_result)
                except Exception:
                    logger.exception("Unexpected error processing upload")
                    response['process_error'] = 'An internal error occurred during processing.'

    return jsonify(response), 201


# ==================== POST /api/uploads/{id}/parse ====================

def _do_parse(upload: Upload) -> Dict[str, Any]:
    """Internal parse function."""
    if upload is None:
        return {"error": "Upload not found"}

    content = upload.content
    if content is None:
        return {"error": "Upload content not available (may have expired)"}

    file_format = upload.file_format

    try:
        upload.update_status(UploadStatus.PARSING)
        parsed = parse_biotek_content(content, file_format)

        metadata = {
            'plate_format': parsed.plate_format,
            'temperature_setpoint': parsed.temperature_setpoint,
            'num_timepoints': parsed.num_timepoints,
            'num_wells': parsed.num_wells
        }

        upload.set_metadata(metadata)
        upload.update_status(UploadStatus.PARSED)
        # Store parsed data in memory for validation (not persisted)
        upload._parsed_data = parsed
        db.session.commit()

        return {
            'status': 'parsed',
            'metadata': metadata
        }

    except BioTekParseError as e:
        logger.warning("BioTek parse error", error=str(e))
        upload.update_status(UploadStatus.PARSE_FAILED, errors=[str(e)])
        db.session.commit()
        return {
            'status': 'parse_failed',
            'error': str(e)
        }


@uploads_api.route('/<upload_id>/parse', methods=['POST'])
@api_protection(limiter_type="write")
def parse_upload(upload_id: str):
    """
    Parse an uploaded file.

    Extracts metadata and validates file format.

    Returns:
        Status and metadata on success
    """
    upload = Upload.get_by_upload_id(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found or expired"}), 404

    if upload.status not in [UploadStatus.PENDING, UploadStatus.PARSE_FAILED]:
        return jsonify({
            "upload_id": upload.upload_id,
            "status": upload.status.value,
            "metadata": upload.parsed_metadata,
            "message": "File already parsed"
        })

    result = _do_parse(upload)

    if 'error' in result:
        return jsonify({
            "upload_id": upload.upload_id,
            "status": "parse_failed",
            "error": result['error']
        }), 400

    return jsonify({
        "upload_id": upload.upload_id,
        "status": result['status'],
        "metadata": result['metadata']
    })


# ==================== POST /api/uploads/{id}/validate ====================

def _do_validate(upload: Upload, suppress_warnings: List[str]) -> Dict[str, Any]:
    """Internal validation function."""
    if upload is None:
        return {"error": "Upload not found"}

    project_id = upload.project_id
    layout_id = upload.layout_id
    content = upload.content
    file_format = upload.file_format

    if content is None:
        return {"error": "Upload content not available (may have expired)"}

    try:
        upload.update_status(UploadStatus.VALIDATING)
        validation = UploadService.validate_upload(
            project_id=project_id,
            layout_id=layout_id,
            file_content=content,
            file_format=file_format
        )

        # Filter suppressed warnings
        active_warnings = [
            {
                'code': w.code,
                'message': w.message,
                'suppressible': w.suppressible,
                'details': w.details
            }
            for w in validation.warnings
            if w.code not in suppress_warnings
        ]

        validation_result = {
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': active_warnings,
            'matching': {
                'matched_wells': validation.matched_wells,
                'unmatched_wells': validation.unmatched_wells,
                'negative_control_count': validation.negative_control_count
            }
        }

        new_status = UploadStatus.VALIDATED if validation.is_valid else UploadStatus.VALIDATION_FAILED
        upload.set_validation_result(validation_result)
        upload.update_status(new_status, errors=validation.errors if not validation.is_valid else None)
        db.session.commit()

        return validation_result

    except UploadValidationError as e:
        logger.warning("Upload validation error", error=str(e))
        upload.update_status(UploadStatus.VALIDATION_FAILED, errors=[str(e)])
        db.session.commit()
        return {
            'is_valid': False,
            'errors': [str(e)],
            'warnings': []
        }


@uploads_api.route('/<upload_id>/validate', methods=['POST'])
@api_protection(limiter_type="write")
def validate_upload(upload_id: str):
    """
    Validate an uploaded file against the layout.

    Request body:
        - suppress_warnings: List of warning codes to suppress

    Returns:
        Validation result with errors and warnings
    """
    upload = Upload.get_by_upload_id(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found or expired"}), 404

    # Ensure file is parsed first
    if upload.status == UploadStatus.PENDING:
        parse_result = _do_parse(upload)
        if 'error' in parse_result:
            return jsonify({
                "upload_id": upload.upload_id,
                "is_valid": False,
                "errors": [parse_result['error']],
                "warnings": []
            })

    if upload.status == UploadStatus.PARSE_FAILED:
        return jsonify({
            "upload_id": upload.upload_id,
            "is_valid": False,
            "errors": upload.errors or ["File parsing failed"],
            "warnings": []
        })

    # Get suppressed warnings (use silent=True to handle missing Content-Type)
    data = request.get_json(silent=True) or {}
    suppress_warnings = data.get('suppress_warnings', [])

    result = _do_validate(upload, suppress_warnings)

    return jsonify({
        "upload_id": upload.upload_id,
        **result
    })


# ==================== GET /api/uploads/{id}/status ====================

@uploads_api.route('/<upload_id>/status', methods=['GET'])
@api_protection(limiter_type="read")
def get_upload_status(upload_id: str):
    """
    Get the status of an upload.

    Returns:
        Upload status, metadata, and validation results
    """
    upload = Upload.get_by_upload_id(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found or expired"}), 404

    response = {
        "upload_id": upload.upload_id,
        "status": upload.status.value,
        "filename": upload.filename,
        "project_id": upload.project_id,
        "layout_id": upload.layout_id,
        "session_id": upload.session_id,
        "created_at": upload.created_at.isoformat() if upload.created_at else None,
        "expires_at": upload.expires_at.isoformat() if upload.expires_at else None
    }

    # Include metadata if parsed
    if upload.parsed_metadata:
        response['metadata'] = upload.parsed_metadata

    # Include validation result if validated
    if upload.validation_result:
        response['validation'] = upload.validation_result

    # Include any errors
    if upload.errors:
        response['errors'] = upload.errors

    return jsonify(response)


# ==================== Helper: Process Upload ====================

def _do_process(upload: Upload, username: str) -> Dict[str, Any]:
    """Process a validated upload to create plate records."""
    if upload is None:
        raise UploadProcessingError("Upload not found")

    if upload.status != UploadStatus.VALIDATED:
        raise UploadProcessingError("Upload must be validated before processing")

    content = upload.content
    if content is None:
        raise UploadProcessingError("Upload content not available (may have expired)")

    try:
        upload.update_status(UploadStatus.PROCESSING)
        result = UploadService.process_upload(
            project_id=upload.project_id,
            layout_id=upload.layout_id,
            session_id=upload.session_id,
            file_content=content,
            file_format=upload.file_format,
            original_filename=upload.filename,
            plate_number=1,
            username=username
        )

        upload.mark_processed(result.plate_id, result.session_id)
        db.session.commit()

        return {
            'status': 'processed',
            'plate_id': result.plate_id,
            'session_id': result.session_id,
            'wells_created': result.wells_created,
            'data_points_created': result.data_points_created
        }

    except (UploadValidationError, UploadProcessingError) as e:
        logger.warning("Upload processing error in _do_process", error=str(e))
        upload.update_status(UploadStatus.PROCESS_FAILED, errors=[str(e)])
        db.session.commit()
        raise


@uploads_api.route('/<upload_id>/process', methods=['POST'])
@api_protection(limiter_type="write")
def process_upload(upload_id: str):
    """
    Process a validated upload to create plate and well records.

    Headers:
        - X-Username: User processing the upload

    Returns:
        Created plate ID and well counts
    """
    username = _get_username()

    upload = Upload.get_by_upload_id(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found or expired"}), 404

    if upload.status not in [UploadStatus.VALIDATED, UploadStatus.PARSED]:
        # Try to validate first
        if upload.status == UploadStatus.PENDING:
            _do_parse(upload)

        if upload.status == UploadStatus.PARSED:
            result = _do_validate(upload, [])
            if not result.get('is_valid'):
                return jsonify({
                    "error": "Validation failed",
                    "errors": result.get('errors', [])
                }), 400

    try:
        result = _do_process(upload, username)
        return jsonify({
            "upload_id": upload.upload_id,
            **result
        })

    except UploadProcessingError as e:
        logger.warning("Upload processing error in process_upload", error=str(e))
        return jsonify({"error": str(e)}), 400


def register_uploads_api(app):
    """Register the uploads API blueprint with the Flask app."""
    app.register_blueprint(uploads_api)
