"""
Frequentist hierarchical modeling using REML.

Phase 5.8: Frequentist REML implementation
Phase 5.9: Bayesian vs Frequentist comparison
Phase 5.10: Adaptive model tier selection
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any, Callable
from dataclasses import dataclass, field
import logging
import warnings

from app.analysis.data_structure import (
    ModelTier,
    ModelMetadata,
    DataStructureAnalyzer,
)
from app.analysis.variance_components import FrequentistVarianceComponents
from app.analysis.constants import DEFAULT_CI_LEVEL, BAYESIAN_FREQUENTIST_TOLERANCE

logger = logging.getLogger(__name__)

# Try importing statsmodels
try:
    import statsmodels.api as sm
    from statsmodels.regression.mixed_linear_model import MixedLM
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except ImportError:
    sm = None
    MixedLM = None
    smf = None
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not available. Frequentist analysis will be disabled.")


@dataclass
class FrequentistEstimate:
    """Estimate summary from frequentist model."""
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    ci_level: float = DEFAULT_CI_LEVEL
    p_value: Optional[float] = None
    t_statistic: Optional[float] = None
    df: Optional[float] = None


@dataclass
class FrequentistResult:
    """Complete result of frequentist hierarchical analysis."""
    # Construct-level estimates (keyed by construct_id then parameter name)
    estimates: Dict[int, Dict[str, FrequentistEstimate]] = field(default_factory=dict)

    # Variance components (keyed by parameter name)
    variance_components: Dict[str, FrequentistVarianceComponents] = field(default_factory=dict)

    # Model tier metadata (adaptive model selection)
    model_metadata: Optional[ModelMetadata] = None

    # Model fit statistics (keyed by parameter)
    log_likelihood: Dict[str, float] = field(default_factory=dict)
    aic: Dict[str, float] = field(default_factory=dict)
    bic: Dict[str, float] = field(default_factory=dict)

    # Convergence info
    converged: Dict[str, bool] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    # Warnings
    warnings: List[str] = field(default_factory=list)


class FrequentistHierarchical:
    """
    Frequentist hierarchical model using REML estimation.

    Implements a linear mixed-effects model:
        y_{c,s,p} = mu_c + gamma_s + delta_{s,p} + epsilon

    where:
        - mu_c: Fixed effect for construct c
        - gamma_s ~ N(0, sigma_session^2): Random session effect
        - delta_{s,p} ~ N(0, sigma_plate^2): Random plate effect
        - epsilon ~ N(0, sigma_residual^2): Residual error

    Uses REML (Restricted Maximum Likelihood) for variance component estimation.
    """

    def __init__(self, ci_level: float = DEFAULT_CI_LEVEL):
        """
        Initialize frequentist hierarchical model.

        Args:
            ci_level: Confidence interval level (default 0.95)
        """
        if not STATSMODELS_AVAILABLE:
            raise ImportError("statsmodels is required for frequentist analysis")

        self.ci_level = ci_level

    def detect_data_structure(
        self,
        fold_changes: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect data structure for adaptive model selection.

        Delegates to :class:`DataStructureAnalyzer` and returns a
        backwards-compatible dict.
        """
        structure = DataStructureAnalyzer.detect(fold_changes)
        return {
            'n_sessions': structure.n_sessions,
            'n_plates': structure.n_plates,
            'max_plates_per_session': structure.max_plates_per_session,
            'plates_per_session': structure.plates_per_session
        }

    def select_model_tier(
        self,
        data_structure: Dict[str, Any]
    ) -> ModelMetadata:
        """
        Select appropriate model tier based on data structure.

        Delegates to :class:`DataStructureAnalyzer`.
        """
        from app.analysis.data_structure import DataStructure
        structure = DataStructure(
            n_sessions=data_structure['n_sessions'],
            n_plates=data_structure['n_plates'],
            max_plates_per_session=data_structure['max_plates_per_session'],
            plates_per_session=data_structure.get('plates_per_session', {})
        )
        return DataStructureAnalyzer.select_model_tier(structure, method="frequentist")

    def prepare_data(
        self,
        fold_changes: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Prepare data for mixed model.

        Expected columns:
        - construct_id: Construct identifier
        - session_id: Session identifier
        - plate_id: Plate identifier
        - log_fc_fmax: Log2 fold change for F_max
        - log_fc_kobs: Log2 fold change for k_obs (optional)
        - delta_tlag: Difference in t_lag (optional)

        Returns:
            Dict with prepared data
        """
        df = fold_changes.copy()

        # Ensure categorical types for grouping
        df['construct_id'] = df['construct_id'].astype(str)
        df['session_id'] = df['session_id'].astype(str)
        df['plate_id'] = df['plate_id'].astype(str)

        # Create unique plate identifier within session
        df['session_plate'] = df['session_id'] + '_' + df['plate_id']

        # Determine which parameters are available
        params = ['log_fc_fmax']
        if 'log_fc_kobs' in df.columns and df['log_fc_kobs'].notna().any():
            params.append('log_fc_kobs')
        if 'delta_tlag' in df.columns and df['delta_tlag'].notna().any():
            params.append('delta_tlag')

        construct_ids = df['construct_id'].unique().tolist()

        return {
            'df': df,
            'params': params,
            'construct_ids': construct_ids,
            'n_constructs': len(construct_ids),
            'n_sessions': df['session_id'].nunique(),
            'n_plates': df['plate_id'].nunique()
        }

    def fit_model(
        self,
        df: pd.DataFrame,
        response_var: str,
        model_metadata: Optional[ModelMetadata] = None
    ) -> Tuple[Any, bool, str]:
        """
        Fit model appropriate for the data structure.

        Adaptive model selection:
        - Tier 1: OLS (no random effects)
        - Tier 2a: Mixed model with session random effect
        - Tier 2b: Mixed model with plate random effect
        - Tier 3: Full mixed model with session and plate random effects

        Args:
            df: DataFrame with data
            response_var: Name of response variable
            model_metadata: Model tier metadata

        Returns:
            Tuple of (fitted model, converged, model_type)
        """
        # Drop missing values for this response
        df_clean = df.dropna(subset=[response_var])

        if len(df_clean) < 3:
            raise ValueError(f"Insufficient data for {response_var}: {len(df_clean)} observations")

        # Create design matrix with construct dummies
        formula = f"{response_var} ~ C(construct_id) - 1"

        tier = model_metadata.tier if model_metadata else ModelTier.TIER_3_FULL

        # ===== TIER 1: Simple OLS (no random effects) =====
        if tier == ModelTier.TIER_1_RESIDUAL_ONLY:
            logger.info(f"Fitting OLS model for {response_var} (Tier 1)")
            try:
                model = smf.ols(formula, data=df_clean)
                result = model.fit()
                return result, True, 'ols'
            except Exception as e:
                logger.error(f"OLS fitting failed: {e}")
                raise

        # ===== TIER 2A: Session random effect only =====
        elif tier == ModelTier.TIER_2A_SESSION:
            logger.info(f"Fitting mixed model with session RE for {response_var} (Tier 2a)")
            try:
                model = MixedLM.from_formula(
                    formula,
                    groups='session_id',
                    re_formula='1',
                    data=df_clean
                )
                result = model.fit(reml=True, method='lbfgs')
                return result, result.converged, 'mixed_session'
            except Exception as e:
                logger.warning(f"Mixed model failed, falling back to OLS: {e}")
                model = smf.ols(formula, data=df_clean)
                result = model.fit()
                return result, True, 'ols'

        # ===== TIER 2B: Plate random effect only =====
        elif tier == ModelTier.TIER_2B_PLATE:
            logger.info(f"Fitting mixed model with plate RE for {response_var} (Tier 2b)")
            try:
                model = MixedLM.from_formula(
                    formula,
                    groups='plate_id',
                    re_formula='1',
                    data=df_clean
                )
                result = model.fit(reml=True, method='lbfgs')
                return result, result.converged, 'mixed_plate'
            except Exception as e:
                logger.warning(f"Mixed model failed, falling back to OLS: {e}")
                model = smf.ols(formula, data=df_clean)
                result = model.fit()
                return result, True, 'ols'

        # ===== TIER 3: Full mixed model =====
        else:
            logger.info(f"Fitting full mixed model for {response_var} (Tier 3)")
            try:
                # Try nested random effects
                model = MixedLM.from_formula(
                    formula,
                    groups='session_id',
                    vc_formula={'plate': '0 + C(session_plate)'},
                    re_formula='1',
                    data=df_clean
                )
                result = model.fit(reml=True, method='lbfgs')
                return result, result.converged, 'mixed_full'
            except Exception as e:
                logger.warning(f"Full model failed, trying session-only: {e}")
                try:
                    model = MixedLM.from_formula(
                        formula,
                        groups='session_id',
                        re_formula='1',
                        data=df_clean
                    )
                    result = model.fit(reml=True, method='lbfgs')
                    return result, result.converged, 'mixed_session'
                except Exception as e2:
                    logger.warning(f"Session model failed, falling back to OLS: {e2}")
                    model = smf.ols(formula, data=df_clean)
                    result = model.fit()
                    return result, True, 'ols'

    def extract_estimates(
        self,
        result: Any,
        construct_ids: List[str],
        response_var: str,
        model_type: str = 'mixed'
    ) -> Dict[str, FrequentistEstimate]:
        """
        Extract construct-level estimates from fitted model.

        Args:
            result: Fitted model result (OLS or MixedLM)
            construct_ids: List of construct IDs
            response_var: Response variable name
            model_type: 'ols' or 'mixed_*'

        Returns:
            Dict mapping construct_id to FrequentistEstimate
        """
        estimates = {}

        # Get coefficient names that match construct pattern
        coef_names = result.params.index.tolist()

        for construct_id in construct_ids:
            # Find matching coefficient
            pattern = f"C(construct_id)[{construct_id}]"
            if pattern in coef_names:
                idx = coef_names.index(pattern)
                mean = float(result.params.iloc[idx])
                std = float(result.bse.iloc[idx])

                # Confidence interval
                alpha = 1 - self.ci_level
                from scipy import stats as scipy_stats
                z = scipy_stats.norm.ppf(1 - alpha / 2)
                ci_lower = mean - z * std
                ci_upper = mean + z * std

                # P-value and t-statistic
                p_value = None
                t_stat = None
                try:
                    p_value = float(result.pvalues.iloc[idx])
                    t_stat = float(result.tvalues.iloc[idx])
                except (IndexError, AttributeError):
                    pass

                estimates[construct_id] = FrequentistEstimate(
                    mean=mean,
                    std=std,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    ci_level=self.ci_level,
                    p_value=p_value,
                    t_statistic=t_stat
                )

        return estimates

    def extract_variance_components(
        self,
        result: Any,
        model_type: str,
        model_metadata: Optional[ModelMetadata] = None
    ) -> FrequentistVarianceComponents:
        """
        Extract variance components from fitted model.

        Args:
            result: Fitted model result (OLS or MixedLM)
            model_type: 'ols', 'mixed_session', 'mixed_plate', or 'mixed_full'
            model_metadata: Model tier metadata

        Returns:
            FrequentistVarianceComponents
        """
        var_session = None
        var_plate = None
        session_status = None
        plate_status = None

        # Get residual variance
        if model_type == 'ols':
            # OLS: MSE is the residual variance
            var_residual = float(result.mse_resid)
            session_status = "N/A — insufficient data (Tier 1)"
            plate_status = "N/A — insufficient data (Tier 1)"
        else:
            # Mixed model: scale is residual variance
            var_residual = float(result.scale)

            # Extract random effect variances based on model type
            if model_type in ['mixed_session', 'mixed_full']:
                try:
                    re_params = result.cov_re
                    if hasattr(re_params, 'values'):
                        re_params = re_params.values
                    if isinstance(re_params, np.ndarray) and len(re_params) > 0:
                        var_session = float(re_params.flatten()[0])
                except Exception:
                    var_session = 0.0
            else:
                session_status = "N/A — insufficient data"

            if model_type == 'mixed_plate':
                try:
                    re_params = result.cov_re
                    if hasattr(re_params, 'values'):
                        re_params = re_params.values
                    if isinstance(re_params, np.ndarray) and len(re_params) > 0:
                        var_plate = float(re_params.flatten()[0])
                except Exception:
                    var_plate = 0.0
            elif model_type != 'mixed_full':
                plate_status = "N/A — insufficient data"

        # Try to get plate-level variance from vcomp if available (for full model)
        if model_type == 'mixed_full':
            try:
                if hasattr(result, 'vcomp') and result.vcomp is not None:
                    for name, var in result.vcomp.items():
                        if 'plate' in str(name).lower():
                            var_plate = float(var)
            except Exception:
                pass
            if var_plate is None:
                var_plate = 0.0

        # Calculate total variance (only from estimated components)
        var_total = var_residual
        if var_session is not None:
            var_total += var_session
        if var_plate is not None:
            var_total += var_plate

        return FrequentistVarianceComponents(
            var_session=var_session,
            var_plate=var_plate,
            var_residual=var_residual,
            var_total=var_total,
            session_status=session_status,
            plate_status=plate_status
        )

    def run_analysis(
        self,
        fold_changes: pd.DataFrame,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> FrequentistResult:
        """
        Run complete frequentist hierarchical analysis with adaptive tier selection.

        Automatically selects the appropriate model complexity:
        - Tier 1: OLS (single session, single plate)
        - Tier 2a: Mixed with session RE (multiple sessions, single plate each)
        - Tier 2b: Mixed with plate RE (single session, multiple plates)
        - Tier 3: Full mixed model (multiple sessions and plates)

        Args:
            fold_changes: DataFrame with fold change data
            progress_callback: Callback(stage, progress_fraction) for progress

        Returns:
            FrequentistResult with all estimates and diagnostics
        """
        start_time = datetime.now()
        result = FrequentistResult()

        if progress_callback:
            progress_callback("Preparing data", 0.05)

        # Prepare data
        data = self.prepare_data(fold_changes)
        df = data['df']
        params = data['params']
        construct_ids = data['construct_ids']

        # ===== ADAPTIVE MODEL SELECTION =====
        if progress_callback:
            progress_callback("Detecting data structure", 0.07)

        data_structure = self.detect_data_structure(fold_changes)
        model_metadata = self.select_model_tier(data_structure)

        # Store metadata in result
        result.model_metadata = model_metadata

        logger.info(
            f"Frequentist model tier: {model_metadata.tier.value} | "
            f"Sessions: {model_metadata.n_sessions}, "
            f"Max plates/session: {model_metadata.max_plates_per_session}"
        )

        # Fit model for each parameter
        for p_idx, param in enumerate(params):
            if progress_callback:
                progress = 0.1 + 0.8 * (p_idx / len(params))
                progress_callback(f"Fitting {param}", progress)

            try:
                # Capture statsmodels warnings during fit
                with warnings.catch_warnings(record=True) as caught_warnings:
                    warnings.simplefilter("always")

                    fitted, converged, model_type = self.fit_model(
                        df, param, model_metadata=model_metadata
                    )

                    # Collect any convergence/estimation warnings
                    for w in caught_warnings:
                        warning_msg = str(w.message)
                        # Filter to relevant warnings
                        if any(kw in warning_msg.lower() for kw in [
                            'singular', 'hessian', 'convergence', 'boundary',
                            'covariance', 'positive definite', 'mle'
                        ]):
                            # Add parameter context to warning
                            result.warnings.append(f"{param}: {warning_msg}")
                            logger.warning(f"Frequentist {param}: {warning_msg}")

                # Extract estimates
                estimates = self.extract_estimates(
                    fitted, construct_ids, param, model_type=model_type
                )
                for construct_id, estimate in estimates.items():
                    # Convert construct_id back to int if needed
                    try:
                        cid = int(construct_id)
                    except ValueError:
                        cid = construct_id

                    if cid not in result.estimates:
                        result.estimates[cid] = {}
                    result.estimates[cid][param] = estimate

                # Variance components
                result.variance_components[param] = self.extract_variance_components(
                    fitted, model_type, model_metadata
                )

                # Model fit statistics
                result.log_likelihood[param] = float(fitted.llf)
                result.aic[param] = float(fitted.aic)
                result.bic[param] = float(fitted.bic)
                result.converged[param] = converged

                if not converged:
                    result.warnings.append(f"Model for {param} did not converge")

            except Exception as e:
                logger.error(f"Failed to fit model for {param}: {e}")
                result.warnings.append(f"Model for {param} failed: {str(e)}")
                result.converged[param] = False

        # Add tier-specific info to warnings if not full model
        if model_metadata.tier != ModelTier.TIER_3_FULL:
            result.warnings.append(model_metadata.user_message)

        result.duration_seconds = (datetime.now() - start_time).total_seconds()

        if progress_callback:
            progress_callback("Complete", 1.0)

        return result


def compare_bayesian_frequentist(
    bayesian_result: 'BayesianResult',
    frequentist_result: FrequentistResult,
    tolerance: float = BAYESIAN_FREQUENTIST_TOLERANCE
) -> Dict[str, Any]:
    """
    Compare Bayesian and frequentist results.

    Args:
        bayesian_result: Result from BayesianHierarchical
        frequentist_result: Result from FrequentistHierarchical
        tolerance: Relative tolerance for agreement (default 10%)

    Returns:
        Dict with comparison statistics and agreement flags
    """
    from app.analysis.bayesian import BayesianResult

    comparison = {
        'constructs': {},
        'overall_agreement': True,
        'max_relative_difference': 0.0,
        'warnings': []
    }

    # Compare estimates for each construct and parameter
    for construct_id in bayesian_result.posteriors.keys():
        if construct_id not in frequentist_result.estimates:
            continue

        comparison['constructs'][construct_id] = {}

        for param in bayesian_result.posteriors[construct_id].keys():
            if param not in frequentist_result.estimates.get(construct_id, {}):
                continue

            bayes = bayesian_result.posteriors[construct_id][param]
            freq = frequentist_result.estimates[construct_id][param]

            # Relative difference in means
            if abs(bayes.mean) > 1e-6:
                rel_diff = abs(bayes.mean - freq.mean) / abs(bayes.mean)
            else:
                rel_diff = abs(bayes.mean - freq.mean)

            agreement = rel_diff <= tolerance

            comparison['constructs'][construct_id][param] = {
                'bayesian_mean': bayes.mean,
                'frequentist_mean': freq.mean,
                'relative_difference': rel_diff,
                'agreement': agreement,
                'bayesian_ci': (bayes.ci_lower, bayes.ci_upper),
                'frequentist_ci': (freq.ci_lower, freq.ci_upper)
            }

            comparison['max_relative_difference'] = max(
                comparison['max_relative_difference'], rel_diff
            )

            if not agreement:
                comparison['overall_agreement'] = False
                comparison['warnings'].append(
                    f"Construct {construct_id}, {param}: {rel_diff:.1%} difference"
                )

    return comparison


def check_statsmodels_available() -> bool:
    """Check if statsmodels is available."""
    return STATSMODELS_AVAILABLE
