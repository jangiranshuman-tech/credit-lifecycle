"""Delinquency status parsing.

The field is unpadded alphanumeric ("0".."162", plus "RA" and "XX"). Comparing it
as a string is lexicographic, so "12" >= "3" is False and a loan twelve months
delinquent reads as performing. These tests exist so that regression cannot recur.
"""
import pandas as pd

from credit_lifecycle.data.freddie_layout import (
    DLQ_90_DPD,
    DLQ_REO_ACQUISITION,
    DLQ_UNAVAILABLE,
    is_default,
    parse_dlq,
)


def test_string_comparison_is_wrong():
    """Demonstrates the bug being defended against, so the reason is self-evident."""
    raw = pd.Series(["0", "1", "2", "3", "9", "10", "12", "162", "RA"])
    lexicographic = raw[raw >= "3"].tolist()
    assert lexicographic == ["3", "9", "RA"]        # "10", "12", "162" wrongly excluded
    assert "12" not in lexicographic


def test_parse_orders_numerically():
    parsed = parse_dlq(pd.Series(["0", "1", "3", "10", "12", "162"]))
    assert parsed.tolist() == [0, 1, 3, 10, 12, 162]
    assert parsed.dtype == "Int16"


def test_deep_delinquency_is_default():
    """The case the string comparison got wrong."""
    parsed = parse_dlq(pd.Series(["0", "2", "3", "10", "12", "162"]))
    assert is_default(parsed).tolist() == [False, False, True, True, True, True]


def test_reo_acquisition_counts_as_default():
    parsed = parse_dlq(pd.Series(["RA"]))
    assert parsed.iloc[0] == DLQ_REO_ACQUISITION
    assert bool(is_default(parsed).iloc[0]) is True


def test_unavailable_is_na_not_false():
    """"XX" means unknown. Treating it as performing would understate default."""
    parsed = parse_dlq(pd.Series(["XX"]))
    assert parsed.iloc[0] == DLQ_UNAVAILABLE
    assert pd.isna(is_default(parsed).iloc[0])


def test_threshold_matches_crr_178():
    """90-119 days past due is bucket 3 under the MBA method."""
    assert DLQ_90_DPD == 3
    assert is_default(parse_dlq(pd.Series(["2"]))).iloc[0] is False or not bool(
        is_default(parse_dlq(pd.Series(["2"]))).iloc[0]
    )
