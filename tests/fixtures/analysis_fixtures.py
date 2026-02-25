"""Analysis-related factory fixtures (fit results, fold changes, analysis versions)."""
import numpy as np
from datetime import datetime, timezone

from app.extensions import db
from app.models.fit_result import FitResult, FoldChange
from app.models.analysis_version import (
    AnalysisVersion, AnalysisStatus, HierarchicalResult,
)


def create_test_fit_result(
    well_id,
    f_max=1000.0,
    f_max_se=50.0,
    k_obs=0.1,
    k_obs_se=0.01,
    t_lag=5.0,
    t_lag_se=1.0,
    f_baseline=100.0,
    f_baseline_se=10.0,
    r_squared=0.98,
    rmse=15.0,
    converged=True,
    model_type="delayed_exponential",
    **kwargs,
):
    """Create a test fit result for a well."""
    fit = FitResult(
        well_id=well_id,
        f_max=f_max,
        f_max_se=f_max_se,
        k_obs=k_obs,
        k_obs_se=k_obs_se,
        t_lag=t_lag,
        t_lag_se=t_lag_se,
        f_baseline=f_baseline,
        f_baseline_se=f_baseline_se,
        r_squared=r_squared,
        rmse=rmse,
        converged=converged,
        model_type=model_type,
        **kwargs,
    )
    db.session.add(fit)
    db.session.commit()
    return fit


def create_test_fold_change(
    test_well_id,
    control_well_id,
    fc_fmax=2.0,
    log_fc_fmax=None,
    fc_fmax_se=0.2,
    fc_kobs=None,
    log_fc_kobs=None,
    delta_tlag=None,
    comparison_type="within_condition",
    ligand_condition=None,
    **kwargs,
):
    """Create a test fold change record."""
    if log_fc_fmax is None:
        log_fc_fmax = float(np.log(fc_fmax)) if fc_fmax and fc_fmax > 0 else 0.0

    fc = FoldChange(
        test_well_id=test_well_id,
        control_well_id=control_well_id,
        fc_fmax=fc_fmax,
        log_fc_fmax=log_fc_fmax,
        fc_fmax_se=fc_fmax_se,
        fc_kobs=fc_kobs,
        log_fc_kobs=log_fc_kobs,
        delta_tlag=delta_tlag,
        comparison_type=comparison_type,
        ligand_condition=ligand_condition,
        **kwargs,
    )
    db.session.add(fc)
    db.session.commit()
    return fc


def create_test_analysis_version(
    project_id,
    name="Test Analysis v1",
    status=AnalysisStatus.COMPLETED,
    model_type="delayed_exponential",
    mcmc_chains=4,
    mcmc_draws=100,
    mcmc_tune=50,
    mcmc_thin=1,
    **kwargs,
):
    """Create a test analysis version."""
    version = AnalysisVersion(
        project_id=project_id,
        name=name,
        status=status,
        model_type=model_type,
        mcmc_chains=mcmc_chains,
        mcmc_draws=mcmc_draws,
        mcmc_tune=mcmc_tune,
        mcmc_thin=mcmc_thin,
        started_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db.session.add(version)
    db.session.commit()
    return version


def create_test_hierarchical_result(
    version_id,
    construct_id,
    parameter_type="log_fc_fmax",
    mean=0.5,
    std=0.1,
    ci_lower=0.3,
    ci_upper=0.7,
    analysis_type="bayesian",
    ligand_condition=None,
    **kwargs,
):
    """Create a test hierarchical result."""
    result = HierarchicalResult(
        analysis_version_id=version_id,
        construct_id=construct_id,
        parameter_type=parameter_type,
        mean=mean,
        std=std,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        analysis_type=analysis_type,
        ligand_condition=ligand_condition,
        **kwargs,
    )
    db.session.add(result)
    db.session.commit()
    return result
