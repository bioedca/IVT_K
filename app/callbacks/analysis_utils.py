"""Shared utility functions for analysis callback modules."""
from typing import Dict, Any, Optional

import dash_mantine_components as dmc

from app.logging_config import get_logger

logger = get_logger(__name__)


def _extract_tier_info(model_tier_metadata):
    """Extract tier information from model_tier_metadata.

    Handles both legacy flat format (``{"tier": "tier_3", ...}``) and the
    per-family format (``{"per_family": {"FamA": {"tier": "tier_2a"}, ...}}``).

    Returns:
        dict with keys:
            - ``has_tier_3``: True if any family is tier_3
            - ``max_tier``: the "highest" tier across families (tier_3 > tier_2a > tier_1)
            - ``per_family``: dict of ``{family: tier_str}`` (empty for legacy)
            - ``frequentist_warnings``: list of warning strings
    """
    meta = model_tier_metadata or {}
    per_family = meta.get("per_family")

    if per_family and isinstance(per_family, dict):
        # Per-family format
        tier_order = {"tier_1": 0, "tier_2a": 1, "tier_2b": 1, "tier_3": 2}
        family_tiers = {}
        max_tier = "tier_1"
        for fam_name, fam_meta in per_family.items():
            if isinstance(fam_meta, dict):
                t = fam_meta.get("tier", "tier_1")
                family_tiers[fam_name] = t
                if tier_order.get(t, 0) > tier_order.get(max_tier, 0):
                    max_tier = t

        return {
            "has_tier_3": max_tier == "tier_3",
            "max_tier": max_tier,
            "per_family": family_tiers,
            "frequentist_warnings": meta.get("frequentist_warnings", []),
        }

    # Legacy flat format
    tier = meta.get("tier", "")
    return {
        "has_tier_3": tier == "tier_3",
        "max_tier": tier or "tier_1",
        "per_family": {},
        "frequentist_warnings": meta.get("frequentist_warnings", []),
    }


def _get_pooled_fc(construct_id: int, control_construct_id: int, project_id: int) -> Optional[Dict[str, float]]:
    """
    Get pooled primary fold-change statistics for a construct pair from the DB.

    Queries FoldChange records where the test well belongs to ``construct_id``
    and the control well belongs to ``control_construct_id``, then pools log-FC
    values using inverse-variance weighting.

    Returns:
        Dict with mean_log_fc, pooled_se, n  — or None if no data.
    """
    from app.extensions import db
    from app.models.fit_result import FoldChange
    from app.models.experiment import Well, Plate
    from sqlalchemy.orm import aliased
    import numpy as np

    # Join twice on Well to filter both test and control construct
    test_well = aliased(Well, name="tw")
    ctrl_well = aliased(Well, name="cw")

    rows = (
        db.session.query(FoldChange.log_fc_fmax, FoldChange.log_fc_fmax_se)
        .join(test_well, FoldChange.test_well_id == test_well.id)
        .join(ctrl_well, FoldChange.control_well_id == ctrl_well.id)
        .join(Plate, test_well.plate_id == Plate.id)
        .filter(
            Plate.session.has(project_id=project_id),
            test_well.construct_id == construct_id,
            ctrl_well.construct_id == control_construct_id,
            FoldChange.log_fc_fmax.isnot(None),
        )
        .all()
    )

    if not rows:
        return None

    log_fcs = [r[0] for r in rows]
    # Paired values for inverse-variance weighting (only rows with valid SE)
    paired = [(r[0], r[1]) for r in rows if r[1] is not None and r[1] > 0]

    if paired:
        # Inverse-variance weighted mean and pooled SE
        fc_arr = np.array([p[0] for p in paired])
        weights = np.array([1.0 / (p[1] ** 2) for p in paired])
        mean_log_fc = float(np.sum(weights * fc_arr) / np.sum(weights))
        pooled_se = float(1.0 / np.sqrt(np.sum(weights)))
    else:
        mean_log_fc = float(np.mean(log_fcs))
        pooled_se = float(np.std(log_fcs, ddof=1) / np.sqrt(len(log_fcs))) if len(log_fcs) > 1 else 0.1

    return {"mean_log_fc": mean_log_fc, "pooled_se": pooled_se, "n": len(log_fcs)}


def _fc_dict_from_log(mean_log_fc: float, se: float) -> Dict[str, Any]:
    """Convert log-FC summary to a result dict with fc, ci_lower, ci_upper."""
    import numpy as np
    fc = float(np.exp(mean_log_fc))
    ci_lower = float(np.exp(mean_log_fc - 1.96 * se))
    ci_upper = float(np.exp(mean_log_fc + 1.96 * se))
    return {"is_valid": True, "fc": fc, "ci_lower": ci_lower, "ci_upper": ci_upper}


def _compute_derived_fc_from_db(
    source_id: int,
    target_id: int,
    wt_id: Optional[int],
    project_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compute a TWO_HOP derived FC (mutant -> WT -> unregulated) from DB records.

    Chains the primary FC (source->WT) and secondary FC (WT->target) in log space.
    """
    import numpy as np

    if wt_id is None:
        return None

    primary = _get_pooled_fc(source_id, wt_id, project_id)
    secondary = _get_pooled_fc(wt_id, target_id, project_id)

    if not primary or not secondary:
        return None

    combined_log_fc = primary["mean_log_fc"] + secondary["mean_log_fc"]
    combined_se = float(np.sqrt(primary["pooled_se"] ** 2 + secondary["pooled_se"] ** 2))

    return _fc_dict_from_log(combined_log_fc, combined_se)


def _compute_cross_family_fc_from_db(
    source_id: int,
    target_id: int,
    project_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Compute a FOUR_HOP cross-family FC (M1 -> WT1 -> Unreg -> WT2 -> M2) from DB.

    Derives the FC as (M1/Unreg) / (M2/Unreg) using primary + secondary records.
    """
    from app.models import Construct
    import numpy as np

    source = Construct.query.get(source_id)
    target = Construct.query.get(target_id)
    if not source or not target:
        return None

    # Find WT for each family
    wt1 = Construct.query.filter_by(
        project_id=source.project_id, family=source.family, is_wildtype=True, is_draft=False
    ).first()
    wt2 = Construct.query.filter_by(
        project_id=target.project_id, family=target.family, is_wildtype=True, is_draft=False
    ).first()
    unreg = Construct.query.filter_by(
        project_id=source.project_id, is_unregulated=True, is_draft=False
    ).first()

    if not wt1 or not wt2 or not unreg:
        return None

    # M1 -> WT1
    fc_m1_wt1 = _get_pooled_fc(source_id, wt1.id, project_id)
    # WT1 -> Unreg
    fc_wt1_unreg = _get_pooled_fc(wt1.id, unreg.id, project_id)
    # M2 -> WT2
    fc_m2_wt2 = _get_pooled_fc(target_id, wt2.id, project_id)
    # WT2 -> Unreg
    fc_wt2_unreg = _get_pooled_fc(wt2.id, unreg.id, project_id)

    if not all([fc_m1_wt1, fc_wt1_unreg, fc_m2_wt2, fc_wt2_unreg]):
        return None

    # M1/Unreg = (M1/WT1) * (WT1/Unreg)
    log_m1_unreg = fc_m1_wt1["mean_log_fc"] + fc_wt1_unreg["mean_log_fc"]
    se_m1_unreg = np.sqrt(fc_m1_wt1["pooled_se"] ** 2 + fc_wt1_unreg["pooled_se"] ** 2)

    # M2/Unreg = (M2/WT2) * (WT2/Unreg)
    log_m2_unreg = fc_m2_wt2["mean_log_fc"] + fc_wt2_unreg["mean_log_fc"]
    se_m2_unreg = np.sqrt(fc_m2_wt2["pooled_se"] ** 2 + fc_wt2_unreg["pooled_se"] ** 2)

    # M1/M2 = (M1/Unreg) / (M2/Unreg)
    combined_log_fc = log_m1_unreg - log_m2_unreg
    combined_se = float(np.sqrt(se_m1_unreg ** 2 + se_m2_unreg ** 2))

    return _fc_dict_from_log(combined_log_fc, combined_se)


def _compute_custom_fc(
    source_id: int,
    target_id: int,
    path,
    project_id: int
) -> Dict[str, Any]:
    """
    Compute custom fold change between two constructs along the given path.

    Handles DIRECT, ONE_HOP, TWO_HOP, and FOUR_HOP path types by chaining
    the appropriate primary/secondary FoldChange records from the DB.
    """
    from app.analysis.comparison import PathType
    import numpy as np

    try:
        if path.path_type == PathType.FOUR_HOP:
            result = _compute_cross_family_fc_from_db(source_id, target_id, project_id)
            return result if result else {
                "is_valid": False,
                "error_message": "Insufficient data for cross-family comparison."
            }

        if path.path_type == PathType.TWO_HOP and path.intermediates:
            wt_id = path.intermediates[0]
            result = _compute_derived_fc_from_db(source_id, target_id, wt_id, project_id)
            return result if result else {
                "is_valid": False,
                "error_message": "Insufficient data for derived comparison."
            }

        if path.path_type == PathType.ONE_HOP and path.intermediates:
            # M1 vs M2 through shared WT: FC_M1/M2 = FC_M1/WT / FC_M2/WT
            wt_id = path.intermediates[0]
            fc_m1_wt = _get_pooled_fc(source_id, wt_id, project_id)
            fc_m2_wt = _get_pooled_fc(target_id, wt_id, project_id)

            if not fc_m1_wt or not fc_m2_wt:
                return {
                    "is_valid": False,
                    "error_message": "Insufficient data for mutant-mutant comparison."
                }

            combined_log_fc = fc_m1_wt["mean_log_fc"] - fc_m2_wt["mean_log_fc"]
            combined_se = float(np.sqrt(
                fc_m1_wt["pooled_se"] ** 2 + fc_m2_wt["pooled_se"] ** 2
            ))
            return _fc_dict_from_log(combined_log_fc, combined_se)

        # DIRECT: just pool the primary FCs
        fc = _get_pooled_fc(source_id, target_id, project_id)
        if fc:
            return _fc_dict_from_log(fc["mean_log_fc"], fc["pooled_se"])

        return {
            "is_valid": False,
            "error_message": "No fold change data found for this comparison."
        }

    except Exception as e:
        logger.exception("Error in custom fold change computation")
        return {
            "is_valid": False,
            "error_message": "An unexpected error occurred during fold change computation."
        }


def dmc_text_dimmed(text: str):
    """Helper to create dimmed text."""
    return dmc.Text(text, c="dimmed", ta="center", size="sm")
