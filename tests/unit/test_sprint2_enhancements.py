"""Tests for Sprint 2 enhancements (F4.1, F4.5, F4.7, F4.8).

Tests the new callbacks and functionality added for:
- First Experiment Wizard (F4.7)
- Recommendation Engine Polish (F4.1)
- Impact Preview Card (F4.6)
- DFHBI Recommendations (F4.5)
- Replicate Recommendations (F4.8)
"""
import pytest
from unittest.mock import patch, MagicMock
from math import isclose

from app.calculator import (
    ConstructStats,
    RecommendationEngine,
    recommend_dfhbi_controls,
    RecommendationConfidence,
    SmartPlanner,
    PlannerMode,
    calculate_sample_size_for_precision,
    DEFAULT_PRECISION_TARGET,
)


class TestFirstExperimentWizard:
    """Tests for First Experiment Wizard (F4.7)."""

    def test_wizard_detects_new_project(self):
        """Test wizard triggers for projects with no data."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=2, name='WT', family='F1',
                is_wildtype=True, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        mode = planner.detect_mode(constructs)
        assert mode == PlannerMode.FIRST_EXPERIMENT

    def test_wizard_generates_wt_first_suggestion(self):
        """Test wizard suggests WT characterization first."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=2, name='Tbox1_WT', family='Tbox1',
                is_wildtype=True, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=3, name='Tbox1_M1', family='Tbox1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        suggestion = planner.generate_first_experiment_suggestion(constructs)

        # Should include reporter-only and WT
        assert suggestion.reporter_only is not None
        assert suggestion.wildtype is not None
        assert suggestion.wildtype.name == 'Tbox1_WT'

        # Should include negative controls
        assert suggestion.negative_template_count >= 2
        assert suggestion.negative_dye_count >= 2

        # Should have rationale for WT-first strategy
        assert len(suggestion.rationale) >= 1
        assert any('baseline' in r.lower() for r in suggestion.rationale)

    def test_wizard_skips_for_existing_data(self):
        """Test wizard doesn't trigger when data exists."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=4, ci_width=0.3, has_data=True,  # Has data
            ),
            ConstructStats(
                construct_id=2, name='WT', family='F1',
                is_wildtype=True, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        mode = planner.detect_mode(constructs)
        assert mode == PlannerMode.NORMAL


class TestRecommendationEnginePolish:
    """Tests for Recommendation Engine Polish (F4.1)."""

    def test_scoring_weights_sum_to_one(self):
        """Verify scoring weights (50/30/20) sum to 1.0."""
        from app.calculator.recommendation import (
            WEIGHT_PRECISION_GAP,
            WEIGHT_UNTESTED,
            WEIGHT_COPLATING,
        )

        total = WEIGHT_PRECISION_GAP + WEIGHT_UNTESTED + WEIGHT_COPLATING
        assert isclose(total, 1.0)

    def test_precision_weight_is_fifty_percent(self):
        """Verify precision gap has 50% weight."""
        from app.calculator.recommendation import WEIGHT_PRECISION_GAP
        assert WEIGHT_PRECISION_GAP == 0.50

    def test_untested_weight_is_thirty_percent(self):
        """Verify untested status has 30% weight."""
        from app.calculator.recommendation import WEIGHT_UNTESTED
        assert WEIGHT_UNTESTED == 0.30

    def test_coplating_weight_is_twenty_percent(self):
        """Verify co-plating benefit has 20% weight."""
        from app.calculator.recommendation import WEIGHT_COPLATING
        assert WEIGHT_COPLATING == 0.20

    def test_recommendation_includes_detailed_reason(self):
        """Test recommendations include detailed explanation."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='M1', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=4, ci_width=0.5, has_data=True,
        )

        rec = engine.score_construct(construct, set())

        assert rec.brief_reason != ""
        assert rec.detailed_reason != ""
        assert len(rec.detailed_reason) > len(rec.brief_reason)

    def test_recommendation_includes_ci_projections(self):
        """Test recommendations include CI projections."""
        engine = RecommendationEngine(target_ci_width=0.3)
        construct = ConstructStats(
            construct_id=1, name='M1', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=4, ci_width=0.5, has_data=True,
        )

        rec = engine.score_construct(construct, set())

        assert rec.current_ci_width == 0.5
        assert rec.target_ci_width == 0.3
        assert rec.replicates_needed >= 0

    def test_untested_constructs_rank_highly(self):
        """Test untested constructs get high scores."""
        engine = RecommendationEngine()
        constructs = [
            ConstructStats(
                construct_id=1, name='Tested', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=4, ci_width=0.3, has_data=True,
            ),
            ConstructStats(
                construct_id=2, name='Untested', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        recommendations = engine.rank_constructs(constructs)

        # Untested should rank first
        assert recommendations[0].name == 'Untested'
        assert recommendations[0].untested_score == 100.0


class TestImpactPreviewCard:
    """Tests for Impact Preview Card (F4.6)."""

    def test_impact_preview_shows_constructs_covered(self):
        """Test impact preview shows constructs covered."""
        planner = SmartPlanner()
        all_constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=4, ci_width=0.3, has_data=True,
            ),
            ConstructStats(
                construct_id=2, name='WT', family='F1',
                is_wildtype=True, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=3, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        selected = [all_constructs[2]]  # Select M1

        impact = planner.calculate_impact_preview(selected, all_constructs)

        assert impact.constructs_before == 1  # Reporter has data
        assert impact.constructs_gained == 1  # M1 is new
        assert impact.constructs_after == 2

    def test_impact_preview_shows_precision_improvement(self):
        """Test impact preview shows precision improvement."""
        planner = SmartPlanner()
        all_constructs = [
            ConstructStats(
                construct_id=1, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=4, ci_width=0.5, has_data=True,
            ),
        ]

        selected = [all_constructs[0]]

        impact = planner.calculate_impact_preview(selected, all_constructs, additional_replicates=4)

        # Should show some improvement
        assert len(impact.per_construct_impact) == 1
        assert impact.per_construct_impact[0]['current_ci'] == 0.5
        assert impact.per_construct_impact[0]['projected_ci'] < 0.5

    def test_impact_preview_shows_per_construct_details(self):
        """Test impact preview includes per-construct breakdown."""
        planner = SmartPlanner()
        all_constructs = [
            ConstructStats(
                construct_id=1, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=4, ci_width=0.5, has_data=True,
            ),
            ConstructStats(
                construct_id=2, name='M2', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

        impact = planner.calculate_impact_preview(all_constructs, all_constructs)

        # Should have details for both constructs
        assert len(impact.per_construct_impact) == 2
        names = [c['name'] for c in impact.per_construct_impact]
        assert 'M1' in names
        assert 'M2' in names


class TestDFHBIRecommendations:
    """Tests for -DFHBI Recommendations (F4.5)."""

    def test_recommend_dfhbi_when_no_recent_controls(self):
        """Test recommendation when no recent controls found."""
        rec = recommend_dfhbi_controls(
            recent_controls=[],
            typical_fmax=10000,
        )

        assert rec.include is True
        assert rec.confidence == RecommendationConfidence.REQUIRED
        assert "14 days" in rec.reason

    def test_recommend_optional_when_stable_low_background(self):
        """Test optional recommendation when background is stable and low."""
        controls = [
            {'signal': 50},
            {'signal': 45},
            {'signal': 55},
        ]

        rec = recommend_dfhbi_controls(
            recent_controls=controls,
            typical_fmax=10000,  # 5% threshold = 500
        )

        # Mean ~50, well below threshold
        assert rec.include is False
        assert rec.confidence == RecommendationConfidence.OPTIONAL
        assert rec.recent_mean_signal is not None
        assert rec.recent_control_count == 3

    def test_recommend_dfhbi_when_background_high(self):
        """Test recommendation when background exceeds 5% threshold."""
        controls = [
            {'signal': 600},  # Above 5% of 10000
            {'signal': 550},
        ]

        rec = recommend_dfhbi_controls(
            recent_controls=controls,
            typical_fmax=10000,
        )

        assert rec.include is True
        assert rec.confidence == RecommendationConfidence.RECOMMENDED
        assert "exceeding" in rec.reason.lower()


class TestReplicateRecommendations:
    """Tests for replicate recommendations (F4.8)."""

    def test_minimum_four_replicates_enforced(self):
        """Test that minimum 4 replicates are required."""
        result = calculate_sample_size_for_precision(
            current_ci_width=None,
            current_n=0,
            target_ci_width=0.3,
        )

        assert result.n_required >= 4

    def test_more_replicates_for_poor_precision(self):
        """Test recommendation for more replicates with poor precision."""
        result = calculate_sample_size_for_precision(
            current_ci_width=0.6,  # Poor precision
            current_n=4,
            target_ci_width=0.3,
        )

        assert result.additional_needed > 0
        assert "more" in result.description.lower()

    def test_no_additional_replicates_at_target(self):
        """Test no additional replicates when at target."""
        result = calculate_sample_size_for_precision(
            current_ci_width=0.25,  # Below target
            current_n=8,
            target_ci_width=0.3,
        )

        assert result.additional_needed == 0
        assert "achieved" in result.description.lower()
