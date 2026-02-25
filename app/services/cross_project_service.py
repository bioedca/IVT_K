"""
Cross-project comparison service.

Sprint 8: Cross-Project Features (PRD Section 3.20)

Provides:
- F20.1: Find constructs by identifier across projects
- F20.2: Side-by-side forest plot for same construct from different projects
- F20.3: Overlay posteriors from different projects
- F20.4: Tabular comparison of estimates with CIs

Note: Read-only comparison view. No meta-analysis or data combining.
Projects remain statistically independent.
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from sqlalchemy import func, and_, or_

from app.extensions import db
from app.models import Project, Construct
from app.models.analysis_version import AnalysisVersion, HierarchicalResult, AnalysisStatus
from app.models.experiment import Plate, ExperimentalSession

logger = logging.getLogger(__name__)


@dataclass
class ProjectConstructMatch:
    """A construct match in a specific project."""
    project_id: int
    project_name: str
    construct_id: int
    construct_identifier: str
    family: str
    is_wildtype: bool
    is_unregulated: bool
    plate_count: int
    replicate_count: int
    has_analysis: bool
    latest_analysis_id: Optional[int] = None
    latest_analysis_date: Optional[datetime] = None


@dataclass
class ConstructComparisonData:
    """Comparison data for a construct across projects."""
    construct_identifier: str
    parameter_type: str  # "log_fc_fmax", "log_fc_kobs", "delta_tlag"
    projects: List[Dict[str, Any]] = field(default_factory=list)
    # Each project dict contains:
    # - project_id, project_name
    # - mean, std, ci_lower, ci_upper
    # - prob_positive, prob_meaningful (if Bayesian)
    # - var_session, var_plate, var_residual
    # - plate_count, replicate_count
    # - analysis_date


@dataclass
class CrossProjectSummary:
    """Summary statistics across projects."""
    n_projects: int
    total_plates: int
    total_replicates: int
    mean_estimate: float
    pooled_std: float
    min_estimate: float
    max_estimate: float
    range_estimate: float
    all_positive: bool
    all_meaningful: bool


class CrossProjectComparisonService:
    """
    Service for cross-project comparison features.

    Enables comparison of the same construct across different projects
    for validation and meta-level insights while maintaining project
    independence (no data pooling or meta-analysis).
    """

    @classmethod
    def get_all_construct_identifiers(cls) -> List[str]:
        """
        Get all unique construct identifiers across all projects.

        Returns:
            Sorted list of unique identifiers that appear in at least one project
        """
        identifiers = db.session.query(Construct.identifier).filter(
            Construct.is_deleted == False,
            Construct.is_draft == False
        ).distinct().all()

        return sorted([i[0] for i in identifiers])

    @classmethod
    def get_shared_construct_identifiers(cls, min_projects: int = 2) -> List[Dict[str, Any]]:
        """
        Get construct identifiers that appear in multiple projects.

        Args:
            min_projects: Minimum number of projects required

        Returns:
            List of dicts with identifier and project_count, sorted by count desc
        """
        query = db.session.query(
            Construct.identifier,
            func.count(func.distinct(Construct.project_id)).label("project_count")
        ).join(
            Project, Construct.project_id == Project.id
        ).filter(
            Construct.is_deleted == False,
            Construct.is_draft == False,
            Project.is_deleted == False,
            Project.is_archived == False
        ).group_by(
            Construct.identifier
        ).having(
            func.count(func.distinct(Construct.project_id)) >= min_projects
        ).order_by(
            func.count(func.distinct(Construct.project_id)).desc(),
            Construct.identifier
        )

        results = query.all()
        return [
            {"identifier": r[0], "project_count": r[1]}
            for r in results
        ]

    @classmethod
    def find_matching_constructs(
        cls,
        identifier: str,
        include_archived: bool = False
    ) -> List[ProjectConstructMatch]:
        """
        Find all projects containing a construct with the given identifier.

        Args:
            identifier: The construct identifier to search for
            include_archived: Whether to include archived projects

        Returns:
            List of ProjectConstructMatch objects with project and construct details

        PRD Reference: F20.1 - View constructs by identifier across projects
        """
        # Base query for constructs matching identifier
        query = db.session.query(
            Construct,
            Project
        ).join(
            Project, Construct.project_id == Project.id
        ).filter(
            Construct.identifier == identifier,
            Construct.is_deleted == False,
            Construct.is_draft == False,
            Project.is_deleted == False
        )

        if not include_archived:
            query = query.filter(Project.is_archived == False)

        results = query.all()

        if not results:
            return []

        # Batch load latest analysis versions for all matched projects (avoid N+1)
        project_ids = list(set(project.id for _, project in results))
        from sqlalchemy import func as sa_func
        latest_analysis_subq = (
            db.session.query(
                AnalysisVersion.project_id,
                sa_func.max(AnalysisVersion.id).label("max_id")
            )
            .filter(
                AnalysisVersion.project_id.in_(project_ids),
                AnalysisVersion.status == AnalysisStatus.COMPLETED
            )
            .group_by(AnalysisVersion.project_id)
            .subquery()
        )
        latest_versions = (
            db.session.query(AnalysisVersion)
            .join(latest_analysis_subq, AnalysisVersion.id == latest_analysis_subq.c.max_id)
            .all()
        )
        analysis_by_project = {v.project_id: v for v in latest_versions}

        # Batch load plate/replicate counts for all construct-project pairs
        from app.models.experiment import Well
        count_results_with_proj = (
            db.session.query(
                Well.construct_id,
                ExperimentalSession.project_id,
                func.count(func.distinct(Well.plate_id)).label("plate_count"),
                func.count(Well.id).label("replicate_count")
            )
            .join(Plate, Well.plate_id == Plate.id)
            .join(ExperimentalSession, Plate.session_id == ExperimentalSession.id)
            .filter(
                Well.construct_id.in_([c.id for c, _ in results]),
                ExperimentalSession.project_id.in_(project_ids),
                Well.is_excluded == False
            )
            .group_by(Well.construct_id, ExperimentalSession.project_id)
            .all()
        )
        counts_lookup = {
            (r.construct_id, r.project_id): (r.plate_count, r.replicate_count)
            for r in count_results_with_proj
        }

        matches = []
        for construct, project in results:
            plate_count, replicate_count = counts_lookup.get(
                (construct.id, project.id), (0, 0)
            )

            latest_analysis = analysis_by_project.get(project.id)

            matches.append(ProjectConstructMatch(
                project_id=project.id,
                project_name=project.name,
                construct_id=construct.id,
                construct_identifier=construct.identifier,
                family=construct.family,
                is_wildtype=construct.is_wildtype,
                is_unregulated=construct.is_unregulated,
                plate_count=plate_count,
                replicate_count=replicate_count,
                has_analysis=latest_analysis is not None,
                latest_analysis_id=latest_analysis.id if latest_analysis else None,
                latest_analysis_date=latest_analysis.completed_at if latest_analysis else None
            ))

        # Sort by project name
        matches.sort(key=lambda x: x.project_name)

        return matches

    @classmethod
    def _count_plates_and_replicates(
        cls,
        project_id: int,
        construct_id: int
    ) -> Tuple[int, int]:
        """Count plates and total replicates for a construct in a project."""
        from app.models.experiment import Well

        # Count distinct plates
        plate_count = db.session.query(
            func.count(func.distinct(Plate.id))
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).join(
            Well, Well.plate_id == Plate.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id == construct_id,
            Well.is_excluded == False
        ).scalar() or 0

        # Count total replicates (wells)
        replicate_count = db.session.query(
            func.count(Well.id)
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id == construct_id,
            Well.is_excluded == False
        ).scalar() or 0

        return plate_count, replicate_count

    @classmethod
    def get_comparison_data(
        cls,
        construct_identifier: str,
        project_ids: List[int],
        parameter_type: str = "log_fc_fmax",
        analysis_type: str = "bayesian"
    ) -> ConstructComparisonData:
        """
        Gather analysis results for a construct across specified projects.

        Args:
            construct_identifier: The construct identifier to compare
            project_ids: List of project IDs to include
            parameter_type: Parameter to compare ("log_fc_fmax", "log_fc_kobs", "delta_tlag")
            analysis_type: "bayesian" or "frequentist"

        Returns:
            ConstructComparisonData with results from each project

        PRD Reference: F20.1-F20.4 - Cross-project comparison view
        """
        comparison = ConstructComparisonData(
            construct_identifier=construct_identifier,
            parameter_type=parameter_type,
            projects=[]
        )

        for project_id in project_ids:
            project = Project.query.get(project_id)
            if not project:
                logger.warning(f"Project {project_id} not found, skipping")
                continue

            # Get the construct in this project
            construct = Construct.query.filter(
                Construct.project_id == project_id,
                Construct.identifier == construct_identifier,
                Construct.is_deleted == False
            ).first()

            if not construct:
                logger.warning(
                    f"Construct {construct_identifier} not found in project {project_id}"
                )
                continue

            # Get latest completed analysis
            analysis = AnalysisVersion.query.filter(
                AnalysisVersion.project_id == project_id,
                AnalysisVersion.status == AnalysisStatus.COMPLETED
            ).order_by(
                AnalysisVersion.completed_at.desc()
            ).first()

            if not analysis:
                logger.info(f"No completed analysis for project {project_id}")
                continue

            # Get hierarchical result for this construct and parameter
            result = HierarchicalResult.query.filter(
                HierarchicalResult.analysis_version_id == analysis.id,
                HierarchicalResult.construct_id == construct.id,
                HierarchicalResult.parameter_type == parameter_type,
                HierarchicalResult.analysis_type == analysis_type
            ).first()

            if not result:
                logger.info(
                    f"No {analysis_type} result for {parameter_type} in project {project_id}"
                )
                continue

            # Count plates and replicates
            plate_count, replicate_count = cls._count_plates_and_replicates(
                project_id, construct.id
            )

            # Build project data dict
            project_data = {
                "project_id": project.id,
                "project_name": project.name,
                "construct_id": construct.id,
                "analysis_id": analysis.id,
                "analysis_date": analysis.completed_at.isoformat() if analysis.completed_at else None,
                "plate_count": plate_count,
                "replicate_count": replicate_count,
                # Estimate summaries
                "mean": result.mean,
                "std": result.std,
                "ci_lower": result.ci_lower,
                "ci_upper": result.ci_upper,
                "ci_width": result.ci_width,
                # Bayesian probabilities
                "prob_positive": result.prob_positive,
                "prob_meaningful": result.prob_meaningful,
                # Variance components
                "var_session": result.var_session,
                "var_plate": result.var_plate,
                "var_residual": result.var_residual,
                # Diagnostics
                "n_samples": result.n_samples,
                "r_hat": result.r_hat,
                "ess_bulk": result.ess_bulk,
            }

            comparison.projects.append(project_data)

        return comparison

    @classmethod
    def compute_cross_project_summary(
        cls,
        comparison_data: ConstructComparisonData,
        meaningful_threshold: float = 0.0
    ) -> Optional[CrossProjectSummary]:
        """
        Compute summary statistics across projects.

        Note: This is descriptive only - NOT a meta-analysis.
        Projects remain statistically independent.

        Args:
            comparison_data: The comparison data to summarize
            meaningful_threshold: Log2 threshold for "meaningful" effect (default 0 = any positive)

        Returns:
            CrossProjectSummary or None if insufficient data
        """
        projects = comparison_data.projects
        if len(projects) < 2:
            return None

        means = [p["mean"] for p in projects]
        stds = [p["std"] for p in projects]
        plate_counts = [p["plate_count"] for p in projects]
        replicate_counts = [p["replicate_count"] for p in projects]

        # Simple descriptive statistics (NOT pooled estimates)
        mean_estimate = np.mean(means)
        min_estimate = np.min(means)
        max_estimate = np.max(means)

        # Weighted average of SDs (by sample size) for descriptive purposes
        total_replicates = sum(replicate_counts)
        if total_replicates > 0:
            pooled_std = np.sqrt(
                sum(n * s**2 for n, s in zip(replicate_counts, stds)) / total_replicates
            )
        elif stds:
            pooled_std = np.mean(stds)
        else:
            pooled_std = 0.0

        # Check if all projects show positive/meaningful effect
        all_positive = all(p["mean"] > 0 for p in projects)
        all_meaningful = all(p["mean"] > meaningful_threshold for p in projects)

        return CrossProjectSummary(
            n_projects=len(projects),
            total_plates=sum(plate_counts),
            total_replicates=total_replicates,
            mean_estimate=mean_estimate,
            pooled_std=pooled_std,
            min_estimate=min_estimate,
            max_estimate=max_estimate,
            range_estimate=max_estimate - min_estimate,
            all_positive=all_positive,
            all_meaningful=all_meaningful
        )

    @classmethod
    def generate_comparison_forest_plot(
        cls,
        comparison_data: ConstructComparisonData,
        title: Optional[str] = None,
        show_summary: bool = True,
        height: Optional[int] = None
    ) -> go.Figure:
        """
        Generate a forest plot comparing the same construct across projects.

        Args:
            comparison_data: The comparison data to plot
            title: Optional chart title
            show_summary: Show summary diamond at bottom
            height: Figure height (auto-calculated if None)

        Returns:
            Plotly figure

        PRD Reference: F20.2 - Side-by-side forest plot for same construct
        """
        projects = comparison_data.projects

        if not projects:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for comparison",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray"),
            )
            return fig

        # Sort by mean estimate
        projects = sorted(projects, key=lambda x: x["mean"], reverse=True)

        n_projects = len(projects)
        if height is None:
            height = max(300, n_projects * 50 + 150)

        fig = go.Figure()

        # Y positions (reversed so first item is at top)
        y_positions = list(range(n_projects - 1, -1, -1))

        # Project labels with sample info
        y_labels = [
            f"{p['project_name']} (n={p['replicate_count']}, {p['plate_count']} plates)"
            for p in projects
        ]

        # Add reference line at FC=1 (log2=0)
        fig.add_vline(
            x=0,
            line=dict(color="gray", width=1, dash="dash"),
            annotation_text="FC=1",
            annotation_position="top"
        )

        # Add confidence intervals as horizontal error bars
        ci_lowers = [p["ci_lower"] for p in projects]
        ci_uppers = [p["ci_upper"] for p in projects]
        means = [p["mean"] for p in projects]

        # Error bar trace
        fig.add_trace(go.Scatter(
            x=means,
            y=y_positions,
            mode="markers",
            marker=dict(size=10, color="#228be6", symbol="diamond"),
            error_x=dict(
                type="data",
                symmetric=False,
                array=[u - m for u, m in zip(ci_uppers, means)],
                arrayminus=[m - l for m, l in zip(means, ci_lowers)],
                color="#228be6",
                thickness=2,
                width=6
            ),
            name="95% CI",
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Mean: %{x:.3f}<br>"
                "95% CI: [%{customdata[1]:.3f}, %{customdata[2]:.3f}]<br>"
                "Plates: %{customdata[3]}<br>"
                "Replicates: %{customdata[4]}"
                "<extra></extra>"
            ),
            customdata=[
                [p["project_name"], p["ci_lower"], p["ci_upper"],
                 p["plate_count"], p["replicate_count"]]
                for p in projects
            ]
        ))

        # Add CI width annotations
        for i, p in enumerate(projects):
            ci_width = p["ci_upper"] - p["ci_lower"]
            fig.add_annotation(
                x=p["ci_upper"] + 0.1,
                y=y_positions[i],
                text=f"{p['mean']:.2f} [{p['ci_lower']:.2f}, {p['ci_upper']:.2f}]",
                showarrow=False,
                font=dict(size=10),
                xanchor="left"
            )

        # Add summary diamond if requested
        if show_summary and len(projects) >= 2:
            summary = cls.compute_cross_project_summary(comparison_data)
            if summary:
                # Add summary row
                summary_y = -1
                fig.add_trace(go.Scatter(
                    x=[summary.mean_estimate],
                    y=[summary_y],
                    mode="markers",
                    marker=dict(
                        size=15,
                        color="#fab005",
                        symbol="diamond",
                        line=dict(color="black", width=1)
                    ),
                    name="Cross-project mean",
                    hovertemplate=(
                        "<b>Cross-Project Summary</b><br>"
                        f"Mean: {summary.mean_estimate:.3f}<br>"
                        f"Range: [{summary.min_estimate:.3f}, {summary.max_estimate:.3f}]<br>"
                        f"Projects: {summary.n_projects}<br>"
                        f"Total replicates: {summary.total_replicates}"
                        "<extra></extra>"
                    )
                ))
                y_labels.append("Summary (not pooled)")
                y_positions.append(summary_y)

        # Update layout
        parameter_labels = {
            "log_fc_fmax": "log\u2082 FC(F_max)",
            "log_fc_kobs": "log\u2082 FC(k_obs)",
            "delta_tlag": "\u0394t_lag (min)"
        }
        x_label = parameter_labels.get(
            comparison_data.parameter_type,
            comparison_data.parameter_type
        )

        fig.update_layout(
            title=title or f"Cross-Project Comparison: {comparison_data.construct_identifier}",
            xaxis_title=x_label,
            yaxis=dict(
                tickmode="array",
                tickvals=y_positions,
                ticktext=y_labels,
                autorange="reversed"
            ),
            height=height,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=200, r=150, t=80, b=50)
        )

        return fig

    @classmethod
    def generate_posterior_overlay_plot(
        cls,
        comparison_data: ConstructComparisonData,
        title: Optional[str] = None,
        height: int = 400
    ) -> go.Figure:
        """
        Generate overlaid posterior density plots for visual comparison.

        Note: Since we don't have full posterior samples, we approximate
        with normal distributions based on mean and std.

        Args:
            comparison_data: The comparison data to plot
            title: Optional chart title
            height: Figure height

        Returns:
            Plotly figure

        PRD Reference: F20.3 - Overlay posteriors from different projects
        """
        projects = comparison_data.projects

        if not projects:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig

        fig = go.Figure()

        # Color palette for projects
        colors = [
            "#228be6", "#40c057", "#fab005", "#fa5252", "#be4bdb",
            "#15aabf", "#82c91e", "#fd7e14", "#e64980", "#7950f2"
        ]

        # Find x-axis range
        all_means = [p["mean"] for p in projects]
        all_stds = [p["std"] for p in projects]
        x_min = min(m - 3*s for m, s in zip(all_means, all_stds))
        x_max = max(m + 3*s for m, s in zip(all_means, all_stds))
        x = np.linspace(x_min, x_max, 200)

        # Add posterior approximation for each project
        for i, p in enumerate(projects):
            mean = p["mean"]
            std = p["std"]
            color = colors[i % len(colors)]

            # Normal approximation of posterior
            y = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std) ** 2)

            fig.add_trace(go.Scatter(
                x=x,
                y=y,
                mode="lines",
                fill="tozeroy",
                fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.3])}",
                line=dict(color=color, width=2),
                name=f"{p['project_name']} (n={p['replicate_count']})",
                hovertemplate=(
                    f"<b>{p['project_name']}</b><br>"
                    f"Mean: {mean:.3f}<br>"
                    f"SD: {std:.3f}<br>"
                    "<extra></extra>"
                )
            ))

        # Add reference line at 0
        fig.add_vline(
            x=0,
            line=dict(color="gray", width=1, dash="dash"),
            annotation_text="FC=1"
        )

        parameter_labels = {
            "log_fc_fmax": "log\u2082 FC(F_max)",
            "log_fc_kobs": "log\u2082 FC(k_obs)",
            "delta_tlag": "\u0394t_lag (min)"
        }

        fig.update_layout(
            title=title or f"Posterior Comparison: {comparison_data.construct_identifier}",
            xaxis_title=parameter_labels.get(
                comparison_data.parameter_type,
                comparison_data.parameter_type
            ),
            yaxis_title="Density",
            height=height,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        return fig

    @classmethod
    def export_comparison_table(
        cls,
        comparison_data: ConstructComparisonData,
        include_diagnostics: bool = False
    ) -> pd.DataFrame:
        """
        Export comparison data as a DataFrame for download.

        Args:
            comparison_data: The comparison data to export
            include_diagnostics: Include MCMC diagnostics columns

        Returns:
            DataFrame with comparison data

        PRD Reference: F20.4 - Tabular comparison of estimates with CIs
        """
        if not comparison_data.projects:
            return pd.DataFrame()

        rows = []
        for p in comparison_data.projects:
            row = {
                "Project": p["project_name"],
                "Construct": comparison_data.construct_identifier,
                "Parameter": comparison_data.parameter_type,
                "N Plates": p["plate_count"],
                "N Replicates": p["replicate_count"],
                "Mean": p["mean"],
                "SD": p["std"],
                "CI Lower (95%)": p["ci_lower"],
                "CI Upper (95%)": p["ci_upper"],
                "CI Width": p["ci_width"],
            }

            # Add Bayesian probabilities if available
            if p.get("prob_positive") is not None:
                row["P(FC > 1)"] = p["prob_positive"]
            if p.get("prob_meaningful") is not None:
                row["P(Meaningful)"] = p["prob_meaningful"]

            # Add variance components if available
            if p.get("var_session") is not None:
                row["Var (Session)"] = p["var_session"]
            if p.get("var_plate") is not None:
                row["Var (Plate)"] = p["var_plate"]
            if p.get("var_residual") is not None:
                row["Var (Residual)"] = p["var_residual"]

            # Add diagnostics if requested
            if include_diagnostics:
                row["N Samples"] = p.get("n_samples")
                row["R-hat"] = p.get("r_hat")
                row["ESS Bulk"] = p.get("ess_bulk")

            row["Analysis Date"] = p.get("analysis_date")

            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    @classmethod
    def get_projects_with_analysis(cls) -> List[Dict[str, Any]]:
        """
        Get list of projects that have completed analyses.

        Returns:
            List of project dicts with id, name, analysis_count
        """
        query = db.session.query(
            Project.id,
            Project.name,
            func.count(AnalysisVersion.id).label("analysis_count")
        ).outerjoin(
            AnalysisVersion,
            and_(
                AnalysisVersion.project_id == Project.id,
                AnalysisVersion.status == AnalysisStatus.COMPLETED
            )
        ).filter(
            Project.is_deleted == False,
            Project.is_archived == False
        ).group_by(
            Project.id, Project.name
        ).having(
            func.count(AnalysisVersion.id) > 0
        ).order_by(
            Project.name
        )

        results = query.all()
        return [
            {
                "id": r[0],
                "name": r[1],
                "analysis_count": r[2]
            }
            for r in results
        ]
