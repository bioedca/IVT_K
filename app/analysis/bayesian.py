"""
Bayesian hierarchical modeling for IVT kinetics analysis.

Phase 5.1: PyMC model specification (multivariate)
Phase 5.2: MCMC sampling with checkpointing
Phase 5.3: Checkpoint save/resume
Phase 5.4: Thinned trace storage (NetCDF)
Phase 5.5: Posterior summaries
Phase 5.6: Probability calculations
Phase 5.7: Variance decomposition
Phase 5.8: Adaptive model tier selection
"""
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any, Callable
from dataclasses import dataclass, field
import logging
import warnings
import json

from app.analysis.data_structure import (
    ModelTier,
    ModelMetadata,
    DataStructureAnalyzer,
)
from app.analysis.variance_components import VarianceComponents
from app.analysis.constants import (
    DEFAULT_MCMC_CHAINS,
    DEFAULT_MCMC_DRAWS,
    DEFAULT_MCMC_TUNE,
    DEFAULT_MCMC_THIN,
    MCMC_CHECKPOINT_INTERVAL,
    DEFAULT_MCMC_TARGET_ACCEPT,
    MEANINGFUL_EFFECT_THRESHOLD,
    DEFAULT_CI_LEVEL,
)

logger = logging.getLogger(__name__)


# Try importing PyMC and ArviZ - they may not be installed in test environment
try:
    import pymc as pm
    import arviz as az
    PYMC_AVAILABLE = True
except ImportError:
    pm = None
    az = None
    PYMC_AVAILABLE = False
    logger.warning("PyMC/ArviZ not available. Bayesian analysis will be disabled.")


@dataclass
class PosteriorSummary:
    """Summary statistics for a posterior distribution."""
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    ci_level: float = DEFAULT_CI_LEVEL

    # MCMC diagnostics
    n_samples: int = 0
    r_hat: Optional[float] = None
    ess_bulk: Optional[float] = None
    ess_tail: Optional[float] = None

    # Additional probabilities
    prob_positive: Optional[float] = None  # P(param > 0)
    prob_meaningful: Optional[float] = None  # P(|param| > threshold)

    # Thinned posterior samples for on-demand probability computation
    # Stored as list of floats (~500-1000 samples)
    samples: Optional[List[float]] = None


@dataclass
class BayesianResult:
    """Complete result of Bayesian hierarchical analysis."""
    # Construct-level posteriors (keyed by construct_id then parameter name)
    posteriors: Dict[int, Dict[str, PosteriorSummary]] = field(default_factory=dict)

    # Variance components (keyed by parameter name)
    variance_components: Dict[str, VarianceComponents] = field(default_factory=dict)

    # Parameter correlations (construct_id -> param_pair -> correlation)
    correlations: Dict[int, Dict[Tuple[str, str], float]] = field(default_factory=dict)

    # Model tier metadata (adaptive model selection)
    model_metadata: Optional[ModelMetadata] = None

    # MCMC diagnostics
    n_chains: int = 4
    n_draws: int = 2000
    n_tune: int = 1000
    thin_factor: int = 5
    divergent_count: int = 0
    max_treedepth_count: int = 0

    # Model residuals per parameter: {"log_fc_fmax": [r1, r2, ...], ...}
    model_residuals: Dict[str, List[float]] = field(default_factory=dict)

    # Trace path
    trace_path: Optional[str] = None

    # Timing
    duration_seconds: float = 0.0

    # Warnings
    warnings: List[str] = field(default_factory=list)


class BayesianHierarchical:
    """
    Bayesian hierarchical model for fold change analysis.

    Implements a multivariate hierarchical model with:
    - Construct-level fixed effects for log fold changes
    - Session and plate random effects with covariance structure
    - LKJ prior for correlation matrices

    Model structure:
        log_FC_{m,s,p} ~ MVNormal(mu_m + gamma_s + delta_{s,p}, Sigma_residual)
        gamma_s ~ MVNormal(0, Sigma_session)
        delta_{s,p} ~ MVNormal(0, Sigma_plate)
    """

    # Default MCMC settings (from app.analysis.constants)
    DEFAULT_CHAINS = DEFAULT_MCMC_CHAINS
    DEFAULT_DRAWS = DEFAULT_MCMC_DRAWS
    DEFAULT_TUNE = DEFAULT_MCMC_TUNE
    DEFAULT_THIN = DEFAULT_MCMC_THIN
    CHECKPOINT_INTERVAL = MCMC_CHECKPOINT_INTERVAL

    def __init__(
        self,
        chains: int = DEFAULT_CHAINS,
        draws: int = DEFAULT_DRAWS,
        tune: int = DEFAULT_TUNE,
        thin: int = DEFAULT_THIN,
        random_seed: Optional[int] = None,
        parallel_chains: bool = True
    ):
        """
        Initialize Bayesian hierarchical model.

        Args:
            chains: Number of MCMC chains
            draws: Number of samples per chain (after tuning)
            tune: Number of tuning samples
            thin: Thinning factor for storage (store every nth sample)
            random_seed: Random seed for reproducibility
            parallel_chains: If True, run chains in parallel using spawn context.
                            Falls back to sequential if parallel fails.
        """
        if not PYMC_AVAILABLE:
            raise ImportError("PyMC is required for Bayesian analysis")

        self.chains = chains
        self.draws = draws
        self.tune = tune
        self.thin = thin
        self.random_seed = random_seed
        self.parallel_chains = parallel_chains
        self.meaningful_threshold = MEANINGFUL_EFFECT_THRESHOLD

    def prepare_data(
        self,
        fold_changes: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Prepare data for PyMC model.

        Expected columns:
        - construct_id: Construct identifier
        - session_id: Session identifier
        - plate_id: Plate identifier
        - log_fc_fmax: Log2 fold change for F_max
        - log_fc_kobs: Log2 fold change for k_obs (optional)
        - delta_tlag: Difference in t_lag (optional)
        - log_fc_fmax_se: Standard error (optional, for weighting)

        Returns:
            Dict with prepared data for PyMC
        """
        df = fold_changes.copy()

        # Create indices
        construct_ids = df['construct_id'].unique()
        session_ids = df['session_id'].unique()
        plate_ids = df['plate_id'].unique()

        construct_idx = pd.Categorical(df['construct_id'], categories=construct_ids).codes
        session_idx = pd.Categorical(df['session_id'], categories=session_ids).codes
        plate_idx = pd.Categorical(df['plate_id'], categories=plate_ids).codes

        # Determine which parameters are available
        params = ['log_fc_fmax']
        if 'log_fc_kobs' in df.columns and df['log_fc_kobs'].notna().any():
            params.append('log_fc_kobs')
        if 'delta_tlag' in df.columns and df['delta_tlag'].notna().any():
            params.append('delta_tlag')

        # Stack observations for multivariate model
        Y = df[params].values

        return {
            'Y': Y,
            'params': params,
            'n_params': len(params),
            'n_obs': len(df),
            'n_constructs': len(construct_ids),
            'n_sessions': len(session_ids),
            'n_plates': len(plate_ids),
            'construct_idx': construct_idx,
            'session_idx': session_idx,
            'plate_idx': plate_idx,
            'construct_ids': construct_ids.tolist(),
            'session_ids': session_ids.tolist(),
            'plate_ids': plate_ids.tolist(),
            'df': df
        }

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
        return DataStructureAnalyzer.select_model_tier(structure, method="bayesian")

    def build_model(
        self,
        data: Dict[str, Any],
        model_metadata: Optional[ModelMetadata] = None
    ) -> 'pm.Model':
        """
        Build PyMC hierarchical model with adaptive tier selection.

        Uses non-centered parameterization for all random effects to avoid
        funnel geometry that causes divergences and slow sampling.

        Model Tiers:
        - Tier 1: log_FC ~ Normal(mu[construct], sigma_residual)
        - Tier 2a: log_FC ~ Normal(mu[construct] + gamma[session], sigma_residual)
        - Tier 2b: log_FC ~ Normal(mu[construct] + delta[plate], sigma_residual)
        - Tier 3: log_FC ~ Normal(mu[construct] + gamma[session] + delta[plate], sigma_residual)

        Args:
            data: Prepared data from prepare_data()
            model_metadata: Model tier metadata (auto-detected if None)

        Returns:
            PyMC model object
        """
        n_params = data['n_params']
        n_constructs = data['n_constructs']
        n_sessions = data['n_sessions']
        n_plates = data['n_plates']
        n_obs = data['n_obs']

        Y = data['Y']
        construct_idx = data['construct_idx']
        session_idx = data['session_idx']
        plate_idx = data['plate_idx']

        # Auto-detect tier if not provided
        if model_metadata is None:
            data_structure = self.detect_data_structure(data['df'])
            model_metadata = self.select_model_tier(data_structure)

        tier = model_metadata.tier
        logger.info(f"Building model: {tier.value}")

        with pm.Model() as model:
            # Store tier info on model for later reference
            model._tier = tier
            model._metadata = model_metadata

            # Store data dimensions as model attributes
            model.add_coord('param', data['params'])
            model.add_coord('construct', range(n_constructs))
            model.add_coord('obs', range(n_obs))

            # Construct-level means (fixed effects) - always included
            # Weakly informative prior: Normal(0, 10) to accommodate different parameter scales
            # log_fc_fmax/log_fc_kobs are typically O(1), but delta_tlag can be O(10-100)
            mu = pm.Normal('mu',
                          mu=0, sigma=10,
                          dims=('construct', 'param'))

            # Initialize expected value with construct means
            expected = mu[construct_idx]

            # ===== Session-level random effects (Tier 2a and Tier 3) =====
            if tier in [ModelTier.TIER_2A_SESSION, ModelTier.TIER_3_FULL]:
                model.add_coord('session', range(n_sessions))

                # Session variance scale
                tau_session = pm.HalfNormal('tau_session',
                                           sigma=1,
                                           dims='param')

                # NON-CENTERED PARAMETERIZATION for session effects
                # gamma_raw ~ Normal(0, 1), then gamma = tau_session * gamma_raw
                gamma_raw = pm.Normal('gamma_session_raw',
                                     mu=0, sigma=1,
                                     dims=('session', 'param'))
                gamma_session = pm.Deterministic(
                    'gamma_session',
                    tau_session * gamma_raw,
                    dims=('session', 'param')
                )

                # Add session effect to expected value
                expected = expected + gamma_session[session_idx]

            # ===== Plate-level random effects (Tier 2b and Tier 3) =====
            if tier in [ModelTier.TIER_2B_PLATE, ModelTier.TIER_3_FULL]:
                model.add_coord('plate', range(n_plates))

                # Plate variance scale
                tau_plate = pm.HalfNormal('tau_plate',
                                         sigma=0.5,
                                         dims='param')

                # NON-CENTERED PARAMETERIZATION for plate effects
                # delta_raw ~ Normal(0, 1), then delta = tau_plate * delta_raw
                delta_raw = pm.Normal('delta_plate_raw',
                                     mu=0, sigma=1,
                                     dims=('plate', 'param'))
                delta_plate = pm.Deterministic(
                    'delta_plate',
                    tau_plate * delta_raw,
                    dims=('plate', 'param')
                )

                # Add plate effect to expected value
                expected = expected + delta_plate[plate_idx]

            # ===== Residual standard deviation (always included) =====
            sigma_residual = pm.HalfNormal('sigma_residual',
                                          sigma=0.5,
                                          dims='param')

            # ===== Likelihood =====
            if n_params > 1:
                # Multivariate normal likelihood with LKJ correlation
                chol_resid, corr_resid, sigma_resid_vec = pm.LKJCholeskyCov(
                    'chol_residual',
                    n=n_params,
                    eta=2,
                    sd_dist=pm.HalfNormal.dist(sigma=0.5),
                    compute_corr=True
                )
                Y_obs = pm.MvNormal('Y_obs',
                                   mu=expected,
                                   chol=chol_resid,
                                   observed=Y,
                                   dims=('obs', 'param'))
            else:
                # Univariate normal likelihood
                Y_obs = pm.Normal('Y_obs',
                                 mu=expected[:, 0],
                                 sigma=sigma_residual[0],
                                 observed=Y[:, 0],
                                 dims='obs')

        return model

    def sample(
        self,
        model: 'pm.Model',
        checkpoint_callback: Optional[Callable[[int, int], None]] = None,
        checkpoint_dir: Optional[Path] = None,
        resume_from_checkpoint: bool = False
    ) -> 'az.InferenceData':
        """
        Run MCMC sampling with checkpointing support.

        PRD Reference: Section 0.2, F11.5

        Args:
            model: PyMC model
            checkpoint_callback: Callback(draw_idx, total_draws) for progress
            checkpoint_dir: Directory for checkpoint files
            resume_from_checkpoint: If True, try to load existing checkpoint

        Returns:
            ArviZ InferenceData with thinned trace
        """
        if checkpoint_dir:
            checkpoint_dir = Path(checkpoint_dir)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            trace_path = checkpoint_dir / 'trace.nc'
            config_path = checkpoint_dir / 'config.json'

            # Check for existing completed checkpoint to resume from
            if resume_from_checkpoint and trace_path.exists():
                logger.info(f"Loading existing checkpoint from {trace_path}")
                try:
                    existing_trace = az.from_netcdf(str(trace_path))
                    # Verify it's complete
                    if self._is_trace_complete(existing_trace):
                        logger.info("Resuming from completed checkpoint")
                        if checkpoint_callback:
                            checkpoint_callback(self.draws, self.draws)
                        return existing_trace
                    else:
                        logger.warning("Existing trace incomplete, re-running sampling")
                except Exception as e:
                    logger.warning(f"Could not load checkpoint: {e}, re-running sampling")

            # Save sampling config for resume capability
            self._save_config(config_path)

        with model:
            # Sample with progress tracking
            # Use higher target_accept (0.95) to reduce divergences
            trace = self._sample_with_fallback()

        # Thin the trace for storage
        thinned_trace = self._thin_trace(trace)

        # Save checkpoint after successful completion
        if checkpoint_dir:
            self._save_checkpoint(thinned_trace, checkpoint_dir)
            if checkpoint_callback:
                checkpoint_callback(self.draws, self.draws)

        return thinned_trace

    def _sample_with_fallback(self) -> 'az.InferenceData':
        """
        Run MCMC sampling with parallel chains if enabled, with fallback to sequential.

        Attempts to run chains in parallel using the 'spawn' multiprocessing context,
        which creates fresh Python interpreters that don't inherit state from the parent.
        This is safer in worker environments like Huey. Falls back to sequential
        sampling if parallel fails.

        Returns:
            ArviZ InferenceData with posterior samples
        """
        # Common sampling arguments
        sample_kwargs = {
            'draws': self.draws,
            'tune': self.tune,
            'chains': self.chains,
            'random_seed': self.random_seed,
            'return_inferencedata': True,
            'progressbar': True,
            'target_accept': DEFAULT_MCMC_TARGET_ACCEPT,
            'idata_kwargs': {'log_likelihood': False}  # Save memory
        }

        if self.parallel_chains and self.chains > 1:
            # Try parallel sampling with spawn context
            try:
                logger.info(
                    f"Attempting parallel MCMC sampling: {self.chains} chains "
                    f"with spawn multiprocessing context"
                )
                trace = pm.sample(
                    **sample_kwargs,
                    cores=self.chains,  # Use all chains in parallel
                    mp_ctx="spawn"  # Spawn context avoids fork-related issues in workers
                )
                logger.info("Parallel MCMC sampling completed successfully")
                return trace

            except Exception as e:
                # Log the error and fall back to sequential
                logger.warning(
                    f"Parallel MCMC sampling failed: {e}. "
                    f"Falling back to sequential sampling."
                )

        # Sequential sampling (fallback or if parallel_chains=False)
        logger.info(f"Running sequential MCMC sampling: {self.chains} chains")
        trace = pm.sample(
            **sample_kwargs,
            cores=1  # Sequential chains - safe in any environment
        )
        return trace

    def _is_trace_complete(self, trace: 'az.InferenceData') -> bool:
        """
        Check if a trace represents a complete sampling run.

        Args:
            trace: ArviZ InferenceData to check

        Returns:
            True if trace appears complete
        """
        try:
            if not hasattr(trace, 'posterior'):
                return False

            # Check number of draws (accounting for thinning)
            n_draws = trace.posterior.dims.get('draw', 0)
            expected_draws = self.draws // self.thin

            # Allow some tolerance for rounding
            return n_draws >= expected_draws - 1
        except Exception:
            return False

    def _save_config(self, config_path: Path) -> None:
        """
        Save sampling configuration for resume capability.

        Args:
            config_path: Path to save config JSON
        """
        config = {
            'chains': self.chains,
            'draws': self.draws,
            'tune': self.tune,
            'thin': self.thin,
            'random_seed': self.random_seed,
            'saved_at': datetime.now().isoformat()
        }
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def _load_config(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load sampling configuration from checkpoint.

        Args:
            config_path: Path to config JSON

        Returns:
            Config dict or None if not found
        """
        if not config_path.exists():
            return None
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            return None

    def _save_checkpoint(
        self,
        trace: 'az.InferenceData',
        checkpoint_dir: Path,
        is_final: bool = True
    ) -> Path:
        """
        Save trace checkpoint to disk.

        PRD Reference: F11.5

        Args:
            trace: ArviZ InferenceData to save
            checkpoint_dir: Directory for checkpoint
            is_final: Whether this is the final checkpoint

        Returns:
            Path to saved trace file
        """
        trace_path = checkpoint_dir / 'trace.nc'
        trace.to_netcdf(str(trace_path))

        logger.info(
            f"Saved {'final' if is_final else 'intermediate'} checkpoint "
            f"to {trace_path}"
        )
        return trace_path

    @classmethod
    def load_checkpoint(cls, checkpoint_path: Path) -> Optional['az.InferenceData']:
        """
        Load trace from checkpoint file.

        Args:
            checkpoint_path: Path to checkpoint NetCDF file

        Returns:
            ArviZ InferenceData or None if load fails
        """
        if not PYMC_AVAILABLE:
            return None

        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint file not found: {checkpoint_path}")
            return None

        try:
            trace = az.from_netcdf(str(checkpoint_path))
            logger.info(f"Loaded checkpoint from {checkpoint_path}")
            return trace
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    @classmethod
    def cleanup_checkpoints(cls, checkpoint_dir: Path, keep_final: bool = True) -> int:
        """
        Clean up checkpoint files after successful completion.

        PRD Reference: F11.5 - Checkpoint cleanup

        Args:
            checkpoint_dir: Directory containing checkpoints
            keep_final: Whether to keep the final trace.nc file

        Returns:
            Number of files deleted
        """
        checkpoint_dir = Path(checkpoint_dir)
        if not checkpoint_dir.exists():
            return 0

        deleted = 0
        for file_path in checkpoint_dir.iterdir():
            if file_path.is_file():
                # Keep final trace if requested
                if keep_final and file_path.name == 'trace.nc':
                    continue
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Could not delete {file_path}: {e}")

        # Remove directory if empty
        try:
            if not any(checkpoint_dir.iterdir()):
                checkpoint_dir.rmdir()
        except Exception:
            pass

        return deleted

    def _thin_trace(self, trace: 'az.InferenceData') -> 'az.InferenceData':
        """Thin trace by selecting every nth sample."""
        if self.thin <= 1:
            return trace

        # Thin posterior samples
        thinned = trace.sel(draw=slice(None, None, self.thin))
        return thinned

    # NOTE: summarize_posterior is defined below run_analysis to handle multivariate case

    def probability_of_direction(
        self,
        trace: 'az.InferenceData',
        param_name: str,
        construct_idx: int
    ) -> float:
        """
        Compute probability that parameter is positive: P(param > 0 | data).

        Args:
            trace: ArviZ InferenceData
            param_name: Parameter name
            construct_idx: Construct index

        Returns:
            Probability between 0 and 1
        """
        samples = trace.posterior[param_name].sel(construct=construct_idx).values.flatten()
        return float(np.mean(samples > 0))

    # NOTE: probability_meaningful is defined below run_analysis to handle multivariate case

    def variance_decomposition(
        self,
        trace: 'az.InferenceData',
        param_idx: int = 0,
        model_metadata: Optional[ModelMetadata] = None
    ) -> VarianceComponents:
        """
        Decompose variance into session, plate, and residual components.

        Only reports components that were actually estimated based on
        the model tier. Missing components are marked as N/A.

        Args:
            trace: ArviZ InferenceData
            param_idx: Parameter index (0=log_fc_fmax, 1=log_fc_kobs, etc.)
            model_metadata: Model tier metadata (to know which components exist)

        Returns:
            VarianceComponents with variance at each level
        """
        var_session = None
        var_plate = None
        session_status = None
        plate_status = None

        # Extract residual variance (always present)
        try:
            sigma_residual = trace.posterior['sigma_residual'].values[:, :, param_idx].flatten()
        except (KeyError, IndexError):
            sigma_residual = trace.posterior['sigma_residual'].values.flatten()
        var_residual = float(np.mean(sigma_residual ** 2))

        # Extract session variance if estimated (tau_session in new model)
        if model_metadata is None or model_metadata.estimates_session_variance:
            try:
                # Try new non-centered parameterization (tau_session)
                tau_session = trace.posterior['tau_session'].values[:, :, param_idx].flatten()
                var_session = float(np.mean(tau_session ** 2))
            except (KeyError, IndexError):
                try:
                    # Fall back to old parameterization (sigma_session)
                    sigma_session = trace.posterior['sigma_session'].values[:, :, param_idx].flatten()
                    var_session = float(np.mean(sigma_session ** 2))
                except (KeyError, IndexError):
                    try:
                        sigma_session = trace.posterior['sigma_session'].values.flatten()
                        var_session = float(np.mean(sigma_session ** 2))
                    except KeyError:
                        var_session = None
                        session_status = "N/A — insufficient data"
        else:
            session_status = "N/A — insufficient data (need 2+ sessions)"

        # Extract plate variance if estimated (tau_plate in new model)
        if model_metadata is None or model_metadata.estimates_plate_variance:
            try:
                # Try new non-centered parameterization (tau_plate)
                tau_plate = trace.posterior['tau_plate'].values[:, :, param_idx].flatten()
                var_plate = float(np.mean(tau_plate ** 2))
            except (KeyError, IndexError):
                try:
                    # Fall back to old parameterization (sigma_plate)
                    sigma_plate = trace.posterior['sigma_plate'].values[:, :, param_idx].flatten()
                    var_plate = float(np.mean(sigma_plate ** 2))
                except (KeyError, IndexError):
                    try:
                        sigma_plate = trace.posterior['sigma_plate'].values.flatten()
                        var_plate = float(np.mean(sigma_plate ** 2))
                    except KeyError:
                        var_plate = None
                        plate_status = "N/A — insufficient data"
        else:
            plate_status = "N/A — insufficient data (need 2+ plates/session)"

        # Calculate total variance (only from estimated components)
        var_total = var_residual
        if var_session is not None:
            var_total += var_session
        if var_plate is not None:
            var_total += var_plate

        return VarianceComponents(
            var_session=var_session,
            var_plate=var_plate,
            var_residual=var_residual,
            var_total=var_total,
            session_status=session_status,
            plate_status=plate_status
        )

    def extract_correlations(
        self,
        trace: 'az.InferenceData',
        params: List[str]
    ) -> Dict[Tuple[str, str], float]:
        """
        Extract parameter correlations from multivariate model.

        Args:
            trace: ArviZ InferenceData
            params: List of parameter names

        Returns:
            Dict mapping (param1, param2) tuples to correlation values
        """
        correlations = {}

        if len(params) < 2:
            return correlations

        try:
            # Try to get correlation matrix from LKJ prior
            if 'corr_session' in trace.posterior:
                corr_samples = trace.posterior['corr_session'].values
                mean_corr = np.mean(corr_samples, axis=(0, 1))

                for i, p1 in enumerate(params):
                    for j, p2 in enumerate(params):
                        if i < j:
                            correlations[(p1, p2)] = float(mean_corr[i, j])
        except Exception as e:
            logger.warning(f"Could not extract correlations: {e}")

        return correlations

    def run_analysis(
        self,
        fold_changes: pd.DataFrame,
        checkpoint_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        resume_from_checkpoint: bool = False
    ) -> BayesianResult:
        """
        Run complete Bayesian hierarchical analysis with adaptive model selection.

        Automatically selects the appropriate model tier based on data structure:
        - Tier 1: Single session, single plate → residual only
        - Tier 2a: Multiple sessions, single plate each → session + residual
        - Tier 2b: Single session, multiple plates → plate + residual
        - Tier 3: Multiple sessions, multiple plates → full hierarchy

        PRD Reference: F11.5 - MCMC with checkpointing

        Args:
            fold_changes: DataFrame with fold change data
            checkpoint_dir: Directory for checkpoints and trace storage
            progress_callback: Callback(stage, progress_fraction) for progress
            resume_from_checkpoint: If True, try to load existing checkpoint

        Returns:
            BayesianResult with all posteriors, diagnostics, and model metadata
        """
        start_time = datetime.now()
        result = BayesianResult(
            n_chains=self.chains,
            n_draws=self.draws,
            n_tune=self.tune,
            thin_factor=self.thin
        )

        if progress_callback:
            progress_callback("Preparing data", 0.05)

        # Prepare data
        data = self.prepare_data(fold_changes)
        params = data['params']
        construct_ids = data['construct_ids']

        # ===== ADAPTIVE MODEL SELECTION =====
        if progress_callback:
            progress_callback("Detecting data structure", 0.07)

        # Detect data structure and select appropriate model tier
        data_structure = self.detect_data_structure(fold_changes)
        model_metadata = self.select_model_tier(data_structure)

        # Store metadata in result
        result.model_metadata = model_metadata

        # Log the tier selection
        logger.info(
            f"Model tier selected: {model_metadata.tier.value} | "
            f"Sessions: {model_metadata.n_sessions}, "
            f"Max plates/session: {model_metadata.max_plates_per_session}"
        )
        logger.info(f"User message: {model_metadata.user_message}")

        if progress_callback:
            progress_callback("Building model", 0.10)

        # Build model with appropriate tier
        model = self.build_model(data, model_metadata=model_metadata)

        if progress_callback:
            progress_callback("Sampling", 0.15)

        # Sample (with optional resume from checkpoint)
        trace = self.sample(
            model,
            checkpoint_dir=checkpoint_dir,
            resume_from_checkpoint=resume_from_checkpoint
        )

        # Store trace path
        if checkpoint_dir:
            result.trace_path = str(checkpoint_dir / 'trace.nc')

        if progress_callback:
            progress_callback("Computing summaries", 0.85)

        # Extract posteriors for each construct and parameter
        for c_idx, construct_id in enumerate(construct_ids):
            result.posteriors[construct_id] = {}

            for p_idx, param in enumerate(params):
                summary = self.summarize_posterior(
                    trace, 'mu', c_idx, param_idx=p_idx, param_label=param
                )
                summary.prob_meaningful = self.probability_meaningful(
                    trace, 'mu', c_idx, param_idx=p_idx, param_label=param,
                    threshold=self.meaningful_threshold
                )
                result.posteriors[construct_id][param] = summary

        if progress_callback:
            progress_callback("Variance decomposition", 0.90)

        # Variance decomposition (with metadata for handling missing components)
        for p_idx, param in enumerate(params):
            result.variance_components[param] = self.variance_decomposition(
                trace, p_idx, model_metadata=model_metadata
            )

        if progress_callback:
            progress_callback("Extracting correlations", 0.95)

        # Parameter correlations (at construct level)
        correlations = self.extract_correlations(trace, params)
        for construct_id in construct_ids:
            result.correlations[construct_id] = correlations

        # MCMC diagnostics
        try:
            # Check for divergences
            if hasattr(trace, 'sample_stats') and 'diverging' in trace.sample_stats:
                result.divergent_count = int(trace.sample_stats['diverging'].sum())
        except Exception:
            pass

        # Add warnings
        if result.divergent_count > 0:
            pct = 100 * result.divergent_count / (self.chains * self.draws)
            result.warnings.append(f"MCMC had {result.divergent_count} divergent transitions ({pct:.1f}%)")

        # Add tier-specific info to warnings if not full model
        if model_metadata.tier != ModelTier.TIER_3_FULL:
            result.warnings.append(model_metadata.user_message)

        # Compute model residuals (observed - posterior mean prediction)
        try:
            result.model_residuals = self._compute_residuals(
                trace, data, model_metadata
            )
        except Exception as e:
            logger.warning(f"Failed to compute model residuals: {e}")

        result.duration_seconds = (datetime.now() - start_time).total_seconds()

        if progress_callback:
            progress_callback("Complete", 1.0)

        return result

    def _compute_residuals(
        self,
        trace: 'az.InferenceData',
        data: Dict[str, Any],
        model_metadata: ModelMetadata
    ) -> Dict[str, List[float]]:
        """
        Compute model residuals: observed - posterior mean prediction.

        For each observation, the predicted value is:
          mu[construct] + gamma[session] (if tier includes sessions)
                        + delta[plate]   (if tier includes plates)

        averaged over all posterior draws.

        Returns:
            Dict mapping parameter name to list of residuals.
        """
        Y = data['Y']  # (n_obs, n_params)
        params = data['params']
        construct_idx = data['construct_idx']
        tier = model_metadata.tier

        # Posterior mean of construct effects: average over chains and draws
        # mu shape in trace: (chains, draws, construct, param)
        mu_mean = trace.posterior['mu'].values.mean(axis=(0, 1))  # (construct, param)
        predicted = mu_mean[construct_idx]  # (n_obs, param)

        # Add session effects if present
        if tier in [ModelTier.TIER_2A_SESSION, ModelTier.TIER_3_FULL]:
            if 'gamma_session' in trace.posterior:
                session_idx = data['session_idx']
                gamma_mean = trace.posterior['gamma_session'].values.mean(axis=(0, 1))
                predicted = predicted + gamma_mean[session_idx]

        # Add plate effects if present
        if tier in [ModelTier.TIER_2B_PLATE, ModelTier.TIER_3_FULL]:
            if 'delta_plate' in trace.posterior:
                plate_idx = data['plate_idx']
                delta_mean = trace.posterior['delta_plate'].values.mean(axis=(0, 1))
                predicted = predicted + delta_mean[plate_idx]

        # Residuals = observed - predicted
        residuals = Y - predicted  # (n_obs, n_params)

        # Package per parameter
        result = {}
        for p_idx, param in enumerate(params):
            result[param] = residuals[:, p_idx].tolist()

        return result

    def summarize_posterior(
        self,
        trace: 'az.InferenceData',
        param_name: str,
        construct_idx: int,
        param_idx: int = 0,
        param_label: str = None,
        ci_level: float = DEFAULT_CI_LEVEL
    ) -> PosteriorSummary:
        """
        Compute posterior summary statistics.

        Args:
            trace: ArviZ InferenceData
            param_name: Parameter name (e.g., 'mu')
            construct_idx: Construct index in the model
            param_idx: Parameter dimension index (for multivariate)
            param_label: Parameter label string (e.g., 'log_fc_fmax') for selection
            ci_level: Credible interval level (default 0.95)

        Returns:
            PosteriorSummary with mean, std, CI, etc.
        """
        # Extract samples
        # The 'param' coordinate may be string labels, so use param_label if provided
        try:
            if param_label is not None:
                # Use string label for selection
                samples = trace.posterior[param_name].sel(
                    construct=construct_idx, param=param_label
                ).values.flatten()
            else:
                # Fall back to integer index
                samples = trace.posterior[param_name].sel(
                    construct=construct_idx, param=param_idx
                ).values.flatten()
        except Exception:
            # Univariate model (no param dimension)
            samples = trace.posterior[param_name].sel(
                construct=construct_idx
            ).values.flatten()

        # Basic statistics
        mean = float(np.mean(samples))
        std = float(np.std(samples))

        # Credible interval
        alpha = 1 - ci_level
        ci_lower = float(np.percentile(samples, 100 * alpha / 2))
        ci_upper = float(np.percentile(samples, 100 * (1 - alpha / 2)))

        # MCMC diagnostics using ArviZ
        r_hat = None
        ess_bulk = None
        ess_tail = None
        try:
            summary = az.summary(trace, var_names=[param_name])
            # Find the right row
            idx = construct_idx * (trace.posterior[param_name].sizes.get('param', 1)) + param_idx
            if idx < len(summary):
                r_hat = float(summary['r_hat'].iloc[idx])
                ess_bulk = float(summary['ess_bulk'].iloc[idx])
                ess_tail = float(summary['ess_tail'].iloc[idx])
        except Exception:
            pass

        # Probability of direction
        prob_positive = float(np.mean(samples > 0))

        # Thin samples for storage (~500-1000 samples)
        target_samples = 500
        if len(samples) > target_samples:
            step = len(samples) // target_samples
            thinned_samples = samples[::step][:target_samples].tolist()
        else:
            thinned_samples = samples.tolist()

        return PosteriorSummary(
            mean=mean,
            std=std,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_level=ci_level,
            n_samples=len(samples),
            r_hat=r_hat,
            ess_bulk=ess_bulk,
            ess_tail=ess_tail,
            prob_positive=prob_positive,
            samples=thinned_samples
        )

    def probability_meaningful(
        self,
        trace: 'az.InferenceData',
        param_name: str,
        construct_idx: int,
        param_idx: int = 0,
        param_label: str = None,
        threshold: float = MEANINGFUL_EFFECT_THRESHOLD
    ) -> float:
        """
        Compute probability of meaningful effect: P(|param| > threshold | data).

        Args:
            trace: ArviZ InferenceData
            param_name: Parameter name
            construct_idx: Construct index
            param_idx: Parameter dimension index
            param_label: Parameter label string for selection
            threshold: Effect size threshold

        Returns:
            Probability between 0 and 1
        """
        try:
            if param_label is not None:
                samples = trace.posterior[param_name].sel(
                    construct=construct_idx, param=param_label
                ).values.flatten()
            else:
                samples = trace.posterior[param_name].sel(
                    construct=construct_idx, param=param_idx
                ).values.flatten()
        except Exception:
            # Univariate model (no param dimension)
            samples = trace.posterior[param_name].sel(
                construct=construct_idx
            ).values.flatten()

        return float(np.mean(np.abs(samples) > threshold))


def check_pymc_available() -> bool:
    """Check if PyMC is available."""
    return PYMC_AVAILABLE
