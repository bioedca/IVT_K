"""
Browser check component for compatibility detection.

Phase 4: UX Enhancements - Browser Check

Provides:
- Browser compatibility detection
- Warning banner for unsupported browsers
- Supported browser list display
- Dismiss functionality
"""
from typing import Optional, Dict, Any
from enum import Enum

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


class BrowserSupport(str, Enum):
    """Browser support status values."""
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


# List of supported browsers
SUPPORTED_BROWSERS = {
    "Chrome": "chrome",
    "Firefox": "firefox",
    "Safari": "safari",
    "Edge": "edge",
    "Opera": "opera",
}

# Minimum browser versions for full support
MINIMUM_VERSIONS = {
    "chrome": 90,
    "Chrome": 90,
    "firefox": 88,
    "Firefox": 88,
    "safari": 14,
    "Safari": 14,
    "edge": 90,
    "Edge": 90,
    "opera": 76,
    "Opera": 76,
}

# Icons for browsers
BROWSER_ICONS = {
    "chrome": "logos:chrome",
    "Chrome": "logos:chrome",
    "firefox": "logos:firefox",
    "Firefox": "logos:firefox",
    "safari": "logos:safari",
    "Safari": "logos:safari",
    "edge": "logos:microsoft-edge",
    "Edge": "logos:microsoft-edge",
    "opera": "logos:opera",
    "Opera": "logos:opera",
}


def create_browser_check_store() -> dcc.Store:
    """
    Create store for browser check state.

    Returns:
        Store component with default browser check data.
    """
    return dcc.Store(
        id="browser-check-store",
        data={
            "browser_name": None,
            "browser_version": None,
            "status": BrowserSupport.UNKNOWN.value,
            "dismissed": False
        },
        storage_type="local"
    )


def create_browser_check_banner(
    browser_status: BrowserSupport = BrowserSupport.UNKNOWN,
    browser_name: Optional[str] = None,
    browser_version: Optional[int] = None,
    dismissed: bool = False
) -> dmc.Alert:
    """
    Create warning banner for unsupported browsers.

    Args:
        browser_status: Current browser support status.
        browser_name: Name of the detected browser.
        browser_version: Version of the detected browser.
        dismissed: Whether the banner has been dismissed.

    Returns:
        Alert component with browser warning or empty div if supported.
    """
    # Don't show if dismissed or supported
    if dismissed or browser_status == BrowserSupport.SUPPORTED:
        return dmc.Alert(
            id="browser-check-banner",
            children=None,
            style={"display": "none"}
        )

    # Build message based on status
    if browser_status == BrowserSupport.UNSUPPORTED:
        if browser_name and browser_version:
            message = (
                f"Your browser ({browser_name} {browser_version}) may not be fully supported. "
                f"For the best experience, please use a recent version of Chrome, Firefox, Safari, or Edge."
            )
        else:
            message = (
                "Your browser may not be fully supported. "
                "For the best experience, please use a recent version of Chrome, Firefox, Safari, or Edge."
            )
        color = "yellow"
        icon = "tabler:alert-triangle"
    else:  # UNKNOWN
        message = (
            "Unable to detect your browser. "
            "For the best experience, use Chrome, Firefox, Safari, or Edge."
        )
        color = "gray"
        icon = "tabler:info-circle"

    return dmc.Alert(
        id="browser-check-banner",
        title="Browser Compatibility",
        children=dmc.Stack(
            [
                dmc.Text(message, size="sm"),
                dmc.Group(
                    [
                        create_supported_browsers_list(),
                        dmc.Button(
                            id="browser-check-dismiss",
                            children="Dismiss",
                            variant="subtle",
                            color="gray",
                            size="xs"
                        )
                    ],
                    justify="space-between",
                    mt="xs"
                )
            ],
            gap="xs"
        ),
        color=color,
        icon=DashIconify(icon=icon, width=20),
        withCloseButton=True,
        mb="md"
    )


def create_supported_browsers_list() -> dmc.Group:
    """
    Create a list of supported browsers with icons.

    Returns:
        Group component with browser icons and minimum versions.
    """
    items = []

    for browser_name, browser_key in SUPPORTED_BROWSERS.items():
        min_version = MINIMUM_VERSIONS.get(browser_key, 0)
        icon = BROWSER_ICONS.get(browser_key, "tabler:browser")

        items.append(
            dmc.Tooltip(
                label=f"{browser_name} {min_version}+",
                children=dmc.ThemeIcon(
                    DashIconify(icon=icon, width=20),
                    variant="subtle",
                    size="md"
                )
            )
        )

    return dmc.Group(
        children=items,
        gap="xs"
    )


def get_browser_check_script() -> str:
    """
    Get JavaScript code for browser detection.

    Returns:
        JavaScript code string to detect browser and version.
    """
    return """
    (function() {
        const userAgent = navigator.userAgent;
        let browserName = 'unknown';
        let browserVersion = 0;

        // Detect browser
        if (userAgent.indexOf('Chrome') > -1 && userAgent.indexOf('Edg') === -1) {
            browserName = 'Chrome';
            const match = userAgent.match(/Chrome\\/([0-9]+)/);
            if (match) browserVersion = parseInt(match[1]);
        } else if (userAgent.indexOf('Firefox') > -1) {
            browserName = 'Firefox';
            const match = userAgent.match(/Firefox\\/([0-9]+)/);
            if (match) browserVersion = parseInt(match[1]);
        } else if (userAgent.indexOf('Safari') > -1 && userAgent.indexOf('Chrome') === -1) {
            browserName = 'Safari';
            const match = userAgent.match(/Version\\/([0-9]+)/);
            if (match) browserVersion = parseInt(match[1]);
        } else if (userAgent.indexOf('Edg') > -1) {
            browserName = 'Edge';
            const match = userAgent.match(/Edg\\/([0-9]+)/);
            if (match) browserVersion = parseInt(match[1]);
        } else if (userAgent.indexOf('Opera') > -1 || userAgent.indexOf('OPR') > -1) {
            browserName = 'Opera';
            const match = userAgent.match(/(?:Opera|OPR)\\/([0-9]+)/);
            if (match) browserVersion = parseInt(match[1]);
        }

        // Check support status
        const minimumVersions = {
            'Chrome': 90,
            'Firefox': 88,
            'Safari': 14,
            'Edge': 90,
            'Opera': 76
        };

        let status = 'unknown';
        if (browserName !== 'unknown') {
            const minVersion = minimumVersions[browserName] || 0;
            status = browserVersion >= minVersion ? 'supported' : 'unsupported';
        }

        return {
            browser_name: browserName,
            browser_version: browserVersion,
            status: status
        };
    })();
    """


def create_browser_check_component() -> dmc.Box:
    """
    Create the complete browser check component.

    This includes the store for state and the banner.

    Returns:
        Box component with store and banner.
    """
    return dmc.Box(
        id="browser-check-container",
        children=[
            create_browser_check_store(),
            create_browser_check_banner()
        ]
    )
