"""
Results API endpoints for IVT Kinetics Analyzer.

Phase 5: API and Scripts - Results API Enhancement
PRD Reference: Section 4.2
Phase 3.3: Rate limiting applied consistently

Endpoints:
- GET /api/projects/{id}/results/posterior     Posterior summaries
- GET /api/projects/{id}/results/fold-changes  Fold change table
- GET /api/projects/{id}/results/diagnostics   MCMC diagnostics
- GET /api/projects/{id}/results/export        Export results as CSV/JSON
"""
import csv
import io
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from flask import Blueprint, jsonify, request, Response
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Project, Construct, AnalysisVersion, HierarchicalResult, FoldChange,
    Well, Plate, ExperimentalSession
)
from app.models.analysis_version import AnalysisStatus
from app.api.middleware import api_protection
from app.utils.validation import parse_bool_param


# Create Blueprint
results_api = Blueprint('results_api', __name__, url_prefix='/api/projects')


def _get_project_or_404(project_id: int):
    """Get project or return None if not found."""
    project = Project.query.get(project_id)
    return project


def _get_latest_analysis(project_id: int, version_id: Optional[int] = None) -> Optional[AnalysisVersion]:
    """Get the latest completed analysis version for a project."""
    if version_id:
        return AnalysisVersion.query.filter_by(
            id=version_id,
            project_id=project_id
        ).first()
    else:
        return AnalysisVersion.query.filter_by(
            project_id=project_id,
            status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisVersion.created_at.desc()).first()


# ==================== GET /api/projects/{id}/results/posterior ====================

@results_api.route('/<int:project_id>/results/posterior', methods=['GET'])
@api_protection(limiter_type="read")
def get_posterior_results(project_id: int):
    """
    Get posterior summaries for a project.

    Query parameters:
        - version_id: Specific analysis version (default: latest completed)
        - parameter_type: Filter by parameter type (e.g., "log_fc_fmax")
        - construct_id: Filter by construct ID

    Returns:
        Posterior summary results with CI, R-hat, and ESS values
    """
    project = _get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Get query parameters
    version_id = request.args.get('version_id', type=int)
    parameter_type = request.args.get('parameter_type')
    construct_id = request.args.get('construct_id', type=int)

    # Get analysis version
    analysis = _get_latest_analysis(project_id, version_id)

    if not analysis:
        return jsonify({
            "project_id": project_id,
            "analysis_version_id": None,
            "results": [],
            "count": 0,
            "message": "No completed analysis found"
        })

    # Build query with eager loading to avoid N+1 queries
    query = HierarchicalResult.query.options(
        joinedload(HierarchicalResult.construct)
    ).filter_by(analysis_version_id=analysis.id)

    if parameter_type:
        query = query.filter_by(parameter_type=parameter_type)

    if construct_id:
        query = query.filter_by(construct_id=construct_id)

    results = query.all()

    # Build response - construct is already loaded via joinedload
    result_data = []
    for r in results:
        construct = r.construct
        result_data.append({
            "id": r.id,
            "construct_id": r.construct_id,
            "construct_identifier": construct.identifier if construct else None,
            "construct_family": construct.family if construct else None,
            "parameter_type": r.parameter_type,
            "analysis_type": r.analysis_type,
            "mean": r.mean,
            "std": r.std,
            "ci_lower": r.ci_lower,
            "ci_upper": r.ci_upper,
            "ci_width": r.ci_width,
            "r_hat": r.r_hat,
            "ess_bulk": r.ess_bulk,
            "ess_tail": r.ess_tail,
            "prob_positive": r.prob_positive,
            "prob_meaningful": r.prob_meaningful,
            "var_session": r.var_session,
            "var_plate": r.var_plate,
            "var_residual": r.var_residual,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None
        })

    return jsonify({
        "project_id": project_id,
        "analysis_version_id": analysis.id,
        "analysis_name": analysis.name,
        "results": result_data,
        "count": len(result_data)
    })


# ==================== GET /api/projects/{id}/results/fold-changes ====================

@results_api.route('/<int:project_id>/results/fold-changes', methods=['GET'])
@api_protection(limiter_type="read")
def get_fold_changes(project_id: int):
    """
    Get fold change table for a project.

    Note: FoldChange model uses well IDs, so we query through wells to get
    fold changes for this project.

    Query parameters:
        - construct_id: Filter by test construct ID

    Returns:
        Fold change results with available fields
    """
    project = _get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Get query parameters
    construct_id = request.args.get('construct_id', type=int)

    # FoldChange model uses well IDs - query through wells belonging to this project
    # Get all wells for this project via session -> plate -> well path
    project_wells = db.session.query(Well.id).join(
        Plate, Well.plate_id == Plate.id
    ).join(
        ExperimentalSession, Plate.session_id == ExperimentalSession.id
    ).filter(
        ExperimentalSession.project_id == project_id
    )

    if construct_id:
        project_wells = project_wells.filter(Well.construct_id == construct_id)

    well_ids = [w[0] for w in project_wells.all()]

    # Get fold changes where test_well_id is in our project wells
    # Use eager loading for wells and their constructs to avoid N+1 queries
    fold_changes = []
    if well_ids:
        fold_changes = FoldChange.query.options(
            joinedload(FoldChange.test_well).joinedload(Well.construct),
            joinedload(FoldChange.control_well).joinedload(Well.construct)
        ).filter(
            FoldChange.test_well_id.in_(well_ids)
        ).all()

    # Build response - wells and constructs are already loaded via joinedload
    fc_data = []
    for fc in fold_changes:
        test_well = fc.test_well
        control_well = fc.control_well

        test_construct = test_well.construct if test_well else None
        control_construct = control_well.construct if control_well else None

        fc_data.append({
            "id": fc.id,
            "test_well_id": fc.test_well_id,
            "control_well_id": fc.control_well_id,
            "test_construct_id": test_construct.id if test_construct else None,
            "test_construct_identifier": test_construct.identifier if test_construct else None,
            "control_construct_id": control_construct.id if control_construct else None,
            "control_construct_identifier": control_construct.identifier if control_construct else None,
            "fc_fmax": fc.fc_fmax,
            "fc_kobs": fc.fc_kobs,
            "delta_tlag": fc.delta_tlag,
            "log_fc_fmax": fc.log_fc_fmax,
            "log_fc_kobs": fc.log_fc_kobs,
            "computed_at": fc.computed_at.isoformat() if fc.computed_at else None
        })

    return jsonify({
        "project_id": project_id,
        "fold_changes": fc_data,
        "count": len(fc_data)
    })


# ==================== GET /api/projects/{id}/results/diagnostics ====================

@results_api.route('/<int:project_id>/results/diagnostics', methods=['GET'])
@api_protection(limiter_type="read")
def get_diagnostics(project_id: int):
    """
    Get MCMC diagnostics for a project.

    Query parameters:
        - version_id: Specific analysis version (default: latest completed)
        - include_parameters: Include per-parameter breakdown (default: false)

    Returns:
        Convergence diagnostics summary and optional per-parameter details
    """
    project = _get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Get query parameters
    version_id = request.args.get('version_id', type=int)
    include_parameters = parse_bool_param(request.args.get('include_parameters'), default=False)

    # Get analysis version
    analysis = _get_latest_analysis(project_id, version_id)

    if not analysis:
        return jsonify({
            "project_id": project_id,
            "diagnostics": None,
            "message": "No completed analysis found"
        })

    # Get hierarchical results for diagnostics
    results = HierarchicalResult.query.filter_by(
        analysis_version_id=analysis.id
    ).all()

    if not results:
        return jsonify({
            "project_id": project_id,
            "analysis_version_id": analysis.id,
            "diagnostics": None,
            "message": "No results found for this analysis"
        })

    # Compute summary diagnostics
    r_hats = [r.r_hat for r in results if r.r_hat is not None]
    ess_bulks = [r.ess_bulk for r in results if r.ess_bulk is not None]
    ess_tails = [r.ess_tail for r in results if r.ess_tail is not None]

    diagnostics = {
        "model_type": analysis.model_type,
        "mcmc_chains": analysis.mcmc_chains,
        "mcmc_draws": analysis.mcmc_draws,
        "mcmc_tune": analysis.mcmc_tune,
        "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "duration_seconds": analysis.duration_seconds,

        # R-hat summary
        "max_r_hat": max(r_hats) if r_hats else None,
        "min_r_hat": min(r_hats) if r_hats else None,
        "mean_r_hat": sum(r_hats) / len(r_hats) if r_hats else None,

        # ESS summary
        "min_ess_bulk": min(ess_bulks) if ess_bulks else None,
        "mean_ess_bulk": sum(ess_bulks) / len(ess_bulks) if ess_bulks else None,
        "min_ess_tail": min(ess_tails) if ess_tails else None,
        "mean_ess_tail": sum(ess_tails) / len(ess_tails) if ess_tails else None,

        # Convergence status
        "all_converged": all(rh < 1.1 for rh in r_hats) if r_hats else False,
        "n_parameters": len(results),
        "n_converged": sum(1 for rh in r_hats if rh < 1.1) if r_hats else 0
    }

    # Add per-parameter details if requested
    if include_parameters:
        diagnostics["parameters"] = [
            {
                "construct_id": r.construct_id,
                "parameter_type": r.parameter_type,
                "r_hat": r.r_hat,
                "ess_bulk": r.ess_bulk,
                "ess_tail": r.ess_tail,
                "converged": r.r_hat < 1.1 if r.r_hat else None
            }
            for r in results
        ]

    return jsonify({
        "project_id": project_id,
        "analysis_version_id": analysis.id,
        "model_type": analysis.model_type,
        "diagnostics": diagnostics
    })


# ==================== GET /api/projects/{id}/results/export ====================

@results_api.route('/<int:project_id>/results/export', methods=['GET'])
@api_protection(limiter_type="read")
def export_results(project_id: int):
    """
    Export analysis results as JSON or CSV.

    Query parameters:
        - format: "json" or "csv" (default: "json")
        - version_id: Specific analysis version (default: latest completed)
        - include: Comma-separated list of sections to include
                   (posterior, fold_changes, diagnostics)

    Returns:
        Results in requested format
    """
    project = _get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Get query parameters
    output_format = request.args.get('format', 'json').lower()
    version_id = request.args.get('version_id', type=int)
    include_str = request.args.get('include', 'posterior,fold_changes')

    # Validate format
    if output_format not in ['json', 'csv']:
        return jsonify({"error": f"Invalid format: {output_format}. Use 'json' or 'csv'"}), 400

    include_sections = [s.strip() for s in include_str.split(',')]

    # Get analysis version
    analysis = _get_latest_analysis(project_id, version_id)

    # Build export data
    export_data = {
        "metadata": {
            "project_id": project_id,
            "project_name": project.name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "analysis_version_id": analysis.id if analysis else None,
            "analysis_name": analysis.name if analysis else None
        }
    }

    # Include posterior results
    if 'posterior' in include_sections:
        if analysis:
            # Use eager loading to avoid N+1 queries
            results = HierarchicalResult.query.options(
                joinedload(HierarchicalResult.construct)
            ).filter_by(
                analysis_version_id=analysis.id
            ).all()

            export_data["posterior"] = [
                {
                    "construct_id": r.construct_id,
                    "construct_identifier": r.construct.identifier if r.construct else None,
                    "parameter_type": r.parameter_type,
                    "mean": r.mean,
                    "std": r.std,
                    "ci_lower": r.ci_lower,
                    "ci_upper": r.ci_upper,
                    "r_hat": r.r_hat,
                    "ess_bulk": r.ess_bulk
                }
                for r in results
            ]
        else:
            export_data["posterior"] = []

    # Include fold changes (query through wells for this project)
    if 'fold_changes' in include_sections:
        project_wells = db.session.query(Well.id).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id
        )
        well_ids = [w[0] for w in project_wells.all()]

        fold_changes = []
        if well_ids:
            fold_changes = FoldChange.query.filter(
                FoldChange.test_well_id.in_(well_ids)
            ).all()

        export_data["fold_changes"] = [
            {
                "test_well_id": fc.test_well_id,
                "control_well_id": fc.control_well_id,
                "fc_fmax": fc.fc_fmax,
                "fc_kobs": fc.fc_kobs,
                "log_fc_fmax": fc.log_fc_fmax,
                "log_fc_kobs": fc.log_fc_kobs
            }
            for fc in fold_changes
        ]

    # Include diagnostics
    if 'diagnostics' in include_sections and analysis:
        results = HierarchicalResult.query.filter_by(
            analysis_version_id=analysis.id
        ).all()

        r_hats = [r.r_hat for r in results if r.r_hat is not None]

        export_data["diagnostics"] = {
            "model_type": analysis.model_type,
            "mcmc_chains": analysis.mcmc_chains,
            "mcmc_draws": analysis.mcmc_draws,
            "max_r_hat": max(r_hats) if r_hats else None,
            "all_converged": all(rh < 1.1 for rh in r_hats) if r_hats else False
        }

    # Return based on format
    if output_format == 'json':
        return jsonify(export_data)

    else:  # CSV format
        # Create CSV with multiple sheets as separate sections
        output = io.StringIO()

        # Write metadata as comments
        output.write(f"# Project: {project.name}\n")
        output.write(f"# Exported: {datetime.now(timezone.utc).isoformat()}\n")
        if analysis:
            output.write(f"# Analysis: {analysis.name}\n")
        output.write("\n")

        # Write posterior results
        if 'posterior' in export_data:
            output.write("# Posterior Results\n")
            if export_data["posterior"]:
                writer = csv.DictWriter(output, fieldnames=list(export_data["posterior"][0].keys()))
                writer.writeheader()
                writer.writerows(export_data["posterior"])
            output.write("\n")

        # Write fold changes
        if 'fold_changes' in export_data:
            output.write("# Fold Changes\n")
            if export_data["fold_changes"]:
                writer = csv.DictWriter(output, fieldnames=list(export_data["fold_changes"][0].keys()))
                writer.writeheader()
                writer.writerows(export_data["fold_changes"])

        csv_content = output.getvalue()
        output.close()

        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=results_project_{project_id}.csv'
            }
        )


def register_results_api(app):
    """Register the results API blueprint with the Flask app."""
    app.register_blueprint(results_api)
