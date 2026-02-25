"""
Precision weight service for storing variance inflation and precision weights.

Handles computation and persistence of precision weights for comparison paths
in the comparison graph, based on variance inflation factors.

Split from comparison_service.py as part of Phase 3 refactoring.
"""
import logging

from app.extensions import db
from app.models.comparison import (
    ComparisonGraph as ComparisonGraphModel,
    PrecisionWeight,
)
from app.analysis.comparison import ComparisonGraph

logger = logging.getLogger(__name__)


class PrecisionWeightService:
    """
    Service for computing and storing precision weights.

    Handles:
    - Variance inflation factor computation per comparison path
    - Precision weight storage for analysis versions
    """

    @classmethod
    def store_precision_weights(
        cls,
        project_id: int,
        analysis_version_id: int,
        graph: ComparisonGraph
    ) -> None:
        """Store precision weights for all comparison paths."""
        # Get or create comparison graph records
        graph_records = ComparisonGraphModel.query.filter_by(
            project_id=project_id
        ).all()

        for record in graph_records:
            path = graph.get_comparison_path(
                record.source_construct_id,
                record.target_construct_id
            )

            if path:
                vif = path.variance_inflation
                if vif == 0:
                    continue
                weight = 1.0 / (vif ** 2)

                # Check for existing
                existing = PrecisionWeight.query.filter_by(
                    comparison_graph_id=record.id,
                    analysis_version_id=analysis_version_id
                ).first()

                if existing:
                    existing.variance_inflation_factor = vif
                    existing.precision_weight = weight
                else:
                    pw = PrecisionWeight(
                        comparison_graph_id=record.id,
                        analysis_version_id=analysis_version_id,
                        variance_inflation_factor=vif,
                        precision_weight=weight
                    )
                    db.session.add(pw)

        db.session.commit()
