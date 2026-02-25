"""Centralized DNA concentration conversion utilities.

Consolidates ng/uL-to-nM conversion and volume calculations that
were previously duplicated in reaction_calculator.py.
"""
from app.calculator.constants import AVG_BP_MOLECULAR_WEIGHT


class DNAConcentrationConverter:
    """Stateless helper for DNA concentration unit conversions."""

    @staticmethod
    def ng_ul_to_nM(stock_ng_ul: float, plasmid_size_bp: int) -> float:
        """
        Convert ng/uL to nM using plasmid size.

        Formula: stock_nM = (stock_ng_ul * 1e6) / (plasmid_size_bp * AVG_BP_MOLECULAR_WEIGHT)

        Args:
            stock_ng_ul: Stock concentration in ng/uL.
            plasmid_size_bp: Plasmid size in base pairs.

        Returns:
            Stock concentration in nM. Returns 0.0 for invalid inputs.
        """
        if stock_ng_ul <= 0 or plasmid_size_bp <= 0:
            return 0.0
        return (stock_ng_ul * 1e6) / (plasmid_size_bp * AVG_BP_MOLECULAR_WEIGHT)

    @staticmethod
    def nM_to_volume(
        target_nM: float,
        stock_nM: float,
        reaction_volume_ul: float,
    ) -> float:
        """
        Calculate DNA volume to achieve a target nM concentration.

        V_DNA = (C_final * V_rxn) / C_stock

        Args:
            target_nM: Target final DNA concentration in nM.
            stock_nM: Stock DNA concentration in nM.
            reaction_volume_ul: Total reaction volume in uL.

        Returns:
            DNA volume in uL. Returns 0.0 if stock_nM <= 0.
        """
        if stock_nM <= 0:
            return 0.0
        return (target_nM * reaction_volume_ul) / stock_nM

    @staticmethod
    def compute_achieved_nM(
        volume_ul: float,
        stock_nM: float,
        reaction_volume_ul: float,
    ) -> float:
        """
        Compute the achieved nM concentration from a given volume.

        achieved_nM = (volume_ul * stock_nM) / reaction_volume_ul

        Args:
            volume_ul: Volume of DNA added in uL.
            stock_nM: Stock DNA concentration in nM.
            reaction_volume_ul: Total reaction volume in uL.

        Returns:
            Achieved concentration in nM. Returns 0.0 if reaction_volume_ul <= 0.
        """
        if reaction_volume_ul <= 0:
            return 0.0
        return (volume_ul * stock_nM) / reaction_volume_ul
