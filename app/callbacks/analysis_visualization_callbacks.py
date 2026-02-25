"""Callbacks for analysis visualization (tables, charts, diagnostics)."""
from dash import Input, Output, State, html
import dash_mantine_components as dmc
import plotly.graph_objects as go

from app.theme import apply_plotly_theme
from app.layouts.analysis_results import (
    create_posterior_table,
    create_frequentist_table,
    create_comparison_table,
    create_method_info_panel,
    create_probability_display,
    create_variance_pie_chart,
    create_diagnostics_panel,
    create_correlations_panel,
    create_empty_results_message,
    create_assumption_tests_display,
    create_effect_size_display,
    create_corrected_pvalues_table,
    create_qq_plot_for_residuals,
    create_diagnostics_warnings_panel,
)
from app.callbacks.analysis_utils import _extract_tier_info, dmc_text_dimmed


def register_analysis_visualization_callbacks(app):
    """Register analysis visualization callbacks."""

    @app.callback(
        Output("analysis-method-select", "data"),
        Output("analysis-method-select", "value"),
        Input("analysis-results-store", "data"),
        State("analysis-method-select", "value"),
    )
    def update_method_options(data, current_method):
        """Show Frequentist/Compare options based on available results."""
        bayesian_only = [
            {"value": "bayesian", "label": "Bayesian"},
        ]
        all_methods = [
            {"value": "bayesian", "label": "Bayesian"},
            {"value": "frequentist", "label": "Frequentist"},
            {"value": "comparison", "label": "Compare"},
        ]

        if not data:
            return all_methods, current_method or "bayesian"

        tier_info = _extract_tier_info(data.get("model_tier"))
        has_freq = data.get("has_frequentist", False)
        has_bayesian = len(data.get("posteriors", [])) > 0

        if tier_info["has_tier_3"] or has_freq:
            # Default to frequentist if Bayesian results are empty
            default = current_method or ("frequentist" if has_freq and not has_bayesian else "bayesian")
            return all_methods, default

        # No tier 3 and no frequentist results: only show Bayesian
        return bayesian_only, "bayesian"

    @app.callback(
        Output("analysis-posterior-table", "children"),
        Output("analysis-table-title", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-parameter-select", "value"),
        Input("analysis-construct-filter", "value"),
        Input("analysis-method-select", "value"),
    )
    def update_posterior_table(data, selected_param, construct_filter, method):
        """Update the results summary table based on selected method."""
        if not data:
            return create_empty_results_message(), "Results"

        method = method or "bayesian"

        # Guard: comparison needs Tier 3 or frequentist results; frequentist shown when results exist
        tier_info = _extract_tier_info(data.get("model_tier"))
        has_freq = data.get("has_frequentist", False)
        if method == "comparison" and not tier_info["has_tier_3"] and not has_freq:
            method = "bayesian"
        elif method == "frequentist" and not has_freq:
            method = "bayesian"

        if method == "bayesian":
            posteriors = data.get("posteriors", [])

            # Filter by parameter
            filtered = [p for p in posteriors if p.get("parameter") == selected_param]

            # Filter by construct if specified
            if construct_filter:
                filtered = [
                    p for p in filtered
                    if p.get("construct_id") is not None and str(p.get("construct_id")) == construct_filter
                ]

            return create_posterior_table(filtered, selected_param), "Posterior Summaries"

        elif method == "frequentist":
            frequentist = data.get("frequentist", [])
            freq_warnings = data.get("frequentist_warnings", [])

            if not frequentist:
                return dmc.Text(
                    "No frequentist results available. Frequentist analysis may have failed or was not run.",
                    c="dimmed",
                    ta="center",
                ), "Frequentist Estimates"

            # Filter by parameter
            filtered = [p for p in frequentist if p.get("parameter") == selected_param]

            # Filter by construct if specified
            if construct_filter:
                filtered = [p for p in filtered if str(p.get("construct_id")) == construct_filter]

            return create_frequentist_table(filtered, selected_param, warnings=freq_warnings), "Frequentist Estimates"

        elif method == "comparison":
            posteriors = data.get("posteriors", [])
            frequentist = data.get("frequentist", [])

            # Filter by parameter
            bayes_filtered = [p for p in posteriors if p.get("parameter") == selected_param]
            freq_filtered = [p for p in frequentist if p.get("parameter") == selected_param]

            # Filter by construct if specified
            if construct_filter:
                bayes_filtered = [p for p in bayes_filtered if str(p.get("construct_id")) == construct_filter]
                freq_filtered = [p for p in freq_filtered if str(p.get("construct_id")) == construct_filter]

            return create_comparison_table(bayes_filtered, freq_filtered, selected_param), "Method Comparison"

        return create_empty_results_message(), "Results"

    @app.callback(
        Output("analysis-method-info-panel", "children"),
        Input("analysis-method-select", "value"),
        Input("analysis-results-store", "data"),
    )
    def update_method_info_panel(method, data):
        """Update the method info panel with guidelines and warnings."""
        method = method or "bayesian"
        has_frequentist = data.get("has_frequentist", False) if data else False
        freq_warnings = data.get("frequentist_warnings", []) if data else []

        return create_method_info_panel(method, has_frequentist, freq_warnings)

    @app.callback(
        Output("analysis-probability-panel", "style"),
        Input("analysis-method-select", "value"),
    )
    def toggle_probability_panel(method):
        """Hide probability panel for non-Bayesian methods."""
        if method == "bayesian":
            return {"display": "block"}
        return {"display": "none"}

    @app.callback(
        Output("analysis-probability-display", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-threshold-input", "value"),
        Input("analysis-construct-filter", "value"),
        Input("analysis-parameter-select", "value"),
    )
    def update_probability_display(data, threshold, construct_filter, selected_param):
        """Update probability display for selected construct."""
        import numpy as np

        if not data or not construct_filter:
            return dmc_text_dimmed("Select a construct to view probabilities")

        # Ensure threshold is a float (user enters FC like 1.5, we convert to log)
        try:
            threshold_fc = float(threshold) if threshold is not None else 1.5
            # Convert FC threshold to log space for comparison
            threshold_log = np.log(threshold_fc) if threshold_fc > 0 else 0.405
        except (ValueError, TypeError):
            threshold_fc = 1.5
            threshold_log = 0.405  # ln(1.5)

        posteriors = data.get("posteriors", [])

        # Find selected construct and parameter
        for p in posteriors:
            if (str(p.get("construct_id")) == construct_filter and
                p.get("parameter") == selected_param):

                # Compute probability dynamically from samples if available
                samples = p.get("samples")
                if samples and len(samples) > 0:
                    samples_arr = np.array(samples)
                    prob_meaningful = float(np.mean(np.abs(samples_arr) > threshold_log))
                else:
                    # Fall back to stored value
                    prob_meaningful = p.get("prob_meaningful", 0)

                return create_probability_display(
                    construct_name=p.get("construct_name", "Unknown"),
                    prob_direction=p.get("prob_positive", 0.5),
                    prob_meaningful=prob_meaningful,
                    threshold=threshold_fc,
                )

        return dmc_text_dimmed("No data for selected construct")

    @app.callback(
        Output("analysis-variance-pie", "figure"),
        Input("analysis-results-store", "data"),
        Input("analysis-parameter-select", "value"),
        Input("color-scheme-store", "data"),
    )
    def update_variance_pie(data, selected_param, scheme):
        """Update variance decomposition pie chart."""
        dark_mode = (scheme == "dark")
        if not data:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        var_comp = data.get("variance_components", {})
        if not var_comp:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        fig = create_variance_pie_chart(
            var_session=var_comp.get("var_session", 0),
            var_plate=var_comp.get("var_plate", 0),
            var_residual=var_comp.get("var_residual", 0),
            dark_mode=dark_mode,
        )
        return fig

    @app.callback(
        Output("analysis-diagnostics-panel", "children"),
        Output("analysis-diagnostics-title", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-method-select", "value"),
    )
    def update_diagnostics(data, method):
        """Update diagnostics panel based on selected method."""
        method = method or "bayesian"

        if not data:
            return dmc_text_dimmed("No diagnostics available"), "Diagnostics"

        if method == "bayesian":
            diag = data.get("diagnostics", {})
            return create_diagnostics_panel(
                n_chains=diag.get("n_chains", 4),
                n_draws=diag.get("n_draws", 2000),
                divergent_count=diag.get("divergent_count", 0),
                duration_seconds=diag.get("duration_seconds", 0),
                warnings=diag.get("warnings", []),
            ), "MCMC Diagnostics"

        elif method == "frequentist":
            # Frequentist diagnostics are simpler - show convergence info
            freq_warnings = data.get("frequentist_warnings", [])
            if freq_warnings:
                return dmc.Stack([
                    dmc.Alert(
                        title="Convergence Issues",
                        color="yellow",
                        children=dmc.List([
                            dmc.ListItem(dmc.Text(w, size="xs")) for w in freq_warnings[:5]
                        ], size="sm"),
                    ),
                    dmc.Text(
                        "These warnings typically indicate near-zero variance components or boundary estimates.",
                        size="xs",
                        c="dimmed",
                    ),
                ], gap="sm"), "Frequentist Diagnostics"
            else:
                return dmc.Stack([
                    dmc.Badge("Converged", color="green", size="lg"),
                    dmc.Text(
                        "REML optimization completed without convergence warnings.",
                        size="sm",
                        c="dimmed",
                    ),
                ], gap="sm"), "Frequentist Diagnostics"

        elif method == "comparison":
            # Show summary of both methods' diagnostics
            diag = data.get("diagnostics", {})
            freq_warnings = data.get("frequentist_warnings", [])
            has_freq = data.get("has_frequentist", False)

            bayes_status = dmc.Badge(
                "OK" if diag.get("divergent_count", 0) == 0 else f"{diag.get('divergent_count')} divergent",
                color="green" if diag.get("divergent_count", 0) == 0 else "red",
                size="sm",
            )

            freq_status = dmc.Badge(
                "Warnings" if freq_warnings else ("OK" if has_freq else "Not Run"),
                color="yellow" if freq_warnings else ("green" if has_freq else "gray"),
                size="sm",
            )

            return dmc.Stack([
                dmc.Group([
                    dmc.Text("Bayesian:", size="sm", fw=500),
                    bayes_status,
                ], gap="xs"),
                dmc.Group([
                    dmc.Text("Frequentist:", size="sm", fw=500),
                    freq_status,
                ], gap="xs"),
            ], gap="sm"), "Convergence Summary"

        return dmc_text_dimmed("No diagnostics available"), "Diagnostics"

    # =========================================================================
    # Statistical Diagnostics Callbacks (PRD F14.1-F14.6, T8.12-T8.14)
    # =========================================================================

    @app.callback(
        Output("analysis-assumption-tests", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-diagnostics-family-select", "value"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_assumption_tests(data, selected_family, project_id):
        """Run and display assumption tests (Shapiro-Wilk, Levene)."""
        if not data or not project_id:
            return dmc.Text("Run an analysis to view assumption tests", c="dimmed", size="sm")

        try:
            from app.services.statistics_service import StatisticsService

            version_id = data.get("version_id")
            if not version_id:
                return dmc.Text("No analysis version available", c="dimmed", size="sm")

            result = StatisticsService.run_assumption_checks(
                version_id, family=selected_family,
            )

            if not result.diagnostics:
                if "insufficient_data" in result.recommendations:
                    return dmc.Text(
                        "Insufficient data for assumption tests (need at least 3 fitted wells)",
                        c="dimmed", size="sm",
                    )
                return dmc.Text("Could not compute assumption tests", c="dimmed", size="sm")

            norm = result.diagnostics.normality
            # Levene test is only meaningful with 2+ construct families
            homo = result.diagnostics.homoscedasticity if result.groups_checked >= 2 else None

            return create_assumption_tests_display(
                normality_stat=norm.statistic if norm else 0,
                normality_p=norm.p_value if norm else 1.0,
                normality_pass=result.normality_passed,
                homoscedasticity_stat=homo.statistic if homo else None,
                homoscedasticity_p=homo.p_value if homo else None,
                homoscedasticity_pass=result.homoscedasticity_passed if homo else None,
            )

        except Exception:
            import traceback
            traceback.print_exc()
            return dmc.Text("Error computing assumption tests", c="red", size="sm")

    @app.callback(
        Output("analysis-qq-plot", "figure"),
        Output("analysis-qq-title", "children"),
        Output("analysis-qq-description", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-diagnostics-family-select", "value"),
        State("analysis-project-store", "data"),
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def update_qq_plot(data, selected_family, project_id, scheme):
        """Generate Q-Q plot for model residuals."""
        dark_mode = (scheme == "dark")
        default_title = "Q-Q Plot"
        default_desc = dmc.Text(
            "Checks whether the hierarchical model's normality "
            "assumption holds. Points following the diagonal line "
            "indicate the data is consistent with a normal distribution.",
            size="xs", c="dimmed",
        )

        empty = go.Figure()
        empty.add_annotation(
            text="Run an analysis to view Q-Q plot",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color="gray"),
        )
        empty.update_layout(
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            height=280, margin=dict(l=20, r=20, t=20, b=20),
        )
        apply_plotly_theme(empty, dark_mode=dark_mode)

        if not data or not project_id:
            return empty, default_title, default_desc

        try:
            from app.services.statistics_service import StatisticsService

            # Prefer stored model residuals; fall back to raw log fold changes
            version_id = data.get("version_id")
            residuals = None
            using_model_residuals = False
            if version_id:
                residuals = StatisticsService.get_model_residuals(
                    version_id, family=selected_family,
                )
                if residuals is not None and len(residuals) >= 3:
                    using_model_residuals = True
            if not using_model_residuals:
                residuals = StatisticsService.get_log_fold_changes(
                    project_id, family=selected_family,
                )

            if residuals is None or len(residuals) < 3:
                empty.layout.annotations[0].text = "Insufficient data for Q-Q plot"
                return empty, default_title, default_desc

            n = len(residuals)

            if using_model_residuals:
                title = "Model Residual Q-Q Plot"
                y_label = "Model Residuals (observed \u2212 predicted)"
                trace_name = "Residuals"
                description = dmc.Text([
                    dmc.Text(
                        "Plots the hierarchical model's residuals "
                        "(observed log FC minus predicted) against a normal "
                        "distribution. ",
                        size="xs", c="dimmed", span=True,
                    ),
                    dmc.Text(
                        "Points close to the diagonal mean the normality "
                        "assumption is satisfied; systematic curves indicate "
                        "skewness or heavy tails.",
                        size="xs", c="dimmed", span=True,
                    ),
                    dmc.Text(
                        f"  n = {n} observations.",
                        size="xs", c="dimmed", span=True, fs="italic",
                    ),
                ])
            else:
                title = "Log Fold-Change Q-Q Plot"
                y_label = "log\u2082(FC) Quantiles"
                trace_name = "log\u2082(FC)"
                description = dmc.Text([
                    dmc.Text(
                        "Plots raw log\u2082 fold-change values against a normal "
                        "distribution. ",
                        size="xs", c="dimmed", span=True,
                    ),
                    dmc.Text(
                        "Re-run the analysis to generate true model residuals "
                        "for a more accurate normality check.",
                        size="xs", c="yellow.8", span=True, fs="italic",
                    ),
                    dmc.Text(
                        f"  n = {n} observations.",
                        size="xs", c="dimmed", span=True, fs="italic",
                    ),
                ])

            fig = create_qq_plot_for_residuals(
                residuals=residuals.tolist(),
                title=title,
                y_label=y_label,
                trace_name=trace_name,
                dark_mode=dark_mode,
            )

            family_suffix = f" \u2014 {selected_family}" if selected_family else " \u2014 All Families (pooled)"
            residual_type = "Model Residuals" if using_model_residuals else "Log Fold-Changes (fallback)"
            panel_title = f"Q-Q Plot \u2014 {residual_type}{family_suffix}"

            return fig, panel_title, description

        except Exception:
            import traceback
            traceback.print_exc()
            return empty, default_title, default_desc

    @app.callback(
        Output("analysis-effect-sizes", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-method-select", "value"),
        Input("analysis-diagnostics-family-select", "value"),
        prevent_initial_call=True,
    )
    def update_effect_sizes(data, method, selected_family):
        """Compute and display Cohen's d effect sizes from analysis results."""
        if not data:
            return dmc.Text("Run an analysis to view effect sizes", c="dimmed", size="sm")

        method = method or "bayesian"

        try:
            import numpy as np

            # Choose the right result set based on method
            if method == "frequentist":
                results = data.get("frequentist", [])
            else:
                results = data.get("posteriors", [])

            # Filter by family if selected
            if selected_family:
                results = [r for r in results if r.get("family") == selected_family]

            if not results:
                return dmc.Text("No results available for effect size computation", c="dimmed", size="sm")

            # Compute Cohen's d per result for log_fc_fmax
            # Use a list to preserve all entries (e.g., different ligand conditions)
            effect_list = []
            var_residual = data.get("variance_components", {}).get("var_residual")

            for r in results:
                if r.get("parameter") != "log_fc_fmax":
                    continue
                name = r.get("construct_name", "Unknown")
                ligand = r.get("ligand_condition")
                label = f"{name} ({ligand})" if ligand else name
                mean = r.get("mean", 0)
                std = r.get("std", 0)

                if std and std > 0:
                    # Cohen's d: effect relative to residual SD if available,
                    # otherwise use posterior SD as denominator
                    if var_residual and var_residual > 0:
                        d = abs(mean) / np.sqrt(var_residual)
                    else:
                        d = abs(mean) / std

                    # Categorize
                    if abs(d) < 0.2:
                        category = "negligible"
                    elif abs(d) < 0.5:
                        category = "small"
                    elif abs(d) < 0.8:
                        category = "medium"
                    else:
                        category = "large"

                    effect_list.append({
                        "comparison": label,
                        "cohens_d": float(d),
                        "category": category,
                        "mean_diff": float(mean),
                    })

            if not effect_list:
                return dmc.Text("No fold change data available for effect sizes", c="dimmed", size="sm")

            # Sort by effect size descending
            sorted_effects = sorted(
                effect_list,
                key=lambda x: abs(x["cohens_d"]),
                reverse=True,
            )

            return create_effect_size_display(sorted_effects)

        except Exception:
            import traceback
            traceback.print_exc()
            return dmc.Text("Error computing effect sizes", c="red", size="sm")

    @app.callback(
        Output("analysis-corrected-pvalues", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-correction-method", "value"),
        Input("analysis-method-select", "value"),
        Input("analysis-diagnostics-family-select", "value"),
        prevent_initial_call=True,
    )
    def update_corrected_pvalues(data, correction_method, analysis_method, selected_family):
        """Apply multiple comparison corrections to p-values."""
        if not data:
            return dmc.Text(
                "Run an analysis to view corrected p-values", c="dimmed", size="sm",
            )

        correction_method = correction_method or "fdr"
        analysis_method = analysis_method or "bayesian"

        try:
            import numpy as np
            from scipy import stats as scipy_stats
            from app.services.statistics_service import StatisticsService

            # Choose the right result set
            if analysis_method == "frequentist":
                results = data.get("frequentist", [])
            else:
                results = data.get("posteriors", [])

            # Filter by family if selected
            if selected_family:
                results = [r for r in results if r.get("family") == selected_family]

            if not results:
                return dmc.Text("No results available", c="dimmed", size="sm")

            # Extract p-values per construct for log_fc_fmax
            names = []
            p_values = []

            for r in results:
                if r.get("parameter") != "log_fc_fmax":
                    continue

                name = r.get("construct_name", "Unknown")
                ligand = r.get("ligand_condition")
                label = f"{name} ({ligand})" if ligand else name
                mean = r.get("mean", 0)
                std = r.get("std", 0)
                prob_pos = r.get("prob_positive")

                # Derive two-sided p-value
                if analysis_method == "bayesian" and prob_pos is not None:
                    # Bayesian: P(no effect) ~ 2 * min(P(>0), P(<0))
                    p = 2.0 * min(prob_pos, 1.0 - prob_pos)
                elif std and std > 0:
                    # Frequentist / fallback: z-test
                    z = abs(mean / std)
                    p = 2.0 * (1.0 - scipy_stats.norm.cdf(z))
                else:
                    p = 1.0

                p = min(max(p, 1e-16), 1.0)
                names.append(label)
                p_values.append(p)

            if not p_values:
                return dmc.Text("No p-value data available", c="dimmed", size="sm")

            # Apply correction (or none)
            if correction_method == "none":
                adjusted = p_values
                significant = [p < 0.05 for p in p_values]
            else:
                mc_result = StatisticsService.get_multiple_comparison_result(
                    p_values, method=correction_method, alpha=0.05,
                )
                adjusted = mc_result.adjusted_p_values
                significant = mc_result.significant

            # Build comparison list for display
            comparisons = []
            for i, name in enumerate(names):
                comparisons.append({
                    "name": name,
                    "p_value": p_values[i],
                    "adjusted_p": adjusted[i],
                    "significant": significant[i],
                })

            # Sort by adjusted p-value
            comparisons.sort(key=lambda x: x["adjusted_p"])

            return create_corrected_pvalues_table(comparisons, method=correction_method)

        except ImportError:
            # scipy not available - fall back to simpler approach
            return dmc.Text(
                "scipy required for p-value computation", c="dimmed", size="sm",
            )
        except Exception:
            import traceback
            traceback.print_exc()
            return dmc.Text("Error computing corrected p-values", c="red", size="sm")

    @app.callback(
        Output("analysis-diagnostics-warnings", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-correction-method", "value"),
        Input("analysis-diagnostics-family-select", "value"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_diagnostics_warnings(data, correction_method, selected_family, project_id):
        """Generate dynamic warnings based on all diagnostic indicators."""
        if not data or not project_id:
            return html.Div()

        try:
            import numpy as np

            warnings = []

            # Filter posteriors and frequentist results by family if selected
            all_posteriors = data.get("posteriors", [])
            all_freq_results = data.get("frequentist", [])
            if selected_family:
                posteriors = [p for p in all_posteriors if p.get("family") == selected_family]
                freq_results_filtered = [f for f in all_freq_results if f.get("family") == selected_family]
            else:
                posteriors = all_posteriors
                freq_results_filtered = all_freq_results

            # -----------------------------------------------------------
            # 1. MCMC convergence issues (Bayesian)
            # -----------------------------------------------------------
            diag = data.get("diagnostics", {})
            divergent = diag.get("divergent_count", 0)
            if divergent > 0:
                pct = ""
                n_draws = diag.get("n_draws", 0)
                n_chains = diag.get("n_chains", 1)
                total = n_draws * n_chains
                if total > 0:
                    pct = f" ({100 * divergent / total:.1f}% of samples)"
                warnings.append({
                    "severity": "critical" if divergent > 10 else "warning",
                    "title": f"{divergent} Divergent Transitions{pct}",
                    "message": (
                        "The MCMC sampler encountered divergent transitions, which means "
                        "parts of the posterior distribution could not be explored reliably. "
                        "Posterior estimates for some constructs may be biased."
                    ),
                    "guidance": (
                        "Increase the target_accept parameter (e.g., 0.95 or 0.99) to use "
                        "a smaller step size, or increase the number of tuning steps. If "
                        "divergences persist, the model may be misspecified for this dataset."
                    ),
                })

            # -----------------------------------------------------------
            # 2. R-hat convergence checks
            # -----------------------------------------------------------
            poor_rhat = []
            for p in posteriors:
                rhat = p.get("r_hat")
                if rhat is not None and rhat > 1.05:
                    poor_rhat.append((p.get("construct_name", "?"), p.get("parameter", "?"), rhat))

            if poor_rhat:
                names = ", ".join(f"{n} ({par}): {rh:.3f}" for n, par, rh in poor_rhat[:5])
                extra = f" and {len(poor_rhat) - 5} more" if len(poor_rhat) > 5 else ""
                warnings.append({
                    "severity": "critical" if any(rh > 1.10 for _, _, rh in poor_rhat) else "warning",
                    "title": f"R-hat > 1.05 for {len(poor_rhat)} Parameter(s)",
                    "message": (
                        f"The following parameters have not converged (R-hat should be < 1.01): "
                        f"{names}{extra}. Chains have not mixed well, so posterior summaries "
                        f"may not represent the true distribution."
                    ),
                    "guidance": (
                        "Run the sampler with more draws (e.g., 4000-8000) or more chains. "
                        "Persistent high R-hat values suggest the model is struggling with "
                        "identifiability — consider whether all variance components are "
                        "estimable given the experimental design."
                    ),
                })

            # -----------------------------------------------------------
            # 3. Low effective sample size (ESS)
            # -----------------------------------------------------------
            low_ess = []
            for p in posteriors:
                ess_bulk = p.get("ess_bulk")
                ess_tail = p.get("ess_tail")
                min_ess = min(
                    ess_bulk if ess_bulk is not None else float("inf"),
                    ess_tail if ess_tail is not None else float("inf"),
                )
                if min_ess < 400 and min_ess != float("inf"):
                    low_ess.append((p.get("construct_name", "?"), p.get("parameter", "?"), min_ess))

            if low_ess:
                names = ", ".join(f"{n} ({par}): {ess:.0f}" for n, par, ess in low_ess[:5])
                extra = f" and {len(low_ess) - 5} more" if len(low_ess) > 5 else ""
                warnings.append({
                    "severity": "warning",
                    "title": f"Low Effective Sample Size for {len(low_ess)} Parameter(s)",
                    "message": (
                        f"Effective sample size (ESS) is below 400 for: {names}{extra}. "
                        f"Low ESS means MCMC estimates of means and credible intervals "
                        f"are imprecise; tail ESS below 400 specifically degrades "
                        f"95% CI reliability."
                    ),
                    "guidance": (
                        "Increase the number of draws or tuning steps to improve ESS. "
                        "If ESS remains low after longer runs, consider reparameterizing "
                        "the model (e.g., non-centered parameterization for variance "
                        "components)."
                    ),
                })

            # -----------------------------------------------------------
            # 4. Assumption test failures
            # -----------------------------------------------------------
            try:
                from app.services.statistics_service import StatisticsService

                version_id = data.get("version_id")
                if version_id:
                    result = StatisticsService.run_assumption_checks(
                        version_id, family=selected_family,
                    )

                    if result.diagnostics and not result.normality_passed:
                        norm = result.diagnostics.normality
                        p_str = f"p = {norm.p_value:.4f}" if norm else ""
                        warnings.append({
                            "severity": "warning",
                            "title": f"Non-Normal Residuals (Shapiro-Wilk {p_str})",
                            "message": (
                                "The Shapiro-Wilk test rejected the null hypothesis of "
                                "normally distributed residuals. This can inflate Type I "
                                "error rates for frequentist confidence intervals and "
                                "p-values. Bayesian credible intervals are more robust "
                                "but may still be affected if the departure is severe."
                            ),
                            "guidance": (
                                "Check the Q-Q plot: mild departures in the tails are "
                                "common and usually tolerable with n > 30. The analysis "
                                "already uses log-transformed fold changes, so a further "
                                "log transform is not appropriate. If the departure is "
                                "severe (S-shaped or multi-modal Q-Q plot), consider "
                                "removing outlier wells or flagging them in QC."
                            ),
                        })

                    if result.diagnostics and not result.homoscedasticity_passed and result.groups_checked >= 2:
                        homo = result.diagnostics.homoscedasticity
                        p_str = f"p = {homo.p_value:.4f}" if homo else ""

                        if selected_family:
                            # Per-family view: Levene across constructs within this family
                            # This IS relevant — the family's model assumes equal residual
                            # variance across its constructs.
                            warnings.append({
                                "severity": "warning",
                                "title": f"Heteroscedastic Residuals (Levene {p_str})",
                                "message": (
                                    f"Variance differs significantly across constructs "
                                    f"within {selected_family}. The hierarchical model "
                                    f"for this family assumes a single residual variance "
                                    f"shared by all its constructs; this violation may "
                                    f"cause standard errors to be too narrow for "
                                    f"high-variance constructs and too wide for "
                                    f"low-variance ones."
                                ),
                                "guidance": (
                                    "Check whether specific constructs have fewer "
                                    "replicates or noisier measurements. Adding more "
                                    "replicates for the noisy constructs will help "
                                    "stabilize the shared variance estimate."
                                ),
                            })
                        else:
                            # Pooled view: Levene across families — informational only
                            # because each family already has its own model with
                            # independent variance components.
                            warnings.append({
                                "severity": "info",
                                "title": f"Cross-Family Variance Differs (Levene {p_str})",
                                "message": (
                                    "Residual variance differs significantly across "
                                    "construct families. Because each family is analyzed "
                                    "with its own hierarchical model (independent "
                                    "variance components), this does not affect the "
                                    "validity of any individual family's estimates."
                                ),
                                "guidance": (
                                    "This is expected when families have different numbers "
                                    "of replicates or inherently different signal-to-noise "
                                    "ratios. Select a specific family above to check "
                                    "within-family homoscedasticity, which is the assumption "
                                    "that matters for each model."
                                ),
                            })
            except Exception:
                import traceback
                traceback.print_exc()

            # -----------------------------------------------------------
            # 5. Frequentist model warnings (only relevant for Tier 3)
            # -----------------------------------------------------------
            freq_warnings = data.get("frequentist_warnings", [])
            # Filter frequentist warnings by family prefix (e.g. "[Tbox1] ...")
            if selected_family:
                freq_warnings = [
                    w for w in freq_warnings
                    if w.startswith(f"[{selected_family}]")
                ]
            diag_tier_info = _extract_tier_info(data.get("model_tier"))
            is_tier_3 = diag_tier_info["has_tier_3"]
            if freq_warnings and is_tier_3:
                has_unrealistic = any("Unrealistic" in w for w in freq_warnings)
                warnings.append({
                    "severity": "critical" if has_unrealistic else "warning",
                    "title": f"Frequentist Model Issues ({len(freq_warnings)})",
                    "message": (
                        "The REML mixed-effects model reported the following: "
                        + "; ".join(freq_warnings[:3])
                        + ("..." if len(freq_warnings) > 3 else "")
                        + (" Unrealistically wide confidence intervals suggest the "
                           "frequentist model failed to converge properly."
                           if has_unrealistic else "")
                    ),
                    "guidance": (
                        "Frequentist mixed models can fail when variance components "
                        "are near zero or the design is unbalanced. The Bayesian "
                        "results are generally more reliable in these cases. If you "
                        "need frequentist estimates, ensure each construct has at "
                        "least 3 replicates across 2+ plates." if has_unrealistic else
                        "These warnings typically indicate near-zero variance "
                        "components or boundary estimates. Verify that the "
                        "experimental design has enough sessions and plates to "
                        "support the random-effects structure."
                    ),
                })

            # -----------------------------------------------------------
            # 6. Multiple comparisons without correction
            # -----------------------------------------------------------
            correction_method = correction_method or "fdr"
            n_comparisons = sum(
                1 for p in posteriors if p.get("parameter") == "log_fc_fmax"
            )
            if correction_method == "none" and n_comparisons > 3:
                warnings.append({
                    "severity": "warning",
                    "title": f"No Multiple-Testing Correction ({n_comparisons} Comparisons)",
                    "message": (
                        f"You are testing {n_comparisons} constructs without adjusting "
                        f"for multiple comparisons. With {n_comparisons} tests at "
                        f"alpha = 0.05, the family-wise error rate is "
                        f"~{min(100, 100 * (1 - 0.95 ** n_comparisons)):.0f}%, "
                        f"meaning false positives are likely."
                    ),
                    "guidance": (
                        "Select a correction method above. Benjamini-Hochberg (FDR) "
                        "is recommended for discovery-oriented experiments — it controls "
                        "the expected proportion of false discoveries rather than the "
                        "probability of any false positive. Bonferroni is more "
                        "conservative and appropriate when every comparison must be "
                        "individually reliable."
                    ),
                })

            # -----------------------------------------------------------
            # 7. All negligible effect sizes
            # -----------------------------------------------------------
            fmax_results = [p for p in posteriors if p.get("parameter") == "log_fc_fmax"]
            if fmax_results:
                var_residual = data.get("variance_components", {}).get("var_residual")
                negligible_count = 0
                for r in fmax_results:
                    mean = r.get("mean", 0)
                    std = r.get("std", 0)
                    if std and std > 0:
                        if var_residual and var_residual > 0:
                            d = abs(mean) / np.sqrt(var_residual)
                        else:
                            d = abs(mean) / std
                        if d < 0.2:
                            negligible_count += 1

                if negligible_count == len(fmax_results) and len(fmax_results) > 1:
                    warnings.append({
                        "severity": "info",
                        "title": "All Effect Sizes Are Negligible",
                        "message": (
                            f"All {len(fmax_results)} constructs show negligible "
                            f"Cohen's d (< 0.2) for F_max fold change. None of the "
                            f"tested constructs produce a meaningfully different "
                            f"fluorescence intensity compared to the control."
                        ),
                        "guidance": (
                            "This may indicate that the constructs genuinely lack "
                            "differential activity, or that the assay's dynamic range "
                            "is insufficient to detect the expected effect. Consider "
                            "optimizing reaction conditions (e.g., longer incubation, "
                            "higher template concentration) or using a more sensitive "
                            "reporter system."
                        ),
                    })

            # -----------------------------------------------------------
            # 8. Dominant variance component
            # -----------------------------------------------------------
            var_comp = data.get("variance_components", {})
            var_session = var_comp.get("var_session", 0) or 0
            var_plate = var_comp.get("var_plate", 0) or 0
            var_residual_val = var_comp.get("var_residual", 0) or 0
            total_var = var_session + var_plate + var_residual_val

            if total_var > 0:
                session_pct = var_session / total_var
                plate_pct = var_plate / total_var

                if session_pct > 0.5:
                    warnings.append({
                        "severity": "warning",
                        "title": f"Session-to-Session Variance Dominates ({session_pct:.0%})",
                        "message": (
                            f"Over half of total variability ({session_pct:.0%}) comes "
                            f"from differences between experimental sessions rather "
                            f"than construct effects or plate-level noise. This means "
                            f"results are highly sensitive to which sessions were run, "
                            f"and adding constructs within existing sessions provides "
                            f"less information than running additional sessions."
                        ),
                        "guidance": (
                            "To improve precision: (1) standardize reagent preparation "
                            "across sessions (same enzyme lot, fresh NTPs), (2) include "
                            "an internal calibration control on every plate, (3) spread "
                            "replicates across more sessions rather than concentrating "
                            "them in fewer sessions."
                        ),
                    })
                elif plate_pct > 0.5:
                    warnings.append({
                        "severity": "info",
                        "title": f"Plate-to-Plate Variance Is Dominant ({plate_pct:.0%})",
                        "message": (
                            f"Plate-level effects account for {plate_pct:.0%} of total "
                            f"variance. This suggests systematic differences between "
                            f"plates within the same session (e.g., edge effects, "
                            f"pipetting order, seal quality)."
                        ),
                        "guidance": (
                            "Consider randomizing well positions across plates, "
                            "using multi-channel pipettes for consistency, and "
                            "including paired controls on each plate to enable "
                            "plate-level normalization."
                        ),
                    })

            # -----------------------------------------------------------
            # 9. Bayesian-Frequentist disagreement (Tier 3 only)
            # -----------------------------------------------------------
            if posteriors and freq_results_filtered and is_tier_3:
                disagreements = []
                freq_by_key = {}
                for f in freq_results_filtered:
                    key = (f.get("construct_name"), f.get("parameter"), f.get("ligand_condition"))
                    freq_by_key[key] = f

                for p in posteriors:
                    key = (p.get("construct_name"), p.get("parameter"), p.get("ligand_condition"))
                    f = freq_by_key.get(key)
                    if not f:
                        continue

                    b_mean = p.get("mean", 0)
                    f_mean = f.get("mean", 0)
                    b_std = p.get("std", 0)

                    if b_std and b_std > 0:
                        diff = abs(b_mean - f_mean) / b_std
                        if diff > 2.0:
                            disagreements.append(
                                (p.get("construct_name", "?"), p.get("parameter", "?"), diff)
                            )

                if disagreements:
                    names = ", ".join(
                        f"{n} ({par})" for n, par, _ in disagreements[:4]
                    )
                    extra = f" and {len(disagreements) - 4} more" if len(disagreements) > 4 else ""
                    warnings.append({
                        "severity": "warning",
                        "title": f"Bayesian/Frequentist Estimates Disagree ({len(disagreements)})",
                        "message": (
                            f"Point estimates differ by more than 2 posterior SDs for: "
                            f"{names}{extra}. This often occurs when the frequentist "
                            f"model hits a boundary condition (e.g., zero variance "
                            f"component) while the Bayesian model uses weakly "
                            f"informative priors that regularize the estimate."
                        ),
                        "guidance": (
                            "When methods disagree, the Bayesian estimates are "
                            "generally more trustworthy because the priors prevent "
                            "degenerate solutions. Verify by checking if the "
                            "frequentist warnings above indicate convergence issues "
                            "for these constructs."
                        ),
                    })

            return create_diagnostics_warnings_panel(warnings)

        except Exception:
            import traceback
            traceback.print_exc()
            return html.Div()

    @app.callback(
        Output("analysis-correlations-panel", "children"),
        Input("analysis-results-store", "data"),
        Input("analysis-construct-filter", "value"),
    )
    def update_correlations(data, construct_filter):
        """Update correlations panel."""
        if not data:
            return dmc_text_dimmed("No correlation data available")

        correlations = data.get("correlations", {})
        if construct_filter and construct_filter in correlations:
            correlations = correlations[construct_filter]

        return create_correlations_panel(correlations)

    @app.callback(
        Output("analysis-forest-plot", "figure"),
        Input("analysis-results-store", "data"),
        Input("analysis-parameter-select", "value"),
        Input("forest-sort-select", "value"),
        Input("forest-group-by-family", "checked"),
        Input("color-scheme-store", "data"),
    )
    def update_forest_plot(data, selected_param, sort_by, group_by_family, scheme):
        """Update the forest plot visualization."""
        import numpy as np
        from app.components.forest_plot import create_forest_plot

        dark_mode = (scheme == "dark")

        if not data:
            fig = go.Figure()
            fig.add_annotation(
                text="Run Bayesian analysis to view forest plot",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray"),
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=300,
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        posteriors = data.get("posteriors", [])

        # Filter by selected parameter
        filtered = [p for p in posteriors if p.get("parameter") == selected_param]

        if not filtered:
            fig = go.Figure()
            fig.add_annotation(
                text="No data for selected parameter",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        # Build construct data for forest plot
        constructs = []
        for p in filtered:
            ligand_condition = p.get("ligand_condition")
            display_name = p.get("construct_name", "Unknown")

            # Suffix name with ligand condition for disambiguation
            if ligand_condition == "+Lig":
                display_name = f"{display_name} (+Lig)"
            elif ligand_condition == "-Lig":
                display_name = f"{display_name} (-Lig)"
            elif ligand_condition == "+Lig/-Lig":
                display_name = f"{display_name} (Lig Effect)"

            construct_data = {
                "name": display_name,
                "mean": p.get("mean", 0),
                "ci_lower": p.get("ci_lower", 0),
                "ci_upper": p.get("ci_upper", 0),
                "vif": 1.0,  # Default VIF for within-project analysis
                "ligand_condition": ligand_condition,
            }

            # Try to get family from construct name or use default
            name = p.get("construct_name", "")
            if "_" in name:
                construct_data["family"] = name.split("_")[0]
            else:
                construct_data["family"] = "Default"

            constructs.append(construct_data)

        # Create forest plot
        group_by = "family" if group_by_family else None

        # Set title based on parameter
        param_titles = {
            "log_fc_fmax": "Fold Change in F_max (log scale)",
            "log_fc_kobs": "Fold Change in k_obs (log scale)",
            "delta_tlag": "Difference in t_lag (minutes)",
        }
        title = param_titles.get(selected_param, selected_param)

        fig = create_forest_plot(
            constructs=constructs,
            sort_by=sort_by or "effect_size",
            group_by=group_by,
            show_reference_line=True,
            show_95_ci=True,
            show_vif_badges=False,  # VIF not relevant for single-project view
            title=title,
            dark_mode=dark_mode,
        )

        return fig
