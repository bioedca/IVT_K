"""Tests for DailyReportService fold-change plate filtering and aggregated output."""
import pytest

from tests.fixtures.project_fixtures import (
    create_test_project,
    create_test_construct,
    create_test_session,
    create_test_plate,
    create_test_well,
)
from tests.fixtures.analysis_fixtures import create_test_fold_change


@pytest.fixture()
def two_plate_project(db_session):
    """Create a project with two plates and fold changes on each.

    Plate A: mutant well + WT well → within-plate FC (fc_fmax=2.5)
    Plate B: mutant well + WT well → within-plate FC (fc_fmax=3.0)
    Cross-plate: Plate-A mutant well ↔ Plate-B WT well → cross-plate FC (fc_fmax=1.8)
    """
    project = create_test_project(name="FC Filter Project")
    wt = create_test_construct(project.id, identifier="WT-1", is_wildtype=True)
    mut = create_test_construct(project.id, identifier="MUT-1")

    session = create_test_session(project.id, batch_identifier="Batch_1")
    plate_a = create_test_plate(session.id, plate_number=1)
    plate_b = create_test_plate(session.id, plate_number=2)

    # Plate A wells
    well_a_mut = create_test_well(plate_a.id, position="A1", construct_id=mut.id)
    well_a_wt = create_test_well(plate_a.id, position="A2", construct_id=wt.id)

    # Plate B wells
    well_b_mut = create_test_well(plate_b.id, position="A1", construct_id=mut.id)
    well_b_wt = create_test_well(plate_b.id, position="A2", construct_id=wt.id)

    # Within-plate FCs
    fc_a = create_test_fold_change(well_a_mut.id, well_a_wt.id, fc_fmax=2.5)
    fc_b = create_test_fold_change(well_b_mut.id, well_b_wt.id, fc_fmax=3.0)

    # Cross-plate FC: test well on plate A, control well on plate B
    fc_cross = create_test_fold_change(well_a_mut.id, well_b_wt.id, fc_fmax=1.8)

    return {
        "project": project,
        "plate_a": plate_a,
        "plate_b": plate_b,
        "fc_a": fc_a,
        "fc_b": fc_b,
        "fc_cross": fc_cross,
    }


@pytest.fixture()
def ligand_project(db_session):
    """Create a project with +Lig/-Lig fold changes and a ligand effect FC."""
    project = create_test_project(name="Ligand Project")
    wt = create_test_construct(project.id, identifier="WT-1", is_wildtype=True)
    mut = create_test_construct(project.id, identifier="MUT-1")

    session = create_test_session(project.id, batch_identifier="Batch_Lig")
    plate = create_test_plate(session.id, plate_number=1)

    well_mut_plus = create_test_well(plate.id, position="A1", construct_id=mut.id, ligand_condition="+Lig")
    well_wt_plus = create_test_well(plate.id, position="A2", construct_id=wt.id, ligand_condition="+Lig")
    well_mut_minus = create_test_well(plate.id, position="B1", construct_id=mut.id, ligand_condition="-Lig")
    well_wt_minus = create_test_well(plate.id, position="B2", construct_id=wt.id, ligand_condition="-Lig")

    # Within-condition FCs
    create_test_fold_change(well_mut_plus.id, well_wt_plus.id, fc_fmax=3.0, ligand_condition="+Lig")
    create_test_fold_change(well_mut_minus.id, well_wt_minus.id, fc_fmax=2.0, ligand_condition="-Lig")

    # Ligand effect FC (production stores "+Lig/-Lig" as condition)
    create_test_fold_change(
        well_mut_plus.id, well_mut_minus.id, fc_fmax=1.5,
        comparison_type="ligand_effect", ligand_condition="+Lig/-Lig",
    )

    return {"project": project, "plate": plate}


@pytest.fixture()
def wt_unreg_project(db_session):
    """Create a project with WT → Unreg fold changes."""
    project = create_test_project(name="WT Unreg Project")
    wt = create_test_construct(project.id, identifier="WT-1", is_wildtype=True)
    unreg = create_test_construct(
        project.id, identifier="UNREG-1", family="universal", is_unregulated=True,
    )

    session = create_test_session(project.id, batch_identifier="Batch_U")
    plate = create_test_plate(session.id, plate_number=1)

    well_wt = create_test_well(plate.id, position="A1", construct_id=wt.id)
    well_unreg = create_test_well(plate.id, position="A2", construct_id=unreg.id)

    create_test_fold_change(
        well_wt.id, well_unreg.id, fc_fmax=0.7, comparison_type="wt_unregulated",
    )

    return {"project": project}


class TestFoldChangePlateFilter:
    """Tests for _generate_fold_change_section plate filtering."""

    def test_no_filter_returns_all(self, two_plate_project):
        """Without plate_ids, all fold changes are included in aggregation."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=None,
        )
        assert "Total FC Records" in html
        # All 3 FCs aggregated
        assert ">3<" in html

    def test_filter_single_plate(self, two_plate_project):
        """Selecting one plate includes only FCs with test wells on that plate."""
        from app.services.daily_report_service import DailyReportService

        plate_a_id = two_plate_project["plate_a"].id
        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=[plate_a_id],
        )
        # Plate A has 2 FCs: within-plate fc_a and cross-plate fc_cross
        assert ">2<" in html

    def test_filter_other_plate(self, two_plate_project):
        """Selecting plate B includes only FC with test well on plate B."""
        from app.services.daily_report_service import DailyReportService

        plate_b_id = two_plate_project["plate_b"].id
        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=[plate_b_id],
        )
        # Plate B has 1 FC: within-plate fc_b only
        assert ">1<" in html

    def test_filter_both_plates(self, two_plate_project):
        """Selecting both plates includes all FCs."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id,
            plate_ids=[
                two_plate_project["plate_a"].id,
                two_plate_project["plate_b"].id,
            ],
        )
        assert ">3<" in html

    def test_cross_plate_fc_included_for_test_plate(self, two_plate_project):
        """Cross-plate FC is counted when its test well's plate is selected."""
        from app.services.daily_report_service import DailyReportService

        plate_a_id = two_plate_project["plate_a"].id
        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=[plate_a_id],
        )
        # 2 FCs on plate A (fc_a=2.5 + fc_cross=1.8) → N pairs=2
        assert ">2<" in html
        assert "MUT-1" in html

    def test_cross_plate_fc_excluded_for_control_plate(self, two_plate_project):
        """Cross-plate FC does NOT appear when only its control well's plate is selected."""
        from app.services.daily_report_service import DailyReportService

        plate_b_id = two_plate_project["plate_b"].id
        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=[plate_b_id],
        )
        # Only fc_b (fc_fmax=3.0) — N pairs=1, mean=3.00
        assert ">1<" in html
        assert "3.00" in html

    def test_nonexistent_plate_returns_empty(self, two_plate_project):
        """Selecting a plate ID that doesn't exist returns no data message."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id, plate_ids=[99999],
        )
        assert "No fold change data available" in html


class TestFoldChangeAggregation:
    """Tests for aggregated fold change output format."""

    def test_aggregated_format_has_summary_columns(self, two_plate_project):
        """Output table has the analysis-interface-style columns."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id,
        )
        assert "Construct" in html
        assert "Type" in html
        assert "N pairs" in html
        assert "FC_Fmax" in html
        assert "FC_kobs" in html

    def test_comparison_type_badge(self, two_plate_project):
        """Mutant → WT comparison type gets correct badge."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id,
        )
        assert "Mutant" in html
        assert "WT" in html
        assert "badge-blue" in html

    def test_stat_cards_present(self, two_plate_project):
        """Summary stat cards show pair counts."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id,
        )
        assert "Mutant" in html
        assert "WT Pairs" in html
        assert "Total FC Records" in html

    def test_mean_sd_format(self, two_plate_project):
        """Multiple FCs per group show mean ± SD format."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            two_plate_project["project"].id,
        )
        # 3 FCs aggregated → should contain ± symbol
        assert "\u00b1" in html


class TestFoldChangeLigandCondition:
    """Tests for ligand condition column and badges in aggregated output."""

    def test_condition_column_present(self, ligand_project):
        """Condition column appears when fold changes have ligand conditions."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            ligand_project["project"].id,
        )
        assert "Condition" in html

    def test_plus_lig_badge(self, ligand_project):
        """Plus-ligand fold changes get teal badge."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            ligand_project["project"].id,
        )
        assert "badge-teal" in html
        assert "+Lig" in html

    def test_minus_lig_badge(self, ligand_project):
        """Minus-ligand fold changes get orange badge."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            ligand_project["project"].id,
        )
        assert "badge-orange" in html
        assert "-Lig" in html

    def test_ligand_effect_badge(self, ligand_project):
        """Ligand effect comparison gets violet badge."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            ligand_project["project"].id,
        )
        assert "badge-violet" in html
        assert "Ligand Effect" in html


class TestFoldChangeWtUnreg:
    """Tests for WT → Unreg comparison type in aggregated output."""

    def test_wt_unreg_badge(self, wt_unreg_project):
        """WT → Unreg comparison type gets green badge."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            wt_unreg_project["project"].id,
        )
        assert "badge-green" in html
        assert "Unreg" in html

    def test_wt_unreg_stat_card(self, wt_unreg_project):
        """WT → Unreg pairs stat card shows correct count."""
        from app.services.daily_report_service import DailyReportService

        html = DailyReportService._generate_fold_change_section(
            wt_unreg_project["project"].id,
        )
        assert "Unreg Pairs" in html
        assert ">1<" in html
