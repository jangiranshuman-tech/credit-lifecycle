"""Pins the Actual Loss formula against the worked examples in the Freddie Mac
User Guide. A sign error in the expenses term produces plausible-looking but
incorrect LGD, so the formula is fixed by test rather than by inspection.
"""
from credit_lifecycle.models.loss import actual_loss


def test_user_guide_example_8():
    """Reconciles exactly. Expenses are negative in the source data."""
    got = actual_loss(
        zb_removal_upb=96_721.02,
        delinquent_accrued_interest=32_272.58,
        net_sale_proceeds=37_348.78,
        mi_recoveries=27_843.41,
        non_mi_recoveries=0.0,
        expenses=-15_139.83,
    )
    assert abs(float(got) - 78_941.24) < 0.01


def test_user_guide_example_9_known_discrepancy():
    """Does not reconcile: computes 59,277.56 against 59,277.74 published.

    Difference is 0.18. Example 8 reconciles exactly with the same formula, so the
    discrepancy is either a typo in the guide or a component mapping I have wrong.
    Unresolved; recorded in docs/limitations.md. The test asserts the computed value
    so that a future change to the formula is caught here.
    """
    got = float(actual_loss(125_811.51, 13_021.51, 99_575.03, 0.0, 1_733.83, -21_753.40))
    assert abs(got - 59_277.56) < 0.01, f"got {got}"
