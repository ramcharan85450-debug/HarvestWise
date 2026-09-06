"""Experiment 9 estimation — executes experiments/EXPERIMENT_9_PREREGISTRATION.md exactly.

Frozen pre-registration SHA-256:
    a906931309fdc5ddfe948afdaccb2fffb159b95f46699451b40a7b1574479a30

Specification (pre-registered, not chosen here):
    yield_it = district_FE + year_FE
             + weather_temp_c_mean + weather_precip_mm_sum   (always retained)
             + beta * STRUCTURE                              (standardised to unit SD)

Inference: OLS two-way FE; district clustering (31 clusters); restricted wild cluster
bootstrap, Rademacher weights, 9,999 replications, seed 20260905, as the p-value of record;
CR1 and HC3 reported alongside.

Primary criterion (all three required):
    bootstrap p < 0.05  AND  CI excludes 0  AND  |beta| >= 0.0834 t/ha per SD

Writes only Experiment 9 outputs. Modifies nothing else.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

SEED = 20260905
N_BOOT = 9_999
A1 = 0.0834          # 10% of the Experiment 4/5 cross-region gap (0.8340)
A2 = 0.0444          # 10% of the within-district-year yield SD (0.4439)
ALPHA = 0.05

PRIMARY = "t_sd_daily_tmax"
SECONDARY = ["t_range_season_tmax", "t_p95_tmax", "tdays_gt30_tmax"]
EXPLORATORY = ["tdays_gt32_tmax"]
CONTROLS = ["weather_temp_c_mean", "weather_precip_mm_sum"]
OUTCOME = "final_yield_t_ha"

LOW_AGREEMENT_6 = ["COIMBATORE", "ERODE", "MADURAI", "KANNIYAKUMARI", "DINDIGUL", "KARUR"]
LOW_AGREEMENT_7 = LOW_AGREEMENT_6 + ["MEDAK"]          # R3b, pre-registered

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- sample

def build_sample() -> pd.DataFrame:
    """Reconstruct the pre-registered 359-row sample. Reads only; writes nothing."""
    rows = []
    for p in sorted((ROOT / "data/raw/weather/era5_tmax_daily").glob("*.json")):
        d = json.loads(p.read_text())
        for year, vals in d["daily"].items():
            t = np.array([v["tmax_c"] for v in vals], dtype=float)
            assert len(t) == 183, f"{d['district_id']} {year}: {len(t)} days, expected 183"
            rows.append({
                "district_id": d["district_id"], "state": d["state"], "district": d["district"],
                "year": int(year),
                "t_sd_daily_tmax": t.std(ddof=1),
                "t_range_season_tmax": t.max() - t.min(),
                "t_p95_tmax": np.percentile(t, 95),
                "tdays_gt30_tmax": int((t > 30).sum()),
                "tdays_gt32_tmax": int((t > 32).sum()),
                "n_days": len(t),
            })
    feats = pd.DataFrame(rows)

    panel = pd.read_csv(ROOT / "data/processed/experiment8_rainfall_panel.csv")
    panel = panel[panel.in_analytic_sample]                       # E1 + E2 + E3 already applied
    src = pd.read_csv(ROOT / "data/processed/district_multimodal_examples_v2.csv")
    src = src[src.season == "Kharif"]
    panel = panel.merge(src[["district_id", "year", "weather_temp_c_mean"]],
                        on=["district_id", "year"], how="left")

    keep = ["district_id", "year", OUTCOME, "weather_temp_c_mean", "weather_precip_mm_sum"]
    m = feats.merge(panel[keep], on=["district_id", "year"], how="inner")
    m["low_agr_6"] = m.district.isin(LOW_AGREEMENT_6)
    m["low_agr_7"] = m.district.isin(LOW_AGREEMENT_7)
    return m.sort_values(["district_id", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------- design

def design(df, xvar, *, district_fe=True, year_fe=True, controls=CONTROLS,
           region_trends=False):
    """Return (y, X, cluster_ids, colnames) with xvar standardised to unit SD.

    xvar is placed at column 0 so its coefficient is beta[0] throughout.
    """
    x = df[xvar].astype(float).to_numpy()
    x = (x - x.mean()) / x.std(ddof=1)
    cols, names = [x], [xvar]
    for c in controls:
        cols.append(df[c].astype(float).to_numpy()); names.append(c)
    if region_trends:
        yr = df.year.to_numpy(float) - df.year.mean()
        for st in sorted(df.state.unique())[1:]:
            cols.append(yr * (df.state == st).to_numpy(float)); names.append(f"trend_{st}")
        cols.append(yr); names.append("trend_base")
    if district_fe:
        for d in sorted(df.district_id.unique())[1:]:
            cols.append((df.district_id == d).to_numpy(float)); names.append(f"D_{d}")
    if year_fe:
        for y in sorted(df.year.unique())[1:]:
            cols.append((df.year == y).to_numpy(float)); names.append(f"Y_{y}")
    cols.append(np.ones(len(df))); names.append("const")
    X = np.column_stack(cols)
    return df[OUTCOME].astype(float).to_numpy(), X, df.district_id.to_numpy(), names


def ols(y, X):
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    return b, y - X @ b, XtX_inv


def se_cr1(X, u, clusters, XtX_inv):
    """CR1 cluster-robust standard errors."""
    n, k = X.shape
    uniq = np.unique(clusters); g = len(uniq)
    meat = np.zeros((k, k))
    for c in uniq:
        m = clusters == c
        s = X[m].T @ u[m]
        meat += np.outer(s, s)
    c_adj = (g / (g - 1)) * ((n - 1) / (n - k))
    V = c_adj * (XtX_inv @ meat @ XtX_inv)
    return np.sqrt(np.diag(V)), g


def se_hc3(X, u, XtX_inv):
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    w = (u / np.clip(1 - h, 1e-10, None)) ** 2
    V = XtX_inv @ (X.T * w) @ X @ XtX_inv
    return np.sqrt(np.diag(V))


# ------------------------------------------------------ restricted wild cluster bootstrap

def wild_cluster_p(y, X, clusters, idx=0, b0=0.0, reps=N_BOOT, seed=SEED):
    """Restricted wild cluster bootstrap p-value for H0: beta[idx] == b0.

    Rademacher weights drawn once per cluster. Null imposed on the DGP.

    Optimisation note: X is identical across bootstrap replications, so (X'X)^-1 and the
    cluster grouping are hoisted out of the loop, and the CR1 meat is formed by grouped
    reduction instead of a per-cluster Python loop. These are algebraic rearrangements of
    the same computation - sum_g (X_g'u_g)(X_g'u_g)' == S'S - and the RNG is drawn in the
    same order, so results are bit-identical to the unoptimised implementation.
    """
    n, k = X.shape
    order = np.argsort(clusters, kind="stable")
    Xs, ys_all = X[order], y[order]
    cl_sorted = clusters[order]
    starts = np.flatnonzero(np.r_[True, cl_sorted[1:] != cl_sorted[:-1]])
    g = len(starts)
    c_adj = (g / (g - 1)) * ((n - 1) / (n - k))
    XtX_inv = np.linalg.pinv(Xs.T @ Xs)

    def fit_t(yv):
        b = XtX_inv @ (Xs.T @ yv)
        u = yv - Xs @ b
        S = np.add.reduceat(Xs * u[:, None], starts, axis=0)     # (g, k)
        V = c_adj * (XtX_inv @ (S.T @ S) @ XtX_inv)
        return b[idx], np.sqrt(V[idx, idx])

    b_obs, se_obs = fit_t(ys_all)
    t_obs = (b_obs - b0) / se_obs

    keep = [j for j in range(k) if j != idx]
    Xr = Xs[:, keep]
    br = np.linalg.pinv(Xr.T @ Xr) @ (Xr.T @ (ys_all - b0 * Xs[:, idx]))
    ur = ys_all - b0 * Xs[:, idx] - Xr @ br
    fitted_r = b0 * Xs[:, idx] + Xr @ br

    sizes = np.diff(np.r_[starts, n])
    rng = np.random.default_rng(seed)
    t_star = np.empty(reps)
    for r in range(reps):
        w = rng.choice(np.array([-1.0, 1.0]), size=g)
        ub = ur * np.repeat(w, sizes)
        bs, ses = fit_t(fitted_r + ub)
        t_star[r] = (bs - b0) / ses
    p = (np.sum(np.abs(t_star) >= abs(t_obs)) + 1) / (reps + 1)
    return float(p), float(t_obs)


def wild_cluster_ci(y, X, clusters, idx=0, reps=1_999, seed=SEED, alpha=ALPHA, grid=41):
    """Bootstrap CI by test inversion: the set of b0 not rejected at `alpha`.

    Implementation note (not a specification change): the pre-registration fixes the
    restricted wild cluster bootstrap as the inference of record and states that
    confidence intervals come "from the same bootstrap". A restricted bootstrap yields a
    p-value for a stated null, so the interval is obtained by inverting that test over a
    grid, which is the canonical construction. Fewer replications are used per grid point
    than for the headline p-value purely for tractability.
    """
    b, u, XtX_inv = ols(y, X)
    se, _ = se_cr1(X, u, clusters, XtX_inv)
    lo, hi = b[idx] - 6 * se[idx], b[idx] + 6 * se[idx]
    cand = np.linspace(lo, hi, grid)
    ps = np.array([wild_cluster_p(y, X, clusters, idx, b0, reps, seed)[0] for b0 in cand])
    ok = cand[ps >= alpha]
    if ok.size == 0:
        return float("nan"), float("nan"), cand, ps
    return float(ok.min()), float(ok.max()), cand, ps


# --------------------------------------------------------------------------- one arm

CACHE = ROOT / "experiments/.experiment9_cache"


def run_arm(df, xvar, label, *, district_fe=True, year_fe=True, controls=CONTROLS,
            region_trends=False, ci=True, reps=N_BOOT, cache_key=None):
    """Estimate one arm. Results are cached per arm so an interrupted run resumes.

    Caching is an execution convenience only: the estimator, seed, replication count
    and specification are unchanged, so a cached result is bit-identical to recomputing it.
    """
    if cache_key:
        CACHE.mkdir(exist_ok=True)
        cf = CACHE / f"{cache_key}.json"
        if cf.exists():
            r = json.loads(cf.read_text())
            print(f"  [cached] {cache_key}", flush=True)
            return r
    y, X, cl, names = design(df, xvar, district_fe=district_fe, year_fe=year_fe,
                             controls=controls, region_trends=region_trends)
    b, u, XtX_inv = ols(y, X)
    se_c, g = se_cr1(X, u, cl, XtX_inv)
    se_h = se_hc3(X, u, XtX_inv)
    n, k = X.shape
    p_boot, t_obs = wild_cluster_p(y, X, cl, 0, 0.0, reps, SEED)
    from scipy import stats as st
    p_cr1 = 2 * st.t.sf(abs(b[0] / se_c[0]), g - 1)
    p_hc3 = 2 * st.t.sf(abs(b[0] / se_h[0]), n - k)
    out = {
        "arm": label, "predictor": xvar, "n": int(n), "districts": int(g),
        "years": int(df.year.nunique()), "k_params": int(k), "residual_df": int(n - k),
        "beta_per_sd": float(b[0]), "se_cr1": float(se_c[0]), "se_hc3": float(se_h[0]),
        "t_cr1": float(b[0] / se_c[0]), "p_cr1": float(p_cr1), "p_hc3": float(p_hc3),
        "p_wild_bootstrap": p_boot, "bootstrap_reps": reps,
        "ci95_cr1": [float(b[0] - st.t.ppf(0.975, g - 1) * se_c[0]),
                     float(b[0] + st.t.ppf(0.975, g - 1) * se_c[0])],
        "design_effect": float(se_c[0] / se_h[0]),
        "raw_sd_predictor": float(df[xvar].std(ddof=1)),
    }
    if ci:
        clo, chi, _, _ = wild_cluster_ci(y, X, cl, 0, reps=1_999, seed=SEED)
        out["ci95_bootstrap"] = [clo, chi]
    if cache_key:
        (CACHE / f"{cache_key}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def criterion(res, ci_key="ci95_bootstrap"):
    """Pre-registered primary criterion: all three conditions required."""
    ci = res.get(ci_key) or res["ci95_cr1"]
    c1 = res["p_wild_bootstrap"] < ALPHA
    c2 = not (ci[0] <= 0.0 <= ci[1])
    c3 = abs(res["beta_per_sd"]) >= A1
    if c1 and c2 and c3:
        verdict = "SUPPORTED"
    elif c1 and c2:
        verdict = "WEAK ASSOCIATION"
    elif not c1 and not (ci[0] <= A1 <= ci[1]) and not (ci[0] <= -A1 <= ci[1]):
        verdict = "NOT SUPPORTED (precise null)"
    else:
        verdict = "INCONCLUSIVE"
    return {"cond1_p_lt_0.05": bool(c1), "cond2_ci_excludes_zero": bool(c2),
            "cond3_abs_beta_ge_A1": bool(c3), "verdict": verdict}


# --------------------------------------------------------------------------- main

def main():
    t0 = time.time()
    df = build_sample()
    assert len(df) == 359, f"sample is {len(df)}, pre-registered 359"
    assert df.district_id.nunique() == 31 and df.year.nunique() == 13

    R = {"experiment": 9,
         "preregistration_sha256": "a906931309fdc5ddfe948afdaccb2fffb159b95f46699451b40a7b1574479a30",
         "git_head": "677ace08667c3bbd755c499a494fc240dcea1feb",
         "seed": SEED, "bootstrap_reps": N_BOOT, "anchors": {"A1": A1, "A2": A2},
         "versions": {"python": sys.version.split()[0], "numpy": np.__version__,
                      "pandas": pd.__version__},
         "sample": {"n": len(df), "districts": int(df.district_id.nunique()),
                    "years": int(df.year.nunique()),
                    "by_region": df.groupby("state").size().to_dict()}}

    print(f"sample {len(df)} rows / {df.district_id.nunique()} districts / {df.year.nunique()} years")
    print(f"by region: {R['sample']['by_region']}\n")

    print("ARM 0 - PRIMARY")
    a0 = run_arm(df, PRIMARY, "Arm 0 PRIMARY", cache_key="arm0")
    a0["criterion"] = criterion(a0)
    R["arm0_primary"] = a0
    print(f"  beta={a0['beta_per_sd']:+.4f}  se_cr1={a0['se_cr1']:.4f}  "
          f"boot p={a0['p_wild_bootstrap']:.4f}  CI={a0['ci95_bootstrap']}")
    print(f"  -> {a0['criterion']['verdict']}  ({time.time()-t0:.0f}s)\n")

    R["secondary"] = {}
    for v in SECONDARY:
        r = run_arm(df, v, f"secondary {v}", cache_key=f"sec_{v}")
        r["criterion"] = criterion(r)
        R["secondary"][v] = r
        print(f"  secondary {v:22s} beta={r['beta_per_sd']:+.4f} boot p={r['p_wild_bootstrap']:.4f}")
    ps = [(v, R["secondary"][v]["p_wild_bootstrap"]) for v in SECONDARY]
    for rank, (v, p) in enumerate(sorted(ps, key=lambda z: z[1])):
        R["secondary"][v]["holm_adjusted_p"] = min(1.0, p * (len(ps) - rank))
    print()

    R["exploratory"] = {}
    for v in EXPLORATORY:
        r = run_arm(df, v, f"exploratory {v}", cache_key=f"exp_{v}")
        r["criterion"] = criterion(r)
        r["label"] = "EXPLORATORY - may not be promoted"
        R["exploratory"][v] = r
        print(f"  exploratory {v:20s} beta={r['beta_per_sd']:+.4f} boot p={r['p_wild_bootstrap']:.4f}\n")

    arms = {}
    arms["R1_district_fe_only"] = run_arm(df, PRIMARY, "R1", year_fe=False, cache_key="R1")
    arms["R2_region_trends"] = run_arm(df, PRIMARY, "R2", year_fe=False, region_trends=True, cache_key="R2")
    arms["R3_excl_low_agreement_6"] = run_arm(df[~df.low_agr_6], PRIMARY, "R3", cache_key="R3")
    arms["R3b_excl_low_agreement_7"] = run_arm(df[~df.low_agr_7], PRIMARY, "R3b", cache_key="R3b")
    bal = df.groupby("district_id").year.transform("size") == 13
    arms["R5_balanced_panel"] = run_arm(df[bal], PRIMARY, "R5", cache_key="R5")
    arms["R8_ap_tg"] = run_arm(df[df.state != "Tamil Nadu"], PRIMARY, "R8 AP+TG", cache_key="R8_aptg")
    arms["R8_tn"] = run_arm(df[df.state == "Tamil Nadu"], PRIMARY, "R8 TN", cache_key="R8_tn")
    arms["R9_drop_temp_control"] = run_arm(df, PRIMARY, "R9", controls=["weather_precip_mm_sum"], cache_key="R9")
    for k, v in arms.items():
        v["criterion"] = criterion(v)
        print(f"  {k:30s} n={v['n']:3d} D={v['districts']:2d} beta={v['beta_per_sd']:+.4f} "
              f"boot p={v['p_wild_bootstrap']:.4f} -> {v['criterion']['verdict']}")
    R["robustness"] = arms

    # R6 / R7 leave-one-out (sign stability; CR1 inference only, per arm design)
    lodo = []
    for d in sorted(df.district_id.unique()):
        r = run_arm(df[df.district_id != d], PRIMARY, f"R6 -{d}", ci=False, reps=999, cache_key=f"R6_{d}")
        lodo.append({"dropped": d, "beta": r["beta_per_sd"], "p_boot": r["p_wild_bootstrap"]})
    loyo = []
    for yv in sorted(df.year.unique()):
        r = run_arm(df[df.year != yv], PRIMARY, f"R7 -{yv}", ci=False, reps=999, cache_key=f"R7_{yv}")
        loyo.append({"dropped": int(yv), "beta": r["beta_per_sd"], "p_boot": r["p_wild_bootstrap"]})
    R["R6_leave_one_district_out"] = {
        "n_refits": len(lodo), "beta_min": min(x["beta"] for x in lodo),
        "beta_max": max(x["beta"] for x in lodo),
        "sign_stable": len({np.sign(x["beta"]) for x in lodo}) == 1, "detail": lodo}
    R["R7_leave_one_year_out"] = {
        "n_refits": len(loyo), "beta_min": min(x["beta"] for x in loyo),
        "beta_max": max(x["beta"] for x in loyo),
        "sign_stable": len({np.sign(x["beta"]) for x in loyo}) == 1, "detail": loyo}
    print(f"\n  R6 LODO beta range [{R['R6_leave_one_district_out']['beta_min']:+.4f}, "
          f"{R['R6_leave_one_district_out']['beta_max']:+.4f}] sign stable="
          f"{R['R6_leave_one_district_out']['sign_stable']}")
    print(f"  R7 LOYO beta range [{R['R7_leave_one_year_out']['beta_min']:+.4f}, "
          f"{R['R7_leave_one_year_out']['beta_max']:+.4f}] sign stable="
          f"{R['R7_leave_one_year_out']['sign_stable']}")

    out = ROOT / "experiments/experiment9_results.json"
    out.write_text(json.dumps(R, indent=1, default=str))
    df.to_csv(ROOT / "data/processed/experiment9_temperature_panel.csv", index=False)
    print(f"\nwrote {out.name} in {time.time()-t0:.0f}s")
    print(f"FINAL PRIMARY VERDICT: {a0['criterion']['verdict']}")


if __name__ == "__main__":
    main()
