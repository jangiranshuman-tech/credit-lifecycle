"""ECL engine must match a hand calculation before you trust it on a portfolio."""
import numpy as np


def test_ecl_matches_hand_calculation():
    ead, marg_pd, lgd, eir = 100_000.0, 0.004, 0.35, 0.06
    disc = 1 / (1 + eir) ** (np.arange(1, 13) / 12)
    ecl = float((marg_pd * lgd * ead * disc).sum())
    manual = sum(0.004 * 0.35 * 100_000 / (1 + 0.06) ** (t / 12) for t in range(1, 13))
    assert abs(ecl - manual) < 1e-6