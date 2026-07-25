# credit-lifecycle

End-to-end credit decisioning and expected-credit-loss platform: application
scorecard with reject inference, calibrated PD term structure, LGD/EAD,
IFRS 9 **and** CECL ECL under macroeconomic scenarios, fair-lending analysis
with adverse-action reason codes - served, monitored, and documented to
SR 11-7 / EBA standard.

> Status: scaffolding. Started 2026-07-25.

## Portfolios

| Dataset | Role |
|---|---|
| Lending Club (accepted + rejected) | Origination: target definition, scorecard, reject inference, fairness |
| Freddie Mac SFLLD (2005-2012 sample) | Lifetime: roll rates, hazard PD, LGD from actual loss, EAD, ECL |
| FRED | Macro conditioning and scenarios |

### Lending Club modelling window: 2007 – Nov 2013

Three independent reasons, measured on the raw files:

1. **Censoring.** The extract is 2018Q4. A 60-month loan issued in late 2013 has matured,
   so outcomes across this window are fully observed. Loans issued from 2015 are still
   `Current`, so a model trained on them fits censored labels.
2. **Score comparability.** The accepted file carries FICO; the rejected file carries FICO
   only until 2013-11-05, then VantageScore. Reject inference requires both sides on the
   same instrument.
3. **Coverage.** 97.5% of FICO-era rejected applications carry a score, against roughly
   21% from 2015 onward.

Splits: train 2007–2012 (95,902 loans), out-of-time 2013 (134,814 loans). The 2,029,952
loans from 2014–2018 cannot support reject inference or outcome modelling, so they serve as
the drift-monitoring population for PSI/CSI.

Reasoning and rejected alternatives in [`docs/decision_log.md`](docs/decision_log.md);
data and modelling constraints in [`docs/limitations.md`](docs/limitations.md).

## Quickstart

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest -q
```

## Layout

```
config/     single source of truth - no magic numbers in notebooks
data/       raw | interim | processed   (all gitignored)
src/        library code
notebooks/  exploration only; anything reusable moves to src/
tests/      including formula pins against official worked examples
docs/       model development document, validation report, decision log
reports/    figures and outputs
```

## Documentation

- `docs/decision_log.md` - why each non-obvious choice was made
- `docs/limitations.md` - known data and model weaknesses, stated upfront