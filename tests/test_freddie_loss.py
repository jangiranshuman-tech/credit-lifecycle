"""Pins the Actual Loss formula and its sign conventions.

Two independent sources: the worked examples in the Freddie Mac User Guide, and a
real terminated loan from sample_svcg_2005.txt. A sign error on the expenses term
or on the published loss field produces plausible-looking but incorrect LGD, so
both conventions are fixed by test rather than by inspection.
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

    Difference is 0.18. Example 8 reconciles exactly under the same formula, and
    the formula reconciles against real data at 100% (see below), so the guide's
    Example 9 appears to contain an error. Recorded in docs/limitations.md.
    """
    got = float(actual_loss(125_811.51, 13_021.51, 99_575.03, 0.0, 1_733.83, -21_753.40))
    assert abs(got - 59_277.56) < 0.01, f"got {got}"


def test_real_loan_reconciles_to_negated_published_field():
    """Loan F05Q10000744 from sample_svcg_2005.txt, zero balance code 09 (REO
    disposition). Freddie's published actual_loss_calculation is -19,995.67.

    This function returns loss as a positive magnitude, so it must equal the
    negated published value. Across the full 2005 sample this holds for all
    2,702 rows carrying a published loss.
    """
    computed = float(
        actual_loss(
            zb_removal_upb=22_791.15,          # field 27
            delinquent_accrued_interest=1_783.88,  # field 28
            net_sale_proceeds=3_036.47,        # field 15
            mi_recoveries=7_521.07,            # field 14
            non_mi_recoveries=704.10,          # field 16
            expenses=-6_682.28,                # field 17, stored negative
        )
    )
    published = -19_995.67                      # field 22, stored negative
    assert abs(computed - (-published)) < 0.01


def test_expense_components_sum_to_total():
    """Fields 18-21 sum to field 17, all stored negative. Same loan as above."""
    legal, maintenance, taxes, misc = -2_888.58, -3_039.85, -498.85, -255.00
    assert abs((legal + maintenance + taxes + misc) - (-6_682.28)) < 0.01
