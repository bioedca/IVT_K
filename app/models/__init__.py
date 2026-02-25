"""SQLAlchemy ORM models for IVT Kinetics Analyzer."""
from app.models.project import Project
from app.models.family import Family
from app.models.construct import Construct
from app.models.plate_layout import PlateLayout, WellAssignment
from app.models.reaction_setup import ReactionSetup, ReactionDNAAddition
from app.models.experiment import ExperimentalSession, Plate, Reaction, Well, RawDataPoint, QCStatus
from app.models.fit_result import FitResult, FitResultArchive, FoldChange, SignalQualityMetrics
from app.models.analysis_version import (
    AnalysisVersion,
    HierarchicalResult,
    ParameterCorrelation,
    MCMCCheckpoint
)
from app.models.comparison import ComparisonGraph, PrecisionWeight, PrecisionHistory, PrecisionOverride
from app.models.background import BackgroundEstimate
from app.models.methods_text import MethodsText
from app.models.archive import ProjectArchive
from app.models.audit_log import AuditLog, UserSession
from app.models.task_progress import TaskProgress, TaskStatus, TaskType
# Phase 4: Warning suppression
from app.models.warning_suppression import WarningSuppression, WarningType
# Phase 1 Security: Database-backed upload tracking
from app.models.upload import Upload, UploadStatus
# Access gate logging
from app.models.access_log import AccessLog
# Shared enums for model columns (Phase 2)
from app.models.enums import FoldChangeCategory, LigandCondition

__all__ = [
    # Core entities
    "Project",
    "Family",
    "Construct",
    "PlateLayout",
    "WellAssignment",
    # Reaction setup
    "ReactionSetup",
    "ReactionDNAAddition",
    # Experimental data
    "ExperimentalSession",
    "Plate",
    "Reaction",
    "Well",
    "RawDataPoint",
    "QCStatus",
    # Fit results
    "FitResult",
    "FitResultArchive",
    "FoldChange",
    "SignalQualityMetrics",
    # Analysis
    "AnalysisVersion",
    "HierarchicalResult",
    "ParameterCorrelation",
    "MCMCCheckpoint",
    # Comparison
    "ComparisonGraph",
    "PrecisionWeight",
    "PrecisionHistory",
    "PrecisionOverride",
    # Supporting
    "BackgroundEstimate",
    "MethodsText",
    "ProjectArchive",
    "AuditLog",
    "UserSession",
    # Task tracking
    "TaskProgress",
    "TaskStatus",
    "TaskType",
    # Warning suppression (Phase 4)
    "WarningSuppression",
    "WarningType",
    # Upload tracking (Phase 1 Security)
    "Upload",
    "UploadStatus",
    # Access gate
    "AccessLog",
    # Shared enums (Phase 2)
    "FoldChangeCategory",
    "LigandCondition",
]
