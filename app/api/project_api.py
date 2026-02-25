"""
Project and Construct API endpoints.

Phase 2.1: Project CRUD with draft/publish states
Phase 2.2-2.3: Construct registry with family management and anchor types
Phase 3.3: Rate limiting applied consistently
"""
from flask import Blueprint, jsonify, request, g
from sqlalchemy.orm import joinedload

from app.models.project import PlateFormat
from app.services.project_service import ProjectService, ProjectValidationError
from app.services.construct_service import ConstructService, ConstructValidationError
from app.api.middleware import api_protection
from app.logging_config import get_logger
from app.utils.validation import validate_enum_value, parse_bool_param

logger = get_logger(__name__)

# Create Blueprint
project_api = Blueprint('project_api', __name__, url_prefix='/api/projects')


# ============ Project Endpoints ============

@project_api.route('/', methods=['GET'])
@api_protection(limiter_type="read")
def list_projects():
    """
    List all projects.

    Query parameters:
        - include_archived: Include archived projects (default: false)
        - draft_only: Only return draft projects
        - search: Search term for name/description
        - limit: Maximum number to return
    """
    include_archived = parse_bool_param(request.args.get('include_archived'), default=False)
    draft_only = parse_bool_param(request.args.get('draft_only'), default=False)
    search = request.args.get('search')
    limit = request.args.get('limit', type=int)

    projects = ProjectService.list_projects(
        include_archived=include_archived,
        draft_only=draft_only,
        search=search,
        limit=limit
    )

    return jsonify({
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "slug": p.name_slug,
                "description": p.description,
                "reporter_system": p.reporter_system,
                "plate_format": p.plate_format.value,
                "is_draft": p.is_draft,
                "is_archived": p.is_archived,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ],
        "count": len(projects)
    })


@project_api.route('/', methods=['POST'])
@api_protection(limiter_type="write")
def create_project():
    """
    Create a new project.

    Request body:
        - name: Project name (required)
        - description: Optional description
        - reporter_system: Fluorogenic aptamer system (default: iSpinach)
        - plate_format: "96" or "384" (default: 384)
        - precision_target: Target CI width (default: 0.3)

    Headers:
        - X-Username: User creating the project
    """
    data = request.get_json() or {}
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    name = data.get('name')
    if not name:
        return jsonify({"error": "Project name is required"}), 400

    # Parse plate format
    format_str = data.get('plate_format', '384')
    plate_format, error = validate_enum_value(format_str, PlateFormat, "plate_format")
    if error:
        return jsonify({'error': error}), 400

    try:
        project = ProjectService.create_project(
            name=name,
            username=username,
            description=data.get('description'),
            reporter_system=data.get('reporter_system', 'iSpinach'),
            plate_format=plate_format,
            precision_target=data.get('precision_target', 0.3)
        )

        return jsonify({
            "id": project.id,
            "name": project.name,
            "slug": project.name_slug,
            "is_draft": project.is_draft,
            "message": "Project created successfully"
        }), 201

    except ProjectValidationError as e:
        logger.warning("Project validation error in create_project", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_project(project_id: int):
    """Get project details with statistics."""
    stats = ProjectService.get_project_statistics(project_id)
    if not stats:
        return jsonify({"error": "Project not found"}), 404

    project = ProjectService.get_project(project_id)
    return jsonify({
        **stats,
        "description": project.description,
        "reporter_system": project.reporter_system,
        "notes": project.notes,
    })


@project_api.route('/<int:project_id>', methods=['PUT', 'PATCH'])
@api_protection(limiter_type="write")
def update_project(project_id: int):
    """
    Update project fields.

    Request body: Fields to update (name, description, precision_target, etc.)
    Headers:
        - X-Username: User making the update
    """
    data = request.get_json() or {}
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    try:
        project, changed_fields = ProjectService.update_project(
            project_id=project_id,
            username=username,
            **data
        )

        return jsonify({
            "id": project.id,
            "changed_fields": changed_fields,
            "message": "Project updated successfully"
        })

    except ProjectValidationError as e:
        logger.warning("Project validation error in update_project", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/publish', methods=['POST'])
@api_protection(limiter_type="write")
def publish_project(project_id: int):
    """Publish a project (mark as non-draft)."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    try:
        project = ProjectService.publish_project(project_id, username)
        return jsonify({
            "id": project.id,
            "is_draft": project.is_draft,
            "message": "Project published successfully"
        })

    except ProjectValidationError as e:
        logger.warning("Project validation error in publish_project", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/unpublish', methods=['POST'])
@api_protection(limiter_type="write")
def unpublish_project(project_id: int):
    """Revert a project to draft state."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    try:
        project = ProjectService.unpublish_project(project_id, username)
        return jsonify({
            "id": project.id,
            "is_draft": project.is_draft,
            "message": "Project reverted to draft"
        })

    except ProjectValidationError as e:
        logger.warning("Project validation error in unpublish_project", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>', methods=['DELETE'])
@api_protection(limiter_type="write")
def delete_project(project_id: int):
    """Soft-delete a project."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')
    force = parse_bool_param(request.args.get('force'), default=False)

    try:
        ProjectService.delete_project(project_id, username, force=force)
        return jsonify({
            "message": "Project deleted successfully"
        })

    except ProjectValidationError as e:
        logger.warning("Project validation error in delete_project", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/restore', methods=['POST'])
@api_protection(limiter_type="write")
def restore_project(project_id: int):
    """Restore a soft-deleted project."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    try:
        project = ProjectService.restore_project(project_id, username)
        return jsonify({
            "id": project.id,
            "message": "Project restored successfully"
        })

    except ProjectValidationError as e:
        logger.warning("Project validation error in restore_project", error=str(e))
        return jsonify({"error": str(e)}), 400


# ============ Construct Endpoints ============

@project_api.route('/<int:project_id>/constructs', methods=['GET'])
@api_protection(limiter_type="read")
def list_constructs(project_id: int):
    """
    List constructs for a project.

    Query parameters:
        - family: Filter by family name
        - include_draft: Include draft constructs (default: true)
        - anchor_only: Only return anchor constructs (WT or unregulated)
    """
    family = request.args.get('family')
    include_draft = parse_bool_param(request.args.get('include_draft'), default=True)
    anchor_only = parse_bool_param(request.args.get('anchor_only'), default=False)

    constructs = ConstructService.list_constructs(
        project_id=project_id,
        family=family,
        include_draft=include_draft,
        anchor_only=anchor_only
    )

    return jsonify({
        "constructs": [
            {
                "id": c.id,
                "identifier": c.identifier,
                "family": c.family,
                "description": c.description,
                "is_wildtype": c.is_wildtype,
                "is_unregulated": c.is_unregulated,
                "is_draft": c.is_draft,
                "display_name": c.display_name,
            }
            for c in constructs
        ],
        "count": len(constructs)
    })


@project_api.route('/<int:project_id>/constructs', methods=['POST'])
@api_protection(limiter_type="write")
def create_construct(project_id: int):
    """
    Create a new construct.

    Request body:
        - identifier: Unique identifier (required)
        - family: T-box family name (required unless unregulated)
        - description: Optional description
        - sequence: Optional DNA sequence
        - is_wildtype: Mark as wild-type for family
        - is_unregulated: Mark as reporter-only control
        - notes: Optional notes

    Headers:
        - X-Username: User creating the construct
    """
    data = request.get_json() or {}
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    identifier = data.get('identifier')
    if not identifier:
        return jsonify({"error": "Construct identifier is required"}), 400

    try:
        construct = ConstructService.create_construct(
            project_id=project_id,
            identifier=identifier,
            username=username,
            family=data.get('family'),
            description=data.get('description'),
            sequence=data.get('sequence'),
            is_wildtype=data.get('is_wildtype', False),
            is_unregulated=data.get('is_unregulated', False),
            notes=data.get('notes'),
            plasmid_size_bp=data.get('plasmid_size_bp'),
        )

        return jsonify({
            "id": construct.id,
            "identifier": construct.identifier,
            "family": construct.family,
            "is_draft": construct.is_draft,
            "display_name": construct.display_name,
            "message": "Construct created successfully"
        }), 201

    except ConstructValidationError as e:
        logger.warning("Construct validation error in create_construct", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/constructs/<int:construct_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_construct(project_id: int, construct_id: int):
    """Get construct details."""
    construct = ConstructService.get_construct(construct_id)

    if not construct or construct.project_id != project_id:
        return jsonify({"error": "Construct not found"}), 404

    return jsonify({
        "id": construct.id,
        "identifier": construct.identifier,
        "family": construct.family,
        "description": construct.description,
        "sequence": construct.sequence,
        "plasmid_size_bp": construct.plasmid_size_bp,
        "is_wildtype": construct.is_wildtype,
        "is_unregulated": construct.is_unregulated,
        "is_draft": construct.is_draft,
        "is_deleted": construct.is_deleted,
        "display_name": construct.display_name,
        "notes": construct.notes,
        "created_at": construct.created_at.isoformat() if construct.created_at else None,
        "updated_at": construct.updated_at.isoformat() if construct.updated_at else None,
    })


@project_api.route('/<int:project_id>/constructs/<int:construct_id>', methods=['PUT', 'PATCH'])
@api_protection(limiter_type="write")
def update_construct(project_id: int, construct_id: int):
    """Update construct fields."""
    data = request.get_json() or {}
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    construct = ConstructService.get_construct(construct_id)
    if not construct or construct.project_id != project_id:
        return jsonify({"error": "Construct not found"}), 404

    try:
        construct, changed_fields = ConstructService.update_construct(
            construct_id=construct_id,
            username=username,
            **data
        )

        return jsonify({
            "id": construct.id,
            "changed_fields": changed_fields,
            "message": "Construct updated successfully"
        })

    except ConstructValidationError as e:
        logger.warning("Construct validation error in update_construct", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/constructs/<int:construct_id>/publish', methods=['POST'])
@api_protection(limiter_type="write")
def publish_construct(project_id: int, construct_id: int):
    """Publish a construct."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    construct = ConstructService.get_construct(construct_id)
    if not construct or construct.project_id != project_id:
        return jsonify({"error": "Construct not found"}), 404

    try:
        construct = ConstructService.publish_construct(construct_id, username)
        return jsonify({
            "id": construct.id,
            "is_draft": construct.is_draft,
            "message": "Construct published successfully"
        })

    except ConstructValidationError as e:
        logger.warning("Construct validation error in publish_construct", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/constructs/<int:construct_id>/unpublish', methods=['POST'])
@api_protection(limiter_type="write")
def unpublish_construct(project_id: int, construct_id: int):
    """Revert a construct to draft state."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    construct = ConstructService.get_construct(construct_id)
    if not construct or construct.project_id != project_id:
        return jsonify({"error": "Construct not found"}), 404

    try:
        construct = ConstructService.unpublish_construct(construct_id, username)
        return jsonify({
            "id": construct.id,
            "is_draft": construct.is_draft,
            "message": "Construct reverted to draft"
        })

    except ConstructValidationError as e:
        logger.warning("Construct validation error in unpublish_construct", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/constructs/<int:construct_id>', methods=['DELETE'])
@api_protection(limiter_type="write")
def delete_construct(project_id: int, construct_id: int):
    """Soft-delete a construct."""
    username = getattr(g, 'username', None) or request.headers.get('X-Username', 'anonymous')

    construct = ConstructService.get_construct(construct_id)
    if not construct or construct.project_id != project_id:
        return jsonify({"error": "Construct not found"}), 404

    try:
        ConstructService.delete_construct(construct_id, username)
        return jsonify({
            "message": "Construct deleted successfully"
        })

    except ConstructValidationError as e:
        logger.warning("Construct validation error in delete_construct", error=str(e))
        return jsonify({"error": str(e)}), 400


@project_api.route('/<int:project_id>/families', methods=['GET'])
@api_protection(limiter_type="read")
def list_families(project_id: int):
    """Get all families in a project with their constructs."""
    families = ConstructService.get_families(project_id)

    return jsonify({
        "families": families,
        "count": len(families)
    })


@project_api.route('/<int:project_id>/validate-anchors', methods=['GET'])
@api_protection(limiter_type="read")
def validate_anchors(project_id: int):
    """Validate that a project has all required anchor constructs."""
    is_valid, issues = ConstructService.validate_project_anchors(project_id)

    return jsonify({
        "valid": is_valid,
        "issues": issues
    })


@project_api.route('/<int:project_id>/analysis', methods=['GET'])
@api_protection(limiter_type="read")
def get_analysis(project_id: int):
    """
    Get analysis results for a project.

    Query parameters:
        - version_id: Specific analysis version ID (default: latest completed)
        - include_posterior: Include full posterior summary (default: true)
        - include_fold_changes: Include fold change results (default: true)
        - include_convergence: Include convergence diagnostics (default: true)

    Returns:
        Analysis version info, posterior summaries, fold changes, and diagnostics
    """
    from app.models import Project, FitResult, FoldChange, Construct
    from app.models.analysis_version import AnalysisVersion, HierarchicalResult, AnalysisStatus

    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Parse query parameters
    version_id = request.args.get('version_id', type=int)
    include_posterior = parse_bool_param(request.args.get('include_posterior'), default=True)
    include_fold_changes = parse_bool_param(request.args.get('include_fold_changes'), default=True)
    include_convergence = parse_bool_param(request.args.get('include_convergence'), default=True)

    # Get analysis version
    if version_id:
        analysis_version = AnalysisVersion.query.filter_by(
            id=version_id,
            project_id=project_id
        ).first()
    else:
        analysis_version = AnalysisVersion.query.filter_by(
            project_id=project_id,
            status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisVersion.created_at.desc()).first()

    if not analysis_version:
        return jsonify({
            "project_id": project_id,
            "analysis": None,
            "message": "No completed analysis found"
        })

    # Build response
    response = {
        "project_id": project_id,
        "analysis_version": {
            "id": analysis_version.id,
            "name": analysis_version.name,
            "status": analysis_version.status.value if analysis_version.status else None,
            "created_at": analysis_version.created_at.isoformat() if analysis_version.created_at else None,
            "completed_at": analysis_version.completed_at.isoformat() if analysis_version.completed_at else None,
        }
    }

    # Posterior summary
    if include_posterior:
        # Use eager loading to avoid N+1 queries
        results = HierarchicalResult.query.options(
            joinedload(HierarchicalResult.construct)
        ).filter_by(
            analysis_version_id=analysis_version.id
        ).all()

        posterior_data = []
        for r in results:
            construct = r.construct
            posterior_data.append({
                "construct_id": r.construct_id,
                "construct_name": construct.identifier if construct else None,
                "parameter": r.parameter_type,
                "analysis_type": r.analysis_type,
                "posterior_mean": r.mean,
                "posterior_std": r.std,
                "ci_lower": r.ci_lower,
                "ci_upper": r.ci_upper,
                "r_hat": r.r_hat,
                "ess_bulk": r.ess_bulk,
                "ess_tail": r.ess_tail,
            })

        response["posterior_summary"] = {
            "results": posterior_data,
            "count": len(posterior_data)
        }

    # Fold changes
    if include_fold_changes:
        from app.extensions import db
        from app.models.experiment import Well, Plate, ExperimentalSession

        # First, get all well IDs for this project
        project_wells = db.session.query(Well.id).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id
        )
        well_ids = [w[0] for w in project_wells.all()]

        # Use eager loading to avoid N+1 queries
        fold_changes = []
        if well_ids:
            fold_changes = FoldChange.query.options(
                joinedload(FoldChange.test_well).joinedload(Well.construct),
                joinedload(FoldChange.control_well).joinedload(Well.construct)
            ).filter(
                FoldChange.test_well_id.in_(well_ids)
            ).all()

        fc_data = []
        for fc in fold_changes:
            test_well = fc.test_well
            control_well = fc.control_well
            test_construct = test_well.construct if test_well else None
            control_construct = control_well.construct if control_well else None

            fc_data.append({
                "id": fc.id,
                "test_construct_id": test_construct.id if test_construct else None,
                "test_construct_name": test_construct.identifier if test_construct else None,
                "control_construct_id": control_construct.id if control_construct else None,
                "control_construct_name": control_construct.identifier if control_construct else None,
                "log_fold_change": getattr(fc, 'log_fold_change', fc.log_fc_fmax),
                "fold_change": getattr(fc, 'fold_change', fc.fc_fmax),
                "ci_lower": getattr(fc, 'ci_lower', None),
                "ci_upper": getattr(fc, 'ci_upper', None),
                "standard_error": getattr(fc, 'standard_error', fc.fc_fmax_se),
                "comparison_type": getattr(fc, 'comparison_type', None),
                "variance_inflation_factor": getattr(fc, 'variance_inflation_factor', None),
            })

        response["fold_changes"] = {
            "results": fc_data,
            "count": len(fc_data)
        }

    # Convergence diagnostics
    if include_convergence:
        results = HierarchicalResult.query.filter_by(
            analysis_version_id=analysis_version.id
        ).all()

        if results:
            r_hats = [r.r_hat for r in results if r.r_hat is not None]
            ess_bulks = [r.ess_bulk for r in results if r.ess_bulk is not None]

            response["convergence"] = {
                "max_r_hat": max(r_hats) if r_hats else None,
                "min_r_hat": min(r_hats) if r_hats else None,
                "mean_r_hat": sum(r_hats) / len(r_hats) if r_hats else None,
                "min_ess_bulk": min(ess_bulks) if ess_bulks else None,
                "mean_ess_bulk": sum(ess_bulks) / len(ess_bulks) if ess_bulks else None,
                "all_converged": all(rh < 1.1 for rh in r_hats) if r_hats else False,
                "n_parameters": len(results),
            }
        else:
            response["convergence"] = None

    return jsonify(response)


@project_api.route('/<int:project_id>/analysis/versions', methods=['GET'])
@api_protection(limiter_type="read")
def list_analysis_versions(project_id: int):
    """
    List all analysis versions for a project.

    Query parameters:
        - status: Filter by status (pending, running, completed, failed)
        - limit: Maximum number to return (default: 10)
    """
    from app.models import Project
    from app.models.analysis_version import AnalysisVersion, AnalysisStatus

    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    status = request.args.get('status')
    limit = request.args.get('limit', 10, type=int)

    query = AnalysisVersion.query.filter_by(project_id=project_id)

    if status:
        # Convert string status to enum if provided
        try:
            status_enum = AnalysisStatus(status)
            query = query.filter_by(status=status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter

    versions = query.order_by(AnalysisVersion.created_at.desc()).limit(limit).all()

    return jsonify({
        "versions": [
            {
                "id": v.id,
                "name": v.name,
                "status": v.status.value if v.status else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "completed_at": v.completed_at.isoformat() if v.completed_at else None,
            }
            for v in versions
        ],
        "count": len(versions)
    })


def register_project_api(app):
    """Register the project API blueprint with the Flask app."""
    app.register_blueprint(project_api)
