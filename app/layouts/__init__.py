"""Dash page layouts using Mantine components."""
from app.layouts.main_layout import create_main_layout
from app.layouts.project_list import (
    create_project_list_layout,
    create_project_card,
    create_empty_projects_message
)
from app.layouts.project_dashboard import (
    create_project_dashboard_layout,
    create_activity_item
)
from app.layouts.hub import (
    create_hub_layout,
    create_workflow_steps_grid,
    create_progress_summary,
    create_quick_actions_panel,
    create_hub_loading_state,
    WORKFLOW_STEPS,
)
from app.layouts.project_settings import create_project_settings_layout
from app.layouts.calculator import (
    create_calculator_layout,
    create_recommendation_card,
    create_selected_construct_item,
)
from app.layouts.repair_wizard import (
    create_repair_wizard_modal,
    create_step1_preview,
    create_step2_header_row,
    create_step3_skip_rows,
    create_step4_column_mapping,
    create_step5_preview_data,
    create_repair_wizard_error,
)
from app.layouts.negative_control_dashboard import (
    create_negative_control_dashboard,
    create_background_summary_table,
    create_detection_limits_display,
    create_detection_status_display,
    create_background_timeseries_plot,
    create_plate_heatmap,
    create_empty_dashboard_message,
)
from app.layouts.curve_browser import (
    create_curve_browser_layout,
    create_well_grid_item,
    create_well_details_panel,
    create_fit_params_panel,
    create_empty_plot_message,
)
from app.layouts.analysis_results import (
    create_analysis_results_layout,
    create_posterior_table,
    create_probability_display,
    create_variance_pie_chart,
    create_diagnostics_panel,
    create_correlations_panel,
    create_empty_results_message,
    # Curve fitting workflow (Phase 4)
    create_curve_fitting_workflow,
    create_step2_fitting_progress,
    create_step3_fit_results,
    create_step4_fold_changes,
    create_curve_fit_plot,
    create_fit_params_display,
    create_fit_quality_histogram,
    create_plate_checkbox_item,
)
from app.layouts.precision_dashboard import (
    create_precision_dashboard_layout,
    create_precision_table_simple,
    create_precision_table_advanced,
    create_sparkline,
    create_overall_progress,
    create_recommendations_panel,
    create_precision_history_chart,
)
from app.layouts.cross_project_comparison import (
    create_cross_project_comparison_layout,
    create_project_checkbox_item,
    create_summary_table,
)
from app.layouts.plate_templates import (
    create_plate_templates_layout,
    create_plate_templates_header,
    create_layout_info_panel,
    create_layout_editor_section,
    create_layout_summary_panel,
    create_plate_templates_loading_state,
    WELL_TYPE_OPTIONS,
)
from app.layouts.data_upload import (
    create_upload_layout,
    create_upload_header,
    create_file_upload_panel,
    create_layout_selection_panel,
    create_validation_panel,
    create_session_panel,
    create_temperature_warning,
    create_upload_loading_state,
    TEMPERATURE_QC_THRESHOLD,
)
# Phase C: Construct registry
from app.layouts.construct_registry import (
    create_construct_registry_layout,
    create_construct_form,
    create_construct_table,
    create_construct_cards,
    create_family_summary,
    create_unregulated_selector,
    create_construct_registry_skeleton,
)
# Phase C: Power analysis
from app.layouts.power_analysis import (
    create_power_analysis_layout,
    create_planning_section,
    create_sample_size_calculator,
    create_power_curve_display,
    create_sample_size_result,
    create_power_analysis_skeleton,
)

__all__ = [
    # Main layout
    "create_main_layout",
    # Project list
    "create_project_list_layout",
    "create_project_card",
    "create_empty_projects_message",
    # Project dashboard
    "create_project_dashboard_layout",
    "create_activity_item",
    # Hub (Phase 1)
    "create_hub_layout",
    "create_workflow_steps_grid",
    "create_progress_summary",
    "create_quick_actions_panel",
    "create_hub_loading_state",
    "WORKFLOW_STEPS",
    # Project settings
    "create_project_settings_layout",
    # Calculator
    "create_calculator_layout",
    "create_recommendation_card",
    "create_selected_construct_item",
    # Repair wizard
    "create_repair_wizard_modal",
    "create_step1_preview",
    "create_step2_header_row",
    "create_step3_skip_rows",
    "create_step4_column_mapping",
    "create_step5_preview_data",
    "create_repair_wizard_error",
    # Negative control dashboard
    "create_negative_control_dashboard",
    "create_background_summary_table",
    "create_detection_limits_display",
    "create_detection_status_display",
    "create_background_timeseries_plot",
    "create_plate_heatmap",
    "create_empty_dashboard_message",
    # Curve browser
    "create_curve_browser_layout",
    "create_well_grid_item",
    "create_well_details_panel",
    "create_fit_params_panel",
    "create_empty_plot_message",
    # Analysis results
    "create_analysis_results_layout",
    "create_posterior_table",
    "create_probability_display",
    "create_variance_pie_chart",
    "create_diagnostics_panel",
    "create_correlations_panel",
    "create_empty_results_message",
    # Curve fitting workflow (Phase 4)
    "create_curve_fitting_workflow",
    "create_step2_fitting_progress",
    "create_step3_fit_results",
    "create_step4_fold_changes",
    "create_curve_fit_plot",
    "create_fit_params_display",
    "create_fit_quality_histogram",
    "create_plate_checkbox_item",
    # Precision dashboard
    "create_precision_dashboard_layout",
    "create_precision_table_simple",
    "create_precision_table_advanced",
    "create_sparkline",
    "create_overall_progress",
    "create_recommendations_panel",
    "create_precision_history_chart",
    # Cross-project comparison (Sprint 8)
    "create_cross_project_comparison_layout",
    "create_project_checkbox_item",
    "create_summary_table",
    # Plate templates (Phase 2)
    "create_plate_templates_layout",
    "create_plate_templates_header",
    "create_layout_info_panel",
    "create_layout_editor_section",
    "create_layout_summary_panel",
    "create_plate_templates_loading_state",
    "WELL_TYPE_OPTIONS",
    # Data upload (Phase 3)
    "create_upload_layout",
    "create_upload_header",
    "create_file_upload_panel",
    "create_layout_selection_panel",
    "create_validation_panel",
    "create_session_panel",
    "create_temperature_warning",
    "create_upload_loading_state",
    "TEMPERATURE_QC_THRESHOLD",
    # Construct registry (Phase C)
    "create_construct_registry_layout",
    "create_construct_form",
    "create_construct_table",
    "create_construct_cards",
    "create_family_summary",
    "create_unregulated_selector",
    "create_construct_registry_skeleton",
    # Power analysis (Phase C)
    "create_power_analysis_layout",
    "create_planning_section",
    "create_sample_size_calculator",
    "create_power_curve_display",
    "create_sample_size_result",
    "create_power_analysis_skeleton",
]
