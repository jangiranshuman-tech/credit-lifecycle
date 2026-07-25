"""Pin the loss formula against Freddie's OWN published worked example.

Run this BEFORE building any LGD model. If it fails, your sign convention is wrong
and every downstream LGD number will be quietly incorrect.
"""
from credit_lifecycle.models.loss import actual_loss


def test_user_guide_example_8():
    """User Guide Example 8. Note Expenses is negative in the source data."""
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
    """Example 9 does NOT tie exactly - computed 59,277.56 vs published 59,277.74.

    Could be a typo in the PDF or a component I mapped slightly wrong.
    ACTION: verify against the PDF yourself. If it genuinely does not reconcile,
    that is a finding worth recording in your validation report.
    """
    got = float(actual_loss(125_811.51, 13_021.51, 99_575.03, 0.0, 1_733.83, -21_753.40))
    assert abs(got - 59_277.56) < 0.01, f"got {got}"