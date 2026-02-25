"""Validators for IVT reaction calculator inputs and outputs."""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum

from .constants import (
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    MIN_REPLICATES,
    MAX_TEMPLATES_RECOMMENDED,
    MAX_TEMPLATES_ABSOLUTE,
    DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
    PlateFormat,
    PLATE_CONSTRAINTS,
    CHECKERBOARD_USABLE_WELLS_384,
)


class ValidationLevel(Enum):
    """Severity level for validation messages."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationMessage:
    """A single validation message."""
    level: ValidationLevel
    field: str
    message: str
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    messages: List[ValidationMessage] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.level == ValidationLevel.ERROR]

    @property
    def warnings(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.level == ValidationLevel.WARNING]

    @property
    def infos(self) -> List[ValidationMessage]:
        return [m for m in self.messages if m.level == ValidationLevel.INFO]


def validate_volume(
    volume_ul: float,
    field_name: str,
    min_volume: float = MIN_PIPETTABLE_VOLUME_UL,
    max_volume: Optional[float] = None,
) -> ValidationResult:
    """
    Validate a single volume value.

    Args:
        volume_ul: Volume to validate
        field_name: Name of field for error messages
        min_volume: Minimum allowed volume
        max_volume: Maximum allowed volume (optional)

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if volume_ul < 0:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field=field_name,
            message=f"Volume cannot be negative ({volume_ul:.3f} µL)",
        ))
        return result

    if volume_ul < min_volume:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field=field_name,
            message=f"Volume {volume_ul:.3f} µL below minimum {min_volume} µL",
            suggestion="Consider DNA dilution or reaction scale-up",
        ))
    elif volume_ul < WARN_PIPETTABLE_VOLUME_UL:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field=field_name,
            message=f"Volume {volume_ul:.3f} µL may reduce pipetting accuracy",
            suggestion="Use 1 µL or greater for best accuracy",
        ))

    if max_volume is not None and volume_ul > max_volume:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field=field_name,
            message=f"Volume {volume_ul:.3f} µL exceeds maximum {max_volume} µL",
            suggestion="Consider splitting across multiple wells",
        ))

    return result


def validate_concentration(
    concentration: float,
    field_name: str,
    min_concentration: float = 0.0,
    max_concentration: Optional[float] = None,
) -> ValidationResult:
    """
    Validate a concentration value.

    Args:
        concentration: Concentration to validate
        field_name: Name of field for error messages
        min_concentration: Minimum allowed concentration
        max_concentration: Maximum allowed concentration (optional)

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if concentration < min_concentration:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field=field_name,
            message=f"Concentration {concentration} below minimum {min_concentration}",
        ))

    if max_concentration is not None and concentration > max_concentration:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field=field_name,
            message=f"Concentration {concentration} exceeds maximum {max_concentration}",
        ))

    return result


def validate_reaction_parameters(
    dna_mass_ug: float,
    n_replicates: int,
    n_constructs: int,
    negative_template_count: int = DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
    negative_dye_count: int = 0,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> ValidationResult:
    """
    Validate overall reaction setup parameters.

    Args:
        dna_mass_ug: DNA mass per reaction
        n_replicates: Replicates per construct
        n_constructs: Number of DNA templates (including anchors)
        negative_template_count: -Template controls
        negative_dye_count: -DFHBI controls
        plate_format: Plate format

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    # DNA mass
    if dna_mass_ug <= 0:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="dna_mass_ug",
            message="DNA mass must be positive",
        ))
    elif dna_mass_ug < 1:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field="dna_mass_ug",
            message=f"DNA mass {dna_mass_ug} µg is very low",
            suggestion="Typical range is 10-50 µg",
        ))
    elif dna_mass_ug > 100:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field="dna_mass_ug",
            message=f"DNA mass {dna_mass_ug} µg is very high",
            suggestion="Typical range is 10-50 µg",
        ))

    # Replicates
    if n_replicates < MIN_REPLICATES:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="n_replicates",
            message=f"Minimum {MIN_REPLICATES} replicates required for statistical validity",
        ))

    # Template count
    if n_constructs < 1:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="n_constructs",
            message="At least one construct is required",
        ))
    elif n_constructs > MAX_TEMPLATES_ABSOLUTE:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="n_constructs",
            message=f"Maximum {MAX_TEMPLATES_ABSOLUTE} templates allowed",
            suggestion="Split into multiple experiments",
        ))
    elif n_constructs > MAX_TEMPLATES_RECOMMENDED:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field="n_constructs",
            message=f"{n_constructs} templates exceeds recommended maximum of {MAX_TEMPLATES_RECOMMENDED}",
            suggestion="Practical experiments typically use 3-4 templates",
        ))

    # Negative controls
    if negative_template_count < 2:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field="negative_template_count",
            message=f"-Template control count ({negative_template_count}) below recommended minimum of 2",
            suggestion="Use at least 2-3 -Template control wells per plate",
        ))

    # Well capacity
    total_wells = (n_constructs * n_replicates) + negative_template_count + negative_dye_count
    constraints = PLATE_CONSTRAINTS[plate_format]

    if plate_format == PlateFormat.WELL_96:
        max_wells = 96
    else:
        max_wells = CHECKERBOARD_USABLE_WELLS_384

    if total_wells > max_wells:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="total_wells",
            message=f"Total wells ({total_wells}) exceeds plate capacity ({max_wells})",
            suggestion="Consider splitting across multiple plates",
        ))
    elif total_wells > max_wells * 0.9:
        result.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            field="total_wells",
            message=f"Plate is {total_wells / max_wells * 100:.0f}% full",
            suggestion="Leave some wells free for flexibility",
        ))

    return result


def validate_construct_list(
    constructs: List[dict],
    require_unregulated: bool = True,
) -> ValidationResult:
    """
    Validate a list of constructs for the calculator.

    Args:
        constructs: List of construct dicts
        require_unregulated: Whether unregulated construct is required

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if not constructs:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="constructs",
            message="At least one construct is required",
        ))
        return result

    # Check for required fields
    has_unregulated = False
    wt_families = set()
    mutant_families = set()

    for i, construct in enumerate(constructs):
        # Required fields
        if 'name' not in construct:
            result.is_valid = False
            result.messages.append(ValidationMessage(
                level=ValidationLevel.ERROR,
                field=f"constructs[{i}]",
                message="Construct missing 'name' field",
            ))
            continue

        name = construct['name']

        # Stock concentration
        stock_conc = construct.get('stock_concentration_ng_ul', 0)
        if stock_conc <= 0:
            result.is_valid = False
            result.messages.append(ValidationMessage(
                level=ValidationLevel.ERROR,
                field=f"constructs[{i}].stock_concentration_ng_ul",
                message=f"Construct '{name}' has invalid stock concentration",
            ))

        # Track construct types
        is_unregulated = construct.get('is_unregulated', False)
        is_wildtype = construct.get('is_wildtype', False)
        family = construct.get('family')

        if is_unregulated:
            has_unregulated = True

        if family:
            if is_wildtype:
                wt_families.add(family)
            elif not is_unregulated:
                # Only non-unregulated, non-WT constructs are "mutants" needing a WT
                mutant_families.add(family)

    # Check for unregulated
    if require_unregulated and not has_unregulated:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="constructs",
            message="Reporter-only (unregulated) construct is required",
            suggestion="Add the project's reporter-only construct to the experiment",
        ))

    # Check that each family with mutants has a WT
    families_missing_wt = mutant_families - wt_families
    if families_missing_wt:
        result.is_valid = False
        for family in families_missing_wt:
            result.messages.append(ValidationMessage(
                level=ValidationLevel.ERROR,
                field="constructs",
                message=f"Family '{family}' has mutants but no wild-type",
                suggestion=f"Add WT construct for {family} family",
            ))

    return result


def validate_well_volume(
    volume_ul: float,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> ValidationResult:
    """
    Validate that a volume is appropriate for the plate format.

    Args:
        volume_ul: Volume to validate
        plate_format: Plate format

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)
    constraints = PLATE_CONSTRAINTS[plate_format]

    if volume_ul < constraints.min_well_volume_ul:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="well_volume",
            message=(
                f"Volume {volume_ul:.1f} µL below minimum "
                f"{constraints.min_well_volume_ul} µL for {plate_format.value}-well plates"
            ),
            suggestion="Scale up reaction volume or use different plate format",
        ))

    if volume_ul > constraints.max_well_volume_ul:
        result.is_valid = False
        result.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            field="well_volume",
            message=(
                f"Volume {volume_ul:.1f} µL exceeds maximum "
                f"{constraints.max_well_volume_ul} µL for {plate_format.value}-well plates"
            ),
            suggestion="Split reaction across multiple wells",
        ))

    if result.is_valid:
        if volume_ul < constraints.optimal_min_ul:
            result.messages.append(ValidationMessage(
                level=ValidationLevel.WARNING,
                field="well_volume",
                message=(
                    f"Volume {volume_ul:.1f} µL below optimal range "
                    f"({constraints.optimal_min_ul}-{constraints.optimal_max_ul} µL)"
                ),
            ))
        elif volume_ul > constraints.optimal_max_ul:
            result.messages.append(ValidationMessage(
                level=ValidationLevel.WARNING,
                field="well_volume",
                message=(
                    f"Volume {volume_ul:.1f} µL above optimal range "
                    f"({constraints.optimal_min_ul}-{constraints.optimal_max_ul} µL)"
                ),
            ))

    return result


def validate_checkerboard_position(
    row: int,
    col: int,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a position is valid for 384-well checkerboard pattern.

    Valid positions: (row + col) is even

    Args:
        row: 0-indexed row number
        col: 0-indexed column number

    Returns:
        Tuple of (is_valid, error_message)
    """
    if (row + col) % 2 == 0:
        return (True, None)
    else:
        row_letter = chr(ord('A') + row)
        return (
            False,
            f"Position {row_letter}{col + 1} is not valid for checkerboard pattern"
        )


def format_validation_result(result: ValidationResult) -> str:
    """
    Format validation result as text.

    Args:
        result: ValidationResult to format

    Returns:
        Formatted text
    """
    lines = []

    if result.is_valid:
        lines.append("✓ Validation passed")
    else:
        lines.append("✗ Validation failed")

    if result.errors:
        lines.append("\nERRORS:")
        for msg in result.errors:
            lines.append(f"  ✗ [{msg.field}] {msg.message}")
            if msg.suggestion:
                lines.append(f"    → {msg.suggestion}")

    if result.warnings:
        lines.append("\nWARNINGS:")
        for msg in result.warnings:
            lines.append(f"  ⚠ [{msg.field}] {msg.message}")
            if msg.suggestion:
                lines.append(f"    → {msg.suggestion}")

    if result.infos:
        lines.append("\nINFO:")
        for msg in result.infos:
            lines.append(f"  ℹ [{msg.field}] {msg.message}")

    return "\n".join(lines)
