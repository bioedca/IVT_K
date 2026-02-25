"""Tests for SmartPlannerService.

Phase 2.5: Constraints & Linking (F4.18-F4.23) tests.
"""
import pytest
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

from app.services import SmartPlannerService, SmartPlannerError
from app.calculator import (
    PlannerMode,
    ConstructStats,
    DEFAULT_PRECISION_TARGET,
)


class TestProjectConstraintValidation:
    """Tests for F4.19: Enforce project-level reporter-only."""

    def test_validate_project_not_found(self, db_session):
        """Test validation with non-existent project."""
        result = SmartPlannerService.validate_project_constraints(99999)
        assert not result.is_valid
        assert any('not found' in e for e in result.errors)

    def test_validate_missing_reporter_only(self, db_session, test_project):
        """Test validation fails without reporter-only construct."""
        from app.models import Construct
        from app.extensions import db

        # Create project without reporter-only
        project = test_project()

        # Add a regular construct
        construct = Construct(
            project_id=project.id,
            identifier="Test_WT",
            family="TestFamily",
            is_wildtype=True,
        )
        db.session.add(construct)
        db.session.commit()

        result = SmartPlannerService.validate_project_constraints(project.id)
        assert not result.is_valid
        assert not result.has_reporter_only
        assert any('reporter-only' in e.lower() for e in result.errors)

    def test_validate_with_reporter_only(self, db_session, test_project):
        """Test validation passes with reporter-only construct."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add reporter-only construct
        construct = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        db.session.add(construct)
        db.session.commit()

        result = SmartPlannerService.validate_project_constraints(project.id)
        assert result.has_reporter_only
        assert len(result.errors) == 0

    def test_validate_missing_wt_for_family(self, db_session, test_project):
        """Test warning when family has mutants but no WT."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add reporter-only
        reporter = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        # Add mutant without WT
        mutant = Construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            is_wildtype=False,
        )
        db.session.add_all([reporter, mutant])
        db.session.commit()

        result = SmartPlannerService.validate_project_constraints(project.id)
        assert result.is_valid  # Missing WT is warning, not error
        assert "Tbox1" in result.has_wildtype_per_family
        assert not result.has_wildtype_per_family["Tbox1"]
        assert any('Tbox1' in w for w in result.warnings)


class TestGetConstructStats:
    """Tests for F4.22: Recommendations from uploaded data only."""

    def test_get_stats_empty_project(self, db_session, test_project):
        """Test getting stats for project with no constructs."""
        project = test_project()
        stats = SmartPlannerService.get_construct_stats(project.id)
        assert stats == []

    def test_get_stats_with_constructs(self, db_session, test_project):
        """Test getting stats for project with constructs."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        constructs = [
            Construct(
                project_id=project.id,
                identifier="Reporter-only",
                family="control",
                is_unregulated=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_WT",
                family="Tbox1",
                is_wildtype=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_M1",
                family="Tbox1",
            ),
        ]
        db.session.add_all(constructs)
        db.session.commit()

        stats = SmartPlannerService.get_construct_stats(project.id)
        assert len(stats) == 3

        # Check stats types
        assert all(isinstance(s, ConstructStats) for s in stats)

        # Check unregulated
        unreg = next(s for s in stats if s.is_unregulated)
        assert unreg.name == "Reporter-only"

        # Check WT
        wt = next(s for s in stats if s.is_wildtype)
        assert wt.name == "Tbox1_WT"
        assert wt.family == "Tbox1"

    def test_get_stats_excludes_deleted(self, db_session, test_project):
        """Test that deleted constructs are excluded."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        active = Construct(
            project_id=project.id,
            identifier="Active",
            family="TestFamily",
        )
        deleted = Construct(
            project_id=project.id,
            identifier="Deleted",
            family="TestFamily",
            is_deleted=True,
        )
        db.session.add_all([active, deleted])
        db.session.commit()

        stats = SmartPlannerService.get_construct_stats(project.id)
        assert len(stats) == 1
        assert stats[0].name == "Active"


class TestDetectPlannerMode:
    """Tests for planner mode detection."""

    def test_first_experiment_mode(self, db_session, test_project):
        """Test first experiment mode for new project."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs but no data
        construct = Construct(
            project_id=project.id,
            identifier="Test",
            family="TestFamily",
        )
        db.session.add(construct)
        db.session.commit()

        mode = SmartPlannerService.detect_planner_mode(project.id)
        assert mode == PlannerMode.FIRST_EXPERIMENT


class TestFirstExperimentSuggestion:
    """Tests for First Experiment Wizard."""

    def test_first_experiment_suggestion(self, db_session, test_project):
        """Test first experiment suggestion generation."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add required constructs
        reporter = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        wt = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
        )
        db.session.add_all([reporter, wt])
        db.session.commit()

        suggestion = SmartPlannerService.get_first_experiment_suggestion(
            project.id, replicates=4
        )

        assert suggestion.reporter_only is not None
        assert suggestion.reporter_only.name == "Reporter-only"
        assert suggestion.wildtype is not None
        assert suggestion.wildtype.name == "Tbox1_WT"
        assert suggestion.replicates_per_construct == 4
        assert suggestion.total_wells > 0
        assert len(suggestion.rationale) > 0

    def test_first_experiment_no_reporter(self, db_session, test_project):
        """Test first experiment without reporter-only construct."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Only add WT, no reporter
        wt = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
        )
        db.session.add(wt)
        db.session.commit()

        suggestion = SmartPlannerService.get_first_experiment_suggestion(
            project.id, replicates=4
        )

        assert suggestion.reporter_only is None
        assert suggestion.wildtype is not None


class TestGetRecommendations:
    """Tests for recommendation generation."""

    def test_get_recommendations_empty(self, db_session, test_project):
        """Test recommendations for empty project."""
        project = test_project()
        recs = SmartPlannerService.get_recommendations(project.id)
        assert recs == []

    def test_get_recommendations_with_constructs(self, db_session, test_project):
        """Test recommendations with constructs."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        constructs = [
            Construct(
                project_id=project.id,
                identifier="Reporter-only",
                family="control",
                is_unregulated=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_WT",
                family="Tbox1",
                is_wildtype=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_M1",
                family="Tbox1",
            ),
        ]
        db.session.add_all(constructs)
        db.session.commit()

        recs = SmartPlannerService.get_recommendations(
            project.id, max_recommendations=10, uploaded_only=False
        )

        # Should have recommendations (excluding unregulated anchor)
        assert len(recs) >= 1


class TestCreateExperimentPlan:
    """Tests for experiment plan creation."""

    def test_create_plan_without_reporter(self, db_session, test_project):
        """Test plan creation fails without reporter-only."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add construct without reporter-only
        construct = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
        )
        db.session.add(construct)
        db.session.commit()

        with pytest.raises(SmartPlannerError) as exc:
            SmartPlannerService.create_experiment_plan(
                project.id,
                selected_construct_ids=[construct.id],
            )
        assert 'reporter-only' in str(exc.value).lower()

    def test_create_plan_with_valid_constructs(self, db_session, test_project):
        """Test successful plan creation."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add required constructs
        reporter = Construct(
            project_id=project.id,
            identifier="Reporter-only",
            family="control",
            is_unregulated=True,
        )
        wt = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
        )
        mutant = Construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
        )
        db.session.add_all([reporter, wt, mutant])
        db.session.commit()

        plan = SmartPlannerService.create_experiment_plan(
            project.id,
            selected_construct_ids=[mutant.id],
            replicates=4,
        )

        # Should have the mutant in constructs
        assert len(plan.constructs) == 1
        assert plan.constructs[0].name == "Tbox1_M1"

        # Should auto-add anchors (reporter + WT)
        assert len(plan.auto_added_anchors) >= 1

        # Verify total wells calculated
        assert plan.total_wells > 0


class TestLinkSetupToSession:
    """Tests for F4.21: Link to ExperimentalSession (mandatory)."""

    def test_link_setup_to_session(self, db_session, test_project):
        """Test successful setup-session linking."""
        from app.models import ReactionSetup, ExperimentalSession
        from app.extensions import db

        project = test_project()

        # Create setup
        setup = ReactionSetup(
            project_id=project.id,
            name="Test Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
        )
        db.session.add(setup)
        db.session.flush()

        # Create session
        session = ExperimentalSession(
            project_id=project.id,
            date=date.today(),
            batch_identifier="Test Session",
        )
        db.session.add(session)
        db.session.commit()

        # Link them
        result = SmartPlannerService.link_setup_to_session(setup.id, session.id)

        assert result.session_id == session.id

    def test_link_setup_not_found(self, db_session, test_project):
        """Test linking with non-existent setup."""
        from app.models import ExperimentalSession
        from app.extensions import db

        project = test_project()

        session = ExperimentalSession(
            project_id=project.id,
            date=date.today(),
            batch_identifier="Test Session",
        )
        db.session.add(session)
        db.session.commit()

        with pytest.raises(SmartPlannerError) as exc:
            SmartPlannerService.link_setup_to_session(99999, session.id)
        assert 'not found' in str(exc.value)

    def test_link_session_not_found(self, db_session, test_project):
        """Test linking with non-existent session."""
        from app.models import ReactionSetup
        from app.extensions import db

        project = test_project()

        setup = ReactionSetup(
            project_id=project.id,
            name="Test Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
        )
        db.session.add(setup)
        db.session.commit()

        with pytest.raises(SmartPlannerError) as exc:
            SmartPlannerService.link_setup_to_session(setup.id, 99999)
        assert 'not found' in str(exc.value)

    def test_link_project_mismatch(self, db_session, test_project):
        """Test linking fails when projects don't match."""
        from app.models import ReactionSetup, ExperimentalSession
        from app.extensions import db

        project1 = test_project()
        project2 = test_project(name="Other Project")

        # Setup in project1
        setup = ReactionSetup(
            project_id=project1.id,
            name="Test Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
        )
        db.session.add(setup)
        db.session.flush()

        # Session in project2
        session = ExperimentalSession(
            project_id=project2.id,
            date=date.today(),
            batch_identifier="Test Session",
        )
        db.session.add(session)
        db.session.commit()

        with pytest.raises(SmartPlannerError) as exc:
            SmartPlannerService.link_setup_to_session(setup.id, session.id)
        assert 'does not match' in str(exc.value)


class TestGetUnlinkedSetups:
    """Tests for getting unlinked setups."""

    def test_get_unlinked_setups(self, db_session, test_project):
        """Test retrieving unlinked setups."""
        from app.models import ReactionSetup
        from app.extensions import db

        project = test_project()

        # Create unlinked setup
        setup = ReactionSetup(
            project_id=project.id,
            name="Unlinked Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
            session_id=None,  # Not linked
        )
        db.session.add(setup)
        db.session.commit()

        setups = SmartPlannerService.get_unlinked_setups(project.id)
        assert len(setups) == 1
        assert setups[0].name == "Unlinked Setup"

    def test_get_unlinked_excludes_linked(self, db_session, test_project):
        """Test that linked setups are excluded."""
        from app.models import ReactionSetup, ExperimentalSession
        from app.extensions import db

        project = test_project()

        # Create session
        session = ExperimentalSession(
            project_id=project.id,
            date=date.today(),
            batch_identifier="Test Session",
        )
        db.session.add(session)
        db.session.flush()

        # Create linked setup
        linked_setup = ReactionSetup(
            project_id=project.id,
            name="Linked Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
            session_id=session.id,
        )
        # Create unlinked setup
        unlinked_setup = ReactionSetup(
            project_id=project.id,
            name="Unlinked Setup",
            n_constructs=2,
            n_replicates=4,
            total_reaction_volume_ul=200.0,
            session_id=None,
        )
        db.session.add_all([linked_setup, unlinked_setup])
        db.session.commit()

        setups = SmartPlannerService.get_unlinked_setups(project.id)
        assert len(setups) == 1
        assert setups[0].name == "Unlinked Setup"


class TestGetProjectSummary:
    """Tests for F4.23: Fresh session (no history/templates)."""

    def test_get_project_summary(self, db_session, test_project):
        """Test project summary generation."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        constructs = [
            Construct(
                project_id=project.id,
                identifier="Reporter-only",
                family="control",
                is_unregulated=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_WT",
                family="Tbox1",
                is_wildtype=True,
            ),
        ]
        db.session.add_all(constructs)
        db.session.commit()

        summary = SmartPlannerService.get_project_summary(project.id)

        assert summary['project_id'] == project.id
        assert summary['total_constructs'] == 2
        assert summary['constructs_with_data'] == 0
        assert summary['mode'] == 'first_experiment'
        assert summary['constraints_valid'] == True  # Has reporter-only

    def test_get_project_summary_not_found(self, db_session):
        """Test summary for non-existent project."""
        with pytest.raises(SmartPlannerError) as exc:
            SmartPlannerService.get_project_summary(99999)
        assert 'not found' in str(exc.value)


class TestImpactPreview:
    """Tests for impact preview calculation."""

    def test_calculate_impact_preview(self, db_session, test_project):
        """Test impact preview calculation."""
        from app.models import Construct
        from app.extensions import db

        project = test_project()

        # Add constructs
        constructs = [
            Construct(
                project_id=project.id,
                identifier="Reporter-only",
                family="control",
                is_unregulated=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_WT",
                family="Tbox1",
                is_wildtype=True,
            ),
            Construct(
                project_id=project.id,
                identifier="Tbox1_M1",
                family="Tbox1",
            ),
        ]
        db.session.add_all(constructs)
        db.session.commit()

        mutant_id = constructs[2].id

        impact = SmartPlannerService.calculate_impact_preview(
            project.id,
            selected_construct_ids=[mutant_id],
            additional_replicates=4,
        )

        assert impact.constructs_before == 0  # No data yet
        assert impact.constructs_gained >= 0
        assert isinstance(impact.per_construct_impact, list)
