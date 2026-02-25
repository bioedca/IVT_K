"""
REST API endpoints for plate layout management.

Phase 2.4: Plate layout templates (F5.1-F5.3)
Phase 3.3: Rate limiting applied consistently
"""
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.plate_layout import PlateLayout, WellAssignment, WellType
from app.services.plate_layout_service import PlateLayoutService, PlateLayoutValidationError
from app.api.middleware import api_protection
from app.logging_config import get_logger
from app.utils.validation import validate_enum_value, validate_non_empty_list, parse_bool_param

logger = get_logger(__name__)

layout_bp = Blueprint('layout', __name__)


@layout_bp.route('/api/projects/<int:project_id>/layouts', methods=['GET'])
@api_protection(limiter_type="read")
def list_layouts(project_id):
    """
    List plate layouts for a project.

    Query params:
        templates_only: Only return templates (default: false)
        include_draft: Include draft layouts (default: true)
    """
    templates_only = parse_bool_param(request.args.get('templates_only'), default=False)
    include_draft = parse_bool_param(request.args.get('include_draft'), default=True)

    layouts = PlateLayoutService.list_layouts(
        project_id=project_id,
        templates_only=templates_only,
        include_draft=include_draft
    )

    return jsonify({
        'layouts': [
            {
                'id': layout.id,
                'name': layout.name,
                'version': layout.version,
                'plate_format': layout.plate_format,
                'rows': layout.rows,
                'cols': layout.cols,
                'is_template': layout.is_template,
                'is_draft': layout.is_draft,
                'total_wells': layout.total_wells,
                'assigned_wells': len(layout.well_assignments)
            }
            for layout in layouts
        ]
    })


@layout_bp.route('/api/projects/<int:project_id>/layouts', methods=['POST'])
@api_protection(limiter_type="write")
def create_layout(project_id):
    """
    Create a new plate layout.

    JSON body:
        name: Layout name (required)
        plate_format: "96" or "384" (default: project format)
        is_template: Whether this is a template (default: true)
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name')
    plate_format = data.get('plate_format')
    is_template = data.get('is_template', True)
    username = request.headers.get('X-Username', 'anonymous')

    # Get project format if not specified
    if not plate_format:
        from app.models import Project
        project = Project.query.get(project_id)
        if project:
            plate_format = project.plate_format.value

    try:
        layout = PlateLayoutService.create_layout(
            project_id=project_id,
            name=name,
            username=username,
            plate_format=plate_format,
            is_template=is_template
        )
        return jsonify({
            'id': layout.id,
            'name': layout.name,
            'version': layout.version,
            'plate_format': layout.plate_format,
            'rows': layout.rows,
            'cols': layout.cols,
            'is_template': layout.is_template,
            'is_draft': layout.is_draft,
            'total_wells': layout.total_wells
        }), 201
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in create_layout", error=str(e))
        return jsonify({'error': str(e)}), 400


@layout_bp.route('/api/layouts/<int:layout_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_layout(layout_id):
    """Get a plate layout by ID."""
    layout = PlateLayoutService.get_layout(layout_id)

    if not layout:
        return jsonify({'error': 'Layout not found'}), 404

    return jsonify({
        'id': layout.id,
        'project_id': layout.project_id,
        'name': layout.name,
        'version': layout.version,
        'plate_format': layout.plate_format,
        'rows': layout.rows,
        'cols': layout.cols,
        'is_template': layout.is_template,
        'is_draft': layout.is_draft,
        'total_wells': layout.total_wells,
        'assigned_wells': len(layout.well_assignments)
    })


@layout_bp.route('/api/layouts/<int:layout_id>/summary', methods=['GET'])
@api_protection(limiter_type="read")
def get_layout_summary(layout_id):
    """Get summary statistics for a layout."""
    try:
        summary = PlateLayoutService.get_layout_summary(layout_id)
        return jsonify(summary)
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in get_layout_summary", error=str(e))
        return jsonify({'error': str(e)}), 404


@layout_bp.route('/api/layouts/<int:layout_id>/grid', methods=['GET'])
@api_protection(limiter_type="read")
def get_layout_grid(layout_id):
    """Get layout as 2D grid for display."""
    try:
        grid = PlateLayoutService.get_layout_grid(layout_id)
        return jsonify({'grid': grid})
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in get_layout_grid", error=str(e))
        return jsonify({'error': str(e)}), 404


@layout_bp.route('/api/layouts/<int:layout_id>/wells', methods=['POST'])
@api_protection(limiter_type="write")
def assign_well(layout_id):
    """
    Assign a well in the layout.

    JSON body:
        well_position: Position (e.g., "A1") (required)
        construct_id: Construct ID (required for sample wells)
        well_type: "sample", "blank", "negative_control_no_template", "negative_control_no_dye", "empty"
        paired_with: Paired control position (optional)
        replicate_group: Replicate group name (optional)
        ligand_concentration: Ligand concentration (optional, F5.10)
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    well_position = data.get('well_position')
    if not well_position:
        return jsonify({'error': 'well_position is required'}), 400

    construct_id = data.get('construct_id')
    well_type_str = data.get('well_type', 'sample')
    paired_with = data.get('paired_with')
    replicate_group = data.get('replicate_group')
    ligand_concentration = data.get('ligand_concentration')
    ligand_condition = data.get('ligand_condition')
    username = request.headers.get('X-Username', 'anonymous')

    well_type, error = validate_enum_value(well_type_str, WellType, "well_type")
    if error:
        return jsonify({'error': error}), 400

    try:
        assignment = PlateLayoutService.assign_well(
            layout_id=layout_id,
            well_position=well_position,
            username=username,
            construct_id=construct_id,
            well_type=well_type,
            paired_with=paired_with,
            replicate_group=replicate_group,
            ligand_concentration=ligand_concentration,
            ligand_condition=ligand_condition,
        )
        return jsonify({
            'id': assignment.id,
            'well_position': assignment.well_position,
            'construct_id': assignment.construct_id,
            'well_type': assignment.well_type.value,
            'paired_with': assignment.paired_with,
            'replicate_group': assignment.replicate_group,
            'ligand_concentration': assignment.ligand_concentration,
            'ligand_condition': assignment.ligand_condition,
        }), 201
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in assign_well", error=str(e))
        return jsonify({'error': str(e)}), 400


@layout_bp.route('/api/layouts/<int:layout_id>/wells/bulk', methods=['POST'])
@api_protection(limiter_type="write")
def bulk_assign_wells(layout_id):
    """
    Assign multiple wells at once.

    JSON body:
        well_positions: List of positions (required)
        construct_id: Construct ID (required for sample wells)
        well_type: Well type (default: "sample")
        replicate_group: Group name (optional)
        ligand_concentration: Ligand concentration (optional, F5.10)
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    well_positions = data.get('well_positions')
    error = validate_non_empty_list(well_positions, "well_positions")
    if error:
        return jsonify({'error': error}), 400

    construct_id = data.get('construct_id')
    well_type_str = data.get('well_type', 'sample')
    replicate_group = data.get('replicate_group')
    ligand_concentration = data.get('ligand_concentration')
    ligand_condition = data.get('ligand_condition')
    username = request.headers.get('X-Username', 'anonymous')

    well_type, error = validate_enum_value(well_type_str, WellType, "well_type")
    if error:
        return jsonify({'error': error}), 400

    try:
        assignments = PlateLayoutService.bulk_assign_wells(
            layout_id=layout_id,
            well_positions=well_positions,
            username=username,
            construct_id=construct_id,
            well_type=well_type,
            replicate_group=replicate_group,
            ligand_concentration=ligand_concentration,
            ligand_condition=ligand_condition,
        )
        return jsonify({
            'assigned_count': len(assignments),
            'assignments': [
                {
                    'id': a.id,
                    'well_position': a.well_position,
                    'well_type': a.well_type.value,
                    'ligand_concentration': a.ligand_concentration,
                    'ligand_condition': a.ligand_condition,
                }
                for a in assignments
            ]
        }), 201
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in bulk_assign_wells", error=str(e))
        return jsonify({'error': str(e)}), 400


@layout_bp.route('/api/layouts/<int:layout_id>/wells/ligand', methods=['POST'])
@api_protection(limiter_type="write")
def bulk_assign_ligand(layout_id):
    """
    Assign ligand concentration to multiple existing wells (F5.10).

    JSON body:
        well_positions: List of positions (required)
        ligand_concentration: Concentration value (required)
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    well_positions = data.get('well_positions')
    error = validate_non_empty_list(well_positions, "well_positions")
    if error:
        return jsonify({'error': error}), 400

    ligand_concentration = data.get('ligand_concentration')
    if ligand_concentration is None:
        return jsonify({'error': 'ligand_concentration is required'}), 400

    username = request.headers.get('X-Username', 'anonymous')

    try:
        updated = PlateLayoutService.bulk_assign_ligand(
            layout_id=layout_id,
            well_positions=well_positions,
            ligand_concentration=ligand_concentration,
            username=username
        )
        return jsonify({
            'updated_count': len(updated),
            'wells': [
                {
                    'well_position': a.well_position,
                    'ligand_concentration': a.ligand_concentration
                }
                for a in updated
            ]
        }), 200
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in bulk_assign_ligand", error=str(e))
        return jsonify({'error': str(e)}), 400


@layout_bp.route('/api/layouts/<int:layout_id>/wells/<well_position>', methods=['DELETE'])
@api_protection(limiter_type="write")
def clear_well(layout_id, well_position):
    """Clear a well assignment."""
    username = request.headers.get('X-Username', 'anonymous')

    try:
        result = PlateLayoutService.clear_well(layout_id, well_position, username)
        if result:
            return jsonify({'message': f'Well {well_position} cleared'}), 200
        else:
            return jsonify({'message': f'Well {well_position} was already empty'}), 200
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in clear_well", error=str(e))
        return jsonify({'error': str(e)}), 404


@layout_bp.route('/api/layouts/<int:layout_id>/validate', methods=['GET'])
@api_protection(limiter_type="read")
def validate_layout(layout_id):
    """Validate a layout meets all requirements."""
    is_valid, issues = PlateLayoutService.validate_layout(layout_id)

    return jsonify({
        'is_valid': is_valid,
        'issues': issues
    })


@layout_bp.route('/api/layouts/<int:layout_id>/publish', methods=['POST'])
@api_protection(limiter_type="write")
def publish_layout(layout_id):
    """Publish a layout (mark as non-draft)."""
    username = request.headers.get('X-Username', 'anonymous')

    try:
        layout = PlateLayoutService.publish_layout(layout_id, username)
        return jsonify({
            'id': layout.id,
            'name': layout.name,
            'is_draft': layout.is_draft
        })
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in publish_layout", error=str(e))
        return jsonify({'error': str(e)}), 400


@layout_bp.route('/api/layouts/<int:layout_id>/unpublish', methods=['POST'])
@api_protection(limiter_type="write")
def unpublish_layout(layout_id):
    """Unpublish a layout (revert to draft)."""
    username = request.headers.get('X-Username', 'anonymous')

    try:
        layout = PlateLayoutService.unpublish_layout(layout_id, username)
        return jsonify({
            'id': layout.id,
            'name': layout.name,
            'is_draft': layout.is_draft
        })
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in unpublish_layout", error=str(e))
        return jsonify({'error': str(e)}), 404


@layout_bp.route('/api/layouts/<int:layout_id>/version', methods=['POST'])
@api_protection(limiter_type="write")
def create_layout_version(layout_id):
    """Create a new version of an existing layout."""
    username = request.headers.get('X-Username', 'anonymous')

    try:
        new_layout = PlateLayoutService.create_version(layout_id, username)
        return jsonify({
            'id': new_layout.id,
            'name': new_layout.name,
            'version': new_layout.version,
            'is_draft': new_layout.is_draft,
            'source_layout_id': layout_id
        }), 201
    except PlateLayoutValidationError as e:
        logger.warning("Layout validation error in create_layout_version", error=str(e))
        return jsonify({'error': str(e)}), 404


def register_layout_api(app):
    """Register layout API blueprint with Flask app."""
    app.register_blueprint(layout_bp)
