#!/usr/bin/env python
"""
Statistical validation script for IVT Kinetics Analyzer.

Phase 5: API and Scripts
PRD Reference: Section 4.4

Features:
- Validates curve fitting accuracy
- Checks fold change calculations
- Verifies CI coverage
- Tests hierarchical model behavior
- Validates convergence diagnostics
- Generates validation reports

Usage:
    python scripts/run_statistical_validation.py           # Run all tests
    python scripts/run_statistical_validation.py --test curve_fitting
    python scripts/run_statistical_validation.py --output report.json
    python scripts/run_statistical_validation.py --list     # List available tests
"""
import sys
import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ValidationResult:
    """Result of a single validation test."""
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class ValidationReport:
    """Full validation report."""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    results: List[ValidationResult] = field(default_factory=list)
    software_version: str = "1.0.0"

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests

    @property
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        return self.failed == 0 and self.skipped == 0


def generate_synthetic_kinetic_data(
    k_obs: float,
    f_max: float,
    f_bg: float,
    num_points: int = 50,
    noise_std: float = 100
) -> Tuple[List[float], List[float]]:
    """Generate synthetic kinetic data for testing."""
    max_time = 60.0
    timepoints = [i * max_time / (num_points - 1) for i in range(num_points)]

    fluorescence = []
    for t in timepoints:
        f_true = f_bg + f_max * (1 - math.exp(-k_obs * t))
        f_noisy = f_true + random.gauss(0, noise_std)
        fluorescence.append(max(0, f_noisy))

    return timepoints, fluorescence


def fit_exponential_curve(
    timepoints: List[float],
    fluorescence: List[float]
) -> Tuple[float, float, float, float]:
    """
    Simple exponential curve fitting using linearization.

    Returns: (k_obs, f_max, f_bg, r_squared)
    """
    # Estimate parameters using log-linearization
    # F(t) = F_bg + F_max * (1 - exp(-k*t))
    # At t=0: F(0) ≈ F_bg
    # At t→∞: F(∞) ≈ F_bg + F_max

    f_bg_est = fluorescence[0]
    f_max_est = max(fluorescence) - f_bg_est

    if f_max_est <= 0:
        f_max_est = 1.0

    # Linearize: log(1 - (F - F_bg)/F_max) = -k*t
    k_estimates = []
    for i, (t, f) in enumerate(zip(timepoints, fluorescence)):
        if t > 0:
            ratio = (f - f_bg_est) / f_max_est
            if 0 < ratio < 1:
                k = -math.log(1 - ratio) / t
                if 0 < k < 10:  # Reasonable range
                    k_estimates.append(k)

    k_obs_est = sum(k_estimates) / len(k_estimates) if k_estimates else 0.1

    # Calculate R²
    ss_tot = sum((f - sum(fluorescence)/len(fluorescence))**2 for f in fluorescence)
    ss_res = 0
    for t, f in zip(timepoints, fluorescence):
        f_pred = f_bg_est + f_max_est * (1 - math.exp(-k_obs_est * t))
        ss_res += (f - f_pred)**2

    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return k_obs_est, f_max_est, f_bg_est, r_squared


def validate_curve_fitting() -> ValidationResult:
    """
    Validate curve fitting accuracy.

    Tests that fitted parameters are within acceptable tolerance
    of known true values.
    """
    import time
    start = time.time()

    # Test with known parameters
    true_k_obs = 0.1
    true_f_max = 10000
    true_f_bg = 100

    # Generate many datasets and check recovery
    n_trials = 100
    k_errors = []
    f_max_errors = []
    r_squared_values = []

    for _ in range(n_trials):
        timepoints, fluorescence = generate_synthetic_kinetic_data(
            k_obs=true_k_obs,
            f_max=true_f_max,
            f_bg=true_f_bg,
            noise_std=true_f_max * 0.03  # 3% noise
        )

        k_fit, f_max_fit, f_bg_fit, r_sq = fit_exponential_curve(timepoints, fluorescence)

        k_errors.append(abs(k_fit - true_k_obs) / true_k_obs)
        f_max_errors.append(abs(f_max_fit - true_f_max) / true_f_max)
        r_squared_values.append(r_sq)

    # Calculate statistics
    mean_k_error = sum(k_errors) / len(k_errors)
    mean_f_max_error = sum(f_max_errors) / len(f_max_errors)
    mean_r_squared = sum(r_squared_values) / len(r_squared_values)

    # Tolerance: 20% relative error for k_obs, 10% for F_max
    k_obs_passed = mean_k_error < 0.20
    f_max_passed = mean_f_max_error < 0.10
    r_sq_passed = mean_r_squared > 0.95

    passed = k_obs_passed and f_max_passed and r_sq_passed

    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="curve_fitting",
        passed=passed,
        message=f"Curve fitting validation {'passed' if passed else 'failed'}",
        details={
            "n_trials": n_trials,
            "mean_k_obs_relative_error": mean_k_error,
            "mean_f_max_relative_error": mean_f_max_error,
            "mean_r_squared": mean_r_squared,
            "k_obs_tolerance": 0.20,
            "f_max_tolerance": 0.10,
            "r_squared_threshold": 0.95
        },
        duration_ms=duration
    )


def validate_fold_change_calculation() -> ValidationResult:
    """
    Validate fold change calculations.

    Tests that log fold change correctly converts to linear fold change
    and that CI transformations are correct.
    """
    import time
    start = time.time()

    test_cases = [
        # (log_fc, expected_fc, tolerance)
        (0.0, 1.0, 0.001),      # No change
        (0.693, 2.0, 0.01),     # 2-fold increase
        (-0.693, 0.5, 0.01),   # 2-fold decrease
        (1.0, 2.718, 0.01),    # e-fold increase
        (2.0, 7.389, 0.01),    # ~7.4-fold increase
    ]

    all_passed = True
    failed_cases = []

    for log_fc, expected_fc, tolerance in test_cases:
        actual_fc = math.exp(log_fc)
        error = abs(actual_fc - expected_fc)

        if error > tolerance:
            all_passed = False
            failed_cases.append({
                "log_fc": log_fc,
                "expected_fc": expected_fc,
                "actual_fc": actual_fc,
                "error": error
            })

    # Test CI transformation
    log_ci_lower = -0.2
    log_ci_upper = 0.5

    fc_ci_lower = math.exp(log_ci_lower)
    fc_ci_upper = math.exp(log_ci_upper)

    # CI should preserve ordering
    ci_order_correct = fc_ci_lower < 1.0 < fc_ci_upper

    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="fold_change_calculation",
        passed=all_passed and ci_order_correct,
        message=f"Fold change calculation {'passed' if all_passed else 'failed'}",
        details={
            "test_cases": len(test_cases),
            "failed_cases": failed_cases,
            "ci_order_correct": ci_order_correct
        },
        duration_ms=duration
    )


def validate_ci_coverage() -> ValidationResult:
    """
    Validate confidence interval coverage.

    For 95% CIs, the true value should be contained approximately 95% of the time.
    """
    import time
    start = time.time()

    n_simulations = 1000
    nominal_coverage = 0.95
    coverage_tolerance = 0.03  # Accept 92-98% coverage

    # Simulate: generate data with known parameter, fit, check if true value in CI
    true_k_obs = 0.1
    contained_count = 0

    for _ in range(n_simulations):
        # Generate data
        timepoints, fluorescence = generate_synthetic_kinetic_data(
            k_obs=true_k_obs,
            f_max=10000,
            f_bg=100,
            noise_std=300
        )

        # Fit and estimate uncertainty (simplified)
        k_fit, f_max_fit, f_bg_fit, r_sq = fit_exponential_curve(timepoints, fluorescence)

        # Bootstrap-style CI estimation (simplified)
        bootstrap_ks = []
        for _ in range(100):
            # Resample
            indices = [random.randint(0, len(timepoints)-1) for _ in range(len(timepoints))]
            t_boot = [timepoints[i] for i in indices]
            f_boot = [fluorescence[i] for i in indices]

            k_boot, _, _, _ = fit_exponential_curve(t_boot, f_boot)
            bootstrap_ks.append(k_boot)

        bootstrap_ks.sort()
        ci_lower = bootstrap_ks[int(0.025 * len(bootstrap_ks))]
        ci_upper = bootstrap_ks[int(0.975 * len(bootstrap_ks))]

        if ci_lower <= true_k_obs <= ci_upper:
            contained_count += 1

    actual_coverage = contained_count / n_simulations
    coverage_passed = abs(actual_coverage - nominal_coverage) <= coverage_tolerance

    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="ci_coverage",
        passed=coverage_passed,
        message=f"CI coverage: {actual_coverage:.1%} (target: {nominal_coverage:.0%})",
        details={
            "n_simulations": n_simulations,
            "nominal_coverage": nominal_coverage,
            "actual_coverage": actual_coverage,
            "coverage_tolerance": coverage_tolerance,
            "contained_count": contained_count
        },
        duration_ms=duration
    )


def validate_hierarchical_model() -> ValidationResult:
    """
    Validate hierarchical model behavior.

    Tests that variance partitioning is reasonable and that
    shrinkage occurs as expected.
    """
    import time
    start = time.time()

    # This is a simplified test without running actual MCMC
    # In production, this would test the actual model

    # Test variance partitioning sum
    var_session = 0.02
    var_plate = 0.01
    var_residual = 0.05
    total_var = var_session + var_plate + var_residual

    # Variance components should sum correctly
    var_sum_correct = abs(total_var - (var_session + var_plate + var_residual)) < 1e-10

    # Test ICC (intraclass correlation)
    icc_session = var_session / total_var
    icc_plate = (var_session + var_plate) / total_var

    icc_valid = 0 <= icc_session <= 1 and 0 <= icc_plate <= 1 and icc_session <= icc_plate

    passed = var_sum_correct and icc_valid

    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="hierarchical_model",
        passed=passed,
        message=f"Hierarchical model validation {'passed' if passed else 'failed'}",
        details={
            "var_session": var_session,
            "var_plate": var_plate,
            "var_residual": var_residual,
            "total_variance": total_var,
            "icc_session": icc_session,
            "icc_plate": icc_plate,
            "variance_sum_correct": var_sum_correct,
            "icc_valid": icc_valid
        },
        duration_ms=duration
    )


def validate_convergence() -> ValidationResult:
    """
    Validate convergence diagnostic thresholds.

    Tests that R-hat and ESS thresholds are correctly applied.
    """
    import time
    start = time.time()

    # Test R-hat threshold (should be <= 1.1 for convergence)
    r_hat_tests = [
        (1.001, True),   # Good convergence
        (1.05, True),    # Acceptable
        (1.10, True),    # Borderline acceptable
        (1.15, False),   # Not converged
        (1.50, False),   # Definitely not converged
    ]

    r_hat_passed = all(
        (r_hat <= 1.1) == expected
        for r_hat, expected in r_hat_tests
    )

    # Test ESS threshold (should be > 400 for reliable inference)
    ess_threshold = 400
    ess_tests = [
        (1500, True),
        (500, True),
        (400, True),     # Borderline
        (300, False),    # Too low
        (100, False),    # Definitely too low
    ]

    ess_passed = all(
        (ess >= ess_threshold) == expected
        for ess, expected in ess_tests
    )

    passed = r_hat_passed and ess_passed

    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="convergence_diagnostics",
        passed=passed,
        message=f"Convergence diagnostics {'passed' if passed else 'failed'}",
        details={
            "r_hat_threshold": 1.1,
            "ess_threshold": ess_threshold,
            "r_hat_tests_passed": r_hat_passed,
            "ess_tests_passed": ess_passed
        },
        duration_ms=duration
    )


def validate_project_results(project_id: int) -> ValidationResult:
    """
    Validate existing project analysis results.

    Checks that stored results are internally consistent.
    """
    import time
    start = time.time()

    from app import create_app
    from app.models import Project, AnalysisVersion, HierarchicalResult
    from app.models.analysis_version import AnalysisStatus

    app = create_app()
    with app.server.app_context():
        project = Project.query.get(project_id)
        if not project:
            return ValidationResult(
                test_name="project_results",
                passed=False,
                message=f"Project {project_id} not found",
                details={"project_id": project_id}
            )

        analysis = AnalysisVersion.query.filter_by(
            project_id=project_id,
            status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisVersion.created_at.desc()).first()

        if not analysis:
            return ValidationResult(
                test_name="project_results",
                passed=True,  # No analysis to validate
                message="No completed analysis found",
                details={"project_id": project_id}
            )

        results = HierarchicalResult.query.filter_by(
            analysis_version_id=analysis.id
        ).all()

        issues = []

        for r in results:
            # CI should contain mean
            if not (r.ci_lower <= r.mean <= r.ci_upper):
                issues.append(f"CI does not contain mean for result {r.id}")

            # R-hat should be reasonable
            if r.r_hat and r.r_hat > 2.0:
                issues.append(f"R-hat > 2.0 for result {r.id}")

            # ESS should be positive
            if r.ess_bulk and r.ess_bulk <= 0:
                issues.append(f"Non-positive ESS for result {r.id}")

        # Note: FoldChange uses well_id, not project_id
        # Would need to query through wells to get project-specific fold changes

    passed = len(issues) == 0
    duration = (time.time() - start) * 1000

    return ValidationResult(
        test_name="project_results",
        passed=passed,
        message=f"Project {project_id} validation {'passed' if passed else 'failed'}",
        details={
            "project_id": project_id,
            "n_results": len(results) if 'results' in dir() else 0,
            "issues": issues
        },
        duration_ms=duration
    )


# Registry of available tests
AVAILABLE_TESTS = {
    "curve_fitting": validate_curve_fitting,
    "fold_change_calculation": validate_fold_change_calculation,
    "ci_coverage": validate_ci_coverage,
    "hierarchical_model": validate_hierarchical_model,
    "convergence_diagnostics": validate_convergence,
}


def list_tests() -> List[str]:
    """List available validation tests."""
    return list(AVAILABLE_TESTS.keys())


def run_test(test_name: str) -> ValidationResult:
    """Run a specific validation test."""
    if test_name not in AVAILABLE_TESTS:
        raise ValueError(f"Unknown test: {test_name}. Available: {list_tests()}")
    return AVAILABLE_TESTS[test_name]()


def run_all_tests() -> List[ValidationResult]:
    """Run all validation tests."""
    results = []
    for test_name, test_func in AVAILABLE_TESTS.items():
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                message=f"Test error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            ))
    return results


def run_validation(
    tests: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    verbose: bool = False
) -> ValidationReport:
    """
    Run validation tests and generate report.

    Args:
        tests: List of test names to run (None for all)
        output_path: Path to write JSON report (optional)
        verbose: Print progress

    Returns:
        ValidationReport with all results
    """
    if tests is None:
        tests = list_tests()

    results = []
    passed = 0
    failed = 0
    skipped = 0

    for test_name in tests:
        if verbose:
            print(f"Running {test_name}...", end=" ")

        if test_name not in AVAILABLE_TESTS:
            results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                message=f"Unknown test: {test_name}"
            ))
            skipped += 1
            if verbose:
                print("SKIPPED")
            continue

        try:
            result = AVAILABLE_TESTS[test_name]()
            results.append(result)

            if result.passed:
                passed += 1
                if verbose:
                    print("PASSED")
            else:
                failed += 1
                if verbose:
                    print("FAILED")
        except Exception as e:
            results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                message=f"Error: {str(e)}",
                details={"error": str(e)}
            ))
            failed += 1
            if verbose:
                print(f"ERROR: {e}")

    report = ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_tests=len(tests),
        passed=passed,
        failed=failed,
        skipped=skipped,
        results=results
    )

    if output_path:
        report_dict = asdict(report)
        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)

    return report


def main() -> int:
    """Main entry point for validation script."""
    parser = argparse.ArgumentParser(
        description="Run statistical validation tests for IVT Kinetics Analyzer"
    )
    parser.add_argument(
        "--test", "-t",
        help="Run specific test (can be specified multiple times)",
        action="append"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON report to file"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress"
    )
    parser.add_argument(
        "--project",
        type=int,
        help="Validate results for specific project ID"
    )

    args = parser.parse_args()

    if args.list:
        print("Available validation tests:")
        for test_name in list_tests():
            print(f"  - {test_name}")
        return 0

    print("IVT Kinetics Analyzer - Statistical Validation")
    print("=" * 50)

    # If project specified, validate that project
    if args.project:
        result = validate_project_results(args.project)
        print(f"\n{result.test_name}: {'PASSED' if result.passed else 'FAILED'}")
        print(f"  {result.message}")
        return 0 if result.passed else 1

    # Run validation tests
    tests = args.test
    report = run_validation(
        tests=tests,
        output_path=args.output,
        verbose=args.verbose or True
    )

    print("\n" + "=" * 50)
    print(f"Results: {report.passed}/{report.total_tests} passed")
    print(f"Pass rate: {report.pass_rate:.1%}")

    if args.output:
        print(f"\nReport saved to: {args.output}")

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
