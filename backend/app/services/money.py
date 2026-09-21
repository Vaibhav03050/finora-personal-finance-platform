"""
All money math happens in integer minor units (paise). Floats only ever
appear at the API boundary (request/response), converted here.
"""


def to_minor(rupees: float) -> int:
    """Convert a whole-currency float (e.g. rupees, from user input) to paise."""
    return round(rupees * 100)


def to_major(minor: int) -> float:
    """Convert paise back to rupees for display, rounded to 2 decimals."""
    return round(minor / 100, 2)


def safe_div(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
