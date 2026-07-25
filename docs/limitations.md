# Known Limitations

Data and modelling constraints affecting this build. Figures measured on the raw files
carry a verification date.

---

## Lending Club

### Structure

Rejected file: 27,648,741 rows, 9 columns (measured 2026-07-25) — Amount Requested,
Application Date, Loan Title, Risk_Score, Debt-To-Income Ratio, Zip Code, State,
Employment Length, Policy Code.

Accepted file is a snapshot: one row per loan, ~2.26M rows, ~145 columns, `loan_status`
as at the 2018Q4 extract. There is no monthly performance panel, so loan duration has to
be reconstructed from `issue_d` to `last_pymnt_d` and is approximate. This is the reason
the lifetime and ECL modules use Freddie Mac rather than Lending Club.

Around 5–6 features are common to both files: amount, DTI, state/zip3, employment length,
risk score. This caps achievable reject inference performance regardless of method.

### Risk_Score

Three separate issues.

**Zero used as a missing-value sentinel.** 86,754 FICO-era rows (6.35%) hold exactly 0.
There are no other values below 300 and the maximum is 850. Untreated, this pulls the mean
from ~638 to 597.5 and inflates the standard deviation to 169 against roughly 75 for a
clean FICO distribution. Set to null in `src/credit_lifecycle/data/lendingclub.py`. Not
imputed — the missingness mechanism is not established.

**Scale changes mid-series.** FICO before 2013-11-05, VantageScore after. The accepted file
carries FICO (`fico_range_low` / `fico_range_high`), so from November 2013 the accepted and
rejected populations are measured on different instruments.

**Coverage collapses in 2015.** Null rate for `Risk_Score` by application year
(measured 2026-07-25):

| Year | Null rate | Year | Null rate |
|---|---|---|---|
| 2007 | 0.020 | 2013 | 0.031 |
| 2008 | 0.098 | 2014 | 0.132 |
| 2009 | 0.109 | 2015 | 0.821 |
| 2010 | 0.071 | 2016 | 0.787 |
| 2011 | 0.013 | 2017 | 0.459 |
| 2012 | 0.013 | 2018 | 0.932 |

The binding constraint is a data-collection change around 2015 rather than the
FICO/VantageScore switch — coverage holds through 2014 at 13% null, then collapses.

2017 breaks the pattern at 0.459 against 0.79–0.93 either side. Non-monotonic and
unexplained; not investigated.

### Censoring

The extract is 2018Q4 and terms are 36 or 60 months. A 60-month loan issued in late 2013
matures in late 2018, so outcomes are fully observed across 2007–2013. Loans issued from
2015 are still `Current` at extract and their final outcome is unknown, so a binary default
model trained on those rows is fitting censored labels.

### Selection

These are Lending Club applicants, not a general credit population. Platform marketing,
channel mix and eligibility rules all shape who appears in the data. Results require
restatement before transferring to a bank's through-the-door population.

---

## Freddie Mac

Agency-conforming universe only, so not representative of subprime. Loss experience is
materially milder than a subprime book would show.

### Field formats

Files are pipe-delimited with the header row removed, so columns are positional only. A
wrong position corrupts downstream results without raising an error. Both origination and
performance files carry exactly 32 fields, verified against `sample_orig_2005.txt` and
`sample_svcg_2005.txt` on 2026-07-25.

`current_loan_delinquency_status` is **unpadded** alphanumeric. Observed values in the 2005
sample run `"0"` to `"162"`, plus `"RA"` for REO acquisition. It counts 30-day periods under
the MBA method, so `"3"` is 90–119 days. `zero_balance_code` by contrast **is** zero-padded
(`"02"`, `"09"`). Comparing delinquency status against `"03"` matches nothing and fails
silently.

`net_sale_proceeds` may hold the string `"U"` for unknown, so the column cannot be parsed
as numeric on read.

Several origination fields use numeric sentinels for "not available" rather than nulls, so
they need the same treatment as the Lending Club `Risk_Score` zeros. In the 2005 sample:
`credit_score` uses 9999 (41 rows), `original_dti` uses 999 (1,532 rows), `original_ltv`
and `original_cltv` use 999 (2 rows), `mi_pct` uses 999, `number_of_units` and
`number_of_borrowers` use 99, `property_type` uses 99. Left untreated these enter models as
extreme valid values.

### Sample composition (2005 vintage, verified 2026-07-25)

50,000 loans in the origination file and 50,000 in the performance file, 3,869,881
performance rows, averaging 77.4 months per loan. Extrapolating to the eight vintages
2005–2012 gives roughly 400,000 loans and 31M performance rows.

Zero balance codes: `01` prepaid or matured 45,091; `09` REO disposition 1,585; `16`
reperforming securitization 695; `03` short sale or charge off 657; `02` third party sale
447; `15` whole loan sale 161; `96` defect 112. So 90% of the book prepays or matures, and
the loss-eligible population is 2,850 rows of which 2,702 carry a populated loss — the
remaining 148 are the defect and three-month-cutoff exclusions.

5,498 loans of 50,000 (11.0%) reach 90+ days delinquent at some point, and 1,596 reach REO
acquisition.

### Loss data

Actual Loss is populated only for zero balance codes `02`, `03`, `09`, `15`. Filtering
incorrectly biases the LGD sample.

Two sign conventions, both established against real rows:

- Total expenses and its components (legal, maintenance, taxes, miscellaneous) are stored
  **negative**, so subtracting them increases the loss.
- Freddie's published `actual_loss_calculation` is stored **negative for a loss** and
  positive for a gain. `models/loss.py` returns a positive magnitude, so reconciliation is
  against the negated published field.

Reconciliation result: 2,702 rows in the 2005 sample carry a published loss, and the
computed value matches all 2,702 to within 0.01. Of those, 67 have a positive published
value — recoveries exceeded exposure, which are genuine gains rather than sign errors.

Loss is also null where `defect_settlement_date` is populated, and for loans disposed within
three months of the performance cutoff. Modification costs are excluded from the published
field.

User Guide Example 9 does not reconcile: 59,277.56 computed against 59,277.74 published, a
difference of 0.18. Example 8 reconciles exactly under the same formula, and the formula
reconciles against real data at 100%, so the discrepancy appears to be an error in the guide.

### Sampling

Using the official 50,000-loans-per-vintage sample rather than the full dataset. It is a
documented simple random sample with identical fields, so portfolio-level estimates are
unbiased with wider standard errors. Coverage in rare segments is thin, which will show up
first in segment-level LGD.

---

## Modelling

Reject inference is scoped to the FICO era, so the selection-bias correction is not
validated on post-2014 data.

Early Lending Club vintages are small — 603 loans in 2007 rising to 12,537 in 2010 — so
segment-level results in those years are noisy.

Fairness analysis uses geography-derived proxies for protected attributes. Proxies are not
the attributes, and the direction of bias under proxy error is not established. HMDA is the
appropriate dataset for this and is out of scope for the current build.

The rank-transform alternative to the FICO-era restriction (D2 in the decision log) was
rejected on reasoning rather than tested empirically.
