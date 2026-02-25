"""
BioTek Synergy HTX plate reader file parser.

Phase 3.1: BioTek Synergy HTX parser (96/384-well)
Phase 3.2: Temperature setpoint extraction from files
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Union, Any
from pathlib import Path
from io import StringIO

import pandas as pd
import numpy as np

from app.parsers.base_parser import BaseParser


class BioTekParseError(Exception):
    """Raised when BioTek file parsing fails."""
    pass


@dataclass
class ParsedPlateData:
    """Container for parsed plate reader data."""
    # Metadata
    reader_type: str = "BioTek Synergy HTX"
    plate_format: int = 384  # 96 or 384
    temperature_setpoint: Optional[float] = None  # °C
    temperature_unit: str = "C"
    read_mode: str = "Fluorescence"
    excitation_wavelength: Optional[int] = None
    emission_wavelength: Optional[int] = None

    # Time course data
    # Dict[str, List[float]] - key is well position (e.g., "A1"), value is list of readings
    well_data: Dict[str, List[float]] = field(default_factory=dict)

    # Timepoints in minutes
    timepoints: List[float] = field(default_factory=list)

    # Per-timepoint temperature readings (if available)
    temperatures: List[float] = field(default_factory=list)

    # Raw file content for archival
    raw_content: str = ""

    # Parsing warnings (non-fatal issues)
    warnings: List[str] = field(default_factory=list)

    @property
    def num_timepoints(self) -> int:
        """Number of timepoints."""
        return len(self.timepoints)

    @property
    def num_wells(self) -> int:
        """Number of wells with data."""
        return len(self.well_data)

    @property
    def rows(self) -> int:
        """Number of rows for this plate format."""
        return 8 if self.plate_format == 96 else 16

    @property
    def cols(self) -> int:
        """Number of columns for this plate format."""
        return 12 if self.plate_format == 96 else 24

    def get_well_timecourse(self, position: str) -> Tuple[List[float], List[float]]:
        """
        Get timepoints and fluorescence values for a specific well.

        Args:
            position: Well position (e.g., "A1")

        Returns:
            Tuple of (timepoints, fluorescence_values)
        """
        if position not in self.well_data:
            return [], []
        return self.timepoints, self.well_data[position]

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert to pandas DataFrame with timepoints as index and wells as columns.

        Returns:
            DataFrame with shape (num_timepoints, num_wells)
        """
        df = pd.DataFrame(self.well_data, index=self.timepoints)
        df.index.name = "Time (min)"
        return df


class BioTekParser(BaseParser):
    """
    Parser for BioTek Synergy HTX plate reader output files.

    Supports:
    - 96-well and 384-well formats
    - Temperature setpoint extraction
    - Time course kinetic data
    - Various export formats (txt, xlsx)
    """

    # Patterns for metadata extraction
    TEMP_PATTERNS = [
        r"Set\s*Temperature[:\s]+(\d+\.?\d*)\s*°?([CF])?",
        r"Temperature[:\s]+(\d+\.?\d*)\s*°?([CF])?",
        r"Temp[:\s]+(\d+\.?\d*)\s*°?([CF])?",
        r"(\d+\.?\d*)\s*°([CF])",
    ]

    PLATE_FORMAT_PATTERNS = [
        r"(\d+)\s*-?\s*well",
        r"Plate\s*Type[:\s]+.*?(\d+)",
    ]

    READ_MODE_PATTERNS = [
        r"Read\s*Mode[:\s]+(\w+)",
        r"Measurement[:\s]+(\w+)",
    ]

    WAVELENGTH_PATTERNS = [
        r"Excitation[:\s]+(\d+)\s*nm",
        r"Ex[:\s]+(\d+)",
        r"Emission[:\s]+(\d+)\s*nm",
        r"Em[:\s]+(\d+)",
    ]

    # Well position patterns
    WELL_PATTERN = re.compile(r'^([A-P])(\d{1,2})$')

    # BaseParser abstract property implementations
    @property
    def name(self) -> str:
        """Human-readable parser name."""
        return "BioTek Synergy HTX"

    @property
    def supported_extensions(self) -> List[str]:
        """List of supported file extensions."""
        return ['.txt', '.csv', '.tsv', '.xlsx', '.xls']

    def parse(self, file_path: Union[str, Path]) -> 'ParsedPlateData':
        """
        Parse a plate reader data file (BaseParser interface).

        Args:
            file_path: Path to the file to parse

        Returns:
            ParsedPlateData with extracted information
        """
        return self.parse_file(file_path)

    def validate(self, file_content: str) -> bool:
        """
        Validate that file content can be parsed by this parser.

        Checks for BioTek-specific markers in the file content.

        Args:
            file_content: Raw file content as string

        Returns:
            bool: True if this parser can handle the file
        """
        content_lower = file_content.lower()

        # Check for BioTek-specific markers
        biotek_markers = [
            'biotek',
            'synergy',
            'set temperature',
            'read mode',
            'plate type',
        ]

        # Check if any BioTek marker is present
        for marker in biotek_markers:
            if marker in content_lower:
                return True

        # Check for typical BioTek data format (Time header with well positions)
        if 'time' in content_lower:
            # Look for well position pattern in header
            lines = file_content.split('\n')
            for line in lines[:20]:  # Check first 20 lines
                if self.WELL_PATTERN.search(line.upper()):
                    return True

        return False

    def extract_metadata(self, file_content: str) -> Dict[str, Any]:
        """
        Extract metadata from file content.

        Args:
            file_content: Raw file content as string

        Returns:
            Dict with metadata (reader_type, plate_format, temperature, etc.)
        """
        # Create a temporary result to extract metadata
        temp_result = ParsedPlateData(raw_content=file_content)
        self.result = temp_result
        self._extract_metadata(file_content)

        return {
            'reader_type': temp_result.reader_type,
            'plate_format': temp_result.plate_format,
            'temperature_setpoint': temp_result.temperature_setpoint,
            'temperature_unit': temp_result.temperature_unit,
            'read_mode': temp_result.read_mode,
            'excitation_wavelength': temp_result.excitation_wavelength,
            'emission_wavelength': temp_result.emission_wavelength,
        }

    def __init__(self):
        self.result: Optional[ParsedPlateData] = None

    def parse_file(self, file_path: Union[str, Path]) -> ParsedPlateData:
        """
        Parse a BioTek output file.

        Args:
            file_path: Path to the BioTek file

        Returns:
            ParsedPlateData with extracted information

        Raises:
            BioTekParseError: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise BioTekParseError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix in ['.xlsx', '.xls']:
            return self._parse_excel(file_path)
        elif suffix in ['.txt', '.csv', '.tsv']:
            return self._parse_text(file_path)
        else:
            # Try text parsing for unknown formats
            try:
                return self._parse_text(file_path)
            except Exception as e:
                raise BioTekParseError(f"Unsupported file format: {suffix}. Error: {e}")

    def parse_content(self, content: str, format_hint: str = "txt") -> ParsedPlateData:
        """
        Parse file content directly (useful for uploaded files).

        Args:
            content: File content as string
            format_hint: Expected format ('txt', 'csv', or 'excel')

        Returns:
            ParsedPlateData with extracted information
        """
        self.result = ParsedPlateData(raw_content=content)

        if format_hint in ['txt', 'csv', 'tsv']:
            return self._parse_text_content(content)
        else:
            raise BioTekParseError(f"Direct content parsing only supports text formats, not {format_hint}")

    def _parse_excel(self, file_path: Path) -> ParsedPlateData:
        """Parse Excel format BioTek output."""
        try:
            # Read all sheets
            xlsx = pd.ExcelFile(file_path)

            with open(file_path, 'rb') as f:
                raw_bytes = f.read()

            self.result = ParsedPlateData(raw_content=f"[Binary Excel file: {len(raw_bytes)} bytes]")

            # Look for kinetic data sheet
            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
                content = df.to_string()

                # Try to extract metadata from this sheet
                self._extract_metadata(content)

                # Try to extract time course data
                if self._try_extract_kinetic_data_excel(df):
                    break

            if not self.result.well_data:
                raise BioTekParseError("Could not find kinetic data in Excel file")

            return self.result

        except Exception as e:
            raise BioTekParseError(f"Error parsing Excel file: {e}")

    def _parse_text(self, file_path: Path) -> ParsedPlateData:
        """Parse text-based BioTek output (txt, csv, tsv)."""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if content is None:
            raise BioTekParseError(f"Could not decode file with any supported encoding")

        return self._parse_text_content(content)

    def _parse_text_content(self, content: str) -> ParsedPlateData:
        """Parse text content."""
        self.result = ParsedPlateData(raw_content=content)

        # Extract metadata
        self._extract_metadata(content)

        # Parse kinetic data
        self._extract_kinetic_data_text(content)

        if not self.result.well_data:
            raise BioTekParseError("Could not find well data in file")

        return self.result

    def _extract_metadata(self, content: str):
        """Extract metadata from file content."""
        # Temperature setpoint
        for pattern in self.TEMP_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                temp_value = float(match.group(1))
                temp_unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else "C"

                # Convert Fahrenheit to Celsius if needed
                if temp_unit and temp_unit.upper() == "F":
                    temp_value = (temp_value - 32) * 5 / 9
                    temp_unit = "C"

                self.result.temperature_setpoint = temp_value
                self.result.temperature_unit = temp_unit
                break

        # Plate format
        for pattern in self.PLATE_FORMAT_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                format_value = int(match.group(1))
                if format_value in [96, 384]:
                    self.result.plate_format = format_value
                    self._plate_format_from_metadata = True
                break

        # Read mode
        for pattern in self.READ_MODE_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                self.result.read_mode = match.group(1)
                break

        # Wavelengths
        ex_match = re.search(r"Excitation[:\s]+(\d+)", content, re.IGNORECASE)
        if ex_match:
            self.result.excitation_wavelength = int(ex_match.group(1))

        em_match = re.search(r"Emission[:\s]+(\d+)", content, re.IGNORECASE)
        if em_match:
            self.result.emission_wavelength = int(em_match.group(1))

    def _extract_kinetic_data_text(self, content: str):
        """Extract kinetic time course data from text content."""
        lines = content.split('\n')

        # Find the data section
        # BioTek exports typically have two formats:
        # 1. Wide format: Time header row with well positions, data rows have time values
        #    Time    A1      A2      A3
        #    0:00    100     110     105
        #    0:30    150     160     155
        # 2. Long format: Well positions in first column
        #    A1      0:00    0:30    1:00
        #    A2      100     150     200

        # Try wide format first (Time as header)
        if self._try_extract_wide_format(lines):
            self._infer_plate_format()
            return

        # Try long format (wells as first column)
        if self._try_extract_long_format(lines):
            self._infer_plate_format()
            return

        # Try grid format as last resort
        self._try_extract_grid_format(lines)
        self._infer_plate_format()

    def _try_extract_wide_format(self, lines: List[str]) -> bool:
        """
        Try to extract data in wide format where Time is the first column header.

        Format:
            Time    A1      A2      A3
            0:00    100     110     105
            0:30    150     160     155
        """
        header_row_index = None
        well_columns = {}  # Maps column index -> well position

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Detect delimiter
            delimiter = '\t' if '\t' in line_stripped else ','
            parts = [p.strip() for p in line_stripped.split(delimiter)]

            if not parts:
                continue

            # Check if this is a header row with "Time" and well positions
            first_col_lower = parts[0].lower()
            if first_col_lower == 'time' or first_col_lower == '':
                # Check remaining columns for well positions
                found_wells = False
                for col_idx, col_val in enumerate(parts[1:], start=1):
                    col_val_upper = col_val.strip().upper()
                    if self.WELL_PATTERN.match(col_val_upper):
                        well_columns[col_idx] = col_val_upper
                        found_wells = True

                if found_wells:
                    header_row_index = i
                    break

        if header_row_index is None or not well_columns:
            return False

        # Determine delimiter from header row
        delimiter = '\t' if '\t' in lines[header_row_index] else ','

        # Initialize well_data for each well
        for well_pos in well_columns.values():
            self.result.well_data[well_pos] = []

        # Parse data rows (after header)
        for i in range(header_row_index + 1, len(lines)):
            line = lines[i].strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(delimiter)]
            if not parts:
                continue

            # First column should be time
            time_str = parts[0]
            if not time_str:
                continue

            # Skip if first column looks like a well position (different format)
            if self.WELL_PATTERN.match(time_str.upper()):
                return False

            # Parse timepoint
            try:
                timepoint = self._parse_single_timepoint(time_str)
                self.result.timepoints.append(timepoint)

                # Parse values for each well column
                for col_idx, well_pos in well_columns.items():
                    if col_idx < len(parts):
                        val_str = parts[col_idx].strip()
                        if val_str:
                            try:
                                self.result.well_data[well_pos].append(float(val_str))
                            except ValueError:
                                self.result.well_data[well_pos].append(None)
                        else:
                            self.result.well_data[well_pos].append(None)
                    else:
                        self.result.well_data[well_pos].append(None)

            except (ValueError, IndexError):
                continue

        # Remove wells with no data
        self.result.well_data = {
            k: v for k, v in self.result.well_data.items()
            if any(x is not None for x in v)
        }

        return len(self.result.well_data) > 0

    def _try_extract_long_format(self, lines: List[str]) -> bool:
        """
        Try to extract data in long format where wells are in first column.

        Format:
            A1      100     150     200
            A2      110     160     210
        """
        data_start = None
        time_row = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            delimiter = '\t' if '\t' in line_stripped else ','
            parts = [p.strip() for p in line_stripped.split(delimiter)]

            if not parts:
                continue

            first_col = parts[0].upper()

            # Check if first column is a well position
            if self.WELL_PATTERN.match(first_col):
                data_start = i
                # Check if previous row has timepoints
                if i > 0:
                    prev_line = lines[i - 1].strip()
                    if prev_line and 'time' in prev_line.lower():
                        time_row = i - 1
                break

        if data_start is None:
            return False

        # Determine delimiter
        delimiter = '\t' if '\t' in lines[data_start] else ','

        # Parse timepoints from time row if found
        if time_row is not None:
            self.result.timepoints = self._parse_time_row(lines[time_row], delimiter)

        # Parse well data
        for i in range(data_start, len(lines)):
            line = lines[i].strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(delimiter)]
            if not parts:
                continue

            first_col = parts[0].strip().upper()
            if not self.WELL_PATTERN.match(first_col):
                continue

            position = first_col
            values = []

            for val in parts[1:]:
                val = val.strip()
                if val:
                    try:
                        values.append(float(val))
                    except ValueError:
                        values.append(None)
                else:
                    values.append(None)

            if values and any(v is not None for v in values):
                self.result.well_data[position] = values

                # Set timepoints if not already set
                if not self.result.timepoints:
                    self.result.timepoints = list(range(len(values)))

        return len(self.result.well_data) > 0

    def _parse_time_row(self, time_line: str, delimiter: str) -> List[float]:
        """Parse timepoints from a time row."""
        timepoints = []
        parts = time_line.split(delimiter)

        for part in parts:
            part = part.strip()

            # Skip empty or header parts
            if not part or part.lower() in ['time', 'well', '']:
                continue

            # Parse time formats: "0:30:00", "00:30", "30", "30 min"
            try:
                # HH:MM:SS format
                if part.count(':') == 2:
                    h, m, s = part.split(':')
                    minutes = int(h) * 60 + int(m) + float(s) / 60
                    timepoints.append(minutes)
                # MM:SS or H:MM format
                elif ':' in part:
                    parts_time = part.split(':')
                    if len(parts_time) == 2:
                        # Assume MM:SS if first part < 60
                        if int(parts_time[0]) < 60:
                            minutes = int(parts_time[0]) + float(parts_time[1]) / 60
                        else:
                            minutes = int(parts_time[0]) * 60 + int(parts_time[1])
                        timepoints.append(minutes)
                # Numeric format (minutes)
                else:
                    # Remove any "min" suffix
                    numeric_part = re.sub(r'\s*min.*', '', part, flags=re.IGNORECASE)
                    timepoints.append(float(numeric_part))
            except (ValueError, IndexError):
                continue

        return timepoints

    def _try_extract_grid_format(self, lines: List[str]):
        """
        Try to extract data from grid/plate format.

        Grid format has wells arranged in a plate-like grid for each timepoint.
        """
        # Look for sections with column headers (1, 2, 3...) and row labels (A, B, C...)
        timepoint_sections = []
        current_section = []
        current_timepoint = None

        for i, line in enumerate(lines):
            line = line.strip()

            # Look for timepoint marker
            time_match = re.search(r'Time[:\s]+(\d+[:\d]*)', line, re.IGNORECASE)
            if time_match:
                if current_section and current_timepoint is not None:
                    timepoint_sections.append((current_timepoint, current_section))
                current_timepoint = self._parse_single_timepoint(time_match.group(1))
                current_section = []
                continue

            # Look for column header row
            if re.match(r'^\s*[,\t\s]*1[,\t\s]+2[,\t\s]+3', line):
                continue

            # Look for data row (starts with row letter)
            if re.match(r'^[A-P]\s*[,\t]', line):
                current_section.append(line)

        # Don't forget the last section
        if current_section and current_timepoint is not None:
            timepoint_sections.append((current_timepoint, current_section))

        # Process sections
        if timepoint_sections:
            self.result.timepoints = [t for t, _ in timepoint_sections]

            # Initialize well_data
            for timepoint, section_lines in timepoint_sections:
                time_index = self.result.timepoints.index(timepoint)

                for line in section_lines:
                    delimiter = '\t' if '\t' in line else ','
                    parts = line.split(delimiter)
                    row_letter = parts[0].strip().upper()

                    for col_num, val in enumerate(parts[1:], start=1):
                        val = val.strip()
                        if val:
                            try:
                                position = f"{row_letter}{col_num}"
                                if position not in self.result.well_data:
                                    self.result.well_data[position] = [None] * len(self.result.timepoints)
                                self.result.well_data[position][time_index] = float(val)
                            except ValueError:
                                continue

    def _parse_single_timepoint(self, time_str: str) -> float:
        """Parse a single timepoint string to minutes."""
        time_str = time_str.strip()

        if ':' in time_str:
            parts = time_str.split(':')
            if len(parts) == 3:
                return int(parts[0]) * 60 + int(parts[1]) + float(parts[2]) / 60
            elif len(parts) == 2:
                return int(parts[0]) + float(parts[1]) / 60
        else:
            return float(time_str)

    def _try_extract_kinetic_data_excel(self, df: pd.DataFrame) -> bool:
        """Try to extract kinetic data from an Excel DataFrame."""
        # Find rows/columns with well positions
        for row_idx in range(min(20, len(df))):
            for col_idx in range(min(5, len(df.columns))):
                cell = str(df.iloc[row_idx, col_idx]).strip()

                # Check if this looks like a well position or "Time" header
                if cell.lower() == 'time' or self.WELL_PATTERN.match(cell.upper()):
                    # This might be the start of our data
                    return self._parse_data_from_position(df, row_idx, col_idx)

        return False

    def _parse_data_from_position(self, df: pd.DataFrame, start_row: int, start_col: int) -> bool:
        """Parse data starting from a detected position in the DataFrame."""
        # Check if this row has timepoints
        first_cell = str(df.iloc[start_row, start_col]).strip().lower()

        if first_cell == 'time' or self.WELL_PATTERN.match(first_cell.upper()):
            # Parse timepoints from first row (if it's Time)
            if first_cell == 'time':
                for col_idx in range(start_col + 1, len(df.columns)):
                    try:
                        val = df.iloc[start_row, col_idx]
                        if pd.notna(val):
                            if isinstance(val, str):
                                self.result.timepoints.append(self._parse_single_timepoint(val))
                            else:
                                self.result.timepoints.append(float(val))
                    except (ValueError, TypeError):
                        continue

                start_row += 1

            # Parse well data
            for row_idx in range(start_row, len(df)):
                first_cell = str(df.iloc[row_idx, start_col]).strip()

                if self.WELL_PATTERN.match(first_cell.upper()):
                    position = first_cell.upper()
                    values = []

                    for col_idx in range(start_col + 1, len(df.columns)):
                        try:
                            val = df.iloc[row_idx, col_idx]
                            if pd.notna(val):
                                values.append(float(val))
                        except (ValueError, TypeError):
                            continue

                    if values:
                        self.result.well_data[position] = values

                        if not self.result.timepoints:
                            self.result.timepoints = list(range(len(values)))

            self._infer_plate_format()
            return bool(self.result.well_data)

        return False

    def _infer_plate_format(self):
        """Infer plate format from well positions (only if not already set from metadata)."""
        if not self.result.well_data:
            return

        # Check if plate format was explicitly set from metadata
        # The default is 384, so if it's still 384 and we found it in metadata, keep it
        # We track this by checking if _plate_format_from_metadata flag is set
        if hasattr(self, '_plate_format_from_metadata') and self._plate_format_from_metadata:
            return

        max_row = 'A'
        max_col = 1

        for position in self.result.well_data.keys():
            match = self.WELL_PATTERN.match(position.upper())
            if match:
                row = match.group(1)
                col = int(match.group(2))

                if row > max_row:
                    max_row = row
                if col > max_col:
                    max_col = col

        # Determine format based on max positions
        row_num = ord(max_row) - ord('A') + 1

        if row_num > 8 or max_col > 12:
            self.result.plate_format = 384
        else:
            self.result.plate_format = 96


def parse_biotek_file(file_path: Union[str, Path]) -> ParsedPlateData:
    """
    Convenience function to parse a BioTek file.

    Args:
        file_path: Path to the BioTek file

    Returns:
        ParsedPlateData with extracted information
    """
    parser = BioTekParser()
    return parser.parse_file(file_path)


def parse_biotek_content(content: str, format_hint: str = "txt") -> ParsedPlateData:
    """
    Convenience function to parse BioTek content directly.

    Args:
        content: File content as string
        format_hint: Expected format

    Returns:
        ParsedPlateData with extracted information
    """
    parser = BioTekParser()
    return parser.parse_content(content, format_hint)
