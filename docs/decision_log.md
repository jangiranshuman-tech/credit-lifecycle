# Decision Log

Design decisions and the reasoning behind them, in date order. Each entry records the
options considered and what was given up.

---

## D1 · Two portfolios — Lending Club for origination, Freddie Mac for lifetime
*2026-07-25*

Lending Club carries the origination half: target definition, scorecard, reject inference,
fairness. Freddie Mac carries the lifetime half: roll rates, hazard PD, LGD, EAD, ECL.

Neither dataset supports the full lifecycle alone. Lending Club is the only public source
that publishes rejected applications, which is what makes the selection-bias work possible,
but its accepted file is a snapshot with no monthly panel — so it cannot produce roll rates,
a DPD-based SICR backstop, or recovery timing. Freddie Mac has a genuine monthly panel with
realised loss but no rejected applications.

Options considered: Lending Club only, Freddie Mac only, both.

Given up: two ingestion pipelines and two data dictionaries. The portfolios are not
reconciled to each other — the framework transfers, the parameters do not.

## D2 · Freddie Mac 50k-per-vintage sample rather than the full dataset
*2026-07-25*

Using the published sample dataset for 2005–2012 vintages, around 400,000 loans and 31M
monthly rows. It is a documented simple random sample with fields identical to the full
dataset.

Measured footprint, extrapolated from the 2005 vintage: **0.33 GB as Parquet on disk, but
~7.0 GB if loaded into pandas** even with a full dtype map using pyarrow-backed strings
(15.2 GB with no dtypes specified, and 18.9 GB with object-backed `string`, which is worse
than doing nothing). An earlier version of this entry claimed 0.66 GB in memory; that was
measured on a synthetic eight-column frame and was wrong by an order of magnitude for the
real 32-column file.

Consequence: the panel is queried from Parquet through DuckDB and only aggregated or
filtered results enter pandas. That is a requirement of the data size, not a preference.

Train on 2005–2009 vintages, out-of-time on 2010–2012 — training through the housing crash
and testing on the recovery, which is a regime shift rather than a random holdout.

Given up: thin coverage in rare segments. Loss is populated for only four zero balance
codes, so segment-level LGD in small cells will be noisy. That is the first thing to revisit
against the full dataset.

## D3 · Restrict Lending Club modelling to 2007 – 2013-11-05
*2026-07-25*

Train 2007–2012 (95,902 accepted loans), out-of-time 2013 (134,814 accepted loans).

Three independent reasons.

**Censoring.** The extract is 2018Q4. A 60-month loan issued in late 2013 matures in late
2018, so every loan in this window has a fully observed outcome. Loans issued from 2015 are
still `Current` at extract, so a binary default model trained on them fits censored labels
and understates the bad rate.

**Score comparability.** The accepted file carries FICO. The rejected file carries FICO only
until 2013-11-05, then VantageScore. Reject inference scores the rejected population using a
model fitted on accepts, which requires the same features on the same scale on both sides.

**Coverage.** 91.3% of FICO-era rejected applications carry a usable score, against 24.8%
from 2015 onward. The like-for-like measure treats the zero sentinel as missing per D5; the
raw non-null rate of 97.5% counts 86,754 rows this project classifies as unscored.

Options considered:

*Full 2007–2018 window* — fails on all three counts, most importantly because post-2015
outcomes are not observable.

*Rank-transform FICO and VantageScore onto a common percentile scale* — rejected. A
percentile transform preserves ordering only within the population transformed. Mapping two
instruments onto a common scale requires an overlap sample of borrowers scored on both, which
Lending Club does not publish. Ranking accepts and rejects separately would implicitly assume
both populations share the same underlying risk distribution, which is the quantity reject
inference exists to estimate. FICO and VantageScore also use different algorithms and
attribute weightings, so they are not monotone transforms of one another and a monotone map
cannot correct for that. Independently of the scale question, post-2015 outcomes remain
unobservable, so the transform would yield a population that still cannot be labelled.

*Include 2014* — the strongest of the alternatives. Coverage is 87% and 36-month loans issued
in 2014 mature in 2017, so those outcomes are observable. Not taken because it introduces a
second score instrument mid-development for limited marginal data. If extended, the approach
would be 2014 36-month loans only, with Vantage-era scores treated as a separate segment
rather than pooled. First candidate for revisiting.

Given up: training volume falls to 95,902 loans, around 14,000 bads at the observed rate,
which is sufficient for a scorecard but leaves early vintages thin. The selection-bias
correction is never validated on post-2014 data.

## D4 · Repurpose Lending Club 2014–2018 as the drift-monitoring population
*2026-07-25*

The 2,029,952 accepted loans from 2014–2018 are used for PSI/CSI population-stability
monitoring only — no outcome modelling, no reject inference.

Outcome labels are censored and rejected-side scores are 79–93% null from 2015, so nothing
requiring a label is defensible on this period. The accepted-side feature distribution is
fully observed, and population drift does not require outcomes. The book grew from 135,000 to
495,000 originations a year over the period, so the drift is real rather than simulated.

Options considered: discard, force into training, monitoring only.

Given up: monitoring conclusions cover population stability only, not performance decay.

## D5 · Treat `Risk_Score == 0` as missing rather than as a valid score
*2026-07-25*

86,754 FICO-era rows (6.35%) hold exactly 0. There are no other values below 300 and the
maximum is 850, so the scale is intact at the top and 0 is a sentinel rather than a score.
Retaining it moves the mean from ~638 to 597.5 and inflates the standard deviation to 169
against roughly 75 for a clean FICO distribution.

Options considered: retain as-is, set to null, impute.

Imputation deferred until the missingness mechanism is understood — if missingness is
informative, imputing would embed a bias rather than remove one.

Given up: 6.35% of FICO-era rejected applications. The missingness is not itself modelled.

## D6 · Temporal split rather than random
*2026-07-25*

Train on originations up to 2012, test on 2013. No random or stratified shuffle.

Originations are time-ordered and the book changed materially year to year, growing from 603
loans in 2007 to 134,814 in 2013 with product, channel and policy shifting throughout. A
random split would let the model see 2013 patterns while being scored on 2013, and would mix
macroeconomic regimes across train and test.

The out-of-time set is larger than the training set, which is an artefact of exponential book
growth — 2013 alone exceeds 2007–2012 combined. The split is kept at the year boundary
because moving the cut into 2013 would place adjacent months on either side and weaken the
out-of-time property.

Given up: an unbalanced split. The alternative, training on 2007–H1 2013, leaves a holdout of
only a few months within a single regime.

## D7 · Cut the accepted and rejected windows on different dates
*2026-07-26*

Accepted side ends 2013-12-31 on `issue_d`; rejected side ends 2013-11-05 on
`Application Date`.

An earlier version applied 2013-11-05 to both. That was wrong twice over. `issue_d` parses to
the first of the month, so the accepted cut silently dropped all of December 2013 — 15,020
loans, 11% of the out-of-time set, against a documented count of 134,814 that the code could
not actually produce. More fundamentally the two dates measure different events: the
FICO/VantageScore break is a property of the rejected file's application dates, while the
accepted file carries FICO throughout and is constrained instead by censoring. Loans are also
issued weeks after application, so no single date cuts both populations at the same point.

Options considered: one date for both, separate dates, reconstruct an application date for
the accepted file.

Given up: the two populations are not aligned to the same calendar instant. Reconstructing an
application date is the cleaner fix and remains open; the offset is on the order of weeks and
does not affect the era assignment.

## D8 · Define default on both CRR Art. 178 legs, not days past due alone
*2026-07-26*

Default requires 90+ DPD **or** evidence of unlikeliness to pay, the latter taken from
terminal disposition codes 02, 03, 09 and 15.

The days-past-due leg alone is insufficient and this is measurable: 16 loans in the 2005
sample carry a realised published loss without ever reaching 90+ DPD, all under code 03
(short sale or charge off). Defining default on DPD alone therefore puts part of the LGD
population outside the PD default population, so the two models would be estimated on
inconsistent samples.

Options considered: DPD only, DPD plus unlikeliness-to-pay, DPD plus a modification flag.

Given up: the default population is larger and no longer reconciles to a simple 90+ DPD
count, so the two legs have to be reported separately in validation.

## D9 · Restrict reject inference to the common support of DTI
*2026-07-26*

The instrument-comparability test that motivated D3 was initially applied only to the credit
score. Applied to DTI it produces a harder constraint.

Accepted `dti` is capped at 34.99 — that was Lending Club credit policy, and no accepted loan
exceeds 35. 20.6% of FICO-era rejected applications sit above that cap, where the accepted
sample provides no observations at all. A model fitted on accepts is unidentified there, so
inferring performance for those applicants is extrapolation beyond support rather than
inference. The rejected column additionally carries a −1 sentinel on 28,258 rows and is
uncapped to 50,000,031, and it is a different construction from the accepted figure —
self-reported at application versus computed at underwriting.

Options considered: ignore and fit anyway; restrict to common support; extrapolate with a
parametric assumption.

Given up: roughly a fifth of the rejected population cannot be assigned an inferred
performance with any credibility. Methods are restricted to parcelling and reweighting inside
the support; the excluded region is reported rather than silently modelled.

## D10 · Lending Club target is terminal outcome, not a fixed performance window
*2026-07-26*

The accepted file is a snapshot, so a fixed months-on-book performance window cannot be
constructed from it. An earlier config carried `performance_window_months: 12`, which the data
does not support. The target is terminal outcome as at the 2018Q4 extract: bad is Charged Off
or Default, good is Fully Paid, and Current, Late and In Grace Period are indeterminate and
excluded. Within the accepted window this is nearly exhaustive — 228,706 of 230,716 loans are
terminal and only 10 remain open.

Options considered: approximate a fixed window from `last_pymnt_d`; use terminal outcome with
vintage adjustment; abandon the LC scorecard.

The first was rejected because `last_pymnt_d` dates the last payment, not the charge-off, so
a reconstructed months-to-default is biased by an unknown lag.

Given up: outcome horizon varies by vintage (about 11.5 years for 2007 against 5 for 2013) and
by 36 versus 60 month term, so bad rates are not directly comparable across vintages. Handled
by vintage-level analysis and reported, not assumed away.

## D11 · Policy-code loans flagged and excluded
*2026-07-26*

2,749 loans carry a `Does not meet the credit policy. Status:X` variant — 1,988 Fully Paid and
761 Charged Off — concentrated entirely in 2007–2010 and absent from 2011 onward. In 2007 they
are 58% of the vintage.

Two reasons to handle them explicitly. A naive equality test against `"Charged Off"` labels
all 761 defaults as good. And they were originated under different policy, so they are a
structurally different population whose inclusion would contaminate the early vintages.

`add_target()` recovers the base status, sets `off_policy`, and the default treatment excludes
them. Retaining them as a flagged segment remains available.

Given up: 2,749 observations, disproportionately from the thinnest vintages.
