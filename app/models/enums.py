"""
Shared enums for model columns.

These string enums provide type safety for columns that use fixed string values.
Since they inherit from str, they are directly compatible with string comparisons
and existing database values (no migration needed).

Note: ``FoldChangeCategory`` is distinct from ``app.analysis.comparison.ComparisonType``
which describes the *hierarchy level* (PRIMARY, SECONDARY, TERTIARY).
``FoldChangeCategory`` describes the *biological comparison type* stored in
``FoldChange.comparison_type`` and ``PrecisionWeight.comparison_type``.
"""
import enum


class FoldChangeCategory(str, enum.Enum):
    """Biological comparison type stored in FoldChange.comparison_type."""
    MUTANT_WT = "mutant_wt"
    WT_UNREGULATED = "wt_unregulated"
    WITHIN_CONDITION = "within_condition"
    LIGAND_EFFECT = "ligand_effect"

    def __str__(self) -> str:
        return self.value

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)


class LigandCondition(str, enum.Enum):
    """Binary ligand condition labels for wells and comparisons."""
    PLUS_LIG = "+Lig"
    MINUS_LIG = "-Lig"

    def __str__(self) -> str:
        return self.value

    def __format__(self, format_spec: str) -> str:
        return self.value.__format__(format_spec)
