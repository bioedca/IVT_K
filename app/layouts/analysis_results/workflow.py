"""Curve fitting workflow components: stepper, plate selection, progress, results, fold changes."""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify
import plotly.graph_objects as go

from app.theme import apply_plotly_theme
from app.layouts.analysis_results.fitting_views import (
    build_fit_results_table,
    create_fit_quality_histogram,
    create_multi_well_curve_plot,
    create_multi_well_params_table,
    build_fold_change_table,
)


def create_curve_fitting_workflow(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the curve fitting workflow section.

    This section allows users to:
    - Select plates to fit
    - Start curve fitting via Huey background task
    - View progress
    - See raw + fit data with parameters
    - Navigate to fold change calculation and hierarchical model

    Args:
        project_id: Optional project ID

    Returns:
        Curve fitting workflow layout
    """
    return html.Div([
        # Workflow header
        dmc.Paper([
            dmc.Group([
                dmc.Group([
                    DashIconify(icon="mdi:chart-bell-curve-cumulative", width=28, color="#228be6"),
                    dmc.Title("Curve Fitting Workflow", order=3),
                ], gap="sm"),
                dmc.Badge(
                    id="fitting-status-badge",
                    children="Not Started",
                    color="gray",
                    size="lg",
                ),
            ], justify="space-between"),
            dmc.Text(
                "Fit kinetic models to fluorescence data. Negative controls are used for "
                "baselining only and are not fitted. Sample wells are fitted with the delayed "
                "exponential model.",
                c="dimmed", size="sm", mt="xs"
            ),
        ], p="md", mb="md", withBorder=True),

        # Workflow steps stepper (non-clickable, display only)
        dmc.Stepper(
            id="fitting-workflow-stepper",
            active=0,
            allowNextStepsSelect=False,  # Prevent clicking to navigate
            children=[
                dmc.StepperStep(
                    label="Select Plates",
                    description="Choose plates to fit",
                    icon=DashIconify(icon="mdi:view-grid-plus"),
                ),
                dmc.StepperStep(
                    label="Fit Curves",
                    description="Run curve fitting",
                    icon=DashIconify(icon="mdi:chart-bell-curve"),
                ),
                dmc.StepperStep(
                    label="Review Results",
                    description="View fit quality",
                    icon=DashIconify(icon="mdi:magnify-scan"),
                ),
                dmc.StepperStep(
                    label="Compute Fold Changes",
                    description="Calculate FC vs controls",
                    icon=DashIconify(icon="mdi:calculator-variant"),
                ),
            ],
            mb="md",
        ),

        # Step content container - populated by callback on page load
        html.Div(id="fitting-step-content", children=[
            dmc.Center([
                dmc.Loader(size="lg"),
            ], style={"minHeight": "200px"}),
        ]),

        # Note: All hidden placeholders for Steps 1-4 are in create_analysis_results_layout
        # to persist across step changes and accordion state
    ])


def _create_step1_plate_selection(
    project_id: Optional[int] = None,
    preselect_plate_ids: Optional[set] = None,
    session_filter: Optional[str] = None,
    model_type: Optional[str] = None,
) -> html.Div:
    """Create Step 1: Plate selection UI with optional pre-selected plates."""
    from app.models import Plate, Well, ExperimentalSession
    from app.models.experiment import QCStatus
    from app.models.plate_layout import WellType
    from app.models.fit_result import FitResult

    preselect_plate_ids = preselect_plate_ids or set()

    # Load plate data
    plate_items = []
    session_options = []
    plate_count = "0 plates"

    if project_id:
        try:
            # Get sessions for filter dropdown
            sessions = ExperimentalSession.query.filter_by(
                project_id=project_id
            ).order_by(ExperimentalSession.date.desc()).all()

            for s in sessions:
                label = f"{s.batch_identifier} ({s.date})"
                if s.qc_status == QCStatus.REJECTED:
                    label += " [QC Rejected]"
                session_options.append({"value": str(s.id), "label": label})

            # Query plates with optional session filter
            plates_query = Plate.query.join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id
            )
            if session_filter:
                try:
                    session_id = int(session_filter)
                    plates_query = plates_query.filter(ExperimentalSession.id == session_id)
                except ValueError:
                    pass  # Invalid filter value, ignore

            plates = plates_query.order_by(ExperimentalSession.date.desc(), Plate.plate_number).all()

            plate_count = f"{len(plates)} plates"

            for plate in plates:
                is_qc_rejected = plate.session and plate.session.qc_status == QCStatus.REJECTED

                sample_wells = Well.query.filter(
                    Well.plate_id == plate.id,
                    Well.well_type == WellType.SAMPLE,
                    Well.is_excluded == False
                ).count()

                negative_wells = Well.query.filter(
                    Well.plate_id == plate.id,
                    Well.well_type.in_([
                        WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                        WellType.NEGATIVE_CONTROL_NO_DYE,
                        WellType.BLANK
                    ])
                ).count()

                fitted_count = Well.query.join(FitResult).filter(
                    Well.plate_id == plate.id,
                    Well.well_type == WellType.SAMPLE,
                    FitResult.converged == True
                ).count()

                total_wells = Well.query.filter(Well.plate_id == plate.id).count()
                session_label = f"{plate.session.batch_identifier}" if plate.session else "Unknown"

                plate_items.append(
                    create_plate_checkbox_item(
                        plate_id=plate.id,
                        plate_name=f"Plate {plate.plate_number}",
                        session_name=session_label,
                        well_count=total_wells,
                        fitted_count=fitted_count,
                        sample_count=sample_wells,
                        negative_count=negative_wells,
                        is_qc_rejected=is_qc_rejected,
                        checked=plate.id in preselect_plate_ids,
                    )
                )
        except Exception as e:
            plate_items = [dmc.Text(f"Error loading plates: {e}", c="red")]

    if not plate_items:
        plate_items = [dmc.Text("No plates found", c="dimmed", ta="center")]

    return html.Div([
        dmc.Grid([
            # Left: Plate selection
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Available Plates", fw=500),
                        dmc.Badge(
                            id="fitting-plate-count-badge",
                            children=plate_count,
                            color="blue",
                            size="sm",
                            variant="light",
                        ),
                    ], justify="space-between", mb="sm"),

                    # Session filter
                    dmc.Select(
                        id="fitting-session-filter",
                        label="Filter by Session",
                        placeholder="All sessions",
                        data=session_options,
                        value=session_filter,
                        clearable=True,
                        mb="sm",
                    ),

                    # Plate list with checkboxes
                    dmc.ScrollArea(
                        id="fitting-plate-scroll",
                        h=300,
                        children=[
                            dmc.Stack(
                                id="fitting-plate-list",
                                gap="xs",
                                children=plate_items,
                            ),
                        ],
                    ),

                    # Selection controls
                    dmc.Group([
                        dmc.Button(
                            "Select All",
                            id="fitting-select-all-btn",
                            variant="subtle",
                            size="xs",
                        ),
                        dmc.Button(
                            "Clear All",
                            id="fitting-clear-all-btn",
                            variant="subtle",
                            size="xs",
                        ),
                    ], mt="sm"),
                ], p="md", withBorder=True),
            ], span=6),

            # Right: Selection summary and fitting options
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Selection Summary", fw=500, mb="sm"),

                    # Summary stats
                    dmc.Stack([
                        dmc.Group([
                            dmc.Text("Selected Plates:", size="sm", c="dimmed"),
                            dmc.Text(id="fitting-selected-plates-count", children="0", fw=500),
                        ], justify="space-between"),
                        dmc.Group([
                            dmc.Text("Sample Wells:", size="sm", c="dimmed"),
                            dmc.Text(id="fitting-sample-wells-count", children="0", fw=500),
                        ], justify="space-between"),
                        dmc.Group([
                            dmc.Text("Negative Controls:", size="sm", c="dimmed"),
                            dmc.Text(id="fitting-negative-controls-count", children="0", fw=500, c="orange"),
                        ], justify="space-between"),
                        dmc.Group([
                            dmc.Text("Already Fitted:", size="sm", c="dimmed"),
                            dmc.Text(id="fitting-already-fitted-count", children="0", fw=500, c="green"),
                        ], justify="space-between"),
                    ], gap="xs", mb="md"),

                    dmc.Divider(my="md"),

                    # Fitting options
                    dmc.Text("Fitting Options", fw=500, mb="sm"),

                    dmc.Select(
                        id="fitting-model-select",
                        label="Kinetic Model",
                        data=[
                            {"value": "delayed_exponential", "label": "Delayed Exponential (Recommended)"},
                            {"value": "logistic", "label": "Logistic (Diagnostic)"},
                            {"value": "double_exponential", "label": "Double Exponential (Diagnostic)"},
                        ],
                        value=model_type or "delayed_exponential",
                        mb="sm",
                    ),

                    dmc.Checkbox(
                        id="fitting-force-refit-checkbox",
                        label="Force refit (overwrite existing fits)",
                        checked=False,
                        mb="md",
                    ),

                    dmc.Alert(
                        title="Note",
                        children="Alternative models (logistic, double exponential) are for diagnostics only. "
                                 "Only delayed exponential parameters are used in the hierarchical analysis.",
                        color="blue",
                        icon=DashIconify(icon="mdi:information"),
                        variant="light",
                        mb="md",
                    ),

                    # Start fitting button
                    dmc.Button(
                        "Start Curve Fitting",
                        id="fitting-start-btn",
                        leftSection=DashIconify(icon="mdi:play"),
                        fullWidth=True,
                        disabled=True,
                    ),
                ], p="md", withBorder=True),
            ], span=6),
        ]),
    ])


def _create_step1_plate_selection_filtered(
    project_id: int,
    session_filter: Optional[str] = None
) -> html.Div:
    """Create Step 1 with session filter applied (for re-rendering on filter change)."""
    return _create_step1_plate_selection(
        project_id=project_id,
        preselect_plate_ids=set(),
        session_filter=session_filter
    )


def create_step2_fitting_progress() -> html.Div:
    """Create Step 2: Fitting progress UI."""
    return html.Div([
        dmc.Paper([
            dmc.Group([
                dmc.Text("Curve Fitting in Progress", fw=500),
                dmc.Loader(size="sm", type="dots"),
            ], gap="sm", mb="md"),

            dmc.Progress(
                id="fitting-progress-bar",
                value=0,
                size="xl",
                animated=True,
                mb="sm",
            ),

            dmc.Group([
                dmc.Text(id="fitting-progress-text", children="Initializing...", c="dimmed", size="sm"),
                dmc.Text(id="fitting-progress-eta", children="", c="dimmed", size="sm"),
            ], justify="space-between", mb="md"),

            # Live stats
            dmc.Grid([
                dmc.GridCol([
                    dmc.Paper([
                        dmc.Text("Fitted", size="xs", c="dimmed", ta="center"),
                        dmc.Text(id="fitting-live-success", children="0", size="xl", fw=700, ta="center", c="green"),
                    ], p="sm", withBorder=True),
                ], span=4),
                dmc.GridCol([
                    dmc.Paper([
                        dmc.Text("Failed", size="xs", c="dimmed", ta="center"),
                        dmc.Text(id="fitting-live-failed", children="0", size="xl", fw=700, ta="center", c="red"),
                    ], p="sm", withBorder=True),
                ], span=4),
                dmc.GridCol([
                    dmc.Paper([
                        dmc.Text("Skipped", size="xs", c="dimmed", ta="center"),
                        dmc.Text(id="fitting-live-skipped", children="0", size="xl", fw=700, ta="center", c="yellow"),
                    ], p="sm", withBorder=True),
                ], span=4),
            ], mb="md"),

            dmc.Alert(
                children="You can close this page. Fitting will continue in the background.",
                color="blue",
                icon=DashIconify(icon="mdi:information"),
                variant="light",
            ),
        ], p="md", withBorder=True),
        # Note: fitting-task-id-store and fitting-progress-interval are at top level in create_analysis_results_layout
    ])


def create_step3_fit_results(
    fit_summary: Optional[Dict[str, Any]] = None,
    project_id: Optional[int] = None,
    selected_well_ids: Optional[List[int]] = None,
    plate_ids: Optional[List[int]] = None,
    dark_mode: bool = False,
) -> html.Div:
    """
    Create Step 3: Fit results review UI.

    Renders complete content including table, histogram, and curve viewer.
    No callbacks needed to populate - everything is rendered directly.

    Args:
        fit_summary: Optional dict with keys: successful, failed, skipped, total
        project_id: Project ID to load fit results from
        selected_well_ids: List of selected well IDs for curve viewer
        plate_ids: Optional list of plate IDs to filter results (from explore panel)
        dark_mode: Whether to apply dark theme to Plotly figures
    """
    # Extract stats from summary or use defaults
    stats = fit_summary or {}
    successful = stats.get("successful", 0)
    failed = stats.get("failed", 0)
    skipped = stats.get("skipped", 0)
    total = successful + failed + skipped

    # Build results table and histogram if we have a project
    results_table_content = dmc.Text("Loading...", c="dimmed", ta="center")
    histogram_fig = go.Figure()
    apply_plotly_theme(histogram_fig, dark_mode=dark_mode)
    curve_fig = go.Figure()
    apply_plotly_theme(curve_fig, dark_mode=dark_mode)
    params_table_content = dmc.Text("Select wells from table", c="dimmed", ta="center")
    selection_count_text = "Select wells from table"
    n_selected_wells = 0  # Track for dynamic graph height

    if project_id:
        try:
            from app.models import Well, Plate, ExperimentalSession
            from app.models.plate_layout import WellType
            from app.models.fit_result import FitResult

            # Get fit results for SAMPLE wells
            query = FitResult.query.join(Well).join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id,
                FitResult.converged == True,
                Well.well_type == WellType.SAMPLE
            )

            # Filter by plate_ids if provided
            if plate_ids:
                query = query.filter(Well.plate_id.in_(plate_ids))

            fits = query.order_by(Plate.plate_number, Well.position).all()

            if fits:
                # Get valid well IDs from the filtered fits
                valid_well_ids = {fit.well.id for fit in fits}

                # Filter selected wells to only include those in the current view
                if selected_well_ids:
                    selected_well_ids = [wid for wid in selected_well_ids if wid in valid_well_ids]

                # Auto-select first well if none selected (or all were filtered out)
                if not selected_well_ids:
                    selected_well_ids = [fits[0].well.id]

                # Build results table
                results_table_content = build_fit_results_table(fits, selected_well_ids)

                # Build histogram
                r_squared_values = [f.r_squared for f in fits if f.r_squared is not None]
                histogram_fig = create_fit_quality_histogram(r_squared_values, dark_mode=dark_mode)

                # Build curve viewer for selected wells
                if selected_well_ids:
                    from app.services.fitting_service import FittingService
                    all_fit_data = []
                    for well_id in selected_well_ids:
                        try:
                            fit_data = FittingService.get_well_fit_data(int(well_id))
                            if fit_data:
                                all_fit_data.append(fit_data)
                        except Exception:
                            pass

                    if all_fit_data:
                        curve_fig = create_multi_well_curve_plot(all_fit_data, dark_mode=dark_mode)
                        params_table_content = create_multi_well_params_table(all_fit_data)
                        n_selected_wells = len(all_fit_data)

                    count = len(selected_well_ids)
                    selection_count_text = f"{count} well{'s' if count != 1 else ''} selected"
            else:
                results_table_content = dmc.Text("No fit results available", c="dimmed", ta="center")

        except Exception as e:
            print(f"Error loading Step 3 content: {e}")
            import traceback
            traceback.print_exc()
            results_table_content = dmc.Text("Error loading results", c="red", ta="center")

    # Get R\u00b2 exclusion preview for the filter panel
    r2_preview = {"below_threshold": 0, "total_wells": total}
    current_threshold = 0.80
    if project_id:
        try:
            from app.services.fitting_service import FittingService
            r2_preview = FittingService.get_r2_exclusion_preview(project_id, current_threshold)
        except Exception:
            pass

    return html.Div([
        # Summary stats row - values are embedded directly
        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Successful", size="xs", c="dimmed", ta="center"),
                    dmc.Text(str(successful), size="xl", fw=700, ta="center", c="green"),
                ], p="sm", withBorder=True),
            ], span=3),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Failed", size="xs", c="dimmed", ta="center"),
                    dmc.Text(str(failed), size="xl", fw=700, ta="center", c="red"),
                ], p="sm", withBorder=True),
            ], span=3),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Skipped", size="xs", c="dimmed", ta="center"),
                    dmc.Text(str(skipped), size="xl", fw=700, ta="center", c="yellow"),
                ], p="sm", withBorder=True),
            ], span=3),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Total Samples", size="xs", c="dimmed", ta="center"),
                    dmc.Text(str(total), size="xl", fw=700, ta="center"),
                ], p="sm", withBorder=True),
            ], span=3),
        ], mb="md"),

        # R\u00b2 Quality Filter Panel
        dmc.Paper([
            dmc.Group([
                dmc.Group([
                    DashIconify(icon="mdi:filter-check", width=20, color="#228be6"),
                    dmc.Text("R\u00b2 Quality Filter", fw=500),
                ], gap="xs"),
                dmc.Badge(
                    id="r2-filter-preview-badge",
                    children=f"{r2_preview['below_threshold']} wells below threshold",
                    color="orange" if r2_preview['below_threshold'] > 0 else "green",
                    size="sm",
                    variant="light",
                ),
            ], justify="space-between", mb="sm"),

            dmc.Text(
                "Exclude wells with low R\u00b2 from fold change calculations. "
                "This helps ensure reliable FC estimates.",
                size="xs", c="dimmed", mb="sm"
            ),

            dmc.Grid([
                dmc.GridCol([
                    dmc.Text("R\u00b2 Threshold", size="sm", mb="xs"),
                    dmc.Slider(
                        id="r2-threshold-slider",
                        value=current_threshold,
                        min=0.70,
                        max=0.95,
                        step=0.01,
                        marks=[
                            {"value": 0.70, "label": "0.70"},
                            {"value": 0.80, "label": "0.80"},
                            {"value": 0.90, "label": "0.90"},
                            {"value": 0.95, "label": "0.95"},
                        ],
                        mb="xs",
                    ),
                ], span=8),
                dmc.GridCol([
                    dmc.Stack([
                        dmc.Button(
                            "Apply Threshold",
                            id="r2-apply-threshold-btn",
                            leftSection=DashIconify(icon="mdi:check"),
                            size="xs",
                            color="blue",
                        ),
                        dmc.Button(
                            "Include All",
                            id="r2-include-all-btn",
                            variant="subtle",
                            size="xs",
                            color="gray",
                        ),
                    ], gap="xs"),
                ], span=4),
            ]),
        ], p="md", mb="md", withBorder=True),

        dmc.Grid([
            # Left: Results table + histogram (content rendered directly)
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Sample Fit Results", fw=500),
                        dmc.Badge(
                            children="Complete",
                            color="green",
                            size="lg",
                        ),
                    ], justify="space-between", mb="md"),

                    # Results table - rendered directly, no ID needed for callback
                    dmc.ScrollArea([
                        results_table_content,
                    ], h=250, type="auto"),

                    # Quality distribution - rendered directly
                    dmc.Text("Fit Quality Distribution", fw=500, size="sm", mt="md", mb="xs"),
                    dcc.Graph(
                        figure=histogram_fig,
                        config={"displayModeBar": False},
                        style={"height": "180px"},
                    ),
                ], p="md", withBorder=True),
            ], span=5),

            # Right: Curve viewer (content rendered directly)
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Curve Viewer", fw=500),
                        dmc.Text(
                            selection_count_text,
                            size="sm",
                            c="dimmed",
                        ),
                    ], justify="space-between", mb="md"),

                    # Curve plot - height matches figure's dynamic height
                    dcc.Graph(
                        figure=curve_fig,
                        config={"displayModeBar": False},
                        style={"height": f"{max(300, min(500, 250 + n_selected_wells * 15))}px"},
                    ),

                    # Clear separator between graph and params table
                    dmc.Divider(my="md"),

                    # Fit parameters table - rendered directly
                    dmc.Text("Fitted Parameters", fw=500, size="sm", mb="xs"),
                    dmc.ScrollArea([
                        params_table_content,
                    ], h=150, type="auto"),
                ], p="md", withBorder=True),
            ], span=7),
        ]),

        # Actions
        dmc.Group([
            dmc.Button(
                "View Failed Wells",
                id="fitting-view-failed-btn",
                variant="outline",
                leftSection=DashIconify(icon="mdi:alert-circle"),
                color="red",
            ),
            dmc.Button(
                "Open Curve Browser",
                id="fitting-open-browser-btn",
                variant="outline",
                leftSection=DashIconify(icon="mdi:chart-line"),
            ),
            dmc.Button(
                "Continue to Fold Changes",
                id="fitting-continue-fc-btn",
                rightSection=DashIconify(icon="mdi:arrow-right"),
                color="blue",
            ),
        ], justify="flex-end", mt="md"),
    ])


def create_step4_fold_changes(
    project_id: Optional[int] = None,
    computed_count: Optional[int] = None,
    error_message: Optional[str] = None,
    is_published: bool = False,
    can_publish: bool = False,
    publish_blockers: Optional[List[str]] = None,
) -> html.Div:
    """Create Step 4: Fold change computation UI.

    Args:
        project_id: Project ID for querying fold change data
        computed_count: Number of fold changes just computed (for showing success message)
        error_message: Error message to display if computation failed
        is_published: Whether fitting results are published
        can_publish: Whether results can be published
        publish_blockers: List of reasons why publishing is blocked
    """
    # Query fold change counts and data if project_id provided
    total_fcs = 0
    mutant_wt_count = 0
    wt_unreg_count = 0
    fold_change_data = []
    publish_blockers = publish_blockers or []

    if project_id:
        from app.models import Well, Plate, ExperimentalSession, Construct, Project
        from app.models.fit_result import FoldChange
        from app.services.fitting_service import FittingService

        # Get project to check publish state
        project = Project.query.get(project_id)
        if project:
            is_published = project.fitting_published or False
            can_publish_result, blockers = FittingService.can_publish_fitting(project_id)
            can_publish = can_publish_result
            publish_blockers = blockers

        # Get total fold changes for this project
        total_fcs = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()

        # Count mutant -> WT pairs (test well's construct is NOT wildtype and NOT unregulated)
        mutant_wt_count = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate).join(ExperimentalSession).join(
            Construct, Well.construct_id == Construct.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Construct.is_wildtype == False,
            Construct.is_unregulated == False
        ).count()

        # Count WT -> Unreg pairs (test well's construct IS wildtype)
        wt_unreg_count = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate).join(ExperimentalSession).join(
            Construct, Well.construct_id == Construct.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Construct.is_wildtype == True
        ).count()

        # Get fold change summary data for table
        if total_fcs > 0:
            fold_change_data = FittingService.get_fold_change_summary(project_id)

    # Determine status badge
    if error_message:
        status_text = "Error"
        status_color = "red"
    elif computed_count is not None:
        status_text = f"Computed {computed_count}"
        status_color = "green"
    elif total_fcs > 0:
        status_text = f"{total_fcs} Records"
        status_color = "green"
    else:
        status_text = "Ready"
        status_color = "blue"

    # Build content
    content = [
        dmc.Group([
            dmc.Text("Fold Change Computation", fw=500),
            dmc.Group([
                # Publish status badge
                dmc.Badge(
                    id="fc-publish-status-badge",
                    children="Published" if is_published else "Draft",
                    color="green" if is_published else "orange",
                    size="lg",
                    variant="filled" if is_published else "outline",
                    leftSection=DashIconify(
                        icon="mdi:check-circle" if is_published else "mdi:pencil",
                        width=14
                    ),
                ),
                dmc.Badge(
                    id="fc-status-badge",
                    children=status_text,
                    color=status_color,
                    size="lg",
                ),
            ], gap="xs"),
        ], justify="space-between", mb="md"),
    ]

    # Show error message if present
    if error_message:
        content.append(
            dmc.Alert(
                title="Computation Error",
                children=error_message,
                color="red",
                icon=DashIconify(icon="mdi:alert-circle"),
                mb="md",
            )
        )
    # Show success message if just computed
    elif computed_count is not None and computed_count > 0:
        content.append(
            dmc.Alert(
                title="Fold Changes Computed",
                children=f"Successfully computed {computed_count} fold change records.",
                color="green",
                icon=DashIconify(icon="mdi:check-circle"),
                mb="md",
            )
        )

    content.extend([
        dmc.Alert(
            title="Comparison Strategy",
            children=[
                "Fold changes are computed using the plate layout pairings: ",
                dmc.Text("Mutants vs Wild-type", fw=700, span=True),
                " (within-family), and ",
                dmc.Text("Wild-type vs Unregulated", fw=700, span=True),
                " (cross-family reference).",
            ],
            color="blue",
            icon=DashIconify(icon="mdi:information"),
            mb="md",
        ),

        # Pairing summary with actual counts
        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Mutant \u2192 WT Pairs", size="xs", c="dimmed", ta="center"),
                    dmc.Text(id="fc-mutant-wt-count", children=str(mutant_wt_count), size="xl", fw=700, ta="center"),
                ], p="sm", withBorder=True),
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("WT \u2192 Unreg Pairs", size="xs", c="dimmed", ta="center"),
                    dmc.Text(id="fc-wt-unreg-count", children=str(wt_unreg_count), size="xl", fw=700, ta="center"),
                ], p="sm", withBorder=True),
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Total FC Records", size="xs", c="dimmed", ta="center"),
                    dmc.Text(id="fc-total-count", children=str(total_fcs), size="xl", fw=700, ta="center"),
                ], p="sm", withBorder=True),
            ], span=4),
        ], mb="md"),

        # Compute button
        dmc.Button(
            "Compute Fold Changes" if total_fcs == 0 else "Recompute Fold Changes",
            id="fc-compute-btn",
            leftSection=DashIconify(icon="mdi:calculator"),
            fullWidth=True,
            mb="md",
        ),

        # Progress
        html.Div(id="fc-progress-container", children=[
            dmc.Progress(
                id="fc-progress-bar",
                value=0,
                size="lg",
                mb="sm",
            ),
            dmc.Text(id="fc-progress-text", children="", c="dimmed", size="sm", ta="center"),
        ], style={"display": "none"}),
    ])

    # Fold Change Results Table (if we have data)
    if fold_change_data:
        content.extend([
            dmc.Divider(my="md"),
            dmc.Text("Fold Change Results", fw=500, mb="sm"),
            dmc.ScrollArea([
                build_fold_change_table(fold_change_data),
            ], h=250, type="auto"),
        ])

    content.append(dmc.Divider(my="md"))

    # Publish/Unpublish section
    if is_published:
        content.extend([
            dmc.Alert(
                title="Fitting Results Published",
                children=[
                    "Fitting results have been published. You can now run ",
                    dmc.Text("hierarchical analysis", fw=700, span=True),
                    " to estimate construct-level effects.",
                ],
                color="green",
                icon=DashIconify(icon="mdi:check-circle"),
                mb="md",
            ),
            dmc.Button(
                "Revert to Draft",
                id="fc-unpublish-btn",
                leftSection=DashIconify(icon="mdi:pencil"),
                variant="outline",
                color="orange",
                fullWidth=True,
                mb="md",
            ),
        ])
    else:
        # Show publish blockers or publish button
        if publish_blockers:
            content.append(
                dmc.Alert(
                    title="Cannot Publish Yet",
                    children=[
                        dmc.Text("The following must be completed before publishing:"),
                        dmc.List([
                            dmc.ListItem(blocker) for blocker in publish_blockers
                        ], size="sm", mt="xs"),
                    ],
                    color="orange",
                    icon=DashIconify(icon="mdi:alert"),
                    mb="md",
                )
            )
        else:
            content.append(
                dmc.Alert(
                    title="Ready to Publish",
                    children=[
                        "Publishing fitting results will enable ",
                        dmc.Text("hierarchical analysis", fw=700, span=True),
                        ". You can revert to draft anytime to make changes.",
                    ],
                    color="blue",
                    icon=DashIconify(icon="mdi:information"),
                    mb="md",
                )
            )

        content.append(
            dmc.Button(
                "Publish Fitting Results",
                id="fc-publish-btn",
                leftSection=DashIconify(icon="mdi:publish"),
                color="green",
                fullWidth=True,
                disabled=not can_publish,
                mb="md",
            )
        )

    # Next step guidance (only show if published)
    if is_published:
        content.append(
            dmc.Alert(
                title="Next: Hierarchical Analysis",
                children=[
                    "Proceed to run the ",
                    dmc.Text("Bayesian hierarchical model", fw=700, span=True),
                    " to estimate construct-level effects with proper variance decomposition.",
                ],
                color="green",
                icon=DashIconify(icon="mdi:arrow-right-circle"),
            )
        )
    else:
        content.append(
            dmc.Alert(
                title="Hierarchical Analysis Locked",
                children=[
                    "Publish fitting results to unlock ",
                    dmc.Text("hierarchical analysis", fw=700, span=True),
                    ".",
                ],
                color="gray",
                icon=DashIconify(icon="mdi:lock"),
                variant="light",
            )
        )

    # Create the analysis button - wrap in Tooltip when disabled
    analysis_btn = dmc.Button(
        "Run Hierarchical Analysis",
        id="fc-run-analysis-btn",
        rightSection=DashIconify(icon="mdi:chart-areaspline"),
        color="green",
        disabled=not is_published,
    )

    if not is_published:
        analysis_btn = dmc.Tooltip(
            analysis_btn,
            label="Publish fitting results to enable hierarchical analysis",
            position="top",
        )

    return html.Div([
        dmc.Paper(content, p="md", withBorder=True),

        # Actions
        dmc.Group([
            dmc.Button(
                "Back to Results",
                id="fc-back-btn",
                variant="outline",
                leftSection=DashIconify(icon="mdi:arrow-left"),
            ),
            analysis_btn,
        ], justify="flex-end", mt="md"),
    ])


def create_plate_checkbox_item(
    plate_id: int,
    plate_name: str,
    session_name: str,
    well_count: int,
    fitted_count: int,
    sample_count: int,
    negative_count: int,
    is_qc_rejected: bool = False,
    checked: bool = False,
) -> dmc.Checkbox:
    """
    Create a plate checkbox item for selection.

    Args:
        plate_id: Plate database ID
        plate_name: Plate display name
        session_name: Session name
        well_count: Total wells
        fitted_count: Already fitted wells
        sample_count: Sample wells (to be fitted)
        negative_count: Negative control wells (not fitted)
        is_qc_rejected: Whether the session was QC rejected (plate cannot be fitted)
        checked: Whether the checkbox should be pre-checked

    Returns:
        Checkbox component with plate info
    """
    progress_pct = (fitted_count / sample_count * 100) if sample_count > 0 else 0

    # Build badge for status
    if is_qc_rejected:
        status_badge = dmc.Badge(
            "QC Rejected",
            color="red",
            size="xs",
            variant="filled",
        )
    else:
        status_badge = dmc.Badge(
            f"{fitted_count}/{sample_count}",
            color="green" if fitted_count == sample_count else "blue",
            size="xs",
            variant="light",
        )

    return dmc.Checkbox(
        id={"type": "fitting-plate-checkbox", "index": plate_id},
        label=dmc.Stack([
            dmc.Group([
                dmc.Text(
                    plate_name,
                    fw=500,
                    size="sm",
                    td="line-through" if is_qc_rejected else None,
                    c="dimmed" if is_qc_rejected else "dark",
                ),
                status_badge,
            ], justify="space-between"),
            dmc.Group([
                dmc.Text(session_name, size="xs", c="dimmed"),
                dmc.Text(f"{sample_count} samples, {negative_count} controls", size="xs", c="dimmed"),
            ], justify="space-between"),
            dmc.Progress(
                value=progress_pct,
                size="xs",
                color="red" if is_qc_rejected else ("green" if progress_pct == 100 else "blue"),
            ),
        ], gap=4),
        value=str(plate_id),
        checked=checked,
        disabled=is_qc_rejected,  # Cannot select QC rejected plates for fitting
        styles={"root": {"width": "100%"}, "body": {"width": "100%"}},
    )
