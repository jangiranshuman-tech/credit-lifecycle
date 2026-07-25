"""
Freddie Mac Actual Loss calculation.

Official formula (User Guide, "Actual Loss" section):

    Actual Loss = (Zero Balance Removal UPB + Delinquent Accrued Interest)
                  - Net Sale Proceeds - MI Recoveries - Non-MI Recoveries - Expenses

GOTCHAS, both verified:
  1. Expenses are stored as a NEGATIVE number, so subtracting them ADDS to the loss.
  2. Modification Costs are NOT included in Freddie's own loss field.
  3. Loss is null for loans disposed within three months of the zero balance date.
  4. Loss is populated only for zero balance codes 02, 03, 09, 15.

Get (1) wrong and your LGD is wrong in a way that still looks plausible.
"""
import numpy as np


def actual_loss(zb_removal_upb, delinquent_accrued_interest, net_sale_proceeds,
                mi_recoveries, non_mi_recoveries, expenses):
    """Vectorised. `expenses` must be passed with Freddie's native sign (negative)."""
    return (
        (np.asarray(zb_removal_upb, dtype="float64")
         + np.asarray(delinquent_accrued_interest, dtype="float64"))
        - np.asarray(net_sale_proceeds, dtype="float64")
        - np.asarray(mi_recoveries, dtype="float64")
        - np.asarray(non_mi_recoveries, dtype="float64")
        - np.asarray(expenses, dtype="float64")
    )