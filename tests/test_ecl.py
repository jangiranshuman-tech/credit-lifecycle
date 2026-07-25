"""ECL summation.

The previous version of this file compared a numpy expression to the same formula
rewritten as a Python loop, which could not detect a wrong discounting convention.
These tests exercise the real function and check properties that would actually
break if the convention were wrong.
"""
import numpy as np
import pytest

from credit_lifecycle.ecl.engine import lifetime_ecl


def test_single_period_matches_closed_form():
    """One month out: ECL = PD x LGD x EAD discounted one month at the EIR."""
    got = lifetime_ecl(np.array([0.004]), np.array([0.35]), np.array([100_000.0]), eir=0.06)
    expected = 0.004 * 0.35 * 100_000 / (1 + 0.06) ** (1 / 12)
    assert abs(got - expected) < 1e-9


def test_discounting_reduces_ecl():
    """A positive EIR must produce a smaller figure than the undiscounted sum.
    This is the check the old test could not make."""
    pd_, lgd, ead = np.full(12, 0.004), np.full(12, 0.35), np.full(12, 100_000.0)
    assert lifetime_ecl(pd_, lgd, ead, eir=0.06) < lifetime_ecl(pd_, lgd, ead, eir=0.0)


def test_zero_eir_equals_simple_sum():
    pd_, lgd, ead = np.full(12, 0.004), np.full(12, 0.35), np.full(12, 100_000.0)
    assert abs(lifetime_ecl(pd_, lgd, ead, eir=0.0) - (0.004 * 0.35 * 100_000 * 12)) < 1e-9


def test_later_losses_discount_more():
    """Same marginal PD later in the term must contribute less present value."""
    early = lifetime_ecl(np.array([0.01, 0.0]), np.full(2, 0.4), np.full(2, 50_000.0), eir=0.08)
    late = lifetime_ecl(np.array([0.0, 0.01]), np.full(2, 0.4), np.full(2, 50_000.0), eir=0.08)
    assert early > late


def test_scales_linearly_in_each_factor():
    base = lifetime_ecl(np.full(6, 0.005), np.full(6, 0.4), np.full(6, 10_000.0), eir=0.05)
    doubled = lifetime_ecl(np.full(6, 0.01), np.full(6, 0.4), np.full(6, 10_000.0), eir=0.05)
    assert abs(doubled - 2 * base) < 1e-9


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        lifetime_ecl(np.full(3, 0.01), np.full(2, 0.4), np.full(3, 1_000.0), eir=0.05)


def test_per_loan_eir_is_supported():
    """IFRS 9 discounts at the instrument's original EIR, not a portfolio rate."""
    a = lifetime_ecl(np.full(6, 0.005), np.full(6, 0.4), np.full(6, 10_000.0), eir=0.04)
    b = lifetime_ecl(np.full(6, 0.005), np.full(6, 0.4), np.full(6, 10_000.0), eir=0.09)
    assert a > b
