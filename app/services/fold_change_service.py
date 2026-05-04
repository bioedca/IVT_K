"""
Fold change computation service.

Handles computation of pairwise fold changes between test and control wells,
including within-condition comparisons (mutant vs WT, WT vs unregulated) and
ligand effect comparisons (+Lig vs -Lig for same construct).

Split from comparison_service.py as part of Phase 3 refactoring.
"""
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone

from sqlalchemy import or_

from app.extensions import db
from app.models import Construct
from app.models.experiment import Plate, Well, FitStatus
from app.models.fit_result import FoldChange
from app.models.enums import FoldChangeCategory, LigandCondition
from app.analysis.comparison import PairedAnalysis, ComparisonType

logger = logging.getLogger(__name__)


class FoldChangeService:
    """
    Service for computing pairwise fold changes between wells.

    Handles:
    - Primary comparisons (mutant vs WT on same plate)
    - Secondary comparisons (WT vs unregulated)
    - Ligand effect comparisons (+Lig vs -Lig for same construct)
    """

    @classmethod
    def compute_plate_fold_changes(
        cls,
        plate_id: int,
        overwrite: bool = False
    ) -> List[FoldChange]:
        """
        Compute all fold changes for wells on a plate.

        When ligand conditions (+Lig/-Lig) are present, comparisons are made
        within the same condition (e.g., mutant+Lig vs WT+Lig). Additionally,
        ligand effect comparisons are computed (same construct, +Lig vs -Lig).

        Args:
            plate_id: Plate ID
            overwrite: If True, recalculate existing fold changes

        Returns:
            List of FoldChange records created/updated
        """
        from app.services.comparison_graph_service import ComparisonError

        plate = Plate.query.get(plate_id)
        if not plate:
            raise ComparisonError(f"Plate {plate_id} not found")

        # Drop FoldChange rows whose test or control well on this plate is now excluded.
        # Why: the iteration loop below only generates pairs from non-excluded wells,
        # so it cannot reach (or overwrite) FCs whose underlying wells were excluded
        # after the row was first written. Without this, marking a well excluded leaves
        # stale FCs in the DB that downstream analyses (HierarchicalService, badge counts)
        # still pull. See fc_exclusion_no_effect_explained.md.
        cls._delete_orphan_fold_changes(plate_id)

        # Get all wells with successful fits (excluding manually excluded and FC-excluded wells)
        wells = Well.query.filter(
            Well.plate_id == plate_id,
            Well.fit_status == FitStatus.SUCCESS,
            Well.construct_id.isnot(None),
            Well.is_excluded == False,
            Well.exclude_from_fc == False,
        ).all()

        if not wells:
            logger.warning(f"No valid wells found on plate {plate_id}")
            return []

        # Check if any wells have ligand conditions
        has_ligand_conditions = any(w.ligand_condition for w in wells)

        # Group wells by (construct_id, ligand_condition)
        # When no ligand conditions, all wells have condition=None and behave as before
        wells_by_construct_condition: Dict[Tuple[int, Optional[str]], List[Well]] = {}
        for well in wells:
            key = (well.construct_id, well.ligand_condition)
            if key not in wells_by_construct_condition:
                wells_by_construct_condition[key] = []
            wells_by_construct_condition[key].append(well)

        # Also group by construct only (for finding which constructs are on plate)
        construct_ids_on_plate = set(w.construct_id for w in wells)

        # Determine unique conditions on the plate
        conditions = set(w.ligand_condition for w in wells)
        if not has_ligand_conditions:
            conditions = {None}  # Treat all as one condition

        # Get project to find anchor constructs
        project = plate.session.project

        # Find WT constructs on plate
        wt_constructs = Construct.query.filter(
            Construct.project_id == project.id,
            Construct.is_wildtype == True,
            Construct.id.in_(construct_ids_on_plate)
        ).all()

        # Build WT lookup by family
        wt_by_family: Dict[str, Construct] = {}
        for wt in wt_constructs:
            wt_by_family[wt.family] = wt

        # Find unregulated construct on plate
        unregulated = Construct.query.filter(
            Construct.project_id == project.id,
            Construct.is_unregulated == True,
            Construct.id.in_(construct_ids_on_plate)
        ).first()

        fold_changes = []
        analyzer = PairedAnalysis()

        # === WITHIN-CONDITION COMPARISONS ===
        # For each ligand condition, compute standard comparisons
        for condition in conditions:
            # Compute primary fold changes (mutant vs WT) within same condition
            for family, wt in wt_by_family.items():
                wt_wells = wells_by_construct_condition.get((wt.id, condition), [])
                if not wt_wells and condition is not None:
                    # Fallback: WT may lack ligand-specific wells; use None-condition WT
                    wt_wells = wells_by_construct_condition.get((wt.id, None), [])
                if not wt_wells:
                    continue

                # Get all mutants in this family on the plate
                family_mutants = Construct.query.filter(
                    Construct.project_id == project.id,
                    Construct.family == family,
                    Construct.is_wildtype == False,
                    Construct.is_unregulated == False,
                    Construct.id.in_(construct_ids_on_plate)
                ).all()

                for mutant in family_mutants:
                    mutant_wells = wells_by_construct_condition.get((mutant.id, condition), [])

                    for mutant_well in mutant_wells:
                        for wt_well in wt_wells:
                            fc = cls._compute_well_pair_fc(
                                mutant_well, wt_well, analyzer,
                                ComparisonType.PRIMARY, overwrite,
                                ligand_condition=condition,
                                comparison_type_str=FoldChangeCategory.WITHIN_CONDITION,
                            )
                            if fc:
                                fold_changes.append(fc)

            # Compute secondary fold changes (WT vs unregulated) within same condition
            if unregulated:
                unreg_wells = wells_by_construct_condition.get((unregulated.id, condition), [])
                if not unreg_wells and condition is not None:
                    unreg_wells = wells_by_construct_condition.get((unregulated.id, None), [])

                for wt in wt_by_family.values():
                    wt_wells = wells_by_construct_condition.get((wt.id, condition), [])
                    if not wt_wells and condition is not None:
                        wt_wells = wells_by_construct_condition.get((wt.id, None), [])

                    for wt_well in wt_wells:
                        for unreg_well in unreg_wells:
                            fc = cls._compute_well_pair_fc(
                                wt_well, unreg_well, analyzer,
                                ComparisonType.SECONDARY, overwrite,
                                ligand_condition=condition,
                                comparison_type_str=FoldChangeCategory.WITHIN_CONDITION,
                            )
                            if fc:
                                fold_changes.append(fc)

        # === LIGAND EFFECT COMPARISONS ===
        # Compare same construct across +Lig vs -Lig conditions.
        # Falls back to None-condition wells as control when explicit -Lig
        # wells don't exist (e.g., wells without ligand left unlabeled).
        if has_ligand_conditions and LigandCondition.PLUS_LIG in conditions:
            for construct_id in construct_ids_on_plate:
                plus_wells = wells_by_construct_condition.get((construct_id, LigandCondition.PLUS_LIG), [])

                # Prefer explicit -Lig wells; fall back to None-condition wells
                minus_wells = wells_by_construct_condition.get((construct_id, LigandCondition.MINUS_LIG), [])
                if not minus_wells:
                    minus_wells = wells_by_construct_condition.get((construct_id, None), [])

                if plus_wells and minus_wells:
                    for plus_well in plus_wells:
                        for minus_well in minus_wells:
                            # +Lig is "test", -Lig is "control" (fold change = +Lig / -Lig)
                            fc = cls._compute_well_pair_fc(
                                plus_well, minus_well, analyzer,
                                ComparisonType.PRIMARY, overwrite,
                                ligand_condition="+Lig/-Lig",
                                comparison_type_str=FoldChangeCategory.LIGAND_EFFECT,
                            )
                            if fc:
                                fold_changes.append(fc)

        db.session.commit()
        return fold_changes

    @classmethod
    def _delete_orphan_fold_changes(cls, plate_id: int) -> int:
        """
        Delete FoldChange rows on this plate whose test or control well is currently
        marked is_excluded=True or exclude_from_fc=True.

        Called from compute_plate_fold_changes so that excluding a well after FCs
        have been written actually removes the affected pairs from the database.

        Returns:
            Number of rows deleted.
        """
        excluded_well_ids = [
            row.id for row in db.session.query(Well.id).filter(
                Well.plate_id == plate_id,
                or_(Well.is_excluded == True, Well.exclude_from_fc == True),
            ).all()
        ]

        if not excluded_well_ids:
            return 0

        deleted = FoldChange.query.filter(
            or_(
                FoldChange.test_well_id.in_(excluded_well_ids),
                FoldChange.control_well_id.in_(excluded_well_ids),
            )
        ).delete(synchronize_session=False)

        if deleted:
            logger.info(
                "Deleted %d orphan FoldChange rows on plate %d "
                "referencing %d now-excluded well(s)",
                deleted, plate_id, len(excluded_well_ids),
            )

        return deleted

    @classmethod
    def _compute_well_pair_fc(
        cls,
        test_well: Well,
        control_well: Well,
        analyzer: PairedAnalysis,
        comparison_type: ComparisonType,
        overwrite: bool,
        ligand_condition: Optional[str] = None,
        comparison_type_str: Optional[str] = None,
    ) -> Optional[FoldChange]:
        """
        Compute fold change between a test and control well.

        Args:
            test_well: Test well
            control_well: Control well
            analyzer: PairedAnalysis instance
            comparison_type: Type of comparison
            overwrite: Whether to overwrite existing
            ligand_condition: Ligand condition ("+Lig", "-Lig", "+Lig/-Lig", or None)
            comparison_type_str: Comparison category ("within_condition", "ligand_effect", or None)

        Returns:
            FoldChange record or None
        """
        # Check for existing
        existing = FoldChange.query.filter_by(
            test_well_id=test_well.id,
            control_well_id=control_well.id
        ).first()

        if existing and not overwrite:
            return existing

        # Get fit results
        test_fit = test_well.fit_result
        control_fit = control_well.fit_result

        if not test_fit or not control_fit:
            return None

        # Compute fold change
        result = analyzer.compute_fold_change(
            test_fmax=test_fit.f_max,
            test_fmax_se=test_fit.f_max_se or 0.0,
            control_fmax=control_fit.f_max,
            control_fmax_se=control_fit.f_max_se or 0.0,
            test_kobs=test_fit.k_obs,
            test_kobs_se=test_fit.k_obs_se,
            control_kobs=control_fit.k_obs,
            control_kobs_se=control_fit.k_obs_se,
            test_tlag=test_fit.t_lag,
            test_tlag_se=test_fit.t_lag_se,
            control_tlag=control_fit.t_lag,
            control_tlag_se=control_fit.t_lag_se,
            test_construct_id=test_well.construct_id,
            control_construct_id=control_well.construct_id,
            comparison_type=comparison_type
        )

        if not result.is_valid:
            return None

        # Create or update record
        if existing:
            fc = existing
        else:
            fc = FoldChange(
                test_well_id=test_well.id,
                control_well_id=control_well.id
            )

        fc.fc_fmax = result.fc_fmax
        fc.fc_fmax_se = result.fc_fmax_se
        fc.fc_kobs = result.fc_kobs
        fc.fc_kobs_se = result.fc_kobs_se
        fc.delta_tlag = result.delta_tlag
        fc.delta_tlag_se = result.delta_tlag_se
        fc.log_fc_fmax = result.log_fc_fmax
        fc.log_fc_fmax_se = result.log_fc_fmax_se
        fc.log_fc_kobs = result.log_fc_kobs
        fc.log_fc_kobs_se = result.log_fc_kobs_se
        fc.ligand_condition = ligand_condition
        fc.comparison_type = comparison_type_str
        fc.computed_at = datetime.now(timezone.utc)

        if not existing:
            db.session.add(fc)

        return fc
