"""
Q-Q Plot visualization components for statistical diagnostics.

Sprint 7: PRD Reference Lines 8542-8543, T8.17

Provides:
- Q-Q plots for random effects
- Normal distribution comparison
- Outlier highlighting
- Multiple distribution support
"""
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from app.theme import apply_plotly_theme

# Try importing scipy
try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def generate_qq_data(
    data: np.ndarray,
    distribution: str = 'norm'
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate Q-Q plot data for visualization.

    Args:
        data: Data to compare against theoretical distribution
        distribution: 'norm' for normal distribution

    Returns:
        Tuple of (theoretical_quantiles, sample_quantiles, fit_line_x, fit_line_y)
    """
    data = np.asarray(data).flatten()
    data = data[~np.isnan(data)]
    data = np.sort(data)

    n = len(data)

    if n == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])

    # Calculate plotting positions (Blom's formula for better approximation)
    positions = (np.arange(1, n + 1) - 0.375) / (n + 0.25)

    # Get theoretical quantiles
    if SCIPY_AVAILABLE:
        if distribution == 'norm':
            theoretical = scipy_stats.norm.ppf(positions)
        elif distribution == 't':
            # t-distribution with n-1 df
            theoretical = scipy_stats.t.ppf(positions, df=n-1)
        else:
            theoretical = scipy_stats.norm.ppf(positions)
    else:
        # Approximate normal quantiles using inverse error function approximation
        theoretical = np.sqrt(2) * np.array([
            _approx_norm_ppf(p) for p in positions
        ])

    # Fit reference line through Q1 and Q3 (robust to outliers)
    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)

    if q3_idx > q1_idx:
        slope = (data[q3_idx] - data[q1_idx]) / (theoretical[q3_idx] - theoretical[q1_idx])
        intercept = data[q1_idx] - slope * theoretical[q1_idx]
    else:
        slope = np.std(data)
        intercept = np.mean(data)

    fit_line_x = np.array([theoretical.min(), theoretical.max()])
    fit_line_y = intercept + slope * fit_line_x

    return theoretical, data, fit_line_x, fit_line_y


def _approx_norm_ppf(p: float) -> float:
    """Approximate inverse normal CDF for when scipy is not available."""
    # Abramowitz and Stegun approximation
    if p <= 0:
        return -np.inf
    if p >= 1:
        return np.inf
    if p == 0.5:
        return 0.0

    if p > 0.5:
        t = np.sqrt(-2 * np.log(1 - p))
        sign = 1
    else:
        t = np.sqrt(-2 * np.log(p))
        sign = -1

    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308

    return sign * (t - (c0 + c1*t + c2*t**2) / (1 + d1*t + d2*t**2 + d3*t**3))


def identify_outliers(
    theoretical: np.ndarray,
    observed: np.ndarray,
    threshold: float = 2.0
) -> np.ndarray:
    """
    Identify outliers in Q-Q plot based on deviation from line.

    Args:
        theoretical: Theoretical quantiles
        observed: Observed quantiles (sorted data)
        threshold: Number of standard deviations for outlier detection

    Returns:
        Boolean array marking outliers
    """
    if len(theoretical) < 3 or len(observed) < 3:
        return np.zeros(len(observed), dtype=bool)

    # Fit line using Q1-Q3
    n = len(observed)
    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)

    if q3_idx <= q1_idx:
        return np.zeros(n, dtype=bool)

    slope = (observed[q3_idx] - observed[q1_idx]) / (theoretical[q3_idx] - theoretical[q1_idx])
    intercept = observed[q1_idx] - slope * theoretical[q1_idx]

    # Calculate residuals
    predicted = intercept + slope * theoretical
    residuals = observed - predicted

    # Identify outliers using MAD
    mad = np.median(np.abs(residuals - np.median(residuals)))
    if mad < 1e-10:
        mad = np.std(residuals)

    return np.abs(residuals - np.median(residuals)) > threshold * 1.4826 * mad


def create_qq_plot(
    samples: np.ndarray,
    title: str = "Q-Q Plot (Normal)",
    height: int = 400,
    show_confidence_band: bool = True,
    highlight_outliers: bool = True,
    outlier_threshold: float = 2.0,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a Q-Q plot comparing samples to normal distribution.

    PRD Reference: Lines 8542-8543, T8.17

    Args:
        samples: Array of samples to test
        title: Chart title
        height: Figure height in pixels
        show_confidence_band: Show 95% confidence band around reference line
        highlight_outliers: Highlight potential outliers
        outlier_threshold: MAD multiplier for outlier detection
        dark_mode: Apply dark mode theme styling to the figure

    Returns:
        Plotly figure
    """
    samples = np.asarray(samples).flatten()
    samples = samples[~np.isnan(samples)]

    if len(samples) < 3:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data for Q-Q plot (n < 3)",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14)
        )
        fig.update_layout(height=height)
        return fig

    # Generate Q-Q data
    theoretical, observed, fit_x, fit_y = generate_qq_data(samples)

    # Identify outliers
    outliers = identify_outliers(theoretical, observed, outlier_threshold) if highlight_outliers else None

    fig = go.Figure()

    # Add confidence band if requested
    if show_confidence_band and len(samples) >= 10:
        n = len(samples)
        se = np.std(observed) / np.sqrt(n)

        # Confidence band widens at tails
        band_width = 1.96 * se * (1 + 0.5 * np.abs(theoretical) / np.max(np.abs(theoretical)))

        slope = (fit_y[1] - fit_y[0]) / (fit_x[1] - fit_x[0])
        intercept = fit_y[0] - slope * fit_x[0]
        expected = intercept + slope * theoretical

        upper = expected + band_width
        lower = expected - band_width

        fig.add_trace(go.Scatter(
            x=np.concatenate([theoretical, theoretical[::-1]]),
            y=np.concatenate([upper, lower[::-1]]),
            fill='toself',
            fillcolor='rgba(66, 133, 244, 0.15)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo='skip',
            showlegend=True,
            name='95% Confidence Band',
        ))

    # Add reference line
    fig.add_trace(go.Scatter(
        x=fit_x,
        y=fit_y,
        mode='lines',
        line=dict(color='#fa5252', width=2, dash='dash'),
        name='Normal Reference',
        hoverinfo='skip',
    ))

    # Add data points (non-outliers)
    if outliers is not None:
        non_outlier_mask = ~outliers
        if np.any(non_outlier_mask):
            fig.add_trace(go.Scatter(
                x=theoretical[non_outlier_mask],
                y=observed[non_outlier_mask],
                mode='markers',
                marker=dict(
                    size=8,
                    color='#228be6',
                    opacity=0.7,
                ),
                name='Normal Points',
                hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<extra></extra>',
            ))

        # Add outlier points
        if np.any(outliers):
            fig.add_trace(go.Scatter(
                x=theoretical[outliers],
                y=observed[outliers],
                mode='markers',
                marker=dict(
                    size=10,
                    color='#fa5252',
                    symbol='diamond',
                    line=dict(width=1, color='#c92a2a'),
                ),
                name=f'Potential Outliers ({np.sum(outliers)})',
                hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<br><b>Potential Outlier</b><extra></extra>',
            ))
    else:
        # No outlier detection
        fig.add_trace(go.Scatter(
            x=theoretical,
            y=observed,
            mode='markers',
            marker=dict(
                size=8,
                color='#228be6',
                opacity=0.7,
            ),
            name='Sample Points',
            hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<extra></extra>',
        ))

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center',
        ),
        xaxis=dict(
            title='Theoretical Quantiles (Normal)',
            zeroline=True,
            zerolinecolor='lightgray',
        ),
        yaxis=dict(
            title='Sample Quantiles',
            zeroline=True,
            zerolinecolor='lightgray',
        ),
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
        ),
        hovermode='closest',
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_multi_qq_plot(
    datasets: List[Dict[str, Any]],
    ncols: int = 2,
    height_per_row: int = 350,
    show_confidence_band: bool = True,
    highlight_outliers: bool = True,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create multiple Q-Q plots in a grid.

    Args:
        datasets: List of dicts with:
            - name: Dataset name (used as subplot title)
            - samples: Array of samples
        ncols: Number of columns in grid
        height_per_row: Height per row in pixels
        show_confidence_band: Show confidence band
        highlight_outliers: Highlight outliers

    Returns:
        Plotly figure with subplot grid
    """
    if not datasets:
        fig = go.Figure()
        fig.add_annotation(
            text="No data provided",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    n_plots = len(datasets)
    nrows = (n_plots + ncols - 1) // ncols
    height = height_per_row * nrows

    subplot_titles = [d.get('name', f'Dataset {i+1}') for i, d in enumerate(datasets)]

    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.1,
        vertical_spacing=0.15,
    )

    for i, dataset in enumerate(datasets):
        row = i // ncols + 1
        col = i % ncols + 1

        samples = np.asarray(dataset.get('samples', [])).flatten()
        samples = samples[~np.isnan(samples)]

        if len(samples) < 3:
            fig.add_annotation(
                text="Insufficient data",
                xref=f"x{i+1}" if i > 0 else "x",
                yref=f"y{i+1}" if i > 0 else "y",
                x=0.5, y=0.5,
                xanchor='center',
                showarrow=False,
                row=row, col=col,
            )
            continue

        theoretical, observed, fit_x, fit_y = generate_qq_data(samples)
        outliers = identify_outliers(theoretical, observed) if highlight_outliers else None

        # Add reference line
        fig.add_trace(
            go.Scatter(
                x=fit_x,
                y=fit_y,
                mode='lines',
                line=dict(color='#fa5252', width=2, dash='dash'),
                showlegend=False,
                hoverinfo='skip',
            ),
            row=row, col=col
        )

        # Add points
        if outliers is not None and np.any(outliers):
            # Non-outliers
            mask = ~outliers
            fig.add_trace(
                go.Scatter(
                    x=theoretical[mask],
                    y=observed[mask],
                    mode='markers',
                    marker=dict(size=6, color='#228be6', opacity=0.7),
                    showlegend=False,
                    hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<extra></extra>',
                ),
                row=row, col=col
            )
            # Outliers
            fig.add_trace(
                go.Scatter(
                    x=theoretical[outliers],
                    y=observed[outliers],
                    mode='markers',
                    marker=dict(size=8, color='#fa5252', symbol='diamond'),
                    showlegend=False,
                    hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<br><b>Outlier</b><extra></extra>',
                ),
                row=row, col=col
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=theoretical,
                    y=observed,
                    mode='markers',
                    marker=dict(size=6, color='#228be6', opacity=0.7),
                    showlegend=False,
                    hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.2f}<extra></extra>',
                ),
                row=row, col=col
            )

    fig.update_layout(
        height=height,
        margin=dict(l=60, r=40, t=80, b=60),
    )

    # Update axes
    for i in range(n_plots):
        fig.update_xaxes(
            title_text='Theoretical',
            zeroline=True,
            zerolinecolor='lightgray',
            row=i // ncols + 1,
            col=i % ncols + 1,
        )
        fig.update_yaxes(
            title_text='Sample',
            zeroline=True,
            zerolinecolor='lightgray',
            row=i // ncols + 1,
            col=i % ncols + 1,
        )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_residuals_vs_fitted_plot(
    residuals: np.ndarray,
    fitted_values: np.ndarray,
    title: str = "Residuals vs Fitted",
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create residuals vs fitted values plot for homoscedasticity check.

    Args:
        residuals: Model residuals
        fitted_values: Fitted/predicted values
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    residuals = np.asarray(residuals).flatten()
    fitted_values = np.asarray(fitted_values).flatten()

    # Remove NaN
    mask = ~(np.isnan(residuals) | np.isnan(fitted_values))
    residuals = residuals[mask]
    fitted_values = fitted_values[mask]

    if len(residuals) < 3:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        fig.update_layout(height=height)
        return fig

    fig = go.Figure()

    # Add scatter points
    fig.add_trace(go.Scatter(
        x=fitted_values,
        y=residuals,
        mode='markers',
        marker=dict(
            size=8,
            color='#228be6',
            opacity=0.6,
        ),
        name='Residuals',
        hovertemplate='Fitted: %{x:.3f}<br>Residual: %{y:.3f}<extra></extra>',
    ))

    # Add horizontal line at y=0
    fig.add_hline(
        y=0,
        line=dict(color='#fa5252', width=2, dash='dash'),
    )

    # Add LOWESS smoother if enough data
    if len(residuals) >= 10:
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            smoothed = lowess(residuals, fitted_values, frac=0.3, return_sorted=True)
            fig.add_trace(go.Scatter(
                x=smoothed[:, 0],
                y=smoothed[:, 1],
                mode='lines',
                line=dict(color='#40c057', width=2),
                name='LOWESS Smooth',
            ))
        except ImportError:
            pass

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center'),
        xaxis=dict(
            title='Fitted Values',
        ),
        yaxis=dict(
            title='Residuals',
            zeroline=True,
            zerolinecolor='lightgray',
        ),
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
        ),
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_scale_location_plot(
    residuals: np.ndarray,
    fitted_values: np.ndarray,
    title: str = "Scale-Location",
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create scale-location plot (sqrt of standardized residuals vs fitted).

    Useful for detecting non-constant variance (heteroscedasticity).

    Args:
        residuals: Model residuals
        fitted_values: Fitted/predicted values
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    residuals = np.asarray(residuals).flatten()
    fitted_values = np.asarray(fitted_values).flatten()

    mask = ~(np.isnan(residuals) | np.isnan(fitted_values))
    residuals = residuals[mask]
    fitted_values = fitted_values[mask]

    if len(residuals) < 3:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        fig.update_layout(height=height)
        return fig

    # Standardize residuals
    std_residuals = residuals / np.std(residuals)
    sqrt_abs_std = np.sqrt(np.abs(std_residuals))

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=fitted_values,
        y=sqrt_abs_std,
        mode='markers',
        marker=dict(
            size=8,
            color='#228be6',
            opacity=0.6,
        ),
        name='|Std Residuals|^0.5',
        hovertemplate='Fitted: %{x:.3f}<br>sqrt(|Std Resid|): %{y:.3f}<extra></extra>',
    ))

    # Add LOWESS smoother
    if len(residuals) >= 10:
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            smoothed = lowess(sqrt_abs_std, fitted_values, frac=0.3, return_sorted=True)
            fig.add_trace(go.Scatter(
                x=smoothed[:, 0],
                y=smoothed[:, 1],
                mode='lines',
                line=dict(color='#fa5252', width=2),
                name='LOWESS Smooth',
            ))
        except ImportError:
            pass

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center'),
        xaxis=dict(
            title='Fitted Values',
        ),
        yaxis=dict(
            title='sqrt(|Standardized Residuals|)',
        ),
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
        ),
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig
