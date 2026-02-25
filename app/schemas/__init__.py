"""
Pydantic validation schemas for API request/response validation.

Phase 3.1: Input Validation Schemas
"""
from app.schemas.project import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    ProjectListResponse,
    CreateConstructRequest,
    UpdateConstructRequest,
    ConstructResponse,
    ConstructListResponse,
)
from app.schemas.upload import (
    UploadFileRequest,
    UploadResponse,
    ParseResponse,
    ValidateRequest,
    ValidateResponse,
    UploadStatusResponse,
)
from app.schemas.layout import (
    CreateLayoutRequest,
    LayoutResponse,
    AssignWellRequest,
    BulkAssignWellsRequest,
    BulkAssignLigandRequest,
    WellAssignmentResponse,
)
from app.schemas.common import (
    ErrorResponse,
    PaginationParams,
    validate_request,
    ValidationError,
)

__all__ = [
    # Project schemas
    "CreateProjectRequest",
    "UpdateProjectRequest",
    "ProjectResponse",
    "ProjectListResponse",
    "CreateConstructRequest",
    "UpdateConstructRequest",
    "ConstructResponse",
    "ConstructListResponse",
    # Upload schemas
    "UploadFileRequest",
    "UploadResponse",
    "ParseResponse",
    "ValidateRequest",
    "ValidateResponse",
    "UploadStatusResponse",
    # Layout schemas
    "CreateLayoutRequest",
    "LayoutResponse",
    "AssignWellRequest",
    "BulkAssignWellsRequest",
    "BulkAssignLigandRequest",
    "WellAssignmentResponse",
    # Common
    "ErrorResponse",
    "PaginationParams",
    "validate_request",
    "ValidationError",
]
