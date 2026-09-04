"""
Experiment 8 analysis, executed exactly as pre-registered in
experiments/EXPERIMENT_8_PREREGISTRATION.md.

Stages, run in the pre-registered order:

    screens   ICC and region-proxy diagnostics for all five block variables.
              A variable with ICC > 0.90 is a district fingerprint and is
              EXCLUDED from the primary model - the rule that disqualified
              seasonal mean temperature at Checkpoint 1. Published before any
              model is fitted, so the exclusion cannot be chosen to suit a
              result.
    panel     Apply exclusions E1/E2/E3 and write the separate Experiment 8
              dataset. The main modelling datasets are never touched.
    primary   Arm 0, run exactly once: two-way fixed effects, seasonal
              rainfall total always retained, 5 df joint Wald on the block,
              restricted wild cluster bootstrap (Rademacher, 9,999 reps).
    robust    Arms 1-8.

Nothing here may be re-specified after results are seen. The thresholds,
variables, exclusions and specifications are fixed by the pre-registration.

Run:
    python -m experiments.run_experiment8_analysis --stage screens
    python -m experiments.run_experiment8_analysis --stage panel
    python -m experiments.run_experiment8_analysis --stage primary
    python -m experiments.run_experiment8_analysis --stage robust
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ROOT / "data" / "processed" / "experiment8_rainfall_features.csv"
PANEL_OUT = ROOT / "data" / "processed" / "experiment8_rainfall_panel.csv"
RESULTS = ROOT / "experiments" / "experiment8_results.json"

# --- pre-registered constants; do not edit after results are seen ----------
BLOCK = ["precip_anomaly_z", "rain_days", "max_dry_spell_days", "precip_cv_10day", "onset_day"]
CONTROL = "weather_precip_mm_sum"
TARGET = "final_yield_t_ha"
ANCHOR_A1 = 0.10 * 0.8340      # 0.0834 t/ha per SD - Exp 4/5 cross-region gap
ANCHOR_A2 = 0.10 * 0.4439      # 0.0444 t/ha per SD - within-district yield SD
ICC_FINGERPRINT = 0.90
KS_SCREEN, SMD_SCREEN = 0.95, 3.0
INCR_R2_THRESHOLD = 0.031
N_BOOT = 9999
SEED = 20260904
# E1: rows whose modern polygon post-dates the yield record's boundary
E1_SPLITS = {"DHARMAPURI": 2004, "COIMBATORE": 2009, "ERODE": 2009}


# ---------------------------------------------------------------- screens --
def icc(df: pd.DataFrame, col: str) -> float:
    """Between-district share of total variance. High ICC = the variable is
    mostly district identity, i.e. a location fingerprint."""
    s = df[["district_id", col]].dropna()
    gm = s.groupby("district_id")[col].transform("mean")
    ssb = ((gm - s[col].mean()) ** 2).sum()
    ssw = ((s[col] - gm) ** 2).sum()
    return float(ssb / (ssb + ssw))


def region_proxy(df: pd.DataFrame, col: str) -> tuple[float, float]:
    a = df.loc[df["state"] == "Tamil Nadu", col].dropna()
    b = df.loc[df["state"] != "Tamil Nadu", col].dropna()
    ks = float(stats.ks_2samp(a, b).statistic)
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return ks, float((a.mean() - b.mean()) / sp)


def run_screens() -> dict:
    df = pd.read_csv(FEATURES)
    df = df[df["status"] == "OBSERVED"]
    out = {}
    print(f"{'variable':22s} {'ICC':>6s} {'within%':>8s} {'KS':>7s} {'SMD':>8s}  verdict")
    for c in BLOCK + [CONTROL]:
        i = icc(df, c)
        ks, smd = region_proxy(df, c)
        fp = i > ICC_FINGERPRINT
        rp = ks >= KS_SCREEN or abs(smd) >= SMD_SCREEN
        verdict = "EXCLUDE (fingerprint)" if fp else ("EXCLUDE (region proxy)" if rp else "PASS")
        out[c] = {"icc": i, "within_pct": 100 * (1 - i), "ks": ks, "smd": smd,
                  "fingerprint_fail": bool(fp), "region_proxy_fail": bool(rp), "verdict": verdict}
        print(f"{c:22s} {i:6.3f} {100*(1-i):7.1f}% {ks:7.3f} {smd:8.3f}  {verdict}")
    return out


# ------------------------------------------------------------------ panel --
def build_panel(screens: dict) -> pd.DataFrame:
    df = pd.read_csv(FEATURES)
    df = df[df["status"] == "OBSERVED"].copy()
    n0 = len(df)

    m = pd.Series(False, index=df.index)
    for dist, yr in E1_SPLITS.items():
        m |= (df["district"] == dist) & (df["year"] < yr)
    df["e1_boundary_mismatch"] = m
    kept = df[~m]
    cnt = kept.groupby("district_id").size()
    singles = set(cnt[cnt < 2].index)
    df["e2_singleton"] = df["district_id"].isin(singles)
    df["in_analytic_sample"] = ~df["e1_boundary_mismatch"] & ~df["e2_singleton"]

    print(f"start {n0} -> E1 drops {int(m.sum())} -> E2 drops {int((df['e2_singleton']).sum())} "
          f"-> analytic {int(df['in_analytic_sample'].sum())}")
    df.to_csv(PANEL_OUT, index=False)
    print(f"wrote {PANEL_OUT}")
    return df


# ------------------------------------------------------------------ model --
def design(df: pd.DataFrame, block: list[str], year_fe: bool, region_trends: bool = False):
    """Returns (y, X, colnames, block index positions). Fixed effects as
    explicit dummies - exact, and with 31 districts x 13 years there is no
    reason to approximate."""
    d = df.copy()
    cols, mats = [], []
    mats.append(np.ones((len(d), 1))); cols.append("const")
    Z = d[[CONTROL] + block].to_numpy(dtype=float)
    mats.append(Z); cols += [CONTROL] + block
    dd = pd.get_dummies(d["district_id"], prefix="d", drop_first=True).to_numpy(dtype=float)
    mats.append(dd); cols += [f"d{i}" for i in range(dd.shape[1])]
    if year_fe:
        yd = pd.get_dummies(d["year"], prefix="y", drop_first=True).to_numpy(dtype=float)
        mats.append(yd); cols += [f"y{i}" for i in range(yd.shape[1])]
    if region_trends:
        t = (d["year"] - d["year"].min()).to_numpy(dtype=float)
        for st in sorted(d["state"].unique())[:-1]:
            mats.append(((d["state"] == st).to_numpy(dtype=float) * t).reshape(-1, 1))
            cols.append(f"trend_{st}")
    X = np.hstack(mats)
    y = d[TARGET].to_numpy(dtype=float)
    bidx = [cols.index(b) for b in block]
    return y, X, cols, bidx


def ols(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return beta, resid


def vcov_cluster(X, resid, groups):
    """CR1 cluster-robust covariance."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        s = groups == g
        u = X[s].T @ resid[s]
        meat += np.outer(u, u)
    G, n, k = len(np.unique(groups)), X.shape[0], np.linalg.matrix_rank(X)
    c = (G / (G - 1)) * ((n - 1) / (n - k))
    return c * XtX_inv @ meat @ XtX_inv


def vcov_hc3(X, resid):
    XtX_inv = np.linalg.pinv(X.T @ X)
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    w = (resid / np.clip(1 - h, 1e-10, None)) ** 2
    return XtX_inv @ (X.T * w) @ X @ XtX_inv


def wald(beta, V, bidx):
    b = beta[bidx]
    Vb = V[np.ix_(bidx, bidx)]
    return float(b @ np.linalg.pinv(Vb) @ b)


def wild_cluster_joint_p(y, X, groups, bidx, reps=N_BOOT, seed=SEED):
    """Restricted wild cluster bootstrap (Rademacher) for the joint null that
    every block coefficient is zero. The null is IMPOSED: the bootstrap DGP is
    the restricted fit, so the reference distribution is the distribution of
    the statistic when H0 is true."""
    rng = np.random.default_rng(seed)
    keep = [j for j in range(X.shape[1]) if j not in bidx]
    Xr = X[:, keep]
    beta_r, resid_r = ols(y, Xr)
    fit_r = Xr @ beta_r

    beta, resid = ols(y, X)
    W_obs = wald(beta, vcov_cluster(X, resid, groups), bidx)

    uniq = np.unique(groups)
    gi = {g: (groups == g) for g in uniq}
    count = 0
    for _ in range(reps):
        w = rng.choice([-1.0, 1.0], size=len(uniq))
        ystar = fit_r.copy()
        for k, g in enumerate(uniq):
            ystar[gi[g]] += resid_r[gi[g]] * w[k]
        b_s, r_s = ols(ystar, X)
        if wald(b_s, vcov_cluster(X, r_s, groups), bidx) >= W_obs:
            count += 1
    return W_obs, (count + 1) / (reps + 1)


def within_r2(y, X, bidx):
    """Incremental R-squared of the block, computed on the fixed-effect
    residualised outcome so it is a WITHIN measure, not inflated by the
    variance the fixed effects already explain."""
    keep = [j for j in range(X.shape[1]) if j not in bidx]
    _, r_res = ols(y, X[:, keep])
    _, r_full = ols(y, X)
    ss_res = (r_res ** 2).sum()
    return float((ss_res - (r_full ** 2).sum()) / ss_res)


def fit_arm(df, block, year_fe=True, region_trends=False, boot=False, label=""):
    y, X, cols, bidx = design(df, block, year_fe, region_trends)
    groups = df["district_id"].to_numpy()
    beta, resid = ols(y, X)
    Vc = vcov_cluster(X, resid, groups)
    Vh = vcov_hc3(X, resid)
    G = df["district_id"].nunique()
    tcrit = stats.t.ppf(0.975, G - 1)
    se_c = np.sqrt(np.diag(Vc)); se_h = np.sqrt(np.diag(Vh))
    XtX_inv = np.linalg.pinv(X.T @ X)
    s2 = (resid ** 2).sum() / (len(y) - np.linalg.matrix_rank(X))
    se_iid = np.sqrt(np.diag(s2 * XtX_inv))

    coefs = {}
    for b in block:
        j = cols.index(b)
        coefs[b] = {
            "beta": float(beta[j]),
            "se_cluster": float(se_c[j]), "se_hc3": float(se_h[j]), "se_iid": float(se_iid[j]),
            "design_effect": float(se_c[j] / se_iid[j]),
            "ci_low": float(beta[j] - tcrit * se_c[j]), "ci_high": float(beta[j] + tcrit * se_c[j]),
            "p_cluster": float(2 * (1 - stats.t.cdf(abs(beta[j] / se_c[j]), G - 1))),
        }
    W = wald(beta, Vc, bidx)
    res = {
        "label": label, "n": int(len(y)), "districts": int(G), "years": int(df["year"].nunique()),
        "year_fe": year_fe, "region_trends": region_trends,
        "control_beta": float(beta[cols.index(CONTROL)]),
        "joint_wald": W,
        "joint_p_chi2": float(1 - stats.chi2.cdf(W, len(block))),
        "incremental_within_r2": within_r2(y, X, bidx),
        "coefficients": coefs,
    }
    if boot:
        _, p = wild_cluster_joint_p(y, X, groups, bidx)
        res["joint_p_wild_bootstrap"] = p
        res["bootstrap_reps"] = N_BOOT
    return res


def decision(primary: dict, arms: dict) -> dict:
    p = primary.get("joint_p_wild_bootstrap", primary["joint_p_chi2"])
    r2 = primary["incremental_within_r2"]
    any_meaningful = any(
        abs(c["beta"]) >= ANCHOR_A1 and (c["ci_low"] > 0 or c["ci_high"] < 0)
        for c in primary["coefficients"].values())
    all_exclude_a1 = all(
        not (c["ci_low"] <= ANCHOR_A1 <= c["ci_high"] or c["ci_low"] <= -ANCHOR_A1 <= c["ci_high"])
        for c in primary["coefficients"].values())
    contains_both = any(
        (c["ci_low"] <= 0 <= c["ci_high"]) and
        (c["ci_low"] <= ANCHOR_A1 <= c["ci_high"] or c["ci_low"] <= -ANCHOR_A1 <= c["ci_high"])
        for c in primary["coefficients"].values())

    if p < 0.05 and r2 >= INCR_R2_THRESHOLD and any_meaningful:
        outcome = "MEANINGFUL SUPPORT"
    elif p < 0.05:
        outcome = "WEAK SUPPORT"
    elif all_exclude_a1:
        outcome = "NO SUPPORT (precise null)"
    elif contains_both:
        outcome = "INCONCLUSIVE"
    else:
        outcome = "INCONCLUSIVE"
    return {"outcome": outcome, "joint_p_used": p, "incremental_within_r2": r2,
            "any_coefficient_at_or_above_A1_with_ci_excluding_zero": bool(any_meaningful),
            "all_cis_exclude_A1": bool(all_exclude_a1),
            "some_ci_contains_both_zero_and_A1": bool(contains_both),
            "anchor_A1": ANCHOR_A1, "anchor_A2": ANCHOR_A2}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items); out = {}; prev = 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p)); prev = adj; out[k] = adj
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["screens", "panel", "primary", "robust"])
    args = ap.parse_args()
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}

    if args.stage == "screens":
        res["screens"] = run_screens()
        res["screens_note"] = (
            "Published BEFORE any model was fitted. A variable with ICC > 0.90 is excluded "
            "from the primary model as a district fingerprint; a variable failing KS >= 0.95 "
            "or |SMD| >= 3 is excluded from cross-region interpretation.")

    elif args.stage == "panel":
        df = build_panel(res.get("screens", {}))
        res["panel"] = {
            "rows_features": int(len(df)),
            "e1_dropped": int(df["e1_boundary_mismatch"].sum()),
            "e2_dropped": int(df["e2_singleton"].sum()),
            "analytic_n": int(df["in_analytic_sample"].sum()),
            "analytic_districts": int(df.loc[df["in_analytic_sample"], "district_id"].nunique()),
            "analytic_years": int(df.loc[df["in_analytic_sample"], "year"].nunique()),
            "by_state": df[df["in_analytic_sample"]].groupby("state").size().to_dict(),
        }
        print(json.dumps(res["panel"], indent=1))

    elif args.stage == "primary":
        df = pd.read_csv(PANEL_OUT)
        a = df[df["in_analytic_sample"]].copy()
        block = [b for b in BLOCK if not res["screens"][b]["fingerprint_fail"]]
        excluded = [b for b in BLOCK if b not in block]
        print(f"block entering primary model ({len(block)}): {block}")
        if excluded:
            print(f"EXCLUDED by pre-registered screen: {excluded}")
        for b in block:
            a[b] = (a[b] - a[b].mean()) / a[b].std(ddof=1)
        res["primary_block"] = block
        res["primary_block_excluded"] = excluded
        print("running Arm 0 (this is the single pre-registered primary run)...")
        arm0 = fit_arm(a, block, year_fe=True, boot=True, label="Arm 0 PRIMARY: two-way FE")
        arm0["holm_adjusted_p"] = holm({k: v["p_cluster"] for k, v in arm0["coefficients"].items()})
        res["arm0_primary"] = arm0
        res["decision"] = decision(arm0, {})
        print(json.dumps({k: v for k, v in arm0.items() if k != "coefficients"}, indent=1))
        for k, v in arm0["coefficients"].items():
            print(f"  {k:22s} beta={v['beta']:+.4f}  CI[{v['ci_low']:+.4f},{v['ci_high']:+.4f}]  "
                  f"DE={v['design_effect']:.2f}  p={v['p_cluster']:.4f}")
        print(f"\nDECISION: {res['decision']['outcome']}")

    elif args.stage == "robust":
        df = pd.read_csv(PANEL_OUT)
        block = res["primary_block"]
        arms = {}

        def std(frame):
            f = frame.copy()
            for b in block:
                f[b] = (f[b] - f[b].mean()) / f[b].std(ddof=1)
            return f

        a = std(df[df["in_analytic_sample"]])
        arms["arm1_district_fe_only"] = fit_arm(a, block, year_fe=False, label="Arm 1: district FE only")
        arms["arm2_region_trends"] = fit_arm(a, block, year_fe=False, region_trends=True,
                                             label="Arm 2: district FE + region linear trends")
        arms["arm3_include_e1"] = fit_arm(std(df[~df["e2_singleton"]]), block, year_fe=True,
                                          label="Arm 3: include the 22 E1 boundary rows")
        full = df[df["in_analytic_sample"]]
        cnt = full.groupby("district_id")["year"].nunique()
        bal = full[full["district_id"].isin(cnt[cnt == 13].index)]
        arms["arm4_balanced"] = fit_arm(std(bal), block, year_fe=True,
                                        label=f"Arm 4: balanced panel ({bal['district_id'].nunique()} districts)")

        lodo = {}
        for d in sorted(full["district_id"].unique()):
            s = std(full[full["district_id"] != d])
            r = fit_arm(s, block, year_fe=True, label=f"drop {d}")
            lodo[d] = {k: v["beta"] for k, v in r["coefficients"].items()} | {"joint_wald": r["joint_wald"]}
        arms["arm5_leave_one_district_out"] = {
            "n_refits": len(lodo),
            "beta_range": {b: [min(v[b] for v in lodo.values()), max(v[b] for v in lodo.values())] for b in block},
            "per_district": lodo}

        loyo = {}
        for yv in sorted(full["year"].unique()):
            s = std(full[full["year"] != yv])
            r = fit_arm(s, block, year_fe=True, label=f"drop {yv}")
            loyo[int(yv)] = {k: v["beta"] for k, v in r["coefficients"].items()} | {"joint_wald": r["joint_wald"]}
        arms["arm6_leave_one_year_out"] = {
            "n_refits": len(loyo),
            "beta_range": {b: [min(v[b] for v in loyo.values()), max(v[b] for v in loyo.values())] for b in block},
            "per_year": loyo}

        alt = full.copy()
        alt["rain_days"] = alt["rain_days_1mm"]
        alt["max_dry_spell_days"] = alt["max_dry_spell_days_1mm"]
        arms["arm7_threshold_1mm"] = fit_arm(std(alt), block, year_fe=True,
                                             label="Arm 7: 1 mm rain-day threshold")

        within = {}
        for name, sub in [("AP_TG", full[full["state"] != "Tamil Nadu"]),
                          ("TN", full[full["state"] == "Tamil Nadu"])]:
            within[name] = fit_arm(std(sub), block, year_fe=True, label=f"Arm 8: {name} only")
        arms["arm8_within_region"] = within

        res["robustness_arms"] = arms
        for k, v in arms.items():
            if "joint_wald" in v:
                print(f"{k:34s} n={v['n']:4d} W={v['joint_wald']:7.3f} p_chi2={v['joint_p_chi2']:.4f} "
                      f"incrR2={v['incremental_within_r2']:.4f}")
            elif "beta_range" in v:
                print(f"{k:34s} {v['n_refits']} refits")
            else:
                for kk, vv in v.items():
                    print(f"{k}/{kk:22s} n={vv['n']:4d} W={vv['joint_wald']:7.3f} "
                          f"p_chi2={vv['joint_p_chi2']:.4f} incrR2={vv['incremental_within_r2']:.4f}")

    RESULTS.write_text(json.dumps(res, indent=1))
    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
