"""Callbacks for cross-family comparison features."""
from dash import Input, Output, State, ctx
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc

from app.logging_config import get_logger
from app.callbacks.analysis_utils import (
    dmc_text_dimmed,
    _compute_derived_fc_from_db,
    _compute_cross_family_fc_from_db,
    _compute_custom_fc,
)

logger = get_logger(__name__)


def register_analysis_comparison_callbacks(app):
    """Register cross-family comparison callbacks."""

    @app.callback(
        Output("cross-family-construct1-select", "data"),
        Output("cross-family-construct2-select", "data"),
        Input("analysis-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_cross_family_constructs(project_id):
        """Load constructs for cross-family comparison selectors."""
        if not project_id:
            return [], []

        try:
            from app.models import Construct

            constructs = Construct.query.filter_by(
                project_id=project_id,
                is_draft=False,
            ).filter(
                Construct.is_unregulated.is_(False)  # Exclude unregulated from direct selection
            ).order_by(Construct.family, Construct.identifier).all()

            # DMC v2 grouped select: {"group": "Name", "items": [...]}
            from collections import OrderedDict
            groups = OrderedDict()
            for c in constructs:
                family = c.family or "Other"
                if family not in groups:
                    groups[family] = []
                groups[family].append({
                    "value": str(c.id),
                    "label": c.identifier,
                })

            options = [
                {"group": family, "items": items}
                for family, items in groups.items()
            ]

            return options, options
        except Exception:
            return [], []

    @app.callback(
        Output("cross-family-precomputed-table", "children"),
        Input("analysis-results-store", "data"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_precomputed_comparisons(analysis_data, project_id):
        """Load pre-computed mutant vs unregulated comparisons."""
        from app.layouts.analysis_results import (
            create_cross_family_precomputed_table,
            create_empty_cross_family,
        )

        if not analysis_data or not project_id:
            return create_empty_cross_family()

        try:
            from app.models import Construct
            from app.models.comparison import ComparisonGraph as ComparisonGraphModel, PathType

            # Get two-hop comparisons (mutant -> WT -> unregulated)
            comparisons = ComparisonGraphModel.query.filter_by(
                project_id=project_id,
            ).filter(
                ComparisonGraphModel.path_type == PathType.TWO_HOP
            ).all()

            if not comparisons:
                return dmc_text_dimmed("No pre-computed comparisons available")

            comparison_list = []
            for comp in comparisons:
                source = Construct.query.get(comp.source_construct_id)
                target = Construct.query.get(comp.target_construct_id)

                if source and target and target.is_unregulated:
                    fc_data = _compute_derived_fc_from_db(
                        comp.source_construct_id,
                        comp.target_construct_id,
                        comp.intermediate_construct_id,
                        project_id,
                    )

                    if fc_data and fc_data.get("is_valid"):
                        comparison_list.append({
                            "test_name": source.identifier,
                            "control_name": target.identifier,
                            "fc": fc_data.get("fc", 1.0),
                            "ci_lower": fc_data.get("ci_lower", 0),
                            "ci_upper": fc_data.get("ci_upper", 0),
                            "vif": 2.0,
                            "path_type": "Two-hop",
                        })

            return create_cross_family_precomputed_table(comparison_list)

        except Exception as e:
            print(f"Error loading precomputed comparisons: {e}")
            return dmc_text_dimmed("Error loading comparisons")

    @app.callback(
        Output("cross-family-mutant-table", "children"),
        Input("analysis-results-store", "data"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_cross_family_mutant_comparisons(analysis_data, project_id):
        """Load cross-family mutant-to-mutant comparisons."""
        from app.layouts.analysis_results import (
            create_cross_family_mutant_table,
        )

        if not analysis_data or not project_id:
            return dmc_text_dimmed("Run analysis to view cross-family comparisons")

        try:
            from app.models.comparison import ComparisonGraph as ComparisonGraphModel, PathType
            from app.models import Construct

            # Get four-hop comparisons (cross-family)
            comparisons = ComparisonGraphModel.query.filter_by(
                project_id=project_id,
            ).filter(
                ComparisonGraphModel.path_type == PathType.FOUR_HOP
            ).all()

            if not comparisons:
                return dmc_text_dimmed("No cross-family mutant comparisons available")

            comparison_list = []
            for comp in comparisons:
                source = Construct.query.get(comp.source_construct_id)
                target = Construct.query.get(comp.target_construct_id)

                if source and target:
                    fc_data = _compute_cross_family_fc_from_db(
                        comp.source_construct_id,
                        comp.target_construct_id,
                        project_id,
                    )

                    if fc_data and fc_data.get("is_valid"):
                        comparison_list.append({
                            "mutant1_name": source.identifier,
                            "mutant1_family": source.family or "Unknown",
                            "mutant2_name": target.identifier,
                            "mutant2_family": target.family or "Unknown",
                            "fc": fc_data.get("fc", 1.0),
                            "ci_lower": fc_data.get("ci_lower", 0),
                            "ci_upper": fc_data.get("ci_upper", 0),
                            "vif": 4.0,
                        })

            return create_cross_family_mutant_table(comparison_list)

        except Exception as e:
            print(f"Error loading cross-family comparisons: {e}")
            return dmc_text_dimmed("Error loading comparisons")

    @app.callback(
        Output("cross-family-custom-result", "children"),
        Input("cross-family-compute-btn", "n_clicks"),
        State("cross-family-construct1-select", "value"),
        State("cross-family-construct2-select", "value"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def compute_custom_comparison(n_clicks, construct1_id, construct2_id, project_id):
        """Compute custom cross-family comparison on demand."""
        from app.layouts.analysis_results import create_custom_comparison_result

        if not n_clicks or not construct1_id or not construct2_id:
            raise PreventUpdate

        if construct1_id == construct2_id:
            return create_custom_comparison_result({
                "is_valid": False,
                "error_message": "Please select two different constructs for comparison."
            })

        try:
            from app.models import Construct
            from app.services.comparison_service import ComparisonService
            from app.analysis.comparison import (
                PairedAnalysis, ComparisonGraph, PathType, VIF_VALUES
            )

            # Get constructs
            c1 = Construct.query.get(int(construct1_id))
            c2 = Construct.query.get(int(construct2_id))

            if not c1 or not c2:
                return create_custom_comparison_result({
                    "is_valid": False,
                    "error_message": "One or both constructs not found."
                })

            # Build comparison graph to find path
            graph = ComparisonService.build_comparison_graph(project_id)
            path = graph.get_comparison_path(c1.id, c2.id)

            if not path:
                return create_custom_comparison_result({
                    "is_valid": False,
                    "error_message": f"No comparison path exists between {c1.identifier} and {c2.identifier}. "
                                   "Ensure both constructs have sufficient data and share a reference path."
                })

            # Determine path type and description
            path_type = path.path_type.value.replace("_", "-").title()
            vif = path.variance_inflation

            # Build path description
            if path.intermediates:
                intermediate_names = []
                for int_id in path.intermediates:
                    int_c = Construct.query.get(int_id)
                    if int_c:
                        intermediate_names.append(int_c.identifier)
                path_desc = f"{c1.identifier} \u2192 " + " \u2192 ".join(intermediate_names) + f" \u2192 {c2.identifier}"
            else:
                path_desc = f"{c1.identifier} \u2192 {c2.identifier} (Direct comparison)"

            # Compute the fold change
            fc_result = _compute_custom_fc(c1.id, c2.id, path, project_id)

            return create_custom_comparison_result({
                "is_valid": fc_result.get("is_valid", False),
                "test_name": c1.identifier,
                "control_name": c2.identifier,
                "fc": fc_result.get("fc", 1.0),
                "ci_lower": fc_result.get("ci_lower", 0),
                "ci_upper": fc_result.get("ci_upper", 0),
                "vif": vif,
                "path_type": path_type,
                "path_description": path_desc,
                "error_message": fc_result.get("error_message"),
            })

        except Exception as e:
            logger.exception("Error computing custom comparison")
            return create_custom_comparison_result({
                "is_valid": False,
                "error_message": "An unexpected error occurred while computing the comparison."
            })
