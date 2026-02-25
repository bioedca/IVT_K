"""
Main application layout with user identity, browser compatibility, and Scientific Editorial theme.

Phase 1.10: User identity (localStorage username)
Phase 1.11: Browser compatibility checks
UX Overhaul: Theme, dark mode, sidebar navigation, breadcrumbs, header tooltips
"""
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app.theme import SCIENTIFIC_THEME


def create_main_layout():
    """
    Create the main application layout.

    Includes:
    - Scientific Editorial theme via MantineProvider
    - Dark/light mode toggle with localStorage persistence
    - Browser compatibility check
    - User identity modal for username entry
    - Sidebar navigation for project pages
    - Breadcrumb navigation
    - Navigation header with tooltips
    - Main content area
    """
    from app.layouts.project_list import create_project_list_layout

    return dmc.MantineProvider(
        id="mantine-provider",
        theme=SCIENTIFIC_THEME,
        forceColorScheme="light",
        children=[
            # Notification provider (required for dmc.Notification action="show")
            dmc.NotificationProvider(position="top-right"),

            # Client-side PIN gate check — redirects stale sessions to login
            html.Script("""
                fetch("/auth/status")
                    .then(r => { if (r.ok) return r.json(); throw new Error(r.status); })
                    .then(d => { if (!d.authenticated) window.location.replace("/auth/login"); })
                    .catch(e => console.warn("Auth check failed:", e));
            """),

            # Hidden stores for client-side state
            dcc.Store(id="user-store", storage_type="local"),
            dcc.Store(id="browser-compat-store", storage_type="session"),
            dcc.Store(id="conflict-check-store", storage_type="memory"),
            dcc.Store(id="refit-wells-store", storage_type="session"),  # Wells to select in analysis for refit
            dcc.Store(id="color-scheme-store", storage_type="local", data="light"),  # Dark/light mode preference

            # Location for routing
            dcc.Location(id="url", refresh=False),

            # Browser compatibility warning banner (hidden by default)
            html.Div(
                id="browser-warning-banner",
                children=[
                    dmc.Alert(
                        title="Unsupported Browser",
                        color="red",
                        children=[
                            html.P([
                                "Your browser may not be fully supported. ",
                                "For the best experience, please use a recent version of ",
                                "Chrome (90+), Firefox (88+), Safari (14+), or Edge (90+)."
                            ]),
                            html.P([
                                "Some features may not work correctly in your current browser."
                            ], style={"marginBottom": 0}),
                        ],
                        withCloseButton=True,
                        id="browser-warning-alert"
                    )
                ],
                style={"display": "none"}
            ),

            # User identity modal (shown on first visit)
            dmc.Modal(
                id="username-modal",
                title="Welcome to IVT Kinetics Analyzer",
                centered=True,
                closeOnClickOutside=False,
                closeOnEscape=False,
                withCloseButton=False,
                children=[
                    html.P(
                        "Please enter your name for audit tracking. "
                        "This will be stored locally in your browser.",
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.TextInput(
                        id="username-input",
                        label="Your Name",
                        placeholder="e.g., John Smith",
                        required=True,
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Continue",
                                id="username-submit-btn",
                                color="blue"
                            )
                        ],
                        justify="flex-end"
                    )
                ],
                opened=False
            ),

            # Main application shell
            dmc.AppShell(
                children=[
                    # Header
                    dmc.AppShellHeader(
                        children=[
                            dmc.Group(
                                children=[
                                    # Left section: back, title, breadcrumbs
                                    dmc.Group(
                                        children=[
                                            dmc.Tooltip(
                                                dmc.ActionIcon(
                                                    DashIconify(icon="ion:arrow-back-outline", width=20),
                                                    size="lg",
                                                    variant="subtle",
                                                    id="global-back-btn",
                                                    color="gray",
                                                    mb=2
                                                ),
                                                label="Go Back",
                                                position="bottom",
                                            ),
                                            dmc.Title(
                                                "IVT Kinetics Analyzer",
                                                order=3,
                                                style={"margin": 0}
                                            ),
                                            dmc.Badge(
                                                "v0.1.0",
                                                color="gray",
                                                variant="light",
                                                size="sm"
                                            ),
                                            # Breadcrumb container (populated by callback)
                                            html.Div(
                                                id="breadcrumb-container",
                                                style={"marginLeft": "0.5rem"},
                                            ),
                                        ],
                                        gap="xs"
                                    ),
                                    # Right section: user, actions
                                    dmc.Group(
                                        children=[
                                            dmc.Text(
                                                id="current-user-display",
                                                size="sm",
                                                c="dimmed"
                                            ),
                                            dmc.Tooltip(
                                                dcc.Link(
                                                    dmc.ActionIcon(
                                                        DashIconify(icon="mdi:shield-lock", width=18),
                                                        variant="subtle",
                                                        color="gray",
                                                        size="lg",
                                                    ),
                                                    href="/admin/access-log",
                                                ),
                                                label="Access Log",
                                                position="bottom",
                                            ),
                                            # Logout button (submits POST to /auth/logout)
                                            dmc.Tooltip(
                                                html.Form(
                                                    children=[
                                                        html.Button(
                                                            DashIconify(icon="mdi:logout", width=18),
                                                            type="submit",
                                                            style={
                                                                "background": "none",
                                                                "border": "none",
                                                                "cursor": "pointer",
                                                                "padding": "4px",
                                                                "borderRadius": "4px",
                                                                "color": "var(--mantine-color-gray-6)",
                                                                "display": "flex",
                                                                "alignItems": "center",
                                                            },
                                                        ),
                                                    ],
                                                    method="POST",
                                                    action="/auth/logout",
                                                    style={"display": "inline"},
                                                ),
                                                label="Sign Out",
                                                position="bottom",
                                            ),
                                            # Dark/light mode toggle
                                            dmc.Tooltip(
                                                dmc.ActionIcon(
                                                    DashIconify(icon="mdi:brightness-6", width=18),
                                                    id="color-scheme-toggle",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="lg",
                                                ),
                                                label="Toggle Dark Mode",
                                                position="bottom",
                                            ),
                                            dmc.Tooltip(
                                                dmc.ActionIcon(
                                                    dmc.Text("?", size="sm", fw=700),
                                                    id="help-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="lg"
                                                ),
                                                label="Help",
                                                position="bottom",
                                            ),
                                        ],
                                        gap="md"
                                    )
                                ],
                                justify="space-between",
                                style={"width": "100%", "padding": "0 1rem"}
                            )
                        ],
                        style={"display": "flex", "alignItems": "center"}
                    ),

                    # Sidebar navigation (populated by callback, hidden on non-project pages)
                    dmc.AppShellNavbar(
                        id="app-sidebar",
                        children=[
                            html.Div(id="sidebar-nav-content")
                        ],
                    ),

                    # Main content area
                    dmc.AppShellMain(
                        children=[
                            html.Div(
                                id="page-content",
                                children=[
                                    # Load project list by default
                                    create_project_list_layout()
                                ]
                            )
                        ]
                    )
                ],
                header={"height": 60},
                navbar={"width": 220, "breakpoint": "sm"},
                padding="md",
            ),

            # Hidden div for clientside callback outputs
            html.Div(id="clientside-output", style={"display": "none"})
        ]
    )


# JavaScript for browser compatibility detection
BROWSER_COMPAT_SCRIPT = """
function checkBrowserCompatibility() {
    const requirements = {
        localStorage: typeof(Storage) !== "undefined",
        fetch: typeof(fetch) !== "undefined",
        cssGrid: CSS.supports && CSS.supports("display", "grid"),
        es6: (function() {
            try {
                new Function("(a = 0) => a");
                return true;
            } catch (e) {
                return false;
            }
        })()
    };

    const allSupported = Object.values(requirements).every(v => v);

    // Check browser version (approximate)
    const ua = navigator.userAgent;
    let browserOk = true;

    if (ua.includes("Chrome/")) {
        const version = parseInt(ua.match(/Chrome\\/([0-9]+)/)?.[1] || "0");
        browserOk = version >= 90;
    } else if (ua.includes("Firefox/")) {
        const version = parseInt(ua.match(/Firefox\\/([0-9]+)/)?.[1] || "0");
        browserOk = version >= 88;
    } else if (ua.includes("Safari/") && !ua.includes("Chrome")) {
        const version = parseInt(ua.match(/Version\\/([0-9]+)/)?.[1] || "0");
        browserOk = version >= 14;
    } else if (ua.includes("Edg/")) {
        const version = parseInt(ua.match(/Edg\\/([0-9]+)/)?.[1] || "0");
        browserOk = version >= 90;
    }

    return {
        supported: allSupported && browserOk,
        features: requirements,
        browserOk: browserOk
    };
}
"""


# JavaScript for localStorage username management
USERNAME_STORAGE_SCRIPT = """
function getStoredUsername() {
    try {
        return localStorage.getItem('ivt_username') || null;
    } catch (e) {
        console.warn('localStorage not available:', e);
        return null;
    }
}

function setStoredUsername(username) {
    try {
        localStorage.setItem('ivt_username', username);
        return true;
    } catch (e) {
        console.warn('Could not save username:', e);
        return false;
    }
}
"""
