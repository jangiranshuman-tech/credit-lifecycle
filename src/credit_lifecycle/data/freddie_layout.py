"""
Freddie Mac SFLLD file layout.

Files are pipe-delimited .txt with the header row removed, so columns are positional:

    pd.read_csv(path, sep="|", header=None, names=ORIGINATION_COLS, low_memory=False)

Field names are from the User Guide "File Layout & Data Dictionary" section
(https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf) and were
checked against sample_orig_2005.txt and sample_svcg_2005.txt on 2026-07-25. Both
files carry exactly 32 fields and every position below was confirmed against real
rows rather than inferred from the guide alone.
"""

# ---------------------------------------------------------------- origination
# historical_data_YYYYQn.txt / sample_orig_YYYY.txt
ORIGINATION_COLS = [
    "credit_score",                  # 1   300-850, 9999 = not available
    "first_payment_date",            # 2   YYYYMM
    "first_time_homebuyer_flag",     # 3   Y / N / 9
    "maturity_date",                 # 4   YYYYMM
    "msa",                           # 5   MSA or metro division code, null = neither/unknown
    "mi_pct",                        # 6   1-55, 0 = no MI, 999 = not available
    "number_of_units",               # 7   1-4, 99 = not available
    "occupancy_status",              # 8   P / I / S / 9
    "original_cltv",                 # 9   999 = not available
    "original_dti",                  # 10  0 < DTI <= 65, 999 = not available
    "original_upb",                  # 11  rounded to nearest $1,000
    "original_ltv",                  # 12  999 = not available
    "original_interest_rate",        # 13
    "channel",                       # 14  R / B / C / T / 9
    "ppm_flag",                      # 15  Y / N
    "amortization_type",             # 16  FRM / ARM
    "property_state",                # 17
    "property_type",                 # 18  CO / PU / MH / SF / CP / 99
    "postal_code",                   # 19  first three digits + "00"
    "loan_sequence_number",          # 20  join key, e.g. F05Q10000006
    "loan_purpose",                  # 21  P / C / N / R / 9
    "original_loan_term",            # 22
    "number_of_borrowers",           # 23  01 / 02 ... 99 = not available
    "seller_name",                   # 24
    "servicer_name",                 # 25
    "super_conforming_flag",         # 26  Y / blank
    "pre_relief_refi_loan_seq_num",  # 27
    "special_eligibility_program",   # 28  H / F / R / 9
    "relief_refinance_indicator",    # 29  Y / blank
    "property_valuation_method",     # 30  1-4, 7 = not available
    "interest_only_indicator",       # 31  Y / N
    "mi_cancellation_indicator",     # 32  Y / N / 7 / 9
]

# ---------------------------------------------------------------- performance
# historical_data_time_YYYYQn.txt / sample_svcg_YYYY.txt
PERFORMANCE_COLS = [
    "loan_sequence_number",              # 1   join key
    "monthly_reporting_period",          # 2   YYYYMM
    "current_actual_upb",                # 3
    "current_loan_delinquency_status",   # 4   see DLQ notes below
    "loan_age",                          # 5
    "remaining_months_to_maturity",      # 6
    "defect_settlement_date",            # 7   if populated, ALL loss fields are null
    "modification_flag",                 # 8   Y / P / null
    "zero_balance_code",                 # 9   zero-padded two digits
    "zero_balance_effective_date",       # 10  YYYYMM
    "current_interest_rate",             # 11
    "current_non_interest_bearing_upb",  # 12
    "ddlpi",                             # 13  due date of last paid installment, YYYYMM
    "mi_recoveries",                     # 14
    "net_sale_proceeds",                 # 15  can be "U" = unknown -> parse as string
    "non_mi_recoveries",                 # 16
    "total_expenses",                    # 17  negative; equals sum of fields 18-21
    "legal_costs",                       # 18  negative
    "maintenance_and_preservation_costs",# 19  negative
    "taxes_and_insurance",               # 20  negative
    "miscellaneous_expenses",            # 21  negative
    "actual_loss_calculation",           # 22  NEGATIVE for a loss, positive for a gain
    "cumulative_modification_cost",      # 23
    "interest_rate_step_indicator",      # 24  Y / N / null
    "payment_deferral_flag",             # 25  Y / P / null
    "estimated_ltv",                     # 26  only from Apr 2017
    "zero_balance_removal_upb",          # 27  loss formula input
    "delinquent_accrued_interest",       # 28  loss formula input
    "delinquency_due_to_disaster",       # 29  only from Jan 2014
    "borrower_assistance_status_code",   # 30  F / R / T / null, only from Jan 2014
    "current_month_modification_cost",   # 31
    "interest_bearing_upb",              # 32
]

# ------------------------------------------------------------------ dtypes
# Every column is specified; unspecified ones default to float64/object and dominate.
# Measured on the 2005 vintage (3,869,881 rows), deep memory:
#     no dtypes given            1.89 GB  -> ~15.2 GB at 31M rows
#     this map with "string"     2.37 GB  -> ~18.9 GB   (object-backed: WORSE)
#     this map with pyarrow      0.87 GB  ->  ~7.0 GB
#     as Parquet on disk         0.04 GB  ->  ~0.33 GB
#
# So the full eight-vintage panel does NOT fit comfortably in pandas on a normal
# machine. Querying it from Parquet through DuckDB is a requirement, not an
# optimisation. Load into pandas only after aggregating or filtering.
#
# Money is float64, never float32. float32 carries ~7 significant digits, so a
# $450,000 balance resolves to about $0.03 and error accumulates over tens of
# millions of rows. The loss reconciliation asserts to 0.01, which float32 cannot
# support.
PERFORMANCE_DTYPES = {
    "loan_sequence_number": "string[pyarrow]",
    "monthly_reporting_period": "string[pyarrow]",              # YYYYMM, parsed downstream
    "current_actual_upb": "float64",
    "current_loan_delinquency_status": "string[pyarrow]",       # "RA"/"XX" are valid -> parse_dlq()
    "loan_age": "float32",                             # negative values occur pre-first payment
    "remaining_months_to_maturity": "float32",
    "defect_settlement_date": "string[pyarrow]",
    "modification_flag": "category",
    "zero_balance_code": "string[pyarrow]",
    "zero_balance_effective_date": "string[pyarrow]",
    "current_interest_rate": "float32",                # a rate, not money
    "current_non_interest_bearing_upb": "float64",
    "ddlpi": "string[pyarrow]",
    "mi_recoveries": "float64",
    "net_sale_proceeds": "string[pyarrow]",                     # "U" is valid -> to_amount()
    "non_mi_recoveries": "float64",
    "total_expenses": "float64",
    "legal_costs": "float64",
    "maintenance_and_preservation_costs": "float64",
    "taxes_and_insurance": "float64",
    "miscellaneous_expenses": "float64",
    "actual_loss_calculation": "float64",
    "cumulative_modification_cost": "float64",
    "interest_rate_step_indicator": "category",
    "payment_deferral_flag": "category",
    "estimated_ltv": "float32",
    "zero_balance_removal_upb": "float64",
    "delinquent_accrued_interest": "float64",
    "delinquency_due_to_disaster": "category",
    "borrower_assistance_status_code": "category",
    "current_month_modification_cost": "float64",
    "interest_bearing_upb": "float64",
}

ORIGINATION_DTYPES = {
    "credit_score": "float32",            # 9999 sentinel, cleaned downstream
    "first_payment_date": "string[pyarrow]",
    "first_time_homebuyer_flag": "category",
    "maturity_date": "string[pyarrow]",
    "msa": "string[pyarrow]",
    "mi_pct": "string[pyarrow]",                   # inconsistently padded: "000" but also "6"
    "number_of_units": "float32",
    "occupancy_status": "category",
    "original_cltv": "float32",
    "original_dti": "float32",
    "original_upb": "float64",
    "original_ltv": "float32",
    "original_interest_rate": "float32",
    "channel": "category",
    "ppm_flag": "category",
    "amortization_type": "category",
    "property_state": "category",
    "property_type": "category",
    "postal_code": "string[pyarrow]",
    "loan_sequence_number": "string[pyarrow]",
    "loan_purpose": "category",
    "original_loan_term": "float32",
    "number_of_borrowers": "float32",
    "seller_name": "category",
    "servicer_name": "category",
    "super_conforming_flag": "category",
    "pre_relief_refi_loan_seq_num": "string[pyarrow]",
    "special_eligibility_program": "category",
    "relief_refinance_indicator": "category",
    "property_valuation_method": "float32",
    "interest_only_indicator": "category",
    "mi_cancellation_indicator": "category",
}

# Numeric "not available" sentinels in the origination file. These are valid-looking
# extreme values, not nulls, so they must be cleaned or they enter models directly.
ORIGINATION_SENTINELS = {
    "credit_score": 9999,
    "original_cltv": 999,
    "original_dti": 999,
    "original_ltv": 999,
    "number_of_units": 99,
    "number_of_borrowers": 99,
    "property_valuation_method": 7,
}

# --------------------------------------------------------- delinquency status
# Field 4 is UNPADDED and alphanumeric. Observed in sample_svcg_2005.txt: "0"
# through "162", plus "RA" (REO acquisition). "XX" (unavailable) appears in some
# vintages. It counts 30-day periods delinquent under the MBA method:
#     0 = current or < 30 days     2 = 60-89 days
#     1 = 30-59 days               3 = 90-119 days   ... and so on
#
# Two traps here, and the second is worse than the first:
#   1. zero_balance_code IS zero-padded ("02", "09") while this field is not, so
#      comparing delinquency status against "03" matches nothing.
#   2. Comparing as STRINGS is lexicographic: "12" >= "3" is False, so a loan 12
#      months delinquent would be classified as performing. Always parse to a
#      number via parse_dlq() before any ordering comparison.
DLQ_CURRENT = 0
DLQ_30_DPD = 1
DLQ_90_DPD = 3            # CRR Art. 178 default threshold
DLQ_REO_ACQUISITION = -1  # sentinel for "RA" after parsing; not an ordinal bucket
DLQ_UNAVAILABLE = -2      # sentinel for "XX"

_DLQ_NON_NUMERIC = {"RA": DLQ_REO_ACQUISITION, "XX": DLQ_UNAVAILABLE}


def parse_dlq(s):
    """Delinquency status -> nullable integer, with RA/XX mapped to sentinels.

    Returns pandas Int16. Use `is_default()` rather than comparing directly, since
    the RA/XX sentinels are negative and would otherwise sort below "current".
    """
    import pandas as pd

    out = pd.Series(s, copy=False).astype("string").str.strip()
    numeric = pd.to_numeric(out, errors="coerce")
    for token, sentinel in _DLQ_NON_NUMERIC.items():
        numeric = numeric.mask(out == token, sentinel)
    return numeric.astype("Int16")


def is_default(dlq_parsed, threshold: int = DLQ_90_DPD):
    """CRR Art. 178 days-past-due leg: 90+ DPD, with REO acquisition counted as
    default. Unavailable ("XX") returns NA rather than False.

    This is only the DPD leg. Unlikeliness-to-pay is evidenced by the zero balance
    codes in LOSS_ZERO_BALANCE_CODES and must be combined with this - see
    docs/decision_log.md D8.
    """
    import pandas as pd

    d = pd.Series(dlq_parsed, copy=False)
    res = (d >= threshold) | (d == DLQ_REO_ACQUISITION)
    return res.mask(d == DLQ_UNAVAILABLE, pd.NA).astype("boolean")

# ------------------------------------------------------------ zero balance
# Zero-padded two digits.
ZB_PREPAID_OR_MATURED = "01"
ZB_THIRD_PARTY_SALE = "02"
ZB_SHORT_SALE_OR_CHARGE_OFF = "03"
ZB_REO_DISPOSITION = "09"
ZB_WHOLE_LOAN_SALE = "15"
ZB_REPERFORMING_SECURITIZATION = "16"
ZB_DEFECT = "96"

# Actual Loss and its components are populated only for these codes. The LGD
# sample must be filtered on them or it is biased.
LOSS_ZERO_BALANCE_CODES = {"02", "03", "09", "15"}

# Additional exclusions on the loss population, per the User Guide:
#   - defect_settlement_date populated  -> all loss fields null
#   - disposed within three months of the performance cutoff -> loss null
#   - modification costs are excluded from actual_loss_calculation
