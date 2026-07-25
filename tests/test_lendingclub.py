"""Pins the Lending Club data findings so they cannot silently regress.

These run without the raw files present - they test transformation logic, not data.
Observed counts from 2026-07-25 are given in docstrings so a reader knows what the
code is defending against.
"""
import numpy as np
import pandas as pd

from credit_lifecycle.data.lendingclub import (
    ACCEPTED_END,
    DTI_SUPPORT_MAX,
    SCORE_BREAK,
    SCORE_SENTINEL,
    add_target,
    clean_rejected_dti,
    clean_risk_score,
    in_common_support,
    split_by_time,
    tag_era,
)


def test_zero_sentinel_becomes_null():
    """86,754 FICO-era rows are exactly 0. Lowest positive value is 363, max 850."""
    out = clean_risk_score(pd.Series([0, 645, 0, 720, 583]))
    assert out.isna().sum() == 2
    assert out.dropna().tolist() == [645, 720, 583]
    assert SCORE_SENTINEL == 0


def test_rejected_dti_sentinel_and_outliers():
    """28,258 FICO-era rows are exactly -1; max is 50,000,031."""
    s = pd.Series([-1.0, 17.2, 384.63, 50_000_031.49, -1.0])
    out = clean_rejected_dti(s)
    assert out.isna().sum() == 2
    assert out.max() == 50_000_031.49          # not capped unless asked
    assert clean_rejected_dti(s, cap=100).max() == 17.2


def test_common_support_reflects_accepted_policy_cap():
    """Accepted dti is capped at 34.99 by credit policy - no accepted loan above 35.
    20.6% of FICO-era rejects sit outside, where the model is unidentified."""
    assert DTI_SUPPORT_MAX == 34.99
    got = in_common_support(pd.Series([10.0, 34.99, 35.01, 46.86]))
    assert got.tolist() == [True, True, False, False]


def test_era_split_at_documented_break():
    dates = pd.Series(pd.to_datetime(["2013-11-04", "2013-11-05", "2013-11-06"]))
    assert tag_era(dates).tolist() == ["FICO", "Vantage", "Vantage"]
    assert SCORE_BREAK == pd.Timestamp("2013-11-05")


def test_unparseable_date_is_na_not_vantage():
    """np.where would silently tag NaT as Vantage."""
    assert pd.isna(tag_era(pd.Series([pd.NaT])).iloc[0])


def test_cleaning_restores_plausible_fico_moments():
    """With the zeros in, mean reads 597.5 and std 169; cleaned it is ~638 / ~69."""
    rng = np.random.default_rng(0)
    contaminated = pd.Series(np.concatenate([rng.normal(638, 69, 9381).clip(363, 850),
                                             np.zeros(619)]))
    assert contaminated.mean() < 620 and contaminated.std() > 150
    cleaned = clean_risk_score(contaminated).dropna()
    assert cleaned.mean() > 630 and cleaned.std() < 100


def test_accepted_window_includes_december_2013():
    """Regression: the window was cut at 2013-11-05 against issue_d, which parses to
    the 1st of the month, silently dropping all of December 2013 - 15,020 loans,
    11% of the out-of-time set."""
    assert ACCEPTED_END == pd.Timestamp("2013-12-31")
    df = pd.DataFrame({"issue_date": pd.to_datetime(["2013-11-01", "2013-12-01"])})
    s = split_by_time(df)
    assert len(s["oot"]) == 2


def test_split_is_temporal_not_random():
    df = pd.DataFrame({"issue_date": pd.to_datetime(
        ["2011-06-01", "2012-12-01", "2013-01-01", "2013-12-01"])})
    s = split_by_time(df)
    assert len(s["train"]) == 2 and len(s["oot"]) == 2
    assert s["train"]["issue_date"].max() < s["oot"]["issue_date"].min()


def test_window_excludes_censored_vintages():
    """Extract is 2018Q4, so a 60-month loan issued after 2013 has not matured."""
    df = pd.DataFrame({"issue_date": pd.to_datetime(
        ["2013-06-01", "2015-06-01", "2017-06-01"])})
    s = split_by_time(df)
    kept = pd.concat([s["train"], s["oot"]])
    assert len(kept) == 1 and kept["issue_date"].iloc[0].year == 2013


def test_off_policy_charged_off_is_labelled_bad():
    """2,749 loans carry a policy-code status variant, all issued 2007-2010; 761 are
    charged off. A naive equality test on loan_status labels those as good."""
    df = pd.DataFrame({"loan_status": [
        "Charged Off",
        "Fully Paid",
        "Does not meet the credit policy. Status:Charged Off",
        "Does not meet the credit policy. Status:Fully Paid",
        "Current",
    ]})
    out = add_target(df)
    assert out["target"].tolist()[:4] == [1, 0, 1, 0]
    assert pd.isna(out["target"].iloc[4])
    assert out["off_policy"].tolist() == [False, False, True, True, False]
    assert out["is_indeterminate"].tolist() == [False, False, False, False, True]


def test_naive_equality_would_have_been_wrong():
    """Demonstrates the bug being defended against."""
    s = pd.Series(["Does not meet the credit policy. Status:Charged Off"])
    assert (s == "Charged Off").sum() == 0
    assert add_target(pd.DataFrame({"loan_status": s}))["target"].iloc[0] == 1
