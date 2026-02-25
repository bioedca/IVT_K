"""
Calculator API endpoints for IVT Reaction Calculator.

Phase 3.3: Rate limiting applied consistently
"""
from flask import Blueprint, jsonify, request
# Import from renamed service (reaction_calculator_service.py per PRD)
from app.services.reaction_calculator_service import CalculatorService
from app.api.middleware import api_protection
from app.logging_config import get_logger
from app.calculator.constants import DEFAULT_OVERAGE_PERCENT
from app.utils.validation import validate_required_fields
from app.calculator import (
    calculate_simple_dilution,
    calculate_dilution_for_target_dna_volume,
    recommend_dna_volume_intervention,
    recommend_well_volume_intervention,
    validate_checkerboard_position,
    format_validation_result,
    PlateFormat,
)

logger = get_logger(__name__)

calculator_bp = Blueprint('calculator', __name__, url_prefix='/api/calculator')


@calculator_bp.route('/constructs/<int:project_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_project_constructs(project_id: int):
    """
    Get constructs available for calculator.

    Returns constructs formatted for calculator input.
    """
    constructs = CalculatorService.get_project_constructs(project_id)
    return jsonify({
        'project_id': project_id,
        'constructs': constructs,
        'count': len(constructs),
    })


@calculator_bp.route('/calculate', methods=['POST'])
@api_protection(limiter_type="write")
def calculate_reaction():
    """
    Calculate reaction setup.

    Request body:
        project_id: int
        construct_ids: list[int]
        replicates_per_construct: int (default 4)
        dna_mass_ug: float (default 20.0)
        overage_percent: float (default DEFAULT_OVERAGE_PERCENT)
        negative_template_count: int (default 3)
        negative_dye_count: int (default 0)
        include_dye: bool (default True)
        ntp_concentrations: dict (optional)

    Returns:
        Master mix calculation result
    """
    data = request.get_json()

    error = validate_required_fields(data, ['project_id', 'construct_ids'])
    if error:
        return jsonify({'error': error}), 400

    try:
        calculation = CalculatorService.calculate_reaction_setup(
            project_id=data['project_id'],
            construct_ids=data['construct_ids'],
            replicates_per_construct=data.get('replicates_per_construct', 4),
            dna_mass_ug=data.get('dna_mass_ug', 20.0),
            overage_percent=data.get('overage_percent', DEFAULT_OVERAGE_PERCENT),
            negative_template_count=data.get('negative_template_count', 3),
            negative_dye_count=data.get('negative_dye_count', 0),
            include_dye=data.get('include_dye', True),
            ntp_concentrations=data.get('ntp_concentrations'),
        )

        # Convert to JSON-serializable format
        return jsonify({
            'success': True,
            'n_reactions': calculation.n_reactions,
            'overage_factor': calculation.overage_factor,
            'n_effective': calculation.n_effective,
            'reaction_volume_ul': calculation.single_reaction.reaction_volume_ul,
            'total_master_mix_volume_ul': calculation.total_master_mix_volume_ul,
            'master_mix_per_tube_ul': calculation.master_mix_per_tube_ul,
            'max_dna_volume_ul': calculation.max_dna_volume_ul,
            'is_valid': calculation.is_valid,
            'components': [
                {
                    'name': c.name,
                    'order': c.order,
                    'single_reaction_volume_ul': c.single_reaction_volume_ul,
                    'master_mix_volume_ul': c.master_mix_volume_ul,
                    'stock_concentration': c.stock_concentration,
                    'stock_unit': c.stock_unit,
                    'final_concentration': c.final_concentration,
                    'final_unit': c.final_unit,
                }
                for c in calculation.components
            ],
            'dna_additions': [
                {
                    'construct_name': a.construct_name,
                    'construct_id': a.construct_id,
                    'stock_concentration_ng_ul': a.stock_concentration_ng_ul,
                    'dna_volume_ul': a.dna_volume_ul,
                    'water_adjustment_ul': a.water_adjustment_ul,
                    'total_addition_ul': a.total_addition_ul,
                    'is_negative_control': a.is_negative_control,
                    'negative_control_type': a.negative_control_type,
                    'ligand_condition': a.ligand_condition,
                    'stock_concentration_nM': a.stock_concentration_nM,
                    'achieved_nM': a.achieved_nM,
                    'is_valid': a.is_valid,
                    'warning': a.warning,
                }
                for a in calculation.dna_additions
            ],
            'warnings': calculation.warnings,
            'errors': calculation.errors,
        })

    except Exception:
        logger.exception("Unexpected error in calculate_reaction")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@calculator_bp.route('/validate', methods=['POST'])
@api_protection(limiter_type="write")
def validate_setup():
    """
    Validate reaction setup before calculation.

    Request body:
        project_id: int
        construct_ids: list[int]
        replicates_per_construct: int
        dna_mass_ug: float
        negative_template_count: int
        negative_dye_count: int (optional)

    Returns:
        Validation result
    """
    data = request.get_json()

    error = validate_required_fields(data, ['project_id', 'construct_ids', 'replicates_per_construct', 'dna_mass_ug'])
    if error:
        return jsonify({'error': error}), 400

    result = CalculatorService.validate_setup(
        project_id=data['project_id'],
        construct_ids=data['construct_ids'],
        replicates_per_construct=data['replicates_per_construct'],
        dna_mass_ug=data['dna_mass_ug'],
        negative_template_count=data.get('negative_template_count', 3),
        negative_dye_count=data.get('negative_dye_count', 0),
    )

    return jsonify({
        'is_valid': result.is_valid,
        'errors': [
            {'field': m.field, 'message': m.message, 'suggestion': m.suggestion}
            for m in result.errors
        ],
        'warnings': [
            {'field': m.field, 'message': m.message, 'suggestion': m.suggestion}
            for m in result.warnings
        ],
    })


@calculator_bp.route('/save', methods=['POST'])
@api_protection(limiter_type="write")
def save_setup():
    """
    Save a reaction setup to database.

    Request body:
        project_id: int
        name: str
        construct_ids: list[int]
        replicates_per_construct: int (default 4, minimum 4)
        created_by: str (optional)
        session_id: int (optional)
        ... (same as calculate endpoint for calculation parameters)

    Returns:
        Created setup ID

    Errors:
        400: If replicates_per_construct < 4 (minimum required for statistical validity)
    """
    data = request.get_json()

    error = validate_required_fields(data, ['project_id', 'name', 'construct_ids'])
    if error:
        return jsonify({'error': error}), 400

    try:
        # Calculate first
        calculation = CalculatorService.calculate_reaction_setup(
            project_id=data['project_id'],
            construct_ids=data['construct_ids'],
            replicates_per_construct=data.get('replicates_per_construct', 4),
            dna_mass_ug=data.get('dna_mass_ug', 20.0),
            overage_percent=data.get('overage_percent', DEFAULT_OVERAGE_PERCENT),
            negative_template_count=data.get('negative_template_count', 3),
            negative_dye_count=data.get('negative_dye_count', 0),
            include_dye=data.get('include_dye', True),
            ntp_concentrations=data.get('ntp_concentrations'),
        )

        if not calculation.is_valid:
            return jsonify({
                'error': 'Calculation is not valid',
                'errors': calculation.errors,
            }), 400

        # Save to database
        setup = CalculatorService.save_reaction_setup(
            project_id=data['project_id'],
            calculation=calculation,
            name=data['name'],
            n_replicates=data.get('replicates_per_construct', 4),
            created_by=data.get('created_by'),
            session_id=data.get('session_id'),
        )

        return jsonify({
            'success': True,
            'setup_id': setup.id,
            'name': setup.name,
        })

    except Exception:
        logger.exception("Unexpected error in save_setup")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@calculator_bp.route('/setups/<int:project_id>', methods=['GET'])
@api_protection(limiter_type="read")
def list_setups(project_id: int):
    """List all reaction setups for a project."""
    setups = CalculatorService.list_reaction_setups(project_id)

    return jsonify({
        'project_id': project_id,
        'setups': [
            {
                'id': s.id,
                'name': s.name,
                'created_at': s.created_at.isoformat() if s.created_at else None,
                'created_by': s.created_by,
                'n_constructs': s.n_constructs,
                'n_replicates': s.n_replicates,
                'session_id': s.session_id,
            }
            for s in setups
        ],
        'count': len(setups),
    })


@calculator_bp.route('/setup/<int:setup_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_setup(setup_id: int):
    """Get a specific reaction setup."""
    setup = CalculatorService.get_reaction_setup(setup_id)

    if not setup:
        return jsonify({'error': 'Setup not found'}), 404

    return jsonify({
        'id': setup.id,
        'name': setup.name,
        'project_id': setup.project_id,
        'created_at': setup.created_at.isoformat() if setup.created_at else None,
        'created_by': setup.created_by,
        'n_constructs': setup.n_constructs,
        'n_replicates': setup.n_replicates,
        'negative_template_count': setup.n_negative_template,
        'negative_dye_count': setup.n_negative_dye,
        'dna_mass_ug': setup.dna_mass_ug,
        'reaction_volume_ul': setup.total_reaction_volume_ul,
        'overage_percent': setup.overage_percent,
        'master_mix_volumes': setup.master_mix_volumes,
        'total_master_mix_volume_ul': setup.total_master_mix_volume_ul,
        'protocol_text': setup.protocol_text,
        'session_id': setup.session_id,
        'dna_additions': [
            {
                'construct_name': dna.construct_name,
                'construct_id': dna.construct_id,
                'is_negative_control': dna.is_negative_control,
                'negative_control_type': dna.negative_control_type,
                'dna_volume_ul': dna.dna_volume_ul,
                'water_adjustment_ul': dna.water_adjustment_ul,
                'total_addition_ul': dna.total_addition_ul,
            }
            for dna in setup.dna_additions
        ],
    })


@calculator_bp.route('/setup/<int:setup_id>/protocol', methods=['GET'])
@api_protection(limiter_type="read")
def export_protocol(setup_id: int):
    """
    Export protocol in specified format.

    Query params:
        format: 'text' or 'csv' (default 'text')
    """
    format_type = request.args.get('format', 'text')

    try:
        content = CalculatorService.export_protocol(setup_id, format=format_type)

        if format_type == 'csv':
            return content, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=protocol_{setup_id}.csv'
            }

        return content, 200, {'Content-Type': 'text/plain'}

    except ValueError as e:
        logger.warning("Value error in export_protocol", error=str(e))
        return jsonify({'error': str(e)}), 404


@calculator_bp.route('/setup/<int:setup_id>/link-session', methods=['POST'])
@api_protection(limiter_type="write")
def link_session(setup_id: int):
    """
    Link a setup to an experimental session.

    Request body:
        session_id: int
    """
    data = request.get_json()

    if not data or 'session_id' not in data:
        return jsonify({'error': 'session_id required'}), 400

    try:
        setup = CalculatorService.link_to_session(setup_id, data['session_id'])
        return jsonify({
            'success': True,
            'setup_id': setup.id,
            'session_id': setup.session_id,
        })
    except ValueError as e:
        logger.warning("Value error in link_session", error=str(e))
        return jsonify({'error': str(e)}), 404


@calculator_bp.route('/dilution', methods=['POST'])
@api_protection(limiter_type="write")
def calculate_dilution():
    """
    Calculate DNA dilution protocol.

    Request body:
        original_concentration_ng_ul: float
        target_concentration_ng_ul: float
        stock_volume_ul: float (optional, default 10)
    """
    data = request.get_json()

    error = validate_required_fields(data, ['original_concentration_ng_ul', 'target_concentration_ng_ul'])
    if error:
        return jsonify({'error': error}), 400

    try:
        protocol = calculate_simple_dilution(
            original_concentration_ng_ul=data['original_concentration_ng_ul'],
            target_concentration_ng_ul=data['target_concentration_ng_ul'],
            stock_volume_ul=data.get('stock_volume_ul', 10.0),
        )

        return jsonify({
            'dilution_factor': protocol.dilution_factor,
            'stock_volume_ul': protocol.stock_volume_ul,
            'diluent_volume_ul': protocol.diluent_volume_ul,
            'final_volume_ul': protocol.final_volume_ul,
            'target_concentration_ng_ul': protocol.target_concentration_ng_ul,
            'is_recommended': protocol.is_recommended,
            'warning': protocol.warning,
            'steps': [
                {
                    'step_number': s.step_number,
                    'action': s.action,
                    'volume_ul': s.volume_ul,
                    'component': s.component,
                    'notes': s.notes,
                }
                for s in protocol.steps
            ],
        })

    except ValueError as e:
        logger.warning("Value error in calculate_dilution", error=str(e))
        return jsonify({'error': str(e)}), 400


@calculator_bp.route('/intervention', methods=['POST'])
@api_protection(limiter_type="write")
def check_intervention():
    """
    Check if volume intervention is needed.

    Request body:
        dna_volume_ul: float
        reaction_volume_ul: float
        dna_stock_ng_ul: float
        dna_stock_available_ul: float (optional)
        plate_format: str ('96' or '384', default '384')
    """
    data = request.get_json()

    error = validate_required_fields(data, ['dna_volume_ul', 'reaction_volume_ul', 'dna_stock_ng_ul'])
    if error:
        return jsonify({'error': error}), 400

    plate_format = PlateFormat.WELL_384 if data.get('plate_format', '384') == '384' else PlateFormat.WELL_96

    intervention = recommend_dna_volume_intervention(
        dna_volume_ul=data['dna_volume_ul'],
        reaction_volume_ul=data['reaction_volume_ul'],
        dna_stock_ng_ul=data['dna_stock_ng_ul'],
        dna_stock_available_ul=data.get('dna_stock_available_ul', 100.0),
        plate_format=plate_format,
    )

    result = {
        'required': intervention.required,
        'intervention_type': intervention.intervention_type.value,
        'warning': intervention.warning,
        'recommended': intervention.recommended,
        'explanation': intervention.explanation,
    }

    if intervention.dilution_option:
        opt = intervention.dilution_option
        result['dilution_option'] = {
            'target_concentration_ng_ul': opt.target_concentration_ng_ul,
            'stock_volume_ul': opt.stock_volume_ul,
            'diluent_volume_ul': opt.diluent_volume_ul,
            'total_diluted_volume_ul': opt.total_diluted_volume_ul,
            'new_dna_volume_ul': opt.new_dna_volume_ul,
            'pros': opt.pros,
            'cons': opt.cons,
        }

    if intervention.scaleup_option:
        opt = intervention.scaleup_option
        result['scaleup_option'] = {
            'new_reaction_volume_ul': opt.new_reaction_volume_ul,
            'scale_factor': opt.scale_factor,
            'new_dna_volume_ul': opt.new_dna_volume_ul,
            'wells_needed': opt.wells_needed,
            'pros': opt.pros,
            'cons': opt.cons,
        }

    return jsonify(result)


@calculator_bp.route('/validate-checkerboard', methods=['POST'])
@api_protection(limiter_type="write")
def validate_checkerboard():
    """
    Validate checkerboard positions for 384-well plates.

    Request body:
        positions: list of {row: int, col: int}
    """
    data = request.get_json()

    if not data or 'positions' not in data:
        return jsonify({'error': 'positions required'}), 400

    results = []
    for pos in data['positions']:
        row = pos.get('row', 0)
        col = pos.get('col', 0)
        valid, msg = validate_checkerboard_position(row, col)
        results.append({
            'row': row,
            'col': col,
            'valid': valid,
            'message': msg,
        })

    all_valid = all(r['valid'] for r in results)

    return jsonify({
        'all_valid': all_valid,
        'positions': results,
    })


def register_calculator_api(app):
    """Register the calculator API blueprint with the Flask app."""
    app.register_blueprint(calculator_bp)
