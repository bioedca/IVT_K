"""
Help panel component for IVT Kinetics Analyzer.

Phase 8.10-8.11: Help System

Provides:
- Expandable help panel component
- JSON-based help content loading
- Section-specific tooltips
- "Why this matters" explanations
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify


# Cache for loaded help content
_help_cache: Dict[str, Any] = {}


def load_help_content(panel_id: str) -> Optional[Dict[str, Any]]:
    """
    Load help content from JSON file.

    Args:
        panel_id: Panel identifier (e.g., "plate_layout", "curve_fitting")

    Returns:
        Help content dict or None if not found
    """
    if panel_id in _help_cache:
        return _help_cache[panel_id]

    # Load from root help/ directory per PRD specification
    # Path: help/panels/{panel_id}.json
    help_dir = Path(__file__).parent.parent.parent / "help" / "panels"
    panel_file = help_dir / f"{panel_id}.json"

    if panel_file.exists():
        try:
            with open(panel_file, "r") as f:
                content = json.load(f)
                _help_cache[panel_id] = content
                return content
        except Exception as e:
            print(f"Error loading help panel {panel_id}: {e}")

    return None


def load_tooltips() -> Dict[str, str]:
    """
    Load tooltip content from JSON file.

    Returns:
        Dict mapping tooltip IDs to tooltip text
    """
    if "tooltips" in _help_cache:
        return _help_cache["tooltips"]

    # Load from root help/ directory per PRD specification
    help_dir = Path(__file__).parent.parent.parent / "help"
    tooltips_file = help_dir / "tooltips.json"

    if tooltips_file.exists():
        try:
            with open(tooltips_file, "r") as f:
                content = json.load(f)
                _help_cache["tooltips"] = content.get("tooltips", {})
                return _help_cache["tooltips"]
        except Exception as e:
            print(f"Error loading tooltips: {e}")

    return {}


def load_glossary() -> Dict[str, Dict[str, str]]:
    """
    Load glossary content from JSON file.

    Returns:
        Dict mapping terms to definitions
    """
    if "glossary" in _help_cache:
        return _help_cache["glossary"]

    # Load from root help/ directory per PRD specification
    help_dir = Path(__file__).parent.parent.parent / "help"
    glossary_file = help_dir / "glossary.json"

    if glossary_file.exists():
        try:
            with open(glossary_file, "r") as f:
                content = json.load(f)
                _help_cache["glossary"] = content.get("terms", {})
                return _help_cache["glossary"]
        except Exception as e:
            print(f"Error loading glossary: {e}")

    return {}


def create_help_panel(
    panel_id: str,
    title: Optional[str] = None,
    default_open: bool = False,
) -> html.Div:
    """
    Create an expandable help panel.

    Args:
        panel_id: Panel identifier for loading content
        title: Optional override for panel title
        default_open: Whether panel starts expanded

    Returns:
        Dash component
    """
    content = load_help_content(panel_id)

    if content is None:
        # Return placeholder if content not found
        content = {
            "title": title or panel_id.replace("_", " ").title(),
            "sections": [
                {
                    "heading": "Help",
                    "content": "Help content for this section is not yet available.",
                }
            ],
        }

    panel_title = title or content.get("title", "Help")

    # Build sections
    sections = []
    for section in content.get("sections", []):
        section_content = []

        # Add heading
        if section.get("heading"):
            section_content.append(
                dmc.Text(section["heading"], fw=600, size="sm", mb="xs")
            )

        # Add main content
        if section.get("content"):
            section_content.append(
                dmc.Text(section["content"], size="sm", c="dimmed", mb="sm")
            )

        # Add subsections
        for subsection in section.get("subsections", []):
            section_content.append(
                dmc.Text(subsection.get("heading", ""), fw=500, size="sm", mb="xs", ml="md")
            )
            section_content.append(
                dmc.Text(subsection.get("content", ""), size="sm", c="dimmed", mb="sm", ml="md")
            )

        sections.append(html.Div(section_content, style={"marginBottom": "12px"}))

    # Add "Why this matters" if present
    if content.get("why_it_matters"):
        sections.append(
            dmc.Alert(
                title="Why this matters",
                children=dmc.Text(content["why_it_matters"], size="sm"),
                color="blue",
                icon=DashIconify(icon="mdi:lightbulb-outline", width=20),
            )
        )

    # Add related topics if present
    if content.get("related"):
        related_links = [
            dmc.Anchor(
                topic.replace("_", " ").title(),
                href=f"#help-{topic}",
                size="sm",
            )
            for topic in content["related"]
        ]
        sections.append(
            dmc.Group([
                dmc.Text("Related topics:", size="sm", c="dimmed"),
                *related_links,
            ], gap="xs", mt="md")
        )

    return dmc.Accordion(
        id=f"help-panel-{panel_id}",
        value=panel_id if default_open else None,
        children=[
            dmc.AccordionItem(
                value=panel_id,
                children=[
                    dmc.AccordionControl(
                        dmc.Group([
                            DashIconify(icon="mdi:help-circle-outline", width=18),
                            dmc.Text(f"Help: {panel_title}", size="sm"),
                        ], gap="xs"),
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(sections, gap="sm"),
                    ),
                ],
            ),
        ],
        styles={
            "control": {"backgroundColor": "#f8f9fa"},
            "panel": {"backgroundColor": "white"},
        },
    )


def create_tooltip(
    tooltip_id: str,
    children: Any,
    position: str = "top",
    multiline: bool = False,
    width: int = 300,
) -> dmc.Tooltip:
    """
    Create a tooltip with content from tooltips.json.

    Args:
        tooltip_id: Tooltip identifier
        children: Element to attach tooltip to
        position: Tooltip position
        multiline: Allow multiline text
        width: Max width for multiline

    Returns:
        Tooltip component
    """
    tooltips = load_tooltips()
    tooltip_text = tooltips.get(tooltip_id, f"Tooltip '{tooltip_id}' not found")

    return dmc.Tooltip(
        label=tooltip_text,
        children=children,
        position=position,
        multiline=multiline,
        w=width if multiline else None,
        withArrow=True,
    )


def create_info_icon_with_tooltip(
    tooltip_id: str,
    size: int = 16,
    color: str = "dimmed",
) -> dmc.Tooltip:
    """
    Create an info icon with tooltip.

    Args:
        tooltip_id: Tooltip identifier
        size: Icon size
        color: Icon color

    Returns:
        Info icon with tooltip
    """
    return create_tooltip(
        tooltip_id=tooltip_id,
        children=DashIconify(
            icon="mdi:information-outline",
            width=size,
            color=color if color != "dimmed" else "#868e96",
            style={"cursor": "help"},
        ),
        multiline=True,
    )


def create_glossary_term(
    term: str,
    inline: bool = True,
) -> Any:
    """
    Create a glossary term with popup definition.

    Args:
        term: Glossary term to look up
        inline: Whether to display inline or as block

    Returns:
        Component with term and definition popup
    """
    glossary = load_glossary()
    term_data = glossary.get(term.lower(), {})

    if not term_data:
        return dmc.Text(term, span=inline)

    definition = term_data.get("definition", "")
    see_also = term_data.get("see_also", [])

    tooltip_content = dmc.Stack([
        dmc.Text(definition, size="sm"),
        dmc.Group([
            dmc.Text("See also:", size="xs", c="dimmed"),
            *[dmc.Text(s, size="xs", c="blue") for s in see_also],
        ], gap="xs") if see_also else None,
    ], gap="xs")

    return dmc.HoverCard(
        children=[
            dmc.HoverCardTarget(
                dmc.Text(
                    term,
                    span=inline,
                    td="underline",
                    style={"textDecorationStyle": "dotted", "cursor": "help"},
                )
            ),
            dmc.HoverCardDropdown(tooltip_content),
        ],
        shadow="md",
        width=300,
    )


def create_help_button(
    panel_id: str,
    label: str = "Help",
) -> dmc.Button:
    """
    Create a help button that opens a help modal.

    Args:
        panel_id: Panel identifier
        label: Button label

    Returns:
        Help button component
    """
    return dmc.Button(
        label,
        id={"type": "help-button", "panel": panel_id},
        variant="subtle",
        size="xs",
        leftSection=DashIconify(icon="mdi:help-circle-outline", width=16),
    )


def create_quick_help(
    items: List[Dict[str, str]],
) -> dmc.Stack:
    """
    Create a quick help section with multiple tips.

    Args:
        items: List of dicts with 'icon', 'title', 'description'

    Returns:
        Quick help component
    """
    help_items = []
    for item in items:
        help_items.append(
            dmc.Group([
                DashIconify(
                    icon=item.get("icon", "mdi:information"),
                    width=20,
                    color="#228be6",
                ),
                dmc.Stack([
                    dmc.Text(item.get("title", ""), fw=500, size="sm"),
                    dmc.Text(item.get("description", ""), size="sm", c="dimmed"),
                ], gap=2),
            ], align="flex-start", gap="sm")
        )

    return dmc.Paper(
        dmc.Stack(help_items, gap="md"),
        p="md",
        withBorder=True,
        style={"backgroundColor": "#f8f9fa"},
    )
