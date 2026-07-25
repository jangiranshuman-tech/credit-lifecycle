"""
Lending Club loaders.

The data quirks recorded in docs/limitations.md are applied here so they cannot be
missed by downstream analysis. Measured on the raw files 2026-07-25:

  * Risk_Score == 0 is a missing-value sentinel (86,754 FICO-era rows, 6.35%)
  * Risk_Score is FICO before 2013-11-05 and VantageScore after
  * The accepted file carries FICO throughout, so only the FICO era is comparable
    across the accept/reject boundary
  * The extract is 2018Q4, so only loans issued up to 2013 have fully observed
    outcomes; later vintages are censored
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_lifecycle.config import CFG, ROOT

LC = CFG["lendingclub"]

SCORE_BREAK = pd.Timestamp(LC["score_definition_break"])
SENTINEL = LC["risk_score_missing_sentinel"]
WINDOW_START = pd.Timestamp(LC["modelling_window"]["start"])
WINDOW_END = pd.Timestamp(LC["modelling_window"]["end"])
TRAIN_END = pd.Timestamp(LC["splits"]["train_end"])
MONITOR_START = pd.Timestamp(LC["monitoring_window"]["start"])
MONITOR_END = pd.Timestamp(LC["monitoring_window"]["end"])

# Only these columns exist in the rejected file. Verified: 27,648,741 x 9.
REJECTED_COLS = [
    "Amount Requested",
    "Application Date",
    "Loan Title",
    "Risk_Score",
    "Debt-To-Income Ratio",
    "Zip Code",
    "State",
    "Employment Length",
    "Policy Code",
]

# The 5-6 features shared with the accepted file. This is the ceiling on reject
# inference performance, independent of method.
SHARED_FEATURES = [
    "amount_requested",
    "dti",
    "risk_score",
    "employment_length",
    "state",
    "zip3",
]


def _resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def clean_risk_score(s: pd.Series) -> pd.Series:
    """Replace the zero sentinel with NaN.

    86,754 FICO-era rows are exactly 0. There are no other sub-300 values and the
    max is 850, so 0 cannot be a real score. Untreated it drags the mean from
    ~638 to 597.5 and inflates std to 169 against a healthy FICO std of ~75.
    """
    return s.replace(SENTINEL, np.nan)


def tag_era(dates: pd.Series) -> pd.Series:
    """FICO before the break date, Vantage after. Different instruments."""
    return pd.Series(
        np.where(dates < SCORE_BREAK, "FICO", "Vantage"), index=dates.index, dtype="object"
    )


def load_rejected(path: str | Path | None = None, nrows: int | None = None) -> pd.DataFrame:
    """Load the rejected-applications file with all known quirks handled.

    Returns tidy snake_case columns plus `era` and `in_modelling_window`.
    """
    path = _resolve(path or LC["rejected_file"])
    df = pd.read_csv(path, nrows=nrows, low_memory=False)

    df = df.rename(
        columns={
            "Amount Requested": "amount_requested",
            "Application Date": "application_date",
            "Loan Title": "loan_title",
            "Risk_Score": "risk_score",
            "Debt-To-Income Ratio": "dti",
            "Zip Code": "zip3",
            "State": "state",
            "Employment Length": "employment_length",
            "Policy Code": "policy_code",
        }
    )

    df["application_date"] = pd.to_datetime(df["application_date"], errors="coerce")
    df["risk_score"] = clean_risk_score(pd.to_numeric(df["risk_score"], errors="coerce"))
    df["era"] = tag_era(df["application_date"])

    # DTI arrives as a string with a trailing percent sign in some vintages.
    if df["dti"].dtype == object:
        df["dti"] = pd.to_numeric(
            df["dti"].astype(str).str.rstrip("%").str.strip(), errors="coerce"
        )

    df["in_modelling_window"] = df["application_date"].between(WINDOW_START, WINDOW_END)
    return df


def load_accepted(
    path: str | Path | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Load the accepted-loans file.

    This is a snapshot: one row per loan, `loan_status` as at the 2018Q4 extract.
    There is no monthly panel, so roll rates are computed on Freddie Mac instead.
    """
    path = _resolve(path or LC["accepted_file"])
    df = pd.read_csv(path, usecols=usecols, nrows=nrows, low_memory=False)

    if "issue_d" in df.columns:
        df["issue_date"] = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce")
        df["in_modelling_window"] = df["issue_date"].between(WINDOW_START, WINDOW_END)
        df["in_monitoring_window"] = df["issue_date"].between(MONITOR_START, MONITOR_END)

    # The accepted file carries FICO as a range; midpoint is the usual convention.
    if {"fico_range_low", "fico_range_high"}.issubset(df.columns):
        df["fico"] = (df["fico_range_low"] + df["fico_range_high"]) / 2

    return df


def split_by_time(df: pd.DataFrame, date_col: str = "issue_date") -> dict[str, pd.DataFrame]:
    """Out-of-time split inside the modelling window.

    train : 2007 - 2012  (~95,902 accepted)
    oot   : 2013         (~134,814 accepted, fully observed outcomes)

    A random split would leak: these are time-ordered originations and the
    portfolio mix changes materially year to year.
    """
    d = df[df[date_col].between(WINDOW_START, WINDOW_END)]
    return {
        "train": d[d[date_col] <= TRAIN_END],
        "oot": d[d[date_col] > TRAIN_END],
    }


def score_coverage_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the coverage diagnostic. Re-run after any ingest change.

    Expected shape: ~1-3% null 2011-2013, then a collapse to 82% in 2015.
    If this materially changes, the ingest is wrong.
    """
    out = (
        df.assign(year=df["application_date"].dt.year)
        .groupby("year")["risk_score"]
        .agg(n="size", n_scored="count", null_rate=lambda s: s.isna().mean())
    )
    return out.round(4)
