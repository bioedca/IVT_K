"""Smart Planner API endpoints.

Phase 2.5: Smart Experiment Planner REST API.
Phase 3.3: Rate limiting applied consistently
"""
from flask import Blueprint, jsonify, request
from typing import Dict, Any

from app.services import SmartPlannerService, SmartPlannerError
from app.api.middleware import api_protection
from app.logging_config import get_logger
from app.utils.validation import parse_bool_param, validate_non_empty_list
from app.calculator import (
    PlannerMode,
    ConstructStats,
    ConstructRecommendation,
)

logger = get_logger(__name__)

smart_planner_bp = Blueprint('smart_planner', __name__, url_prefix='/api/smart-planner')


def construct_recommendation_to_dict(rec: ConstructRecommendation) -> Dict[str, Any]:
    """Convert ConstructRecommendation to API response dict."""
    return {
        'construct_id': rec.construct_id,
        'name': rec.name,
        'family': rec.family,
        'is_wildtype': rec.is_wildtype,
        'is_anchor': rec.is_anchor,
        'total_score': round(rec.total_score, 2),
        'precision_gap_score': round(rec.precision_gap_score, 2),
        'untested_score': round(rec.untested_score, 2),
        'coplating_score': round(rec.coplating_score, 2),
        'brief_reason': rec.brief_reason,
        'detailed_reason': rec.detailed_reason,
        'current_ci_width': round(rec.current_ci_width, 4) if rec.current_ci_width else None,
        'target_ci_width': round(rec.target_ci_width, 4),
        'replicates_needed': rec.replicates_needed,
        'plates_estimate': rec.plates_estimate,
    }


@smart_planner_bp.route('/projects/<int:project_id>/summary', methods=['GET'])
@api_protection(limiter_type="read")
def get_project_summary(project_id: int):
    """
    Get project summary for smart planner.

    Returns overview of project state including construct counts,
    planner mode, and constraint validation.
    """
    try:
        summary = SmartPlannerService.get_project_summary(project_id)
        return jsonify(summary)
    except SmartPlannerError as e:
        logger.warning("Smart planner error in get_project_summary", error=str(e))
        return jsonify({'error': str(e)}), 404
    except Exception:
        logger.exception("Unexpected error in get_project_summary")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/mode', methods=['GET'])
@api_protection(limiter_type="read")
def detect_mode(project_id: int):
    """
    Detect planner mode for project.

    Returns 'first_experiment' for new projects without data,
    'normal' for projects with existing data.
    """
    try:
        mode = SmartPlannerService.detect_planner_mode(project_id)
        return jsonify({
            'mode': mode.value,
            'description': 'New project - use First Experiment Wizard' if mode == PlannerMode.FIRST_EXPERIMENT else 'Project with data - use recommendations'
        })
    except Exception:
        logger.exception("Unexpected error in detect_mode")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/constraints', methods=['GET'])
@api_protection(limiter_type="read")
def validate_constraints(project_id: int):
    """
    Validate project constraints for smart planning.

    Checks for required reporter-only construct and WT per family.
    """
    try:
        validation = SmartPlannerService.validate_project_constraints(project_id)
        return jsonify({
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings,
            'has_reporter_only': validation.has_reporter_only,
            'has_wildtype_per_family': validation.has_wildtype_per_family,
        })
    except Exception:
        logger.exception("Unexpected error in validate_constraints")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/first-experiment', methods=['GET'])
@api_protection(limiter_type="read")
def get_first_experiment_suggestion(project_id: int):
    """
    Get first experiment suggestion for new project.

    Returns recommended setup with reporter-only and WT constructs.
    """
    try:
        replicates = request.args.get('replicates', 4, type=int)
        suggestion = SmartPlannerService.get_first_experiment_suggestion(
            project_id, replicates
        )

        return jsonify({
            'reporter_only': {
                'construct_id': suggestion.reporter_only.construct_id,
                'name': suggestion.reporter_only.name,
            } if suggestion.reporter_only else None,
            'wildtype': {
                'construct_id': suggestion.wildtype.construct_id,
                'name': suggestion.wildtype.name,
                'family': suggestion.wildtype.family,
            } if suggestion.wildtype else None,
            'negative_template_count': suggestion.negative_template_count,
            'negative_dye_count': suggestion.negative_dye_count,
            'total_wells': suggestion.total_wells,
            'replicates_per_construct': suggestion.replicates_per_construct,
            'rationale': suggestion.rationale,
        })
    except Exception:
        logger.exception("Unexpected error in get_first_experiment_suggestion")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/recommendations', methods=['GET'])
@api_protection(limiter_type="read")
def get_recommendations(project_id: int):
    """
    Get ranked construct recommendations.

    Returns constructs sorted by recommendation score based on
    precision gaps, untested status, and co-plating benefits.
    """
    try:
        max_recs = request.args.get('max', 10, type=int)
        uploaded_only = parse_bool_param(request.args.get('uploaded_only'), default=True)

        recommendations = SmartPlannerService.get_recommendations(
            project_id, max_recs, uploaded_only
        )

        return jsonify({
            'recommendations': [
                construct_recommendation_to_dict(rec)
                for rec in recommendations
            ]
        })
    except Exception:
        logger.exception("Unexpected error in get_recommendations")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/constructs', methods=['GET'])
@api_protection(limiter_type="read")
def get_construct_stats(project_id: int):
    """
    Get construct statistics for project.

    Returns all constructs with their current precision metrics.
    """
    try:
        uploaded_only = parse_bool_param(request.args.get('uploaded_only'), default=False)

        stats = SmartPlannerService.get_construct_stats(project_id, uploaded_only)

        return jsonify({
            'constructs': [
                {
                    'construct_id': s.construct_id,
                    'name': s.name,
                    'family': s.family,
                    'is_wildtype': s.is_wildtype,
                    'is_unregulated': s.is_unregulated,
                    'replicate_count': s.replicate_count,
                    'ci_width': round(s.ci_width, 4) if s.ci_width else None,
                    'has_data': s.has_data,
                    'meets_precision_target': s.meets_precision_target,
                }
                for s in stats
            ]
        })
    except Exception:
        logger.exception("Unexpected error in get_construct_stats")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/plan', methods=['POST'])
@api_protection(limiter_type="write")
def create_experiment_plan(project_id: int):
    """
    Create an experiment plan from selected constructs.

    Request body:
    {
        "construct_ids": [1, 2, 3],
        "replicates": 4,
        "include_dfhbi": true  // optional override
    }

    Returns complete plan with auto-added anchors and validation.
    """
    try:
        data = request.get_json() or {}
        construct_ids = data.get('construct_ids', [])
        replicates = data.get('replicates', 4)
        include_dfhbi = data.get('include_dfhbi')  # None = use recommendation

        error = validate_non_empty_list(construct_ids, "construct_ids")
        if error:
            return jsonify({'error': error}), 400

        plan = SmartPlannerService.create_experiment_plan(
            project_id, construct_ids, replicates, include_dfhbi
        )

        return jsonify({
            'constructs': [
                construct_recommendation_to_dict(c) for c in plan.constructs
            ],
            'auto_added_anchors': [
                construct_recommendation_to_dict(c) for c in plan.auto_added_anchors
            ],
            'negative_template_count': plan.negative_template_count,
            'negative_dye_count': plan.negative_dye_count,
            'dfhbi_recommendation': {
                'include': plan.dfhbi_recommendation.include,
                'confidence': plan.dfhbi_recommendation.confidence.value,
                'reason': plan.dfhbi_recommendation.reason,
                'recent_control_count': plan.dfhbi_recommendation.recent_control_count,
                'recent_mean_signal': plan.dfhbi_recommendation.recent_mean_signal,
            },
            'total_wells': plan.total_wells,
            'total_templates': plan.total_templates,
            'template_limit_exceeded': plan.template_limit_exceeded,
            'capacity_exceeded': plan.capacity_exceeded,
            'warnings': plan.warnings,
        })
    except SmartPlannerError as e:
        logger.warning("Smart planner error in create_experiment_plan", error=str(e))
        return jsonify({'error': str(e)}), 400
    except Exception:
        logger.exception("Unexpected error in create_experiment_plan")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/impact', methods=['POST'])
@api_protection(limiter_type="write")
def calculate_impact_preview(project_id: int):
    """
    Preview impact of proposed experiment.

    Request body:
    {
        "construct_ids": [1, 2, 3],
        "additional_replicates": 4
    }

    Returns precision improvements and construct coverage gains.
    """
    try:
        data = request.get_json() or {}
        construct_ids = data.get('construct_ids', [])
        additional_replicates = data.get('additional_replicates', 4)

        error = validate_non_empty_list(construct_ids, "construct_ids")
        if error:
            return jsonify({'error': error}), 400

        impact = SmartPlannerService.calculate_impact_preview(
            project_id, construct_ids, additional_replicates
        )

        return jsonify({
            'constructs_before': impact.constructs_before,
            'constructs_after': impact.constructs_after,
            'constructs_gained': impact.constructs_gained,
            'plates_to_target_before': impact.plates_to_target_before,
            'plates_to_target_after': impact.plates_to_target_after,
            'plates_saved': impact.plates_saved,
            'precision_improvement_pct': round(impact.precision_improvement_pct, 1),
            'per_construct_impact': impact.per_construct_impact,
        })
    except Exception:
        logger.exception("Unexpected error in calculate_impact_preview")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/setups/<int:setup_id>/link', methods=['POST'])
@api_protection(limiter_type="write")
def link_setup_to_session(setup_id: int):
    """
    Link a reaction setup to an experimental session.

    Request body:
    {
        "session_id": 123
    }

    F4.21: Mandatory linkage for audit trail.
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'error': 'session_id required'}), 400

        setup = SmartPlannerService.link_setup_to_session(setup_id, session_id)

        return jsonify({
            'setup_id': setup.id,
            'session_id': setup.session_id,
            'linked_at': setup.updated_at.isoformat() if setup.updated_at else None,
        })
    except SmartPlannerError as e:
        logger.warning("Smart planner error in link_setup_to_session", error=str(e))
        return jsonify({'error': str(e)}), 400
    except Exception:
        logger.exception("Unexpected error in link_setup_to_session")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


@smart_planner_bp.route('/projects/<int:project_id>/unlinked-setups', methods=['GET'])
@api_protection(limiter_type="read")
def get_unlinked_setups(project_id: int):
    """
    Get reaction setups not yet linked to a session.

    Used to prompt users to link setups when creating sessions.
    """
    try:
        setups = SmartPlannerService.get_unlinked_setups(project_id)

        return jsonify({
            'setups': [
                {
                    'id': s.id,
                    'name': s.name,
                    'created_by': s.created_by,
                    'created_at': s.created_at.isoformat() if s.created_at else None,
                    'n_constructs': s.n_constructs,
                    'n_replicates': s.n_replicates,
                    'total_wells': (
                        s.n_constructs * s.n_replicates +
                        s.n_negative_template +
                        s.n_negative_dye
                    ),
                }
                for s in setups
            ]
        })
    except Exception:
        logger.exception("Unexpected error in get_unlinked_setups")
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500


def register_smart_planner_api(app):
    """Register smart planner API blueprint with app."""
    app.register_blueprint(smart_planner_bp)
