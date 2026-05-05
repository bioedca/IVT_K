"""Backfill reliability metrics on existing fits.

Walks every FitResult (and optionally FitResultArchive) row, computing:
- run_length_min, pct_plateau_reached, mean_signal
- residual_autocorr_dw (Durbin-Watson on raw - fitted residuals)

No re-fitting is performed. Where a metric can't be computed (missing raw
points, missing fit params, or trace too short), the field is left NULL.

Usage:
    python scripts/backfill_fit_reliability_metrics.py [--dry-run] [--archives]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(APP_ROOT))

if "FLASK_ENV" not in os.environ:
    os.environ["FLASK_ENV"] = "development"

import numpy as np  # noqa: E402

from app import create_app  # noqa: E402
from app.analysis.curve_fitting import compute_durbin_watson  # noqa: E402
from app.analysis.kinetic_models import ModelParameters, get_model  # noqa: E402
from app.config import get_config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import RawDataPoint, Well  # noqa: E402
from app.models.fit_result import FitResult, FitResultArchive  # noqa: E402
from app.services.fit_computation_service import compute_pct_plateau_reached  # noqa: E402
from sqlalchemy import func

logger = logging.getLogger(__name__)


def _compute_residual_autocorr_dw(fit) -> float | None:
    """Recompute residuals from raw points + stored fit params, return DW."""
    if fit.well_id is None or not fit.model_type:
        return None
    if fit.k_obs is None or fit.f_max is None or fit.t_lag is None:
        return None
    points = RawDataPoint.query.filter_by(well_id=fit.well_id).order_by(
        RawDataPoint.timepoint
    ).all()
    if len(points) < 2:
        return None
    t = np.array([p.timepoint for p in points], dtype=float)
    F = np.array([
        p.fluorescence_corrected if p.fluorescence_corrected is not None else p.fluorescence_raw
        for p in points
    ], dtype=float)
    try:
        params = ModelParameters()
        params.set("F_baseline", fit.f_baseline or 0)
        params.set("F_max", fit.f_max)
        params.set("k_obs", fit.k_obs)
        params.set("t_lag", fit.t_lag)
        model = get_model(fit.model_type)
        F_pred = model.evaluate(t, params)
    except (KeyError, ValueError, TypeError) as exc:
        # KeyError: unknown model_type; ValueError/TypeError: malformed params.
        # Anything else is unexpected — let it propagate.
        logger.warning(
            "Skipping autocorr backfill for fit id=%s model_type=%s: %s",
            getattr(fit, "id", "?"),
            getattr(fit, "model_type", "?"),
            exc,
        )
        return None
    return compute_durbin_watson(F - F_pred)


def _plate_run_length(plate_id: int, cache: dict) -> float | None:
    if plate_id in cache:
        return cache[plate_id]
    value = (
        db.session.query(func.max(RawDataPoint.timepoint))
        .join(Well, RawDataPoint.well_id == Well.id)
        .filter(Well.plate_id == plate_id)
        .scalar()
    )
    cache[plate_id] = value
    return value


def _well_mean_signal(well_id: int) -> float | None:
    points = RawDataPoint.query.filter_by(well_id=well_id).all()
    if not points:
        return None
    vals = []
    for dp in points:
        v = dp.fluorescence_corrected
        if v is None:
            v = dp.fluorescence_raw
        if v is not None:
            vals.append(float(v))
    if not vals:
        return None
    return sum(vals) / len(vals)


def _well_run_length(well_id: int) -> float | None:
    return (
        db.session.query(func.max(RawDataPoint.timepoint))
        .filter(RawDataPoint.well_id == well_id)
        .scalar()
    )


def backfill_fit_results(dry_run: bool = False) -> int:
    fits = FitResult.query.all()
    plate_cache: dict = {}
    updated = 0
    for fit in fits:
        if (
            fit.run_length_min is not None
            and fit.pct_plateau_reached is not None
            and fit.mean_signal is not None
            and fit.residual_autocorr_dw is not None
        ):
            continue

        well = fit.well
        plate_id = well.plate_id if well else None

        run_length = None
        if plate_id is not None:
            run_length = _plate_run_length(plate_id, plate_cache)
        if run_length is None and fit.well_id is not None:
            run_length = _well_run_length(fit.well_id)

        changed = False
        if fit.run_length_min is None and run_length is not None:
            fit.run_length_min = run_length
            changed = True
        if fit.mean_signal is None and fit.well_id is not None:
            mean_signal = _well_mean_signal(fit.well_id)
            if mean_signal is not None:
                fit.mean_signal = mean_signal
                changed = True
        if fit.pct_plateau_reached is None:
            pct = compute_pct_plateau_reached(
                k_obs=fit.k_obs, t_lag=fit.t_lag, run_length_min=fit.run_length_min
            )
            if pct is not None:
                fit.pct_plateau_reached = pct
                changed = True
        if fit.residual_autocorr_dw is None:
            dw = _compute_residual_autocorr_dw(fit)
            if dw is not None:
                fit.residual_autocorr_dw = dw
                changed = True
        if changed:
            updated += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return updated


def backfill_archives(dry_run: bool = False) -> int:
    archives = FitResultArchive.query.all()
    plate_cache: dict = {}
    updated = 0
    for arch in archives:
        if (
            arch.run_length_min is not None
            and arch.pct_plateau_reached is not None
            and arch.mean_signal is not None
            and arch.residual_autocorr_dw is not None
        ):
            continue

        well_id = arch.well_id
        well = arch.well
        plate_id = well.plate_id if well else None

        run_length = None
        if plate_id is not None:
            run_length = _plate_run_length(plate_id, plate_cache)
        if run_length is None and well_id is not None:
            run_length = _well_run_length(well_id)

        changed = False
        if arch.run_length_min is None and run_length is not None:
            arch.run_length_min = run_length
            changed = True
        if arch.mean_signal is None and well_id is not None:
            mean_signal = _well_mean_signal(well_id)
            if mean_signal is not None:
                arch.mean_signal = mean_signal
                changed = True
        if arch.pct_plateau_reached is None:
            pct = compute_pct_plateau_reached(
                k_obs=arch.k_obs, t_lag=arch.t_lag, run_length_min=arch.run_length_min
            )
            if pct is not None:
                arch.pct_plateau_reached = pct
                changed = True
        if arch.residual_autocorr_dw is None:
            dw = _compute_residual_autocorr_dw(arch)
            if dw is not None:
                arch.residual_autocorr_dw = dw
                changed = True
        if changed:
            updated += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't commit.")
    parser.add_argument(
        "--archives",
        action="store_true",
        help="Also backfill FitResultArchive rows.",
    )
    args = parser.parse_args()

    app = create_app(get_config())
    with app.server.app_context():
        n_fits = backfill_fit_results(dry_run=args.dry_run)
        print(f"FitResult rows updated: {n_fits}")
        if args.archives:
            n_arch = backfill_archives(dry_run=args.dry_run)
            print(f"FitResultArchive rows updated: {n_arch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
