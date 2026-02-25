"""
Hierarchical Model Validation for IVT Kinetics Analyzer.

Comprehensive validation rules for:
- Construct-level validation (flags, family constraints)
- WellAssignment (template) validation
- Well (instance) validation
- Plate-level validation (anchors, replicates, pairing)
- Pairing chain validation (Mutant → WT → Unregulated)
"""
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field


@dataclass
class HierarchicalValidationResult:
    """Result of a hierarchical validation check."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False
        
    def add_warning(self, msg: str):
        self.warnings.append(msg)
        
    def merge(self, other: "HierarchicalValidationResult"):
        """Merge another result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


# =============================================================================
# CONSTRUCT-LEVEL VALIDATION
# =============================================================================

def validate_construct(
    construct: Dict[str, Any],
    project_constructs: List[Dict[str, Any]],
    project: Dict[str, Any]
) -> HierarchicalValidationResult:
    """
    Validate a single construct against all construct-level rules.
    
    Args:
        construct: Dict with keys: id, is_unregulated, is_wildtype, family, family_id
        project_constructs: All constructs in the project
        project: Project dict with unregulated_construct_id
        
    Returns:
        HierarchicalValidationResult with errors/warnings
    """
    result = HierarchicalValidationResult()
    
    is_unreg = construct.get("is_unregulated", False)
    is_wt = construct.get("is_wildtype", False)
    family = construct.get("family", "")
    cid = construct.get("id")
    
    # Rule: is_unregulated and is_wildtype cannot both be true
    if is_unreg and is_wt:
        result.add_error(f"Construct {cid}: Cannot be both unregulated and wildtype")
    
    # === UNREGULATED CONSTRUCT RULES ===
    if is_unreg:
        # Must have family = 'universal'
        if family != "universal":
            result.add_error(f"Construct {cid}: Unregulated construct must have family='universal'")
        
        # Check uniqueness: only one unregulated per project
        unreg_in_project = [c for c in project_constructs if c.get("is_unregulated")]
        if len(unreg_in_project) > 1:
            result.add_error(f"Project has {len(unreg_in_project)} unregulated constructs (max 1)")
        
        # Project's unregulated_construct_id must match
        if project.get("unregulated_construct_id") != cid:
            result.add_warning(f"Project's unregulated_construct_id does not match construct {cid}")
    
    # === WILD-TYPE CONSTRUCT RULES ===
    if is_wt:
        # Cannot have family = 'universal'
        if family == "universal":
            result.add_error(f"Construct {cid}: Wild-type cannot have family='universal'")
        
        # Family must not be empty
        if not family:
            result.add_error(f"Construct {cid}: Wild-type must have a non-empty family")
        
        # Check uniqueness: exactly one WT per family
        wt_in_family = [c for c in project_constructs if c.get("is_wildtype") and c.get("family") == family]
        if len(wt_in_family) > 1:
            result.add_error(f"Family '{family}' has {len(wt_in_family)} wild-types (max 1)")
    
    # === MUTANT CONSTRUCT RULES ===
    if not is_unreg and not is_wt:
        # Cannot have family = 'universal'
        if family == "universal":
            result.add_error(f"Construct {cid}: Mutant cannot have family='universal'")
        
        # Family must not be empty
        if not family:
            result.add_error(f"Construct {cid}: Mutant must have a non-empty family")
        
        # Family must have a WT defined
        wt_exists = any(c.get("is_wildtype") and c.get("family") == family for c in project_constructs)
        if not wt_exists:
            result.add_error(f"Construct {cid}: No wild-type defined for family '{family}'")
    
    return result


def validate_project_constructs(
    project_constructs: List[Dict[str, Any]],
    project: Dict[str, Any]
) -> HierarchicalValidationResult:
    """Validate all constructs in a project."""
    result = HierarchicalValidationResult()
    
    for construct in project_constructs:
        r = validate_construct(construct, project_constructs, project)
        result.merge(r)
    
    # Project must have exactly one unregulated construct
    unreg_count = sum(1 for c in project_constructs if c.get("is_unregulated"))
    if unreg_count == 0:
        result.add_error("Project must have exactly one unregulated construct")
    elif unreg_count > 1:
        result.add_error(f"Project has {unreg_count} unregulated constructs (expected 1)")
    
    return result


# =============================================================================
# WELL ASSIGNMENT (TEMPLATE) VALIDATION
# =============================================================================

def validate_well_assignment(
    assignment: Dict[str, Any],
    all_assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> HierarchicalValidationResult:
    """
    Validate a single well assignment.
    
    Args:
        assignment: Dict with keys: position, well_type, construct_id, paired_with, family_id
        all_assignments: All assignments in the layout, keyed by position
        constructs_metadata: Construct info keyed by construct_id (as string)
    """
    result = HierarchicalValidationResult()
    
    pos = assignment.get("position", "?")
    well_type = assignment.get("well_type", "empty")
    construct_id = assignment.get("construct_id")
    paired_with = assignment.get("paired_with")
    replicate_group = assignment.get("replicate_group")
    
    # === EMPTY WELLS ===
    if well_type == "empty":
        if construct_id is not None:
            result.add_error(f"Well {pos}: Empty well cannot have construct_id")
        if paired_with is not None:
            result.add_error(f"Well {pos}: Empty well cannot have paired_with")
        if replicate_group is not None:
            result.add_error(f"Well {pos}: Empty well cannot have replicate_group")
    
    # === SAMPLE WELLS ===
    elif well_type == "sample":
        if construct_id is None:
            result.add_error(f"Well {pos}: Sample well must have construct_id")
        else:
            c_meta = constructs_metadata.get(str(construct_id), {})
            is_unreg = c_meta.get("is_unregulated", False)
            is_wt = c_meta.get("is_wildtype", False)
            family_id = c_meta.get("family_id")
            
            # Unregulated sample: paired_with must be null
            if is_unreg:
                if paired_with is not None:
                    result.add_error(f"Well {pos}: Unregulated sample must have paired_with=null")
            
            # Wild-type sample: paired_with must reference unregulated
            elif is_wt:
                if paired_with is None:
                    result.add_error(f"Well {pos}: Wild-type sample must be paired with unregulated")
                else:
                    paired_assignment = all_assignments.get(paired_with, {})
                    paired_cid = paired_assignment.get("construct_id")
                    if paired_cid:
                        paired_meta = constructs_metadata.get(str(paired_cid), {})
                        if not paired_meta.get("is_unregulated"):
                            result.add_error(f"Well {pos}: Wild-type must pair with unregulated well")
            
            # Mutant sample: paired_with must reference WT from same family
            else:
                if paired_with is None:
                    result.add_error(f"Well {pos}: Mutant sample must be paired with wild-type")
                else:
                    paired_assignment = all_assignments.get(paired_with, {})
                    paired_cid = paired_assignment.get("construct_id")
                    if paired_cid:
                        paired_meta = constructs_metadata.get(str(paired_cid), {})
                        if not paired_meta.get("is_wildtype"):
                            result.add_error(f"Well {pos}: Mutant must pair with wild-type well")
                        elif paired_meta.get("family_id") != family_id:
                            result.add_error(f"Well {pos}: Mutant must pair with wild-type from same family")
    
    # === BLANK / NEGATIVE CONTROL WELLS ===
    elif well_type in ["blank", "negative_control_no_template", "negative_control_no_dye"]:
        if construct_id is not None:
            result.add_error(f"Well {pos}: Control well cannot have construct_id")
        if paired_with is not None:
            result.add_error(f"Well {pos}: Control well cannot have paired_with")
    
    return result


def validate_layout_assignments(
    assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> HierarchicalValidationResult:
    """Validate all assignments in a layout."""
    result = HierarchicalValidationResult()
    
    for pos, assignment in assignments.items():
        r = validate_well_assignment(assignment, assignments, constructs_metadata)
        result.merge(r)
    
    return result


# =============================================================================
# PLATE-LEVEL VALIDATION
# =============================================================================

def validate_plate_requirements(
    assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> HierarchicalValidationResult:
    """
    Validate plate-level requirements.
    
    Args:
        assignments: All assignments in the layout
        constructs_metadata: Construct info keyed by construct_id
    """
    result = HierarchicalValidationResult()
    
    # Collect stats
    by_type: Dict[str, int] = {}
    by_role: Dict[str, int] = {}
    families_mutant: Set[int] = set()
    families_wt: Set[int] = set()
    unreg_wells: List[str] = []
    wt_wells_by_family: Dict[int, List[str]] = {}
    mutant_wells_by_family: Dict[int, List[str]] = {}
    
    for pos, assignment in assignments.items():
        wt = assignment.get("well_type", "empty")
        by_type[wt] = by_type.get(wt, 0) + 1
        
        construct_id = assignment.get("construct_id")
        if construct_id and wt == "sample":
            c_meta = constructs_metadata.get(str(construct_id), {})
            is_unreg = c_meta.get("is_unregulated", False)
            is_wt = c_meta.get("is_wildtype", False)
            family_id = c_meta.get("family_id")
            
            if is_unreg:
                by_role["unregulated"] = by_role.get("unregulated", 0) + 1
                unreg_wells.append(pos)
            elif is_wt:
                by_role["wildtype"] = by_role.get("wildtype", 0) + 1
                if family_id:
                    families_wt.add(family_id)
                    wt_wells_by_family.setdefault(family_id, []).append(pos)
            else:
                by_role["mutant"] = by_role.get("mutant", 0) + 1
                if family_id:
                    families_mutant.add(family_id)
                    mutant_wells_by_family.setdefault(family_id, []).append(pos)
    
    # === REQUIRED ANCHORS ===
    # At least 1 unregulated well
    if by_role.get("unregulated", 0) < 1:
        result.add_error("Plate must have at least 1 sample well with unregulated construct")
    
    # At least 2 NTC wells
    ntc_count = by_type.get("negative_control_no_template", 0)
    if ntc_count < 2:
        result.add_error(f"Plate must have at least 2 NTC wells (found {ntc_count})")
    
    # For each family with mutants, must have WT
    missing_wt = families_mutant - families_wt
    if missing_wt:
        result.add_error(f"Missing wild-type for {len(missing_wt)} families with mutants")
    
    # === UNREGULATED REPLICATE REQUIREMENTS ===
    unreg_count = len(unreg_wells)
    if unreg_count > 0 and unreg_count < 4:
        result.add_error(f"Unregulated must have at least 4 replicate wells (found {unreg_count})")
    
    # Unreg replicates >= max WT replicates
    if wt_wells_by_family:
        max_wt_reps = max(len(wells) for wells in wt_wells_by_family.values())
        if unreg_count < max_wt_reps:
            result.add_error(f"Unregulated replicates ({unreg_count}) must >= max WT replicates ({max_wt_reps})")
    
    # === PAIRING COMPLETENESS ===
    # Every mutant must have valid paired_with pointing to WT
    for family_id, mutant_positions in mutant_wells_by_family.items():
        for pos in mutant_positions:
            assignment = assignments.get(pos, {})
            paired_with = assignment.get("paired_with")
            if not paired_with:
                result.add_error(f"Mutant well {pos} has no paired wild-type")
            else:
                # Verify paired well is WT from same family
                paired_assignment = assignments.get(paired_with, {})
                paired_cid = paired_assignment.get("construct_id")
                if paired_cid:
                    paired_meta = constructs_metadata.get(str(paired_cid), {})
                    if not paired_meta.get("is_wildtype"):
                        result.add_error(f"Mutant well {pos} not paired with wild-type")
                    elif paired_meta.get("family_id") != family_id:
                        result.add_error(f"Mutant well {pos} paired with wrong family WT")
    
    # Every WT must have valid paired_with pointing to unregulated
    for family_id, wt_positions in wt_wells_by_family.items():
        for pos in wt_positions:
            assignment = assignments.get(pos, {})
            paired_with = assignment.get("paired_with")
            if not paired_with:
                result.add_error(f"Wild-type well {pos} has no paired unregulated")
            else:
                paired_assignment = assignments.get(paired_with, {})
                paired_cid = paired_assignment.get("construct_id")
                if paired_cid:
                    paired_meta = constructs_metadata.get(str(paired_cid), {})
                    if not paired_meta.get("is_unregulated"):
                        result.add_error(f"Wild-type well {pos} not paired with unregulated")
    
    # Unregulated must have paired_with = null
    for pos in unreg_wells:
        assignment = assignments.get(pos, {})
        if assignment.get("paired_with") is not None:
            result.add_error(f"Unregulated well {pos} must not be paired")
    
    # === REPLICATE BALANCE WARNINGS ===
    # Warning if any construct has < 3 replicates
    construct_counts: Dict[int, int] = {}
    for assignment in assignments.values():
        cid = assignment.get("construct_id")
        if cid:
            construct_counts[cid] = construct_counts.get(cid, 0) + 1
    
    for cid, count in construct_counts.items():
        if count < 3:
            result.add_warning(f"Construct {cid} has only {count} replicate wells (recommended >= 3)")
    
    return result


# =============================================================================
# PAIRING CHAIN VALIDATION
# =============================================================================

def validate_pairing_chain(
    assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> HierarchicalValidationResult:
    """
    Validate that all sample wells form a valid pairing chain to unregulated.
    
    Mutant -> WT -> Unregulated (null)
    """
    result = HierarchicalValidationResult()
    
    for pos, assignment in assignments.items():
        well_type = assignment.get("well_type", "empty")
        if well_type != "sample":
            continue
            
        construct_id = assignment.get("construct_id")
        if not construct_id:
            continue
            
        c_meta = constructs_metadata.get(str(construct_id), {})
        is_unreg = c_meta.get("is_unregulated", False)
        
        if is_unreg:
            # Unregulated is the chain terminus - must have null pairing
            if assignment.get("paired_with") is not None:
                result.add_error(f"Well {pos}: Unregulated must have paired_with=null")
        else:
            # Trace the chain to unregulated
            visited = {pos}
            current_pos = pos
            chain_valid = False
            
            for _ in range(10):  # Max 10 hops to prevent infinite loops
                current_assignment = assignments.get(current_pos, {})
                paired_with = current_assignment.get("paired_with")
                
                if paired_with is None:
                    # Chain ended without reaching unregulated
                    break
                
                if paired_with in visited:
                    result.add_error(f"Well {pos}: Circular pairing detected")
                    break
                
                visited.add(paired_with)
                paired_assignment = assignments.get(paired_with, {})
                paired_cid = paired_assignment.get("construct_id")
                
                if paired_cid:
                    paired_meta = constructs_metadata.get(str(paired_cid), {})
                    if paired_meta.get("is_unregulated"):
                        chain_valid = True
                        break
                
                current_pos = paired_with
            
            if not chain_valid:
                result.add_error(f"Well {pos}: Pairing chain does not reach unregulated anchor")
    
    return result


# =============================================================================
# FULL LAYOUT VALIDATION (combines all checks)
# =============================================================================

def validate_layout_full(
    assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> HierarchicalValidationResult:
    """
    Perform full validation of a plate layout.
    
    Combines:
    - Individual assignment validation
    - Plate-level requirements
    - Pairing chain validation
    """
    result = HierarchicalValidationResult()
    
    # Individual assignment validation
    r = validate_layout_assignments(assignments, constructs_metadata)
    result.merge(r)
    
    # Plate-level requirements
    r = validate_plate_requirements(assignments, constructs_metadata)
    result.merge(r)
    
    # Pairing chain validation
    r = validate_pairing_chain(assignments, constructs_metadata)
    result.merge(r)
    
    return result


# =============================================================================
# SUMMARY HELPER (for layout_callbacks integration)
# =============================================================================

def get_layout_validation_summary(
    assignments: Dict[str, Dict[str, Any]],
    constructs_metadata: Dict[str, Dict[str, Any]]
) -> Tuple[bool, List[str], List[str]]:
    """
    Get validation summary suitable for UI display.
    
    Returns:
        Tuple of (is_valid, errors_list, warnings_list)
    """
    result = validate_layout_full(assignments, constructs_metadata)
    return result.is_valid, result.errors, result.warnings
