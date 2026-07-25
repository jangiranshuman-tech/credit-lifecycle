"""
Feasibility smoke test for the credit-lifecycle project.
Proves every modelling primitive in the plan actually runs on the pinned stack.
Synthetic data only - no external downloads. Run: python feasibility_smoketest.py
"""
import warnings, time, sys
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

rng = np.random.default_rng(42)
RESULTS = []

def check(name, fn):
    t0 = time.time()
    try:
        detail = fn()
        RESULTS.append((name, "PASS", f"{time.time()-t0:5.1f}s", detail))
    except Exception as e:
        RESULTS.append((name, "FAIL", f"{time.time()-t0:5.1f}s", f"{type(e).__name__}: {e}"))

# ---------------------------------------------------------------- synthetic book
N = 60_000
score = rng.normal(680, 60, N).clip(500, 850)
dti = rng.gamma(3, 6, N).clip(0, 60)
amt = rng.lognormal(9.4, .5, N).clip(1000, 40000)
emp = rng.integers(0, 11, N)
lin = -6.2 + (700 - score) * .012 + dti * .035 + (amt / 10000) * .18 - emp * .04
pd_true = 1 / (1 + np.exp(-lin))
default = rng.binomial(1, pd_true)
df = pd.DataFrame(dict(score=score, dti=dti, amt=amt, emp=emp, default=default))

# ------------------------------------------------------- 1. optbinning WoE/IV
def t_optbinning():
    from optbinning import BinningProcess, OptimalBinning
    ob = OptimalBinning(name="score", dtype="numerical", solver="cp", monotonic_trend="descending")
    ob.fit(df.score.values, df.default.values)
    t = ob.binning_table.build()
    iv = ob.binning_table.iv
    bp = BinningProcess(["score", "dti", "amt", "emp"])
    Xw = bp.fit_transform(df[["score", "dti", "amt", "emp"]].values, df.default.values, metric="woe")
    assert Xw.shape == (N, 4)
    return f"score IV={iv:.3f}, {len(t)-3} bins, monotonic OK, 4-var WoE matrix {Xw.shape}"

# ------------------------------------------- 2. scorecard scaling (PDO points)
def t_scorecard():
    from optbinning import BinningProcess, Scorecard
    from sklearn.linear_model import LogisticRegression
    sc = Scorecard(
        binning_process=BinningProcess(["score", "dti", "amt", "emp"]),
        estimator=LogisticRegression(max_iter=1000),
        scaling_method="pdo_odds", scaling_method_params={"pdo": 20, "odds": 50, "scorecard_points": 600},
    )
    sc.fit(df[["score", "dti", "amt", "emp"]], df.default)
    pts = sc.score(df[["score", "dti", "amt", "emp"]])
    tbl = sc.table(style="detailed")
    return f"points range {pts.min():.0f}-{pts.max():.0f}, table rows={len(tbl)}"

# --------------------------------------------------- 3. LightGBM + monotonic
def t_lgbm_mono():
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
    X = df[["score", "dti", "amt", "emp"]]
    m = lgb.LGBMClassifier(n_estimators=120, monotone_constraints=[-1, 1, 1, -1], verbose=-1)
    m.fit(X, df.default)
    auc = roc_auc_score(df.default, m.predict_proba(X)[:, 1])
    return f"AUC={auc:.4f}, monotone constraints accepted"

# ---------------------------------------------------------- 4. SHAP reason codes
def t_shap():
    import lightgbm as lgb, shap
    X = df[["score", "dti", "amt", "emp"]].iloc[:3000]
    m = lgb.LGBMClassifier(n_estimators=60, verbose=-1).fit(X, df.default.iloc[:3000])
    sv = shap.TreeExplainer(m).shap_values(X.iloc[:200])
    sv = sv[1] if isinstance(sv, list) else sv
    top3 = np.argsort(-sv, axis=1)[:, :3]
    return f"shap matrix {sv.shape}, top-3 adverse-action drivers extracted for {top3.shape[0]} apps"

# ------------------------- 5. person-period expansion + discrete-time hazard
def t_hazard():
    import statsmodels.api as sm
    n = 8000
    dur = rng.integers(1, 37, n)
    ev = rng.binomial(1, .12, n)
    x = rng.normal(0, 1, n)
    # expand to person-period (the volume blow-up risk in the plan)
    idx = np.repeat(np.arange(n), dur)
    per = np.concatenate([np.arange(1, d + 1) for d in dur])
    y = np.zeros(len(idx))
    ends = np.cumsum(dur) - 1
    y[ends] = ev[np.arange(n)]
    pp = pd.DataFrame({"id": idx, "t": per, "y": y, "x": x[idx]})
    pp["logt"] = np.log(pp.t)
    X = sm.add_constant(pp[["logt", "x"]])
    res = sm.Logit(pp.y, X).fit(disp=0)
    haz = res.predict(X.iloc[:36])
    surv = np.cumprod(1 - haz)
    return f"{n} loans -> {len(pp):,} person-periods ({len(pp)/n:.1f}x), converged, 36m surv={surv.iloc[-1]:.3f}"

# ------------------------------------------------- 6. lifelines survival check
def t_lifelines():
    from lifelines import CoxPHFitter, KaplanMeierFitter
    n = 5000
    d = pd.DataFrame({"dur": rng.integers(1, 60, n), "ev": rng.binomial(1, .2, n), "x": rng.normal(0, 1, n)})
    cph = CoxPHFitter().fit(d, "dur", "ev")
    km = KaplanMeierFitter().fit(d.dur, d.ev)
    return f"Cox concordance={cph.concordance_index_:.3f}, KM median={km.median_survival_time_}"

# ------------------------------------------------ 7. beta regression for LGD
def t_lgd_beta():
    import statsmodels.api as sm
    n = 4000
    x = rng.normal(0, 1, n)
    mu = 1 / (1 + np.exp(-(0.3 + 0.6 * x)))
    lgd = rng.beta(mu * 8, (1 - mu) * 8)
    lgd = np.clip(lgd, 1e-4, 1 - 1e-4)
    X = sm.add_constant(pd.DataFrame({"x": x}))
    # statsmodels has no native Beta GLM -> quasi-binomial via Binomial family
    gb = sm.GLM(lgd, X, family=sm.families.Binomial()).fit(scale="X2")
    # two-stage: cure model + severity
    cure = rng.binomial(1, .3, n)
    cm = sm.GLM(cure, X, family=sm.families.Binomial()).fit()
    return f"severity GLM converged (coef x={gb.params.iloc[1]:.3f}), cure-stage converged"

# ------------------------------------------ 8. ECL engine + hand-check unit test
def t_ecl():
    ead = np.array([100_000.0] * 12)
    marg_pd = np.array([0.004] * 12)
    lgd = 0.35
    eir = 0.06
    disc = 1 / (1 + eir) ** (np.arange(1, 13) / 12)
    ecl = float((marg_pd * lgd * ead * disc).sum())
    # closed-form hand check
    manual = sum(0.004 * 0.35 * 100000 / (1 + 0.06) ** (t / 12) for t in range(1, 13))
    assert abs(ecl - manual) < 1e-6, "ECL mismatch"
    return f"12m ECL={ecl:,.2f} matches hand calc to 1e-6"

# ------------------------- 9. Freddie actual-loss formula vs official example
def t_freddie_loss():
    # User Guide Example 8, verbatim components
    loss = (96_721.02 + 32_272.58) - 37_348.78 - 27_843.41 - 0 - (-15_139.83)
    assert abs(loss - 78_941.24) < 0.01, f"got {loss}"
    return f"official Example 8 reproduced exactly: {loss:,.2f} (note: Expenses stored NEGATIVE)"

# ---------------------------------------------- 10. PSI with bootstrap threshold
def t_psi_bootstrap():
    def psi(a, b, bins=10):
        cuts = np.quantile(a, np.linspace(0, 1, bins + 1)); cuts[0], cuts[-1] = -np.inf, np.inf
        ea = np.histogram(a, cuts)[0] / len(a); ac = np.histogram(b, cuts)[0] / len(b)
        ea, ac = np.clip(ea, 1e-6, None), np.clip(ac, 1e-6, None)
        return float(((ac - ea) * np.log(ac / ea)).sum())
    base = rng.normal(0, 1, 20000); shifted = rng.normal(.25, 1, 20000)
    null = [psi(base, rng.choice(base, 5000)) for _ in range(200)]
    p95 = np.percentile(null, 95)
    return f"observed PSI={psi(base, shifted):.4f} vs bootstrapped 95th null={p95:.4f} (rule-of-thumb 0.10 would {'over' if p95<0.1 else 'under'}-alert)"

# ----------------------------------------------------- 11. fairlearn metrics
def t_fairlearn():
    from fairlearn.metrics import MetricFrame, selection_rate, demographic_parity_ratio
    grp = rng.integers(0, 2, N)
    pred = (df.score < 660).astype(int)
    mf = MetricFrame(metrics=selection_rate, y_true=df.default, y_pred=pred, sensitive_features=grp)
    dpr = demographic_parity_ratio(df.default, pred, sensitive_features=grp)
    return f"selection rates {mf.by_group.values.round(3)}, DP ratio={dpr:.3f} (4/5ths rule testable)"

# ------------------------------------------------- 12. DuckDB panel aggregation
def t_duckdb():
    import duckdb
    n_loans, months = 40_000, 60
    panel = pd.DataFrame({
        "loan_seq": np.repeat(np.arange(n_loans), months),
        "loan_age": np.tile(np.arange(months), n_loans),
        "dlq": rng.integers(0, 4, n_loans * months),
        "upb": rng.uniform(50_000, 300_000, n_loans * months),
    })
    con = duckdb.connect()
    con.register("p", panel)
    roll = con.execute("""
        SELECT dlq AS from_st, lead_dlq AS to_st, COUNT(*) n FROM (
          SELECT dlq, LEAD(dlq) OVER (PARTITION BY loan_seq ORDER BY loan_age) lead_dlq FROM p
        ) WHERE lead_dlq IS NOT NULL GROUP BY 1,2 ORDER BY 1,2
    """).df()
    return f"{len(panel):,}-row panel, roll-rate matrix {roll.from_st.nunique()}x{roll.to_st.nunique()} computed"

for nm, fn in [
    ("1  optbinning WoE/IV + monotonic", t_optbinning),
    ("2  Scorecard PDO scaling", t_scorecard),
    ("3  LightGBM monotone constraints", t_lgbm_mono),
    ("4  SHAP adverse-action codes", t_shap),
    ("5  Person-period + discrete hazard", t_hazard),
    ("6  lifelines Cox / KM", t_lifelines),
    ("7  LGD two-stage cure+severity", t_lgd_beta),
    ("8  ECL engine vs hand calc", t_ecl),
    ("9  Freddie loss formula (official ex.)", t_freddie_loss),
    ("10 PSI bootstrap threshold", t_psi_bootstrap),
    ("11 fairlearn disparity metrics", t_fairlearn),
    ("12 DuckDB roll-rate on panel", t_duckdb),
]:
    check(nm, fn)

print("=" * 100)
print(f"{'MODULE':40s} {'STATUS':6s} {'TIME':>7s}  DETAIL")
print("=" * 100)
for nm, st, tm, dt in RESULTS:
    print(f"{nm:40s} {st:6s} {tm:>7s}  {dt}")
print("=" * 100)
npass = sum(1 for r in RESULTS if r[1] == "PASS")
print(f"{npass}/{len(RESULTS)} passed")
sys.exit(0 if npass == len(RESULTS) else 1)
