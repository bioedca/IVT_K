"""
Callbacks for user identity and browser compatibility.

Phase 1.10: User identity (localStorage username)
Phase 1.11: Browser compatibility checks
"""
from dash import callback, Output, Input, State, clientside_callback, no_update, ClientsideFunction


def register_user_callbacks(app):
    """Register callbacks for user identity management."""

    # Clientside callback to check browser compatibility on load
    clientside_callback(
        """
        function(pathname) {
            // Check browser compatibility
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

            const allFeaturesSupported = Object.values(requirements).every(v => v);

            // Check browser version
            const ua = navigator.userAgent;
            let browserOk = true;
            let browserName = "Unknown";
            let browserVersion = 0;

            if (ua.includes("Chrome/") && !ua.includes("Edg/")) {
                browserName = "Chrome";
                browserVersion = parseInt(ua.match(/Chrome\\/([0-9]+)/)?.[1] || "0");
                browserOk = browserVersion >= 90;
            } else if (ua.includes("Firefox/")) {
                browserName = "Firefox";
                browserVersion = parseInt(ua.match(/Firefox\\/([0-9]+)/)?.[1] || "0");
                browserOk = browserVersion >= 88;
            } else if (ua.includes("Safari/") && !ua.includes("Chrome")) {
                browserName = "Safari";
                browserVersion = parseInt(ua.match(/Version\\/([0-9]+)/)?.[1] || "0");
                browserOk = browserVersion >= 14;
            } else if (ua.includes("Edg/")) {
                browserName = "Edge";
                browserVersion = parseInt(ua.match(/Edg\\/([0-9]+)/)?.[1] || "0");
                browserOk = browserVersion >= 90;
            }

            return {
                supported: allFeaturesSupported && browserOk,
                features: requirements,
                browserOk: browserOk,
                browserName: browserName,
                browserVersion: browserVersion
            };
        }
        """,
        Output("browser-compat-store", "data"),
        Input("url", "pathname")
    )

    # Clientside callback to show/hide browser warning
    clientside_callback(
        """
        function(compatData) {
            if (!compatData) return {display: "none"};
            if (compatData.supported) return {display: "none"};
            return {display: "block"};
        }
        """,
        Output("browser-warning-banner", "style"),
        Input("browser-compat-store", "data")
    )

    # Clientside callback to load username from localStorage on page load
    clientside_callback(
        """
        function(pathname) {
            try {
                const username = localStorage.getItem('ivt_username');
                if (username) {
                    return {username: username, loaded: true};
                }
                return {username: null, loaded: true};
            } catch (e) {
                console.warn('localStorage not available:', e);
                return {username: null, loaded: true, error: e.message};
            }
        }
        """,
        Output("user-store", "data"),
        Input("url", "pathname")
    )

    # Clientside callback to show username modal if no username stored
    clientside_callback(
        """
        function(userData) {
            if (!userData || !userData.loaded) return window.dash_clientside.no_update;
            if (userData.username) return false;
            return true;
        }
        """,
        Output("username-modal", "opened"),
        Input("user-store", "data")
    )

    # Clientside callback to display current username
    clientside_callback(
        """
        function(userData) {
            if (!userData || !userData.username) return "";
            return "Logged in as: " + userData.username;
        }
        """,
        Output("current-user-display", "children"),
        Input("user-store", "data")
    )

    # Server-side callback to save username and close modal
    @app.callback(
        [Output("user-store", "data", allow_duplicate=True),
         Output("username-modal", "opened", allow_duplicate=True)],
        Input("username-submit-btn", "n_clicks"),
        State("username-input", "value"),
        prevent_initial_call=True
    )
    def register_user(n_clicks, username):
        """Handle user registration."""
        if not n_clicks or not username or not username.strip():
            return no_update, no_update
            
        # Create user data
        user_data = {"username": username.strip(), "loaded": True}
        
        # Return data and CLOSE the modal (False)
        return user_data, False

    # Clientside callback to save username to localStorage when user-store updates
    clientside_callback(
        """
        function(userData) {
            if (userData && userData.username) {
                try {
                    localStorage.setItem('ivt_username', userData.username);
                } catch (e) {
                    console.warn('Could not save username:', e);
                }
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("clientside-output", "children"),
        Input("user-store", "data")
    )

    # Dark/light mode toggle: click toggles the stored scheme
    clientside_callback(
        """
        function(n_clicks, currentScheme) {
            if (!n_clicks) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            var newScheme = (currentScheme === 'dark') ? 'light' : 'dark';
            return [newScheme, newScheme];
        }
        """,
        Output("color-scheme-store", "data"),
        Output("mantine-provider", "forceColorScheme"),
        Input("color-scheme-toggle", "n_clicks"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )

    # On page load, apply stored color scheme preference (default to light)
    clientside_callback(
        """
        function(storedScheme) {
            if (!storedScheme) return 'light';
            return storedScheme;
        }
        """,
        Output("mantine-provider", "forceColorScheme", allow_duplicate=True),
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
