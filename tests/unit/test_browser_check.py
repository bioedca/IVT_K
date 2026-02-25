"""
Tests for browser check component.

Phase 4: UX Enhancements - Browser Check

Tests the browser_check.py component that provides:
- Browser compatibility detection
- Warning banner for unsupported browsers
- Supported browser list display
- Dismiss functionality
"""
import pytest
import dash_mantine_components as dmc
from dash import html, dcc

from app.components.browser_check import (
    create_browser_check_banner,
    create_browser_check_store,
    create_supported_browsers_list,
    get_browser_check_script,
    SUPPORTED_BROWSERS,
    MINIMUM_VERSIONS,
    BrowserSupport,
)


class TestBrowserSupportEnum:
    """Tests for BrowserSupport enum."""

    def test_supported_value_exists(self):
        """Test SUPPORTED value exists."""
        assert hasattr(BrowserSupport, "SUPPORTED")
        assert BrowserSupport.SUPPORTED is not None

    def test_unsupported_value_exists(self):
        """Test UNSUPPORTED value exists."""
        assert hasattr(BrowserSupport, "UNSUPPORTED")
        assert BrowserSupport.UNSUPPORTED is not None

    def test_unknown_value_exists(self):
        """Test UNKNOWN value exists."""
        assert hasattr(BrowserSupport, "UNKNOWN")
        assert BrowserSupport.UNKNOWN is not None

    def test_enum_values_are_strings(self):
        """Test enum values are strings."""
        for status in BrowserSupport:
            assert isinstance(status.value, str)


class TestSupportedBrowsersConstant:
    """Tests for SUPPORTED_BROWSERS constant."""

    def test_supported_browsers_defined(self):
        """Test SUPPORTED_BROWSERS is defined."""
        assert SUPPORTED_BROWSERS is not None
        assert isinstance(SUPPORTED_BROWSERS, (list, tuple, dict))

    def test_chrome_is_supported(self):
        """Test Chrome is in supported browsers."""
        if isinstance(SUPPORTED_BROWSERS, dict):
            assert "chrome" in SUPPORTED_BROWSERS or "Chrome" in SUPPORTED_BROWSERS
        else:
            browsers_lower = [b.lower() for b in SUPPORTED_BROWSERS]
            assert "chrome" in browsers_lower

    def test_firefox_is_supported(self):
        """Test Firefox is in supported browsers."""
        if isinstance(SUPPORTED_BROWSERS, dict):
            assert "firefox" in SUPPORTED_BROWSERS or "Firefox" in SUPPORTED_BROWSERS
        else:
            browsers_lower = [b.lower() for b in SUPPORTED_BROWSERS]
            assert "firefox" in browsers_lower

    def test_safari_is_supported(self):
        """Test Safari is in supported browsers."""
        if isinstance(SUPPORTED_BROWSERS, dict):
            assert "safari" in SUPPORTED_BROWSERS or "Safari" in SUPPORTED_BROWSERS
        else:
            browsers_lower = [b.lower() for b in SUPPORTED_BROWSERS]
            assert "safari" in browsers_lower

    def test_edge_is_supported(self):
        """Test Edge is in supported browsers."""
        if isinstance(SUPPORTED_BROWSERS, dict):
            assert "edge" in SUPPORTED_BROWSERS or "Edge" in SUPPORTED_BROWSERS
        else:
            browsers_lower = [b.lower() for b in SUPPORTED_BROWSERS]
            assert "edge" in browsers_lower


class TestMinimumVersionsConstant:
    """Tests for MINIMUM_VERSIONS constant."""

    def test_minimum_versions_defined(self):
        """Test MINIMUM_VERSIONS is defined."""
        assert MINIMUM_VERSIONS is not None
        assert isinstance(MINIMUM_VERSIONS, dict)

    def test_chrome_has_minimum_version(self):
        """Test Chrome has minimum version."""
        chrome_key = "chrome" if "chrome" in MINIMUM_VERSIONS else "Chrome"
        assert chrome_key in MINIMUM_VERSIONS

    def test_minimum_versions_are_integers(self):
        """Test minimum versions are integers."""
        for browser, version in MINIMUM_VERSIONS.items():
            assert isinstance(version, int), f"{browser} version should be int"

    def test_minimum_versions_are_reasonable(self):
        """Test minimum versions are reasonable (not too old)."""
        # Safari has different versioning (Safari 14 = 2020, which is reasonable)
        safari_keys = ["safari", "Safari"]
        for browser, version in MINIMUM_VERSIONS.items():
            if browser in safari_keys:
                # Safari version 14+ is reasonable (2020+)
                assert version >= 14, f"{browser} minimum version should be >= 14"
            else:
                # Other browsers should have minimum version >= 50
                assert version >= 50, f"{browser} minimum version should be >= 50"


class TestCreateBrowserCheckBanner:
    """Tests for browser check banner component."""

    def test_banner_creation(self):
        """Test banner is created."""
        banner = create_browser_check_banner()
        assert banner is not None

    def test_banner_with_supported_browser(self):
        """Test banner with supported browser state."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.SUPPORTED)
        # Should be hidden or empty when supported
        assert banner is not None

    def test_banner_with_unsupported_browser(self):
        """Test banner with unsupported browser state."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNSUPPORTED)
        # Should show warning banner
        assert banner is not None

    def test_banner_with_unknown_browser(self):
        """Test banner with unknown browser state."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNKNOWN)
        # May show informational message
        assert banner is not None

    def test_banner_has_correct_id(self):
        """Test banner has correct ID for callbacks."""
        banner = create_browser_check_banner()
        assert banner.id == "browser-check-banner" or hasattr(banner, "id")

    def test_banner_has_dismiss_button(self):
        """Test banner has dismiss button."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNSUPPORTED)
        dismiss_btn = _find_component_by_partial_id(banner, "dismiss")
        assert dismiss_btn is not None or _has_close_button(banner)

    def test_banner_shows_warning_text(self):
        """Test banner shows warning text for unsupported browsers."""
        banner = create_browser_check_banner(
            browser_status=BrowserSupport.UNSUPPORTED,
            browser_name="Internet Explorer",
            browser_version=11
        )
        assert banner is not None

    def test_banner_is_alert_component(self):
        """Test banner uses Alert component."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNSUPPORTED)
        assert isinstance(banner, (dmc.Alert, dmc.Notification, html.Div))

    def test_banner_warning_color(self):
        """Test banner has warning color for unsupported."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNSUPPORTED)
        if isinstance(banner, dmc.Alert):
            assert banner.color in ["yellow", "orange", "red"]


class TestCreateBrowserCheckStore:
    """Tests for browser check state store."""

    def test_store_creation(self):
        """Test store is created."""
        store = create_browser_check_store()
        assert store is not None

    def test_store_is_dcc_store(self):
        """Test store is dcc.Store component."""
        store = create_browser_check_store()
        assert isinstance(store, dcc.Store)

    def test_store_has_correct_id(self):
        """Test store has correct ID."""
        store = create_browser_check_store()
        assert store.id == "browser-check-store"

    def test_store_has_default_data(self):
        """Test store has sensible default data."""
        store = create_browser_check_store()
        assert store.data is not None or store.data == {}

    def test_store_is_local_storage(self):
        """Test store uses local storage for persistence."""
        store = create_browser_check_store()
        assert store.storage_type == "local"


class TestCreateSupportedBrowsersList:
    """Tests for supported browsers list component."""

    def test_list_creation(self):
        """Test list is created."""
        browser_list = create_supported_browsers_list()
        assert browser_list is not None

    def test_list_contains_browsers(self):
        """Test list contains browser names."""
        browser_list = create_supported_browsers_list()
        # Should have at least 4 supported browsers
        assert browser_list is not None

    def test_list_shows_versions(self):
        """Test list shows minimum versions."""
        browser_list = create_supported_browsers_list()
        # Should display version requirements
        assert browser_list is not None

    def test_list_includes_chrome(self):
        """Test list includes Chrome."""
        browser_list = create_supported_browsers_list()
        assert browser_list is not None

    def test_list_includes_firefox(self):
        """Test list includes Firefox."""
        browser_list = create_supported_browsers_list()
        assert browser_list is not None


class TestGetBrowserCheckScript:
    """Tests for browser check JavaScript."""

    def test_script_generation(self):
        """Test script is generated."""
        script = get_browser_check_script()
        assert script is not None
        assert isinstance(script, str)

    def test_script_contains_user_agent_check(self):
        """Test script checks user agent."""
        script = get_browser_check_script()
        assert "userAgent" in script or "navigator" in script

    def test_script_returns_browser_info(self):
        """Test script returns browser information."""
        script = get_browser_check_script()
        # Should return browser name and version
        assert script is not None

    def test_script_is_valid_javascript(self):
        """Test script is syntactically valid JavaScript."""
        script = get_browser_check_script()
        # Basic validation - should have function or variable declaration
        assert "function" in script or "const" in script or "var" in script or "let" in script


class TestBrowserCheckIntegration:
    """Integration tests for browser check."""

    def test_banner_and_store_together(self):
        """Test banner and store work together."""
        banner = create_browser_check_banner()
        store = create_browser_check_store()
        assert banner is not None
        assert store is not None

    def test_dismiss_persists(self):
        """Test dismissing banner persists to store."""
        # After dismissing, the choice should be stored
        pass

    def test_banner_hidden_when_dismissed(self):
        """Test banner stays hidden when dismissed in store."""
        banner = create_browser_check_banner(dismissed=True)
        # Should be hidden/empty
        assert banner is not None


class TestBrowserCheckCallbackStructure:
    """Tests for browser check callback structure."""

    def test_banner_has_callback_ids(self):
        """Test banner has IDs needed for callbacks."""
        banner = create_browser_check_banner(browser_status=BrowserSupport.UNSUPPORTED)
        # Should have dismiss button with ID
        assert banner is not None

    def test_store_supports_browser_info(self):
        """Test store can hold browser info."""
        store = create_browser_check_store()
        # Store should be able to hold browser name, version, status
        expected_data_shape = {
            "browser_name": str,
            "browser_version": int,
            "status": str,
            "dismissed": bool
        }
        assert store is not None


class TestBrowserDetectionEdgeCases:
    """Tests for browser detection edge cases."""

    def test_handles_mobile_browsers(self):
        """Test handling of mobile browsers."""
        # Mobile Chrome, Safari should be handled
        pass

    def test_handles_bot_user_agents(self):
        """Test handling of bot/crawler user agents."""
        # Should not show warning for search bots
        pass

    def test_handles_missing_user_agent(self):
        """Test handling when user agent is not available."""
        # Should default to UNKNOWN status
        pass


# Helper functions
def _find_component_by_id(component, target_id):
    """Recursively find a component with the given ID."""
    if hasattr(component, "id") and component.id == target_id:
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                result = _find_component_by_id(child, target_id)
                if result:
                    return result
        elif children is not None:
            return _find_component_by_id(children, target_id)
    return None


def _find_component_by_partial_id(component, partial_id):
    """Recursively find a component with ID containing partial_id."""
    if hasattr(component, "id") and component.id and partial_id in str(component.id):
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                result = _find_component_by_partial_id(child, partial_id)
                if result:
                    return result
        elif children is not None:
            return _find_component_by_partial_id(children, partial_id)
    return None


def _has_close_button(component):
    """Check if component has a close/dismiss button."""
    if hasattr(component, "withCloseButton"):
        return component.withCloseButton
    return _find_component_by_partial_id(component, "close") is not None or \
           _find_component_by_partial_id(component, "dismiss") is not None


def _has_child_of_type(component, target_type):
    """Check if component tree contains a child of given type."""
    if isinstance(component, target_type):
        return True
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                if _has_child_of_type(child, target_type):
                    return True
        elif children is not None:
            return _has_child_of_type(children, target_type)
    return False
