"""Reconcile the computed Actual Loss against Freddie Mac's published field.

This is the evidence behind the reconciliation figure quoted in docs/limitations.md.
It was previously an unreproducible claim; running this regenerates it.

    python scripts/reconcile_loss.py                # 2005 vintage
    python scripts/reconcile_loss.py 2005 2006 2008 # several

Requires the sample_YYYY.zip files in data/raw/freddie/.
"""
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from credit_lifecycle.data.freddie_layout import (
    LOSS_ZERO_BALANCE_CODES,
    PERFORMANCE_COLS,
    is_default,
    parse_dlq,
)
from credit_lifecycle.models.loss import actual_loss, to_amount

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "freddie"


def load_vintage(year: int) -> pd.DataFrame:
    with zipfile.ZipFile(RAW / f"sample_{year}.zip") as z:
        name = next(n for n in z.namelist() if "svcg" in n)
        with z.open(name) as fh:
            return pd.read_csv(
                fh, sep="|", header=None, names=PERFORMANCE_COLS, low_memory=False,
                dtype={"current_loan_delinquency_status": "string",
                       "zero_balance_code": "string",
                       "net_sale_proceeds": "string",
                       "defect_settlement_date": "string"},
            )


def reconcile(year: int) -> dict:
    p = load_vintage(year)
    published = pd.to_numeric(p["actual_loss_calculation"], errors="coerce")
    have = published.notna()

    computed = actual_loss(
        to_amount(p["zero_balance_removal_upb"]),
        to_amount(p["delinquent_accrued_interest"]),
        to_amount(p["net_sale_proceeds"]),
        to_amount(p["mi_recoveries"]),
        to_amount(p["non_mi_recoveries"]),
        to_amount(p["total_expenses"]),
    )
    # published stores a loss as negative; actual_loss returns positive magnitude
    diff = np.abs(computed[have.to_numpy()] + published[have].to_numpy())
    ok = np.isfinite(diff) & (diff < 0.01)

    zb_eligible = p["zero_balance_code"].isin(LOSS_ZERO_BALANCE_CODES)
    dflt = is_default(parse_dlq(p["current_loan_delinquency_status"])).fillna(False)
    loss_loans = set(p.loc[have, "loan_sequence_number"])
    default_loans = set(p.loc[dflt, "loan_sequence_number"])

    return {
        "year": year,
        "rows": len(p),
        "loans": p["loan_sequence_number"].nunique(),
        "zb_eligible_rows": int(zb_eligible.sum()),
        "published_loss_rows": int(have.sum()),
        "null_loss_with_eligible_zb": int((zb_eligible & ~have).sum()),
        "of_which_defect": int((zb_eligible & ~have & p["defect_settlement_date"].notna()).sum()),
        "reconciled": int(ok.sum()),
        "max_abs_diff": float(np.nanmax(diff)) if len(diff) else float("nan"),
        "published_negative": int((published[have] < 0).sum()),
        "published_zero": int((published[have] == 0).sum()),
        "published_positive": int((published[have] > 0).sum()),
        "loss_loans_not_in_default_pop": len(loss_loans - default_loans),
    }


def main(years: list[int]) -> int:
    rows = [reconcile(y) for y in years]
    df = pd.DataFrame(rows).set_index("year")
    pd.set_option("display.width", 200)
    print(df.T.to_string())

    total = df["published_loss_rows"].sum()
    ok = df["reconciled"].sum()
    print(f"\nreconciled {ok:,} / {total:,} ({100 * ok / total:.2f}%), "
          f"max abs diff {df['max_abs_diff'].max():.2e}")
    if df["loss_loans_not_in_default_pop"].sum():
        print(f"\nWARNING: {df['loss_loans_not_in_default_pop'].sum()} loans carry a realised "
              "loss but never reach 90+ DPD. The LGD population is not a subset of the "
              "DPD-only default population - the unlikeliness-to-pay leg is required (D8).")
    return 0 if ok == total else 1


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [2005]
    raise SystemExit(main(args))
