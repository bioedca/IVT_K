"""Analysis results layout package.

Split from monolithic analysis_results.py for maintainability.
All public functions are re-exported here for backwards compatibility.
"""
from app.layouts.analysis_results.main_layout import create_analysis_results_layout
from app.layouts.analysis_results.workflow import (
    create_curve_fitting_workflow,
    _create_step1_plate_selection,
    _create_step1_plate_selection_filtered,
    create_step2_fitting_progress,
    create_step3_fit_results,
    create_step4_fold_changes,
    create_plate_checkbox_item,
)
from app.layouts.analysis_results.fitting_views import (
    create_curve_fit_plot,
    create_fit_params_display,
    build_fit_results_table,
    create_multi_well_curve_plot,
    create_multi_well_params_table,
    create_fit_quality_histogram,
    build_fold_change_table,
)
from app.layouts.analysis_results.result_tables import (
    create_posterior_table,
    create_frequentist_table,
    create_comparison_table,
    create_method_info_panel,
    create_probability_display,
    create_variance_pie_chart,
)
from app.layouts.analysis_results.diagnostics import (
    create_diagnostics_panel,
    create_correlations_panel,
    create_icc_display,
    create_empty_results_message,
    create_assumption_tests_display,
    create_effect_size_display,
    create_corrected_pvalues_table,
    create_qq_plot_for_residuals,
    create_empty_diagnostics,
    create_diagnostics_warnings_panel,
)
from app.layouts.analysis_results.cross_family import (
    create_cross_family_precomputed_table,
    create_cross_family_mutant_table,
    create_custom_comparison_result,
    create_empty_cross_family,
)
from app.layouts.analysis_results.components import (
    get_ligand_condition_badge,
    get_vif_badge,
    _format_with_se,
)

__all__ = [
    # Main layout
    "create_analysis_results_layout",
    # Workflow
    "create_curve_fitting_workflow",
    "_create_step1_plate_selection",
    "_create_step1_plate_selection_filtered",
    "create_step2_fitting_progress",
    "create_step3_fit_results",
    "create_step4_fold_changes",
    "create_plate_checkbox_item",
    # Fitting views
    "create_curve_fit_plot",
    "create_fit_params_display",
    "build_fit_results_table",
    "create_multi_well_curve_plot",
    "create_multi_well_params_table",
    "create_fit_quality_histogram",
    "build_fold_change_table",
    # Result tables
    "create_posterior_table",
    "create_frequentist_table",
    "create_comparison_table",
    "create_method_info_panel",
    "create_probability_display",
    "create_variance_pie_chart",
    # Diagnostics
    "create_diagnostics_panel",
    "create_correlations_panel",
    "create_icc_display",
    "create_empty_results_message",
    "create_assumption_tests_display",
    "create_effect_size_display",
    "create_corrected_pvalues_table",
    "create_qq_plot_for_residuals",
    "create_empty_diagnostics",
    "create_diagnostics_warnings_panel",
    # Cross-family
    "create_cross_family_precomputed_table",
    "create_cross_family_mutant_table",
    "create_custom_comparison_result",
    "create_empty_cross_family",
    # Components
    "get_ligand_condition_badge",
    "get_vif_badge",
    "_format_with_se",
]
