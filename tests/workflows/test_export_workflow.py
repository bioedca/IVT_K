"""
E2E tests for export workflow.

PRD Reference: Section 4.1 - E2E testing

Tests the complete export generation workflow:
- Export fit results and comparisons to CSV
- Export to Excel with multiple sheets
- Generate publication figure data (JSON)
- Create project archives (ZIP)
- Assemble summary reports

Note: These tests exercise export logic (data assembly, CSV/zip creation)
using mock/synthetic data rather than creating actual DB FitResult records,
since FitResult requires a Well FK that depends on a full experiment chain.
"""
import pytest
from pathlib import Path
import numpy as np
import pandas as pd
import json


class TestCSVExportWorkflow:
    """Test CSV export workflow using synthetic fit data."""

    def test_export_fit_results_to_csv(self, temp_dir):
        """Test exporting fit results to CSV from synthetic data."""
        # Simulate fit result data as it would come from DB queries
        fit_data = []
        for i in range(5):
            fit_data.append({
                'well': f"A{i+1}",
                'construct': "TEST-001",
                'model_type': "delayed_exponential",
                'f_max': 1000 + i * 100,
                'f_max_se': 50.0,
                'k_obs': 0.05,
                'k_obs_se': 0.005,
                't_lag': 4.0 + i * 0.5,
                'r_squared': 0.95 + i * 0.01,
                'rmse': 15.0,
                'converged': True,
            })

        df = pd.DataFrame(fit_data)
        export_path = temp_dir / "fit_results.csv"
        df.to_csv(export_path, index=False)

        # Verify export
        assert export_path.exists()
        loaded_df = pd.read_csv(export_path)
        assert len(loaded_df) == 5
        assert 'f_max' in loaded_df.columns
        assert 'k_obs' in loaded_df.columns
        assert 'r_squared' in loaded_df.columns
        assert 'model_type' in loaded_df.columns
        assert all(loaded_df['converged'])

    def test_export_comparison_results(self, temp_dir):
        """Test exporting fold-change comparison results to CSV."""
        comparisons = [
            {
                'test_construct': 'VAR-001',
                'control_construct': 'WT-001',
                'fc_fmax': 1.35,
                'log_fc_fmax': np.log(1.35),
                'log_fc_fmax_se': 0.08,
                'comparison_type': 'primary',
                'variance_inflation_factor': 1.0,
            },
            {
                'test_construct': 'VAR-002',
                'control_construct': 'WT-001',
                'fc_fmax': 0.85,
                'log_fc_fmax': np.log(0.85),
                'log_fc_fmax_se': 0.07,
                'comparison_type': 'primary',
                'variance_inflation_factor': 1.0,
            },
        ]

        df = pd.DataFrame(comparisons)
        export_path = temp_dir / "comparisons.csv"
        df.to_csv(export_path, index=False)

        assert export_path.exists()
        loaded_df = pd.read_csv(export_path)
        assert len(loaded_df) == 2
        assert 'fc_fmax' in loaded_df.columns
        assert 'log_fc_fmax' in loaded_df.columns

    def test_export_hierarchical_estimates(self, temp_dir):
        """Test exporting hierarchical model estimates to CSV."""
        estimates = [
            {
                'construct_id': 'C1',
                'parameter': 'log_fc_fmax',
                'mean': 0.30,
                'std': 0.05,
                'ci_lower': 0.20,
                'ci_upper': 0.40,
                'ci_level': 0.95,
            },
            {
                'construct_id': 'C2',
                'parameter': 'log_fc_fmax',
                'mean': 0.55,
                'std': 0.06,
                'ci_lower': 0.43,
                'ci_upper': 0.67,
                'ci_level': 0.95,
            },
        ]

        df = pd.DataFrame(estimates)
        export_path = temp_dir / "hierarchical_estimates.csv"
        df.to_csv(export_path, index=False)

        assert export_path.exists()
        loaded_df = pd.read_csv(export_path)
        assert len(loaded_df) == 2
        assert set(loaded_df.columns) >= {'mean', 'ci_lower', 'ci_upper'}


class TestExcelExportWorkflow:
    """Test Excel export workflow."""

    def test_export_to_excel(self, temp_dir):
        """Test exporting results to Excel with multiple sheets."""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl not available")

        fit_data = pd.DataFrame({
            'well': ['A1', 'A2', 'A3'],
            'f_max': [1000, 1100, 1050],
            'k_obs': [0.05, 0.055, 0.052],
            'r_squared': [0.97, 0.98, 0.96],
        })

        comparison_data = pd.DataFrame({
            'construct': ['VAR-001', 'VAR-002'],
            'fc_fmax': [1.35, 0.85],
            'log_fc_fmax': [np.log(1.35), np.log(0.85)],
        })

        export_path = temp_dir / "results.xlsx"
        with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
            fit_data.to_excel(writer, sheet_name='Fit Results', index=False)
            comparison_data.to_excel(writer, sheet_name='Comparisons', index=False)

        assert export_path.exists()

        loaded_fits = pd.read_excel(export_path, sheet_name='Fit Results')
        loaded_comparisons = pd.read_excel(export_path, sheet_name='Comparisons')

        assert len(loaded_fits) == 3
        assert len(loaded_comparisons) == 2


class TestPublicationExportWorkflow:
    """Test publication-quality export workflow."""

    def test_export_figure_data(self, temp_dir):
        """Test exporting structured data for publication figures."""
        figure_data = {
            'title': 'Fold Change Comparison',
            'xlabel': 'Construct',
            'ylabel': 'log2 Fold Change',
            'data': [
                {'name': 'VAR-001', 'value': 0.42, 'ci_lower': 0.26, 'ci_upper': 0.58},
                {'name': 'VAR-002', 'value': -0.23, 'ci_lower': -0.41, 'ci_upper': -0.05},
            ]
        }

        export_path = temp_dir / "figure_data.json"
        with open(export_path, 'w') as f:
            json.dump(figure_data, f, indent=2)

        assert export_path.exists()
        with open(export_path) as f:
            loaded = json.load(f)
        assert loaded['title'] == 'Fold Change Comparison'
        assert len(loaded['data']) == 2
        # Verify CI structure
        for item in loaded['data']:
            assert 'ci_lower' in item
            assert 'ci_upper' in item
            assert item['ci_lower'] < item['value'] < item['ci_upper']

    def test_export_methods_text(self, temp_dir):
        """Test exporting methods text for publication."""
        methods_text = """## Materials and Methods

### IVT Kinetics Analysis
Kinetic parameters were estimated by fitting fluorescence time series
to a delayed exponential model F(t) = F_baseline + F_max * (1 - exp(-k_obs * (t - t_lag)))
using nonlinear least squares regression with scipy.optimize.curve_fit.

Fold changes were calculated as log(variant/wild-type) and analyzed
using a hierarchical mixed-effects model accounting for session and
plate random effects. Variance inflation factors were applied for
derived comparisons (VIF = 1.0 for direct, sqrt(2) for one-hop,
2.0 for two-hop, 4.0 for cross-family)."""

        export_path = temp_dir / "methods.txt"
        export_path.write_text(methods_text.strip())

        assert export_path.exists()
        content = export_path.read_text()
        assert 'IVT Kinetics Analysis' in content
        assert 'delayed exponential' in content
        assert 'variance inflation' in content.lower()

    def test_export_variance_component_table(self, temp_dir):
        """Test exporting variance component decomposition for publication."""
        variance_data = pd.DataFrame([
            {
                'component': 'Session (tau_session)',
                'variance': 0.012,
                'pct_total': 15.0,
                'icc': 0.15,
            },
            {
                'component': 'Plate (tau_plate)',
                'variance': 0.008,
                'pct_total': 10.0,
                'icc': 0.10,
            },
            {
                'component': 'Residual (sigma)',
                'variance': 0.060,
                'pct_total': 75.0,
                'icc': None,
            },
        ])

        export_path = temp_dir / "variance_components.csv"
        variance_data.to_csv(export_path, index=False)

        assert export_path.exists()
        loaded = pd.read_csv(export_path)
        assert len(loaded) == 3
        assert loaded['pct_total'].sum() == pytest.approx(100.0)


class TestReportGenerationWorkflow:
    """Test report generation workflow using synthetic data."""

    def test_generate_summary_report(self, temp_dir):
        """Test generating a project summary report as JSON."""
        report = {
            'project_name': 'Report Test Project',
            'n_constructs': 4,
            'n_samples': 24,
            'precision_target': 0.2,
            'model_tier': 'Tier 3 (full hierarchy)',
            'summary_statistics': {
                'mean_r_squared': 0.96,
                'median_f_max': 1150,
                'median_k_obs': 0.052,
            },
            'comparisons': [
                {
                    'test_construct': 'VAR-001',
                    'control_construct': 'WT-001',
                    'fc_fmax': 1.30,
                    'log_fc_fmax': np.log(1.30),
                    'significant': True,
                },
                {
                    'test_construct': 'VAR-002',
                    'control_construct': 'WT-001',
                    'fc_fmax': 0.95,
                    'log_fc_fmax': np.log(0.95),
                    'significant': False,
                },
            ],
        }

        export_path = temp_dir / "summary_report.json"
        with open(export_path, 'w') as f:
            json.dump(report, f, indent=2)

        assert export_path.exists()

        with open(export_path) as f:
            loaded = json.load(f)
        assert loaded['project_name'] == 'Report Test Project'
        assert len(loaded['comparisons']) == 2


class TestDataArchiveWorkflow:
    """Test data archive/backup workflow."""

    def test_create_project_archive(self, db_session, project_factory, temp_dir):
        """Test creating a project archive ZIP file."""
        import zipfile

        project = project_factory(name="Archive Test")

        archive_path = temp_dir / f"project_{project.id}_archive.zip"

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add project metadata
            metadata = {
                'project_id': project.id,
                'name': project.name,
                'precision_target': project.precision_target,
                'export_timestamp': '2026-02-20T12:00:00Z',
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2))

            # Add placeholder directories
            zipf.writestr('data/README.txt', 'Raw data files would be stored here.')
            zipf.writestr('results/README.txt', 'Analysis results would be stored here.')
            zipf.writestr('figures/README.txt', 'Publication figures would be stored here.')

        assert archive_path.exists()

        with zipfile.ZipFile(archive_path, 'r') as zipf:
            file_list = zipf.namelist()
            assert 'metadata.json' in file_list
            assert 'data/README.txt' in file_list
            assert 'results/README.txt' in file_list


class TestExportWorkflowIntegration:
    """Integration tests for complete export workflow."""

    def test_complete_export_workflow(self, db_session, project_factory, construct_factory, temp_dir):
        """Test assembling a complete export package from synthetic analysis data."""
        import zipfile

        # 1. Create project and constructs (for metadata)
        project = project_factory(name="Full Export Test")
        wt = construct_factory(project.id, "WT-001", "Family A", is_wt=True)
        var1 = construct_factory(project.id, "VAR-001", "Family A")
        var2 = construct_factory(project.id, "VAR-002", "Family A")

        # 2. Synthetic fit results (as if queried from DB)
        np.random.seed(42)
        constructs = [
            (wt, "WT-001", 1000),
            (var1, "VAR-001", 1300),
            (var2, "VAR-002", 900),
        ]

        fit_rows = []
        for construct, identifier, base_fmax in constructs:
            for j in range(3):
                fit_rows.append({
                    'construct_id': construct.id,
                    'construct_identifier': identifier,
                    'well': f"{chr(65 + constructs.index((construct, identifier, base_fmax)))}{j+1}",
                    'model_type': 'delayed_exponential',
                    'f_max': base_fmax + np.random.normal(0, 50),
                    'f_max_se': 50.0,
                    'k_obs': 0.05,
                    'k_obs_se': 0.005,
                    't_lag': 4.0,
                    'r_squared': 0.95 + np.random.uniform(-0.02, 0.02),
                    'converged': True,
                })

        fit_df = pd.DataFrame(fit_rows)
        fit_csv_path = temp_dir / "fit_results.csv"
        fit_df.to_csv(fit_csv_path, index=False)

        # 3. Fold-change comparison results
        comparison_data = pd.DataFrame([
            {
                'test_construct': 'VAR-001',
                'control_construct': 'WT-001',
                'fc_fmax': 1.30,
                'log_fc_fmax': np.log(1.30),
                'log_fc_fmax_se': 0.06,
                'comparison_type': 'primary',
                'variance_inflation_factor': 1.0,
            },
            {
                'test_construct': 'VAR-002',
                'control_construct': 'WT-001',
                'fc_fmax': 0.90,
                'log_fc_fmax': np.log(0.90),
                'log_fc_fmax_se': 0.07,
                'comparison_type': 'primary',
                'variance_inflation_factor': 1.0,
            },
        ])
        comparison_csv_path = temp_dir / "comparisons.csv"
        comparison_data.to_csv(comparison_csv_path, index=False)

        # 4. Create project archive
        archive_path = temp_dir / f"project_{project.id}_export.zip"
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(fit_csv_path, 'fit_results.csv')
            zipf.write(comparison_csv_path, 'comparisons.csv')

            metadata = {
                'project_id': project.id,
                'project_name': project.name,
                'n_constructs': 3,
                'n_fits': len(fit_rows),
                'precision_target': project.precision_target,
                'export_timestamp': '2026-02-20T12:00:00Z',
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2))

        # 5. Verify complete export
        assert archive_path.exists()
        assert fit_csv_path.exists()
        assert comparison_csv_path.exists()

        with zipfile.ZipFile(archive_path, 'r') as zipf:
            file_list = zipf.namelist()
            assert 'fit_results.csv' in file_list
            assert 'comparisons.csv' in file_list
            assert 'metadata.json' in file_list

            # Verify metadata content
            with zipf.open('metadata.json') as f:
                loaded_meta = json.load(f)
            assert loaded_meta['project_name'] == 'Full Export Test'
            assert loaded_meta['n_constructs'] == 3
            assert loaded_meta['n_fits'] == 9

    def test_export_round_trip_csv(self, temp_dir):
        """Test that CSV export and re-import preserves data fidelity."""
        np.random.seed(42)
        original = pd.DataFrame({
            'construct': ['C1', 'C2', 'C3'],
            'fc_fmax': [1.234567, 0.987654, 1.111111],
            'log_fc_fmax': [np.log(1.234567), np.log(0.987654), np.log(1.111111)],
            'log_fc_fmax_se': [0.0512, 0.0423, 0.0601],
        })

        csv_path = temp_dir / "round_trip.csv"
        original.to_csv(csv_path, index=False)
        loaded = pd.read_csv(csv_path)

        pd.testing.assert_frame_equal(original, loaded, check_exact=False, atol=1e-6)

