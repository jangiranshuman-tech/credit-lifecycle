"""
Freddie Mac SFLLD file layout.

CRITICAL: the files are pipe-delimited .txt with the HEADER ROW REMOVED.
Columns are identified by POSITION ONLY. Read with:

    pd.read_csv(path, sep="|", header=None, names=ORIGINATION_COLS, low_memory=False)

The field names below were verified against the official User Guide
(https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf).

>>> ACTION REQUIRED (Week 1, ~20 min) <<<
Positions marked TODO_* were not captured in my extraction. Open the User Guide,
go to the "File Layout & Data Dictionary" section, and fill them in IN ORDER.
Do NOT guess - a wrong position silently corrupts every downstream model.
Freddie also publishes a SAS parsing script on the dataset page; use it as the
authoritative field order and cross-check against what you transcribe.
"""

# --- Origination file: 32 fields (historical_data_YYYYQn.txt / sample_orig_YYYY.txt)
ORIGINATION_COLS = [
    "credit_score",              # 1  - verified
    "first_payment_date",        # 2  - verified
    "first_time_homebuyer_flag", # 3  - verified
    "maturity_date",             # 4  - verified
    "TODO_FIELD_05",             # 5
    "TODO_FIELD_06",             # 6
    "number_of_units",           # 7  - verified
    "occupancy_status",          # 8  - verified
    "TODO_FIELD_09",             # 9
    "TODO_FIELD_10",             # 10
    "original_upb",              # 11 - verified
    "TODO_FIELD_12",             # 12
    "original_interest_rate",    # 13 - verified
    "channel",                   # 14 - verified
    "TODO_FIELD_15",             # 15
    "amortization_type",         # 16 - verified
    "property_state",            # 17 - verified
    "property_type",             # 18 - verified
    "TODO_FIELD_19",             # 19
    "loan_sequence_number",      # 20 - verified (join key)
    "loan_purpose",              # 21 - verified
    "original_loan_term",        # 22 - verified
    "number_of_borrowers",       # 23 - verified
    "seller_name",               # 24 - verified
    "servicer_name",             # 25 - verified
    "TODO_FIELD_26",             # 26
    "TODO_FIELD_27",             # 27
    "TODO_FIELD_28",             # 28
    "TODO_FIELD_29",             # 29
    "TODO_FIELD_30",             # 30
    "TODO_FIELD_31",             # 31
    "mi_cancellation_indicator", # 32 - verified
]

# --- Performance file (historical_data_time_YYYYQn.txt / sample_svcg_YYYY.txt)
PERFORMANCE_COLS = [
    "loan_sequence_number",         # 1  - verified (join key)
    "TODO_FIELD_02",                # 2  (monthly reporting period)
    "current_actual_upb",           # 3  - verified
    "TODO_FIELD_04",                # 4  (current loan delinquency status - CONFIRM POSITION)
    "loan_age",                     # 5  - verified
    "remaining_months_to_maturity", # 6  - verified
    "defect_settlement_date",       # 7  - verified
    "TODO_FIELD_08",                # 8
    "zero_balance_code",            # 9  - verified
    "zero_balance_effective_date",  # 10 - verified
    "current_interest_rate",        # 11 - verified
    "TODO_FIELD_12",                # 12
    "TODO_FIELD_13",                # 13
    "mi_recoveries",                # 14 - verified
    "net_sale_proceeds",            # 15 - verified
    "non_mi_recoveries",            # 16 - verified
    "total_expenses",               # 17 - verified  (STORED NEGATIVE)
    "legal_costs",                  # 18 - verified
    "TODO_FIELD_19",                # 19
    "TODO_FIELD_20",                # 20
    "miscellaneous_expenses",       # 21 - verified
    "actual_loss_calculation",      # 22 - verified
    # fields 23-30 TODO
    "current_month_modification_cost",  # 31 - verified
    "interest_bearing_upb",             # 32 - verified
]

# Memory-safe dtypes. Cast on ingest or the panel is 2.4x larger than it needs to be.
PERFORMANCE_DTYPES = {
    "current_actual_upb": "float32",
    "loan_age": "int16",
    "remaining_months_to_maturity": "float32",
    "current_interest_rate": "float32",
}

# Actual Loss is ONLY populated for these zero balance codes. Filter or your LGD is biased.
LOSS_ZERO_BALANCE_CODES = {"02", "03", "09", "15"}