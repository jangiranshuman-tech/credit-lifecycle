"""Pin the Lending Club data findings so they cannot silently regress.

These run without the raw files present - they test the transformation logic,
not the data. The observed counts from 2026-07-25 are recorded in the docstrings
so a future reader knows what the code is defending against.
"""
import numpy as np
import pandas as pd

from credit_lifecycle.data.lendingclub import (
    SCORE_BREAK,
    SENTINEL,
    clean_risk_score,
    split_by_time,
    tag_era,
)


def test_zero_sentinel_becomes_null():
    """86,754 FICO-era rows (6.35%) are exactly 0. Max is 850, no other sub-300
    values, so 0 is a sentinel not a score."""
    s = pd.Series([0, 645, 0, 720, 583])
    out = clean_risk_score(s)
    assert out.isna().sum() == 2
    assert out.dropna().tolist() == [645, 720, 583]


def test_sentinel_is_zero_not_negative():
    assert SENTINEL == 0


def test_era_split_at_documented_break():
    """FICO before 2013-11-05, VantageScore after. The accepted file is FICO,
    so only the FICO era is comparable across the accept/reject boundary."""
    dates = pd.Series(pd.to_datetime(["2013-11-04", "2013-11-05", "2013-11-06"]))
    assert tag_era(dates).tolist() == ["FICO", "Vantage", "Vantage"]
    assert SCORE_BREAK == pd.Timestamp("2013-11-05")


def test_cleaning_restores_plausible_fico_moments():
    """With 6.35% zeros the mean reads 597.5 / std 169. Dropping them should
    move the mean up and collapse the std toward a realistic FICO spread."""
    rng = np.random.default_rng(0)
    real = rng.normal(638, 75, 9365).clip(300, 850)
    contaminated = pd.Series(np.concatenate([real, np.zeros(635)]))

    assert contaminated.mean() < 620
    assert contaminated.std() > 150

    cleaned = clean_risk_score(contaminated).dropna()
    assert cleaned.mean() > 630
    assert cleaned.std() < 100


def test_split_is_temporal_not_random():
    """Train 2007-2012, out-of-time 2013. A random split leaks: originations are
    time-ordered and portfolio mix shifts materially year to year."""
    df = pd.DataFrame(
        {"issue_date": pd.to_datetime(["2011-06-01", "2012-12-31", "2013-01-01", "2013-10-01"])}
    )
    s = split_by_time(df)
    assert len(s["train"]) == 2
    assert len(s["oot"]) == 2
    assert s["train"]["issue_date"].max() < s["oot"]["issue_date"].min()


def test_modelling_window_excludes_censored_vintages():
    """Extract is 2018Q4. A 60-month loan issued after 2013 has not matured, so
    its outcome is unknowable. Those vintages must fall outside the window."""
    df = pd.DataFrame({"issue_date": pd.to_datetime(["2013-06-01", "2015-06-01", "2017-06-01"])})
    s = split_by_time(df)
    kept = pd.concat([s["train"], s["oot"]])
    assert len(kept) == 1
    assert kept["issue_date"].iloc[0].year == 2013
