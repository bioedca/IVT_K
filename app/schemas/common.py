"""
Common validation schemas and utilities.

Provides base classes, validators, and helper functions for API validation.
"""
from functools import wraps
from typing import Any, TypeVar, Type

from flask import request, jsonify
from pydantic import BaseModel, ConfigDict, field_validator


class ValidationError(Exception):
    """Exception raised when request validation fails."""

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_min_length=None,
        validate_assignment=True,
        extra="forbid",  # Reject unknown fields
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    details: list[dict[str, Any]] | None = None
    code: str | None = None


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    limit: int | None = None
    offset: int | None = None

    @field_validator("limit", "offset")
    @classmethod
    def validate_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("must be non-negative")
        return v


T = TypeVar("T", bound=BaseModel)


def validate_request(schema_class: Type[T]):
    """
    Decorator to validate request JSON body against a Pydantic schema.

    Usage:
        @app.route('/api/projects', methods=['POST'])
        @validate_request(CreateProjectRequest)
        def create_project(validated_data: CreateProjectRequest):
            # validated_data is a validated Pydantic model instance
            ...

    On validation error, returns 400 with error details.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get JSON body
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({
                    "error": "Request body required",
                    "details": [{"loc": ["body"], "msg": "Missing JSON body"}]
                }), 400

            # Validate against schema
            try:
                validated = schema_class.model_validate(data)
            except Exception as e:
                # Pydantic validation error
                if hasattr(e, "errors"):
                    errors = e.errors()
                    formatted_errors = [
                        {
                            "loc": list(err.get("loc", [])),
                            "msg": err.get("msg", str(err)),
                            "type": err.get("type", "validation_error"),
                        }
                        for err in errors
                    ]
                    return jsonify({
                        "error": "Validation failed",
                        "details": formatted_errors
                    }), 400
                else:
                    return jsonify({
                        "error": f"Validation failed: {e}"
                    }), 400

            # Call the wrapped function with validated data
            return f(validated, *args, **kwargs)

        return wrapper

    return decorator


def validate_query_params(schema_class: Type[T]):
    """
    Decorator to validate query parameters against a Pydantic schema.

    Usage:
        @app.route('/api/projects', methods=['GET'])
        @validate_query_params(ListProjectsParams)
        def list_projects(params: ListProjectsParams):
            ...
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Convert query params to dict
            data = request.args.to_dict()

            # Convert string values to appropriate types for common params
            for key in ["limit", "offset"]:
                if key in data:
                    try:
                        data[key] = int(data[key])
                    except (ValueError, TypeError):
                        pass

            # Convert boolean strings
            for key, value in list(data.items()):
                if isinstance(value, str) and value.lower() in ("true", "false"):
                    data[key] = value.lower() == "true"

            try:
                validated = schema_class.model_validate(data)
            except Exception as e:
                if hasattr(e, "errors"):
                    errors = e.errors()
                    formatted_errors = [
                        {
                            "loc": ["query"] + list(err.get("loc", [])),
                            "msg": err.get("msg", str(err)),
                            "type": err.get("type", "validation_error"),
                        }
                        for err in errors
                    ]
                    return jsonify({
                        "error": "Invalid query parameters",
                        "details": formatted_errors
                    }), 400
                else:
                    return jsonify({
                        "error": f"Invalid query parameters: {e}"
                    }), 400

            return f(validated, *args, **kwargs)

        return wrapper

    return decorator
