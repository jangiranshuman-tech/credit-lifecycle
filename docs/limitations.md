# Known Limitations

Data and modelling constraints affecting this build. Figures measured on the raw files
carry a verification date.

---

## Lending Club

### Structure

Rejected file: 27,648,741 rows, 9 columns (measured 2026-07-25) — Amount Requested,
Application Date, Loan Title, Risk_Score, Debt-To-Income Ratio, Zip Code, State,
Employment Length, Policy Code.

Accepted file is a snapshot: one row per loan, 2,260,701 rows, 151 columns, `loan_status`
as at the 2018Q4 extract. There is no monthly performance panel, so a fixed months-on-book
performance window cannot be constructed from it. This is the reason the lifetime and ECL
modules use Freddie Mac rather than Lending Club.

Six features are common to both files: amount, DTI, risk score, employment length, state
and zip3. That count is the headline constraint on reject inference, but it is not the
binding one — see the DTI common-support problem below.

### Risk_Score

Three separate issues.

**Zero used as a missing-value sentinel.** 86,754 FICO-era rows hold exactly 0 — 6.19% of
FICO-era rows, or 6.35% of those with a non-null score. The lowest positive value is 363 and
the maximum is 850, so 0 cannot be a score. Untreated it pulls the mean from 638.0 to 597.5
and inflates the standard deviation to 169.4 against 69.3 for the cleaned series. Set to null
in `data/lendingclub.py`. Not imputed — the missingness mechanism is not established.

**Scale changes mid-series.** FICO before 2013-11-05, VantageScore after. The accepted file
carries FICO (`fico_range_low` / `fico_range_high`), so from November 2013 the accepted and
rejected populations are measured on different instruments.

**Coverage collapses in 2015, and the missingness mechanism changes with it.** Rates below
are null-or-zero, which is the like-for-like measure once the zero sentinel is recognised.
Quoting null-only rates understates pre-2015 missingness roughly tenfold and is not
comparable across the break, because there are no zeros at all from 2015 onward — the
sentinel is replaced by true nulls.

| Year | Missing | n | Year | Missing | n |
|---|---|---|---|---|---|
| 2007 | 0.062 | 5,274 | 2013 | 0.076 | 760,942 |
| 2008 | 0.138 | 25,596 | 2014 | 0.132 | 1,933,700 |
| 2009 | 0.168 | 56,991 | 2015 | 0.821 | 2,859,379 |
| 2010 | 0.155 | 112,561 | 2016 | 0.787 | 4,769,874 |
| 2011 | 0.103 | 217,792 | 2017 | 0.459 | 7,072,573 |
| 2012 | 0.068 | 337,277 | 2018 | 0.932 | 9,496,782 |

The binding constraint is a data-collection change around 2015 rather than the
FICO/VantageScore switch — coverage holds through 2014 at 13% missing, then collapses.

FICO-era usable coverage is therefore **91.28%** (1,279,817 of 1,402,039), not the 97.47%
non-null rate, which counts the 86,754 rows the project itself treats as unscored. From 2015
coverage is 24.81%.

2017 breaks the pattern at 0.459 against 0.79–0.93 either side. Non-monotonic and
unexplained; not investigated.

### Debt-To-Income Ratio — the binding constraint on reject inference

The instrument-comparability test that ruled the FICO era in must also be applied to every
other shared feature. Applied to DTI it produces a harder constraint than the score does.

Measured over the FICO era:

| | n | min | p50 | p90 | p99 | max |
|---|---|---|---|---|---|---|
| Rejected `Debt-To-Income Ratio` | 1,402,039 | −1.0 | 17.20 | 46.86 | 384.63 | 50,000,031 |
| Accepted `dti` | 230,716 | 0.0 | 16.13 | 26.72 | 33.39 | **34.99** |

Three problems:

1. The rejected column carries its own sentinel — 28,258 rows at exactly −1 — and is
   otherwise uncapped.
2. The two columns are different constructions: Lending Club computes the accepted figure at
   underwriting, while the rejected figure is self-reported at application.
3. **Accepted `dti` is hard-capped at 34.99 because that was credit policy — zero accepted
   loans sit above 35, while 20.6% of FICO-era rejects do.** A model fitted on accepts is
   therefore not identified over a fifth of the reject population. This constrains which
   reject-inference methods are defensible: parcelling and reweighting within the common
   support are, extrapolation above it is not.

### Censoring and target horizon

The extract is 2018Q4 and terms are 36 or 60 months. A 60-month loan issued in late 2013
matures in late 2018, so outcomes across 2007–2013 are effectively complete: of the 230,716
loans in the accepted window, 228,706 are terminal (192,619 Fully Paid, 35,338 Charged Off,
plus 2,749 policy-code variants) and only 10 remain open — 6 Current, 3 Late, 1 In Grace.
Loans issued from 2015 are still `Current` at extract, so a model trained on them fits
censored labels.

What censoring does **not** fix is the horizon. Because the file is a snapshot, the target is
necessarily "terminal outcome as at the extract" rather than a fixed months-on-book window.
Observation length therefore varies by vintage — around 11.5 years for 2007 against 5 years
for 2013 — and by 36 versus 60 month term within each vintage. Bad rates are consequently not
directly comparable across vintages, and this is handled by vintage-level analysis rather
than by asserting a 12-month window the data cannot support.

### Policy-code statuses

2,749 loans carry a `Does not meet the credit policy. Status:X` variant — 1,988 Fully Paid
and 761 Charged Off. They are concentrated entirely in the early vintages: 352 in 2007 (58%
of that year's 603 originations), 831 in 2008, 565 in 2009, 1,001 in 2010, and none from
2011 onward. A naive equality test against `"Charged Off"` labels all 761 defaults as good.
They are also a structurally different population, originated under different policy, so
`add_target()` recovers the base status, flags the row via `off_policy`, and the default
treatment excludes them.

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
sample run `"0"` to `"162"`, plus `"RA"` for REO acquisition (13,351 rows); `"XX"` occurs in
later vintages. It counts 30-day periods under the MBA method, so `3` is 90–119 days.

Two traps, and the second is worse than the first. `zero_balance_code` **is** zero-padded
(`"02"`, `"09"`) while this field is not, so comparing against `"03"` matches nothing. And
comparing as strings at all is lexicographic: `"12" >= "3"` is False, so a loan twelve months
delinquent classifies as performing. Parse to an integer with `freddie_layout.parse_dlq`
before any ordering comparison. Pinned by `tests/test_freddie_delinquency.py`.

The ever-default count barely moves under the string bug — 5,496 against 5,498 — because
loans that go deeply delinquent usually also reach `"RA"`, which does compare above `"3"`.
The error would instead corrupt point-in-time staging, where the comparison is applied per
reporting month rather than over a loan's history.

`net_sale_proceeds` may hold the string `"U"` for unknown, so the column cannot be parsed
as numeric on read.

Several origination fields use numeric sentinels for "not available" rather than nulls, so
they need the same treatment as the Lending Club `Risk_Score` zeros. Counts in the 2005
sample: `credit_score` 9999 on 41 rows, `original_dti` 999 on 1,532, `original_ltv` 999 on 2,
`original_cltv` 999 on 2, `number_of_units` 99 on 1, `number_of_borrowers` 99 on 11,
`property_type` 99 on 1. `mi_pct` documents 999 as its sentinel but no such rows occur in
this vintage; it is also inconsistently padded (`"000"` alongside `"6"`), so string
comparison on it is unsafe. Left untreated these enter models as extreme valid values.
Encoded in `freddie_layout.ORIGINATION_SENTINELS`.

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

Reconciliation, reproducible via `python scripts/reconcile_loss.py`: 2,702 rows in the 2005
sample carry a published loss and all 2,702 reconcile, maximum absolute difference 8.7e-11.
Of those, 2,635 are negative, 58 are strictly positive (recoveries exceeded exposure — real
gains) and 9 are exactly zero (break-even third-party sales where proceeds equalled exposure
plus accrued interest).

Blank components mean zero, not unknown, and must be coerced before arithmetic — 8 of the
2,702 rows have blank `mi_recoveries`, `non_mi_recoveries` and `total_expenses`. `"U"` in
`net_sale_proceeds` genuinely means unknown and maps to NaN instead, dropping the row from
reconciliation rather than contributing a wrong figure. Both handled in `models.loss.to_amount`.

Of 2,850 rows with a loss-eligible zero balance code, 148 have no published loss, and all 148
have `defect_settlement_date` populated. The three-month disposal cutoff excludes nothing in
this vintage. Modification costs are excluded from the published field.

**The LGD population is not a subset of the DPD default population.** 16 loans in the 2005
sample carry a realised published loss without ever reaching 90+ DPD, all under zero balance
code 03. Defining default on days-past-due alone therefore leaves realised losses outside the
default population, which is a standard validation finding. The unlikeliness-to-pay leg is
required — see decision log D8.

Both User Guide worked examples reconcile exactly. Note that the prose formula line beneath
Example 9 transcribes Zero Balance Removal UPB as 125,811.51 while the data table for that
loan gives 125,811.69; the table value is the one that reconciles.

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
