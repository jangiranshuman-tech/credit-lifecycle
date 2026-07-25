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

Actual Loss is populated only for zero balance codes `02`, `03`, `09`, `15`. Filtering
incorrectly biases the LGD sample.

Expenses are stored as negative values, so subtracting them adds to the loss. Pinned by
`tests/test_freddie_loss.py`.

Modification costs are excluded from Freddie's published loss field.

Loss is null for loans disposed within three months of the zero balance date.

Files are pipe-delimited with the header row removed, so columns are positional only. A
wrong position corrupts downstream results without raising an error.

Using the official 50,000-loans-per-vintage sample rather than the full dataset. It is a
documented simple random sample with identical fields, so portfolio-level estimates are
unbiased with wider standard errors. Coverage in rare segments is thin, which will show up
first in segment-level LGD.

User Guide Example 9 does not reconcile: 59,277.56 computed against 59,277.74 published, a
difference of 0.18. Example 8 reconciles exactly under the same formula, so this is either a
typo in the guide or a component mapping error. Unresolved.

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
