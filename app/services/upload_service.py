"""
Data upload service for plate reader files.

Phase 3.3: Upload workflow with draft construct block
Phase 3.5: Local filesystem storage (hierarchical)
Phase 3.6: Blank subtraction
Phase 3.11: Empty well detection and classification
Phase 3.12: Negative control validation at upload
Phase 3.13: Incomplete plate warning (suppressible)
"""
import os
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field

from app.extensions import db
from app.models import (
    Project, Construct, PlateLayout, WellAssignment, ExperimentalSession,
    Plate, Well, Reaction, RawDataPoint, AuditLog
)
from app.models.plate_layout import WellType
from app.models.experiment import FitStatus
from app.parsers import parse_biotek_file, parse_biotek_content, ParsedPlateData, BioTekParseError


class UploadValidationError(Exception):
    """Raised when upload validation fails."""
    pass


class UploadProcessingError(Exception):
    """Raised when upload processing fails."""
    pass


class SecurityError(Exception):
    """Raised when a security violation is detected (Phase 1 Security Fix)."""
    pass


@dataclass
class UploadWarning:
    """A non-fatal warning during upload."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    suppressible: bool = True


@dataclass
class UploadValidationResult:
    """Result of upload validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[UploadWarning] = field(default_factory=list)
    parsed_data: Optional[ParsedPlateData] = None

    # Metadata extracted from file
    plate_format: int = 384
    temperature_setpoint: Optional[float] = None
    num_timepoints: int = 0
    num_wells_with_data: int = 0

    # Layout matching info
    matched_wells: int = 0
    unmatched_wells: int = 0
    empty_layout_wells: int = 0

    # Negative control info
    negative_control_count: int = 0
    blank_count: int = 0


@dataclass
class UploadResult:
    """Result of successful upload."""
    plate_id: int
    session_id: int
    wells_created: int
    data_points_created: int
    raw_file_path: str
    warnings: List[UploadWarning] = field(default_factory=list)


class UploadService:
    """
    Service for handling plate reader file uploads.

    Manages the upload workflow including:
    - File parsing and validation
    - Draft construct blocking
    - Layout matching
    - Storage of raw files
    - Well and data point creation
    """

    # Configuration
    DATA_DIR = Path("data")
    RAW_FILES_DIR = DATA_DIR / "raw_files"

    @classmethod
    def _validate_path_id(cls, value: int, name: str) -> int:
        """
        Validate that a path component ID is a positive integer.

        Phase 1 Security Fix: Prevents path traversal via malicious IDs.

        Args:
            value: The ID value to validate
            name: Name of the parameter for error messages

        Returns:
            Validated positive integer

        Raises:
            SecurityError: If value is not a positive integer
        """
        if not isinstance(value, int) or value <= 0:
            raise SecurityError(f"{name} must be a positive integer, got: {value}")
        return value

    @classmethod
    def _validate_path_within_base(cls, path: Path, base_dir: Path) -> Path:
        """
        Validate that a path stays within the base directory.

        Phase 1 Security Fix: Prevents path traversal attacks.

        Args:
            path: Path to validate
            base_dir: Base directory that path must stay within

        Returns:
            Resolved absolute path

        Raises:
            SecurityError: If path escapes base directory
        """
        # Ensure base_dir exists for resolution
        base_dir.mkdir(parents=True, exist_ok=True)

        # Resolve both paths to absolute form
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()

        # Check if resolved path is within base directory
        try:
            resolved_path.relative_to(resolved_base)
        except ValueError:
            raise SecurityError(
                f"Path traversal detected: {path} escapes base directory {base_dir}"
            )

        return resolved_path

    # Thresholds
    INCOMPLETE_PLATE_THRESHOLD = 0.5  # Warn if <50% wells have data
    MIN_NEGATIVE_CONTROLS = 2  # Minimum negative control wells required

    @classmethod
    def validate_upload(
        cls,
        project_id: int,
        layout_id: int,
        file_content: str,
        file_format: str = "txt"
    ) -> UploadValidationResult:
        """
        Validate an upload before processing.

        Checks:
        1. Project exists and is not archived
        2. Layout exists and belongs to project
        3. No draft constructs in layout
        4. File parses successfully
        5. Plate format matches project
        6. Minimum negative controls present

        Args:
            project_id: Target project ID
            layout_id: Target layout ID
            file_content: Raw file content
            file_format: File format hint ('txt', 'csv', 'xlsx')

        Returns:
            UploadValidationResult with validation status
        """
        result = UploadValidationResult(is_valid=True)

        # Check project
        project = Project.query.get(project_id)
        if not project:
            result.is_valid = False
            result.errors.append(f"Project {project_id} not found")
            return result

        if project.is_archived:
            result.is_valid = False
            result.errors.append("Cannot upload to archived project")
            return result

        # Check layout
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            result.is_valid = False
            result.errors.append(f"Layout {layout_id} not found")
            return result

        if layout.project_id != project_id:
            result.is_valid = False
            result.errors.append("Layout does not belong to this project")
            return result

        # Check for draft constructs in layout (F6.4)
        draft_constructs = cls._check_draft_constructs(layout_id)
        if draft_constructs:
            result.is_valid = False
            construct_names = ", ".join(draft_constructs)
            result.errors.append(
                f"Cannot upload: Layout contains draft constructs: {construct_names}. "
                "Publish all constructs before uploading data."
            )
            return result

        # Parse file
        try:
            parsed = parse_biotek_content(file_content, file_format)
            result.parsed_data = parsed
            result.plate_format = parsed.plate_format
            result.temperature_setpoint = parsed.temperature_setpoint
            result.num_timepoints = parsed.num_timepoints
            result.num_wells_with_data = parsed.num_wells
        except BioTekParseError as e:
            result.is_valid = False
            result.errors.append(f"File parsing failed: {e}")
            return result

        # Check plate format matches project
        project_format = int(project.plate_format.value)
        if parsed.plate_format != project_format:
            result.is_valid = False
            result.errors.append(
                f"Plate format mismatch: File appears to be {parsed.plate_format}-well, "
                f"but project is configured for {project_format}-well"
            )
            return result

        # Match wells to layout and check for issues
        layout_wells = WellAssignment.query.filter_by(layout_id=layout_id).all()
        layout_positions = {w.well_position: w for w in layout_wells}

        # Count negative controls and blanks in layout
        for pos, assignment in layout_positions.items():
            if assignment.well_type == WellType.NEGATIVE_CONTROL_NO_TEMPLATE:
                result.negative_control_count += 1
            elif assignment.well_type == WellType.NEGATIVE_CONTROL_NO_DYE:
                result.negative_control_count += 1
            elif assignment.well_type == WellType.BLANK:
                result.blank_count += 1

        # Check negative control minimum (F19.12)
        if result.negative_control_count < cls.MIN_NEGATIVE_CONTROLS:
            result.is_valid = False
            result.errors.append(
                f"Insufficient negative controls: Layout has {result.negative_control_count}, "
                f"minimum required is {cls.MIN_NEGATIVE_CONTROLS}"
            )
            return result

        # Match wells
        for pos in parsed.well_data.keys():
            if pos in layout_positions:
                result.matched_wells += 1
            else:
                result.unmatched_wells += 1

        # Count empty layout wells (assigned but no data)
        for pos, assignment in layout_positions.items():
            if assignment.well_type != WellType.EMPTY and pos not in parsed.well_data:
                result.empty_layout_wells += 1

        # Warning for unmatched wells
        if result.unmatched_wells > 0:
            result.warnings.append(UploadWarning(
                code="UNMATCHED_WELLS",
                message=f"{result.unmatched_wells} wells in file have no layout assignment",
                details={"count": result.unmatched_wells}
            ))

        # Warning for incomplete plate (F7.8-F7.11)
        total_layout_wells = len([w for w in layout_wells if w.well_type != WellType.EMPTY])
        if total_layout_wells > 0:
            fill_ratio = result.matched_wells / total_layout_wells
            if fill_ratio < cls.INCOMPLETE_PLATE_THRESHOLD:
                result.warnings.append(UploadWarning(
                    code="INCOMPLETE_PLATE",
                    message=f"Only {result.matched_wells}/{total_layout_wells} assigned wells have data ({fill_ratio:.0%})",
                    details={
                        "matched": result.matched_wells,
                        "expected": total_layout_wells,
                        "fill_ratio": fill_ratio
                    },
                    suppressible=True
                ))

        return result

    @classmethod
    def process_upload(
        cls,
        project_id: int,
        layout_id: int,
        session_id: Optional[int],
        file_content: str,
        file_format: str,
        original_filename: str,
        plate_number: int,
        username: str,
        session_date: Optional[date] = None,
        session_batch_id: Optional[str] = None,
        suppressed_warnings: Optional[List[str]] = None
    ) -> UploadResult:
        """
        Process an upload and create database records.

        Args:
            project_id: Target project ID
            layout_id: Target layout ID
            session_id: Existing session ID (None to create new)
            file_content: Raw file content
            file_format: File format hint
            original_filename: Original uploaded filename
            plate_number: Plate number in session
            username: User performing upload
            session_date: Date for new session (required if session_id is None)
            session_batch_id: Batch ID for new session
            suppressed_warnings: Warning codes to suppress

        Returns:
            UploadResult with created entities

        Raises:
            UploadValidationError: If validation fails
            UploadProcessingError: If processing fails
        """
        suppressed_warnings = suppressed_warnings or []

        # Validate first
        validation = cls.validate_upload(project_id, layout_id, file_content, file_format)

        if not validation.is_valid:
            raise UploadValidationError("; ".join(validation.errors))

        # Check for non-suppressed, non-suppressible warnings
        for warning in validation.warnings:
            if warning.code not in suppressed_warnings and not warning.suppressible:
                raise UploadValidationError(f"Cannot proceed: {warning.message}")

        # Filter suppressed warnings
        active_warnings = [
            w for w in validation.warnings
            if w.code not in suppressed_warnings
        ]

        try:
            # Get or create session
            if session_id:
                session = ExperimentalSession.query.get(session_id)
                if not session:
                    raise UploadProcessingError(f"Session {session_id} not found")
            else:
                if not session_date:
                    session_date = date.today()
                if not session_batch_id:
                    session_batch_id = f"Session_{session_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"

                session = ExperimentalSession(
                    project_id=project_id,
                    date=session_date,
                    batch_identifier=session_batch_id
                )
                db.session.add(session)
                db.session.flush()

            # Store raw file
            raw_file_path = cls._store_raw_file(
                project_id, session.id, original_filename, file_content
            )

            # Create plate record
            plate = Plate(
                session_id=session.id,
                layout_id=layout_id,
                plate_number=plate_number,
                raw_file_path=raw_file_path
            )
            db.session.add(plate)
            db.session.flush()

            # Create wells and data points
            wells_created, data_points_created = cls._create_wells_and_data(
                plate.id,
                layout_id,
                validation.parsed_data
            )

            # Log the action
            AuditLog.log_action(
                username=username,
                action_type="upload",
                entity_type="plate",
                entity_id=plate.id,
                project_id=project_id,
                changes=[
                    {"field": "filename", "old": None, "new": original_filename},
                    {"field": "wells", "old": None, "new": str(wells_created)},
                    {"field": "timepoints", "old": None, "new": str(validation.num_timepoints)}
                ]
            )

            db.session.commit()

            return UploadResult(
                plate_id=plate.id,
                session_id=session.id,
                wells_created=wells_created,
                data_points_created=data_points_created,
                raw_file_path=raw_file_path,
                warnings=active_warnings
            )

        except Exception as e:
            db.session.rollback()
            raise UploadProcessingError(f"Upload processing failed: {e}")

    @classmethod
    def _check_draft_constructs(cls, layout_id: int) -> List[str]:
        """
        Check for draft constructs in a layout.

        Returns:
            List of draft construct names
        """
        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()
        draft_names = set()

        for assignment in assignments:
            if assignment.construct_id:
                construct = Construct.query.get(assignment.construct_id)
                if construct and construct.is_draft:
                    draft_names.add(construct.identifier)

        return list(draft_names)

    @classmethod
    def _store_raw_file(
        cls,
        project_id: int,
        session_id: int,
        original_filename: str,
        content: str
    ) -> str:
        """
        Store raw file in hierarchical directory structure.

        Structure: data/raw_files/{project_id}/{session_id}/{timestamp}_{filename}

        Phase 1 Security Fix: Added path validation to prevent traversal attacks.

        Args:
            project_id: Project ID
            session_id: Session ID
            original_filename: Original filename
            content: File content

        Returns:
            Relative path to stored file

        Raises:
            SecurityError: If IDs are invalid or path traversal detected
        """
        # Validate IDs are positive integers (Phase 1 Security Fix)
        cls._validate_path_id(project_id, "project_id")
        cls._validate_path_id(session_id, "session_id")

        # Sanitize filename - only allow safe characters
        safe_filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_filename)
        # Limit filename length to prevent issues
        if len(safe_filename) > 200:
            safe_filename = safe_filename[:200]
        # Ensure filename is not empty after sanitization
        if not safe_filename or safe_filename.strip('.') == '':
            safe_filename = "unnamed_file"

        # Create directory structure
        dir_path = cls.RAW_FILES_DIR / str(project_id) / str(session_id)

        # Validate path stays within RAW_FILES_DIR (Phase 1 Security Fix)
        cls._validate_path_within_base(dir_path, cls.RAW_FILES_DIR)

        dir_path.mkdir(parents=True, exist_ok=True)

        # Create unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stored_filename = f"{timestamp}_{safe_filename}"

        file_path = dir_path / stored_filename

        # Final validation of the complete file path
        cls._validate_path_within_base(file_path, cls.RAW_FILES_DIR)

        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(file_path)

    @classmethod
    def _create_wells_and_data(
        cls,
        plate_id: int,
        layout_id: int,
        parsed_data: ParsedPlateData
    ) -> Tuple[int, int]:
        """
        Create Well and RawDataPoint records from parsed data.

        Args:
            plate_id: Plate ID
            layout_id: Layout ID for well type mapping
            parsed_data: Parsed plate data

        Returns:
            Tuple of (wells_created, data_points_created)
        """
        # Get layout assignments
        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()
        layout_map = {a.well_position: a for a in assignments}

        wells_created = 0
        data_points_created = 0

        for position, values in parsed_data.well_data.items():
            # Get assignment if exists
            assignment = layout_map.get(position)

            # Determine well type
            well_type = WellType.EMPTY
            construct_id = None
            ligand_concentration = None

            ligand_condition = None

            if assignment:
                well_type = assignment.well_type
                construct_id = assignment.construct_id
                ligand_concentration = assignment.ligand_concentration
                ligand_condition = assignment.ligand_condition

            # Create well
            well = Well(
                plate_id=plate_id,
                position=position,
                well_type=well_type,
                construct_id=construct_id,
                ligand_concentration=ligand_concentration,
                ligand_condition=ligand_condition,
                fit_status=FitStatus.PENDING
            )
            db.session.add(well)
            db.session.flush()

            wells_created += 1

            # Create raw data points
            for i, fluorescence in enumerate(values):
                if fluorescence is None:
                    continue

                timepoint = parsed_data.timepoints[i] if i < len(parsed_data.timepoints) else float(i)

                # Get temperature if available
                temperature = None
                if i < len(parsed_data.temperatures):
                    temperature = parsed_data.temperatures[i]
                elif parsed_data.temperature_setpoint:
                    temperature = parsed_data.temperature_setpoint

                data_point = RawDataPoint(
                    well_id=well.id,
                    timepoint=timepoint,
                    fluorescence_raw=fluorescence,
                    temperature=temperature
                )
                db.session.add(data_point)
                data_points_created += 1

        return wells_created, data_points_created

    @classmethod
    def get_upload_preview(
        cls,
        project_id: int,
        layout_id: int,
        file_content: str,
        file_format: str = "txt"
    ) -> Dict[str, Any]:
        """
        Generate a preview of the upload before processing.

        Args:
            project_id: Target project ID
            layout_id: Target layout ID
            file_content: Raw file content
            file_format: File format hint

        Returns:
            Dict with preview information including validation result and sample data
        """
        validation = cls.validate_upload(project_id, layout_id, file_content, file_format)

        preview = {
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "suppressible": w.suppressible
                }
                for w in validation.warnings
            ],
            "metadata": {
                "plate_format": validation.plate_format,
                "temperature_setpoint": validation.temperature_setpoint,
                "num_timepoints": validation.num_timepoints,
                "num_wells_with_data": validation.num_wells_with_data
            },
            "matching": {
                "matched_wells": validation.matched_wells,
                "unmatched_wells": validation.unmatched_wells,
                "empty_layout_wells": validation.empty_layout_wells,
                "negative_control_count": validation.negative_control_count,
                "blank_count": validation.blank_count
            }
        }

        # Add sample data if valid
        if validation.parsed_data and validation.is_valid:
            sample_wells = list(validation.parsed_data.well_data.keys())[:5]
            preview["sample_data"] = {
                "wells": sample_wells,
                "timepoints": validation.parsed_data.timepoints[:10],
                "values": {
                    pos: validation.parsed_data.well_data[pos][:10]
                    for pos in sample_wells
                }
            }

        return preview

    @classmethod
    def detect_empty_wells(
        cls,
        parsed_data: ParsedPlateData,
        threshold: float = 100.0
    ) -> List[str]:
        """
        Detect wells that appear empty based on signal level.

        Args:
            parsed_data: Parsed plate data
            threshold: Maximum mean signal to be considered empty (default: 100 RFU)

        Returns:
            List of positions identified as empty
        """
        empty_wells = []

        for position, values in parsed_data.well_data.items():
            valid_values = [v for v in values if v is not None]
            if not valid_values:
                empty_wells.append(position)
                continue

            mean_signal = sum(valid_values) / len(valid_values)
            if mean_signal < threshold:
                empty_wells.append(position)

        return empty_wells

    @classmethod
    def apply_blank_subtraction(
        cls,
        parsed_data: ParsedPlateData,
        blank_positions: List[str]
    ) -> Dict[str, List[float]]:
        """
        Apply blank subtraction to well data.

        Args:
            parsed_data: Parsed plate data
            blank_positions: List of blank well positions

        Returns:
            Dict of corrected well data (same structure as parsed_data.well_data)
        """
        if not blank_positions:
            return dict(parsed_data.well_data)

        # Calculate mean blank signal at each timepoint
        num_timepoints = len(parsed_data.timepoints)
        blank_means = [0.0] * num_timepoints

        valid_blanks = [pos for pos in blank_positions if pos in parsed_data.well_data]

        if not valid_blanks:
            return dict(parsed_data.well_data)

        for i in range(num_timepoints):
            blank_values = []
            for pos in valid_blanks:
                if i < len(parsed_data.well_data[pos]):
                    val = parsed_data.well_data[pos][i]
                    if val is not None:
                        blank_values.append(val)

            if blank_values:
                blank_means[i] = sum(blank_values) / len(blank_values)

        # Subtract blank from all wells
        corrected = {}
        for position, values in parsed_data.well_data.items():
            corrected_values = []
            for i, val in enumerate(values):
                if val is not None and i < len(blank_means):
                    corrected_values.append(val - blank_means[i])
                else:
                    corrected_values.append(val)
            corrected[position] = corrected_values

        return corrected

    # --- Upload CRUD wrappers (extracted from Upload model, Phase 2) ---

    @staticmethod
    def create_upload(
        project_id: int,
        layout_id: int,
        filename: str,
        content: str,
        username: str,
        client_ip: Optional[str] = None,
        session_id: Optional[int] = None,
        file_format: str = "txt",
        ttl_hours: int = 24
    ) -> "Upload":
        """
        Create a new upload record.

        Service-layer wrapper for Upload.create().

        Returns:
            New Upload instance (added to session, not yet committed)
        """
        from app.models.upload import Upload
        return Upload.create(
            project_id=project_id,
            layout_id=layout_id,
            filename=filename,
            content=content,
            username=username,
            client_ip=client_ip,
            session_id=session_id,
            file_format=file_format,
            ttl_hours=ttl_hours
        )

    @staticmethod
    def get_upload_by_id(upload_id: str) -> Optional["Upload"]:
        """
        Get upload by public UUID, excluding expired uploads.

        Service-layer wrapper for Upload.get_by_upload_id().

        Returns:
            Upload instance or None
        """
        from app.models.upload import Upload
        return Upload.get_by_upload_id(upload_id)

    @staticmethod
    def cleanup_expired_uploads() -> int:
        """
        Mark expired uploads for cleanup.

        Service-layer wrapper for Upload.cleanup_expired().

        Returns:
            Number of uploads marked as expired
        """
        from app.models.upload import Upload
        return Upload.cleanup_expired()
