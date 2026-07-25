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
# Cast on ingest. Verified footprint at these dtypes: ~30M rows in 0.66 GB.
PERFORMANCE_DTYPES = {
    "loan_sequence_number": "string",
    "current_actual_upb": "float32",
    "current_loan_delinquency_status": "string",  # not numeric: "RA" is a valid value
    "loan_age": "int16",
    "remaining_months_to_maturity": "float32",
    "zero_balance_code": "string",
    "current_interest_rate": "float32",
    "net_sale_proceeds": "string",                # not numeric: "U" is a valid value
}

ORIGINATION_DTYPES = {
    "loan_sequence_number": "string",
    "credit_score": "float32",   # 9999 sentinel, cleaned downstream
    "original_upb": "float32",
    "original_ltv": "float32",
    "original_cltv": "float32",
    "original_dti": "float32",
    "original_interest_rate": "float32",
    "original_loan_term": "int16",
}

# --------------------------------------------------------- delinquency status
# Field 4 is UNPADDED and alphanumeric. Observed values in sample_svcg_2005.txt:
# "0" through "162", plus "RA" (REO acquisition). It is the count of 30-day
# periods delinquent under the MBA method, so:
#     "0" = current or < 30 days      "2" = 60-89 days
#     "1" = 30-59 days                "3" = 90-119 days   ... and so on
# Note the contrast with zero_balance_code, which IS zero-padded ("02", "09").
# Comparing against "03" will silently match nothing.
DLQ_CURRENT = "0"
DLQ_30_DPD = "1"
DLQ_90_DPD = "3"          # CRR Art. 178 default threshold
DLQ_REO_ACQUISITION = "RA"

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
