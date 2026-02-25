"""
Comparison graph service for managing construct comparison hierarchies.

Handles building, saving, and validating comparison graphs that represent
the relationships between constructs (mutant vs WT, WT vs unregulated, etc.).
Also manages WT exclusion impact analysis, orphaned well detection,
derived comparison computation, and comparison summaries.

Split from comparison_service.py as part of Phase 3 refactoring.
"""
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

import numpy as np

from app.extensions import db
from app.models import Project, Construct
from app.models.experiment import Plate, Well, FitStatus
from app.models.fit_result import FoldChange
from app.models.comparison import (
    ComparisonGraph as ComparisonGraphModel,
    PathType as ModelPathType,
)
from app.analysis.comparison import (
    PairedAnalysis,
    ComparisonGraph,
    ComparisonType,
    PathType,
    FoldChangeResult,
    AnalysisScope,
)

logger = logging.getLogger(__name__)


class ComparisonError(Exception):
    """Raised when comparison computation fails."""
    pass


@dataclass
class ExclusionImpact:
    """Impact of excluding a WT well."""
    affected_mutant_wells: List[int]
    orphaned_mutant_count: int
    remaining_wt_count: int
    is_complete_exclusion: bool
    ci_widening_estimate: float
    warning_message: str


@dataclass
class ComparisonSummary:
    """Summary of comparisons for a project."""
    primary_count: int
    secondary_count: int
    tertiary_count: int
    mutant_mutant_count: int
    cross_family_count: int
    low_precision_count: int
    scope: AnalysisScope


class ComparisonGraphService:
    """
    Service for building and managing comparison graphs.

    Handles:
    - Graph construction from fold change data
    - Graph persistence and retrieval
    - Connectivity validation
    - WT exclusion impact analysis
    - Orphaned well detection
    - Derived comparison computation
    - Comparison summaries
    """

    @classmethod
    def build_comparison_graph(cls, project_id: int) -> ComparisonGraph:
        """
        Build comparison graph for a project.

        Args:
            project_id: Project ID

        Returns:
            ComparisonGraph with all constructs and paths
        """
        project = Project.query.get(project_id)
        if not project:
            raise ComparisonError(f"Project {project_id} not found")

        graph = ComparisonGraph()

        # Add all constructs (published = not draft)
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_draft=False
        ).all()

        for construct in constructs:
            graph.add_construct(
                construct_id=construct.id,
                family=construct.family,
                is_wildtype=construct.is_wildtype,
                is_unregulated=construct.is_unregulated
            )

        # Find direct comparisons from fold changes
        fold_changes = (
            db.session.query(
                FoldChange.test_well_id,
                FoldChange.control_well_id,
                Well.construct_id.label('test_construct_id')
            )
            .join(Well, FoldChange.test_well_id == Well.id)
            .join(Plate, Well.plate_id == Plate.id)
            .filter(Plate.session.has(project_id=project_id))
            .all()
        )

        # Batch-load control wells to avoid N+1
        control_well_ids = list({fc.control_well_id for fc in fold_changes})
        control_wells_by_id = {
            w.id: w
            for w in Well.query.filter(Well.id.in_(control_well_ids)).all()
        } if control_well_ids else {}

        # Count co-occurrences
        co_occurrence: Dict[Tuple[int, int], int] = {}
        for fc in fold_changes:
            control_well = control_wells_by_id.get(fc.control_well_id)

            if fc.test_construct_id and control_well:
                key = (fc.test_construct_id, control_well.construct_id)
                co_occurrence[key] = co_occurrence.get(key, 0) + 1

        # Add direct comparison edges
        for (source_id, target_id), count in co_occurrence.items():
            graph.add_direct_comparison(source_id, target_id, count)

        # Build derived paths
        graph.build_derived_paths()

        return graph

    @classmethod
    def save_comparison_graph(
        cls,
        project_id: int,
        graph: ComparisonGraph
    ) -> List[ComparisonGraphModel]:
        """
        Save comparison graph to database.

        Args:
            project_id: Project ID
            graph: ComparisonGraph to save

        Returns:
            List of saved ComparisonGraphModel records
        """
        # Clear existing graph for project
        ComparisonGraphModel.query.filter_by(project_id=project_id).delete()

        records = []
        for (source_id, target_id), path in graph.edges.items():
            # Map PathType to ModelPathType
            model_path_type = ModelPathType(path.path_type.value)

            record = ComparisonGraphModel(
                project_id=project_id,
                source_construct_id=source_id,
                target_construct_id=target_id,
                path_type=model_path_type,
                intermediate_construct_id=path.intermediates[0] if path.intermediates else None,
                co_occurrence_count=1,
                computed_at=datetime.now(timezone.utc)
            )
            db.session.add(record)
            records.append(record)

        db.session.commit()
        return records

    @classmethod
    def validate_graph_connectivity(cls, project_id: int) -> AnalysisScope:
        """
        Validate that the comparison graph is connected.

        Args:
            project_id: Project ID

        Returns:
            AnalysisScope indicating analysis capabilities
        """
        graph = cls.build_comparison_graph(project_id)
        return graph.determine_analysis_scope()

    @classmethod
    def propagate_wt_exclusion(
        cls,
        wt_well_id: int
    ) -> ExclusionImpact:
        """
        Calculate impact of excluding a WT well.

        Args:
            wt_well_id: ID of WT well to exclude

        Returns:
            ExclusionImpact with affected comparisons
        """
        wt_well = Well.query.get(wt_well_id)
        if not wt_well:
            raise ComparisonError(f"Well {wt_well_id} not found")

        wt_construct = Construct.query.get(wt_well.construct_id)
        if not wt_construct or not wt_construct.is_wildtype:
            raise ComparisonError(f"Well {wt_well_id} is not a wildtype well")

        plate = wt_well.plate

        # Find all other WT wells for this construct on this plate
        other_wt_wells = Well.query.filter(
            Well.plate_id == plate.id,
            Well.construct_id == wt_construct.id,
            Well.id != wt_well_id,
            Well.fit_status == FitStatus.SUCCESS
        ).count()

        # Find affected mutant wells (same family, same plate)
        family_mutants = Construct.query.filter(
            Construct.project_id == wt_construct.project_id,
            Construct.family == wt_construct.family,
            Construct.is_wildtype == False,
            Construct.is_unregulated == False
        ).all()

        mutant_ids = [m.id for m in family_mutants]

        affected_mutant_wells = Well.query.filter(
            Well.plate_id == plate.id,
            Well.construct_id.in_(mutant_ids),
            Well.fit_status == FitStatus.SUCCESS
        ).all()

        affected_ids = [w.id for w in affected_mutant_wells]

        # Count fold changes that would be invalidated
        fc_count = FoldChange.query.filter(
            FoldChange.control_well_id == wt_well_id
        ).count()

        # Determine if this is complete exclusion
        is_complete = (other_wt_wells == 0)

        # Estimate CI widening
        if other_wt_wells > 0:
            # Rough estimate: CI widens by sqrt(n/(n-1))
            original_n = other_wt_wells + 1
            new_n = other_wt_wells
            ci_widening = (np.sqrt(original_n / new_n) - 1) * 100
        else:
            ci_widening = float('inf')

        # Build warning message
        if is_complete:
            warning = (
                f"Complete WT exclusion: {len(affected_ids)} mutant wells "
                f"on plate {plate.plate_number} will become orphaned"
            )
        else:
            warning = (
                f"Partial WT exclusion: {fc_count} fold changes affected, "
                f"expected CI widening ~{ci_widening:.1f}%"
            )

        return ExclusionImpact(
            affected_mutant_wells=affected_ids,
            orphaned_mutant_count=len(affected_ids) if is_complete else 0,
            remaining_wt_count=other_wt_wells,
            is_complete_exclusion=is_complete,
            ci_widening_estimate=ci_widening,
            warning_message=warning
        )

    @classmethod
    def get_orphaned_wells(cls, project_id: int) -> List[Well]:
        """
        Get all orphaned wells (valid data but no comparison possible).

        Args:
            project_id: Project ID

        Returns:
            List of orphaned Well records
        """
        from sqlalchemy import exists, or_

        # Get all wells with successful fits that have NO fold changes
        # Use a NOT EXISTS subquery to avoid N+1
        fc_exists = exists().where(
            or_(
                FoldChange.test_well_id == Well.id,
                FoldChange.control_well_id == Well.id
            )
        )

        wells = (
            db.session.query(Well)
            .join(Plate, Well.plate_id == Plate.id)
            .join(Construct, Well.construct_id == Construct.id)
            .filter(
                Plate.session.has(project_id=project_id),
                Well.fit_status == FitStatus.SUCCESS,
                Well.construct_id.isnot(None),
                ~fc_exists,
                # Only mutants can be orphaned (WT and unreg are references)
                Construct.is_wildtype == False,
                Construct.is_unregulated == False,
            )
            .all()
        )

        return wells

    @classmethod
    def compute_derived_comparisons(
        cls,
        project_id: int,
        analysis_version_id: int
    ) -> Dict[str, Any]:
        """
        Compute all derived comparisons for a project.

        Args:
            project_id: Project ID
            analysis_version_id: Analysis version ID for storing results

        Returns:
            Summary of computed comparisons
        """
        from app.services.precision_weight_service import PrecisionWeightService

        graph = cls.build_comparison_graph(project_id)
        scope = graph.determine_analysis_scope()

        if not scope.can_analyze:
            raise ComparisonError(f"Cannot analyze project: {scope.warnings}")

        analyzer = PairedAnalysis()

        # Get all primary fold changes grouped by construct pair
        primary_fcs = cls._get_primary_fold_changes(project_id)

        # Compute tertiary comparisons (mutant vs unregulated)
        tertiary_count = 0
        if graph.unregulated_id and scope.scope in ('full', 'within_family_only'):
            for family, wt_id in graph.wildtypes.items():
                # Get WT vs unregulated FCs
                secondary_fcs = cls._get_secondary_fold_changes(project_id, wt_id)
                if not secondary_fcs:
                    continue

                # Get mutants in family
                for mutant_id in graph.families.get(family, []):
                    if mutant_id == wt_id:
                        continue

                    mutant_fcs = primary_fcs.get((mutant_id, wt_id), [])
                    for primary_fc in mutant_fcs:
                        for secondary_fc in secondary_fcs:
                            # Compute derived FC
                            derived = analyzer.compute_derived_fc(
                                primary_fc, secondary_fc
                            )
                            if derived.is_valid:
                                tertiary_count += 1

        # Compute mutant-to-mutant comparisons
        mutant_mutant_count = 0
        for family, construct_ids in graph.families.items():
            wt_id = graph.wildtypes.get(family)
            if not wt_id:
                continue

            mutants = [c for c in construct_ids if c != wt_id and c != graph.unregulated_id]

            for i, m1 in enumerate(mutants):
                for m2 in mutants[i+1:]:
                    fc_m1_wt = primary_fcs.get((m1, wt_id), [])
                    fc_m2_wt = primary_fcs.get((m2, wt_id), [])

                    if fc_m1_wt and fc_m2_wt:
                        mutant_mutant_count += 1

        # Store precision weights
        PrecisionWeightService.store_precision_weights(project_id, analysis_version_id, graph)

        return {
            'scope': scope.scope,
            'primary_count': len(primary_fcs),
            'tertiary_count': tertiary_count,
            'mutant_mutant_count': mutant_mutant_count,
            'warnings': scope.warnings
        }

    @classmethod
    def _get_primary_fold_changes(
        cls,
        project_id: int
    ) -> Dict[Tuple[int, int], List[FoldChangeResult]]:
        """Get primary fold changes grouped by construct pair."""
        # Join both test and control wells to avoid N+1 queries
        from sqlalchemy.orm import aliased
        ControlWell = aliased(Well, name='control_well')

        fold_changes = (
            db.session.query(
                FoldChange,
                Well.construct_id.label('test_construct_id'),
                ControlWell.construct_id.label('control_construct_id'),
            )
            .join(Well, FoldChange.test_well_id == Well.id)
            .join(ControlWell, FoldChange.control_well_id == ControlWell.id)
            .join(Plate, Well.plate_id == Plate.id)
            .filter(Plate.session.has(project_id=project_id))
            .all()
        )

        result: Dict[Tuple[int, int], List[FoldChangeResult]] = {}

        for fc, test_construct_id, control_construct_id in fold_changes:
            if not control_construct_id:
                continue

            key = (test_construct_id, control_construct_id)
            if key not in result:
                result[key] = []

            fc_result = FoldChangeResult(
                fc_fmax=fc.fc_fmax,
                fc_fmax_se=fc.fc_fmax_se,
                fc_kobs=fc.fc_kobs,
                fc_kobs_se=fc.fc_kobs_se,
                delta_tlag=fc.delta_tlag,
                delta_tlag_se=fc.delta_tlag_se,
                log_fc_fmax=fc.log_fc_fmax,
                log_fc_fmax_se=fc.log_fc_fmax_se,
                log_fc_kobs=fc.log_fc_kobs,
                log_fc_kobs_se=fc.log_fc_kobs_se,
                test_construct_id=test_construct_id,
                control_construct_id=control_construct_id,
                comparison_type=ComparisonType.PRIMARY
            )
            result[key].append(fc_result)

        return result

    @classmethod
    def _get_secondary_fold_changes(
        cls,
        project_id: int,
        wt_construct_id: int
    ) -> List[FoldChangeResult]:
        """Get secondary (WT vs unregulated) fold changes."""
        # Find unregulated construct
        unreg = Construct.query.filter_by(
            project_id=project_id,
            is_unregulated=True
        ).first()

        if not unreg:
            return []

        # Join control well to filter by unregulated construct (avoid N+1)
        from sqlalchemy.orm import aliased
        ControlWell = aliased(Well, name='control_well')

        fold_changes = (
            db.session.query(FoldChange)
            .join(Well, FoldChange.test_well_id == Well.id)
            .join(ControlWell, FoldChange.control_well_id == ControlWell.id)
            .join(Plate, Well.plate_id == Plate.id)
            .filter(
                Plate.session.has(project_id=project_id),
                Well.construct_id == wt_construct_id,
                ControlWell.construct_id == unreg.id
            )
            .all()
        )

        results = []
        for fc in fold_changes:
            fc_result = FoldChangeResult(
                fc_fmax=fc.fc_fmax,
                fc_fmax_se=fc.fc_fmax_se,
                log_fc_fmax=fc.log_fc_fmax,
                log_fc_fmax_se=fc.log_fc_fmax_se,
                test_construct_id=wt_construct_id,
                control_construct_id=unreg.id,
                comparison_type=ComparisonType.SECONDARY
            )
            results.append(fc_result)

        return results

    @classmethod
    def get_comparison_summary(cls, project_id: int) -> ComparisonSummary:
        """
        Get summary of all comparisons in a project.

        Args:
            project_id: Project ID

        Returns:
            ComparisonSummary with counts by type
        """
        graph = cls.build_comparison_graph(project_id)
        scope = graph.determine_analysis_scope()

        # Count by path type
        primary = sum(1 for p in graph.edges.values() if p.path_type == PathType.DIRECT)
        one_hop = sum(1 for p in graph.edges.values() if p.path_type == PathType.ONE_HOP)
        two_hop = sum(1 for p in graph.edges.values() if p.path_type == PathType.TWO_HOP)
        four_hop = sum(1 for p in graph.edges.values() if p.path_type == PathType.FOUR_HOP)

        # Count low precision from fold changes
        low_precision = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate, Well.plate_id == Plate.id).filter(
            Plate.session.has(project_id=project_id),
            FoldChange.log_fc_fmax_se > 0.25  # ~0.5 CI width at 95%
        ).count()

        return ComparisonSummary(
            primary_count=primary,
            secondary_count=0,  # Need to track separately
            tertiary_count=two_hop,
            mutant_mutant_count=one_hop,
            cross_family_count=four_hop,
            low_precision_count=low_precision,
            scope=scope
        )
