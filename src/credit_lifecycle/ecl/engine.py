"""Expected credit loss summation.

    ECL = sum_t  discount(t) * marginal_PD(t) * LGD(t) * EAD(t)

Discounting is monthly at the instrument's effective interest rate. IFRS 9 requires
the ORIGINAL EIR of the instrument, not a portfolio-wide rate, which is why `eir` is
a per-call argument rather than read from config - Freddie supplies
`original_interest_rate` per loan.

This module is deliberately framework-agnostic. Staging (IFRS 9) and the
reasonable-and-supportable horizon with reversion (CECL) sit above it, so the same
summation serves both.
"""
from __future__ import annotations

import numpy as np


def discount_factors(n_periods: int, eir: float) -> np.ndarray:
    """Monthly discount factors for periods 1..n at an annual effective rate."""
    t = np.arange(1, n_periods + 1)
    return 1.0 / (1.0 + eir) ** (t / 12.0)


def lifetime_ecl(marginal_pd, lgd, ead, eir: float) -> float:
    """Discounted expected credit loss over the supplied term structure.

    `marginal_pd[t]` is the probability of default in period t conditional on
    survival to t - a marginal, not cumulative, term structure. Passing cumulative
    PDs overstates ECL substantially.
    """
    pd_ = np.asarray(marginal_pd, dtype="float64")
    lgd_ = np.asarray(lgd, dtype="float64")
    ead_ = np.asarray(ead, dtype="float64")
    if not (pd_.shape == lgd_.shape == ead_.shape):
        raise ValueError(
            f"shape mismatch: pd={pd_.shape}, lgd={lgd_.shape}, ead={ead_.shape}"
        )
    return float((pd_ * lgd_ * ead_ * discount_factors(len(pd_), eir)).sum())


def scenario_weighted_ecl(scenario_ecls: dict[str, float], weights: dict[str, float]) -> float:
    """Probability-weighted ECL across macroeconomic scenarios.

    IFRS 9 requires an unbiased probability-weighted amount, so weights must sum to
    one and every scenario supplied must carry a weight.
    """
    missing = set(scenario_ecls) - set(weights)
    if missing:
        raise ValueError(f"no weight supplied for scenario(s): {sorted(missing)}")
    total = sum(weights[k] for k in scenario_ecls)
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"scenario weights must sum to 1.0, got {total}")
    return float(sum(scenario_ecls[k] * weights[k] for k in scenario_ecls))
