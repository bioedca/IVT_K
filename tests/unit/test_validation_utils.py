"""Tests for app.utils.validation shared validation utilities."""
import enum

import pytest

from app.utils.validation import (
    parse_bool_param,
    validate_enum_value,
    validate_non_empty_list,
    validate_positive_id,
    validate_required_fields,
)


class SampleEnum(str, enum.Enum):
    """Test enum for validation tests."""
    ALPHA = "alpha"
    BETA = "beta"
    GAMMA = "gamma"


class TestValidateRequiredFields:
    """Tests for validate_required_fields()."""

    def test_all_fields_present(self):
        data = {"name": "test", "value": 42}
        assert validate_required_fields(data, ["name", "value"]) is None

    def test_missing_field(self):
        data = {"name": "test"}
        error = validate_required_fields(data, ["name", "value"])
        assert error == "Missing required field: value"

    def test_empty_data(self):
        error = validate_required_fields({}, ["name"])
        assert error == "Request body required"

    def test_none_data(self):
        error = validate_required_fields(None, ["name"])
        assert error == "Request body required"

    def test_empty_fields_list(self):
        data = {"name": "test"}
        assert validate_required_fields(data, []) is None

    def test_first_missing_field_reported(self):
        data = {"unrelated": "value"}
        error = validate_required_fields(data, ["a", "b", "c"])
        assert error == "Missing required field: a"

    def test_field_with_none_value_passes(self):
        """Field present but None still passes (presence check only)."""
        data = {"name": None}
        assert validate_required_fields(data, ["name"]) is None


class TestValidateEnumValue:
    """Tests for validate_enum_value()."""

    def test_valid_value(self):
        result, error = validate_enum_value("alpha", SampleEnum, "sample")
        assert result == SampleEnum.ALPHA
        assert error is None

    def test_invalid_value(self):
        result, error = validate_enum_value("invalid", SampleEnum, "sample")
        assert result is None
        assert "Invalid sample: invalid" in error
        assert "alpha" in error
        assert "beta" in error

    def test_valid_values_listed_in_error(self):
        _, error = validate_enum_value("bad", SampleEnum, "type")
        assert "Valid values:" in error
        assert "['alpha', 'beta', 'gamma']" in error

    def test_default_field_name(self):
        _, error = validate_enum_value("bad", SampleEnum)
        assert "Invalid value: bad" in error


class TestValidatePositiveId:
    """Tests for validate_positive_id()."""

    def test_valid_positive_int(self):
        value, error = validate_positive_id(42, "project_id")
        assert value == 42
        assert error is None

    def test_valid_string_number(self):
        value, error = validate_positive_id("7", "id")
        assert value == 7
        assert error is None

    def test_zero(self):
        value, error = validate_positive_id(0, "id")
        assert value is None
        assert "positive integer" in error

    def test_negative(self):
        value, error = validate_positive_id(-1, "id")
        assert value is None
        assert "positive integer" in error

    def test_non_numeric_string(self):
        value, error = validate_positive_id("abc", "id")
        assert value is None
        assert "positive integer" in error

    def test_none_value(self):
        value, error = validate_positive_id(None, "id")
        assert value is None
        assert "positive integer" in error

    def test_field_name_in_error(self):
        _, error = validate_positive_id(-1, "session_id")
        assert "session_id" in error


class TestValidateNonEmptyList:
    """Tests for validate_non_empty_list()."""

    def test_valid_list(self):
        assert validate_non_empty_list([1, 2, 3], "items") is None

    def test_empty_list(self):
        error = validate_non_empty_list([], "items")
        assert "non-empty list" in error

    def test_none_value(self):
        error = validate_non_empty_list(None, "items")
        assert "non-empty list" in error

    def test_non_list_type(self):
        error = validate_non_empty_list("not a list", "items")
        assert "non-empty list" in error

    def test_field_name_in_error(self):
        error = validate_non_empty_list([], "construct_ids")
        assert "construct_ids" in error

    def test_single_element_list(self):
        assert validate_non_empty_list([1], "items") is None


class TestParseBoolParam:
    """Tests for parse_bool_param()."""

    def test_true_lowercase(self):
        assert parse_bool_param("true") is True

    def test_true_mixed_case(self):
        assert parse_bool_param("True") is True

    def test_true_uppercase(self):
        assert parse_bool_param("TRUE") is True

    def test_false_string(self):
        assert parse_bool_param("false") is False

    def test_none_default_false(self):
        assert parse_bool_param(None) is False

    def test_none_default_true(self):
        assert parse_bool_param(None, default=True) is True

    def test_empty_string(self):
        assert parse_bool_param("") is False

    def test_arbitrary_string(self):
        assert parse_bool_param("yes") is False

    def test_numeric_string(self):
        assert parse_bool_param("1") is False
