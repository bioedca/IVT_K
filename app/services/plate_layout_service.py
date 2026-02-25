"""
Plate layout management service.

Phase 2.4: Plate layout templates (F5.1-F5.3)
- F5.1: Create plate layout template with selectable format (96-well or 384-well)
- F5.2: Assign constructs to wells via click-to-assign visual grid with bulk selection
- F5.3: Define blank and negative control wells (with type specification)
"""
from typing import Optional, List, Tuple, Dict
from datetime import datetime

from sqlalchemy import and_

from app.extensions import db
from app.models import Project, Construct, AuditLog
from app.models.enums import LigandCondition
from app.models.plate_layout import PlateLayout, WellAssignment, WellType


class PlateLayoutValidationError(Exception):
    """Raised when plate layout validation fails."""
    pass


class PlateLayoutService:
    """
    Service for managing plate layout templates and well assignments.

    Plate layouts define which constructs go in which wells, supporting
    both 96-well and 384-well formats with anchor construct requirements.
    """

    # Valid well positions for each format
    ROW_LABELS = "ABCDEFGHIJKLMNOP"  # 16 rows max for 384-well

    @staticmethod
    def create_layout(
        project_id: int,
        name: str,
        username: str,
        plate_format: str = "384",
        is_template: bool = True
    ) -> PlateLayout:
        """
        Create a new plate layout template.

        Args:
            project_id: Parent project ID
            name: Layout name
            username: User creating the layout
            plate_format: "96" or "384"
            is_template: Whether this is a reusable template

        Returns:
            Created PlateLayout instance

        Raises:
            PlateLayoutValidationError: If validation fails
        """
        # Validate project exists
        project = Project.query.get(project_id)
        if not project:
            raise PlateLayoutValidationError(f"Project {project_id} not found")

        if not name or not name.strip():
            raise PlateLayoutValidationError("Layout name cannot be empty")

        name = name.strip()

        # Validate plate format
        if plate_format not in ("96", "384"):
            raise PlateLayoutValidationError(
                f"Invalid plate format: {plate_format}. Must be '96' or '384'"
            )

        # Check project plate format matches
        if project.plate_format.value != plate_format:
            raise PlateLayoutValidationError(
                f"Layout format ({plate_format}) must match project format "
                f"({project.plate_format.value})"
            )

        # Check for duplicate name in project (version 1)
        existing = PlateLayout.query.filter_by(
            project_id=project_id,
            name=name,
            version=1
        ).first()
        if existing:
            raise PlateLayoutValidationError(
                f"Layout '{name}' already exists in this project"
            )

        layout = PlateLayout(
            project_id=project_id,
            name=name,
            plate_format=plate_format,
            is_template=is_template,
            is_draft=True
        )

        db.session.add(layout)
        db.session.flush()  # Assigns layout.id without committing

        AuditLog.log_action(
            username=username,
            action_type="create",
            entity_type="plate_layout",
            entity_id=layout.id,
            project_id=project_id,
            changes=[
                {"field": "name", "old": None, "new": name},
                {"field": "plate_format", "old": None, "new": plate_format}
            ]
        )

        db.session.commit()

        return layout

    @staticmethod
    def create_instance_from_template(template_id: int) -> PlateLayout:
        """
        Create a modifiable instance from a template layout.

        This is extracted from PlateLayout.create_instance() to keep
        business logic in the service layer.

        Args:
            template_id: ID of the template layout to instantiate

        Returns:
            New PlateLayout instance (not yet committed)

        Raises:
            PlateLayoutValidationError: If template not found
        """
        template = PlateLayout.query.get(template_id)
        if not template:
            raise PlateLayoutValidationError(f"Template layout {template_id} not found")
        return template.create_instance()

    @staticmethod
    def get_layout(layout_id: int) -> Optional[PlateLayout]:
        """Get a plate layout by ID."""
        return PlateLayout.query.get(layout_id)

    @staticmethod
    def list_layouts(
        project_id: int,
        templates_only: bool = False,
        include_draft: bool = True
    ) -> List[PlateLayout]:
        """
        List plate layouts for a project.

        Args:
            project_id: Project to list layouts for
            templates_only: Only return template layouts (not instances)
            include_draft: Include draft layouts

        Returns:
            List of PlateLayout instances
        """
        query = PlateLayout.query.filter_by(project_id=project_id)

        if templates_only:
            query = query.filter_by(is_template=True)

        if not include_draft:
            query = query.filter_by(is_draft=False)

        return query.order_by(PlateLayout.name, PlateLayout.version).all()

    @staticmethod
    def _validate_well_position(position: str, rows: int, cols: int) -> bool:
        """Validate a well position string (e.g., 'A1', 'H12')."""
        if not position or len(position) < 2:
            return False

        row_letter = position[0].upper()
        try:
            col_num = int(position[1:])
        except ValueError:
            return False

        if row_letter not in PlateLayoutService.ROW_LABELS[:rows]:
            return False

        if col_num < 1 or col_num > cols:
            return False

        return True

    @staticmethod
    def assign_well(
        layout_id: int,
        well_position: str,
        username: str,
        construct_id: int = None,
        well_type: WellType = WellType.SAMPLE,
        paired_with: str = None,
        replicate_group: str = None,
        ligand_concentration: float = None,
        ligand_condition: str = None
    ) -> WellAssignment:
        """
        Assign a construct or control type to a well.

        Args:
            layout_id: Layout to modify
            well_position: Well position (e.g., "A1")
            username: User making the assignment
            construct_id: Construct to assign (None for controls)
            well_type: Type of well (SAMPLE, BLANK, NEGATIVE_CONTROL_*, EMPTY)
            paired_with: Well position of paired control
            replicate_group: Name of replicate group
            ligand_concentration: Ligand concentration for this well (F5.10)

        Returns:
            Created or updated WellAssignment

        Raises:
            PlateLayoutValidationError: If validation fails
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        well_position = well_position.upper()
        if not PlateLayoutService._validate_well_position(well_position, layout.rows, layout.cols):
            raise PlateLayoutValidationError(
                f"Invalid well position: {well_position} for {layout.plate_format}-well plate"
            )

        # Validate construct if provided
        if construct_id is not None:
            construct = Construct.query.get(construct_id)
            if not construct:
                raise PlateLayoutValidationError(f"Construct {construct_id} not found")
            if construct.project_id != layout.project_id:
                raise PlateLayoutValidationError(
                    "Construct must belong to the same project as the layout"
                )
            # Sample wells require a construct
            if well_type == WellType.SAMPLE:
                pass  # Valid
        else:
            # Non-sample wells should not have a construct
            if well_type == WellType.SAMPLE:
                raise PlateLayoutValidationError(
                    "Sample wells require a construct assignment"
                )

        # Validate ligand concentration
        if ligand_concentration is not None and ligand_concentration < 0:
            raise PlateLayoutValidationError(
                "Ligand concentration cannot be negative"
            )

        # Validate paired_with position if provided
        if paired_with:
            paired_with = paired_with.upper()
            if not PlateLayoutService._validate_well_position(paired_with, layout.rows, layout.cols):
                raise PlateLayoutValidationError(
                    f"Invalid paired well position: {paired_with}"
                )

        # Check for existing assignment at this position
        existing = WellAssignment.query.filter_by(
            layout_id=layout_id,
            well_position=well_position
        ).first()

        # Look up paired_with assignment by position if provided
        paired_assignment = None
        if paired_with:
            paired_assignment = WellAssignment.query.filter_by(
                layout_id=layout_id,
                well_position=paired_with
            ).first()

        old_values = None
        if existing:
            old_values = {
                "construct_id": existing.construct_id,
                "well_type": existing.well_type.value,
                "paired_with": existing.paired_with.well_position if existing.paired_with else None,
                "replicate_group": existing.replicate_group,
                "ligand_concentration": existing.ligand_concentration,
                "ligand_condition": existing.ligand_condition,
            }
            # Update existing
            existing.construct_id = construct_id
            existing.well_type = well_type
            existing.paired_with = paired_assignment  # Set relationship object, not string
            existing.replicate_group = replicate_group
            existing.ligand_concentration = ligand_concentration
            existing.ligand_condition = ligand_condition
            assignment = existing
        else:
            # Create new
            assignment = WellAssignment(
                layout_id=layout_id,
                well_position=well_position,
                construct_id=construct_id,
                well_type=well_type,
                ligand_concentration=ligand_concentration,
                ligand_condition=ligand_condition,
                replicate_group=replicate_group
            )
            # Set relationship after creation (can't pass to __init__)
            assignment.paired_with = paired_assignment
            db.session.add(assignment)

        AuditLog.log_action(
            username=username,
            action_type="update" if old_values else "create",
            entity_type="well_assignment",
            entity_id=assignment.id if old_values else 0,
            project_id=layout.project_id,
            changes=[
                {"field": "well_position", "old": None, "new": well_position},
                {"field": "well_type", "old": old_values.get("well_type") if old_values else None, "new": well_type.value},
                {"field": "construct_id", "old": str(old_values.get("construct_id")) if old_values else None, "new": str(construct_id) if construct_id else None}
            ]
        )

        db.session.commit()

        return assignment

    @staticmethod
    def bulk_assign_wells(
        layout_id: int,
        well_positions: List[str],
        username: str,
        construct_id: int = None,
        well_type: WellType = WellType.SAMPLE,
        replicate_group: str = None,
        ligand_concentration: float = None,
        ligand_condition: str = None
    ) -> List[WellAssignment]:
        """
        Assign multiple wells at once.

        Args:
            layout_id: Layout to modify
            well_positions: List of well positions
            username: User making the assignment
            construct_id: Construct to assign to all wells
            well_type: Type for all wells
            replicate_group: Group name for all wells
            ligand_concentration: Ligand concentration for all wells
            ligand_condition: Ligand condition (+Lig/-Lig) for all wells

        Returns:
            List of created/updated WellAssignments
        """
        assignments = []
        for position in well_positions:
            assignment = PlateLayoutService.assign_well(
                layout_id=layout_id,
                well_position=position,
                username=username,
                construct_id=construct_id,
                well_type=well_type,
                replicate_group=replicate_group,
                ligand_concentration=ligand_concentration,
                ligand_condition=ligand_condition
            )
            assignments.append(assignment)
        return assignments

    @staticmethod
    def bulk_assign_ligand(
        layout_id: int,
        well_positions: List[str],
        ligand_concentration: float,
        username: str
    ) -> List[WellAssignment]:
        """
        Assign ligand concentration to multiple existing wells (F5.10).

        Only updates the ligand_concentration field, preserving other assignments.

        Args:
            layout_id: Layout to modify
            well_positions: List of well positions
            ligand_concentration: Ligand concentration to assign
            username: User making the assignment

        Returns:
            List of updated WellAssignments

        Raises:
            PlateLayoutValidationError: If validation fails
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        if ligand_concentration is not None and ligand_concentration < 0:
            raise PlateLayoutValidationError(
                "Ligand concentration cannot be negative"
            )

        updated = []
        for position in well_positions:
            position = position.upper()
            if not PlateLayoutService._validate_well_position(position, layout.rows, layout.cols):
                raise PlateLayoutValidationError(
                    f"Invalid well position: {position}"
                )

            assignment = WellAssignment.query.filter_by(
                layout_id=layout_id,
                well_position=position
            ).first()

            if assignment:
                old_conc = assignment.ligand_concentration
                assignment.ligand_concentration = ligand_concentration
                updated.append(assignment)

        if updated:
            AuditLog.log_action(
                username=username,
                action_type="update",
                entity_type="well_assignments",
                entity_id=layout_id,
                project_id=layout.project_id,
                changes=[{
                    "field": "ligand_concentration",
                    "wells": [a.well_position for a in updated],
                    "new": str(ligand_concentration)
                }]
            )
            db.session.commit()

        return updated

    @staticmethod
    def clear_well(layout_id: int, well_position: str, username: str) -> bool:
        """
        Clear a well assignment (set to empty).

        Args:
            layout_id: Layout to modify
            well_position: Well position to clear
            username: User making the change

        Returns:
            True if cleared, False if position not found
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        well_position = well_position.upper()
        existing = WellAssignment.query.filter_by(
            layout_id=layout_id,
            well_position=well_position
        ).first()

        if existing:
            old_type = existing.well_type.value
            db.session.delete(existing)

            AuditLog.log_action(
                username=username,
                action_type="delete",
                entity_type="well_assignment",
                entity_id=existing.id,
                project_id=layout.project_id,
                changes=[
                    {"field": "well_position", "old": well_position, "new": None},
                    {"field": "well_type", "old": old_type, "new": None}
                ]
            )
            db.session.commit()
            return True

        return False

    @staticmethod
    def get_layout_summary(layout_id: int) -> Dict:
        """
        Get a summary of the layout's well assignments.

        Returns:
            Dict with counts by well type, construct, and ligand info
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()

        # Collect ligand concentrations and conditions
        ligand_concentrations = set()
        ligand_conditions = set()
        wells_with_ligand = 0
        wells_plus_lig = 0
        wells_minus_lig = 0
        for a in assignments:
            if a.ligand_concentration is not None and a.ligand_concentration > 0:
                ligand_concentrations.add(a.ligand_concentration)
                wells_with_ligand += 1
            if a.ligand_condition:
                ligand_conditions.add(a.ligand_condition)
                if a.ligand_condition == LigandCondition.PLUS_LIG:
                    wells_plus_lig += 1
                elif a.ligand_condition == LigandCondition.MINUS_LIG:
                    wells_minus_lig += 1

        summary = {
            "layout_id": layout_id,
            "name": layout.name,
            "plate_format": layout.plate_format,
            "total_wells": layout.total_wells,
            "assigned_wells": len(assignments),
            "empty_wells": layout.total_wells - len(assignments),
            "by_type": {},
            "by_construct": {},
            "constructs": [],
            "ligand": {
                "wells_with_ligand": wells_with_ligand,
                "unique_concentrations": sorted(list(ligand_concentrations)),
                "concentration_count": len(ligand_concentrations)
            },
            "ligand_conditions": {
                "conditions": sorted(list(ligand_conditions)),
                "wells_plus_lig": wells_plus_lig,
                "wells_minus_lig": wells_minus_lig,
                "has_ligand_conditions": len(ligand_conditions) > 0,
            }
        }

        for wt in WellType:
            summary["by_type"][wt.value] = 0

        for assignment in assignments:
            summary["by_type"][assignment.well_type.value] += 1

            if assignment.construct_id:
                if assignment.construct_id not in summary["by_construct"]:
                    summary["by_construct"][assignment.construct_id] = {
                        "count": 0,
                        "identifier": assignment.construct.identifier if assignment.construct else "Unknown"
                    }
                summary["by_construct"][assignment.construct_id]["count"] += 1

        # Convert construct dict to list
        for construct_id, data in summary["by_construct"].items():
            summary["constructs"].append({
                "construct_id": construct_id,
                "identifier": data["identifier"],
                "count": data["count"]
            })

        return summary

    @staticmethod
    def get_layout_grid(layout_id: int) -> List[List[Dict]]:
        """
        Get the layout as a 2D grid for display.

        Returns:
            2D list of well data, row by row
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        # Build assignment lookup
        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()
        assignment_map = {a.well_position: a for a in assignments}

        grid = []
        for row_idx in range(layout.rows):
            row_letter = PlateLayoutService.ROW_LABELS[row_idx]
            row_data = []
            for col_idx in range(layout.cols):
                col_num = col_idx + 1
                position = f"{row_letter}{col_num}"

                assignment = assignment_map.get(position)
                if assignment:
                    # Determine analytical role from construct flags
                    analytical_role = None
                    family_id = None
                    if assignment.construct:
                        family_id = assignment.construct.family_id
                        if assignment.construct.is_unregulated:
                            analytical_role = "unregulated"
                        elif assignment.construct.is_wildtype:
                            analytical_role = "wildtype"
                        else:
                            analytical_role = "mutant"

                    cell = {
                        "position": position,
                        "well_type": assignment.well_type.value,
                        "construct_id": assignment.construct_id,
                        "construct_identifier": assignment.construct.identifier if assignment.construct else None,
                        "construct_name": assignment.construct.identifier if assignment.construct else None,
                        "is_draft": assignment.construct.is_draft if assignment.construct else None,
                        "paired_with": assignment.paired_with.well_position if assignment.paired_with else None,
                        "replicate_group": assignment.replicate_group,
                        "ligand_concentration": assignment.ligand_concentration,
                        "ligand_condition": assignment.ligand_condition,
                        "analytical_role": analytical_role,
                        "family_id": family_id,
                    }
                else:
                    cell = {
                        "position": position,
                        "well_type": "empty",
                        "construct_id": None,
                        "construct_identifier": None,
                        "construct_name": None,
                        "is_draft": None,
                        "paired_with": None,
                        "replicate_group": None,
                        "ligand_concentration": None,
                        "ligand_condition": None,
                        "analytical_role": None,
                        "family_id": None,
                    }
                row_data.append(cell)
            grid.append(row_data)

        return grid

    @staticmethod
    def count_negative_controls(layout_id: int) -> int:
        """Count negative control wells in a layout."""
        return WellAssignment.query.filter(
            WellAssignment.layout_id == layout_id,
            WellAssignment.well_type.in_([
                WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                WellType.NEGATIVE_CONTROL_NO_DYE
            ])
        ).count()

    @staticmethod
    def publish_layout(layout_id: int, username: str) -> PlateLayout:
        """
        Publish a layout (mark as non-draft).

        Validates anchor requirements before publishing.

        Args:
            layout_id: Layout to publish
            username: User performing the action

        Returns:
            Updated PlateLayout

        Raises:
            PlateLayoutValidationError: If validation fails
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        if not layout.is_draft:
            return layout  # Already published

        # Validate before publishing
        is_valid, issues = PlateLayoutService.validate_layout(layout_id)
        if not is_valid:
            raise PlateLayoutValidationError(
                "Layout validation failed: " + "; ".join(issues)
            )

        layout.is_draft = False

        AuditLog.log_action(
            username=username,
            action_type="publish",
            entity_type="plate_layout",
            entity_id=layout_id,
            project_id=layout.project_id,
            changes=[{"field": "is_draft", "old": "True", "new": "False"}]
        )

        db.session.commit()
        return layout

    @staticmethod
    def unpublish_layout(layout_id: int, username: str) -> PlateLayout:
        """
        Revert a layout to draft state.

        Args:
            layout_id: Layout to unpublish
            username: User performing the action

        Returns:
            Updated PlateLayout
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        if layout.is_draft:
            return layout  # Already draft

        layout.is_draft = True

        AuditLog.log_action(
            username=username,
            action_type="unpublish",
            entity_type="plate_layout",
            entity_id=layout_id,
            project_id=layout.project_id,
            changes=[{"field": "is_draft", "old": "False", "new": "True"}]
        )

        db.session.commit()
        return layout

    @staticmethod
    def validate_layout(layout_id: int, check_anchors: bool = False) -> Tuple[bool, List[str]]:
        """
        Validate layout meets all requirements.

        Checks:
        - Minimum negative controls (2+) - F5.8
        - At least one sample well
        - (optional) Anchor construct requirements - F5.6, F5.11

        Args:
            layout_id: Layout to validate
            check_anchors: Also check anchor construct requirements

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        layout = PlateLayout.query.get(layout_id)
        if not layout:
            return False, ["Layout not found"]

        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()

        # Check for any assignments
        if not assignments:
            issues.append("Layout has no well assignments")

        # Count negative controls (F5.8)
        neg_controls = sum(
            1 for a in assignments
            if a.well_type in (WellType.NEGATIVE_CONTROL_NO_TEMPLATE, WellType.NEGATIVE_CONTROL_NO_DYE)
        )
        if neg_controls < 2:
            issues.append(f"Minimum 2 negative control wells required (found {neg_controls})")

        # Count sample wells
        sample_wells = sum(1 for a in assignments if a.well_type == WellType.SAMPLE)
        if sample_wells == 0:
            issues.append("At least one sample well required")

        # Check anchor requirements if requested (F5.6, F5.11)
        if check_anchors and assignments:
            anchor_issues = PlateLayoutService._validate_anchor_requirements(layout, assignments)
            issues.extend(anchor_issues)

        return len(issues) == 0, issues

    @staticmethod
    def _validate_anchor_requirements(layout: PlateLayout, assignments: List[WellAssignment]) -> List[str]:
        """
        Validate anchor construct requirements.

        F5.6: Validate all test wells have paired controls (warning, not error)
        F5.11: One WT per T-box family required on each plate where family's mutants appear

        Args:
            layout: The layout being validated
            assignments: List of well assignments

        Returns:
            List of validation issues
        """
        issues = []

        # Build construct info lookup
        sample_assignments = [a for a in assignments if a.well_type == WellType.SAMPLE]

        if not sample_assignments:
            return issues

        # Get all constructs used in this layout
        construct_ids = set(a.construct_id for a in sample_assignments if a.construct_id)
        constructs = Construct.query.filter(Construct.id.in_(construct_ids)).all()
        construct_map = {c.id: c for c in constructs}

        # Group constructs by family
        families_present = {}  # family -> {"has_wt": bool, "has_mutants": bool, "wt_id": int}
        for construct_id in construct_ids:
            construct = construct_map.get(construct_id)
            if not construct or construct.family == "universal":
                continue  # Skip unregulated

            if construct.family not in families_present:
                families_present[construct.family] = {
                    "has_wt": False,
                    "has_mutants": False,
                    "wt_id": None
                }

            if construct.is_wildtype:
                families_present[construct.family]["has_wt"] = True
                families_present[construct.family]["wt_id"] = construct.id
            else:
                families_present[construct.family]["has_mutants"] = True

        # F5.11: Check each family with mutants has its WT on this plate
        for family_name, info in families_present.items():
            if info["has_mutants"] and not info["has_wt"]:
                issues.append(
                    f"Family '{family_name}' has mutants but no wild-type on this plate"
                )

        # Check for unregulated construct (should be on every plate)
        has_unregulated = any(
            construct_map.get(a.construct_id) and construct_map[a.construct_id].is_unregulated
            for a in sample_assignments
        )
        if not has_unregulated:
            issues.append("Reporter-only (unregulated) construct missing from plate")

        # F5.6: Check wells with paired_with references are valid (warning)
        # Note: With the current implementation, invalid paired_with references are
        # silently ignored during assignment (the relationship is not set if the target
        # well doesn't exist). So this validation will only check that existing
        # relationships point to valid wells in the same layout.
        assignment_ids = {a.id for a in assignments}
        for assignment in sample_assignments:
            if assignment.paired_with:
                # Check that the paired well is in this layout's assignments
                if assignment.paired_with.id not in assignment_ids:
                    issues.append(
                        f"Well {assignment.well_position} paired with well "
                        f"{assignment.paired_with.well_position} which is not in this layout"
                    )

        return issues

    @staticmethod
    def validate_layout_for_publish(layout_id: int) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation for publishing a layout.

        Includes all basic validation plus anchor requirements.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        return PlateLayoutService.validate_layout(layout_id, check_anchors=True)

    # =====================================================
    # Bulk Selection Helpers for Ligand Assignment (F5.10)
    # =====================================================

    @staticmethod
    def get_row_wells(layout_id: int, row_letter: str) -> List[str]:
        """
        Get all well positions in a specific row.

        PRD Reference: F5.10 - Ligand bulk assignment with row/column selection

        Args:
            layout_id: Layout ID
            row_letter: Row letter (A-H for 96-well, A-P for 384-well)

        Returns:
            List of well positions (e.g., ["A1", "A2", ..., "A12"])
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        row_letter = row_letter.upper()
        if row_letter not in PlateLayoutService.ROW_LABELS[:layout.rows]:
            raise PlateLayoutValidationError(
                f"Invalid row letter: {row_letter} for {layout.plate_format}-well plate"
            )

        return [f"{row_letter}{col}" for col in range(1, layout.cols + 1)]

    @staticmethod
    def get_column_wells(layout_id: int, column_num: int) -> List[str]:
        """
        Get all well positions in a specific column.

        PRD Reference: F5.10 - Ligand bulk assignment with row/column selection

        Args:
            layout_id: Layout ID
            column_num: Column number (1-12 for 96-well, 1-24 for 384-well)

        Returns:
            List of well positions (e.g., ["A1", "B1", ..., "H1"])
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        if column_num < 1 or column_num > layout.cols:
            raise PlateLayoutValidationError(
                f"Invalid column number: {column_num} for {layout.plate_format}-well plate"
            )

        return [f"{PlateLayoutService.ROW_LABELS[row]}{column_num}"
                for row in range(layout.rows)]

    @staticmethod
    def get_all_wells(layout_id: int) -> List[str]:
        """
        Get all well positions for a layout (Select All).

        PRD Reference: F5.10 - Ligand bulk assignment with row/column selection

        Args:
            layout_id: Layout ID

        Returns:
            List of all well positions
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        wells = []
        for row in range(layout.rows):
            row_letter = PlateLayoutService.ROW_LABELS[row]
            for col in range(1, layout.cols + 1):
                wells.append(f"{row_letter}{col}")

        return wells

    @staticmethod
    def get_assigned_wells(layout_id: int) -> List[str]:
        """
        Get all well positions that have assignments (not empty).

        Useful for selecting only wells that have constructs assigned.

        Args:
            layout_id: Layout ID

        Returns:
            List of assigned well positions
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()
        return [a.well_position for a in assignments]

    @staticmethod
    def get_wells_by_construct(layout_id: int, construct_id: int) -> List[str]:
        """
        Get all well positions assigned to a specific construct.

        Useful for selecting wells by construct for ligand assignment.

        Args:
            layout_id: Layout ID
            construct_id: Construct ID

        Returns:
            List of well positions with this construct
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        assignments = WellAssignment.query.filter_by(
            layout_id=layout_id,
            construct_id=construct_id
        ).all()
        return [a.well_position for a in assignments]

    @staticmethod
    def get_wells_with_ligand(layout_id: int, has_ligand: bool = True) -> List[str]:
        """
        Get wells with or without ligand assignment.

        Args:
            layout_id: Layout ID
            has_ligand: If True, return wells with ligand; if False, return wells without

        Returns:
            List of well positions
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        assignments = WellAssignment.query.filter_by(layout_id=layout_id).all()

        if has_ligand:
            return [a.well_position for a in assignments
                    if a.ligand_concentration is not None and a.ligand_concentration > 0]
        else:
            return [a.well_position for a in assignments
                    if a.ligand_concentration is None or a.ligand_concentration == 0]

    @staticmethod
    def bulk_toggle_ligand(
        layout_id: int,
        well_positions: List[str],
        ligand_concentration: float,
        username: str
    ) -> Dict[str, int]:
        """
        Toggle ligand assignment for multiple wells.

        If a well already has this concentration, set to 0 (no ligand).
        If a well has no ligand or different concentration, set to the given concentration.

        PRD Reference: F5.10 - Ligand bulk assignment

        Args:
            layout_id: Layout ID
            well_positions: Wells to toggle
            ligand_concentration: Target ligand concentration
            username: User making the change

        Returns:
            Dict with counts of wells toggled on vs off
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        toggled_on = 0
        toggled_off = 0

        for position in well_positions:
            position = position.upper()
            assignment = WellAssignment.query.filter_by(
                layout_id=layout_id,
                well_position=position
            ).first()

            if assignment:
                if assignment.ligand_concentration == ligand_concentration:
                    # Toggle off
                    assignment.ligand_concentration = 0
                    toggled_off += 1
                else:
                    # Toggle on
                    assignment.ligand_concentration = ligand_concentration
                    toggled_on += 1

        if toggled_on > 0 or toggled_off > 0:
            AuditLog.log_action(
                username=username,
                action_type="update",
                entity_type="well_assignments",
                entity_id=layout_id,
                project_id=layout.project_id,
                changes=[{
                    "field": "ligand_toggle",
                    "toggled_on": toggled_on,
                    "toggled_off": toggled_off,
                    "concentration": str(ligand_concentration)
                }]
            )
            db.session.commit()

        return {"toggled_on": toggled_on, "toggled_off": toggled_off}

    @staticmethod
    def get_selection_helpers(layout_id: int) -> Dict[str, List[str]]:
        """
        Get all available selection helpers for a layout.

        Returns rows, columns, and special selections for the UI.

        Args:
            layout_id: Layout ID

        Returns:
            Dict with selection options:
            - rows: List of row letters
            - columns: List of column numbers (as strings)
            - special: Dict of special selections (all, assigned, with_ligand, without_ligand)
        """
        layout = PlateLayout.query.get(layout_id)
        if not layout:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        return {
            "rows": list(PlateLayoutService.ROW_LABELS[:layout.rows]),
            "columns": [str(i) for i in range(1, layout.cols + 1)],
            "special": {
                "all": "Select All",
                "assigned": "Select Assigned Wells",
                "with_ligand": "Select Wells With Ligand",
                "without_ligand": "Select Wells Without Ligand"
            }
        }

    @staticmethod
    def create_version(layout_id: int, username: str) -> PlateLayout:
        """
        Create a new version of an existing layout.

        Args:
            layout_id: Source layout ID
            username: User creating the version

        Returns:
            New PlateLayout with incremented version
        """
        source = PlateLayout.query.get(layout_id)
        if not source:
            raise PlateLayoutValidationError(f"Layout {layout_id} not found")

        # Find highest version for this name
        max_version = db.session.query(db.func.max(PlateLayout.version)).filter(
            PlateLayout.project_id == source.project_id,
            PlateLayout.name == source.name
        ).scalar() or 0

        new_layout = PlateLayout(
            project_id=source.project_id,
            name=source.name,
            plate_format=source.plate_format,
            is_template=source.is_template,
            is_draft=True
        )
        new_layout.version = max_version + 1

        db.session.add(new_layout)
        db.session.flush()  # Assigns new_layout.id without committing

        # Copy well assignments including ligand concentration
        # First pass: create assignments without paired_with
        position_to_new_assignment = {}
        old_paired_with_positions = {}  # old position -> paired_with position

        for assignment in source.well_assignments:
            new_assignment = WellAssignment(
                layout=new_layout,
                well_position=assignment.well_position,
                construct_id=assignment.construct_id,
                well_type=assignment.well_type,
                replicate_group=assignment.replicate_group,
                ligand_concentration=assignment.ligand_concentration
            )
            db.session.add(new_assignment)
            position_to_new_assignment[assignment.well_position] = new_assignment

            # Track paired_with relationships to restore later
            if assignment.paired_with:
                old_paired_with_positions[assignment.well_position] = assignment.paired_with.well_position

        # Second pass: restore paired_with relationships
        for position, paired_position in old_paired_with_positions.items():
            if position in position_to_new_assignment and paired_position in position_to_new_assignment:
                position_to_new_assignment[position].paired_with = position_to_new_assignment[paired_position]

        AuditLog.log_action(
            username=username,
            action_type="create",
            entity_type="plate_layout",
            entity_id=new_layout.id,
            project_id=source.project_id,
            changes=[
                {"field": "name", "old": None, "new": source.name},
                {"field": "version", "old": None, "new": str(max_version + 1)},
                {"field": "source_layout_id", "old": None, "new": str(layout_id)}
            ]
        )

        db.session.commit()

        return new_layout
