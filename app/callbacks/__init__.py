"""Dash callbacks for interactive UI functionality."""
from app.callbacks.user_callbacks import register_user_callbacks
from app.callbacks.project_callbacks import register_project_callbacks
from app.callbacks.calculator_callbacks import register_calculator_callbacks
from app.callbacks.repair_callbacks import register_repair_callbacks
from app.callbacks.negative_control_callbacks import register_negative_control_callbacks
from app.callbacks.curve_browser_callbacks import register_curve_browser_callbacks
from app.callbacks.analysis_callbacks import register_analysis_callbacks
from app.callbacks.precision_callbacks import register_precision_callbacks
from app.callbacks.cross_project_callbacks import register_cross_project_callbacks
from app.callbacks.hub_callbacks import register_hub_callbacks
from app.callbacks.layout_callbacks import register_layout_callbacks
from app.callbacks.upload_callbacks import register_upload_callbacks
from app.callbacks.routing_callbacks import register_routing_callbacks
from app.callbacks.construct_registry_callbacks import register_construct_registry_callbacks
from app.callbacks.publication_export_callbacks import register_publication_export_callbacks
from app.callbacks.digestion_callbacks import register_digestion_callbacks
from app.callbacks.access_log_callbacks import register_access_log_callbacks


def register_callbacks(app):
    """Register all application callbacks."""
    # Page routing (must be registered early)
    register_routing_callbacks(app)
    # Phase 1: Hub navigation and step unlock logic
    register_hub_callbacks(app)
    # Phase 1.10, 1.11: User identity and browser compatibility
    register_user_callbacks(app)
    # Phase 2.8, 2.9: Project dashboard and settings
    register_project_callbacks(app)
    # Phase 2.5.34: Calculator UI
    register_calculator_callbacks(app)
    # Phase 3.7: Repair wizard
    register_repair_callbacks(app)
    # Phase 3.5.8: Negative control dashboard
    register_negative_control_callbacks(app)
    # Phase 4.12: Curve browser
    register_curve_browser_callbacks(app)
    # Phase 5.5-5.7: Analysis results (posterior summaries)
    register_analysis_callbacks(app)
    # Phase 7.1: Precision dashboard
    register_precision_callbacks(app)
    # Sprint 8: Cross-project comparison
    register_cross_project_callbacks(app)
    # Phase 2: Plate layout editor
    register_layout_callbacks(app)
    # Phase 3: Data upload workflow
    register_upload_callbacks(app)
    # Phase C: Construct registry
    register_construct_registry_callbacks(app)
    # Phase 9: Publication export & daily report
    register_publication_export_callbacks(app)
    # Standalone tools
    register_digestion_callbacks(app)
    # Admin pages
    register_access_log_callbacks(app)
