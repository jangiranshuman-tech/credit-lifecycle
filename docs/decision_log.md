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

Using the published sample dataset for 2005–2012 vintages, around 400,000 loans and 30M
monthly rows. It is a documented simple random sample with fields identical to the full
dataset. Measured footprint is 0.66 GB in memory with appropriate dtypes and 0.38 GB as
Parquet, with roll-rate aggregation in about a second under DuckDB.

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

**Coverage.** 97.5% of FICO-era rejected applications carry a score, against roughly 21%
from 2015 onward.

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
