"""Tests for Smart Experiment Planner (Phase 2.5.8-2.5.17)."""
import pytest
from math import isclose

from app.calculator import (
    # Power analysis
    calculate_power_for_fold_change,
    calculate_sample_size_for_power,
    calculate_sample_size_for_precision,
    estimate_precision_improvement,
    calculate_precision_gap_score,
    calculate_untested_score,
    estimate_coplating_benefit,
    # Recommendation
    ConstructStats,
    RecommendationEngine,
    RecommendationConfidence,
    recommend_dfhbi_controls,
    check_template_limit,
    calculate_wells_needed,
    check_capacity,
    # Smart Planner
    SmartPlanner,
    PlannerMode,
    create_planner_for_project,
    PlateFormat,
    DEFAULT_PRECISION_TARGET,
    TARGET_EFFECT_PROBABILITY,
    MIN_REPLICATES,
    MAX_TEMPLATES_RECOMMENDED,
    MAX_TEMPLATES_ABSOLUTE,
)


class TestPowerAnalysis:
    """Tests for power analysis functions (F4.8)."""

    def test_power_increases_with_sample_size(self):
        """Test that power increases as n increases."""
        power_4 = calculate_power_for_fold_change(n=4, effect_size=0.5, sigma=0.5)
        power_8 = calculate_power_for_fold_change(n=8, effect_size=0.5, sigma=0.5)
        power_16 = calculate_power_for_fold_change(n=16, effect_size=0.5, sigma=0.5)

        assert power_4 < power_8 < power_16
        assert 0 < power_4 < 1
        assert 0 < power_16 < 1

    def test_power_increases_with_effect_size(self):
        """Test that power increases with larger effects."""
        power_small = calculate_power_for_fold_change(n=8, effect_size=0.2, sigma=0.5)
        power_large = calculate_power_for_fold_change(n=8, effect_size=1.0, sigma=0.5)

        assert power_small < power_large

    def test_sample_size_for_power_returns_valid(self):
        """Test sample size calculation returns reasonable values."""
        n = calculate_sample_size_for_power(
            effect_size=0.5,
            sigma=0.5,
            target_power=0.80,
        )

        assert n >= 2
        assert n <= 100

        # Verify the returned n achieves target power
        achieved_power = calculate_power_for_fold_change(n=n, effect_size=0.5, sigma=0.5)
        assert achieved_power >= 0.80

    def test_sample_size_for_precision_untested(self):
        """Test sample size for construct with no data."""
        result = calculate_sample_size_for_precision(
            current_ci_width=None,
            current_n=0,
            target_ci_width=0.3,
        )

        assert result.n_required == MIN_REPLICATES
        assert result.additional_needed == MIN_REPLICATES
        assert "Starting point" in result.description

    def test_sample_size_for_precision_at_target(self):
        """Test sample size when already at target."""
        result = calculate_sample_size_for_precision(
            current_ci_width=0.25,
            current_n=8,
            target_ci_width=0.3,
        )

        assert result.additional_needed == 0
        assert "achieved" in result.description.lower()

    def test_sample_size_for_precision_needs_more(self):
        """Test sample size when more replicates needed."""
        result = calculate_sample_size_for_precision(
            current_ci_width=0.6,  # Double the target
            current_n=4,
            target_ci_width=0.3,
        )

        assert result.additional_needed > 0
        assert result.n_required > result.current_n

    def test_estimate_precision_improvement(self):
        """Test CI width improvement estimation."""
        current_ci = 0.6
        current_n = 4
        additional = 4

        new_ci = estimate_precision_improvement(current_ci, current_n, additional)

        # CI should decrease when adding replicates
        assert new_ci < current_ci
        # CI scales as 1/sqrt(n), so with doubled n, CI should be ~0.71x
        expected = current_ci * (current_n / (current_n + additional)) ** 0.5
        assert isclose(new_ci, expected, rel_tol=0.01)


class TestRecommendationScoring:
    """Tests for recommendation scoring (F4.1)."""

    def test_precision_gap_score_no_data(self):
        """Test precision gap when no data available."""
        score = calculate_precision_gap_score(None, 0.3)
        assert score == 50.0  # Moderate default

    def test_precision_gap_score_at_target(self):
        """Test precision gap when at target."""
        score = calculate_precision_gap_score(0.25, 0.3)
        assert score == 0.0

    def test_precision_gap_score_above_target(self):
        """Test precision gap when above target."""
        # 100% gap (0.6 vs 0.3)
        score = calculate_precision_gap_score(0.6, 0.3)
        assert score == 100.0

        # 50% gap
        score = calculate_precision_gap_score(0.45, 0.3)
        assert isclose(score, 50.0, rel_tol=0.01)

    def test_untested_score_no_data(self):
        """Test untested score for construct without data."""
        score = calculate_untested_score(has_data=False)
        assert score == 100.0

    def test_untested_score_has_data(self):
        """Test untested score for construct with data."""
        score = calculate_untested_score(has_data=True)
        assert score == 0.0

    def test_coplating_benefit_same_family(self):
        """Test co-plating benefit for same family."""
        score = estimate_coplating_benefit(
            constructs_on_plate=[{'family': 'F1'}],
            new_construct_family='F1',
            families_on_plate={'F1'},
        )
        assert score > 50  # Should get high score

    def test_coplating_benefit_new_family(self):
        """Test co-plating benefit for new family."""
        score = estimate_coplating_benefit(
            constructs_on_plate=[{'family': 'F1'}],
            new_construct_family='F2',
            families_on_plate={'F1'},
        )
        assert score < 50  # Lower score for new family

    def test_recommendation_weights(self):
        """Test that weights sum to 1.0 (50/30/20)."""
        from app.calculator.recommendation import (
            WEIGHT_PRECISION_GAP,
            WEIGHT_UNTESTED,
            WEIGHT_COPLATING,
        )

        total = WEIGHT_PRECISION_GAP + WEIGHT_UNTESTED + WEIGHT_COPLATING
        assert isclose(total, 1.0, rel_tol=0.01)


class TestRecommendationEngine:
    """Tests for recommendation engine (F4.1)."""

    @pytest.fixture
    def sample_constructs(self):
        """Create sample constructs for testing."""
        return [
            ConstructStats(
                construct_id=1,
                name='Reporter-only',
                family=None,
                is_wildtype=False,
                is_unregulated=True,
                replicate_count=8,
                ci_width=0.2,
                has_data=True,
            ),
            ConstructStats(
                construct_id=2,
                name='Tbox1_WT',
                family='Tbox1',
                is_wildtype=True,
                is_unregulated=False,
                replicate_count=4,
                ci_width=0.4,
                has_data=True,
            ),
            ConstructStats(
                construct_id=3,
                name='Tbox1_M1',
                family='Tbox1',
                is_wildtype=False,
                is_unregulated=False,
                replicate_count=4,
                ci_width=0.5,
                has_data=True,
            ),
            ConstructStats(
                construct_id=4,
                name='Tbox1_M2',
                family='Tbox1',
                is_wildtype=False,
                is_unregulated=False,
                replicate_count=0,
                ci_width=None,
                has_data=False,
            ),
        ]

    def test_score_construct(self, sample_constructs):
        """Test scoring a single construct."""
        engine = RecommendationEngine()
        construct = sample_constructs[2]  # M1 with data

        rec = engine.score_construct(construct, set())

        assert rec.construct_id == 3
        assert rec.total_score >= 0
        assert rec.precision_gap_score >= 0
        assert rec.untested_score == 0  # Has data
        assert rec.coplating_score >= 0

    def test_untested_construct_ranks_high(self, sample_constructs):
        """Test that untested constructs rank higher (F4.1)."""
        engine = RecommendationEngine()

        recommendations = engine.rank_constructs(sample_constructs)

        # Find M2 (untested)
        m2_rec = next(r for r in recommendations if r.name == 'Tbox1_M2')

        # M2 should have high score due to untested bonus
        assert m2_rec.untested_score == 100.0
        # WT sorts first (required), then M2 should be highest-scored non-WT
        non_wt = [r for r in recommendations if not r.is_wildtype]
        assert non_wt[0].name == 'Tbox1_M2'

    def test_get_required_anchors(self, sample_constructs):
        """Test auto-adding anchor constructs (F4.2)."""
        engine = RecommendationEngine()

        # Select just M1
        selected = [sample_constructs[2]]  # M1

        anchors = engine.get_required_anchors(selected, sample_constructs)

        # Should add Reporter-only
        anchor_names = [a.name for a in anchors]
        assert 'Reporter-only' in anchor_names

    def test_anchors_not_duplicated(self, sample_constructs):
        """Test anchors aren't added if already selected."""
        engine = RecommendationEngine()

        # Select Reporter-only and M1
        selected = [sample_constructs[0], sample_constructs[2]]

        anchors = engine.get_required_anchors(selected, sample_constructs)

        # Should NOT add Reporter-only again
        anchor_names = [a.name for a in anchors]
        assert 'Reporter-only' not in anchor_names


class TestDFHBIRecommendation:
    """Tests for -DFHBI recommendation logic (F4.5)."""

    def test_recommend_no_recent_controls(self):
        """Test recommendation when no recent controls."""
        rec = recommend_dfhbi_controls(
            recent_controls=[],
            typical_fmax=10000,
        )

        assert rec.include is True
        assert rec.confidence == RecommendationConfidence.REQUIRED
        assert "14 days" in rec.reason

    def test_recommend_stable_background(self):
        """Test recommendation with stable low background."""
        controls = [
            {'signal': 50},
            {'signal': 45},
            {'signal': 55},
        ]

        rec = recommend_dfhbi_controls(
            recent_controls=controls,
            typical_fmax=10000,  # 5% = 500 RFU threshold
        )

        # Mean ~50, well below 500 threshold
        assert rec.include is False
        assert rec.confidence == RecommendationConfidence.OPTIONAL
        assert "stable" in rec.reason.lower()

    def test_recommend_high_background(self):
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


class TestTemplateLimits:
    """Tests for template limit enforcement (F4.3)."""

    def test_template_limit_ok(self):
        """Test that 3-4 templates are OK."""
        exceeded, warning = check_template_limit(3)
        assert exceeded is False
        assert warning is None

        exceeded, warning = check_template_limit(4)
        assert exceeded is False
        assert warning is None

    def test_template_limit_warning(self):
        """Test warning for 5 templates."""
        exceeded, warning = check_template_limit(5)
        assert exceeded is False
        assert warning is not None
        assert "exceeds recommended" in warning.lower()

    def test_template_limit_error(self):
        """Test error for >6 templates."""
        exceeded, warning = check_template_limit(7)
        assert exceeded is True
        assert "exceeds maximum" in warning.lower()


class TestCapacityManagement:
    """Tests for capacity management (F4.9)."""

    def test_capacity_96_well_ok(self):
        """Test 96-well plate capacity OK."""
        exceeded, plates, warning = check_capacity(50, "96")
        assert exceeded is False
        assert plates == 1
        assert warning is None

    def test_capacity_96_well_exceeded(self):
        """Test 96-well plate capacity exceeded."""
        exceeded, plates, warning = check_capacity(120, "96")
        assert exceeded is True
        assert plates == 2
        assert warning is not None

    def test_capacity_384_well_checkerboard(self):
        """Test 384-well checkerboard capacity (192 usable)."""
        exceeded, plates, warning = check_capacity(100, "384", is_checkerboard=True)
        assert exceeded is False
        assert plates == 1

        exceeded, plates, warning = check_capacity(200, "384", is_checkerboard=True)
        assert exceeded is True
        assert plates == 2

    def test_wells_needed_calculation(self):
        """Test total wells calculation."""
        from app.calculator.recommendation import ConstructRecommendation

        constructs = [
            ConstructRecommendation(
                construct_id=1, name='C1', family='F1', is_wildtype=False,
                is_unregulated=False,
                is_anchor=False, total_score=50, precision_gap_score=0,
                untested_score=0, coplating_score=0, brief_reason='',
                detailed_reason='', current_ci_width=None, target_ci_width=0.3,
                replicates_needed=0, plates_estimate=0,
            )
            for _ in range(4)
        ]

        wells = calculate_wells_needed(
            constructs=constructs,
            replicates=4,
            negative_template_count=3,
            negative_dye_count=2,
        )

        # 4 constructs × 4 reps + 3 + 2 = 21 wells
        assert wells == 21


class TestSmartPlanner:
    """Tests for SmartPlanner class."""

    @pytest.fixture
    def sample_constructs(self):
        """Create sample constructs."""
        return [
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
            ConstructStats(
                construct_id=3, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]

    def test_detect_first_experiment_mode(self, sample_constructs):
        """Test first experiment detection (F4.7)."""
        planner = SmartPlanner()

        mode = planner.detect_mode(sample_constructs)
        assert mode == PlannerMode.FIRST_EXPERIMENT

    def test_detect_normal_mode(self, sample_constructs):
        """Test normal mode detection when data exists."""
        planner = SmartPlanner()

        # Add some data
        sample_constructs[0].has_data = True
        sample_constructs[0].replicate_count = 4

        mode = planner.detect_mode(sample_constructs)
        assert mode == PlannerMode.NORMAL

    def test_first_experiment_suggestion(self, sample_constructs):
        """Test first experiment wizard suggestion (F4.7)."""
        planner = SmartPlanner()

        suggestion = planner.generate_first_experiment_suggestion(sample_constructs)

        assert suggestion.reporter_only is not None
        assert suggestion.reporter_only.name == 'Reporter'
        assert suggestion.wildtype is not None
        assert suggestion.wildtype.name == 'WT'
        assert suggestion.negative_template_count >= 2
        assert len(suggestion.rationale) > 0

    def test_create_experiment_plan(self, sample_constructs):
        """Test creating experiment plan."""
        planner = SmartPlanner()

        # Select M1
        selected = [sample_constructs[2]]

        plan = planner.create_experiment_plan(
            selected_constructs=selected,
            all_constructs=sample_constructs,
        )

        # Should auto-add anchors
        assert len(plan.auto_added_anchors) >= 1
        assert plan.negative_template_count >= 2
        assert plan.total_wells > 0

    def test_validate_plan_missing_unregulated(self, sample_constructs):
        """Test validation catches missing reporter-only."""
        planner = SmartPlanner()

        # Select only M1, but remove Reporter from all_constructs
        selected = [sample_constructs[2]]
        constructs_no_reporter = [c for c in sample_constructs if not c.is_unregulated]

        plan = planner.create_experiment_plan(
            selected_constructs=selected,
            all_constructs=constructs_no_reporter,
        )

        validation = planner.validate_plan(plan)

        assert validation.is_valid is False
        assert any('reporter' in e.lower() for e in validation.errors)

    def test_validate_plan_missing_wt(self):
        """Test validation catches missing WT for family."""
        planner = SmartPlanner()

        constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=2, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            # No WT for F1!
        ]

        selected = [constructs[1]]  # M1

        plan = planner.create_experiment_plan(
            selected_constructs=selected,
            all_constructs=constructs,
        )

        validation = planner.validate_plan(plan)

        # Should flag missing WT
        assert any('wild-type' in e.lower() or 'wt' in e.lower() for e in validation.errors)

    def test_impact_preview(self, sample_constructs):
        """Test impact preview calculation (F4.6)."""
        planner = SmartPlanner()

        # Add some existing data
        sample_constructs[0].has_data = True
        sample_constructs[0].replicate_count = 4
        sample_constructs[0].ci_width = 0.4

        selected = [sample_constructs[2]]  # M1 (untested)

        preview = planner.calculate_impact_preview(
            selected_constructs=selected,
            all_constructs=sample_constructs,
        )

        assert preview.constructs_before == 1  # Only Reporter has data
        assert preview.constructs_gained == 1  # M1 is new
        assert preview.constructs_after == 2

    def test_create_planner_for_project(self):
        """Test factory function."""
        planner_96 = create_planner_for_project("96")
        assert planner_96.plate_format == PlateFormat.WELL_96

        planner_384 = create_planner_for_project("384")
        assert planner_384.plate_format == PlateFormat.WELL_384


class TestReplicateRecommendations:
    """Tests for replicate recommendations (F4.8)."""

    def test_minimum_replicates_enforced(self):
        """Test that minimum 4 replicates are enforced."""
        result = calculate_sample_size_for_precision(
            current_ci_width=None,
            current_n=0,
            target_ci_width=0.3,
        )

        assert result.n_required >= MIN_REPLICATES

    def test_replicate_recommendation_for_precision(self):
        """Test replicate recommendation based on precision."""
        # With large precision gap, should recommend more
        result = calculate_sample_size_for_precision(
            current_ci_width=0.6,
            current_n=4,
            target_ci_width=0.3,
        )

        assert result.additional_needed > 0
        assert result.n_required > MIN_REPLICATES


class TestRawNeedScoring:
    """Tests for the share-of-remaining-gap scoring system."""

    def test_raw_need_untested(self):
        """Untested constructs get raw_need = 100."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='Untested', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=0, ci_width=None, has_data=False,
        )
        assert engine._compute_raw_need(construct) == 100.0

    def test_raw_need_both_targets_met(self):
        """Construct meeting both CI and prob_meaningful targets has raw_need = 0."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='Good', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=16, ci_width=0.2, has_data=True,
            prob_meaningful=0.99,
        )
        assert engine._compute_raw_need(construct) == 0.0

    def test_raw_need_low_prob_meaningful(self):
        """Low prob_meaningful contributes to raw_need even if CI is at target."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='LowProb', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=16, ci_width=0.2, has_data=True,
            prob_meaningful=0.50,  # 50% — well below 95% target
        )
        raw = engine._compute_raw_need(construct)
        # CI is at target (0.2 <= 0.3), so precision_gap = 0
        # effect_gap = (1 - 0.50/0.95) * 50 ≈ 23.7
        assert raw > 20
        assert raw < 30

    def test_raw_need_precision_gap_only(self):
        """High CI with prob_meaningful at target contributes precision gap."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='WideCi', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=4, ci_width=0.6, has_data=True,
            prob_meaningful=0.98,  # Above 95% target
        )
        raw = engine._compute_raw_need(construct)
        # precision_gap: (0.6-0.3)/0.3 * 50 = 50.0 (capped at 50)
        # effect_gap: 0 (prob above target)
        assert isclose(raw, 50.0, rel_tol=0.01)

    def test_raw_need_no_analysis_moderate_penalty(self):
        """Has data but no Bayesian analysis gets moderate effect_gap penalty."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='NoAnalysis', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=4, ci_width=0.25, has_data=True,
            prob_meaningful=None,  # No Bayesian analysis yet
        )
        raw = engine._compute_raw_need(construct)
        # CI at target (0.25 <= 0.3), so precision_gap = 0
        # No prob_meaningful but has data+CI → effect_gap = 25
        assert isclose(raw, 25.0, rel_tol=0.01)

    def test_normalization_sums_to_100(self):
        """rank_constructs normalizes scores to sum to ~100%."""
        engine = RecommendationEngine()
        constructs = [
            ConstructStats(
                construct_id=1, name='A', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=2, name='B', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=4, ci_width=0.5, has_data=True,
                prob_meaningful=0.80,
            ),
            ConstructStats(
                construct_id=3, name='C', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=16, ci_width=0.2, has_data=True,
                prob_meaningful=0.99,
            ),
        ]
        recs = engine.rank_constructs(constructs)
        total = sum(r.total_score for r in recs)
        assert isclose(total, 100.0, rel_tol=0.01)

    def test_normalization_all_zero_raw_need(self):
        """When all raw needs are 0, scores stay at 0."""
        engine = RecommendationEngine()
        constructs = [
            ConstructStats(
                construct_id=1, name='Done', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=16, ci_width=0.2, has_data=True,
                prob_meaningful=0.99,
            ),
        ]
        recs = engine.rank_constructs(constructs)
        assert len(recs) == 1
        assert recs[0].total_score == 0.0

    def test_wt_excluded_from_normalization(self):
        """WT constructs get score=0 and don't eat into the 100% budget."""
        engine = RecommendationEngine()
        constructs = [
            ConstructStats(
                construct_id=1, name='WT', family='F1',
                is_wildtype=True, is_unregulated=False,
                replicate_count=4, ci_width=0.4, has_data=True,
            ),
            ConstructStats(
                construct_id=2, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=3, name='M2', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=4, ci_width=0.5, has_data=True,
                prob_meaningful=0.80,
            ),
        ]
        recs = engine.rank_constructs(constructs)
        wt_rec = next(r for r in recs if r.name == 'WT')
        non_wt = [r for r in recs if not r.is_wildtype]

        # WT gets score 0 and "Required" label
        assert wt_rec.total_score == 0.0
        assert "Required" in wt_rec.brief_reason

        # Non-WT scores still sum to ~100%
        total_non_wt = sum(r.total_score for r in non_wt)
        assert isclose(total_non_wt, 100.0, rel_tol=0.01)

        # WT sorts first
        assert recs[0].is_wildtype


class TestClassification:
    """Tests for construct classification."""

    def test_classify_untested(self):
        """Untested construct classified as 'Untested construct'."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='New', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=0, ci_width=None, has_data=False,
        )
        rec = engine.score_construct(construct, set())
        assert rec.brief_reason == "Untested construct"

    def test_classify_low_prob_meaningful(self):
        """Low prob_meaningful → NOT 'Maintenance testing'."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='LowP', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=8, ci_width=0.25, has_data=True,
            prob_meaningful=0.60,
        )
        rec = engine.score_construct(construct, set())
        assert "Effect not yet established" in rec.brief_reason
        assert "60%" in rec.brief_reason
        assert rec.brief_reason != "Maintenance testing"

    def test_classify_precision_gap(self):
        """High CI with good prob → classified as precision gap."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='WideCI', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=4, ci_width=0.6, has_data=True,
            prob_meaningful=0.98,
        )
        rec = engine.score_construct(construct, set())
        assert "precision gap" in rec.brief_reason

    def test_classify_maintenance(self):
        """Construct meeting both targets → 'Maintenance testing'."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='Done', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=16, ci_width=0.2, has_data=True,
            prob_meaningful=0.99,
        )
        rec = engine.score_construct(construct, set())
        assert rec.brief_reason == "Maintenance testing"

    def test_prob_meaningful_in_recommendation(self):
        """prob_meaningful is passed through to the recommendation."""
        engine = RecommendationEngine()
        construct = ConstructStats(
            construct_id=1, name='Test', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=8, ci_width=0.25, has_data=True,
            prob_meaningful=0.85,
        )
        rec = engine.score_construct(construct, set())
        assert rec.prob_meaningful == 0.85


class TestPlatesEstimation:
    """Tests for the _estimate_plates_to_target helper."""

    def test_untested_needs_one_plate(self):
        """Untested non-anchor constructs need at least 1 plate."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='Reporter', family=None,
                is_wildtype=False, is_unregulated=True,
                replicate_count=0, ci_width=None, has_data=False,
            ),
            ConstructStats(
                construct_id=2, name='M1', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=0, ci_width=None, has_data=False,
            ),
        ]
        plates = planner._estimate_plates_to_target(constructs)
        # Reporter is unregulated (skipped), M1 is untested → 1 plate
        assert plates == 1

    def test_at_target_needs_zero(self):
        """Construct meeting all targets needs 0 additional plates."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='Done', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=16, ci_width=0.2, has_data=True,
                prob_meaningful=0.99,
            ),
        ]
        plates = planner._estimate_plates_to_target(constructs)
        assert plates == 0

    def test_low_prob_needs_plate(self):
        """Construct with low prob_meaningful needs at least 1 plate."""
        planner = SmartPlanner()
        constructs = [
            ConstructStats(
                construct_id=1, name='LowP', family='F1',
                is_wildtype=False, is_unregulated=False,
                replicate_count=8, ci_width=0.2, has_data=True,
                prob_meaningful=0.60,
            ),
        ]
        plates = planner._estimate_plates_to_target(constructs)
        assert plates >= 1

    def test_selected_reduces_plates(self):
        """Selecting a construct for testing should reduce plates-to-target."""
        planner = SmartPlanner()
        untested = ConstructStats(
            construct_id=2, name='M1', family='F1',
            is_wildtype=False, is_unregulated=False,
            replicate_count=0, ci_width=None, has_data=False,
        )
        constructs = [untested]

        plates_before = planner._estimate_plates_to_target(constructs)
        plates_after = planner._estimate_plates_to_target(
            constructs, selected_set={2}, additional_replicates=4,
        )
        # Before: untested → 1 plate. After: now has data but no CI → 1 plate (pending analysis)
        # But the projected state changes, showing progress
        assert plates_before >= 1
        assert plates_after <= plates_before
