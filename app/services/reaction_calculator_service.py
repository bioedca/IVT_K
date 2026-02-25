"""Calculator service - bridges calculator module with database models."""
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.extensions import db
from app.models import Project, Construct, ExperimentalSession, ReactionSetup, ReactionDNAAddition
from app.calculator import (
    calculate_master_mix,
    generate_protocol,
    format_protocol_text,
    format_protocol_csv,
    validate_reaction_parameters,
    validate_construct_list,
    PlateFormat,
    MasterMixCalculation,
    PipettingProtocol,
    ValidationResult,
)
from app.calculator.constants import DEFAULT_OVERAGE_PERCENT


class CalculatorService:
    """Service for IVT Reaction Calculator operations."""

    @staticmethod
    def get_project_constructs(project_id: int) -> List[Dict[str, Any]]:
        """
        Get constructs for a project formatted for calculator.

        Args:
            project_id: Project ID

        Returns:
            List of construct dicts with calculator-required fields
        """
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).all()

        return [
            {
                'id': c.id,
                'name': c.identifier,
                'family': c.family,
                'is_wildtype': c.is_wildtype,
                'is_unregulated': c.is_unregulated,
                'stock_concentration_ng_ul': c.stock_concentration_ng_ul or 100.0,
                'stock_available_ul': c.stock_volume_ul or 100.0,
                'replicates': 4,  # Default, can be overridden
            }
            for c in constructs
        ]

    @staticmethod
    def calculate_reaction_setup(
        project_id: int,
        construct_ids: List[int],
        replicates_per_construct: int = 4,
        dna_mass_ug: float = 20.0,
        overage_percent: float = DEFAULT_OVERAGE_PERCENT,
        negative_template_count: int = 3,
        negative_dye_count: int = 0,
        include_dye: bool = True,
        ntp_concentrations: Optional[Dict[str, float]] = None,
    ) -> MasterMixCalculation:
        """
        Calculate reaction setup for selected constructs.

        Args:
            project_id: Project ID
            construct_ids: List of construct IDs to include
            replicates_per_construct: Replicates per construct
            dna_mass_ug: DNA mass per reaction
            overage_percent: Master mix overage percentage
            negative_template_count: -Template control wells
            negative_dye_count: -DFHBI control wells
            include_dye: Whether to include DFHBI
            ntp_concentrations: Optional custom NTP concentrations

        Returns:
            MasterMixCalculation result
        """
        # Get construct details from database
        constructs_db = Construct.query.filter(
            Construct.id.in_(construct_ids),
            Construct.project_id == project_id,
            Construct.is_deleted == False,
        ).all()

        constructs = [
            {
                'id': c.id,
                'name': c.identifier,
                'family': c.family,
                'is_wildtype': c.is_wildtype,
                'is_unregulated': c.is_unregulated,
                'stock_concentration_ng_ul': c.stock_concentration_ng_ul or 100.0,
                'replicates': replicates_per_construct,
            }
            for c in constructs_db
        ]

        # Calculate total reactions
        n_reactions = (
            len(constructs) * replicates_per_construct
            + negative_template_count
            + negative_dye_count
        )

        # Get NTP concentrations
        ntp = ntp_concentrations or {}

        return calculate_master_mix(
            n_reactions=n_reactions,
            dna_mass_ug=dna_mass_ug,
            overage_percent=overage_percent,
            constructs=constructs,
            negative_template_count=negative_template_count,
            negative_dye_count=negative_dye_count,
            include_dye=include_dye,
            gtp_stock_mm=ntp.get('gtp_stock_mm', 467.3),
            gtp_final_mm=ntp.get('gtp_final_mm', 6.0),
            atp_stock_mm=ntp.get('atp_stock_mm', 364.8),
            atp_final_mm=ntp.get('atp_final_mm', 5.0),
            ctp_stock_mm=ntp.get('ctp_stock_mm', 343.3),
            ctp_final_mm=ntp.get('ctp_final_mm', 5.0),
            utp_stock_mm=ntp.get('utp_stock_mm', 407.8),
            utp_final_mm=ntp.get('utp_final_mm', 5.0),
        )

    @staticmethod
    def validate_setup(
        project_id: int,
        construct_ids: List[int],
        replicates_per_construct: int,
        dna_mass_ug: float,
        negative_template_count: int,
        negative_dye_count: int = 0,
    ) -> ValidationResult:
        """
        Validate a reaction setup before calculation.

        Args:
            project_id: Project ID
            construct_ids: List of construct IDs
            replicates_per_construct: Replicates per construct
            dna_mass_ug: DNA mass per reaction
            negative_template_count: -Template control wells
            negative_dye_count: -DFHBI control wells

        Returns:
            ValidationResult
        """
        # Get project plate format
        project = Project.query.get(project_id)
        if not project:
            result = ValidationResult(is_valid=False)
            result.messages.append({
                'level': 'error',
                'field': 'project_id',
                'message': f'Project {project_id} not found',
            })
            return result

        plate_format = PlateFormat.WELL_384 if project.plate_format == '384' else PlateFormat.WELL_96

        # Get constructs
        constructs = CalculatorService.get_project_constructs(project_id)
        selected_constructs = [c for c in constructs if c['id'] in construct_ids]

        # Validate parameters
        param_result = validate_reaction_parameters(
            dna_mass_ug=dna_mass_ug,
            n_replicates=replicates_per_construct,
            n_constructs=len(selected_constructs),
            negative_template_count=negative_template_count,
            negative_dye_count=negative_dye_count,
            plate_format=plate_format,
        )

        # Validate construct list
        construct_result = validate_construct_list(
            selected_constructs,
            require_unregulated=True,
        )

        # Combine results
        combined = ValidationResult(
            is_valid=param_result.is_valid and construct_result.is_valid,
            messages=param_result.messages + construct_result.messages,
        )

        return combined

    @staticmethod
    def save_reaction_setup(
        project_id: int,
        calculation: MasterMixCalculation,
        name: str,
        n_replicates: int = 4,
        created_by: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> ReactionSetup:
        """
        Save a reaction setup to the database.

        Args:
            project_id: Project ID
            calculation: MasterMixCalculation result
            name: Setup name
            n_replicates: Number of replicates per construct (minimum 4, per PRD F4.8)
            created_by: Username
            session_id: Optional session ID to link

        Returns:
            Created ReactionSetup

        Raises:
            ValueError: If n_replicates is less than 4
        """
        # Validate minimum replicate count (PRD requirement F4.8, T2.5.20)
        if n_replicates < 4:
            raise ValueError(
                f"Minimum of 4 replicates required for statistical validity, got {n_replicates}"
            )
        # Build master mix volumes dict
        mm_volumes = {
            comp.name: {
                'single_ul': comp.single_reaction_volume_ul,
                'total_ul': comp.master_mix_volume_ul,
                'stock_concentration': comp.stock_concentration,
                'stock_unit': comp.stock_unit,
                'final_concentration': comp.final_concentration,
                'final_unit': comp.final_unit,
            }
            for comp in calculation.components
        }

        # Generate protocol text
        protocol = generate_protocol(calculation, title=name, created_by=created_by)
        protocol_text = format_protocol_text(protocol)

        # Create setup record
        setup = ReactionSetup(
            project_id=project_id,
            name=name,
            created_by=created_by,
            n_constructs=len([a for a in calculation.dna_additions if not a.is_negative_control]),
            n_replicates=n_replicates,
            include_negative_template=calculation.dna_additions and any(
                a.negative_control_type == 'no_template' for a in calculation.dna_additions
            ),
            n_negative_template=len([
                a for a in calculation.dna_additions
                if a.is_negative_control and a.negative_control_type == 'no_template'
            ]),
            include_negative_dye=calculation.dna_additions and any(
                a.negative_control_type == 'no_dye' for a in calculation.dna_additions
            ),
            n_negative_dye=len([
                a for a in calculation.dna_additions
                if a.is_negative_control and a.negative_control_type == 'no_dye'
            ]),
            overage_percent=(calculation.overage_factor - 1) * 100,
            dna_mass_ug=calculation.single_reaction.dna_mass_ug,
            total_reaction_volume_ul=calculation.single_reaction.reaction_volume_ul,
            master_mix_volumes=mm_volumes,
            total_master_mix_volume_ul=calculation.total_master_mix_volume_ul,
            n_reactions=calculation.n_reactions,
            master_mix_per_tube_ul=calculation.master_mix_per_tube_ul,
            ligand_stock_concentration_um=(
                calculation.ligand_config.stock_concentration_uM
                if calculation.is_ligand_workflow and calculation.ligand_config else None
            ),
            ligand_final_concentration_um=(
                calculation.ligand_config.final_concentration_uM
                if calculation.is_ligand_workflow and calculation.ligand_config else None
            ),
            ligand_volume_per_rxn_ul=(
                calculation.ligand_volume_per_rxn_ul
                if calculation.is_ligand_workflow and calculation.ligand_config else None
            ),
            protocol_text=protocol_text,
            session_id=session_id,
        )

        db.session.add(setup)
        db.session.flush()

        # Create DNA addition records
        for addition in calculation.dna_additions:
            lig_cond = getattr(addition, 'ligand_condition', None)
            dna_record = ReactionDNAAddition(
                reaction_setup_id=setup.id,
                construct_id=addition.construct_id,
                construct_name=addition.construct_name,
                is_negative_control=addition.is_negative_control,
                negative_control_type=addition.negative_control_type,
                dna_stock_concentration_ng_ul=addition.stock_concentration_ng_ul if not addition.is_negative_control else None,
                ligand_condition=str(lig_cond) if lig_cond else None,
                dna_volume_ul=addition.dna_volume_ul,
                water_adjustment_ul=addition.water_adjustment_ul,
                total_addition_ul=addition.total_addition_ul,
            )
            db.session.add(dna_record)

        db.session.commit()
        return setup

    @staticmethod
    def get_reaction_setup(setup_id: int) -> Optional[ReactionSetup]:
        """
        Get a reaction setup by ID.

        Args:
            setup_id: ReactionSetup ID

        Returns:
            ReactionSetup or None
        """
        return ReactionSetup.query.get(setup_id)

    @staticmethod
    def list_reaction_setups(project_id: int) -> List[ReactionSetup]:
        """
        List all reaction setups for a project.

        Args:
            project_id: Project ID

        Returns:
            List of ReactionSetup
        """
        return ReactionSetup.query.filter_by(project_id=project_id).order_by(
            ReactionSetup.created_at.desc()
        ).all()

    @staticmethod
    def link_to_session(setup_id: int, session_id: int) -> ReactionSetup:
        """
        Link a reaction setup to an experimental session.

        Args:
            setup_id: ReactionSetup ID
            session_id: ExperimentalSession ID

        Returns:
            Updated ReactionSetup
        """
        setup = ReactionSetup.query.get(setup_id)
        if not setup:
            raise ValueError(f"ReactionSetup {setup_id} not found")

        session = ExperimentalSession.query.get(session_id)
        if not session:
            raise ValueError(f"ExperimentalSession {session_id} not found")

        setup.session_id = session_id
        db.session.commit()
        return setup

    @staticmethod
    def export_protocol(setup_id: int, format: str = 'text') -> str:
        """
        Export protocol in specified format.

        Args:
            setup_id: ReactionSetup ID
            format: 'text' or 'csv'

        Returns:
            Formatted protocol string
        """
        setup = ReactionSetup.query.get(setup_id)
        if not setup:
            raise ValueError(f"ReactionSetup {setup_id} not found")

        if format == 'csv':
            # Regenerate calculation for CSV export
            constructs = [
                {
                    'name': dna.construct_name,
                    'id': dna.construct_id,
                    'stock_concentration_ng_ul': dna.dna_stock_concentration_ng_ul or 100.0,
                }
                for dna in setup.dna_additions
                if not dna.is_negative_control
            ]

            n_reactions = (
                setup.n_reactions
                if setup.n_reactions is not None
                else (
                    (setup.n_constructs or 0) * (setup.n_replicates or 0)
                    + (setup.n_negative_template or 0)
                    + (setup.n_negative_dye or 0)
                )
            )
            mm = calculate_master_mix(
                n_reactions=n_reactions,
                dna_mass_ug=setup.dna_mass_ug,
                overage_percent=setup.overage_percent,
                constructs=constructs,
                negative_template_count=setup.n_negative_template,
                negative_dye_count=setup.n_negative_dye,
            )

            protocol = generate_protocol(mm, title=setup.name, created_by=setup.created_by)
            return format_protocol_csv(protocol)

        # Default to stored text
        return setup.protocol_text or ""
