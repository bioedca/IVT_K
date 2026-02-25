"""
Generate synthetic test data files for IVT Kinetics Analyzer.

PRD Reference: Section 4.3 - Synthetic test data files

This script generates synthetic kinetic data with known parameters
for use in testing and validation.
"""
import numpy as np
import pandas as pd
import json
from pathlib import Path


def kinetic_model(t, fmax, kobs, tlag=0, bg=100):
    """
    Exponential growth kinetic model.

    F(t) = bg + fmax * (1 - exp(-kobs * (t - tlag)))  for t > tlag
    F(t) = bg                                          for t <= tlag
    """
    result = np.zeros_like(t, dtype=float)
    mask = t > tlag
    result[mask] = bg + fmax * (1 - np.exp(-kobs * (t[mask] - tlag)))
    result[~mask] = bg
    return result


def generate_synthetic_simple():
    """Generate simple kinetic data with 4 wells, no complications."""
    np.random.seed(42)

    time = np.arange(0, 120, 5, dtype=float)  # 0-120 min, 5 min intervals
    n_timepoints = len(time)

    # Parameters for each well
    params = {
        'A1': {'fmax': 1000, 'kobs': 0.05, 'bg': 100},
        'A2': {'fmax': 1200, 'kobs': 0.06, 'bg': 110},
        'B1': {'fmax': 1100, 'kobs': 0.055, 'bg': 95},
        'B2': {'fmax': 1050, 'kobs': 0.052, 'bg': 105},
    }

    data = {'Time': time}
    noise_std = 20  # Relatively low noise

    for well, p in params.items():
        signal = kinetic_model(time, p['fmax'], p['kobs'], bg=p['bg'])
        noise = np.random.normal(0, noise_std, n_timepoints)
        data[well] = signal + noise

    df = pd.DataFrame(data)
    return df, params, {'noise_std': noise_std, 'description': 'Simple kinetic data'}


def generate_synthetic_outliers():
    """Generate kinetic data with outliers in some wells."""
    np.random.seed(43)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    params = {
        'A1': {'fmax': 1000, 'kobs': 0.05, 'bg': 100},
        'A2': {'fmax': 1200, 'kobs': 0.06, 'bg': 110},
        'B1': {'fmax': 1100, 'kobs': 0.055, 'bg': 95},  # Will have outliers
        'B2': {'fmax': 1050, 'kobs': 0.052, 'bg': 105},
    }

    data = {'Time': time}
    noise_std = 25

    for well, p in params.items():
        signal = kinetic_model(time, p['fmax'], p['kobs'], bg=p['bg'])
        noise = np.random.normal(0, noise_std, n_timepoints)
        values = signal + noise

        # Add outliers to B1
        if well == 'B1':
            # Add 3 outlier points
            outlier_indices = [5, 12, 18]
            for idx in outlier_indices:
                values[idx] += np.random.choice([-1, 1]) * 300  # Large spike

        data[well] = values

    df = pd.DataFrame(data)
    return df, params, {'noise_std': noise_std, 'outlier_wells': ['B1'],
                        'description': 'Data with outliers for QC testing'}


def generate_synthetic_drift():
    """Generate kinetic data with baseline drift."""
    np.random.seed(44)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    params = {
        'A1': {'fmax': 1000, 'kobs': 0.05, 'bg': 100, 'drift': 0.5},  # Positive drift
        'A2': {'fmax': 1200, 'kobs': 0.06, 'bg': 110, 'drift': 0.0},  # No drift
        'B1': {'fmax': 1100, 'kobs': 0.055, 'bg': 95, 'drift': -0.3},  # Negative drift
        'B2': {'fmax': 1050, 'kobs': 0.052, 'bg': 105, 'drift': 0.0},  # No drift
    }

    data = {'Time': time}
    noise_std = 20

    for well, p in params.items():
        signal = kinetic_model(time, p['fmax'], p['kobs'], bg=p['bg'])
        drift = p['drift'] * time  # Linear drift
        noise = np.random.normal(0, noise_std, n_timepoints)
        data[well] = signal + drift + noise

    df = pd.DataFrame(data)
    return df, params, {'noise_std': noise_std,
                        'description': 'Data with baseline drift'}


def generate_synthetic_hierarchical():
    """Generate hierarchical data for mixed effects model testing."""
    np.random.seed(45)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    # True parameters
    true_params = {
        'mu_fmax': 1000,  # Population mean Fmax
        'sigma_session': 100,  # Session-level variation
        'sigma_plate': 50,  # Plate-level variation
        'sigma_residual': 20,  # Residual noise
        'kobs': 0.05,
        'bg': 100,
    }

    # Structure: 3 sessions, 2 plates per session, 4 wells per plate
    data_rows = []

    for session_id in range(1, 4):
        session_effect = np.random.normal(0, true_params['sigma_session'])

        for plate_id in range(1, 3):
            plate_effect = np.random.normal(0, true_params['sigma_plate'])

            for well_idx in range(4):
                well_row = chr(65 + well_idx // 2)  # A or B
                well_col = (well_idx % 2) + 1
                well_pos = f"{well_row}{well_col}"

                # True Fmax for this well
                fmax = true_params['mu_fmax'] + session_effect + plate_effect

                # Generate kinetic curve
                signal = kinetic_model(time, fmax, true_params['kobs'],
                                       bg=true_params['bg'])
                noise = np.random.normal(0, true_params['sigma_residual'], n_timepoints)
                values = signal + noise

                for t_idx, (t, v) in enumerate(zip(time, values)):
                    data_rows.append({
                        'session_id': f'S{session_id}',
                        'plate_id': f'P{session_id}_{plate_id}',
                        'well': well_pos,
                        'construct_id': f'C{well_idx + 1}',
                        'time': t,
                        'fluorescence': v
                    })

    df = pd.DataFrame(data_rows)
    return df, true_params, {'description': 'Hierarchical data for mixed model testing'}


def generate_synthetic_negative_controls():
    """Generate data with negative control wells."""
    np.random.seed(46)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    # Sample wells have signal, controls are flat
    params = {
        'A1': {'fmax': 1000, 'kobs': 0.05, 'bg': 100, 'type': 'sample'},
        'A2': {'fmax': 1200, 'kobs': 0.06, 'bg': 110, 'type': 'sample'},
        'A3': {'fmax': 0, 'kobs': 0, 'bg': 95, 'type': 'negative_control'},  # No signal
        'A4': {'fmax': 0, 'kobs': 0, 'bg': 98, 'type': 'negative_control'},
        'B1': {'fmax': 1100, 'kobs': 0.055, 'bg': 95, 'type': 'sample'},
        'B2': {'fmax': 1050, 'kobs': 0.052, 'bg': 105, 'type': 'sample'},
        'B3': {'fmax': 0, 'kobs': 0, 'bg': 100, 'type': 'negative_control'},
        'B4': {'fmax': 0, 'kobs': 0, 'bg': 102, 'type': 'negative_control'},
    }

    data = {'Time': time}
    noise_std = 20

    for well, p in params.items():
        if p['type'] == 'negative_control':
            # Flat signal with noise
            signal = np.full(n_timepoints, p['bg'], dtype=float)
        else:
            signal = kinetic_model(time, p['fmax'], p['kobs'], bg=p['bg'])

        noise = np.random.normal(0, noise_std, n_timepoints)
        data[well] = signal + noise

    df = pd.DataFrame(data)
    return df, params, {'noise_std': noise_std,
                        'negative_control_wells': ['A3', 'A4', 'B3', 'B4'],
                        'description': 'Data with negative control wells'}


def generate_synthetic_96well():
    """Generate full 96-well plate data."""
    np.random.seed(47)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    data = {'Time': time}
    params = {}
    noise_std = 25

    rows = 'ABCDEFGH'  # 8 rows
    cols = range(1, 13)  # 12 columns

    for row in rows:
        for col in cols:
            well = f"{row}{col}"

            # Vary parameters across plate
            row_idx = rows.index(row)
            col_idx = col - 1

            # Gradient across plate
            fmax = 800 + row_idx * 50 + col_idx * 30
            kobs = 0.04 + row_idx * 0.002 + col_idx * 0.001
            bg = 80 + row_idx * 5

            params[well] = {'fmax': fmax, 'kobs': kobs, 'bg': bg}

            signal = kinetic_model(time, fmax, kobs, bg=bg)
            noise = np.random.normal(0, noise_std, n_timepoints)
            data[well] = signal + noise

    df = pd.DataFrame(data)
    return df, params, {'noise_std': noise_std,
                        'plate_format': 96,
                        'description': '96-well plate data'}


def generate_synthetic_low_snr():
    """Generate data with low signal-to-noise ratio."""
    np.random.seed(48)

    time = np.arange(0, 120, 5, dtype=float)
    n_timepoints = len(time)

    params = {
        'A1': {'fmax': 500, 'kobs': 0.03, 'bg': 200},  # Lower signal, higher bg
        'A2': {'fmax': 600, 'kobs': 0.035, 'bg': 220},
        'B1': {'fmax': 550, 'kobs': 0.032, 'bg': 190},
        'B2': {'fmax': 525, 'kobs': 0.028, 'bg': 210},
    }

    data = {'Time': time}
    noise_std = 80  # High noise

    for well, p in params.items():
        signal = kinetic_model(time, p['fmax'], p['kobs'], bg=p['bg'])
        noise = np.random.normal(0, noise_std, n_timepoints)
        data[well] = signal + noise

    df = pd.DataFrame(data)

    # Calculate SNR
    mean_fmax = np.mean([p['fmax'] for p in params.values()])
    snr = mean_fmax / noise_std

    return df, params, {'noise_std': noise_std,
                        'snr': snr,
                        'description': 'Low signal-to-noise ratio data'}


def main():
    """Generate all synthetic data files."""
    output_dir = Path(__file__).parent

    # All generators
    generators = [
        ('synthetic_simple', generate_synthetic_simple),
        ('synthetic_outliers', generate_synthetic_outliers),
        ('synthetic_drift', generate_synthetic_drift),
        ('synthetic_hierarchical', generate_synthetic_hierarchical),
        ('synthetic_negative_controls', generate_synthetic_negative_controls),
        ('synthetic_96well', generate_synthetic_96well),
        ('synthetic_low_snr', generate_synthetic_low_snr),
    ]

    all_params = {}

    for name, generator in generators:
        print(f"Generating {name}...")
        df, params, metadata = generator()

        # Save CSV
        csv_path = output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  Saved {csv_path}")

        # Store parameters
        all_params[name] = {
            'true_parameters': params,
            'metadata': metadata
        }

    # Save all parameters to JSON
    params_path = output_dir / "synthetic_parameters.json"

    # Convert numpy types to Python types for JSON serialization
    def convert_to_serializable(obj):
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_to_serializable(i) for i in obj]
        return obj

    all_params_serializable = convert_to_serializable(all_params)

    with open(params_path, 'w') as f:
        json.dump(all_params_serializable, f, indent=2)
    print(f"Saved parameters to {params_path}")

    print("\nGeneration complete!")


if __name__ == '__main__':
    main()
