"""
Upload validation schemas.

Pydantic models for request/response validation on upload endpoints.
"""
from datetime import datetime
from typing import Literal, Any

from pydantic import Field, field_validator, model_validator

from app.schemas.common import BaseSchema


class UploadFileRequest(BaseSchema):
    """Request schema for uploading a data file."""

    project_id: int = Field(..., gt=0, description="Project ID")
    layout_id: int = Field(..., gt=0, description="Layout ID")
    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    content: str = Field(..., min_length=1, description="File content (base64 or text)")
    content_encoding: Literal["base64", "text"] = Field("base64", description="Content encoding")
    session_id: int | None = Field(None, gt=0, description="Optional existing session ID")
    process: bool = Field(False, description="Auto-process after validation")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Filename cannot be empty")
        # Validate filename doesn't contain path separators (security)
        if "/" in v or "\\" in v:
            raise ValueError("Filename cannot contain path separators")
        # Validate reasonable filename characters
        cleaned = v.strip()
        if len(cleaned) > 255:
            raise ValueError("Filename too long (max 255 characters)")
        return cleaned

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Content cannot be empty")
        # Check reasonable size limit (10MB base64 encoded is ~13.3MB)
        max_encoded_size = 15 * 1024 * 1024  # 15MB encoded
        if len(v) > max_encoded_size:
            raise ValueError(f"Content too large (max {max_encoded_size // (1024*1024)}MB encoded)")
        return v


class UploadMetadata(BaseSchema):
    """Metadata extracted from parsed file."""

    model_config = {"extra": "allow"}

    plate_format: str | None = None
    temperature_setpoint: float | None = None
    num_timepoints: int | None = None
    num_wells: int | None = None


class UploadResponse(BaseSchema):
    """Response schema for file upload."""

    model_config = {"extra": "ignore"}

    upload_id: str
    status: str
    filename: str
    project_id: int
    layout_id: int
    session_id: int | None = None
    message: str | None = None
    process_error: str | None = None


class ParseResponse(BaseSchema):
    """Response schema for parse operation."""

    model_config = {"extra": "ignore"}

    upload_id: str
    status: str
    metadata: UploadMetadata | None = None
    error: str | None = None


class ValidateRequest(BaseSchema):
    """Request schema for validation operation."""

    suppress_warnings: list[str] = Field(default_factory=list, description="Warning codes to suppress")

    @field_validator("suppress_warnings")
    @classmethod
    def validate_warning_codes(cls, v: list[str]) -> list[str]:
        # Validate each code is a reasonable string
        for code in v:
            if not isinstance(code, str) or len(code) > 50:
                raise ValueError(f"Invalid warning code: {code}")
        return v


class ValidationWarning(BaseSchema):
    """A single validation warning."""

    model_config = {"extra": "allow"}

    code: str
    message: str
    suppressible: bool = True
    details: dict[str, Any] | None = None


class ValidationMatching(BaseSchema):
    """Well matching results from validation."""

    model_config = {"extra": "allow"}

    matched_wells: int | None = None
    unmatched_wells: int | None = None
    negative_control_count: int | None = None


class ValidateResponse(BaseSchema):
    """Response schema for validation operation."""

    model_config = {"extra": "ignore"}

    upload_id: str
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)
    matching: ValidationMatching | None = None


class UploadStatusResponse(BaseSchema):
    """Response schema for upload status check."""

    model_config = {"extra": "ignore"}

    upload_id: str
    status: str
    filename: str
    project_id: int
    layout_id: int
    session_id: int | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: UploadMetadata | dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    errors: list[str] | None = None
