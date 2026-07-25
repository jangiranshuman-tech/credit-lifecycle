# Decision Log

One entry per non-obvious choice. This file is a hiring signal on its own -
it shows you reason about trade-offs rather than accepting defaults.

| Date | Decision | Options considered | Why | Trade-off accepted |
|---|---|---|---|---|
| 2026-07-25 | Two portfolios: Lending Club for origination, Freddie Mac for lifetime | (a) LC only (b) Freddie only (c) both | LC is the only public source with rejected applications; LC has no monthly panel so it cannot support hazard/staging. Freddie has a true panel but no rejects. | Extra ingestion work; two data dictionaries to learn |
| 2026-07-25 | Freddie official 50k/vintage sample rather than full dataset | full download vs sample | Documented simple random sample, identical fields, 30M rows fits in 0.66 GB | Thinner tails for rare-segment LGD |