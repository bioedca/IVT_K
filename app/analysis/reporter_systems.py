"""
Reporter System Metadata for IVT Kinetics Analyzer.

Sprint 9.6: Reporter system metadata (PRD Lines 2385, 8696)

This module defines metadata for fluorogenic RNA reporter systems
commonly used in IVT kinetics experiments.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ReporterSystemInfo:
    """
    Metadata for a fluorogenic reporter system.

    Attributes:
        name: Display name of the reporter system
        fluorophore: The small molecule fluorophore used
        aptamer_type: The RNA aptamer type (e.g., "Spinach", "Broccoli")
        excitation_nm: Peak excitation wavelength in nanometers
        emission_nm: Peak emission wavelength in nanometers
        typical_background_rfu: Typical background fluorescence (RFU)
        typical_max_rfu: Typical maximum fluorescence (RFU)
        description: Brief description of the reporter system
        reference: Publication reference or DOI
    """
    name: str
    fluorophore: str
    aptamer_type: str
    excitation_nm: int
    emission_nm: int
    typical_background_rfu: float
    typical_max_rfu: float
    description: str
    reference: Optional[str] = None


# Known reporter systems
REPORTER_SYSTEMS: Dict[str, ReporterSystemInfo] = {
    "iSpinach": ReporterSystemInfo(
        name="iSpinach",
        fluorophore="DFHBI-1T",
        aptamer_type="Spinach",
        excitation_nm=482,
        emission_nm=505,
        typical_background_rfu=100.0,
        typical_max_rfu=50000.0,
        description="Improved Spinach aptamer with enhanced brightness and thermal stability",
        reference="Autour et al., Nucleic Acids Res. 2016"
    ),
    "Broccoli": ReporterSystemInfo(
        name="Broccoli",
        fluorophore="DFHBI-1T",
        aptamer_type="Broccoli",
        excitation_nm=472,
        emission_nm=507,
        typical_background_rfu=80.0,
        typical_max_rfu=40000.0,
        description="Broccoli aptamer - selected for cellular imaging applications",
        reference="Filonov et al., J Am Chem Soc. 2014"
    ),
    "Spinach2": ReporterSystemInfo(
        name="Spinach2",
        fluorophore="DFHBI",
        aptamer_type="Spinach",
        excitation_nm=469,
        emission_nm=501,
        typical_background_rfu=150.0,
        typical_max_rfu=45000.0,
        description="Second-generation Spinach aptamer with improved folding",
        reference="Strack et al., Nat Methods. 2013"
    ),
    "Corn": ReporterSystemInfo(
        name="Corn",
        fluorophore="DFHO",
        aptamer_type="Corn",
        excitation_nm=505,
        emission_nm=545,
        typical_background_rfu=50.0,
        typical_max_rfu=30000.0,
        description="Yellow-emitting aptamer for orthogonal imaging",
        reference="Song et al., J Am Chem Soc. 2017"
    ),
    "Mango": ReporterSystemInfo(
        name="Mango",
        fluorophore="TO1-Biotin",
        aptamer_type="Mango",
        excitation_nm=510,
        emission_nm=535,
        typical_background_rfu=30.0,
        typical_max_rfu=25000.0,
        description="Thiazole orange-binding aptamer with low background",
        reference="Dolgosheina et al., ACS Chem Biol. 2014"
    ),
    "Pepper": ReporterSystemInfo(
        name="Pepper",
        fluorophore="HBC",
        aptamer_type="Pepper",
        excitation_nm=580,
        emission_nm=620,
        typical_background_rfu=40.0,
        typical_max_rfu=35000.0,
        description="Red-shifted aptamer for multiplexing applications",
        reference="Chen et al., Nat Chem Biol. 2019"
    ),
}


def get_reporter_system(name: str) -> Optional[ReporterSystemInfo]:
    """
    Get metadata for a reporter system by name.

    Args:
        name: The reporter system name (case-insensitive)

    Returns:
        ReporterSystemInfo or None if not found
    """
    # Try exact match first
    if name in REPORTER_SYSTEMS:
        return REPORTER_SYSTEMS[name]

    # Try case-insensitive match
    name_lower = name.lower()
    for key, info in REPORTER_SYSTEMS.items():
        if key.lower() == name_lower:
            return info

    return None


def list_reporter_systems() -> List[str]:
    """
    Get list of known reporter system names.

    Returns:
        List of reporter system names
    """
    return list(REPORTER_SYSTEMS.keys())


def get_all_reporter_systems() -> Dict[str, ReporterSystemInfo]:
    """
    Get all reporter system metadata.

    Returns:
        Dict mapping names to ReporterSystemInfo objects
    """
    return REPORTER_SYSTEMS.copy()


def validate_reporter_system(name: str) -> bool:
    """
    Check if a reporter system name is known.

    Args:
        name: The reporter system name to validate

    Returns:
        True if the reporter system is known
    """
    return get_reporter_system(name) is not None


def suggest_qc_thresholds(reporter_name: str) -> Dict[str, float]:
    """
    Suggest QC thresholds based on reporter system.

    Different reporter systems have different typical fluorescence ranges,
    which can inform appropriate QC thresholds.

    Args:
        reporter_name: The reporter system name

    Returns:
        Dict with suggested threshold values, or defaults if unknown
    """
    info = get_reporter_system(reporter_name)

    if info is None:
        # Return sensible defaults
        return {
            "empty_well_threshold": 100.0,
            "saturation_threshold": 0.95,
            "snr_threshold": 10.0,
        }

    return {
        # Empty wells should have fluorescence below typical background * 2
        "empty_well_threshold": info.typical_background_rfu * 2,
        # Standard saturation threshold
        "saturation_threshold": 0.95,
        # SNR threshold based on typical background
        "snr_threshold": 10.0,
    }
