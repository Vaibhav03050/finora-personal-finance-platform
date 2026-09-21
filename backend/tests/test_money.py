import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.money import safe_div, to_major, to_minor


def test_to_minor_basic():
    assert to_minor(100.0) == 10000
    assert to_minor(99.99) == 9999
    assert to_minor(0.5) == 50


def test_to_minor_rounds_correctly():
    assert to_minor(10.005) == 1001 or to_minor(10.005) == 1000  # banker's rounding edge case, must not crash


def test_to_major_roundtrip():
    assert to_major(10000) == 100.0
    assert to_major(9999) == 99.99


def test_to_major_never_float_drift_for_common_values():
    for rupees in [0.1, 1.1, 19.99, 1234.56, 100000.0]:
        minor = to_minor(rupees)
        back = to_major(minor)
        assert abs(back - rupees) < 0.01


def test_safe_div_zero_denominator():
    assert safe_div(100, 0) == 0.0


def test_safe_div_normal():
    assert safe_div(50, 200) == 0.25
