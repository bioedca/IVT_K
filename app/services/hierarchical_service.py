"""
Hierarchical analysis service.

Phase 5: Advanced Statistics (Hierarchical Modeling)
Coordinates Bayesian and frequentist analyses with database integration.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
import logging
import traceback

from app.extensions import db
from app.models import Project, Construct, ExperimentalSession
from app.models.experiment import Plate, Well, QCStatus
from app.models.fit_result import FitResult, FoldChange
from app.models.analysis_version import (
    AnalysisVersion, AnalysisStatus,
    HierarchicalResult, ParameterCorrelation, MCMCCheckpoint, CheckpointStatus
)
from app.analysis.bayesian import (
    BayesianHierarchical, BayesianResult, PosteriorSummary,
    check_pymc_available, PYMC_AVAILABLE
)
from app.analysis.frequentist import (
    FrequentistHierarchical, FrequentistResult,
    compare_bayesian_frequentist, check_statsmodels_available, STATSMODELS_AVAILABLE
)

logger = logging.getLogger(__name__)


class HierarchicalAnalysisError(Exception):
    """Raised when hierarchical analysis fails."""
    pass


@dataclass
class AnalysisConfig:
    """Configuration for hierarchical analysis."""
    # MCMC settings
    mcmc_chains: int = 4
    mcmc_draws: int = 2000
    mcmc_tune: int = 1000
    mcmc_thin: int = 5
    random_seed: Optional[int] = None
    parallel_chains: bool = True  # Run MCMC chains in parallel (with fallback)

    # Analysis options
    run_bayesian: bool = True
    run_frequentist: bool = True
    meaningful_threshold: float = 0.182  # ln(1.2) — natural log, matching fold change data
    ci_level: float = 0.95

    @classmethod
    def from_project(cls, project) -> "AnalysisConfig":
        """Build AnalysisConfig with meaningful_threshold from a Project model."""
        import numpy as np
        config = cls()
        if project and getattr(project, 'meaningful_fc_threshold', None):
            config.meaningful_threshold = np.log(project.meaningful_fc_threshold)
        return config


class HierarchicalService:
    """
    Service for running hierarchical analyses.

    Coordinates Bayesian and frequentist analyses, manages checkpoints,
    and stores results in the database.
    """

    # Storage paths
    DATA_DIR = Path("data")
    TRACES_DIR = DATA_DIR / "traces"
    CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

    @classmethod
    def create_analysis_version(
        cls,
        project_id: int,
        name: str,
        config: AnalysisConfig,
        description: Optional[str] = None
    ) -> AnalysisVersion:
        """
        Create a new analysis version record.

        Args:
            project_id: Project ID
            name: Version name (must be unique within project)
            config: Analysis configuration
            description: Optional description

        Returns:
            AnalysisVersion database model
        """
        project = Project.query.get(project_id)
        if not project:
            raise HierarchicalAnalysisError(f"Project {project_id} not found")

        # Check for duplicate name
        existing = AnalysisVersion.query.filter_by(
            project_id=project_id, name=name
        ).first()
        if existing:
            raise HierarchicalAnalysisError(
                f"Analysis version '{name}' already exists for this project"
            )

        version = AnalysisVersion(
            project_id=project_id,
            name=name,
            description=description,
            status=AnalysisStatus.RUNNING,
            model_type="delayed_exponential",
            mcmc_chains=config.mcmc_chains,
            mcmc_draws=config.mcmc_draws,
            mcmc_tune=config.mcmc_tune,
            mcmc_thin=config.mcmc_thin,
            random_seed=config.random_seed,
            started_at=datetime.now(timezone.utc)
        )
        db.session.add(version)
        db.session.commit()

        return version

    @classmethod
    def get_fold_change_data(
        cls,
        project_id: int,
        ligand_condition: str = None,
        comparison_type: str = None,
    ) -> pd.DataFrame:
        """
        Gather fold change data for hierarchical analysis.

        Args:
            project_id: Project ID
            ligand_condition: Filter by ligand condition ("+Lig", "-Lig", "+Lig/-Lig", or None for all)
            comparison_type: Filter by comparison type ("within_condition", "ligand_effect", or None for all)

        Returns:
            DataFrame with columns: construct_id, session_id, plate_id,
                                   log_fc_fmax, log_fc_kobs, delta_tlag,
                                   ligand_condition, comparison_type
        """
        # Get all fold changes for the project
        # Exclude data from QC rejected sessions
        query = (
            db.session.query(
                FoldChange,
                Well.construct_id,
                Well.plate_id,
                Plate.session_id,
                Construct.family,
            )
            .join(Well, FoldChange.test_well_id == Well.id)
            .join(Plate, Well.plate_id == Plate.id)
            .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
            .outerjoin(Construct, Well.construct_id == Construct.id)
            .filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status != QCStatus.REJECTED
            )
        )

        # Apply ligand condition filter
        if ligand_condition is not None:
            query = query.filter(FoldChange.ligand_condition == ligand_condition)

        # Apply comparison type filter
        if comparison_type is not None:
            query = query.filter(FoldChange.comparison_type == comparison_type)

        fold_changes = query.all()

        if not fold_changes:
            raise HierarchicalAnalysisError(
                "No fold change data available. Run curve fitting first."
            )

        data = []
        for fc, construct_id, plate_id, session_id, family in fold_changes:
            if construct_id is None:
                continue

            row = {
                'construct_id': construct_id,
                'session_id': session_id,
                'plate_id': plate_id,
                'log_fc_fmax': fc.log_fc_fmax,
                'log_fc_kobs': fc.log_fc_kobs,
                'delta_tlag': fc.delta_tlag,
                'ligand_condition': fc.ligand_condition,
                'comparison_type': fc.comparison_type,
                'family': family,
            }
            data.append(row)

        df = pd.DataFrame(data)

        if len(df) == 0:
            raise HierarchicalAnalysisError(
                "No valid fold change data with construct assignments"
            )

        return df

    @classmethod
    def get_available_ligand_conditions(cls, project_id: int) -> List[str]:
        """
        Get unique ligand conditions available in fold change data for a project.

        Args:
            project_id: Project ID

        Returns:
            List of unique ligand condition strings (e.g., ["+Lig", "-Lig", "+Lig/-Lig"])
        """
        conditions = (
            db.session.query(FoldChange.ligand_condition)
            .join(Well, FoldChange.test_well_id == Well.id)
            .join(Plate, Well.plate_id == Plate.id)
            .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
            .filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status != QCStatus.REJECTED,
                FoldChange.ligand_condition.isnot(None)
            )
            .distinct()
            .all()
        )
        return [c[0] for c in conditions if c[0]]

    @classmethod
    def get_available_families(cls, project_id: int) -> List[str]:
        """
        Get unique construct families available in fold change data for a project.

        Excludes "universal" family (unregulated constructs) since they serve
        as reference and shouldn't get their own hierarchical model.

        Args:
            project_id: Project ID

        Returns:
            List of unique family names
        """
        families = (
            db.session.query(Construct.family)
            .join(Well, Well.construct_id == Construct.id)
            .join(FoldChange, FoldChange.test_well_id == Well.id)
            .join(Plate, Well.plate_id == Plate.id)
            .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
            .filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status != QCStatus.REJECTED,
                Construct.family.isnot(None),
                Construct.is_unregulated == False,  # noqa: E712
            )
            .distinct()
            .all()
        )
        return [f[0] for f in families if f[0] and f[0] != "universal"]

    @classmethod
    def run_analysis(
        cls,
        project_id: int,
        version_name: str,
        config: Optional[AnalysisConfig] = None,
        description: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        resume_from_checkpoint: bool = False,
        ligand_condition: Optional[str] = None,
        comparison_type: Optional[str] = None,
    ) -> AnalysisVersion:
        """
        Run complete hierarchical analysis with checkpoint support.

        PRD Reference: F11.5 - MCMC checkpointing

        Both Bayesian and frequentist analyses are run by default.

        Args:
            project_id: Project ID
            version_name: Name for this analysis version
            config: Analysis configuration (uses defaults if None)
            description: Optional description
            progress_callback: Callback(stage, progress) for progress updates
            resume_from_checkpoint: If True, try to resume from existing checkpoint

        Returns:
            AnalysisVersion with results
        """
        config = config or AnalysisConfig()

        # Create version record
        version = cls.create_analysis_version(
            project_id, version_name, config, description
        )

        # Track current draw for error checkpoints
        current_draw = 0

        try:
            # Get fold change data
            if progress_callback:
                progress_callback("Gathering data", 0.05)

            df = cls.get_fold_change_data(
                project_id,
                ligand_condition=ligand_condition,
                comparison_type=comparison_type,
            )

            # Create checkpoint directory
            checkpoint_dir = cls.CHECKPOINTS_DIR / str(project_id) / str(version.id)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            # Determine ligand conditions to loop over
            if ligand_condition is not None:
                # Explicitly requested — data already filtered by get_fold_change_data
                conditions = [ligand_condition]
            elif 'ligand_condition' in df.columns:
                has_null_condition = df['ligand_condition'].isna().any()
                unique_conds = sorted(
                    c for c in df['ligand_condition'].dropna().unique()
                )
                if has_null_condition and unique_conds:
                    # Mixed: some FCs have no condition (standard comparisons),
                    # others have explicit conditions (+Lig, -Lig, etc.)
                    conditions = [None, *unique_conds]
                elif unique_conds:
                    conditions = unique_conds
                else:
                    conditions = [None]
            else:
                conditions = [None]
            n_conditions = len(conditions)

            # Determine families to run separate models for
            families = sorted(
                f for f in df['family'].dropna().unique()
                if f != "universal"
            )
            if not families:
                # Fallback: treat all data as one group (legacy behaviour)
                families = [None]

            n_families = len(families)
            n_iterations = n_families * n_conditions
            any_bayesian_succeeded = False
            any_frequentist_succeeded = False

            # Per-family storage for version-level metadata
            per_family_tier_metadata = {}
            per_family_residuals = {}
            per_family_comparisons = {}
            all_frequentist_warnings = []
            last_checkpoint_info = None  # Track last successful Bayesian checkpoint

            # Progress budget allocation:
            #   0.05        – data gathering (done)
            #   0.05–0.90   – per-family×condition Bayesian + Frequentist (0.85 total)
            #   0.90–0.95   – model comparisons
            #   0.95–1.00   – finalization
            iter_budget = 0.85 / n_iterations  # progress per family×condition

            # Warn about constructs that will be excluded (NULL family)
            null_family_count = int(df['family'].isna().sum())
            if null_family_count > 0 and families != [None]:
                logger.warning(
                    f"{null_family_count} fold-change observations have no family "
                    f"assignment and will be excluded from per-family analysis"
                )

            for fam_idx, family in enumerate(families):
                family_label = family or "all"

                if family is not None:
                    family_df = df[df['family'] == family]
                else:
                    family_df = df

                if len(family_df) == 0:
                    logger.warning(f"No fold change data for family '{family_label}', skipping")
                    continue

                for cond_idx, condition in enumerate(conditions):
                    iteration_idx = fam_idx * n_conditions + cond_idx
                    iter_start = 0.05 + iteration_idx * iter_budget
                    current_draw = 0  # Reset per iteration for error checkpoints

                    # Build iteration label / metadata key
                    if condition is not None:
                        iter_label = f"{family_label}|{condition}"
                    else:
                        iter_label = family_label

                    # Filter to condition
                    if condition is not None:
                        condition_df = family_df[family_df['ligand_condition'] == condition]
                    elif n_conditions > 1:
                        # Mixed conditions: isolate only null-condition rows
                        condition_df = family_df[family_df['ligand_condition'].isna()]
                    else:
                        # No ligand conditions at all: use everything
                        condition_df = family_df

                    if len(condition_df) == 0:
                        logger.warning(f"No fold change data for '{iter_label}', skipping")
                        continue

                    logger.info(
                        f"Running analysis for '{iter_label}' "
                        f"({len(condition_df)} observations, "
                        f"iteration {iteration_idx + 1}/{n_iterations})"
                    )

                    # --- Bayesian analysis ---
                    bayesian_result = None
                    if config.run_bayesian and PYMC_AVAILABLE:
                        if progress_callback:
                            progress_callback(
                                f"Bayesian: {iter_label} ({iteration_idx + 1}/{n_iterations})",
                                iter_start
                            )

                        try:
                            bayesian = BayesianHierarchical(
                                chains=config.mcmc_chains,
                                draws=config.mcmc_draws,
                                tune=config.mcmc_tune,
                                thin=config.mcmc_thin,
                                random_seed=config.random_seed,
                                parallel_chains=config.parallel_chains
                            )
                            bayesian.meaningful_threshold = config.meaningful_threshold

                            # Bayesian gets ~60% of each iteration's budget
                            bayes_budget = iter_budget * 0.60

                            def bayesian_progress(stage, prog, _start=iter_start, _budget=bayes_budget, _label=iter_label):
                                nonlocal current_draw
                                current_draw = int(prog * config.mcmc_draws)
                                overall = _start + _budget * prog
                                if progress_callback:
                                    progress_callback(
                                        f"Bayesian [{_label}]: {stage}",
                                        overall
                                    )

                            safe_label = iter_label.replace('|', '_').replace('/', '_')
                            iter_checkpoint_dir = checkpoint_dir / safe_label
                            iter_checkpoint_dir.mkdir(parents=True, exist_ok=True)

                            bayesian_result = bayesian.run_analysis(
                                condition_df,
                                checkpoint_dir=iter_checkpoint_dir,
                                progress_callback=bayesian_progress,
                                resume_from_checkpoint=resume_from_checkpoint
                            )

                            # Store Bayesian results
                            cls._store_bayesian_results(
                                version, bayesian_result,
                                ligand_condition=condition
                            )

                            # Collect per-iteration metadata
                            if bayesian_result.model_metadata is not None:
                                per_family_tier_metadata[iter_label] = (
                                    bayesian_result.model_metadata.to_dict()
                                )
                            if bayesian_result.model_residuals:
                                per_family_residuals[iter_label] = (
                                    bayesian_result.model_residuals
                                )

                            any_bayesian_succeeded = True

                            # Update trace path (last iteration wins; individual traces
                            # are in per-iteration checkpoint dirs)
                            version.trace_file_path = bayesian_result.trace_path
                            version.trace_thin_factor = config.mcmc_thin

                            # Create checkpoint record (final flag set post-loop)
                            last_checkpoint_info = {
                                'checkpoint_path': str(iter_checkpoint_dir / 'trace.nc'),
                                'config_path': str(iter_checkpoint_dir / 'config.json'),
                            }
                            cls.create_mcmc_checkpoint(
                                version=version,
                                draw_idx=config.mcmc_draws,
                                total_draws=config.mcmc_draws,
                                checkpoint_path=last_checkpoint_info['checkpoint_path'],
                                config_path=last_checkpoint_info['config_path'],
                                is_final=False
                            )

                        except Exception as e:
                            logger.exception(f"Bayesian analysis failed for '{iter_label}'")
                            err_msg = f"Bayesian analysis failed for '{iter_label}': {type(e).__name__}"
                            tb = traceback.format_exc()
                            if version.error_message:
                                version.error_message += f"; {err_msg}"
                                version.error_traceback = (version.error_traceback or "") + f"\n---\n{tb}"
                            else:
                                version.error_message = err_msg
                                version.error_traceback = tb

                            # Create error checkpoint (PRD F11.4)
                            cls.create_error_checkpoint(
                                version=version,
                                draw_idx=current_draw,
                                error_message=str(e),
                                error_traceback=traceback.format_exc()
                            )

                    # --- Frequentist analysis ---
                    frequentist_result = None
                    if config.run_frequentist and STATSMODELS_AVAILABLE:
                        freq_start = iter_start + iter_budget * 0.60

                        if progress_callback:
                            progress_callback(
                                f"Frequentist: {iter_label} ({iteration_idx + 1}/{n_iterations})",
                                freq_start
                            )

                        try:
                            frequentist = FrequentistHierarchical(ci_level=config.ci_level)

                            freq_budget = iter_budget * 0.30

                            def freq_progress(stage, prog, _start=freq_start, _budget=freq_budget, _label=iter_label):
                                overall = _start + _budget * prog
                                if progress_callback:
                                    progress_callback(
                                        f"Frequentist [{_label}]: {stage}",
                                        overall
                                    )

                            frequentist_result = frequentist.run_analysis(
                                condition_df, progress_callback=freq_progress
                            )

                            # Store frequentist results
                            cls._store_frequentist_results(
                                version, frequentist_result,
                                ligand_condition=condition
                            )

                            # Collect warnings
                            if frequentist_result.warnings:
                                for w in frequentist_result.warnings:
                                    all_frequentist_warnings.append(
                                        f"[{iter_label}] {w}"
                                    )

                            any_frequentist_succeeded = True

                        except Exception as e:
                            logger.exception(f"Frequentist analysis failed for '{iter_label}'")
                            err_msg = f"Frequentist analysis failed for '{iter_label}': {type(e).__name__}"
                            if version.error_message:
                                version.error_message += f"; {err_msg}"
                            else:
                                version.error_message = err_msg

                    # --- Model comparison ---
                    if bayesian_result and frequentist_result:
                        try:
                            comparison = compare_bayesian_frequentist(
                                bayesian_result, frequentist_result
                            )
                            per_family_comparisons[iter_label] = comparison

                            if not comparison['overall_agreement']:
                                logger.warning(
                                    f"Bayesian-frequentist disagreement for "
                                    f"'{iter_label}': "
                                    f"{comparison['max_relative_difference']:.1%}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Model comparison failed for '{iter_label}': {e}"
                            )

            # --- Mark last successful Bayesian checkpoint as final ---
            if last_checkpoint_info and any_bayesian_succeeded:
                cls.create_mcmc_checkpoint(
                    version=version,
                    draw_idx=config.mcmc_draws,
                    total_draws=config.mcmc_draws,
                    checkpoint_path=last_checkpoint_info['checkpoint_path'],
                    config_path=last_checkpoint_info['config_path'],
                    is_final=True
                )

            # --- Build and persist comparison graph ---
            try:
                from app.services.comparison_service import ComparisonService
                graph = ComparisonService.build_comparison_graph(project_id)
                ComparisonService.save_comparison_graph(project_id, graph)
                logger.info(
                    f"Saved comparison graph for project {project_id}: "
                    f"{len(graph.edges)} edges"
                )
            except Exception as e:
                logger.warning(f"Could not build/save comparison graph: {e}")

            # --- Store aggregated per-family metadata on version ---
            if progress_callback:
                progress_callback("Finalizing results", 0.92)

            # Model tier metadata: per-family structure
            version.model_tier_metadata = {"per_family": per_family_tier_metadata}
            if all_frequentist_warnings:
                version.model_tier_metadata['frequentist_warnings'] = all_frequentist_warnings
                logger.info(f"Stored {len(all_frequentist_warnings)} frequentist warnings across families")

            # Model residuals: per-family structure
            if per_family_residuals:
                version.model_residuals = {"per_family": per_family_residuals}

            # Model comparison: per-family structure
            if per_family_comparisons:
                version.model_comparison = {"per_family": per_family_comparisons}

            # Determine final status
            if any_bayesian_succeeded or any_frequentist_succeeded:
                version.status = AnalysisStatus.COMPLETED
            else:
                version.status = AnalysisStatus.FAILED
                if not version.error_message:
                    version.error_message = "Both Bayesian and frequentist analyses failed for all families"

            version.completed_at = datetime.now(timezone.utc)
            version.duration_seconds = cls._compute_duration(version)

            db.session.commit()

            if progress_callback:
                progress_callback("Complete", 1.0)

            return version

        except Exception as e:
            # Mark version as failed
            logger.exception("Analysis failed")
            version.status = AnalysisStatus.FAILED
            version.error_message = f"Analysis failed: {type(e).__name__}: {e}"
            version.error_traceback = traceback.format_exc()
            version.completed_at = datetime.now(timezone.utc)
            version.duration_seconds = cls._compute_duration(version)
            db.session.commit()

            raise HierarchicalAnalysisError(f"Analysis failed: {type(e).__name__}") from e

    @staticmethod
    def _compute_duration(version: AnalysisVersion) -> Optional[float]:
        """Compute duration in seconds, handling naive/aware datetime mixing."""
        if not version.started_at or not version.completed_at:
            return None
        # Strip timezone from both to avoid naive/aware mismatch
        # (SQLite DateTime columns don't preserve timezone info)
        started = version.started_at.replace(tzinfo=None)
        completed = version.completed_at.replace(tzinfo=None)
        delta = (completed - started).total_seconds()
        if delta < 0:
            logger.warning(f"Negative duration for version {version.id}: {delta}s")
            return 0.0
        return delta

    @classmethod
    def _store_bayesian_results(
        cls,
        version: AnalysisVersion,
        result: BayesianResult,
        ligand_condition: Optional[str] = None
    ) -> None:
        """
        Store Bayesian results in database.

        Uses nested transaction (savepoint) to ensure atomicity.
        If any error occurs, all results for this batch are rolled back.
        """
        try:
            # Use nested transaction (savepoint) for atomicity
            with db.session.begin_nested():
                # Note: model_tier_metadata and model_residuals are now stored
                # at the version level by run_analysis() in per-family structure.
                # This method only stores construct-level posteriors and correlations.

                if result.model_metadata is not None:
                    logger.info(
                        f"Storing Bayesian results for tier: "
                        f"{result.model_metadata.tier.value}, "
                        f"analysis version {version.id}"
                    )

                # Store construct-level posteriors
                for construct_id, params in result.posteriors.items():
                    for param_name, summary in params.items():
                        hr = HierarchicalResult(
                            analysis_version_id=version.id,
                            construct_id=construct_id,
                            parameter_type=param_name,
                            analysis_type="bayesian",
                            ligand_condition=ligand_condition,
                            mean=summary.mean,
                            std=summary.std,
                            ci_lower=summary.ci_lower,
                            ci_upper=summary.ci_upper,
                            prob_positive=summary.prob_positive,
                            prob_meaningful=summary.prob_meaningful,
                            n_samples=summary.n_samples,
                            r_hat=summary.r_hat,
                            ess_bulk=summary.ess_bulk,
                            ess_tail=summary.ess_tail,
                            posterior_samples=summary.samples
                        )

                        # Add variance components
                        if param_name in result.variance_components:
                            vc = result.variance_components[param_name]
                            hr.var_session = vc.var_session
                            hr.var_plate = vc.var_plate
                            hr.var_residual = vc.var_residual

                        db.session.add(hr)

                # Store parameter correlations
                for construct_id, corrs in result.correlations.items():
                    for (p1, p2), corr in corrs.items():
                        pc = ParameterCorrelation(
                            analysis_version_id=version.id,
                            construct_id=construct_id,
                            parameter_1=p1,
                            parameter_2=p2,
                            correlation=corr
                        )
                        db.session.add(pc)

                db.session.flush()
        except Exception as e:
            logger.error(f"Failed to store Bayesian results: {e}")
            raise HierarchicalAnalysisError(f"Failed to store Bayesian results: {e}") from e

    @classmethod
    def _store_frequentist_results(
        cls,
        version: AnalysisVersion,
        result: FrequentistResult,
        ligand_condition: Optional[str] = None
    ) -> None:
        """
        Store frequentist results in database.

        Uses nested transaction (savepoint) to ensure atomicity.
        If any error occurs, all results for this batch are rolled back.
        """
        try:
            # Use nested transaction (savepoint) for atomicity
            with db.session.begin_nested():
                # Store construct-level estimates
                for construct_id, params in result.estimates.items():
                    for param_name, estimate in params.items():
                        # Skip estimates with NaN values (singular covariance)
                        if (
                            np.isnan(estimate.mean)
                            or np.isnan(estimate.std)
                            or np.isnan(estimate.ci_lower)
                            or np.isnan(estimate.ci_upper)
                        ):
                            logger.warning(
                                f"Skipping frequentist result for construct "
                                f"{construct_id}/{param_name}: NaN in std/CI "
                                f"(singular covariance)"
                            )
                            continue

                        hr = HierarchicalResult(
                            analysis_version_id=version.id,
                            construct_id=construct_id,
                            parameter_type=param_name,
                            analysis_type="frequentist",
                            ligand_condition=ligand_condition,
                            mean=estimate.mean,
                            std=estimate.std,
                            ci_lower=estimate.ci_lower,
                            ci_upper=estimate.ci_upper
                        )

                        # Add variance components
                        if param_name in result.variance_components:
                            vc = result.variance_components[param_name]
                            hr.var_session = vc.var_session
                            hr.var_plate = vc.var_plate
                            hr.var_residual = vc.var_residual

                        db.session.add(hr)

                db.session.flush()
        except Exception as e:
            logger.error(f"Failed to store frequentist results: {e}")
            raise HierarchicalAnalysisError(f"Failed to store frequentist results: {e}") from e

    @classmethod
    def get_analysis_summary(
        cls,
        version_id: int
    ) -> Dict[str, Any]:
        """
        Get summary of analysis results.

        Args:
            version_id: AnalysisVersion ID

        Returns:
            Dict with analysis summary
        """
        version = AnalysisVersion.query.get(version_id)
        if not version:
            raise HierarchicalAnalysisError(f"Analysis version {version_id} not found")

        # Get results grouped by analysis type
        results = HierarchicalResult.query.filter_by(
            analysis_version_id=version_id
        ).all()

        bayesian_results = [r for r in results if r.analysis_type == 'bayesian']
        frequentist_results = [r for r in results if r.analysis_type == 'frequentist']

        # Identify unique ligand conditions in results
        ligand_conditions = list(set(
            r.ligand_condition for r in results if r.ligand_condition
        ))

        summary = {
            'version_id': version_id,
            'name': version.name,
            'status': version.status.value,
            'duration_seconds': version.duration_seconds,
            'n_constructs': len(set(r.construct_id for r in results)),
            'parameters': list(set(r.parameter_type for r in results)),
            'ligand_conditions': sorted(ligand_conditions) if ligand_conditions else [],
            'has_ligand_conditions': len(ligand_conditions) > 0,
            'bayesian': {
                'available': len(bayesian_results) > 0,
                'n_results': len(bayesian_results)
            },
            'frequentist': {
                'available': len(frequentist_results) > 0,
                'n_results': len(frequentist_results)
            },
            'model_comparison': version.model_comparison
        }

        return summary

    @classmethod
    def get_construct_results(
        cls,
        version_id: int,
        construct_id: int,
        ligand_condition: str = None,
    ) -> Dict[str, Any]:
        """
        Get results for a specific construct, optionally filtered by ligand condition.

        Args:
            version_id: AnalysisVersion ID
            construct_id: Construct ID
            ligand_condition: Filter by ligand condition (None = all results)

        Returns:
            Dict with Bayesian and frequentist results for the construct
        """
        query = HierarchicalResult.query.filter_by(
            analysis_version_id=version_id,
            construct_id=construct_id
        )
        if ligand_condition is not None:
            query = query.filter_by(ligand_condition=ligand_condition)

        results = query.all()

        # Group results by ligand_condition, then by analysis_type
        by_condition = {}
        for r in results:
            cond = r.ligand_condition or "all"
            if cond not in by_condition:
                by_condition[cond] = {"bayesian": {}, "frequentist": {}}

            data = {
                'mean': r.mean,
                'std': r.std,
                'ci_lower': r.ci_lower,
                'ci_upper': r.ci_upper,
                'ligand_condition': r.ligand_condition,
                'variance_components': {
                    'session': r.var_session,
                    'plate': r.var_plate,
                    'residual': r.var_residual
                }
            }

            if r.analysis_type == 'bayesian':
                data.update({
                    'prob_positive': r.prob_positive,
                    'prob_meaningful': r.prob_meaningful,
                    'r_hat': r.r_hat,
                    'ess_bulk': r.ess_bulk,
                    'ess_tail': r.ess_tail
                })
                by_condition[cond]["bayesian"][r.parameter_type] = data
            else:
                by_condition[cond]["frequentist"][r.parameter_type] = data

        # For backwards compatibility, flatten if only one condition
        if len(by_condition) == 1:
            cond_key = list(by_condition.keys())[0]
            bayesian = by_condition[cond_key]["bayesian"]
            frequentist = by_condition[cond_key]["frequentist"]
        else:
            # Multiple conditions - return "all" if present, otherwise first condition
            if "all" in by_condition:
                bayesian = by_condition["all"].get("bayesian", {})
                frequentist = by_condition["all"].get("frequentist", {})
            else:
                first_cond = sorted(by_condition.keys())[0]
                bayesian = by_condition[first_cond].get("bayesian", {})
                frequentist = by_condition[first_cond].get("frequentist", {})

        # Get correlations
        correlations = ParameterCorrelation.query.filter_by(
            analysis_version_id=version_id,
            construct_id=construct_id
        ).all()

        corr_dict = {}
        for c in correlations:
            corr_dict[(c.parameter_1, c.parameter_2)] = c.correlation

        return {
            'construct_id': construct_id,
            'bayesian': bayesian,
            'frequentist': frequentist,
            'correlations': corr_dict,
            'by_condition': by_condition,
        }

    @classmethod
    def list_versions(cls, project_id: int) -> List[Dict[str, Any]]:
        """
        List all analysis versions for a project.

        Args:
            project_id: Project ID

        Returns:
            List of version summaries
        """
        versions = AnalysisVersion.query.filter_by(
            project_id=project_id
        ).order_by(AnalysisVersion.created_at.desc()).all()

        return [
            {
                'id': v.id,
                'name': v.name,
                'description': v.description,
                'status': v.status.value,
                'created_at': v.created_at.isoformat() if v.created_at else None,
                'duration_seconds': v.duration_seconds,
                'is_complete': v.is_complete
            }
            for v in versions
        ]

    @classmethod
    def delete_version(cls, version_id: int) -> bool:
        """
        Delete an analysis version and all associated results.

        Args:
            version_id: AnalysisVersion ID

        Returns:
            True if deleted, False if not found
        """
        version = AnalysisVersion.query.get(version_id)
        if not version:
            return False

        db.session.delete(version)
        db.session.commit()
        return True

    # =========================================================================
    # MCMC Checkpoint Management (PRD F11.4-F11.5)
    # =========================================================================

    @classmethod
    def create_mcmc_checkpoint(
        cls,
        version: AnalysisVersion,
        draw_idx: int,
        total_draws: int,
        checkpoint_path: str,
        config_path: str = None,
        is_final: bool = False
    ) -> MCMCCheckpoint:
        """
        Create an MCMC checkpoint record.

        PRD Reference: F11.5 - Checkpoint save

        Args:
            version: AnalysisVersion
            draw_idx: Current draw index
            total_draws: Total draws expected
            checkpoint_path: Path to trace file
            config_path: Path to config JSON
            is_final: Whether this is the final checkpoint

        Returns:
            MCMCCheckpoint record
        """
        checkpoint = MCMCCheckpoint.create_checkpoint(
            analysis_version_id=version.id,
            draw_idx=draw_idx,
            total_draws=total_draws,
            checkpoint_path=checkpoint_path,
            config_path=config_path,
            chain_idx=0,
            total_chains=version.mcmc_chains,
            is_final=is_final,
            status=CheckpointStatus.COMPLETED if is_final else CheckpointStatus.IN_PROGRESS
        )
        db.session.add(checkpoint)
        db.session.flush()
        return checkpoint

    @classmethod
    def create_error_checkpoint(
        cls,
        version: AnalysisVersion,
        draw_idx: int,
        error_message: str,
        error_traceback: str = None
    ) -> MCMCCheckpoint:
        """
        Create an error checkpoint for debugging.

        PRD Reference: F11.4 - Error checkpoint

        Args:
            version: AnalysisVersion
            draw_idx: Draw index at failure (0 if failed before sampling)
            error_message: Error message
            error_traceback: Full traceback

        Returns:
            MCMCCheckpoint with error status
        """
        checkpoint_dir = cls.CHECKPOINTS_DIR / str(version.project_id) / str(version.id)
        checkpoint_path = str(checkpoint_dir / 'error_checkpoint.json')

        # Save error details to file
        try:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            import json
            with open(checkpoint_path, 'w') as f:
                json.dump({
                    'version_id': version.id,
                    'project_id': version.project_id,
                    'draw_idx': draw_idx,
                    'error_message': error_message,
                    'error_traceback': error_traceback,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save error checkpoint file: {e}")

        checkpoint = MCMCCheckpoint.create_error_checkpoint(
            analysis_version_id=version.id,
            draw_idx=draw_idx,
            total_draws=version.mcmc_draws,
            checkpoint_path=checkpoint_path,
            error_message=error_message,
            error_traceback=error_traceback
        )
        db.session.add(checkpoint)
        db.session.flush()
        return checkpoint

    @classmethod
    def get_resumable_checkpoint(
        cls,
        version_id: int
    ) -> Optional[MCMCCheckpoint]:
        """
        Get a resumable checkpoint for an analysis version.

        PRD Reference: F11.5 - Resume from checkpoint

        Args:
            version_id: AnalysisVersion ID

        Returns:
            Resumable MCMCCheckpoint or None
        """
        return MCMCCheckpoint.get_resumable_checkpoint(version_id)

    @classmethod
    def cleanup_checkpoints(
        cls,
        version_id: int,
        keep_final: bool = True
    ) -> int:
        """
        Clean up checkpoint files after successful analysis.

        PRD Reference: F11.5 - Checkpoint cleanup

        Args:
            version_id: AnalysisVersion ID
            keep_final: Whether to keep the final trace file

        Returns:
            Number of checkpoints deleted
        """
        # Clean up database records
        db_deleted = MCMCCheckpoint.cleanup_for_version(version_id)

        # Clean up files
        version = AnalysisVersion.query.get(version_id)
        if version:
            checkpoint_dir = cls.CHECKPOINTS_DIR / str(version.project_id) / str(version_id)
            if keep_final:
                # Just clean intermediate files, keep trace.nc
                BayesianHierarchical.cleanup_checkpoints(checkpoint_dir, keep_final=True)
            else:
                # Remove everything
                import shutil
                try:
                    shutil.rmtree(checkpoint_dir)
                except Exception:
                    pass

        db.session.commit()
        return db_deleted

    @classmethod
    def resume_analysis(
        cls,
        version_id: int,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> AnalysisVersion:
        """
        Resume an analysis from checkpoint.

        PRD Reference: F11.5 - Resume from checkpoint on worker restart

        NOTE: This method does not yet support per-family analysis.
        It processes a single checkpoint/trace as a monolithic model.
        For per-family analyses, re-run via run_analysis() instead of
        resuming from checkpoint.

        Args:
            version_id: AnalysisVersion ID to resume
            progress_callback: Progress callback

        Returns:
            AnalysisVersion with results

        Raises:
            HierarchicalAnalysisError if cannot resume
        """
        version = AnalysisVersion.query.get(version_id)
        if not version:
            raise HierarchicalAnalysisError(f"Analysis version {version_id} not found")

        if version.status == AnalysisStatus.COMPLETED:
            logger.info(f"Analysis {version_id} already completed")
            return version

        # Check for resumable checkpoint
        checkpoint = cls.get_resumable_checkpoint(version_id)
        if not checkpoint:
            raise HierarchicalAnalysisError(
                f"No resumable checkpoint found for analysis {version_id}"
            )

        # Load the checkpoint trace
        from pathlib import Path
        trace_path = Path(checkpoint.checkpoint_path)
        if not trace_path.exists():
            raise HierarchicalAnalysisError(
                f"Checkpoint file not found: {trace_path}"
            )

        if progress_callback:
            progress_callback("Loading checkpoint", 0.10)

        trace = BayesianHierarchical.load_checkpoint(trace_path)
        if trace is None:
            raise HierarchicalAnalysisError(
                f"Could not load checkpoint from {trace_path}"
            )

        if progress_callback:
            progress_callback("Processing results", 0.50)

        # Re-create Bayesian analyzer to process results
        bayesian = BayesianHierarchical(
            chains=version.mcmc_chains,
            draws=version.mcmc_draws,
            tune=version.mcmc_tune,
            thin=version.mcmc_thin,
            random_seed=version.random_seed
        )

        # Get meaningful threshold from project settings
        from app.models.project import Project
        project = Project.query.get(version.project_id)
        meaningful_threshold = AnalysisConfig.from_project(project).meaningful_threshold

        # Get fold change data for construct mapping
        df = cls.get_fold_change_data(version.project_id)
        data = bayesian.prepare_data(df)
        construct_ids = data['construct_ids']
        params = data['params']

        # Extract results from loaded trace
        result = BayesianResult(
            n_chains=version.mcmc_chains,
            n_draws=version.mcmc_draws,
            n_tune=version.mcmc_tune,
            thin_factor=version.mcmc_thin,
            trace_path=str(trace_path)
        )

        # Extract posteriors
        for c_idx, construct_id in enumerate(construct_ids):
            result.posteriors[construct_id] = {}
            for p_idx, param in enumerate(params):
                summary = bayesian.summarize_posterior(trace, 'mu', c_idx, param_idx=p_idx)
                summary.prob_meaningful = bayesian.probability_meaningful(
                    trace, 'mu', c_idx, param_idx=p_idx,
                    threshold=meaningful_threshold
                )
                result.posteriors[construct_id][param] = summary

        # Variance decomposition
        for p_idx, param in enumerate(params):
            result.variance_components[param] = bayesian.variance_decomposition(trace, p_idx)

        if progress_callback:
            progress_callback("Storing results", 0.80)

        # Store results
        cls._store_bayesian_results(version, result)

        # Update version status
        version.status = AnalysisStatus.COMPLETED
        version.trace_file_path = str(trace_path)
        version.completed_at = datetime.now(timezone.utc)
        version.duration_seconds = cls._compute_duration(version)

        db.session.commit()

        if progress_callback:
            progress_callback("Complete", 1.0)

        return version

    @classmethod
    def get_checkpoint_status(cls, version_id: int) -> Dict[str, Any]:
        """
        Get checkpoint status for an analysis version.

        Args:
            version_id: AnalysisVersion ID

        Returns:
            Dict with checkpoint information
        """
        checkpoints = MCMCCheckpoint.query.filter_by(
            analysis_version_id=version_id
        ).order_by(MCMCCheckpoint.checkpoint_at.desc()).all()

        return {
            'version_id': version_id,
            'total_checkpoints': len(checkpoints),
            'latest': {
                'id': checkpoints[0].id,
                'draw_idx': checkpoints[0].draw_idx,
                'total_draws': checkpoints[0].total_draws,
                'status': checkpoints[0].status.value if checkpoints[0].status else None,
                'is_final': checkpoints[0].is_final,
                'checkpoint_at': checkpoints[0].checkpoint_at.isoformat(),
                'is_resumable': checkpoints[0].is_resumable
            } if checkpoints else None,
            'has_error': any(c.status == CheckpointStatus.ERROR for c in checkpoints),
            'error_message': next(
                (c.error_message for c in checkpoints if c.status == CheckpointStatus.ERROR),
                None
            )
        }
