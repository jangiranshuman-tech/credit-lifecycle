"""Guards that the modelling stack imports and that the two library APIs this
project depends on still behave as expected.

The fuller 12-primitive check is scripts/verify_stack.py, run by hand. This file
is the fast subset that runs in CI.
"""
import importlib

import pytest

REQUIRED = [
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "statsmodels",
    "duckdb",
    "optbinning",
    "lightgbm",
    "lifelines",
    "shap",
    "fairlearn",
    "pandera",
]


@pytest.mark.parametrize("mod", REQUIRED)
def test_dependency_importable(mod):
    importlib.import_module(mod)


def test_optbinning_monotonic_binning_api():
    """The scorecard depends on this API, so it is pinned rather than assumed."""
    import numpy as np
    from optbinning import OptimalBinning

    rng = np.random.default_rng(0)
    x = rng.normal(680, 60, 5000)
    y = rng.binomial(1, 1 / (1 + np.exp((x - 680) / 40)))

    ob = OptimalBinning(name="score", dtype="numerical", monotonic_trend="descending")
    ob.fit(x, y)
    table = ob.binning_table.build()

    assert ob.binning_table.iv > 0
    assert len(table) > 3


def test_lightgbm_accepts_monotone_constraints():
    """Monotone constraints are required for the benchmark model to be defensible
    under model risk review, so a version bump that drops the argument fails here."""
    import lightgbm as lgb
    import numpy as np

    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, (500, 2))
    y = rng.binomial(1, 0.3, 500)

    lgb.LGBMClassifier(n_estimators=5, monotone_constraints=[-1, 1], verbose=-1).fit(x, y)
