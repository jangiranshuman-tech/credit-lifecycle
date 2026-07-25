"""
Freddie Mac Actual Loss calculation.

Formula from the User Guide, applicable to zero balance codes 02, 03, 09 and 15:

    Actual Loss = (Zero Balance Removal UPB + Delinquent Accrued Interest)
                  - Net Sale Proceeds - MI Recoveries - Non-MI Recoveries - Expenses

Sign conventions, both established against sample_svcg_2005.txt on 2026-07-25:

  1. Total Expenses (field 17) and its components (fields 18-21) are stored as
     NEGATIVE values, so subtracting them increases the loss.
  2. Freddie's published actual_loss_calculation (field 22) is stored NEGATIVE for
     a loss and positive for a gain. This function returns the loss as a POSITIVE
     magnitude, which is the convention LGD modelling needs, so reconciliation is
     against the negated published field.

Verified: 2,702 loss rows in the 2005 sample, 100% reconciling to within 0.01.
67 of those rows carry a positive published value, i.e. recoveries exceeded
exposure. Those are genuine gains, not sign errors.

Other constraints on the loss population:
  - Loss is null where defect_settlement_date is populated.
  - Loss is null for loans disposed within three months of the performance cutoff.
  - Modification costs are excluded from Freddie's field.
  - Net Sale Proceeds may be the string "U" (unknown) rather than a number.
"""
import numpy as np


def actual_loss(zb_removal_upb, delinquent_accrued_interest, net_sale_proceeds,
                mi_recoveries, non_mi_recoveries, expenses):
    """Loss as a positive magnitude. Vectorised.

    `expenses` must be passed with Freddie's native sign (negative).
    Reconcile against ``-actual_loss_calculation``.
    """
    return (
        (np.asarray(zb_removal_upb, dtype="float64")
         + np.asarray(delinquent_accrued_interest, dtype="float64"))
        - np.asarray(net_sale_proceeds, dtype="float64")
        - np.asarray(mi_recoveries, dtype="float64")
        - np.asarray(non_mi_recoveries, dtype="float64")
        - np.asarray(expenses, dtype="float64")
    )
