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