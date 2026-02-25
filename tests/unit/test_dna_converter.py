"""Tests for app.calculator.dna_converter DNA concentration utilities."""
import pytest

from app.calculator.constants import AVG_BP_MOLECULAR_WEIGHT
from app.calculator.dna_converter import DNAConcentrationConverter


class TestNgUlToNM:
    """Tests for DNAConcentrationConverter.ng_ul_to_nM()."""

    @pytest.mark.parametrize("ng_ul,bp", [
        (100, 5000),    # standard
        (500, 5000),    # high concentration
        (10, 5000),     # low concentration
        (100, 1000),    # small plasmid
        (100, 10000),   # medium plasmid
        (100, 50000),   # large plasmid
    ])
    def test_formula_accuracy(self, ng_ul, bp):
        """Conversion matches (ng_ul * 1e6) / (bp * AVG_BP_MOLECULAR_WEIGHT)."""
        result = DNAConcentrationConverter.ng_ul_to_nM(ng_ul, bp)
        expected = (ng_ul * 1e6) / (bp * AVG_BP_MOLECULAR_WEIGHT)
        assert result == pytest.approx(expected)

    def test_smaller_plasmid_yields_higher_nM(self):
        """Smaller plasmid → higher nM for same ng/uL."""
        assert DNAConcentrationConverter.ng_ul_to_nM(100, 1000) > \
               DNAConcentrationConverter.ng_ul_to_nM(100, 10000)

    def test_zero_concentration_returns_zero(self):
        result = DNAConcentrationConverter.ng_ul_to_nM(0, 5000)
        assert result == 0.0

    def test_negative_concentration_returns_zero(self):
        result = DNAConcentrationConverter.ng_ul_to_nM(-10, 5000)
        assert result == 0.0

    def test_zero_plasmid_size_returns_zero(self):
        result = DNAConcentrationConverter.ng_ul_to_nM(100, 0)
        assert result == 0.0

    def test_negative_plasmid_size_returns_zero(self):
        result = DNAConcentrationConverter.ng_ul_to_nM(100, -1000)
        assert result == 0.0


class TestNMToVolume:
    """Tests for DNAConcentrationConverter.nM_to_volume()."""

    def test_standard_calculation(self):
        """V_DNA = (target_nM * V_rxn) / stock_nM."""
        result = DNAConcentrationConverter.nM_to_volume(50, 200, 20)
        expected = (50 * 20) / 200
        assert result == pytest.approx(expected)

    def test_zero_stock_returns_zero(self):
        result = DNAConcentrationConverter.nM_to_volume(50, 0, 20)
        assert result == 0.0

    def test_negative_stock_returns_zero(self):
        result = DNAConcentrationConverter.nM_to_volume(50, -100, 20)
        assert result == 0.0


class TestComputeAchievedNM:
    """Tests for DNAConcentrationConverter.compute_achieved_nM()."""

    def test_standard_calculation(self):
        """achieved_nM = (volume_ul * stock_nM) / reaction_volume_ul."""
        result = DNAConcentrationConverter.compute_achieved_nM(5, 200, 20)
        expected = (5 * 200) / 20
        assert result == pytest.approx(expected)

    def test_zero_reaction_volume_returns_zero(self):
        result = DNAConcentrationConverter.compute_achieved_nM(5, 200, 0)
        assert result == 0.0

    def test_negative_reaction_volume_returns_zero(self):
        result = DNAConcentrationConverter.compute_achieved_nM(5, 200, -10)
        assert result == 0.0

    def test_roundtrip_consistency(self):
        """nM_to_volume → compute_achieved_nM should return the target nM."""
        target_nM = 50.0
        stock_nM = 200.0
        rxn_vol = 20.0
        volume = DNAConcentrationConverter.nM_to_volume(target_nM, stock_nM, rxn_vol)
        achieved = DNAConcentrationConverter.compute_achieved_nM(volume, stock_nM, rxn_vol)
        assert achieved == pytest.approx(target_nM)
