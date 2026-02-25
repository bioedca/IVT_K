"""
Project settings layout.

Phase 2.9: Project settings (plate format, precision targets) (F2.1)
"""
from dash import html, dcc
import dash_mantine_components as dmc


def create_project_settings_layout(project_id: int = None):
    """
    Create the project settings layout.

    Args:
        project_id: Project ID to load settings for

    Features:
    - Basic project info (name, description)
    - Plate format selection
    - Precision target configuration
    - QC threshold settings
    - Ligand experiment settings
    """
    return dmc.Container(
        children=[
            # Store for project data
            dcc.Store(id="settings-project-store", data={"project_id": project_id}),

            # Header with back navigation
            dmc.Group(
                children=[
                    dmc.ActionIcon(
                        dmc.Text("←", size="lg"),
                        id="settings-back-btn",
                        variant="subtle",
                        size="lg"
                    ),
                    dmc.Title("Project Settings", order=2)
                ],
                gap="md",
                style={"marginBottom": "1.5rem"}
            ),

            # Settings tabs
            dmc.Tabs(
                id="settings-tabs",
                value="general",
                children=[
                    dmc.TabsList(
                        children=[
                            dmc.TabsTab("General", value="general"),
                            dmc.TabsTab("Analysis", value="analysis"),
                            dmc.TabsTab("QC Thresholds", value="qc"),
                            dmc.TabsTab("Ligand", value="ligand"),
                            dmc.TabsTab("Storage & Archive", value="storage")
                        ]
                    ),

                    # General settings tab
                    dmc.TabsPanel(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Title("Basic Information", order=4, mb="md"),
                                    dmc.TextInput(
                                        id="settings-project-name",
                                        label="Project Name",
                                        required=True,
                                        style={"marginBottom": "1rem"}
                                    ),
                                    dmc.Textarea(
                                        id="settings-project-description",
                                        label="Description",
                                        autosize=True,
                                        minRows=3,
                                        style={"marginBottom": "1rem"}
                                    ),
                                    dmc.TextInput(
                                        id="settings-reporter-system",
                                        label="Reporter System",
                                        placeholder="e.g., iSpinach",
                                        style={"marginBottom": "1rem"}
                                    ),
                                    dmc.Select(
                                        id="settings-plate-format",
                                        label="Plate Format",
                                        description="Cannot be changed once plates have been uploaded",
                                        data=[
                                            {"value": "384", "label": "384-well plate (16x24)"},
                                            {"value": "96", "label": "96-well plate (8x12)"}
                                        ],
                                        style={"marginBottom": "1rem"}
                                    ),
                                    dmc.Textarea(
                                        id="settings-project-notes",
                                        label="Notes",
                                        placeholder="Additional notes about this project...",
                                        autosize=True,
                                        minRows=2
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        value="general",
                        pt="md"
                    ),

                    # Analysis settings tab
                    dmc.TabsPanel(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Title("Precision Targets", order=4, mb="md"),
                                    dmc.Text(
                                        "Configure the target precision for fold change estimates. "
                                        "The precision target defines the acceptable confidence interval width.",
                                        size="sm",
                                        c="dimmed",
                                        mb="md"
                                    ),
                                    dmc.NumberInput(
                                        id="settings-precision-target",
                                        label="Precision Target (CI Width)",
                                        description="Target 95% CI width for fold change (default: 0.3)",
                                        value=0.3,
                                        min=0.05,
                                        max=1.0,
                                        step=0.05,
                                        decimalScale=2,
                                        style={"marginBottom": "1rem", "maxWidth": "300px"}
                                    ),
                                    dmc.NumberInput(
                                        id="settings-fc-threshold",
                                        label="Meaningful Fold Change Threshold",
                                        description="Minimum fold change considered biologically meaningful",
                                        value=1.5,
                                        min=1.1,
                                        max=5.0,
                                        step=0.1,
                                        decimalScale=1,
                                        style={"marginBottom": "1rem", "maxWidth": "300px"}
                                    ),
                                    dmc.Divider(my="lg"),
                                    dmc.Title("Kinetic Model", order=4, mb="md"),
                                    dmc.Select(
                                        id="settings-kinetic-model",
                                        label="Kinetic Model Type",
                                        description="Model used for curve fitting",
                                        data=[
                                            {"value": "delayed_exponential", "label": "Delayed Exponential (default)"},
                                            {"value": "logistic", "label": "Logistic"},
                                            {"value": "double_exponential", "label": "Double Exponential"}
                                        ],
                                        value="delayed_exponential",
                                        style={"maxWidth": "300px"}
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        value="analysis",
                        pt="md"
                    ),

                    # QC thresholds tab
                    dmc.TabsPanel(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Title("Quality Control Thresholds", order=4, mb="md"),
                                    dmc.Text(
                                        "Configure thresholds for automated quality control checks.",
                                        size="sm",
                                        c="dimmed",
                                        mb="md"
                                    ),
                                    dmc.SimpleGrid(
                                        cols=2,
                                        children=[
                                            dmc.NumberInput(
                                                id="settings-qc-cv-threshold",
                                                label="CV Threshold",
                                                description="Max coefficient of variation",
                                                value=0.20,
                                                min=0.05,
                                                max=0.50,
                                                step=0.01,
                                                decimalScale=2
                                            ),
                                            dmc.NumberInput(
                                                id="settings-qc-outlier-threshold",
                                                label="Outlier Threshold (σ)",
                                                description="Standard deviations for outlier detection",
                                                value=3.0,
                                                min=2.0,
                                                max=5.0,
                                                step=0.5,
                                                decimalScale=1
                                            ),
                                            dmc.NumberInput(
                                                id="settings-qc-drift-threshold",
                                                label="Drift Threshold",
                                                description="Max baseline drift rate",
                                                value=0.1,
                                                min=0.01,
                                                max=0.50,
                                                step=0.01,
                                                decimalScale=2
                                            ),
                                            dmc.NumberInput(
                                                id="settings-qc-saturation-threshold",
                                                label="Saturation Threshold",
                                                description="Signal saturation limit (fraction)",
                                                value=0.95,
                                                min=0.80,
                                                max=1.0,
                                                step=0.01,
                                                decimalScale=2
                                            ),
                                            dmc.NumberInput(
                                                id="settings-qc-snr-threshold",
                                                label="SNR Threshold",
                                                description="Minimum signal-to-noise ratio",
                                                value=10.0,
                                                min=3.0,
                                                max=50.0,
                                                step=1.0,
                                                decimalScale=1
                                            ),
                                            dmc.NumberInput(
                                                id="settings-qc-empty-well-threshold",
                                                label="Empty Well Threshold",
                                                description="Max signal for empty wells (RFU)",
                                                value=100.0,
                                                min=10.0,
                                                max=1000.0,
                                                step=10.0,
                                                decimalScale=0
                                            )
                                        ],
                                        spacing="lg"
                                    ),
                                    dmc.Divider(my="lg"),
                                    dmc.Title("LOD/LOQ Settings", order=4, mb="md"),
                                    dmc.SimpleGrid(
                                        cols=2,
                                        children=[
                                            dmc.NumberInput(
                                                id="settings-lod-coverage",
                                                label="LOD Coverage Factor",
                                                description="Multiplier for limit of detection",
                                                value=3.0,
                                                min=2.0,
                                                max=5.0,
                                                step=0.5,
                                                decimalScale=1
                                            ),
                                            dmc.NumberInput(
                                                id="settings-loq-coverage",
                                                label="LOQ Coverage Factor",
                                                description="Multiplier for limit of quantification",
                                                value=10.0,
                                                min=5.0,
                                                max=20.0,
                                                step=1.0,
                                                decimalScale=1
                                            )
                                        ],
                                        spacing="lg"
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        value="qc",
                        pt="md"
                    ),

                    # Ligand settings tab
                    dmc.TabsPanel(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Title("Ligand Experiment Settings", order=4, mb="md"),
                                    dmc.Switch(
                                        id="settings-has-ligand",
                                        label="This project includes ligand dose-response experiments",
                                        description="Enable to configure ligand concentration settings",
                                        checked=False,
                                        style={"marginBottom": "1rem"}
                                    ),
                                    html.Div(
                                        id="ligand-settings-container",
                                        children=[
                                            dmc.TextInput(
                                                id="settings-ligand-name",
                                                label="Ligand Name",
                                                placeholder="e.g., Glycine, SAM",
                                                style={"marginBottom": "1rem", "maxWidth": "300px"}
                                            ),
                                            dmc.Select(
                                                id="settings-ligand-unit",
                                                label="Concentration Unit",
                                                data=[
                                                    {"value": "µM", "label": "µM (micromolar)"},
                                                    {"value": "mM", "label": "mM (millimolar)"},
                                                    {"value": "nM", "label": "nM (nanomolar)"},
                                                    {"value": "pM", "label": "pM (picomolar)"}
                                                ],
                                                value="µM",
                                                style={"marginBottom": "1rem", "maxWidth": "200px"}
                                            ),
                                            dmc.NumberInput(
                                                id="settings-ligand-max-conc",
                                                label="Maximum Concentration",
                                                description="Highest ligand concentration used",
                                                min=0,
                                                step=1,
                                                style={"marginBottom": "1rem", "maxWidth": "200px"}
                                            )
                                        ],
                                        style={"display": "none"}  # Hidden by default
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        value="ligand",
                        pt="md"
                    ),

                    # Storage & Archive settings tab (Phase H.3)
                    dmc.TabsPanel(
                        children=[
                            # Storage usage section
                            dmc.Paper(
                                children=[
                                    dmc.Title("Storage Usage", order=4, mb="md"),
                                    dmc.Text(
                                        "View storage consumption for this project's data files.",
                                        size="sm",
                                        c="dimmed",
                                        mb="md"
                                    ),
                                    html.Div(
                                        id="storage-usage-container",
                                        children=[
                                            dmc.Skeleton(height=100, visible=True)
                                        ]
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md",
                                mb="md"
                            ),

                            # Activity tracking section
                            dmc.Paper(
                                children=[
                                    dmc.Title("Activity Status", order=4, mb="md"),
                                    dmc.Text(
                                        "Projects inactive for 6+ months may be flagged for archival.",
                                        size="sm",
                                        c="dimmed",
                                        mb="md"
                                    ),
                                    html.Div(
                                        id="activity-status-container",
                                        children=[
                                            dmc.Skeleton(height=80, visible=True)
                                        ]
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md",
                                mb="md"
                            ),

                            # Archive actions section
                            dmc.Paper(
                                children=[
                                    dmc.Title("Archive Management", order=4, mb="md"),
                                    dmc.Text(
                                        "Archive completed projects to free up active storage. "
                                        "Archived projects can be restored at any time.",
                                        size="sm",
                                        c="dimmed",
                                        mb="md"
                                    ),
                                    html.Div(
                                        id="archive-status-container",
                                        children=[
                                            dmc.Skeleton(height=60, visible=True)
                                        ]
                                    ),
                                    dmc.Group(
                                        children=[
                                            dmc.Button(
                                                "Archive Project",
                                                id="settings-archive-btn",
                                                color="orange",
                                                variant="outline",
                                                leftSection=html.Span("📦")
                                            ),
                                            dmc.Button(
                                                "Restore Project",
                                                id="settings-restore-btn",
                                                color="green",
                                                variant="outline",
                                                leftSection=html.Span("📂"),
                                                style={"display": "none"}
                                            )
                                        ],
                                        mt="md"
                                    ),
                                    # Confirmation modal for archive
                                    dmc.Modal(
                                        id="archive-confirm-modal",
                                        title="Confirm Archive",
                                        centered=True,
                                        children=[
                                            dmc.Text(
                                                "Are you sure you want to archive this project? "
                                                "The project data will be compressed and moved to cold storage. "
                                                "You can restore it at any time.",
                                                mb="md"
                                            ),
                                            dmc.Textarea(
                                                id="archive-reason",
                                                label="Archive Reason (optional)",
                                                placeholder="e.g., Project completed, data preserved for publication",
                                                minRows=2,
                                                mb="md"
                                            ),
                                            dmc.Group(
                                                children=[
                                                    dmc.Button(
                                                        "Cancel",
                                                        id="archive-cancel-btn",
                                                        variant="subtle"
                                                    ),
                                                    dmc.Button(
                                                        "Archive",
                                                        id="archive-confirm-btn",
                                                        color="orange"
                                                    )
                                                ],
                                                justify="flex-end"
                                            )
                                        ]
                                    )
                                ],
                                p="lg",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        value="storage",
                        pt="md"
                    )
                ]
            ),

            # Save button footer
            dmc.Group(
                children=[
                    dmc.Button(
                        "Cancel",
                        id="settings-cancel-btn",
                        variant="subtle"
                    ),
                    dmc.Button(
                        "Save Changes",
                        id="settings-save-btn",
                        color="blue"
                    )
                ],
                justify="flex-end",
                style={"marginTop": "2rem"}
            ),

            # Notification for save status
            html.Div(id="settings-notification-container")
        ],
        size="md",
        style={"paddingTop": "1rem", "paddingBottom": "2rem"}
    )
