"""Data export service for IVT Kinetics Analyzer.

Phase 3: Service Layer Decomposition
Handles data export in multiple formats (CSV, JSON, Excel, ZIP archive)
and publication package data retrieval from the database.
Extracted from ExportService to follow single-responsibility principle.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from io import BytesIO, StringIO
import json
import csv
import zipfile


class DataExportService:
    """Service for exporting data as CSV, JSON, Excel, and retrieving publication data."""

    @staticmethod
    def export_data_csv(
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> str:
        """
        Export data as CSV.

        Args:
            data: List of dictionaries to export
            columns: Optional column order

        Returns:
            CSV string
        """
        if not data:
            return ""

        output = StringIO()

        if columns is None:
            columns = list(data[0].keys())

        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

        return output.getvalue()

    @staticmethod
    def export_data_json(
        data: Any,
        indent: int = 2,
    ) -> str:
        """
        Export data as JSON.

        Args:
            data: Data to export (must be JSON-serializable)
            indent: JSON indentation

        Returns:
            JSON string
        """
        def json_serializer(obj):
            """Handle datetime and other non-serializable types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(data, indent=indent, default=json_serializer)

    @staticmethod
    def generate_filename(
        base_name: str,
        extension: str,
        project_name: Optional[str] = None,
        timestamp: bool = True,
    ) -> str:
        """
        Generate a standardized filename for exports.

        Args:
            base_name: Base name for the file
            extension: File extension (without dot)
            project_name: Optional project name to include
            timestamp: Whether to include timestamp

        Returns:
            Generated filename
        """
        parts = []

        if project_name:
            # Sanitize project name for filename
            safe_name = "".join(
                c if c.isalnum() or c in "-_" else "_"
                for c in project_name
            )
            parts.append(safe_name)

        parts.append(base_name)

        if timestamp:
            parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))

        return "_".join(parts) + f".{extension}"

    @staticmethod
    def export_excel_multisheet(
        sheets: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Export data as Excel workbook with multiple sheets.

        Args:
            sheets: Dict mapping sheet names to data (list of dicts)
            metadata: Optional metadata to include in first sheet

        Returns:
            Excel file bytes
        """
        try:
            import openpyxl

            wb = openpyxl.Workbook()
            ws = wb.active

            # First sheet: metadata (if provided)
            if metadata:
                ws.title = "Metadata"
                ws.append(["IVT Kinetics Analyzer Export"])
                ws.append([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                ws.append([])

                for key, value in metadata.items():
                    ws.append([key, str(value)])

                ws.append([])
                ws.append(["Sheet Index:"])
                for sheet_name in sheets.keys():
                    ws.append(["", sheet_name])
            else:
                ws.title = list(sheets.keys())[0] if sheets else "Sheet1"

            # Create sheets for each data category
            first_sheet = True
            for sheet_name, data in sheets.items():
                if first_sheet and metadata is None:
                    # Use the active sheet for first data
                    sheet = ws
                    first_sheet = False
                else:
                    sheet = wb.create_sheet(title=sheet_name[:31])  # Excel 31 char limit

                if data:
                    # Write headers
                    headers = list(data[0].keys())
                    sheet.append(headers)

                    # Write data rows
                    for row in data:
                        sheet.append([row.get(h, "") for h in headers])

            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            raise RuntimeError(
                "Excel export requires openpyxl. Install with: pip install openpyxl"
            )

    @staticmethod
    def export_analysis_excel(
        raw_data: List[Dict[str, Any]],
        fitted_params: List[Dict[str, Any]],
        fold_changes: List[Dict[str, Any]],
        posterior_summary: Optional[List[Dict[str, Any]]] = None,
        convergence: Optional[Dict[str, Any]] = None,
        project_info: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Export complete analysis results as multi-sheet Excel workbook.

        Sheets:
        1. Metadata - Project info and export metadata
        2. Raw Data - Original measurement data
        3. Fitted Parameters - k_obs, F_max, R² per well
        4. Fold Changes - Construct-level fold changes with CIs
        5. Posterior Summary - MCMC posterior statistics
        6. Convergence - R-hat and ESS diagnostics

        Args:
            raw_data: Raw measurement data
            fitted_params: Fitted kinetic parameters
            fold_changes: Fold change estimates
            posterior_summary: Optional posterior statistics
            convergence: Optional convergence diagnostics
            project_info: Optional project metadata

        Returns:
            Excel file bytes
        """
        sheets = {}

        # Raw data sheet
        if raw_data:
            sheets["Raw Data"] = raw_data

        # Fitted parameters sheet
        if fitted_params:
            sheets["Fitted Parameters"] = fitted_params

        # Fold changes sheet
        if fold_changes:
            sheets["Fold Changes"] = fold_changes

        # Posterior summary sheet
        if posterior_summary:
            sheets["Posterior Summary"] = posterior_summary

        # Convergence diagnostics sheet
        if convergence:
            # Flatten convergence dict for tabular format
            conv_rows = []
            if "r_hat" in convergence and isinstance(convergence["r_hat"], dict):
                for param, value in convergence["r_hat"].items():
                    conv_rows.append({
                        "parameter": param,
                        "metric": "r_hat",
                        "value": value,
                    })
            if "ess" in convergence and isinstance(convergence["ess"], dict):
                for param, value in convergence["ess"].items():
                    conv_rows.append({
                        "parameter": param,
                        "metric": "ess",
                        "value": value,
                    })
            if conv_rows:
                sheets["Convergence"] = conv_rows

        # Metadata
        metadata = {
            "Software": "IVT Kinetics Analyzer",
            "Version": "1.0.0",
            "Export Date": datetime.now().isoformat(),
            "N Constructs": len(set(fc.get("construct") for fc in fold_changes)) if fold_changes else 0,
            "N Wells": len(fitted_params) if fitted_params else 0,
        }
        if project_info:
            metadata.update(project_info)

        return DataExportService.export_excel_multisheet(sheets, metadata)

    @staticmethod
    def export_json_archive(
        data: Dict[str, Any],
        include_metadata: bool = True,
    ) -> bytes:
        """
        Export complete analysis as JSON archive (ZIP containing JSON files).

        Args:
            data: Dict with keys for different data categories
            include_metadata: Whether to include export metadata

        Returns:
            ZIP file bytes containing JSON files
        """
        buffer = BytesIO()

        def json_serializer(obj):
            """Handle datetime and other non-serializable types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "tolist"):  # numpy arrays
                return obj.tolist()
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Export metadata
            if include_metadata:
                metadata = {
                    "software": "IVT Kinetics Analyzer",
                    "version": "1.0.0",
                    "export_date": datetime.now().isoformat(),
                    "contents": list(data.keys()),
                }
                zf.writestr(
                    "metadata.json",
                    json.dumps(metadata, indent=2, default=json_serializer),
                )

            # Export each data category as separate JSON file
            for key, value in data.items():
                filename = f"{key}.json"
                content = json.dumps(value, indent=2, default=json_serializer)
                zf.writestr(filename, content)

        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def export_results_summary_csv(
        fold_changes: List[Dict[str, Any]],
        include_ci: bool = True,
        include_vif: bool = True,
    ) -> str:
        """
        Export fold change results as CSV summary.

        Args:
            fold_changes: List of fold change dictionaries
            include_ci: Include confidence intervals
            include_vif: Include VIF values

        Returns:
            CSV string
        """
        if not fold_changes:
            return ""

        output = StringIO()

        # Determine columns based on options
        base_columns = ["construct", "family", "reference", "mean_log2", "mean_fold"]

        if include_ci:
            base_columns.extend(["ci_lower_log2", "ci_upper_log2", "ci_lower_fold", "ci_upper_fold"])

        if include_vif:
            base_columns.append("vif")

        base_columns.append("n_replicates")

        # Filter to available columns
        if fold_changes:
            available = set(fold_changes[0].keys())
            columns = [c for c in base_columns if c in available]
        else:
            columns = base_columns

        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for fc in fold_changes:
            row = {k: fc.get(k, "") for k in columns}
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_plate_data_csv(
        plate_data: Dict[str, Any],
        format_type: str = "wide",
    ) -> str:
        """
        Export plate data as CSV in wide or long format.

        Args:
            plate_data: Plate data dictionary
            format_type: "wide" (wells as columns) or "long" (one row per well)

        Returns:
            CSV string
        """
        output = StringIO()

        if format_type == "long":
            # Long format: one row per well
            rows = []
            wells = plate_data.get("wells", {})
            for well_id, well_data in wells.items():
                row = {"well_id": well_id}
                row.update(well_data)
                rows.append(row)

            if rows:
                writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        else:
            # Wide format: wells as columns (for time series)
            time_points = plate_data.get("time_points", [])
            wells = plate_data.get("wells", {})

            if time_points and wells:
                # Header: time, well1, well2, ...
                well_ids = sorted(wells.keys())
                header = ["time"] + well_ids
                writer = csv.writer(output)
                writer.writerow(header)

                # Data rows
                for i, t in enumerate(time_points):
                    row = [t]
                    for well_id in well_ids:
                        well_data = wells.get(well_id, {})
                        measurements = well_data.get("measurements", [])
                        value = measurements[i] if i < len(measurements) else ""
                        row.append(value)
                    writer.writerow(row)

        return output.getvalue()

    # ========== Publication Package Data Retrieval ==========

    @staticmethod
    def get_raw_data_for_export(project_id: int) -> Dict[str, Any]:
        """
        Get raw data for publication package export.

        Args:
            project_id: Project ID

        Returns:
            Dict with plates and original files
        """
        from app.models import Plate, Well, RawDataPoint, ExperimentalSession

        raw_data = {"plates": {}, "original_files": {}}

        plates = Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).all()
        for plate in plates:
            plate_data = {
                "plate_id": plate.id,
                "plate_name": f"Plate {plate.plate_number}",
                "wells": {},
            }

            wells = Well.query.filter_by(plate_id=plate.id).all()
            for well in wells:
                well_data = {
                    "well_id": well.id,
                    "position": well.position,
                    "row": well.row_letter,
                    "column": well.col_number,
                    "construct_id": well.construct_id,
                    "well_type": well.well_type.value if well.well_type else None,
                    "timepoints": [],
                    "fluorescence": [],
                }

                # Get raw data points
                points = RawDataPoint.query.filter_by(well_id=well.id).order_by(
                    RawDataPoint.timepoint
                ).all()
                for point in points:
                    well_data["timepoints"].append(point.timepoint)
                    well_data["fluorescence"].append(point.fluorescence_raw)

                plate_data["wells"][well.position] = well_data

            raw_data["plates"][str(plate.id)] = plate_data

        return raw_data

    @staticmethod
    def get_results_for_export(project_id: int) -> Dict[str, Any]:
        """
        Get analysis results for publication package export.

        Args:
            project_id: Project ID

        Returns:
            Dict with fitted params, fold changes, posterior summary
        """
        from app.models import FitResult, FoldChange, Construct, Plate, Well, ExperimentalSession
        from app.models.analysis_version import AnalysisVersion, HierarchicalResult, AnalysisStatus

        results = {
            "fitted_params": [],
            "fold_changes": [],
            "posterior_summary": {},
            "convergence": {},
            "data_summary": {},
        }

        # Get fitted parameters - join through Well -> Plate -> Session
        fits = FitResult.query.join(Well).join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).all()
        for fit in fits:
            well = fit.well
            results["fitted_params"].append({
                "well_id": fit.well_id,
                "well_position": well.position if well else None,
                "plate_id": well.plate_id if well else None,
                "construct_id": well.construct_id if well else None,
                "k_obs": fit.k_obs,
                "k_obs_se": fit.k_obs_se,
                "f_max": fit.f_max,
                "f_max_se": fit.f_max_se,
                "f_baseline": fit.f_baseline,
                "t_lag": fit.t_lag,
                "r_squared": fit.r_squared,
                "rmse": fit.rmse,
                "model_type": fit.model_type,
            })

        # Get fold changes - join through test_well -> Plate -> Session
        fcs = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).all()

        for fc in fcs:
            test_well = fc.test_well
            control_well = fc.control_well
            test_construct = test_well.construct if test_well else None
            control_construct = control_well.construct if control_well else None

            results["fold_changes"].append({
                "test_well_id": fc.test_well_id,
                "test_construct_id": test_well.construct_id if test_well else None,
                "test_construct_name": test_construct.identifier if test_construct else None,
                "control_well_id": fc.control_well_id,
                "control_construct_id": control_well.construct_id if control_well else None,
                "control_construct_name": control_construct.identifier if control_construct else None,
                "fc_fmax": fc.fc_fmax,
                "fc_fmax_se": fc.fc_fmax_se,
                "log_fc_fmax": fc.log_fc_fmax,
                "log_fc_fmax_se": fc.log_fc_fmax_se,
                "fc_kobs": fc.fc_kobs,
                "fc_kobs_se": fc.fc_kobs_se,
                "log_fc_kobs": fc.log_fc_kobs,
                "delta_tlag": fc.delta_tlag,
                "delta_tlag_se": fc.delta_tlag_se,
            })

        # Get latest posterior summary
        latest_version = AnalysisVersion.query.filter_by(
            project_id=project_id, status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisVersion.created_at.desc()).first()

        if latest_version:
            hierarchical_results = HierarchicalResult.query.filter_by(
                analysis_version_id=latest_version.id
            ).all()

            posterior_data = []
            for ar in hierarchical_results:
                posterior_data.append({
                    "construct_id": ar.construct_id,
                    "parameter": ar.parameter_type,
                    "analysis_type": ar.analysis_type,
                    "posterior_mean": ar.mean,
                    "posterior_std": ar.std,
                    "ci_lower": ar.ci_lower,
                    "ci_upper": ar.ci_upper,
                    "r_hat": ar.r_hat,
                    "ess_bulk": ar.ess_bulk,
                    "ess_tail": ar.ess_tail,
                })

            results["posterior_summary"] = {
                "version_id": latest_version.id,
                "version_name": latest_version.name,
                "created_at": latest_version.created_at.isoformat(),
                "results": posterior_data,
            }

            # Convergence diagnostics
            results["convergence"] = {
                "max_r_hat": max((ar.r_hat or 1.0) for ar in hierarchical_results) if hierarchical_results else None,
                "min_ess_bulk": min((ar.ess_bulk or 0) for ar in hierarchical_results) if hierarchical_results else None,
                "all_converged": all((ar.r_hat or 1.0) < 1.1 for ar in hierarchical_results) if hierarchical_results else False,
            }

        # Data summary
        n_constructs = Construct.query.filter_by(project_id=project_id).count()
        n_plates = Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()
        n_wells = Well.query.join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()

        results["data_summary"] = {
            "n_constructs": n_constructs,
            "n_plates": n_plates,
            "n_wells": n_wells,
            "n_fits": len(fits),
            "n_fold_changes": len(fcs),
        }

        return results

    @staticmethod
    def get_mcmc_traces_for_export(project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get MCMC traces for publication package export.

        Args:
            project_id: Project ID

        Returns:
            Dict with trace data or None if not available
        """
        from app.models.analysis_version import AnalysisVersion, MCMCCheckpoint, AnalysisStatus
        from pathlib import Path

        # Find latest completed analysis version
        latest_version = AnalysisVersion.query.filter_by(
            project_id=project_id, status=AnalysisStatus.COMPLETED
        ).order_by(AnalysisVersion.created_at.desc()).first()

        if not latest_version:
            return None

        # Check for checkpoint with traces
        checkpoint = MCMCCheckpoint.query.filter_by(
            analysis_version_id=latest_version.id
        ).order_by(MCMCCheckpoint.checkpoint_at.desc()).first()

        if not checkpoint or not checkpoint.checkpoint_path:
            return None

        trace_path = Path(checkpoint.checkpoint_path)
        if not trace_path.exists():
            return None

        # Try to load traces
        try:
            import xarray as xr
            ds = xr.open_dataset(trace_path)

            # Convert to dict for export
            traces = {}
            for var_name in ds.data_vars:
                traces[var_name] = ds[var_name].values.tolist()

            ds.close()
            return traces

        except Exception:
            # If xarray fails, return None
            return None
