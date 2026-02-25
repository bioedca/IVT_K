"""
Validation service for IVT Kinetics Analyzer.

Phase 9.6-9.7: Package validation (F15.14-F15.16)

Provides:
- Re-run analysis from package data
- Compare results against stored values
- Generate validation certificates
- Create diff reports on mismatch
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import hashlib
import math


@dataclass
class ValidationResult:
    """Result of a validation check."""
    parameter: str
    expected: float
    actual: float
    relative_error: float
    is_valid: bool
    tolerance: float
    details: str = ""


@dataclass
class ValidationCertificate:
    """Validation certificate for a publication package."""
    package_id: str
    validated_at: datetime
    is_valid: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: List[ValidationResult]
    software_version: str
    validator_hash: str  # Hash of validation code for reproducibility

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "package_id": self.package_id,
            "validated_at": self.validated_at.isoformat(),
            "is_valid": self.is_valid,
            "summary": {
                "total_checks": self.total_checks,
                "passed_checks": self.passed_checks,
                "failed_checks": self.failed_checks,
                "pass_rate": self.passed_checks / max(1, self.total_checks),
            },
            "results": [
                {
                    "parameter": r.parameter,
                    "expected": r.expected,
                    "actual": r.actual,
                    "relative_error": r.relative_error,
                    "is_valid": r.is_valid,
                    "tolerance": r.tolerance,
                    "details": r.details,
                }
                for r in self.results
            ],
            "software_version": self.software_version,
            "validator_hash": self.validator_hash,
        }


@dataclass
class DiffReport:
    """Diff report for validation failures."""
    generated_at: datetime
    package_id: str
    failed_validations: List[ValidationResult]
    summary: str

    def to_markdown(self) -> str:
        """Generate Markdown diff report."""
        lines = [
            "# Validation Diff Report",
            "",
            f"**Package ID**: {self.package_id}",
            f"**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            self.summary,
            "",
            "## Failed Validations",
            "",
            "| Parameter | Expected | Actual | Relative Error | Tolerance |",
            "|-----------|----------|--------|----------------|-----------|",
        ]

        for v in self.failed_validations:
            lines.append(
                f"| {v.parameter} | {v.expected:.6g} | {v.actual:.6g} | "
                f"{v.relative_error:.2e} | {v.tolerance:.2e} |"
            )

        lines.extend([
            "",
            "## Details",
            "",
        ])

        for v in self.failed_validations:
            if v.details:
                lines.append(f"### {v.parameter}")
                lines.append(f"{v.details}")
                lines.append("")

        return "\n".join(lines)


class ValidationService:
    """Service for validating publication packages."""

    # Default relative tolerance for numerical comparisons
    DEFAULT_TOLERANCE = 1e-4

    # Software version for certificate
    SOFTWARE_VERSION = "1.0.0"

    @staticmethod
    def compute_relative_error(expected: float, actual: float) -> float:
        """
        Compute relative error between expected and actual values.

        Args:
            expected: Expected value
            actual: Actual value

        Returns:
            Relative error (absolute value)
        """
        if expected == 0:
            return abs(actual) if actual != 0 else 0.0
        return abs((actual - expected) / expected)

    @staticmethod
    def validate_scalar(
        parameter: str,
        expected: float,
        actual: float,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> ValidationResult:
        """
        Validate a single scalar value.

        Args:
            parameter: Parameter name
            expected: Expected value
            actual: Actual value
            tolerance: Relative tolerance

        Returns:
            ValidationResult
        """
        # Handle NaN values
        if math.isnan(expected) and math.isnan(actual):
            return ValidationResult(
                parameter=parameter,
                expected=expected,
                actual=actual,
                relative_error=0.0,
                is_valid=True,
                tolerance=tolerance,
                details="Both values are NaN (considered equal)",
            )

        if math.isnan(expected) or math.isnan(actual):
            return ValidationResult(
                parameter=parameter,
                expected=expected,
                actual=actual,
                relative_error=float("inf"),
                is_valid=False,
                tolerance=tolerance,
                details="One value is NaN, the other is not",
            )

        relative_error = ValidationService.compute_relative_error(expected, actual)
        is_valid = relative_error <= tolerance

        return ValidationResult(
            parameter=parameter,
            expected=expected,
            actual=actual,
            relative_error=relative_error,
            is_valid=is_valid,
            tolerance=tolerance,
            details="" if is_valid else f"Error {relative_error:.2e} exceeds tolerance {tolerance:.2e}",
        )

    @staticmethod
    def validate_array(
        parameter: str,
        expected: List[float],
        actual: List[float],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> List[ValidationResult]:
        """
        Validate an array of values element-wise.

        Args:
            parameter: Parameter name prefix
            expected: Expected values
            actual: Actual values
            tolerance: Relative tolerance

        Returns:
            List of ValidationResults
        """
        results = []

        if len(expected) != len(actual):
            results.append(ValidationResult(
                parameter=f"{parameter}_length",
                expected=len(expected),
                actual=len(actual),
                relative_error=abs(len(expected) - len(actual)),
                is_valid=False,
                tolerance=0,
                details=f"Array length mismatch: {len(expected)} vs {len(actual)}",
            ))
            return results

        for i, (exp, act) in enumerate(zip(expected, actual)):
            result = ValidationService.validate_scalar(
                f"{parameter}[{i}]",
                exp,
                act,
                tolerance,
            )
            results.append(result)

        return results

    @staticmethod
    def validate_fitted_parameters(
        expected_params: List[Dict[str, Any]],
        actual_params: List[Dict[str, Any]],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> List[ValidationResult]:
        """
        Validate fitted kinetic parameters.

        Args:
            expected_params: Expected parameter dictionaries
            actual_params: Actual parameter dictionaries
            tolerance: Relative tolerance

        Returns:
            List of ValidationResults
        """
        results = []

        # Build lookup by well ID
        expected_lookup = {p.get("well_id", str(i)): p for i, p in enumerate(expected_params)}
        actual_lookup = {p.get("well_id", str(i)): p for i, p in enumerate(actual_params)}

        all_wells = set(expected_lookup.keys()) | set(actual_lookup.keys())

        for well_id in sorted(all_wells):
            if well_id not in expected_lookup:
                results.append(ValidationResult(
                    parameter=f"well_{well_id}",
                    expected=0,
                    actual=1,
                    relative_error=float("inf"),
                    is_valid=False,
                    tolerance=tolerance,
                    details=f"Well {well_id} present in actual but not expected",
                ))
                continue

            if well_id not in actual_lookup:
                results.append(ValidationResult(
                    parameter=f"well_{well_id}",
                    expected=1,
                    actual=0,
                    relative_error=float("inf"),
                    is_valid=False,
                    tolerance=tolerance,
                    details=f"Well {well_id} present in expected but not actual",
                ))
                continue

            exp = expected_lookup[well_id]
            act = actual_lookup[well_id]

            # Validate k_obs
            if "k_obs" in exp and "k_obs" in act:
                results.append(ValidationService.validate_scalar(
                    f"well_{well_id}_k_obs",
                    exp["k_obs"],
                    act["k_obs"],
                    tolerance,
                ))

            # Validate F_max
            if "f_max" in exp and "f_max" in act:
                results.append(ValidationService.validate_scalar(
                    f"well_{well_id}_f_max",
                    exp["f_max"],
                    act["f_max"],
                    tolerance,
                ))

            # Validate R²
            if "r_squared" in exp and "r_squared" in act:
                results.append(ValidationService.validate_scalar(
                    f"well_{well_id}_r_squared",
                    exp["r_squared"],
                    act["r_squared"],
                    tolerance,
                ))

        return results

    @staticmethod
    def validate_fold_changes(
        expected_fc: List[Dict[str, Any]],
        actual_fc: List[Dict[str, Any]],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> List[ValidationResult]:
        """
        Validate fold change estimates.

        Args:
            expected_fc: Expected fold change dictionaries
            actual_fc: Actual fold change dictionaries
            tolerance: Relative tolerance

        Returns:
            List of ValidationResults
        """
        results = []

        # Build lookup by construct name
        expected_lookup = {fc.get("construct"): fc for fc in expected_fc}
        actual_lookup = {fc.get("construct"): fc for fc in actual_fc}

        all_constructs = set(expected_lookup.keys()) | set(actual_lookup.keys())

        for construct in sorted(all_constructs):
            if construct is None:
                continue

            if construct not in expected_lookup:
                results.append(ValidationResult(
                    parameter=f"fc_{construct}",
                    expected=0,
                    actual=1,
                    relative_error=float("inf"),
                    is_valid=False,
                    tolerance=tolerance,
                    details=f"Construct {construct} present in actual but not expected",
                ))
                continue

            if construct not in actual_lookup:
                results.append(ValidationResult(
                    parameter=f"fc_{construct}",
                    expected=1,
                    actual=0,
                    relative_error=float("inf"),
                    is_valid=False,
                    tolerance=tolerance,
                    details=f"Construct {construct} present in expected but not actual",
                ))
                continue

            exp = expected_lookup[construct]
            act = actual_lookup[construct]

            # Validate mean fold change
            if "mean" in exp and "mean" in act:
                results.append(ValidationService.validate_scalar(
                    f"fc_{construct}_mean",
                    exp["mean"],
                    act["mean"],
                    tolerance,
                ))

            # Validate CI bounds
            for bound in ["ci_lower", "ci_upper"]:
                if bound in exp and bound in act:
                    results.append(ValidationService.validate_scalar(
                        f"fc_{construct}_{bound}",
                        exp[bound],
                        act[bound],
                        tolerance,
                    ))

        return results

    @staticmethod
    def validate_convergence_diagnostics(
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> List[ValidationResult]:
        """
        Validate MCMC convergence diagnostics.

        Args:
            expected: Expected convergence metrics
            actual: Actual convergence metrics
            tolerance: Relative tolerance

        Returns:
            List of ValidationResults
        """
        results = []

        # Validate R-hat values
        if "r_hat" in expected and "r_hat" in actual:
            exp_rhat = expected["r_hat"]
            act_rhat = actual["r_hat"]

            if isinstance(exp_rhat, dict) and isinstance(act_rhat, dict):
                for param in set(exp_rhat.keys()) | set(act_rhat.keys()):
                    if param in exp_rhat and param in act_rhat:
                        results.append(ValidationService.validate_scalar(
                            f"r_hat_{param}",
                            exp_rhat[param],
                            act_rhat[param],
                            tolerance,
                        ))

        # Validate ESS values
        if "ess" in expected and "ess" in actual:
            exp_ess = expected["ess"]
            act_ess = actual["ess"]

            if isinstance(exp_ess, dict) and isinstance(act_ess, dict):
                for param in set(exp_ess.keys()) | set(act_ess.keys()):
                    if param in exp_ess and param in act_ess:
                        results.append(ValidationService.validate_scalar(
                            f"ess_{param}",
                            exp_ess[param],
                            act_ess[param],
                            tolerance,
                        ))

        return results

    @staticmethod
    def validate_package(
        package_path: Path,
        rerun_results: Optional[Dict[str, Any]] = None,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> ValidationCertificate:
        """
        Validate a publication package.

        Args:
            package_path: Path to extracted package
            rerun_results: Optional re-run analysis results (if None, loads from package)
            tolerance: Relative tolerance for numerical comparisons

        Returns:
            ValidationCertificate
        """
        all_results = []

        # Load expected results from package
        processed_path = package_path / "processed"

        # Load fitted parameters
        fitted_params_path = processed_path / "fitted_parameters.csv"
        if fitted_params_path.exists():
            import csv
            with open(fitted_params_path, "r") as f:
                reader = csv.DictReader(f)
                expected_params = []
                for row in reader:
                    param = {
                        "well_id": row.get("well_id"),
                        "k_obs": float(row.get("k_obs", 0)),
                        "f_max": float(row.get("f_max", 0)),
                        "r_squared": float(row.get("r_squared", 0)),
                    }
                    expected_params.append(param)

            if rerun_results and "fitted_params" in rerun_results:
                results = ValidationService.validate_fitted_parameters(
                    expected_params,
                    rerun_results["fitted_params"],
                    tolerance,
                )
                all_results.extend(results)

        # Load fold changes
        fold_changes_path = processed_path / "fold_changes.csv"
        if fold_changes_path.exists():
            import csv
            with open(fold_changes_path, "r") as f:
                reader = csv.DictReader(f)
                expected_fc = []
                for row in reader:
                    fc = {
                        "construct": row.get("construct"),
                        "mean": float(row.get("mean", 0)),
                        "ci_lower": float(row.get("ci_lower", 0)),
                        "ci_upper": float(row.get("ci_upper", 0)),
                    }
                    expected_fc.append(fc)

            if rerun_results and "fold_changes" in rerun_results:
                results = ValidationService.validate_fold_changes(
                    expected_fc,
                    rerun_results["fold_changes"],
                    tolerance,
                )
                all_results.extend(results)

        # Load convergence diagnostics
        convergence_path = processed_path / "convergence_diagnostics.json"
        if convergence_path.exists():
            expected_conv = json.loads(convergence_path.read_text())

            if rerun_results and "convergence" in rerun_results:
                results = ValidationService.validate_convergence_diagnostics(
                    expected_conv,
                    rerun_results["convergence"],
                    tolerance,
                )
                all_results.extend(results)

        # Calculate summary
        passed = sum(1 for r in all_results if r.is_valid)
        failed = sum(1 for r in all_results if not r.is_valid)

        # Generate package ID from manifest
        manifest_path = package_path / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            package_id = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()[:16]
        else:
            package_id = "unknown"

        # Compute validator hash for reproducibility
        validator_hash = hashlib.sha256(
            f"ValidationService_v{ValidationService.SOFTWARE_VERSION}".encode()
        ).hexdigest()[:16]

        return ValidationCertificate(
            package_id=package_id,
            validated_at=datetime.now(),
            is_valid=failed == 0,
            total_checks=len(all_results),
            passed_checks=passed,
            failed_checks=failed,
            results=all_results,
            software_version=ValidationService.SOFTWARE_VERSION,
            validator_hash=validator_hash,
        )

    @staticmethod
    def generate_diff_report(
        certificate: ValidationCertificate,
    ) -> DiffReport:
        """
        Generate diff report for failed validations.

        Args:
            certificate: Validation certificate

        Returns:
            DiffReport
        """
        failed = [r for r in certificate.results if not r.is_valid]

        summary = (
            f"Validation found {certificate.failed_checks} failures "
            f"out of {certificate.total_checks} checks "
            f"({certificate.passed_checks / max(1, certificate.total_checks) * 100:.1f}% pass rate)."
        )

        return DiffReport(
            generated_at=datetime.now(),
            package_id=certificate.package_id,
            failed_validations=failed,
            summary=summary,
        )

    @staticmethod
    def generate_certificate_pdf(
        certificate: ValidationCertificate,
    ) -> bytes:
        """
        Generate PDF validation certificate.

        Args:
            certificate: Validation certificate

        Returns:
            PDF bytes
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            )
            from reportlab.lib import colors
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72,
            )

            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                'CertTitle',
                parent=styles['Heading1'],
                fontSize=20,
                spaceAfter=20,
                alignment=1,  # Center
            )
            story.append(Paragraph("Validation Certificate", title_style))
            story.append(Spacer(1, 20))

            # Status badge
            status_color = colors.green if certificate.is_valid else colors.red
            status_text = "VALID" if certificate.is_valid else "INVALID"
            status_style = ParagraphStyle(
                'Status',
                parent=styles['Heading2'],
                textColor=status_color,
                alignment=1,
            )
            story.append(Paragraph(f"Status: {status_text}", status_style))
            story.append(Spacer(1, 20))

            # Summary table
            summary_data = [
                ["Property", "Value"],
                ["Package ID", certificate.package_id],
                ["Validated At", certificate.validated_at.strftime("%Y-%m-%d %H:%M:%S")],
                ["Total Checks", str(certificate.total_checks)],
                ["Passed Checks", str(certificate.passed_checks)],
                ["Failed Checks", str(certificate.failed_checks)],
                ["Pass Rate", f"{certificate.passed_checks / max(1, certificate.total_checks) * 100:.1f}%"],
                ["Software Version", certificate.software_version],
                ["Validator Hash", certificate.validator_hash],
            ]

            summary_table = Table(summary_data, colWidths=[2.5*inch, 3*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))

            # Failed checks (if any)
            if certificate.failed_checks > 0:
                story.append(Paragraph("Failed Checks", styles['Heading2']))
                story.append(Spacer(1, 10))

                failed_data = [["Parameter", "Expected", "Actual", "Error"]]
                for r in certificate.results:
                    if not r.is_valid:
                        failed_data.append([
                            r.parameter[:30],  # Truncate long names
                            f"{r.expected:.4g}",
                            f"{r.actual:.4g}",
                            f"{r.relative_error:.2e}",
                        ])

                if len(failed_data) > 1:
                    failed_table = Table(failed_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
                    failed_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ]))
                    story.append(failed_table)

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            # Fallback to text if reportlab not available
            text = [
                "VALIDATION CERTIFICATE",
                "=" * 40,
                f"Status: {'VALID' if certificate.is_valid else 'INVALID'}",
                f"Package ID: {certificate.package_id}",
                f"Validated At: {certificate.validated_at.isoformat()}",
                f"Checks: {certificate.passed_checks}/{certificate.total_checks} passed",
                f"Software Version: {certificate.software_version}",
            ]
            return "\n".join(text).encode("utf-8")


class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass
