"""
Project and Construct validation schemas.

Pydantic models for request/response validation on project endpoints.
"""
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class CreateProjectRequest(BaseSchema):
    """Request schema for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    reporter_system: str = Field("iSpinach", max_length=100, description="Fluorogenic aptamer system")
    plate_format: Literal["96", "384"] = Field("384", description="Plate format")
    precision_target: float = Field(0.3, ge=0.01, le=1.0, description="Target CI width")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Project name cannot be empty or whitespace only")
        return v.strip()


class UpdateProjectRequest(BaseSchema):
    """Request schema for updating a project."""

    model_config = {"extra": "ignore"}  # Allow partial updates

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    reporter_system: str | None = Field(None, max_length=100)
    precision_target: float | None = Field(None, ge=0.01, le=1.0)
    notes: str | None = Field(None, max_length=5000)

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Project name cannot be empty or whitespace only")
        return v.strip() if v else v


class ProjectResponse(BaseSchema):
    """Response schema for a single project."""

    model_config = {"extra": "ignore"}

    id: int
    name: str
    slug: str | None = None
    description: str | None = None
    reporter_system: str | None = None
    plate_format: str
    is_draft: bool
    is_archived: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectListResponse(BaseSchema):
    """Response schema for project list."""

    model_config = {"extra": "ignore"}

    projects: list[ProjectResponse]
    count: int


class CreateConstructRequest(BaseSchema):
    """Request schema for creating a new construct."""

    identifier: str = Field(..., min_length=1, max_length=100, description="Unique identifier")
    family: str | None = Field(None, max_length=100, description="T-box family name")
    description: str | None = Field(None, max_length=2000)
    sequence: str | None = Field(None, max_length=50000, description="DNA sequence")
    is_wildtype: bool = Field(False, description="Mark as wild-type for family")
    is_unregulated: bool = Field(False, description="Mark as reporter-only control")
    notes: str | None = Field(None, max_length=5000)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Construct identifier cannot be empty")
        # Allow alphanumeric, underscores, hyphens, and dots
        import re
        if not re.match(r'^[\w\-\.]+$', v.strip()):
            raise ValueError("Identifier can only contain letters, numbers, underscores, hyphens, and dots")
        return v.strip()

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Remove whitespace and validate DNA sequence characters
        cleaned = ''.join(v.upper().split())
        import re
        if cleaned and not re.match(r'^[ATCGN]+$', cleaned):
            raise ValueError("Sequence can only contain A, T, C, G, or N characters")
        return cleaned if cleaned else None


class UpdateConstructRequest(BaseSchema):
    """Request schema for updating a construct."""

    model_config = {"extra": "ignore"}

    identifier: str | None = Field(None, min_length=1, max_length=100)
    family: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    sequence: str | None = Field(None, max_length=50000)
    is_wildtype: bool | None = None
    is_unregulated: bool | None = None
    notes: str | None = Field(None, max_length=5000)


class ConstructResponse(BaseSchema):
    """Response schema for a single construct."""

    model_config = {"extra": "ignore"}

    id: int
    identifier: str
    family: str | None = None
    description: str | None = None
    sequence: str | None = None
    is_wildtype: bool
    is_unregulated: bool
    is_draft: bool
    is_deleted: bool = False
    display_name: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConstructListResponse(BaseSchema):
    """Response schema for construct list."""

    model_config = {"extra": "ignore"}

    constructs: list[ConstructResponse]
    count: int
