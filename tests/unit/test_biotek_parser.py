"""
Tests for BioTek Synergy HTX file parser.

Phase 3.1: BioTek Synergy HTX parser (96/384-well)
Phase 3.2: Temperature setpoint extraction from files
"""
import pytest
from textwrap import dedent
from app.parsers import (
    BioTekParser,
    BioTekParseError,
    ParsedPlateData,
    parse_biotek_content
)


class TestBioTekParser:
    """Tests for the BioTek file parser."""

    def test_parse_simple_kinetic_file(self):
        """T3.1: Basic kinetic data parsing."""
        content = dedent("""\
            BioTek Synergy HTX
            Read Mode: Fluorescence
            Set Temperature: 37°C
            Plate Type: 384-well

            Time\tA1\tA2\tA3
            0:00\t100.5\t110.2\t105.3
            0:30\t150.8\t160.4\t155.1
            1:00\t200.3\t210.7\t205.6
            1:30\t250.1\t260.5\t255.4
        """)
        result = parse_biotek_content(content)

        assert result.plate_format == 384
        assert result.temperature_setpoint == 37.0
        assert result.read_mode == "Fluorescence"
        assert len(result.timepoints) == 4
        assert len(result.well_data) == 3
        assert "A1" in result.well_data
        assert result.well_data["A1"][0] == 100.5

    def test_parse_96_well_format(self):
        """T3.1: 96-well file parsed correctly."""
        content = dedent("""\
            Plate: 96-well
            Temperature: 30 C

            Time\tA1\tH12
            0:00\t50.0\t55.0
            1:00\t100.0\t110.0
        """)
        result = parse_biotek_content(content)

        assert result.plate_format == 96
        assert result.temperature_setpoint == 30.0
        assert len(result.well_data) == 2
        assert "A1" in result.well_data
        assert "H12" in result.well_data

    def test_parse_384_well_positions(self):
        """T3.2: 384-well file with extended positions."""
        content = dedent("""\
            Set Temperature: 37°C

            Time\tA1\tP24\tI12
            0\t100\t200\t150
            30\t150\t250\t200
        """)
        result = parse_biotek_content(content)

        # Should infer 384-well from positions P24 (row > H) or col > 12
        assert result.plate_format == 384
        assert "A1" in result.well_data
        assert "P24" in result.well_data
        assert "I12" in result.well_data

    def test_temperature_extraction_celsius(self):
        """T3.3: Temperature setpoint extracted (°C format)."""
        content = dedent("""\
            Set Temperature: 37°C
            Time\tA1
            0\t100
        """)
        result = parse_biotek_content(content)
        assert result.temperature_setpoint == 37.0
        assert result.temperature_unit == "C"

    def test_temperature_extraction_fahrenheit(self):
        """T3.3: Temperature in Fahrenheit converted to Celsius."""
        content = dedent("""\
            Set Temperature: 98.6°F
            Time\tA1
            0\t100
        """)
        result = parse_biotek_content(content)
        # 98.6°F = 37°C
        assert result.temperature_setpoint == pytest.approx(37.0, rel=0.01)
        assert result.temperature_unit == "C"

    def test_temperature_missing(self):
        """T3.3: Missing temperature handled gracefully."""
        content = dedent("""\
            Time\tA1
            0\t100
            30\t150
        """)
        result = parse_biotek_content(content)
        assert result.temperature_setpoint is None

    def test_parse_timepoints_hhmmss_format(self):
        """Parse HH:MM:SS time format."""
        content = dedent("""\
            Time\tA1
            0:00:00\t100
            0:30:00\t150
            1:00:00\t200
        """)
        result = parse_biotek_content(content)
        assert result.timepoints == [0.0, 30.0, 60.0]

    def test_parse_timepoints_mmss_format(self):
        """Parse MM:SS time format."""
        content = dedent("""\
            Time\tA1
            0:00\t100
            0:30\t150
            1:00\t200
        """)
        result = parse_biotek_content(content)
        # MM:SS means minutes:seconds, so 0:30 = 0.5 min
        assert result.timepoints[0] == 0.0
        assert result.timepoints[1] == pytest.approx(0.5, rel=0.01)  # 30 seconds
        assert result.timepoints[2] == pytest.approx(1.0, rel=0.01)  # 60 seconds

    def test_parse_timepoints_numeric(self):
        """Parse numeric timepoints (assumed minutes)."""
        content = dedent("""\
            Time\tA1
            0\t100
            30\t150
            60\t200
        """)
        result = parse_biotek_content(content)
        assert result.timepoints == [0.0, 30.0, 60.0]

    def test_csv_delimiter(self):
        """Parse CSV format with comma delimiter."""
        content = dedent("""\
            Temperature: 37C
            Time,A1,A2,A3
            0,100.5,110.2,105.3
            30,150.8,160.4,155.1
        """)
        result = parse_biotek_content(content, format_hint="csv")

        assert len(result.well_data) == 3
        assert result.well_data["A1"][0] == 100.5

    def test_tab_delimiter(self):
        """Parse TSV format with tab delimiter."""
        content = "Temperature: 37C\nTime\tA1\tA2\tA3\n0\t100.5\t110.2\t105.3\n30\t150.8\t160.4\t155.1\n"
        result = parse_biotek_content(content)

        assert len(result.well_data) == 3
        assert result.well_data["A1"][0] == 100.5

    def test_parse_with_extra_headers(self):
        """T3.1: Handle extra header rows before data."""
        content = dedent("""\
            BioTek Instruments
            Synergy HTX
            Experiment Name: Test
            Date: 2024-01-15
            Set Temperature: 37°C
            Plate: 96-well

            Time\tA1\tA2
            0:00\t100\t110
            0:30\t150\t160
        """)
        result = parse_biotek_content(content)

        assert result.temperature_setpoint == 37.0
        assert len(result.well_data) == 2

    def test_parse_empty_file_raises_error(self):
        """Empty file should raise error."""
        content = ""
        with pytest.raises(BioTekParseError):
            parse_biotek_content(content)

    def test_parse_no_well_data_raises_error(self):
        """File with no well data should raise error."""
        content = dedent("""\
            BioTek Synergy HTX
            Temperature: 37°C
            No actual data here
        """)
        with pytest.raises(BioTekParseError, match="Could not find well data"):
            parse_biotek_content(content)

    def test_wavelength_extraction(self):
        """Extract excitation and emission wavelengths."""
        content = dedent("""\
            Read Mode: Fluorescence
            Excitation: 485 nm
            Emission: 528 nm

            Time\tA1
            0\t100
        """)
        result = parse_biotek_content(content)

        assert result.excitation_wavelength == 485
        assert result.emission_wavelength == 528

    def test_well_position_case_insensitive(self):
        """Well positions should be normalized to uppercase."""
        content = "Time\ta1\tb2\tC3\n0\t100\t110\t120\n"
        result = parse_biotek_content(content)

        assert "A1" in result.well_data
        assert "B2" in result.well_data
        assert "C3" in result.well_data

    def test_skip_non_numeric_values(self):
        """Non-numeric values in data should be skipped."""
        content = "Time\tA1\tA2\n0\t100\tN/A\n30\t150\t200\n"
        result = parse_biotek_content(content)

        assert len(result.well_data["A1"]) == 2
        # A2 should have only the numeric value
        assert 200 in result.well_data["A2"]


class TestParsedPlateData:
    """Tests for ParsedPlateData dataclass."""

    def test_num_timepoints_property(self):
        """Test num_timepoints property."""
        data = ParsedPlateData(timepoints=[0, 30, 60])
        assert data.num_timepoints == 3

    def test_num_wells_property(self):
        """Test num_wells property."""
        data = ParsedPlateData(well_data={"A1": [100], "A2": [110]})
        assert data.num_wells == 2

    def test_rows_cols_96_well(self):
        """Test rows/cols for 96-well."""
        data = ParsedPlateData(plate_format=96)
        assert data.rows == 8
        assert data.cols == 12

    def test_rows_cols_384_well(self):
        """Test rows/cols for 384-well."""
        data = ParsedPlateData(plate_format=384)
        assert data.rows == 16
        assert data.cols == 24

    def test_get_well_timecourse(self):
        """Test get_well_timecourse method."""
        data = ParsedPlateData(
            timepoints=[0, 30, 60],
            well_data={"A1": [100, 150, 200]}
        )

        times, values = data.get_well_timecourse("A1")
        assert times == [0, 30, 60]
        assert values == [100, 150, 200]

    def test_get_well_timecourse_missing(self):
        """Test get_well_timecourse for missing well."""
        data = ParsedPlateData(well_data={"A1": [100]})

        times, values = data.get_well_timecourse("Z99")
        assert times == []
        assert values == []

    def test_to_dataframe(self):
        """Test conversion to DataFrame."""
        data = ParsedPlateData(
            timepoints=[0, 30],
            well_data={"A1": [100, 150], "A2": [110, 160]}
        )

        df = data.to_dataframe()
        assert df.shape == (2, 2)
        assert df.index.name == "Time (min)"
        assert "A1" in df.columns
        assert df.loc[0, "A1"] == 100


class TestBioTekParserEdgeCases:
    """Edge case tests for the BioTek parser."""

    def test_checkerboard_data(self):
        """T3.2: 384-well checkerboard pattern data."""
        # Checkerboard: only A1, A3, B2, B4, etc have data
        content = dedent("""\
            Set Temperature: 37°C
            Time\tA1\tA3\tB2\tB4
            0\t100\t105\t110\t115
            30\t150\t155\t160\t165
        """)
        result = parse_biotek_content(content)

        # Should infer 384-well due to pattern
        assert len(result.well_data) == 4
        assert "A1" in result.well_data
        assert "B4" in result.well_data

    def test_many_timepoints(self):
        """T3.7: Data preview shows all timepoints (100 timepoints)."""
        # Generate 100 timepoints
        time_values = list(range(0, 100))
        fluorescence = list(range(100, 200))

        time_row = "\t".join(["Time"] + [str(t) for t in time_values])
        data_row = "\t".join(["A1"] + [str(f) for f in fluorescence])

        content = f"Set Temperature: 37°C\n{time_row}\n{data_row}\n"
        result = parse_biotek_content(content)

        assert len(result.timepoints) == 100
        assert len(result.well_data["A1"]) == 100

    def test_mixed_content_lines(self):
        """Handle files with mixed metadata and blank lines."""
        content = dedent("""\
            BioTek Synergy HTX

            Date: 2024-01-15

            Set Temperature: 37°C

            Read Mode: Fluorescence


            Time\tA1\tA2
            0\t100\t110

            30\t150\t160
        """)
        result = parse_biotek_content(content)

        assert result.temperature_setpoint == 37.0
        assert len(result.well_data) == 2

    def test_negative_values(self):
        """Handle negative fluorescence values (after background subtraction)."""
        content = "Time\tA1\n0\t100\n30\t-10\n60\t150\n"
        result = parse_biotek_content(content)

        assert result.well_data["A1"][1] == -10

    def test_scientific_notation(self):
        """Handle values in scientific notation."""
        content = "Time\tA1\n0\t1.5e3\n30\t2.5E4\n60\t3.5e-1\n"
        result = parse_biotek_content(content)

        assert result.well_data["A1"][0] == 1500.0
        assert result.well_data["A1"][1] == 25000.0
        assert result.well_data["A1"][2] == 0.35

    def test_decimal_timepoints(self):
        """Handle decimal timepoints."""
        content = "Time\tA1\n0.0\t100\n0.5\t125\n1.0\t150\n1.5\t175\n"
        result = parse_biotek_content(content)

        assert result.timepoints == [0.0, 0.5, 1.0, 1.5]

    def test_saturation_detection_values(self):
        """T3.10: High fluorescence values (near saturation) parsed correctly."""
        content = "Time\tA1\tA2\tA3\n0\t100\t100\t100\n30\t30000\t50000\t65535\n60\t60000\t65000\t65535\n"
        result = parse_biotek_content(content)

        # Values should be preserved as-is
        assert result.well_data["A2"][1] == 50000
        assert result.well_data["A3"][2] == 65535
