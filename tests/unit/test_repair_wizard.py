"""
Tests for the Interactive Repair Wizard.

Phase 3.7: Interactive Repair Wizard Tests
"""
import pytest

from app.layouts.repair_wizard import (
    create_repair_wizard_modal,
    create_step1_preview,
    create_step2_header_row,
    create_step3_skip_rows,
    create_step4_column_mapping,
    create_step5_preview_data,
    create_repair_wizard_error,
)
from app.callbacks.repair_callbacks import (
    _parse_columns_from_header,
    _parse_skip_rows_input,
    _format_row_ranges,
    open_repair_wizard,
    apply_repair_settings,
)


class TestRepairWizardLayout:
    """Tests for repair wizard layout components."""

    def test_create_repair_wizard_modal(self):
        """Test creating the repair wizard modal."""
        modal = create_repair_wizard_modal()
        assert modal is not None
        modal_str = str(modal)
        assert "repair-wizard-modal" in modal_str

    def test_step1_preview(self):
        """Test step 1 file preview component."""
        file_lines = [
            "Software Version: 3.11.19",
            "User Name: Admin",
            "Time\tT\tA1\tA2\tA3",
            "0:00:00\t37.0\t1000\t1100\t1200",
        ]

        component = create_step1_preview(file_lines, "Header not found")
        assert component is not None
        component_str = str(component)
        assert "Software Version" in component_str

    def test_step1_preview_long_lines(self):
        """Test step 1 handles long lines."""
        long_line = "A" * 200
        file_lines = [long_line]

        component = create_step1_preview(file_lines)
        # Should truncate long lines
        assert component is not None

    def test_step2_header_row(self):
        """Test step 2 header row selection."""
        file_lines = [
            "Metadata line",
            "Time\tT\tA1\tA2",
            "0:00:00\t37.0\t1000\t1100",
        ]

        component = create_step2_header_row(file_lines, suggested_row=2)
        assert component is not None
        component_str = str(component)
        assert "repair-header-row-input" in component_str

    def test_step3_skip_rows(self):
        """Test step 3 skip rows configuration."""
        file_lines = [
            "Time\tT\tA1",
            "0:00:00\t37.0\t0",
            "0:00:05\t37.0\t100",
        ]

        component = create_step3_skip_rows(file_lines, header_row=1)
        assert component is not None
        component_str = str(component)
        assert "repair-skip-rows-input" in component_str

    def test_step4_column_mapping(self):
        """Test step 4 column mapping interface."""
        columns = ["Time", "T°", "A1", "A2", "A3", "B1", "B2"]

        component = create_step4_column_mapping(columns)
        assert component is not None
        component_str = str(component)
        assert "repair-time-column" in component_str
        assert "repair-first-well-column" in component_str

    def test_step4_column_mapping_with_suggestions(self):
        """Test step 4 with auto-detected suggestions."""
        columns = ["Time", "Temperature", "A1", "A2"]
        mapping = {"time": "Time", "temperature": "Temperature", "first_well": "A1"}

        component = create_step4_column_mapping(columns, mapping)
        assert component is not None

    def test_step5_preview_data(self):
        """Test step 5 data preview."""
        preview_data = {
            "temperature_setpoint": 37.0,
        }
        sample_wells = ["A1", "A2", "A3", "B1", "B2"]

        component = create_step5_preview_data(
            preview_data=preview_data,
            num_wells=96,
            num_timepoints=60,
            sample_wells=sample_wells,
        )
        assert component is not None
        component_str = str(component)
        assert "96" in component_str
        assert "60" in component_str

    def test_repair_wizard_error(self):
        """Test error display component."""
        component = create_repair_wizard_error("File format not supported")
        assert component is not None
        component_str = str(component)
        assert "File format not supported" in component_str


class TestColumnParsing:
    """Tests for column parsing utilities."""

    def test_parse_tab_separated_columns(self):
        """Test parsing tab-separated header."""
        header = "Time\tT°\tA1\tA2\tA3"

        columns = _parse_columns_from_header(header)

        assert columns == ["Time", "T°", "A1", "A2", "A3"]

    def test_parse_comma_separated_columns(self):
        """Test parsing comma-separated header."""
        header = "Time,Temperature,A1,A2,A3"

        columns = _parse_columns_from_header(header)

        assert columns == ["Time", "Temperature", "A1", "A2", "A3"]

    def test_parse_columns_with_whitespace(self):
        """Test parsing columns with extra whitespace."""
        header = "Time\t  T°  \t A1 \t A2"

        columns = _parse_columns_from_header(header)

        assert columns == ["Time", "T°", "A1", "A2"]

    def test_parse_empty_columns_removed(self):
        """Test empty columns are removed."""
        header = "Time\t\tA1\t\tA2"

        columns = _parse_columns_from_header(header)

        assert columns == ["Time", "A1", "A2"]


class TestSkipRowsParsing:
    """Tests for skip rows input parsing."""

    def test_parse_single_row(self):
        """Test parsing single row number."""
        rows = _parse_skip_rows_input("42")
        assert rows == [42]

    def test_parse_row_range(self):
        """Test parsing row range."""
        rows = _parse_skip_rows_input("92-95")
        assert rows == [92, 93, 94, 95]

    def test_parse_mixed_input(self):
        """Test parsing mixed rows and ranges."""
        rows = _parse_skip_rows_input("92-94, 100, 105-107")
        assert rows == [92, 93, 94, 100, 105, 106, 107]

    def test_parse_with_spaces(self):
        """Test parsing with extra spaces."""
        rows = _parse_skip_rows_input("92 - 94,  100 , 105")
        assert rows == [92, 93, 94, 100, 105]

    def test_parse_empty_input(self):
        """Test parsing empty input."""
        rows = _parse_skip_rows_input("")
        assert rows == []

    def test_parse_invalid_input(self):
        """Test parsing invalid input is handled."""
        rows = _parse_skip_rows_input("abc, 42, xyz")
        assert 42 in rows


class TestRowRangeFormatting:
    """Tests for row range formatting."""

    def test_format_single_row(self):
        """Test formatting single row."""
        result = _format_row_ranges([42])
        assert result == "42"

    def test_format_consecutive_rows(self):
        """Test formatting consecutive rows as range."""
        result = _format_row_ranges([1, 2, 3, 4, 5])
        assert result == "1-5"

    def test_format_mixed_rows(self):
        """Test formatting mixed rows and ranges."""
        result = _format_row_ranges([1, 2, 3, 10, 15, 16, 17])
        assert result == "1-3, 10, 15-17"

    def test_format_empty_list(self):
        """Test formatting empty list."""
        result = _format_row_ranges([])
        assert result == "None"


class TestOpenRepairWizard:
    """Tests for opening repair wizard with file content."""

    def test_open_repair_wizard_basic(self):
        """Test opening repair wizard with file content."""
        content = "Software Version: 3.11.19\nUser Name: Admin\nTime\tT\tA1\tA2\tA3\n0:00:00\t37.0\t1000\t1100\t1200"
        state = open_repair_wizard(content, "Parsing failed")

        assert state["step"] == 1
        assert state["file_content"] == content
        assert len(state["file_lines"]) == 4
        assert state["issue_message"] == "Parsing failed"

    def test_open_repair_wizard_detects_header(self):
        """Test repair wizard auto-detects header row."""
        content = """Line 1
Line 2
Time\tTemperature\tA1\tA2
0:00:00\t37.0\t1000\t1100
"""
        state = open_repair_wizard(content)

        # Should detect line 3 as header (contains Time and A1)
        assert state["header_row"] == 3


class TestApplyRepairSettings:
    """Tests for applying repair settings."""

    def test_apply_repair_settings(self):
        """Test applying repair settings to file."""
        content = """Header line
Metadata line
Time\tT\tA1
0:00:00\t37.0\t1000
0:00:05\t37.0\t1100
"""
        state = {
            "header_row": 3,
            "skip_rows": [],
            "column_mapping": {
                "time": "Time",
                "temperature": "T",
                "first_well": "A1",
            }
        }

        repaired, metadata = apply_repair_settings(content, state)

        # Should start from header row
        assert repaired.startswith("Time\tT\tA1")
        assert metadata["original_header_row"] == "3"

    def test_apply_repair_with_skip_rows(self):
        """Test applying repair with skip rows."""
        content = """Time\tT\tA1
0:00:00\t37.0\t0
0:00:05\t37.0\t1000
0:00:10\t37.0\t1100
"""
        state = {
            "header_row": 1,
            "skip_rows": [2],  # Skip empty time row
            "column_mapping": {}
        }

        repaired, metadata = apply_repair_settings(content, state)

        lines = repaired.split('\n')
        # Should have header + 2 data rows (line 2 skipped)
        non_empty_lines = [l for l in lines if l.strip()]
        assert len(non_empty_lines) == 3
        assert "2" in metadata["skipped_rows"]


class TestRepairWizardIntegration:
    """Integration tests for repair wizard workflow."""

    def test_full_repair_workflow(self):
        """Test complete repair workflow."""
        # Simulate a file with parsing issues
        file_content = """BioTek Synergy HTX
Experiment: Test
Time\tT\tA1\tA2\tA3
0:00:00\t37.0\t100\t110\t120
0:00:05\t37.0\t200\t210\t220
"""
        # Step 1: Open wizard
        state = open_repair_wizard(file_content, "Header at unexpected location")
        assert state["step"] == 1

        # Step 2: Detect header at line 3
        assert state["header_row"] == 3

        # Step 3: No rows to skip
        state["skip_rows"] = []

        # Step 4: Set column mapping
        state["column_mapping"] = {
            "time": "Time",
            "temperature": "T",
            "first_well": "A1",
            "auto_detect_wells": True,
        }

        # Step 5: Apply and get repaired content
        repaired, metadata = apply_repair_settings(file_content, state)

        # Verify repaired content starts with header
        assert "Time" in repaired.split('\n')[0]
        assert "A1" in repaired.split('\n')[0]
