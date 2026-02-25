"""
Sprint 9: Reporter Systems Metadata Tests

Tests for the reporter system metadata module.

PRD Reference: Phase 12.9 - Additional reporter systems
"""
import pytest

from app.analysis.reporter_systems import (
    ReporterSystemInfo,
    REPORTER_SYSTEMS,
    get_reporter_system,
    list_reporter_systems,
    get_all_reporter_systems,
    validate_reporter_system,
    suggest_qc_thresholds,
)


class TestReporterSystemInfo:
    """Tests for ReporterSystemInfo dataclass."""

    def test_reporter_system_info_fields(self):
        """Test ReporterSystemInfo has expected fields."""
        info = ReporterSystemInfo(
            name="Test",
            fluorophore="TestFluor",
            aptamer_type="TestAptamer",
            excitation_nm=480,
            emission_nm=510,
            typical_background_rfu=100.0,
            typical_max_rfu=50000.0,
            description="Test reporter",
            reference="Test et al., 2024"
        )

        assert info.name == "Test"
        assert info.fluorophore == "TestFluor"
        assert info.excitation_nm == 480
        assert info.emission_nm == 510
        assert info.typical_background_rfu == 100.0
        assert info.reference == "Test et al., 2024"

    def test_reporter_system_info_optional_reference(self):
        """Test reference field is optional."""
        info = ReporterSystemInfo(
            name="Test",
            fluorophore="TestFluor",
            aptamer_type="TestAptamer",
            excitation_nm=480,
            emission_nm=510,
            typical_background_rfu=100.0,
            typical_max_rfu=50000.0,
            description="Test reporter"
        )

        assert info.reference is None


class TestKnownReporterSystems:
    """Tests for known reporter systems."""

    def test_ispinach_is_known(self):
        """iSpinach should be a known reporter system."""
        info = get_reporter_system("iSpinach")

        assert info is not None
        assert info.name == "iSpinach"
        assert info.fluorophore == "DFHBI-1T"
        assert info.aptamer_type == "Spinach"
        assert 400 < info.excitation_nm < 550
        assert 450 < info.emission_nm < 600

    def test_broccoli_is_known(self):
        """Broccoli should be a known reporter system."""
        info = get_reporter_system("Broccoli")

        assert info is not None
        assert info.name == "Broccoli"
        assert info.fluorophore == "DFHBI-1T"

    def test_spinach2_is_known(self):
        """Spinach2 should be a known reporter system."""
        info = get_reporter_system("Spinach2")

        assert info is not None
        assert info.aptamer_type == "Spinach"

    def test_corn_is_known(self):
        """Corn should be a known reporter system."""
        info = get_reporter_system("Corn")

        assert info is not None
        # Corn uses DFHO fluorophore, yellow emission
        assert info.emission_nm > 530

    def test_mango_is_known(self):
        """Mango should be a known reporter system."""
        info = get_reporter_system("Mango")

        assert info is not None
        assert "TO1" in info.fluorophore

    def test_pepper_is_known(self):
        """Pepper should be a known reporter system."""
        info = get_reporter_system("Pepper")

        assert info is not None
        # Pepper is red-shifted
        assert info.emission_nm > 600


class TestGetReporterSystem:
    """Tests for get_reporter_system function."""

    def test_get_existing_reporter(self):
        """Get existing reporter by name."""
        info = get_reporter_system("iSpinach")
        assert info is not None
        assert info.name == "iSpinach"

    def test_get_nonexistent_reporter(self):
        """Get nonexistent reporter returns None."""
        info = get_reporter_system("NonexistentReporter")
        assert info is None

    def test_get_reporter_case_insensitive(self):
        """Get reporter should be case-insensitive."""
        info1 = get_reporter_system("ispinach")
        info2 = get_reporter_system("ISPINACH")
        info3 = get_reporter_system("iSpinach")

        assert info1 is not None
        assert info2 is not None
        assert info3 is not None
        assert info1.name == info2.name == info3.name


class TestListReporterSystems:
    """Tests for list_reporter_systems function."""

    def test_list_returns_known_reporters(self):
        """List should contain known reporter systems."""
        reporters = list_reporter_systems()

        assert isinstance(reporters, list)
        assert len(reporters) >= 6  # At least 6 known systems
        assert "iSpinach" in reporters
        assert "Broccoli" in reporters

    def test_list_returns_strings(self):
        """All items in list should be strings."""
        reporters = list_reporter_systems()

        for name in reporters:
            assert isinstance(name, str)


class TestGetAllReporterSystems:
    """Tests for get_all_reporter_systems function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        all_systems = get_all_reporter_systems()
        assert isinstance(all_systems, dict)

    def test_returns_copy(self):
        """Should return a copy, not the original."""
        all_systems = get_all_reporter_systems()
        original_count = len(REPORTER_SYSTEMS)

        # Modify the returned dict
        all_systems["test"] = None

        # Original should be unchanged
        assert len(REPORTER_SYSTEMS) == original_count

    def test_values_are_reporter_info(self):
        """All values should be ReporterSystemInfo objects."""
        all_systems = get_all_reporter_systems()

        for name, info in all_systems.items():
            assert isinstance(name, str)
            assert isinstance(info, ReporterSystemInfo)


class TestValidateReporterSystem:
    """Tests for validate_reporter_system function."""

    def test_validate_known_reporter(self):
        """Known reporter should validate True."""
        assert validate_reporter_system("iSpinach") is True
        assert validate_reporter_system("Broccoli") is True

    def test_validate_unknown_reporter(self):
        """Unknown reporter should validate False."""
        assert validate_reporter_system("UnknownReporter") is False

    def test_validate_case_insensitive(self):
        """Validation should be case-insensitive."""
        assert validate_reporter_system("ISPINACH") is True
        assert validate_reporter_system("ispinach") is True


class TestSuggestQCThresholds:
    """Tests for suggest_qc_thresholds function."""

    def test_suggest_for_known_reporter(self):
        """Suggest thresholds for known reporter."""
        thresholds = suggest_qc_thresholds("iSpinach")

        assert isinstance(thresholds, dict)
        assert "empty_well_threshold" in thresholds
        assert "saturation_threshold" in thresholds
        assert "snr_threshold" in thresholds

        # Empty well threshold should be based on background
        ispinach_info = get_reporter_system("iSpinach")
        assert thresholds["empty_well_threshold"] == ispinach_info.typical_background_rfu * 2

    def test_suggest_for_unknown_reporter(self):
        """Suggest sensible defaults for unknown reporter."""
        thresholds = suggest_qc_thresholds("UnknownReporter")

        assert isinstance(thresholds, dict)
        assert thresholds["empty_well_threshold"] == 100.0
        assert thresholds["saturation_threshold"] == 0.95
        assert thresholds["snr_threshold"] == 10.0

    def test_threshold_values_are_numeric(self):
        """All threshold values should be numeric."""
        for reporter_name in list_reporter_systems():
            thresholds = suggest_qc_thresholds(reporter_name)

            for key, value in thresholds.items():
                assert isinstance(value, (int, float))
                assert value >= 0


class TestReporterSystemConsistency:
    """Tests for consistency of reporter system data."""

    def test_excitation_less_than_emission(self):
        """Excitation wavelength should be less than emission."""
        for name, info in REPORTER_SYSTEMS.items():
            assert info.excitation_nm < info.emission_nm, \
                f"{name}: excitation ({info.excitation_nm}) should be < emission ({info.emission_nm})"

    def test_background_less_than_max(self):
        """Typical background should be less than typical max."""
        for name, info in REPORTER_SYSTEMS.items():
            assert info.typical_background_rfu < info.typical_max_rfu, \
                f"{name}: background ({info.typical_background_rfu}) should be < max ({info.typical_max_rfu})"

    def test_wavelengths_in_visible_range(self):
        """Wavelengths should be in visible range (380-750nm)."""
        for name, info in REPORTER_SYSTEMS.items():
            assert 380 <= info.excitation_nm <= 750, \
                f"{name}: excitation out of visible range"
            assert 380 <= info.emission_nm <= 750, \
                f"{name}: emission out of visible range"

    def test_all_have_descriptions(self):
        """All reporter systems should have descriptions."""
        for name, info in REPORTER_SYSTEMS.items():
            assert info.description, f"{name} missing description"
            assert len(info.description) > 10, f"{name} description too short"
