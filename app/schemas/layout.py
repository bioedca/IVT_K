"""
Layout validation schemas.

Pydantic models for request/response validation on layout endpoints.
"""
import re
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


# Well position pattern: A-P (rows) followed by 1-24 (columns)
WELL_POSITION_PATTERN = re.compile(r'^[A-P](?:[1-9]|1[0-9]|2[0-4])$')


def validate_well_position(position: str) -> str:
    """Validate and normalize well position format."""
    pos = position.strip().upper()
    if not WELL_POSITION_PATTERN.match(pos):
        raise ValueError(f"Invalid well position format: {position}. Expected format: A1-P24")
    return pos


class CreateLayoutRequest(BaseSchema):
    """Request schema for creating a new layout."""

    name: str = Field(..., min_length=1, max_length=255, description="Layout name")
    plate_format: Literal["96", "384"] | None = Field(None, description="Plate format (defaults to project format)")
    is_template: bool = Field(True, description="Whether this is a template")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Layout name cannot be empty or whitespace only")
        return v.strip()


class AssignWellRequest(BaseSchema):
    """Request schema for assigning a single well."""

    well_position: str = Field(..., description="Position (e.g., 'A1')")
    construct_id: int | None = Field(None, gt=0, description="Construct ID (required for sample wells)")
    well_type: Literal[
        "sample",
        "blank",
        "negative_control_no_template",
        "negative_control_no_dye",
        "empty"
    ] = Field("sample", description="Type of well")
    paired_with: str | None = Field(None, description="Paired control position")
    replicate_group: str | None = Field(None, max_length=100, description="Replicate group name")
    ligand_concentration: float | None = Field(None, ge=0, description="Ligand concentration")

    @field_validator("well_position")
    @classmethod
    def validate_position(cls, v: str) -> str:
        return validate_well_position(v)

    @field_validator("paired_with")
    @classmethod
    def validate_paired_position(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_well_position(v)
        return v


class BulkAssignWellsRequest(BaseSchema):
    """Request schema for bulk well assignment."""

    well_positions: list[str] = Field(..., min_length=1, max_length=384, description="List of positions")
    construct_id: int | None = Field(None, gt=0, description="Construct ID")
    well_type: Literal[
        "sample",
        "blank",
        "negative_control_no_template",
        "negative_control_no_dye",
        "empty"
    ] = Field("sample", description="Type of wells")
    replicate_group: str | None = Field(None, max_length=100, description="Replicate group name")
    ligand_concentration: float | None = Field(None, ge=0, description="Ligand concentration")

    @field_validator("well_positions")
    @classmethod
    def validate_positions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("well_positions list cannot be empty")
        validated = []
        for pos in v:
            validated.append(validate_well_position(pos))
        # Check for duplicates
        if len(validated) != len(set(validated)):
            raise ValueError("Duplicate well positions not allowed")
        return validated


class BulkAssignLigandRequest(BaseSchema):
    """Request schema for bulk ligand assignment."""

    well_positions: list[str] = Field(..., min_length=1, max_length=384, description="List of positions")
    ligand_concentration: float = Field(..., ge=0, description="Ligand concentration")

    @field_validator("well_positions")
    @classmethod
    def validate_positions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("well_positions list cannot be empty")
        validated = []
        for pos in v:
            validated.append(validate_well_position(pos))
        if len(validated) != len(set(validated)):
            raise ValueError("Duplicate well positions not allowed")
        return validated


class WellAssignmentResponse(BaseSchema):
    """Response schema for a well assignment."""

    model_config = {"extra": "ignore"}

    id: int
    well_position: str
    construct_id: int | None = None
    well_type: str
    paired_with: str | None = None
    replicate_group: str | None = None
    ligand_concentration: float | None = None


class LayoutResponse(BaseSchema):
    """Response schema for a layout."""

    model_config = {"extra": "ignore"}

    id: int
    project_id: int | None = None
    name: str
    version: int | None = None
    plate_format: str
    rows: int
    cols: int
    is_template: bool
    is_draft: bool
    total_wells: int
    assigned_wells: int | None = None


class LayoutListResponse(BaseSchema):
    """Response schema for layout list."""

    model_config = {"extra": "ignore"}

    layouts: list[LayoutResponse]
