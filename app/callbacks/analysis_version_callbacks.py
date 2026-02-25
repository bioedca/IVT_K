"""Callbacks for analysis version selection and results loading."""
from dash import Input, Output, State, no_update
import dash_mantine_components as dmc

from app.layouts.analysis_results import (
    create_empty_results_message,
)
from app.callbacks.analysis_utils import _extract_tier_info


def register_analysis_version_callbacks(app):
    """Register analysis version selection and results loading callbacks."""

    @app.callback(
        Output("analysis-version-select", "data"),
        Output("analysis-version-select", "value"),
        Input("analysis-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_analysis_versions(project_id):
        """Load available analysis versions for the project and auto-select most recent."""
        if not project_id:
            return [], None

        try:
            from app.models.analysis_version import AnalysisVersion

            versions = AnalysisVersion.query.filter_by(
                project_id=project_id
            ).order_by(AnalysisVersion.created_at.desc()).all()

            options = [
                {
                    "value": str(v.id),
                    "label": f"{v.name} ({v.created_at.strftime('%Y-%m-%d %H:%M')})"
                }
                for v in versions
            ]

            # Auto-select the most recent version
            selected = str(versions[0].id) if versions else None

            return options, selected
        except Exception:
            return [], None

    @app.callback(
        Output("fitting-model-select-store", "data", allow_duplicate=True),
        Output("analysis-threshold-input", "value"),
        Input("analysis-project-store", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def init_analysis_settings_from_project(project_id):
        """Initialize kinetic model dropdown and FC threshold from project settings."""
        if not project_id:
            return no_update, no_update

        try:
            from app.models.project import Project
            project = Project.query.get(project_id)
            if not project:
                return no_update, no_update

            kinetic_model = project.kinetic_model_type or "delayed_exponential"
            fc_threshold = project.meaningful_fc_threshold or 1.5

            return kinetic_model, fc_threshold
        except Exception:
            return no_update, no_update

    @app.callback(
        Output("analysis-construct-filter", "data"),
        Output("analysis-construct-filter", "value"),
        Input("analysis-results-store", "data"),
        prevent_initial_call=False,
    )
    def load_constructs_from_results(results_data):
        """Load constructs from analysis results for filtering."""
        if not results_data:
            return [], None

        try:
            posteriors = results_data.get("posteriors", [])
            if not posteriors:
                return [], None

            # Get unique constructs from posteriors
            seen = set()
            options = []
            for p in posteriors:
                cid = str(p.get("construct_id"))
                if cid not in seen:
                    seen.add(cid)
                    options.append({
                        "value": cid,
                        "label": p.get("construct_name", f"Construct {cid}")
                    })

            # Sort by label
            options.sort(key=lambda x: x["label"])

            # Auto-select first construct
            selected = options[0]["value"] if options else None

            return options, selected
        except Exception:
            return [], None

    @app.callback(
        Output("analysis-diagnostics-family-select", "data"),
        Output("analysis-diagnostics-family-select", "value"),
        Input("analysis-results-store", "data"),
        prevent_initial_call=True,
    )
    def populate_diagnostics_family_select(results_data):
        """Populate the family selector in the diagnostics section."""
        if not results_data:
            return [], None

        model_tier = results_data.get("model_tier") or {}
        per_family = model_tier.get("per_family")
        if not per_family or not isinstance(per_family, dict):
            return [], None

        options = sorted(
            [{"value": fam, "label": fam} for fam in per_family.keys()],
            key=lambda x: x["label"],
        )
        return options, None  # Default to pooled (None)

    @app.callback(
        Output("analysis-results-store", "data"),
        Output("analysis-status-badge", "children"),
        Output("analysis-status-badge", "color"),
        Output("analysis-scope-badge", "children"),
        Output("analysis-scope-badge", "color"),
        Input("analysis-version-select", "value"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_analysis_results(version_id, project_id):
        """Load analysis results for selected version."""
        if not version_id:
            return None, "No Analysis", "gray", "Unknown", "gray"

        try:
            from app.models.analysis_version import AnalysisVersion, HierarchicalResult, AnalysisStatus
            from app.services.comparison_service import ComparisonService

            version = AnalysisVersion.query.get(int(version_id))
            if not version:
                return None, "Not Found", "red", "Unknown", "gray"

            # Get scope
            scope = ComparisonService.validate_graph_connectivity(project_id)
            scope_colors = {
                "full": "green",
                "within_family_only": "yellow",
                "partial": "yellow",
                "none": "red",
            }
            scope_labels = {
                "full": "Full Analysis",
                "within_family_only": "Within-Family Only",
                "partial": "Partial",
                "none": "No Analysis",
            }

            # Load Bayesian results (posteriors)
            bayesian_results = HierarchicalResult.query.filter_by(
                analysis_version_id=version.id,
                analysis_type="bayesian"
            ).all()

            # Extract tier info (handles per-family and legacy formats)
            tier_info = _extract_tier_info(version.model_tier_metadata)

            # Always load frequentist results — they may exist even when
            # Bayesian analysis failed (e.g. pytensor crash).  The method
            # selector already gates which tabs are shown to the user.
            frequentist_results = HierarchicalResult.query.filter_by(
                analysis_version_id=version.id,
                analysis_type="frequentist"
            ).all()

            if not bayesian_results and not frequentist_results:
                return None, "No Results", "yellow", scope_labels.get(scope.scope, "Unknown"), scope_colors.get(scope.scope, "gray")

            # Format results for storage
            data = {
                "version_id": version.id,
                "version_name": version.name,
                "posteriors": [],  # Bayesian
                "frequentist": [],  # Frequentist
                "has_frequentist": len(frequentist_results) > 0,
                "frequentist_warnings": [],  # Populated from model tier metadata
                "variance_components": {},
                "correlations": {},
                "diagnostics": {
                    "n_chains": version.mcmc_chains or 4,
                    "n_draws": version.mcmc_draws or 2000,
                    "divergent_count": 0,  # Not stored on version directly
                    "duration_seconds": version.duration_seconds or 0,
                    "warnings": [],
                },
                "model_tier": version.model_tier_metadata,
            }

            # Extract frequentist warnings (Tier 3 only)
            if tier_info["has_tier_3"] and tier_info["frequentist_warnings"]:
                data["frequentist_warnings"] = tier_info["frequentist_warnings"]

            # Batch-load all constructs referenced by results (avoid N+1 queries)
            from app.models import Construct
            all_construct_ids = set(
                r.construct_id for r in bayesian_results + frequentist_results
                if r.construct_id is not None
            )
            constructs_by_id = {
                c.id: c
                for c in Construct.query.filter(Construct.id.in_(all_construct_ids)).all()
            } if all_construct_ids else {}

            # Group Bayesian results by construct and parameter
            for result in bayesian_results:
                construct = constructs_by_id.get(result.construct_id)
                data["posteriors"].append({
                    "construct_id": result.construct_id,
                    "construct_name": construct.identifier if construct else f"ID:{result.construct_id}",
                    "family": construct.family if construct else None,
                    "parameter": result.parameter_type,
                    "analysis_type": result.analysis_type,
                    "ligand_condition": result.ligand_condition,
                    "mean": result.mean,
                    "std": result.std,
                    "ci_lower": result.ci_lower,
                    "ci_upper": result.ci_upper,
                    "r_hat": result.r_hat,
                    "ess_bulk": result.ess_bulk,
                    "ess_tail": result.ess_tail,
                    "prob_positive": result.prob_positive,
                    "prob_meaningful": result.prob_meaningful,
                    "var_session": result.var_session,
                    "var_plate": result.var_plate,
                    "var_residual": result.var_residual,
                    "samples": result.posterior_samples,  # For on-demand probability computation
                })

            # Group Frequentist results by construct and parameter
            # Also detect unrealistic results that indicate model failure
            unrealistic_results = []
            for result in frequentist_results:
                construct = constructs_by_id.get(result.construct_id)
                data["frequentist"].append({
                    "construct_id": result.construct_id,
                    "construct_name": construct.identifier if construct else f"ID:{result.construct_id}",
                    "family": construct.family if construct else None,
                    "parameter": result.parameter_type,
                    "analysis_type": result.analysis_type,
                    "ligand_condition": result.ligand_condition,
                    "mean": result.mean,
                    "std": result.std,
                    "ci_lower": result.ci_lower,
                    "ci_upper": result.ci_upper,
                })

                # Detect unrealistic CI widths that indicate model failure
                if result.ci_upper is None or result.ci_lower is None:
                    continue
                ci_width = abs(result.ci_upper - result.ci_lower)
                is_log_param = result.parameter_type in ("log_fc_fmax", "log_fc_kobs")

                # For log FC params, CI width > 10 means range of exp(10) = 22000x - unrealistic
                # For delta_tlag, CI width > 100 minutes is unrealistic
                max_reasonable_width = 10.0 if is_log_param else 100.0

                if ci_width > max_reasonable_width or result.std > 1000:
                    family_prefix = f"[{construct.family}] " if construct and construct.family else ""
                    unrealistic_results.append(
                        f"{family_prefix}{result.parameter_type}: Unrealistic CI width ({ci_width:.1f}) - model likely failed"
                    )

            # Add unrealistic result warnings if no stored warnings exist
            if unrealistic_results and not data["frequentist_warnings"]:
                data["frequentist_warnings"] = unrealistic_results

            # Extract variance components from the first Bayesian result (same for all constructs)
            if bayesian_results and bayesian_results[0].var_residual is not None:
                data["variance_components"] = {
                    "var_session": bayesian_results[0].var_session,
                    "var_plate": bayesian_results[0].var_plate,
                    "var_residual": bayesian_results[0].var_residual,
                }

            # Build status text
            bayes_count = len(bayesian_results)
            freq_count = len(frequentist_results)
            if bayes_count and freq_count:
                status_text = f"{bayes_count} Bayes, {freq_count} Freq"
            elif bayes_count:
                status_text = f"{bayes_count} Bayesian"
            elif freq_count:
                status_text = f"{freq_count} Frequentist"
            else:
                status_text = "No results"

            status_color = "green" if version.status == AnalysisStatus.COMPLETED else (
                "yellow" if version.status == AnalysisStatus.RUNNING else "gray"
            )

            return (
                data,
                status_text,
                status_color,
                scope_labels.get(scope.scope, "Unknown"),
                scope_colors.get(scope.scope, "gray"),
            )

        except Exception as e:
            import traceback
            print(f"Error loading analysis results: {e}")
            traceback.print_exc()
            return None, "Error", "red", "Unknown", "gray"
