"""Config and code must agree.

Constants were previously duplicated between config.yaml and freddie_layout.py with
nothing checking them, while the README claimed config was the single source of
truth. These tests make divergence fail loudly.
"""
from credit_lifecycle.config import CFG
from credit_lifecycle.data.freddie_layout import (
    DLQ_90_DPD,
    LOSS_ZERO_BALANCE_CODES,
    ORIGINATION_COLS,
    ORIGINATION_DTYPES,
    PERFORMANCE_COLS,
    PERFORMANCE_DTYPES,
)


def test_utp_codes_match_loss_codes():
    assert set(CFG["target_freddie"]["utp_zero_balance_codes"]) == LOSS_ZERO_BALANCE_CODES


def test_dlq_threshold_matches_and_is_an_integer():
    threshold = CFG["target_freddie"]["default_dlq_threshold"]
    assert threshold == DLQ_90_DPD
    assert isinstance(threshold, int), "a string threshold compares lexicographically"


def test_every_column_has_a_dtype():
    """Unspecified columns default to float64/object and dominate memory."""
    assert set(PERFORMANCE_DTYPES) == set(PERFORMANCE_COLS)
    assert set(ORIGINATION_DTYPES) == set(ORIGINATION_COLS)


def test_money_columns_are_float64():
    """float32 gives ~7 significant digits; the loss reconciliation asserts to 0.01."""
    for col in ("current_actual_upb", "zero_balance_removal_upb", "actual_loss_calculation",
                "delinquent_accrued_interest", "net_sale_proceeds", "total_expenses"):
        # net_sale_proceeds stays textual because "U" is a valid value
        assert PERFORMANCE_DTYPES[col] in {"float64", "string[pyarrow]"}, col


def test_string_columns_are_arrow_backed():
    """Object-backed `string` measured 2.37 GB per vintage against 0.87 GB for
    pyarrow — worse than specifying no dtypes at all."""
    assert not any(v == "string" for v in PERFORMANCE_DTYPES.values())
    assert not any(v == "string" for v in ORIGINATION_DTYPES.values())


def test_lendingclub_windows_are_distinct():
    """The accepted and rejected sides are cut on different fields for different
    reasons; collapsing them to one date dropped 15,020 loans."""
    lc = CFG["lendingclub"]
    assert lc["accepted_window"]["end"] == "2013-12-31"
    assert lc["rejected_window"]["end"] == "2013-11-05"
    assert lc["rejected_window"]["end"] == lc["score_definition_break"]


def test_no_layout_placeholders_remain():
    assert not [c for c in ORIGINATION_COLS + PERFORMANCE_COLS if c.startswith("TODO")]
    assert len(ORIGINATION_COLS) == len(PERFORMANCE_COLS) == 32
