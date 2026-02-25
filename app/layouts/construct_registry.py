"""
Construct Registry layout.

Phase C: UI Layer Completion

Provides:
- Construct management UI (add, edit, delete)
- Family organization and wild-type designation
- Unregulated reference selection
- Duplicate identifier validation

PRD References:
- Section 3.3: Construct Registry (F3.1-F3.9)
- F3.1: Add construct with identifier
- F3.2: Assign to family, mark as wild-type
- F3.3: Prevent duplicate identifiers
- F3.7: Designate unregulated reference
"""
from typing import Optional, List, Dict, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_construct_registry_layout(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the construct registry layout.

    Phase C: UI Layer Completion (F3.1-F3.9)

    Args:
        project_id: Optional project ID

    Returns:
        Construct registry layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="construct-registry-project-store", data=project_id),
        dcc.Store(id="construct-registry-data-store", data=None),
        dcc.Store(id="construct-registry-editing-store", data=None),
        dcc.Store(id="construct-registry-validation-store", data=None),

        # Header
        dmc.Group([
            dmc.Group([
                DashIconify(icon="mdi:dna", width=28, color="var(--mantine-color-teal-6)"),
                dmc.Title("Construct Registry", order=2),
            ], gap="sm"),
            dmc.Group([
                dmc.Badge(
                    id="construct-count-badge",
                    children="0 constructs",
                    color="blue",
                    size="lg",
                    variant="light",
                ),
                dmc.Button(
                    "Add Construct",
                    id="construct-add-btn",
                    leftSection=DashIconify(icon="mdi:plus"),
                    color="blue",
                ),
            ]),
        ], justify="space-between", mb="md"),

        # Validation alerts
        html.Div(id="construct-validation-alerts"),

        # Main content grid
        dmc.Grid([
            # Left: Construct table
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.TextInput(
                            id="construct-search-input",
                            placeholder="Search constructs...",
                            leftSection=DashIconify(icon="mdi:magnify"),
                            style={"flex": 1},
                        ),
                        dmc.Select(
                            id="construct-family-filter",
                            placeholder="All families",
                            data=[],
                            clearable=True,
                            style={"width": "150px"},
                        ),
                        dmc.SegmentedControl(
                            id="construct-view-mode",
                            data=[
                                {"value": "table", "label": "Table"},
                                {"value": "cards", "label": "Cards"},
                            ],
                            value="table",
                            size="xs",
                        ),
                    ], mb="md"),
                    dmc.ScrollArea([
                        html.Div(id="construct-table-container"),
                    ], h=500),
                ], p="md", withBorder=True),
            ], span=8),

            # Right: Add/Edit form and summary
            dmc.GridCol([
                # Add/Edit form
                dmc.Paper([
                    dmc.Text(
                        id="construct-form-title",
                        children="Add New Construct",
                        fw=500,
                        mb="md",
                    ),
                    html.Div(id="construct-form-container"),
                ], p="md", mb="md", withBorder=True),

                # Family summary
                dmc.Paper([
                    dmc.Text("Family Summary", fw=500, mb="sm"),
                    html.Div(id="construct-family-summary"),
                ], p="md", mb="md", withBorder=True),

                # Unregulated reference
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Unregulated Reference", fw=500),
                        dmc.Tooltip(
                            DashIconify(
                                icon="mdi:help-circle-outline",
                                width=16,
                                color="gray",
                            ),
                            label="The unregulated reference is used as the baseline for all fold-change calculations across families.",
                            multiline=True,
                            w=250,
                        ),
                    ], gap="xs", mb="sm"),
                    html.Div(id="construct-unregulated-selector"),
                ], p="md", withBorder=True),
            ], span=4),
        ]),

        # Edit modal
        dmc.Modal(
            id="construct-edit-modal",
            title="Edit Construct",
            centered=True,
            size="md",
            children=[
                html.Div(id="construct-edit-form-container"),
            ],
        ),

        # Delete confirmation modal
        dmc.Modal(
            id="construct-delete-modal",
            title="Delete Construct",
            centered=True,
            size="sm",
            children=[
                dmc.Stack([
                    dmc.Text(
                        id="construct-delete-message",
                        children="Are you sure you want to delete this construct?",
                    ),
                    dmc.Alert(
                        title="Warning",
                        children="This will remove all associated plate assignments and analysis data.",
                        color="red",
                        icon=DashIconify(icon="mdi:alert"),
                    ),
                    dmc.Group([
                        dmc.Button(
                            "Cancel",
                            id="construct-delete-cancel",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Delete",
                            id="construct-delete-confirm",
                            color="red",
                        ),
                    ], justify="flex-end", mt="md"),
                ], gap="md"),
            ],
        ),

        # Result notifications
        html.Div(id="construct-operation-result"),
    ])


def create_construct_form(
    families: Optional[List[str]] = None,
    editing: Optional[Dict[str, Any]] = None,
    form_index: str = "default",
) -> dmc.Stack:
    """
    Create construct add/edit form.

    PRD Ref: F3.1, F3.2 - Add construct with identifier, family, wild-type

    Args:
        families: List of existing family names for autocomplete
        editing: Existing construct data if editing
        form_index: Unique index for this form instance (for pattern matching)

    Returns:
        Form component
    """
    is_editing = editing is not None
    families = families or []

    return dmc.Stack([
        # Identifier field
        dmc.TextInput(
            id={"type": "construct-form-field", "field": "identifier", "index": form_index},
            label="Identifier",
            description="Unique identifier for this construct",
            placeholder="e.g., Tbox1_M1",
            value=editing.get("identifier", "") if editing else "",
            required=True,
            error=None,
        ),

        # Family selection with autocomplete
        # Family selection with autocomplete (allows custom values)
        dmc.Autocomplete(
            id={"type": "construct-form-field", "field": "family", "index": form_index},
            label="Family",
            description="Group related constructs by family",
            placeholder="Select or type family name",
            data=families,  # Autocomplete accepts list of strings
            value=editing.get("family", "") if editing else "",
        ),

        # Wild-type checkbox
        dmc.Checkbox(
            id={"type": "construct-form-field", "field": "is_wildtype", "index": form_index},
            label="This is the wild-type for this family",
            checked=editing.get("is_wildtype", False) if editing else False,
            description="Wild-types serve as the reference within their family",
        ),

        # Reporter checkbox
        dmc.Checkbox(
            id={"type": "construct-form-field", "field": "is_reporter_only", "index": form_index},
            label="Reporter-only (no promoter)",
            checked=editing.get("is_reporter_only", False) if editing else False,
            description="Mark if this construct contains only the reporter gene",
        ),

        # Plasmid size field
        dmc.NumberInput(
            id={"type": "construct-form-field", "field": "plasmid_size_bp", "index": form_index},
            label="Plasmid size (bp)",
            description="Total plasmid size in base pairs (for nM-based DNA targeting)",
            placeholder="e.g., 5000",
            value=editing.get("plasmid_size_bp") if editing else None,
            min=100,
            step=1,
        ),

        # Notes field
        dmc.Textarea(
            id={"type": "construct-form-field", "field": "notes", "index": form_index},
            label="Notes",
            placeholder="Optional notes about this construct",
            value=editing.get("notes", "") if editing else "",
            minRows=2,
        ),

        # Form actions
        dmc.Group([
            dmc.Button(
                "Cancel",
                id={"type": "construct-form-cancel", "index": form_index},
                variant="outline",
            ) if is_editing else None,
            dmc.Button(
                "Update Construct" if is_editing else "Add Construct",
                id={"type": "construct-form-submit", "index": form_index},
                color="blue",
                leftSection=DashIconify(
                    icon="mdi:content-save" if is_editing else "mdi:plus"
                ),
            ),
        ], justify="flex-end", mt="md"),
    ], gap="md")


def create_construct_table(
    constructs: List[Dict[str, Any]],
    show_actions: bool = True,
) -> dmc.Table:
    """
    Create construct table display.

    Args:
        constructs: List of construct dicts with:
            - id: Construct ID
            - identifier: Construct identifier
            - family: Family name
            - is_wildtype: Whether wild-type
            - is_reporter_only: Whether reporter-only
            - replicate_count: Number of replicates
        show_actions: Whether to show edit/delete actions

    Returns:
        Table component
    """
    if not constructs:
        return dmc.Stack([
            DashIconify(
                icon="mdi:flask-empty-outline",
                width=48,
                color="gray",
            ),
            dmc.Text(
                "No constructs defined yet",
                c="dimmed",
                ta="center",
            ),
            dmc.Text(
                "Use the form to add your first construct",
                size="sm",
                c="dimmed",
                ta="center",
            ),
        ], align="center", gap="xs", py="xl")

    rows = []
    for construct in constructs:
        badges = []

        # Wild-type badge
        if construct.get("is_wildtype"):
            badges.append(
                dmc.Badge("WT", color="green", size="xs", variant="light")
            )

        # Reporter-only badge
        if construct.get("is_reporter_only"):
            badges.append(
                dmc.Badge("Reporter", color="orange", size="xs", variant="light")
            )

        # Unregulated badge
        if construct.get("is_unregulated"):
            badges.append(
                dmc.Badge("Unreg", color="blue", size="xs", variant="filled")
            )

        # Draft badge
        is_draft = construct.get("is_draft", True)
        if is_draft:
            badges.append(
                dmc.Badge("Draft", color="gray", size="xs", variant="outline")
            )

        # Actions column
        actions = None
        if show_actions:
            # Publish/Unpublish button
            if is_draft:
                publish_btn = dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:publish", width=16),
                        id={"type": "construct-publish-btn", "index": construct.get("id")},
                        variant="subtle",
                        size="sm",
                        color="green",
                    ),
                    label="Publish construct",
                    position="top",
                )
            else:
                publish_btn = dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:publish-off", width=16),
                        id={"type": "construct-unpublish-btn", "index": construct.get("id")},
                        variant="subtle",
                        size="sm",
                        color="orange",
                    ),
                    label="Unpublish construct",
                    position="top",
                )

            actions = dmc.Group([
                publish_btn,
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:pencil-outline", width=16),
                        id={"type": "construct-edit-btn", "index": construct.get("id")},
                        variant="subtle",
                        size="sm",
                        color="blue",
                    ),
                    label="Edit construct",
                    position="top",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:delete-outline", width=16),
                        id={"type": "construct-delete-btn", "index": construct.get("id")},
                        variant="subtle",
                        size="sm",
                        color="red",
                    ),
                    label="Delete construct",
                    position="top",
                ),
            ], gap="xs")

        rows.append(
            html.Tr([
                html.Td(
                    dmc.Group([
                        dmc.Text(construct.get("identifier", "Unknown"), fw=500),
                        dmc.Group(badges, gap="xs") if badges else None,
                    ], gap="sm")
                ),
                html.Td(construct.get("family", "—")),
                html.Td(str(construct.get("replicate_count", 0))),
                html.Td(actions) if show_actions else None,
            ])
        )

    headers = [
        html.Th("Identifier"),
        html.Th("Family"),
        html.Th("Replicates"),
    ]
    if show_actions:
        headers.append(html.Th("Actions", style={"width": "80px"}))

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(html.Tr(headers)),
            html.Tbody(rows),
        ],
    )


def create_construct_cards(
    constructs: List[Dict[str, Any]],
) -> dmc.SimpleGrid:
    """
    Create card view for constructs.

    Args:
        constructs: List of construct dicts

    Returns:
        SimpleGrid of construct cards
    """
    if not constructs:
        return create_construct_table([])  # Use empty table message

    cards = []
    for construct in constructs:
        badges = []

        if construct.get("is_wildtype"):
            badges.append(dmc.Badge("Wild-type", color="green", size="sm"))
        if construct.get("is_reporter_only"):
            badges.append(dmc.Badge("Reporter", color="orange", size="sm"))
        if construct.get("is_unregulated"):
            badges.append(dmc.Badge("Unregulated", color="blue", size="sm"))
        if construct.get("is_draft", True):
            badges.append(dmc.Badge("Draft", color="gray", size="sm", variant="outline"))

        cards.append(
            dmc.Paper([
                dmc.Group([
                    dmc.Text(construct.get("identifier", "Unknown"), fw=600),
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:dots-vertical", width=16),
                            id={"type": "construct-menu-btn", "index": construct.get("id")},
                            variant="subtle",
                            size="sm",
                        ),
                        label="Construct options",
                        position="top",
                    ),
                ], justify="space-between", mb="xs"),

                dmc.Text(
                    f"Family: {construct.get('family', 'None')}",
                    size="sm",
                    c="dimmed",
                    mb="xs",
                ),

                dmc.Group(badges, gap="xs", mb="sm") if badges else None,

                dmc.Group([
                    dmc.Text(
                        f"{construct.get('replicate_count', 0)} replicates",
                        size="xs",
                        c="dimmed",
                    ),
                ], justify="space-between"),
            ], p="md", withBorder=True, radius="md")
        )

    return dmc.SimpleGrid(
        cols={"base": 1, "sm": 2, "lg": 3},
        spacing="md",
        children=cards,
    )


def create_family_summary(
    families: List[Dict[str, Any]],
) -> html.Div:
    """
    Create family summary display.

    Args:
        families: List of family dicts with:
            - name: Family name
            - construct_count: Number of constructs
            - has_wildtype: Whether family has wild-type

    Returns:
        Family summary component
    """
    if not families:
        return dmc.Text("No families defined", c="dimmed", size="sm")

    items = []
    for family in families:
        has_wt = family.get("has_wildtype", False)

        items.append(
            dmc.Group([
                dmc.Group([
                    DashIconify(
                        icon="mdi:folder-outline",
                        width=16,
                        color="var(--mantine-color-blue-6)",
                    ),
                    dmc.Text(family.get("name", "Unknown"), size="sm"),
                ], gap="xs"),
                dmc.Group([
                    dmc.Badge(
                        f"{family.get('construct_count', 0)}",
                        size="xs",
                        color="gray",
                        variant="light",
                    ),
                    DashIconify(
                        icon="mdi:check-circle" if has_wt else "mdi:alert-circle-outline",
                        width=16,
                        color="green" if has_wt else "orange",
                    ),
                ], gap="xs"),
            ], justify="space-between", py="xs")
        )

    return html.Div([
        *items,
        dmc.Divider(my="sm"),
        dmc.Group([
            dmc.Text("Total:", size="sm", c="dimmed"),
            dmc.Text(
                f"{sum(f.get('construct_count', 0) for f in families)} constructs in {len(families)} families",
                size="sm",
            ),
        ], justify="space-between"),
    ])


def create_unregulated_selector(
    constructs: List[Dict[str, Any]],
    current_unregulated_id: Optional[int] = None,
) -> dmc.Stack:
    """
    Create unregulated reference selector.

    PRD Ref: F3.7 - Designate one construct as unregulated reference

    Args:
        constructs: List of available constructs
        current_unregulated_id: Currently selected unregulated construct ID

    Returns:
        Selector component
    """
    if not constructs:
        return dmc.Alert(
            children="Add constructs first to designate an unregulated reference.",
            color="gray",
            icon=DashIconify(icon="mdi:information"),
        )

    options = [
        {"value": str(c.get("id")), "label": c.get("identifier", f"ID {c.get('id')}")}
        for c in constructs
    ]

    return dmc.Stack([
        dmc.Select(
            id="construct-unregulated-select",
            data=options,
            value=str(current_unregulated_id) if current_unregulated_id else None,
            placeholder="Select unregulated reference",
            description="This construct will be auto-assigned to the 'universal' family",
            clearable=True,
        ),
        dmc.Button(
            "Set as Unregulated",
            id="construct-unregulated-set-btn",
            variant="light",
            size="sm",
            leftSection=DashIconify(icon="mdi:check"),
        ),
    ], gap="sm")


def create_construct_registry_skeleton() -> html.Div:
    """Create skeleton for loading state."""
    return html.Div([
        dmc.Group([
            dmc.Skeleton(height=32, width=200),
            dmc.Skeleton(height=36, width=140, radius="md"),
        ], justify="space-between", mb="md"),

        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Skeleton(height=36, width="100%", mb="md"),
                    dmc.Skeleton(height=300, width="100%"),
                ], p="md", withBorder=True),
            ], span=8),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Skeleton(height=24, width=150, mb="md"),
                    dmc.Skeleton(height=36, width="100%", mb="sm"),
                    dmc.Skeleton(height=36, width="100%", mb="sm"),
                    dmc.Skeleton(height=36, width="100%", mb="sm"),
                ], p="md", withBorder=True),
            ], span=4),
        ]),
    ])
