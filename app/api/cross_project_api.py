"""
Cross-Project Comparison API endpoints.

Sprint 8: Cross-Project Features (PRD Section 3.20)
Phase 3.3: Rate limiting applied consistently

Provides REST API for:
- F20.1: View constructs by identifier across projects
- F20.2-F20.4: Get comparison data for visualization

Note: Read-only endpoints. No data modification.
"""
import logging

from flask import Blueprint, jsonify, request

from app.services.cross_project_service import (
    CrossProjectComparisonService,
    ProjectConstructMatch,
    ConstructComparisonData,
)
from app.api.middleware import api_protection
from app.utils.validation import parse_bool_param, validate_non_empty_list

logger = logging.getLogger(__name__)

# Create Blueprint
cross_project_api = Blueprint(
    'cross_project_api',
    __name__,
    url_prefix='/api/cross-project'
)


@cross_project_api.route('/constructs', methods=['GET'])
@api_protection(limiter_type="read")
def list_shared_constructs():
    """
    List construct identifiers shared across multiple projects.

    Query parameters:
        - min_projects: Minimum number of projects (default: 2)

    Returns:
        List of construct identifiers with project counts

    PRD Reference: F20.1 - View constructs by identifier across projects
    """
    min_projects = request.args.get('min_projects', 2, type=int)

    try:
        shared = CrossProjectComparisonService.get_shared_construct_identifiers(
            min_projects=min_projects
        )

        return jsonify({
            "constructs": shared,
            "count": len(shared)
        })

    except Exception:
        logger.exception("Cross-project API error")
        return jsonify({"error": "Internal server error"}), 500


@cross_project_api.route('/constructs/<identifier>/projects', methods=['GET'])
@api_protection(limiter_type="read")
def find_projects_with_construct(identifier: str):
    """
    Find all projects containing a construct with the given identifier.

    Path parameters:
        - identifier: The construct identifier to search for

    Query parameters:
        - include_archived: Include archived projects (default: false)

    Returns:
        List of projects with plate/replicate counts and analysis status

    PRD Reference: F20.1 - View constructs by identifier across projects
    """
    include_archived = parse_bool_param(
        request.args.get('include_archived'), default=False
    )

    try:
        matches = CrossProjectComparisonService.find_matching_constructs(
            identifier=identifier,
            include_archived=include_archived
        )

        return jsonify({
            "identifier": identifier,
            "projects": [
                {
                    "project_id": m.project_id,
                    "project_name": m.project_name,
                    "construct_id": m.construct_id,
                    "family": m.family,
                    "is_wildtype": m.is_wildtype,
                    "is_unregulated": m.is_unregulated,
                    "plate_count": m.plate_count,
                    "replicate_count": m.replicate_count,
                    "has_analysis": m.has_analysis,
                    "latest_analysis_id": m.latest_analysis_id,
                    "latest_analysis_date": (
                        m.latest_analysis_date.isoformat()
                        if m.latest_analysis_date else None
                    )
                }
                for m in matches
            ],
            "count": len(matches)
        })

    except Exception:
        logger.exception("Cross-project API error")
        return jsonify({"error": "Internal server error"}), 500


@cross_project_api.route('/compare', methods=['POST'])
@api_protection(limiter_type="read")
def get_comparison_data():
    """
    Get comparison data for a construct across specified projects.

    Request body:
        - construct_identifier: The construct identifier (required)
        - project_ids: List of project IDs to compare (required)
        - parameter_type: "log_fc_fmax", "log_fc_kobs", or "delta_tlag" (default: log_fc_fmax)
        - analysis_type: "bayesian" or "frequentist" (default: bayesian)

    Returns:
        Comparison data including estimates, CIs, and summary

    PRD Reference: F20.2-F20.4 - Cross-project comparison data
    """
    data = request.get_json() or {}

    construct_identifier = data.get('construct_identifier')
    project_ids = data.get('project_ids', [])
    parameter_type = data.get('parameter_type', 'log_fc_fmax')
    analysis_type = data.get('analysis_type', 'bayesian')

    if not construct_identifier:
        return jsonify({"error": "construct_identifier is required"}), 400

    error = validate_non_empty_list(project_ids, "project_ids")
    if error:
        return jsonify({"error": error}), 400

    if parameter_type not in ['log_fc_fmax', 'log_fc_kobs', 'delta_tlag']:
        return jsonify({
            "error": "parameter_type must be one of: log_fc_fmax, log_fc_kobs, delta_tlag"
        }), 400

    if analysis_type not in ['bayesian', 'frequentist']:
        return jsonify({
            "error": "analysis_type must be one of: bayesian, frequentist"
        }), 400

    try:
        comparison = CrossProjectComparisonService.get_comparison_data(
            construct_identifier=construct_identifier,
            project_ids=project_ids,
            parameter_type=parameter_type,
            analysis_type=analysis_type
        )

        # Compute summary if we have enough data
        summary = None
        if len(comparison.projects) >= 2:
            summary_obj = CrossProjectComparisonService.compute_cross_project_summary(
                comparison_data=comparison
            )
            if summary_obj:
                summary = {
                    "n_projects": summary_obj.n_projects,
                    "total_plates": summary_obj.total_plates,
                    "total_replicates": summary_obj.total_replicates,
                    "mean_estimate": summary_obj.mean_estimate,
                    "pooled_std": summary_obj.pooled_std,
                    "min_estimate": summary_obj.min_estimate,
                    "max_estimate": summary_obj.max_estimate,
                    "range_estimate": summary_obj.range_estimate,
                    "all_positive": summary_obj.all_positive,
                    "all_meaningful": summary_obj.all_meaningful
                }

        return jsonify({
            "construct_identifier": comparison.construct_identifier,
            "parameter_type": comparison.parameter_type,
            "projects": comparison.projects,
            "summary": summary
        })

    except Exception:
        logger.exception("Cross-project API error")
        return jsonify({"error": "Internal server error"}), 500


@cross_project_api.route('/compare/export', methods=['POST'])
@api_protection(limiter_type="read")
def export_comparison_table():
    """
    Export comparison data as CSV.

    Request body:
        - construct_identifier: The construct identifier (required)
        - project_ids: List of project IDs to compare (required)
        - parameter_type: "log_fc_fmax", "log_fc_kobs", or "delta_tlag"
        - analysis_type: "bayesian" or "frequentist"
        - include_diagnostics: Include MCMC diagnostics (default: false)

    Returns:
        CSV file content

    PRD Reference: F20.4 - Tabular comparison of estimates with CIs
    """
    data = request.get_json() or {}

    construct_identifier = data.get('construct_identifier')
    project_ids = data.get('project_ids', [])
    parameter_type = data.get('parameter_type', 'log_fc_fmax')
    analysis_type = data.get('analysis_type', 'bayesian')
    include_diagnostics = data.get('include_diagnostics', False)

    if not construct_identifier:
        return jsonify({
            "error": "construct_identifier is required"
        }), 400

    error = validate_non_empty_list(project_ids, "project_ids")
    if error:
        return jsonify({"error": error}), 400

    try:
        comparison = CrossProjectComparisonService.get_comparison_data(
            construct_identifier=construct_identifier,
            project_ids=project_ids,
            parameter_type=parameter_type,
            analysis_type=analysis_type
        )

        df = CrossProjectComparisonService.export_comparison_table(
            comparison_data=comparison,
            include_diagnostics=include_diagnostics
        )

        from flask import Response
        csv_content = df.to_csv(index=False)

        filename = f"cross_project_{construct_identifier}_{parameter_type}.csv"

        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    except Exception:
        logger.exception("Cross-project API error")
        return jsonify({"error": "Internal server error"}), 500


@cross_project_api.route('/projects', methods=['GET'])
@api_protection(limiter_type="read")
def list_projects_with_analysis():
    """
    List all projects that have completed analyses.

    Returns:
        List of projects with analysis counts

    This is useful for showing which projects are available for comparison.
    """
    try:
        projects = CrossProjectComparisonService.get_projects_with_analysis()

        return jsonify({
            "projects": projects,
            "count": len(projects)
        })

    except Exception:
        logger.exception("Cross-project API error")
        return jsonify({"error": "Internal server error"}), 500


def register_cross_project_api(app):
    """Register the cross-project API blueprint."""
    app.register_blueprint(cross_project_api)
