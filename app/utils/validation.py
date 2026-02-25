"""
Shared validation utilities for API endpoints.

Phase 7: Cross-Cutting Concerns
Provides reusable validation functions for common API patterns.
"""
from enum import Enum
from typing import Any, Optional


def validate_required_fields(data: dict, fields: list[str]) -> Optional[str]:
    """
    Check that all required fields are present in data dict.

    Returns error message string if validation fails, None if all fields present.
    """
    if not data:
        return "Request body required"
    for field in fields:
        if field not in data:
            return f"Missing required field: {field}"
    return None


def validate_enum_value(value: str, enum_class: type[Enum], field_name: str = "value") -> tuple[Optional[Enum], Optional[str]]:
    """
    Validate and convert a string to an enum value.

    Returns (enum_value, None) on success, or (None, error_message) on failure.
    """
    try:
        return enum_class(value), None
    except (ValueError, KeyError):
        valid_values = [e.value for e in enum_class]
        return None, f"Invalid {field_name}: {value}. Valid values: {valid_values}"


def validate_positive_id(value: Any, field_name: str = "id") -> tuple[Optional[int], Optional[str]]:
    """
    Validate that a value is a positive integer (suitable for database IDs).

    Returns (int_value, None) on success, or (None, error_message) on failure.
    """
    try:
        int_value = int(value)
        if int_value <= 0:
            return None, f"{field_name} must be a positive integer"
        return int_value, None
    except (ValueError, TypeError):
        return None, f"{field_name} must be a positive integer"


def validate_non_empty_list(value: Any, field_name: str = "items") -> Optional[str]:
    """
    Validate that a value is a non-empty list.

    Returns error message string if validation fails, None if valid.
    """
    if not value or not isinstance(value, list):
        return f"{field_name} must be a non-empty list"
    return None


def parse_bool_param(value: Optional[str], default: bool = False) -> bool:
    """
    Parse a query string parameter as a boolean.

    Treats 'true' (case-insensitive) as True, everything else as default.
    """
    if value is None:
        return default
    return str(value).lower() == "true"
