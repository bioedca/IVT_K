"""
Numerical utility functions for safe mathematical operations.

Provides guarded division and logarithmic operations to prevent
ZeroDivisionError and related runtime crashes in scientific computations.
"""
import math
from typing import Union

Number = Union[int, float]


def safe_divide(
    numerator: Number,
    denominator: Number,
    default: float = 0.0,
    min_denominator: float = 1e-10,
) -> float:
    """
    Safe division with floor on denominator magnitude.

    Args:
        numerator: The numerator value.
        denominator: The denominator value.
        default: Value to return when denominator is effectively zero.
        min_denominator: Minimum absolute value for denominator to be
            considered non-zero.

    Returns:
        Result of division, or default if denominator is too small.
    """
    if abs(denominator) < min_denominator:
        return default
    return float(numerator) / float(denominator)


def safe_log_ratio(
    numerator: Number,
    denominator: Number,
    default: float = 0.0,
    base: float = 2.0,
) -> float:
    """
    Safely compute log(numerator / denominator).

    Both numerator and denominator must be positive for a valid result.

    Args:
        numerator: The numerator value (must be > 0 for valid log).
        denominator: The denominator value (must be > 0 for valid log).
        default: Value to return when inputs are non-positive.
        base: Logarithm base (must be > 0 and != 1; default 2 for fold-change calculations).

    Returns:
        log_base(numerator / denominator), or default if inputs are invalid.
    """
    if numerator <= 0 or denominator <= 0:
        return default
    if base <= 0 or base == 1:
        return default
    return math.log(numerator / denominator) / math.log(base)
