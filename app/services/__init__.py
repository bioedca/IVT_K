"""Business logic layer for IVT Kinetics Analyzer."""
from app.services.task_service import (
    TaskService,
    tracked_task,
    enqueue_curve_fitting,
    enqueue_mcmc_sampling
)
from app.services.task_progress_service import TaskProgressService
from app.services.conflict_service import (
    ConflictDetectionService,
    ConflictResolution,
    ConflictInfo,
    ConflictAwareModel,
    check_and_save_with_conflict_detection
)
from app.services.project_service import ProjectService, ProjectValidationError
from app.services.construct_service import ConstructService, ConstructValidationError
from app.services.plate_layout_service import PlateLayoutService, PlateLayoutValidationError
from app.services.upload_service import UploadService, UploadValidationError, UploadProcessingError
# Fitting service (Phase 3 split: fit_computation, fold_change_calculation, fit_management)
from app.services.fitting_service import FittingService, FittingError, BatchFitResult
from app.services.fit_computation_service import FitComputationService, BatchFitProgress, BatchProcessingResult
from app.services.fold_change_calculation_service import FoldChangeCalculationService
from app.services.fit_management_service import FitManagementService
from app.services.hierarchical_service import (
    HierarchicalService, HierarchicalAnalysisError, AnalysisConfig
)
# Comparison service (Phase 3 split: fold_change, comparison_graph, precision_weight)
from app.services.comparison_service import (
    ComparisonService, ComparisonError, ExclusionImpact, ComparisonSummary
)
from app.services.fold_change_service import FoldChangeService
from app.services.comparison_graph_service import ComparisonGraphService
from app.services.precision_weight_service import PrecisionWeightService
# Renamed from calculator_service.py per PRD
from app.services.reaction_calculator_service import CalculatorService
from app.services.smart_planner_service import (
    SmartPlannerService,
    SmartPlannerError,
    ProjectConstraintValidation,
)
# Export service (Phase 3 split: protocol_export, figure_export, data_export)
from app.services.export_service import ExportService
from app.services.protocol_export_service import ProtocolExportService
from app.services.figure_export_service import FigureExportService
from app.services.data_export_service import DataExportService
from app.services.methods_text_service import (
    MethodsTextService,
    MethodsTextConfig,
    MethodsTextError,
)
from app.services.publication_package_service import (
    PublicationPackageService,
    PublicationPackageConfig,
    PublicationPackageError,
    FileHash,
)
from app.services.validation_service import (
    ValidationService,
    ValidationResult,
    ValidationCertificate,
    DiffReport,
    ValidationError,
)
from app.services.package_validation_service import (
    PackageValidationService,
    PackageValidationResult,
    PackageValidationError,
    VersionInfo,
    VersionCheck,
    ValidationProgress,
)
from app.services.audit_service import (
    AuditService,
    AuditQueryFilter,
    AuditServiceError,
)
from app.services.cross_project_service import (
    CrossProjectComparisonService,
    ProjectConstructMatch,
    ConstructComparisonData,
    CrossProjectSummary,
)
# Phase 4: Warning suppression
from app.services.warning_suppression_service import (
    WarningSuppressionService,
    WarningSuppressionError,
    suppress_warning,
    get_suppressed_warnings,
    is_warning_suppressed,
    get_suppression_history,
    MINIMUM_REASON_LENGTH,
)
# Phase B: Service Layer Completion
from app.services.power_analysis_service import (
    PowerAnalysisService,
    PowerAnalysisServiceError,
    PrecisionDashboard,
    ConstructPrecisionSummary,
    CoplatingRecommendation,
)
from app.services.statistics_service import (
    StatisticsService,
    StatisticsServiceError,
    AssumptionCheckResult,
)

__all__ = [
    # Task management
    "TaskService",
    "TaskProgressService",
    "tracked_task",
    "enqueue_curve_fitting",
    "enqueue_mcmc_sampling",
    # Conflict detection
    "ConflictDetectionService",
    "ConflictResolution",
    "ConflictInfo",
    "ConflictAwareModel",
    "check_and_save_with_conflict_detection",
    # Project and Construct management
    "ProjectService",
    "ProjectValidationError",
    "ConstructService",
    "ConstructValidationError",
    # Plate layout management
    "PlateLayoutService",
    "PlateLayoutValidationError",
    # Upload service
    "UploadService",
    "UploadValidationError",
    "UploadProcessingError",
    # Fitting service (facade + sub-services)
    "FittingService",
    "FittingError",
    "BatchFitResult",
    "FitComputationService",
    "BatchFitProgress",
    "BatchProcessingResult",
    "FoldChangeCalculationService",
    "FitManagementService",
    # Hierarchical analysis
    "HierarchicalService",
    "HierarchicalAnalysisError",
    "AnalysisConfig",
    # Comparison hierarchy (facade + sub-services)
    "ComparisonService",
    "ComparisonError",
    "ExclusionImpact",
    "ComparisonSummary",
    "FoldChangeService",
    "ComparisonGraphService",
    "PrecisionWeightService",
    # Calculator service
    "CalculatorService",
    # Smart planner service
    "SmartPlannerService",
    "SmartPlannerError",
    "ProjectConstraintValidation",
    # Export service (facade + sub-services)
    "ExportService",
    "ProtocolExportService",
    "FigureExportService",
    "DataExportService",
    # Methods text service
    "MethodsTextService",
    "MethodsTextConfig",
    "MethodsTextError",
    # Publication package service
    "PublicationPackageService",
    "PublicationPackageConfig",
    "PublicationPackageError",
    "FileHash",
    # Validation service
    "ValidationService",
    "ValidationResult",
    "ValidationCertificate",
    "DiffReport",
    "ValidationError",
    # Package validation service (F15.11-F15.16)
    "PackageValidationService",
    "PackageValidationResult",
    "PackageValidationError",
    "VersionInfo",
    "VersionCheck",
    "ValidationProgress",
    # Audit service
    "AuditService",
    "AuditQueryFilter",
    "AuditServiceError",
    # Cross-project comparison service (Sprint 8)
    "CrossProjectComparisonService",
    "ProjectConstructMatch",
    "ConstructComparisonData",
    "CrossProjectSummary",
    # Warning suppression (Phase 4)
    "WarningSuppressionService",
    "WarningSuppressionError",
    "suppress_warning",
    "get_suppressed_warnings",
    "is_warning_suppressed",
    "get_suppression_history",
    "MINIMUM_REASON_LENGTH",
    # Power Analysis Service (Phase B)
    "PowerAnalysisService",
    "PowerAnalysisServiceError",
    "PrecisionDashboard",
    "ConstructPrecisionSummary",
    "CoplatingRecommendation",
    # Statistics Service (Phase B)
    "StatisticsService",
    "StatisticsServiceError",
    "AssumptionCheckResult",
]
