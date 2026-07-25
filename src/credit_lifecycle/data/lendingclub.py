"""
Lending Club loaders.

The data quirks recorded in docs/limitations.md are applied here so they cannot be
missed by downstream analysis. All figures measured on the raw files 2026-07-25.

  * Risk_Score == 0 is a missing-value sentinel (86,754 FICO-era rows).
  * Debt-To-Income Ratio on the rejected side has its own -1 sentinel (28,258 rows)
    and is uncapped, running to 50,000,031.
  * Accepted dti is hard-capped at 34.99 by credit policy, so the accepted sample
    gives no support over the 20.6% of rejects above that. This binds harder on
    reject inference than the shared-feature count does.
  * Risk_Score is FICO before 2013-11-05 and VantageScore after; the accepted file
    carries FICO throughout.
  * The accepted and rejected windows are cut on DIFFERENT date fields for
    different reasons - see config, `accepted_window` and `rejected_window`.
  * 2,749 accepted loans carry "Does not meet the credit policy" status variants,
    all issued 2007-2010.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_lifecycle.config import CFG, ROOT

LC = CFG["lendingclub"]
TGT = CFG["target_lendingclub"]

SCORE_BREAK = pd.Timestamp(LC["score_definition_break"])
SCORE_SENTINEL = LC["risk_score_missing_sentinel"]
DTI_SENTINEL = LC["dti_missing_sentinel"]
DTI_SUPPORT_MAX = LC["dti_common_support_max"]

ACCEPTED_START = pd.Timestamp(LC["accepted_window"]["start"])
ACCEPTED_END = pd.Timestamp(LC["accepted_window"]["end"])
REJECTED_START = pd.Timestamp(LC["rejected_window"]["start"])
REJECTED_END = pd.Timestamp(LC["rejected_window"]["end"])
TRAIN_END = pd.Timestamp(LC["splits"]["train_end"])
MONITOR_START = pd.Timestamp(LC["monitoring_window"]["start"])
MONITOR_END = pd.Timestamp(LC["monitoring_window"]["end"])

POLICY_PREFIX = TGT["policy_code_prefix"]

REJECTED_RENAME = {
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

REJECTED_DTYPES = {
    "Amount Requested": "float32",
    "Loan Title": "category",
    "Risk_Score": "float32",
    "Zip Code": "category",
    "State": "category",
    "Employment Length": "category",
    "Policy Code": "float32",
}

# Features present on BOTH sides. Every one needs an instrument-comparability check
# before use - see D9. `dti` in particular is not the same construction on the two
# sides and the accepted side is policy-capped.
SHARED_FEATURES = ["amount_requested", "dti", "risk_score", "employment_length", "state", "zip3"]


def _resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def clean_risk_score(s: pd.Series) -> pd.Series:
    """Replace the zero sentinel with NaN.

    86,754 FICO-era rows are exactly 0. The lowest positive value is 363 and the
    max is 850, so 0 cannot be a score. Untreated it drags the mean from ~638 to
    597.5 and inflates std to 169 against roughly 69 for the cleaned series.
    """
    return s.replace(SCORE_SENTINEL, np.nan)


def clean_rejected_dti(s: pd.Series, cap: float | None = None) -> pd.Series:
    """Replace the -1 sentinel with NaN and optionally cap extreme values.

    The rejected DTI is self-reported and uncapped: p99 is 384.63 and the maximum
    is 50,000,031. `cap` is not applied by default because truncating changes the
    reject population's shape; pass a value explicitly and record it.
    """
    out = pd.to_numeric(s, errors="coerce").replace(DTI_SENTINEL, np.nan)
    if cap is not None:
        out = out.where(out <= cap)
    return out


def in_common_support(dti: pd.Series) -> pd.Series:
    """Rows inside the accepted sample's DTI support.

    Accepted `dti` maxes at 34.99 because that was Lending Club credit policy, so a
    model fitted on accepts is not identified above it. 20.6% of FICO-era rejects
    sit outside. Reject-inference methods must either restrict to this region or
    state the extrapolation explicitly.
    """
    return pd.to_numeric(dti, errors="coerce").le(DTI_SUPPORT_MAX)


def tag_era(dates: pd.Series) -> pd.Series:
    """FICO before the break date, VantageScore after. Different instruments.

    Unparseable dates return NA rather than defaulting to one era.
    """
    d = pd.to_datetime(dates, errors="coerce")
    out = pd.Series(pd.NA, index=d.index, dtype="string")
    out[d < SCORE_BREAK] = "FICO"
    out[d >= SCORE_BREAK] = "Vantage"
    return out


def load_rejected(
    path: str | Path | None = None,
    nrows: int | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Load rejected applications with the known quirks handled.

    The full file is 27,648,741 rows. Dtypes are set on read and string columns are
    categorical; loading it without these will exhaust memory on a normal machine.
    Prefer the Parquet build for repeated work.
    """
    path = _resolve(path or LC["rejected_file"])
    usecols = list(REJECTED_RENAME) if columns is None else columns
    df = pd.read_csv(path, nrows=nrows, usecols=usecols, dtype=REJECTED_DTYPES)
    df = df.rename(columns=REJECTED_RENAME)

    df["application_date"] = pd.to_datetime(df["application_date"], errors="coerce")
    df["risk_score"] = clean_risk_score(df["risk_score"])
    df["era"] = tag_era(df["application_date"])

    if df["dti"].dtype == object:
        df["dti"] = df["dti"].astype(str).str.rstrip("%").str.strip()
    df["dti"] = clean_rejected_dti(df["dti"])
    df["dti_in_common_support"] = in_common_support(df["dti"])

    df["in_modelling_window"] = df["application_date"].between(REJECTED_START, REJECTED_END)
    return df


def load_accepted(
    path: str | Path | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Load accepted loans.

    This is a snapshot: one row per loan, `loan_status` as at the 2018Q4 extract.
    There is no monthly panel, so roll rates are computed on Freddie Mac instead.
    """
    path = _resolve(path or LC["accepted_file"])
    df = pd.read_csv(path, usecols=usecols, nrows=nrows, low_memory=False)

    if "issue_d" in df.columns:
        df["issue_date"] = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce")
        df["in_modelling_window"] = df["issue_date"].between(ACCEPTED_START, ACCEPTED_END)
        df["in_monitoring_window"] = df["issue_date"].between(MONITOR_START, MONITOR_END)

    if {"fico_range_low", "fico_range_high"}.issubset(df.columns):
        df["fico"] = (df["fico_range_low"] + df["fico_range_high"]) / 2

    if "loan_status" in df.columns:
        df = add_target(df)

    return df


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """Attach `target`, `is_indeterminate` and `off_policy` from `loan_status`.

    `loan_status` carries "Does not meet the credit policy. Status:X" variants on
    2,749 loans, all issued 2007-2010. A naive equality test against "Charged Off"
    labels the 761 charged-off ones as good. The base status is recovered and the
    row is flagged so it can be excluded or segmented deliberately.

    `target` is 1 for bad, 0 for good, NA for indeterminate.
    """
    status = df["loan_status"].astype("string")
    off_policy = status.str.startswith(POLICY_PREFIX, na=False)
    base = status.where(~off_policy, status.str.split("Status:").str[-1].str.strip())

    target = pd.Series(pd.NA, index=df.index, dtype="Int8")
    target[base.isin(TGT["bad_statuses"])] = 1
    target[base.isin(TGT["good_statuses"])] = 0

    df = df.copy()
    df["loan_status_base"] = base
    df["off_policy"] = off_policy
    df["target"] = target
    df["is_indeterminate"] = base.isin(TGT["indeterminate_statuses"])
    return df


def split_by_time(df: pd.DataFrame, date_col: str = "issue_date") -> dict[str, pd.DataFrame]:
    """Out-of-time split inside the accepted window.

    train : 2007-01-01 to 2012-12-31   (95,902 accepted)
    oot   : 2013-01-01 to 2013-12-31   (134,814 accepted)

    A random split would leak: originations are time-ordered and the book grew from
    603 loans in 2007 to 134,814 in 2013 with product, channel and policy changing
    throughout.
    """
    d = df[df[date_col].between(ACCEPTED_START, ACCEPTED_END)]
    return {"train": d[d[date_col] <= TRAIN_END], "oot": d[d[date_col] > TRAIN_END]}


def score_coverage_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage diagnostic on the rejected file. Re-run after any ingest change.

    Expects `df` from `load_rejected`, where the zero sentinel is already NaN, so
    these are null-OR-zero rates. Measured baseline: 0.062 / 0.138 / 0.168 / 0.155 /
    0.103 / 0.068 / 0.076 for 2007-2013, 0.132 in 2014, then 0.821 / 0.787 / 0.459 /
    0.932. A material departure means the ingest is wrong.
    """
    out = (
        df.assign(year=df["application_date"].dt.year)
        .groupby("year")["risk_score"]
        .agg(n="size", n_scored="count", missing_rate=lambda s: s.isna().mean())
    )
    return out.round(4)
