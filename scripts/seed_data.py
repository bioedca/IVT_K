#!/usr/bin/env python
"""
Seed data script for IVT Kinetics Analyzer.

Phase 5: API and Scripts
PRD Reference: Section 1.2

Features:
- Creates sample projects with realistic data
- Seeds constructs with families and anchor types
- Generates plate layouts with proper well assignments
- Creates experimental sessions and plates
- Generates synthetic kinetic data
- Optionally seeds analysis results

Usage:
    python scripts/seed_data.py                    # Seed basic data
    python scripts/seed_data.py --full             # Seed with analysis results
    python scripts/seed_data.py --verbose          # Show detailed output
    python scripts/seed_data.py --clean            # Clear existing data first
"""
import sys
import argparse
import math
import random
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import (
    Project, Construct, PlateLayout, WellAssignment,
    ExperimentalSession, Plate, Well, RawDataPoint,
    FitResult, AnalysisVersion, HierarchicalResult, FoldChange
)
from app.models.project import PlateFormat
from app.models.plate_layout import WellType
from app.models.experiment import FitStatus
from app.models.analysis_version import AnalysisStatus


# Sample data configuration
SAMPLE_FAMILIES = [
    ("Tbox1", "T-box riboswitch family 1"),
    ("Tbox2", "T-box riboswitch family 2"),
    ("GlyRS", "Glycine riboswitch"),
]

SAMPLE_CONSTRUCTS = [
    # Tbox1 family
    {"identifier": "Tbox1_WT", "family": "Tbox1", "is_wildtype": True, "description": "Wild-type T-box1 construct"},
    {"identifier": "Tbox1_M1", "family": "Tbox1", "description": "Single mutation in stem 1"},
    {"identifier": "Tbox1_M2", "family": "Tbox1", "description": "Double mutation in stem 2"},
    {"identifier": "Tbox1_M3", "family": "Tbox1", "description": "Triple mutation"},
    # Tbox2 family
    {"identifier": "Tbox2_WT", "family": "Tbox2", "is_wildtype": True, "description": "Wild-type T-box2 construct"},
    {"identifier": "Tbox2_Del1", "family": "Tbox2", "description": "Deletion mutant"},
    # Unregulated control (family is required by model, use "Unregulated" as family)
    {"identifier": "iSpinach_Only", "family": "Unregulated", "is_unregulated": True, "description": "Reporter-only control"},
]


def generate_kinetic_data(
    k_obs: float = 0.1,
    f_max: float = 10000,
    f_background: float = 100,
    t_lag: float = 0.0,
    num_timepoints: int = 50,
    noise_level: float = 0.05,
    temperature_setpoint: float = 37.0
) -> Tuple[List[float], List[float], List[float]]:
    """
    Generate synthetic kinetic data using exponential growth model.

    Args:
        k_obs: Rate constant (1/min)
        f_max: Maximum fluorescence
        f_background: Background fluorescence
        t_lag: Lag time (min)
        num_timepoints: Number of time points
        noise_level: Relative noise level (0-1)
        temperature_setpoint: Temperature setpoint

    Returns:
        Tuple of (timepoints, fluorescence_values, temperatures)
    """
    # Generate time points (0 to 60 minutes, every ~1.2 minutes for 50 points)
    max_time = 60.0
    timepoints = [i * max_time / (num_timepoints - 1) for i in range(num_timepoints)]

    fluorescence_values = []
    temperatures = []

    for t in timepoints:
        # Exponential growth model: F(t) = F_bg + F_max * (1 - exp(-k_obs * (t - t_lag)))
        if t < t_lag:
            f = f_background
        else:
            f = f_background + f_max * (1 - math.exp(-k_obs * (t - t_lag)))

        # Add noise
        noise = random.gauss(0, noise_level * f_max)
        f_noisy = max(0, f + noise)  # Ensure non-negative

        fluorescence_values.append(f_noisy)

        # Temperature with slight variation
        temp = temperature_setpoint + random.gauss(0, 0.3)
        temperatures.append(temp)

    return timepoints, fluorescence_values, temperatures


def create_sample_project(
    name: str = "Sample IVT Project",
    plate_format: PlateFormat = PlateFormat.PLATE_384,
    precision_target: float = 0.2
) -> Project:
    """Create a sample project."""
    project = Project(
        name=name,
        description=f"Sample project for testing - {datetime.now().strftime('%Y-%m-%d')}",
        reporter_system="iSpinach",
        plate_format=plate_format,
        precision_target=precision_target,
        is_draft=False
    )
    db.session.add(project)
    db.session.flush()
    return project


def create_sample_constructs(project_id: int, include_draft: bool = False) -> List[Construct]:
    """Create sample constructs for a project."""
    constructs = []

    for config in SAMPLE_CONSTRUCTS:
        construct = Construct(
            project_id=project_id,
            identifier=config["identifier"],
            family=config.get("family"),
            description=config.get("description"),
            is_wildtype=config.get("is_wildtype", False),
            is_unregulated=config.get("is_unregulated", False),
            is_draft=include_draft and len(constructs) == len(SAMPLE_CONSTRUCTS) - 1
        )
        db.session.add(construct)
        constructs.append(construct)

    db.session.flush()
    return constructs


def create_sample_layout(
    project_id: int,
    constructs: List[Construct],
    name: str = "Standard Layout"
) -> PlateLayout:
    """Create a sample plate layout with well assignments."""
    project = Project.query.get(project_id)
    plate_format = project.plate_format

    # Use string value for plate_format as model expects
    plate_format_str = plate_format.value if hasattr(plate_format, 'value') else str(plate_format)

    layout = PlateLayout(
        project_id=project_id,
        name=name,
        plate_format=plate_format_str,
        is_template=True
    )
    db.session.add(layout)
    db.session.flush()

    # Determine grid size
    if plate_format_str == "384":
        rows = 16
        cols = 24
    else:
        rows = 8
        cols = 12

    row_labels = "ABCDEFGHIJKLMNOP"[:rows]

    # Create well assignments
    well_idx = 0
    construct_idx = 0

    for row in range(rows):
        for col in range(cols):
            position = f"{row_labels[row]}{col + 1}"

            # Skip odd positions for 384-well checkerboard
            if plate_format_str == "384":
                if (row + col) % 2 == 1:
                    continue  # Skip for checkerboard pattern

            # Assign negative controls in last two columns
            if col >= cols - 2:
                if col == cols - 2:
                    well_type = WellType.NEGATIVE_CONTROL_NO_TEMPLATE
                else:
                    well_type = WellType.NEGATIVE_CONTROL_NO_DYE
                assignment = WellAssignment(
                    layout_id=layout.id,
                    well_position=position,
                    well_type=well_type
                )
            # Assign blanks in first column (first 4 wells)
            elif col == 0 and row < 4:
                assignment = WellAssignment(
                    layout_id=layout.id,
                    well_position=position,
                    well_type=WellType.BLANK
                )
            # Assign constructs to remaining wells
            else:
                construct = constructs[construct_idx % len(constructs)]
                construct_idx += 1

                # Alternate ligand concentration
                ligand = 100.0 if well_idx % 2 == 0 else 0.0

                assignment = WellAssignment(
                    layout_id=layout.id,
                    well_position=position,
                    well_type=WellType.SAMPLE,
                    construct_id=construct.id,
                    ligand_concentration=ligand,
                    replicate_group=f"Rep{(well_idx // len(constructs)) + 1}"
                )
                well_idx += 1

            db.session.add(assignment)

    db.session.flush()
    return layout


def create_sample_data(
    project_id: int,
    layout: PlateLayout,
    constructs: List[Construct],
    num_sessions: int = 2,
    plates_per_session: int = 2
) -> Dict[str, Any]:
    """Create sample experimental data with sessions, plates, and raw data."""
    stats = {
        "sessions_created": 0,
        "plates_created": 0,
        "wells_created": 0,
        "data_points_created": 0
    }

    # Define kinetic parameters for each construct
    construct_params = {}
    for i, construct in enumerate(constructs):
        if construct.is_wildtype:
            k_obs = 0.1
            f_max = 10000
        elif construct.is_unregulated:
            k_obs = 0.15
            f_max = 12000
        else:
            # Mutants have varied parameters
            k_obs = 0.1 * (1 + random.uniform(-0.3, 0.5))
            f_max = 10000 * (1 + random.uniform(-0.4, 0.6))

        construct_params[construct.id] = {"k_obs": k_obs, "f_max": f_max}

    # Get well assignments
    assignments = WellAssignment.query.filter_by(layout_id=layout.id).all()
    assignment_map = {a.well_position: a for a in assignments}

    for session_num in range(num_sessions):
        session_date = date.today() - timedelta(days=session_num * 7)
        session = ExperimentalSession(
            project_id=project_id,
            date=session_date,
            batch_identifier=f"Batch_{session_date.strftime('%Y%m%d')}_{session_num + 1}",
            notes=f"Session {session_num + 1} of {num_sessions}"
        )
        db.session.add(session)
        db.session.flush()
        stats["sessions_created"] += 1

        for plate_num in range(plates_per_session):
            plate = Plate(
                session_id=session.id,
                layout_id=layout.id,
                plate_number=plate_num + 1,
                raw_file_path=f"data/raw_files/{project_id}/{session.id}/plate_{plate_num + 1}.txt"
            )
            db.session.add(plate)
            db.session.flush()
            stats["plates_created"] += 1

            # Create wells and data points
            for position, assignment in assignment_map.items():
                # Determine kinetic parameters
                if assignment.construct_id and assignment.construct_id in construct_params:
                    params = construct_params[assignment.construct_id]
                    k_obs = params["k_obs"]
                    f_max = params["f_max"]

                    # Ligand effect
                    if assignment.ligand_concentration and assignment.ligand_concentration > 0:
                        k_obs *= 1.5  # Ligand enhances rate
                        f_max *= 1.2
                else:
                    # Controls/blanks
                    k_obs = 0.0
                    f_max = 0.0

                # Generate data
                timepoints, fluorescence, temps = generate_kinetic_data(
                    k_obs=k_obs,
                    f_max=f_max,
                    f_background=random.uniform(80, 120),
                    noise_level=0.03 + random.uniform(0, 0.02)
                )

                # Create well
                well = Well(
                    plate_id=plate.id,
                    position=position,
                    well_type=assignment.well_type,
                    construct_id=assignment.construct_id,
                    ligand_concentration=assignment.ligand_concentration,
                    fit_status=FitStatus.PENDING
                )
                db.session.add(well)
                db.session.flush()
                stats["wells_created"] += 1

                # Create raw data points
                for t, f, temp in zip(timepoints, fluorescence, temps):
                    data_point = RawDataPoint(
                        well_id=well.id,
                        timepoint=t,
                        fluorescence_raw=f,
                        temperature=temp
                    )
                    db.session.add(data_point)
                    stats["data_points_created"] += 1

    db.session.flush()
    return stats


def create_sample_analysis_results(
    project_id: int,
    constructs: List[Construct]
) -> Dict[str, Any]:
    """Create sample analysis results."""
    stats = {
        "analyses_created": 0,
        "hierarchical_results_created": 0
    }

    # Create analysis version
    analysis = AnalysisVersion(
        project_id=project_id,
        name=f"Analysis {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        description="Sample analysis run",
        status=AnalysisStatus.COMPLETED,
        model_type="bayesian_hierarchical",
        mcmc_chains=4,
        mcmc_draws=2000,
        mcmc_tune=1000,
        started_at=datetime.now() - timedelta(hours=1),
        completed_at=datetime.now(),
        duration_seconds=3600
    )
    db.session.add(analysis)
    db.session.flush()
    stats["analyses_created"] += 1

    # Find WT construct for comparisons
    wt_construct = next((c for c in constructs if c.is_wildtype), None)

    for construct in constructs:
        # Generate hierarchical result
        if construct.is_wildtype:
            mean = 0.0
            std = 0.05
        elif construct.is_unregulated:
            mean = 0.18
            std = 0.08
        else:
            mean = random.uniform(-0.5, 1.0)
            std = random.uniform(0.08, 0.15)

        ci_lower = mean - 1.96 * std
        ci_upper = mean + 1.96 * std

        result = HierarchicalResult(
            analysis_version_id=analysis.id,
            construct_id=construct.id,
            parameter_type="log_fc_fmax",
            analysis_type="bayesian",
            mean=mean,
            std=std,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            r_hat=1.0 + random.uniform(0, 0.05),
            ess_bulk=random.randint(1200, 2000),
            ess_tail=random.randint(1000, 1800),
            prob_positive=0.5 + 0.5 * math.tanh(mean / std) if std > 0 else 0.5,
            var_session=random.uniform(0.01, 0.05),
            var_plate=random.uniform(0.005, 0.02),
            var_residual=random.uniform(0.02, 0.08)
        )
        db.session.add(result)
        stats["hierarchical_results_created"] += 1

        # Note: FoldChange model uses well IDs, not construct IDs
        # Fold changes would be computed after curve fitting at the well level
        # Skipping fold change seeding as it requires actual well data

    db.session.flush()
    return stats


def seed_database(
    include_analysis: bool = False,
    verbose: bool = False,
    clean: bool = False
) -> Dict[str, Any]:
    """
    Seed the database with sample data.

    Args:
        include_analysis: Include analysis results
        verbose: Print detailed progress
        clean: Clear existing data first

    Returns:
        Statistics about created data
    """
    stats = {
        "projects": 0,
        "constructs": 0,
        "layouts": 0,
        "sessions": 0,
        "plates": 0,
        "wells": 0,
        "data_points": 0
    }

    if clean:
        if verbose:
            print("Cleaning existing data...")
        # Disable FK checks to avoid ordering issues with complex FK graph
        db.session.execute(db.text("PRAGMA foreign_keys=OFF"))
        try:
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(table.delete())
        finally:
            db.session.execute(db.text("PRAGMA foreign_keys=ON"))
        db.session.commit()

    if verbose:
        print("Creating sample project...")

    # Create project
    project = create_sample_project(
        name="T-box Riboswitch Study",
        plate_format=PlateFormat.PLATE_384
    )
    stats["projects"] = 1

    if verbose:
        print(f"  Created project: {project.name} (ID: {project.id})")

    # Create constructs
    if verbose:
        print("Creating constructs...")

    constructs = create_sample_constructs(project.id)
    stats["constructs"] = len(constructs)

    if verbose:
        for c in constructs:
            print(f"  - {c.identifier} (family: {c.family})")

    # Create layout
    if verbose:
        print("Creating plate layout...")

    layout = create_sample_layout(project.id, constructs)
    stats["layouts"] = 1

    assignments_count = WellAssignment.query.filter_by(layout_id=layout.id).count()
    if verbose:
        print(f"  Created layout with {assignments_count} well assignments")

    # Create experimental data
    if verbose:
        print("Creating experimental data...")

    data_stats = create_sample_data(project.id, layout, constructs)
    stats["sessions"] = data_stats["sessions_created"]
    stats["plates"] = data_stats["plates_created"]
    stats["wells"] = data_stats["wells_created"]
    stats["data_points"] = data_stats["data_points_created"]

    if verbose:
        print(f"  Sessions: {stats['sessions']}")
        print(f"  Plates: {stats['plates']}")
        print(f"  Wells: {stats['wells']}")
        print(f"  Data points: {stats['data_points']}")

    # Create analysis results if requested
    if include_analysis:
        if verbose:
            print("Creating analysis results...")

        analysis_stats = create_sample_analysis_results(project.id, constructs)
        stats["analyses"] = analysis_stats["analyses_created"]
        stats["hierarchical_results"] = analysis_stats["hierarchical_results_created"]

        if verbose:
            print(f"  Analysis versions: {stats.get('analyses', 0)}")
            print(f"  Hierarchical results: {stats.get('hierarchical_results', 0)}")

    # Commit all changes
    db.session.commit()

    if verbose:
        print("\nSeeding complete!")
        print(f"Total records created: {sum(stats.values())}")

    return stats


def main():
    """Main entry point for seed data script."""
    parser = argparse.ArgumentParser(
        description="Seed the IVT Kinetics Analyzer database with sample data"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include analysis results in seed data"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear existing data before seeding"
    )

    args = parser.parse_args()

    print("IVT Kinetics Analyzer - Data Seeding")
    print("=" * 40)

    app = create_app()

    with app.server.app_context():
        stats = seed_database(
            include_analysis=args.full,
            verbose=args.verbose,
            clean=args.clean
        )

        print("\nSummary:")
        for key, value in stats.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
