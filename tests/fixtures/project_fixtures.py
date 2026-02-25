"""Project, construct, session, plate, and well factory fixtures."""
from datetime import date, datetime, timezone

from app.extensions import db
from app.models import Project, Construct
from app.models.project import PlateFormat
from app.models.experiment import ExperimentalSession, Plate, Well, FitStatus, QCStatus
from app.models.plate_layout import PlateLayout, WellAssignment, WellType


def create_test_project(
    name="Test Project",
    plate_format=PlateFormat.PLATE_384,
    precision_target=0.2,
    **kwargs,
):
    """Create a test project."""
    project = Project(
        name=name,
        plate_format=plate_format,
        precision_target=precision_target,
        **kwargs,
    )
    db.session.add(project)
    db.session.commit()
    return project


def create_test_construct(
    project_id,
    identifier="TEST-001",
    family="TestFamily",
    is_wildtype=False,
    is_unregulated=False,
    **kwargs,
):
    """Create a test construct."""
    construct = Construct(
        project_id=project_id,
        identifier=identifier,
        family=family if family else "TestFamily",
        is_wildtype=is_wildtype,
        is_unregulated=is_unregulated,
        **kwargs,
    )
    db.session.add(construct)
    db.session.commit()
    return construct


def create_test_session(
    project_id,
    batch_identifier="Batch_001",
    session_date=None,
    qc_status=QCStatus.APPROVED,
    **kwargs,
):
    """Create a test experimental session.

    Args:
        project_id: ID of the parent project.
        batch_identifier: Batch identifier string.
        session_date: Date of the session (defaults to today).
        qc_status: QC review status (defaults to APPROVED).
        **kwargs: Additional fields passed to ExperimentalSession.

    Returns:
        The created ExperimentalSession instance.
    """
    if session_date is None:
        session_date = date.today()
    session = ExperimentalSession(
        project_id=project_id,
        batch_identifier=batch_identifier,
        date=session_date,
        qc_status=qc_status,
        **kwargs,
    )
    db.session.add(session)
    db.session.commit()
    return session


def _ensure_layout(project_id, layout_id=None):
    """Return an existing layout_id or create a minimal PlateLayout.

    Internal helper so callers of ``create_test_plate`` don't have to
    manually create a layout every time.
    """
    if layout_id is not None:
        return layout_id

    layout = PlateLayout(
        project_id=project_id,
        name=f"Auto Layout {datetime.now(timezone.utc).isoformat()}",
    )
    db.session.add(layout)
    db.session.flush()
    return layout.id


def create_test_plate(
    session_id,
    plate_number=1,
    layout_id=None,
    **kwargs,
):
    """Create a test plate.

    If *layout_id* is ``None`` a minimal :class:`PlateLayout` is created
    automatically (requires the session's project to exist).

    Args:
        session_id: ID of the parent ExperimentalSession.
        plate_number: Plate number within the session.
        layout_id: Optional existing PlateLayout id. When omitted a
            layout is auto-created using the session's project_id.
        **kwargs: Additional fields passed to Plate.

    Returns:
        The created Plate instance.
    """
    # Resolve project_id from the session for auto-layout creation.
    session = db.session.get(ExperimentalSession, session_id)
    if session is None:
        raise ValueError(f"ExperimentalSession with id {session_id} not found")
    resolved_layout_id = _ensure_layout(session.project_id, layout_id)

    plate = Plate(
        session_id=session_id,
        layout_id=resolved_layout_id,
        plate_number=plate_number,
        **kwargs,
    )
    db.session.add(plate)
    db.session.commit()
    return plate


def create_test_well(
    plate_id,
    position="A1",
    construct_id=None,
    fit_status=FitStatus.SUCCESS,
    is_excluded=False,
    exclude_from_fc=False,
    ligand_condition=None,
    **kwargs,
):
    """Create a test well."""
    well = Well(
        plate_id=plate_id,
        position=position,
        construct_id=construct_id,
        fit_status=fit_status,
        is_excluded=is_excluded,
        exclude_from_fc=exclude_from_fc,
        ligand_condition=ligand_condition,
        **kwargs,
    )
    db.session.add(well)
    db.session.commit()
    return well


def create_test_project_with_constructs(
    name="Test Project",
    n_mutants=3,
    n_wt=1,
    family="TestFamily",
    include_unregulated=True,
):
    """Create a project with constructs (mutants + WT + optional unregulated).

    Returns:
        Tuple of (project, constructs).
    """
    project = create_test_project(name=name)
    constructs = []

    # Create WT construct(s)
    for i in range(n_wt):
        wt = create_test_construct(
            project_id=project.id,
            identifier=f"WT-{i+1}",
            family=family,
            is_wildtype=True,
        )
        constructs.append(wt)

    # Create mutant constructs
    for i in range(n_mutants):
        mut = create_test_construct(
            project_id=project.id,
            identifier=f"MUT-{i+1}",
            family=family,
            is_wildtype=False,
        )
        constructs.append(mut)

    # Create unregulated construct
    if include_unregulated:
        unreg = create_test_construct(
            project_id=project.id,
            identifier="UNREG-1",
            family="universal",
            is_unregulated=True,
        )
        constructs.append(unreg)

    return project, constructs


def create_test_project_with_wells(
    name="Test Project",
    n_mutants=2,
    n_wt=1,
    wells_per_construct=3,
    family="TestFamily",
    include_unregulated=True,
    with_fits=False,
):
    """Create a project with constructs, session, plate, and wells.

    Returns:
        Tuple of (project, constructs, session, plate, wells).
    """
    project, constructs = create_test_project_with_constructs(
        name=name,
        n_mutants=n_mutants,
        n_wt=n_wt,
        family=family,
        include_unregulated=include_unregulated,
    )

    session = create_test_session(project.id)
    plate = create_test_plate(session.id)

    wells = []
    pos_idx = 0
    for construct in constructs:
        for j in range(wells_per_construct):
            row = chr(65 + pos_idx // 24)  # A, B, C, ...
            col = (pos_idx % 24) + 1
            position = f"{row}{col}"

            well = create_test_well(
                plate_id=plate.id,
                position=position,
                construct_id=construct.id,
                fit_status=FitStatus.SUCCESS if with_fits else FitStatus.PENDING,
            )
            wells.append(well)
            pos_idx += 1

    return project, constructs, session, plate, wells
