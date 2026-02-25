"""
Methods text generation service for IVT Kinetics Analyzer.

Phase 8.8-8.9: Auto-generated methods text (F13.17-F13.18)

Generates publication-ready methods sections with actual values
from the analysis configuration and results.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MethodsTextConfig:
    """Configuration for methods text generation."""

    # Analysis parameters
    n_samples: int = 4000
    n_chains: int = 4
    n_warmup: int = 1000
    target_accept: float = 0.8

    # Model specification
    model_type: str = "hierarchical_bayesian"
    prior_type: str = "weakly_informative"

    # Data collection
    n_constructs: int = 0
    n_plates: int = 0
    n_wells: int = 0
    n_sessions: int = 0
    n_families: int = 0

    # Curve fitting
    equation: str = "F(t) = F_max × (1 - e^(-k_obs × t))"
    fitting_method: str = "nonlinear_least_squares"
    fitting_algorithm: str = "Levenberg-Marquardt"
    convergence_threshold: float = 1e-6
    max_iterations: int = 1000

    # Quality thresholds
    r_squared_threshold: float = 0.95
    convergence_threshold_mcmc: float = 1.1  # R-hat
    ess_threshold: int = 400

    # Statistical analysis
    ci_level: float = 0.95
    precision_target: float = 0.3  # log2 units

    # Reference constructs
    has_unregulated: bool = True
    wt_constructs: List[str] = None

    # Software versions
    software_name: str = "IVT Kinetics Analyzer"
    software_version: str = "1.0.0"
    stan_version: str = "2.26.0"

    def __post_init__(self):
        if self.wt_constructs is None:
            self.wt_constructs = []


class MethodsTextService:
    """Service for generating publication-ready methods text."""

    @staticmethod
    def generate_data_collection_section(config: MethodsTextConfig) -> str:
        """
        Generate methods text for data collection.

        Args:
            config: Methods text configuration

        Returns:
            Formatted methods paragraph
        """
        text = (
            f"Kinetic measurements were collected for {config.n_constructs} constructs "
            f"across {config.n_plates} plates and {config.n_sessions} independent sessions. "
            f"A total of {config.n_wells} wells were analyzed. "
        )

        if config.has_unregulated:
            text += (
                "An unregulated reference construct was included on all plates "
                "to enable cross-plate normalization and cross-family comparisons. "
            )

        if config.wt_constructs:
            text += (
                f"Wild-type references ({', '.join(config.wt_constructs)}) were included "
                f"for each protein family to anchor within-family fold change calculations. "
            )

        return text

    @staticmethod
    def generate_curve_fitting_section(config: MethodsTextConfig) -> str:
        """
        Generate methods text for curve fitting.

        Args:
            config: Methods text configuration

        Returns:
            Formatted methods paragraph
        """
        text = (
            f"Reaction progress curves were fit to the first-order kinetic model "
            f"{config.equation} using {config.fitting_method.replace('_', ' ')} "
            f"with the {config.fitting_algorithm} algorithm. "
            f"Convergence was defined as parameter changes < {config.convergence_threshold:.0e} "
            f"over {config.max_iterations} maximum iterations. "
            f"Fits with R² < {config.r_squared_threshold:.2f} were flagged for review. "
        )

        text += (
            "Observed rate constants (k_obs) were log₂-transformed prior to "
            "statistical analysis to achieve approximate normality and enable "
            "interpretation of differences as fold changes."
        )

        return text

    @staticmethod
    def generate_statistical_analysis_section(config: MethodsTextConfig) -> str:
        """
        Generate methods text for statistical analysis.

        Args:
            config: Methods text configuration

        Returns:
            Formatted methods paragraph
        """
        text = (
            f"Statistical analysis employed a {config.model_type.replace('_', ' ')} model "
            f"implemented in Stan (version {config.stan_version}). "
            f"The model accounts for batch effects at the plate and session levels "
            f"while estimating construct-level activity. "
        )

        text += (
            f"Markov Chain Monte Carlo sampling used {config.n_chains} chains "
            f"with {config.n_warmup} warmup iterations and {config.n_samples} sampling iterations "
            f"per chain (target acceptance rate = {config.target_accept}). "
        )

        text += (
            f"Convergence was assessed using the R-hat statistic (threshold < {config.convergence_threshold_mcmc:.2f}) "
            f"and effective sample size (ESS > {config.ess_threshold}). "
        )

        text += (
            f"Posterior {int(config.ci_level * 100)}% credible intervals were used "
            f"for inference, with precision targets of ±{config.precision_target} log₂ units "
            f"(approximately ±{(2**config.precision_target - 1) * 100:.0f}% fold change). "
        )

        # Variance inflation factor explanation
        text += (
            "Variance inflation factors (VIF) were calculated to quantify precision loss "
            "for indirect comparisons: VIF = 1.0 for same-plate comparisons, "
            "VIF = √2 for one-hop comparisons through a common reference, "
            "VIF = 2.0 for two-hop comparisons, and VIF = 4.0 for cross-family comparisons."
        )

        return text

    @staticmethod
    def generate_software_section(config: MethodsTextConfig) -> str:
        """
        Generate methods text for software attribution.

        Args:
            config: Methods text configuration

        Returns:
            Formatted methods paragraph
        """
        text = (
            f"All analyses were performed using {config.software_name} "
            f"(version {config.software_version}). "
            "The software implements curve fitting, hierarchical Bayesian modeling, "
            "and power analysis for IVT kinetic assays. "
            "Complete analysis settings and reproducibility manifests are available "
            "in the supplementary materials."
        )

        return text

    @staticmethod
    def generate_full_methods(
        config: MethodsTextConfig,
        include_software: bool = True,
    ) -> str:
        """
        Generate complete methods section.

        Args:
            config: Methods text configuration
            include_software: Whether to include software attribution

        Returns:
            Complete formatted methods section
        """
        sections = [
            "**Data Collection**\n",
            MethodsTextService.generate_data_collection_section(config),
            "\n\n**Curve Fitting**\n",
            MethodsTextService.generate_curve_fitting_section(config),
            "\n\n**Statistical Analysis**\n",
            MethodsTextService.generate_statistical_analysis_section(config),
        ]

        if include_software:
            sections.extend([
                "\n\n**Software**\n",
                MethodsTextService.generate_software_section(config),
            ])

        return "".join(sections)

    @staticmethod
    def generate_methods_from_analysis(
        analysis_result: Dict[str, Any],
        project_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate methods text from analysis results.

        Args:
            analysis_result: Results from hierarchical analysis
            project_info: Optional project metadata

        Returns:
            Complete formatted methods section
        """
        config = MethodsTextConfig()

        # Extract values from analysis result
        if "mcmc_config" in analysis_result:
            mcmc = analysis_result["mcmc_config"]
            config.n_samples = mcmc.get("n_samples", 4000)
            config.n_chains = mcmc.get("n_chains", 4)
            config.n_warmup = mcmc.get("n_warmup", 1000)
            config.target_accept = mcmc.get("target_accept", 0.8)

        if "data_summary" in analysis_result:
            data = analysis_result["data_summary"]
            config.n_constructs = data.get("n_constructs", 0)
            config.n_plates = data.get("n_plates", 0)
            config.n_wells = data.get("n_wells", 0)
            config.n_sessions = data.get("n_sessions", 0)
            config.n_families = data.get("n_families", 0)

        if "convergence" in analysis_result:
            conv = analysis_result["convergence"]
            config.convergence_threshold_mcmc = conv.get("r_hat_threshold", 1.1)
            config.ess_threshold = conv.get("ess_threshold", 400)

        if "reference_constructs" in analysis_result:
            refs = analysis_result["reference_constructs"]
            config.has_unregulated = refs.get("has_unregulated", True)
            config.wt_constructs = refs.get("wt_names", [])

        if project_info:
            config.software_version = project_info.get("software_version", "1.0.0")

        return MethodsTextService.generate_full_methods(config)

    @staticmethod
    def generate_latex_methods(config: MethodsTextConfig) -> str:
        """
        Generate LaTeX-formatted methods section.

        Args:
            config: Methods text configuration

        Returns:
            LaTeX-formatted methods text
        """
        sections = MethodsTextService.generate_full_methods(config)

        # Convert markdown to LaTeX
        latex = sections.replace("**", "\\textbf{")

        # Close bold tags properly
        import re
        latex = re.sub(r'\\textbf\{([^}]+)\}', r'\\textbf{\1}', latex)

        # Convert subscripts
        latex = latex.replace("k_obs", "$k_{obs}$")
        latex = latex.replace("F_max", "$F_{max}$")
        latex = latex.replace("log₂", "$\\log_2$")
        latex = latex.replace("R²", "$R^2$")
        latex = latex.replace("√2", "$\\sqrt{2}$")
        latex = latex.replace("±", "$\\pm$")

        return latex

    @staticmethod
    def generate_citation() -> str:
        """
        Generate citation text for the software.

        Returns:
            Citation text
        """
        return (
            "IVT Kinetics Analyzer: A tool for hierarchical Bayesian analysis "
            "of in vitro transcription kinetics data. Available at: "
            "[URL]. Accessed: " + datetime.now().strftime("%Y-%m-%d") + "."
        )


    # =========================================================================
    # Sprint 4: Methods Text Diff Tracking (F13.17, Task 8.3)
    # =========================================================================

    @staticmethod
    def save_with_diff(
        project_id: int,
        user_edited_text: str,
        edited_by: str = "current_user",
    ) -> Dict[str, Any]:
        """
        Save user-edited methods text with diff tracking.

        PRD Reference: Section 0.9, F13.17

        Args:
            project_id: Project ID
            user_edited_text: The edited methods text
            edited_by: Username of the editor

        Returns:
            Dict with save result and diff info
        """
        import difflib
        from app.models.methods_text import MethodsText
        from app.extensions import db

        # Get existing record or generate new original
        record = MethodsText.query.filter_by(project_id=project_id).first()

        if record:
            original_text = record.original_text
        else:
            # Need to generate original text from project data
            # This would normally pull from analysis results
            original_text = user_edited_text  # Fallback if no original exists

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            original_text.splitlines(keepends=True),
            user_edited_text.splitlines(keepends=True),
            fromfile='auto-generated',
            tofile='user-edited',
            lineterm=''
        ))
        diff_text = '\n'.join(diff_lines) if diff_lines else None

        # Calculate diff statistics
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        if record:
            # Update existing record
            record.edited_text = user_edited_text
            record.diff_text = diff_text
            record.edited_at = datetime.now()
            record.edited_by = edited_by
        else:
            # Create new record
            record = MethodsText(
                project_id=project_id,
                original_text=original_text,
                edited_text=user_edited_text,
                diff_text=diff_text,
                edited_at=datetime.now(),
                edited_by=edited_by,
            )
            db.session.add(record)

        db.session.commit()

        return {
            'success': True,
            'was_modified': diff_text is not None and len(diff_text) > 0,
            'additions': additions,
            'deletions': deletions,
            'diff_preview': diff_text[:500] if diff_text else None,
        }

    @staticmethod
    def get_methods_for_export(
        project_id: int,
        include_diff: bool = True,
    ) -> Dict[str, Any]:
        """
        Get methods text for export, with diff visible if edited.

        PRD Reference: Section 0.9, F13.17

        Args:
            project_id: Project ID
            include_diff: Whether to include diff in export

        Returns:
            Dict with text, was_edited flag, and optional diff
        """
        from app.models.methods_text import MethodsText

        record = MethodsText.query.filter_by(project_id=project_id).first()

        if not record:
            # Generate default methods text
            return {
                'text': '',
                'was_edited': False,
                'has_record': False,
            }

        was_edited = record.original_text != record.edited_text

        result = {
            'text': record.edited_text,
            'was_edited': was_edited,
            'has_record': True,
        }

        if was_edited and include_diff:
            result['diff'] = record.diff_text
            result['original'] = record.original_text
            result['edited_at'] = record.edited_at.isoformat() if record.edited_at else None
            result['edited_by'] = record.edited_by

        return result

    @staticmethod
    def generate_and_save_original(
        project_id: int,
        analysis_result: Dict[str, Any],
        project_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate methods text from analysis and save as original.

        Args:
            project_id: Project ID
            analysis_result: Results from hierarchical analysis
            project_info: Optional project metadata

        Returns:
            Dict with the generated text and save status
        """
        from app.models.methods_text import MethodsText
        from app.extensions import db

        # Generate the methods text
        text = MethodsTextService.generate_methods_from_analysis(
            analysis_result, project_info
        )

        # Check for existing record
        record = MethodsText.query.filter_by(project_id=project_id).first()

        if record:
            # Update original (but preserve edits if any)
            record.original_text = text
            if not record.edited_at:
                # If never edited, update edited_text too
                record.edited_text = text
                record.diff_text = None
        else:
            # Create new record
            record = MethodsText(
                project_id=project_id,
                original_text=text,
                edited_text=text,
                diff_text=None,
            )
            db.session.add(record)

        db.session.commit()

        return {
            'success': True,
            'text': text,
            'project_id': project_id,
        }

    @staticmethod
    def format_diff_for_display(diff_text: str) -> List[Dict[str, Any]]:
        """
        Format unified diff for UI display.

        Args:
            diff_text: Unified diff string

        Returns:
            List of dicts with line info for display
        """
        if not diff_text:
            return []

        lines = []
        for line in diff_text.split('\n'):
            if line.startswith('+++') or line.startswith('---'):
                line_type = 'header'
                color = 'gray'
            elif line.startswith('@@'):
                line_type = 'range'
                color = 'blue'
            elif line.startswith('+'):
                line_type = 'addition'
                color = 'green'
            elif line.startswith('-'):
                line_type = 'deletion'
                color = 'red'
            else:
                line_type = 'context'
                color = 'gray'

            lines.append({
                'text': line,
                'type': line_type,
                'color': color,
            })

        return lines


class MethodsTextError(Exception):
    """Exception raised for methods text generation errors."""
    pass
