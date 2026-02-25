"""
Fold change calculation service.

Extracted from fitting_service.py (Phase 3 refactoring).

Handles:
- Paired fold change computation between test and control wells
- Fold change summary reporting
"""
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging

from app.extensions import db
from app.models.enums import FoldChangeCategory
from app.models.fit_result import FitResult as FitResultModel, FoldChange

from app.services.fit_computation_service import FittingError

logger = logging.getLogger(__name__)


class FoldChangeCalculationService:
    """
    Service for fold change calculations.

    Handles computing fold changes between test and control wells,
    and summarizing fold change data for display.
    """

    @classmethod
    def compute_fold_change(
        cls,
        test_well_id: int,
        control_well_id: int,
        force_recompute: bool = False
    ) -> FoldChange:
        """
        Compute fold change between test and control wells.

        Args:
            test_well_id: ID of test (mutant) well
            control_well_id: ID of control (WT or unregulated) well
            force_recompute: If True, recompute even if exists

        Returns:
            FoldChange database model

        Raises:
            FittingError: If wells not found or don't have fit results
        """
        # Check for existing
        existing = FoldChange.query.filter_by(
            test_well_id=test_well_id,
            control_well_id=control_well_id
        ).first()

        if existing and not force_recompute:
            return existing

        # Get fit results
        test_fit = FitResultModel.query.filter_by(well_id=test_well_id).first()
        control_fit = FitResultModel.query.filter_by(well_id=control_well_id).first()

        if not test_fit or not test_fit.converged:
            raise FittingError(f"Test well {test_well_id} has no valid fit")
        if not control_fit or not control_fit.converged:
            raise FittingError(f"Control well {control_well_id} has no valid fit")

        # Compute fold changes
        if existing:
            fc = existing
        else:
            fc = FoldChange(
                test_well_id=test_well_id,
                control_well_id=control_well_id
            )

        # FC for F_max
        if test_fit.f_max and control_fit.f_max and control_fit.f_max > 0:
            fc.fc_fmax = test_fit.f_max / control_fit.f_max

            # Propagate uncertainty (ratio of independent variables)
            # SE(A/B) ~ (A/B) * sqrt((SE_A/A)^2 + (SE_B/B)^2)
            if test_fit.f_max_se and control_fit.f_max_se:
                rel_se_test = test_fit.f_max_se / test_fit.f_max if test_fit.f_max != 0 else 0
                rel_se_ctrl = control_fit.f_max_se / control_fit.f_max if control_fit.f_max != 0 else 0
                fc.fc_fmax_se = fc.fc_fmax * np.sqrt(rel_se_test**2 + rel_se_ctrl**2)

            # Log fold change
            if fc.fc_fmax > 0:
                fc.log_fc_fmax = np.log2(fc.fc_fmax)
                if fc.fc_fmax_se:
                    # SE of log(X) ~ SE_X / X
                    fc.log_fc_fmax_se = fc.fc_fmax_se / (fc.fc_fmax * np.log(2))

        # FC for k_obs
        if test_fit.k_obs and control_fit.k_obs and control_fit.k_obs > 0:
            fc.fc_kobs = test_fit.k_obs / control_fit.k_obs

            if test_fit.k_obs_se and control_fit.k_obs_se:
                rel_se_test = test_fit.k_obs_se / test_fit.k_obs if test_fit.k_obs != 0 else 0
                rel_se_ctrl = control_fit.k_obs_se / control_fit.k_obs if control_fit.k_obs != 0 else 0
                fc.fc_kobs_se = fc.fc_kobs * np.sqrt(rel_se_test**2 + rel_se_ctrl**2)

            if fc.fc_kobs > 0:
                fc.log_fc_kobs = np.log2(fc.fc_kobs)
                if fc.fc_kobs_se:
                    fc.log_fc_kobs_se = fc.fc_kobs_se / (fc.fc_kobs * np.log(2))

        # Delta t_lag (difference, not ratio)
        if test_fit.t_lag is not None and control_fit.t_lag is not None:
            fc.delta_tlag = test_fit.t_lag - control_fit.t_lag

            if test_fit.t_lag_se and control_fit.t_lag_se:
                fc.delta_tlag_se = np.sqrt(test_fit.t_lag_se**2 + control_fit.t_lag_se**2)

        fc.computed_at = datetime.now(timezone.utc)
        db.session.add(fc)
        db.session.commit()

        return fc

    @classmethod
    def get_fold_change_summary(cls, project_id: int) -> List[Dict[str, Any]]:
        """
        Get fold change data for display in Step 4 table.

        Args:
            project_id: Project ID

        Returns:
            List of fold change records with construct info
        """
        from app.models import Well, Plate, ExperimentalSession, Construct
        from sqlalchemy.orm import aliased

        TestWell = aliased(Well, name='test_well')
        ControlWell = aliased(Well, name='control_well')

        # Query fold changes with both test and control wells joined
        fold_changes = (
            db.session.query(FoldChange, TestWell, ControlWell)
            .join(TestWell, FoldChange.test_well_id == TestWell.id)
            .join(ControlWell, FoldChange.control_well_id == ControlWell.id)
            .join(Plate, TestWell.plate_id == Plate.id)
            .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
            .filter(ExperimentalSession.project_id == project_id)
            .order_by(FoldChange.computed_at.desc())
            .all()
        )

        # Batch-load all construct IDs
        all_construct_ids = set()
        for fc, tw, cw in fold_changes:
            if tw.construct_id:
                all_construct_ids.add(tw.construct_id)
            if cw.construct_id:
                all_construct_ids.add(cw.construct_id)

        constructs_by_id = {
            c.id: c
            for c in Construct.query.filter(Construct.id.in_(all_construct_ids)).all()
        } if all_construct_ids else {}

        results = []
        for fc, test_well, control_well in fold_changes:
            test_construct = constructs_by_id.get(test_well.construct_id) if test_well.construct_id else None
            control_construct = constructs_by_id.get(control_well.construct_id) if control_well.construct_id else None

            # Determine comparison type
            if test_construct:
                if test_construct.is_wildtype:
                    comparison_type = "WT -> Unreg"
                elif not test_construct.is_wildtype and not test_construct.is_unregulated:
                    comparison_type = "Mutant -> WT"
                else:
                    comparison_type = "Other"
            else:
                comparison_type = "Unknown"

            # Override comparison type for ligand effect comparisons
            if fc.comparison_type == FoldChangeCategory.LIGAND_EFFECT:
                comparison_type = "Ligand Effect"

            results.append({
                "id": fc.id,
                "test_well_id": fc.test_well_id,
                "test_well_position": test_well.position,
                "test_plate_number": test_well.plate.plate_number if test_well.plate else "?",
                "control_well_id": fc.control_well_id,
                "control_well_position": control_well.position,
                "control_plate_number": control_well.plate.plate_number if control_well.plate else "?",
                "test_construct_name": test_construct.identifier if test_construct else "Unknown",
                "control_construct_name": control_construct.identifier if control_construct else "Unknown",
                "comparison_type": comparison_type,
                "ligand_condition": fc.ligand_condition,
                "fc_comparison_type": fc.comparison_type,
                "fc_fmax": fc.fc_fmax,
                "fc_fmax_se": fc.fc_fmax_se,
                "fc_kobs": fc.fc_kobs,
                "fc_kobs_se": fc.fc_kobs_se,
                "delta_tlag": fc.delta_tlag,
                "delta_tlag_se": fc.delta_tlag_se,
                "computed_at": fc.computed_at.isoformat() if fc.computed_at else None,
            })

        return results
