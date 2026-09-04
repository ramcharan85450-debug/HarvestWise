"""
Experiment 6, Checkpoint 6 — approved two-period within-district analysis.

Runs EXACTLY the design approved at Checkpoint 5. No specification is added,
removed or searched after the fact.

DESIGN (approved)
    Convention C, two-period within-district.
    P1: irrigation Fasli 1414 (2004-05)  ->  yield Kharif 2004
    P2: irrigation Fasli 1421 (2011-12)  ->  yield Kharif 2011

    First difference (equivalently two-way district+period FE):
        d_yield = a + b*d_pct_net_irrigated + g1*d_non_rice_cropped_area
                    + g2*d_n_crops_grown + e
    N = 27 districts. HC3 primary; restricted wild bootstrap (Rademacher,
    9999) for inference given the small N.

WHAT THIS DESIGN CANNOT DO
    `is_tn` is time-invariant and absorbed by district fixed effects, so the
    region coefficient is inestimable and Experiment 5's incremental statistic
    is not computable here. Experiment 6 answers a DIFFERENT question:
    do within-district CHANGES in irrigation track CHANGES in yield?

PRE-REGISTERED ANCHOR
    Regional gap +0.8340 t/ha (Exp 5 beta_A); TN minus AP+TG irrigation share
    in 2004-05 = 14.27 pp. An effect fully accounting for the regional gap
    would be b ~ 0.0584 t/ha per percentage point. Reported against the CI.

LANGUAGE
    Every result is an ASSOCIATION. A 27-district two-period observational
    panel does not support a causal claim.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.tamil_nadu_overlap_extract import DISTRICT_ALIASES  # noqa: E402

V2 = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
COV = ROOT / "data" / "raw" / "external" / "district_covariates" / "district_agricultural_covariates.csv"
PANEL = ROOT / "data" / "raw" / "external" / "district_irrigation" / "irrigation_panel_2year.csv"
OUT = ROOT / "experiments" / "experiment6_results.json"

TARGET = "final_yield_t_ha"
IRR = "pct_net_irrigated_to_net_area_sown"
COVS = ["non_rice_cropped_area_ha", "n_crops_grown"]
P1_YEAR, P2_YEAR = 2004, 2011
ANCHOR = 0.8340 / 14.27          # t/ha per pp that would account for the whole regional gap
SEED = 20260904
N_BOOT = 9999


# ------------------------------------------------------------------ helpers
def ols(X, y):
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    # HC3
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    omega = (e / (1 - h)) ** 2
    V = XtX_inv @ (X.T * omega) @ X @ XtX_inv
    se = np.sqrt(np.diag(V))
    r2 = 1 - float(e @ e) / float(((y - y.mean()) ** 2).sum())
    return b, se, e, r2, n, k


def wild_bootstrap_p(X, y, idx, reps=N_BOOT, seed=SEED):
    """Restricted wild bootstrap (Rademacher) for H0: beta[idx] == 0."""
    rng = np.random.default_rng(seed)
    b_full, se_full, _, _, n, k = ols(X, y)
    t_obs = b_full[idx] / se_full[idx]
    keep = [j for j in range(X.shape[1]) if j != idx]
    Xr = X[:, keep]
    br, _, er, _, _, _ = ols(Xr, y)
    fitted_r = Xr @ br
    cnt = 0
    for _ in range(reps):
        v = rng.choice([-1.0, 1.0], size=n)
        ystar = fitted_r + er * v
        bs, ses, _, _, _, _ = ols(X, ystar)
        if abs(bs[idx] / ses[idx]) >= abs(t_obs):
            cnt += 1
    return float(t_obs), float((cnt + 1) / (reps + 1))


def build_two_period():
    y = pd.read_csv(V2)
    y = y[y.weather_available & y.satellite_available & y.soil_available]
    y = y[(y.season == "Kharif") & (y.year.between(2000, 2012))].copy()

    cov = pd.read_csv(COV)
    cov["district"] = cov["district"].replace(DISTRICT_ALIASES)
    cov["year"] = cov["year"].astype(int)
    y = y.merge(cov[["state", "district", "year", "season"] + COVS],
                on=["state", "district", "year", "season"], how="left")
    y["du"] = y["district"].str.upper().str.strip()

    pan = pd.read_csv(PANEL)
    irr = pan.pivot_table(index="canonical_district", columns="year", values=IRR)
    reg = pan.drop_duplicates("canonical_district").set_index("canonical_district")["region"]

    rows = []
    for d in sorted(irr.index):
        for period, yr, icol in ((1, P1_YEAR, "2004-05"), (2, P2_YEAR, "2011-12")):
            yy = y[(y.du == d) & (y.year == yr)]
            if yy.empty or pd.isna(irr.loc[d, icol]):
                continue
            rows.append({
                "district": d, "region": reg.get(d), "period": period, "yield_year": yr,
                "irrigation_year": icol, IRR: float(irr.loc[d, icol]),
                TARGET: float(yy[TARGET].mean()),
                COVS[0]: float(yy[COVS[0]].mean()), COVS[1]: float(yy[COVS[1]].mean()),
            })
    return pd.DataFrame(rows)


def differences(long: pd.DataFrame) -> pd.DataFrame:
    both = long.groupby("district")["period"].nunique()
    keep = both[both == 2].index
    w = long[long.district.isin(keep)]
    p1 = w[w.period == 1].set_index("district")
    p2 = w[w.period == 2].set_index("district")
    d = pd.DataFrame({
        "region": p1["region"],
        "d_yield": p2[TARGET] - p1[TARGET],
        "d_irr": p2[IRR] - p1[IRR],
        f"d_{COVS[0]}": p2[COVS[0]] - p1[COVS[0]],
        f"d_{COVS[1]}": p2[COVS[1]] - p1[COVS[1]],
    }).dropna()
    return d


def fit_fd(d: pd.DataFrame, label="primary"):
    X = np.column_stack([np.ones(len(d)), d["d_irr"].to_numpy(float),
                         d[f"d_{COVS[0]}"].to_numpy(float), d[f"d_{COVS[1]}"].to_numpy(float)])
    yv = d["d_yield"].to_numpy(float)
    b, se, e, r2, n, k = ols(X, yv)
    tcrit = stats.t.ppf(0.975, n - k)
    out = {
        "label": label, "n": int(n),
        "beta_irrigation": float(b[1]), "se_hc3": float(se[1]),
        "ci95_hc3": [float(b[1] - tcrit * se[1]), float(b[1] + tcrit * se[1])],
        "t_hc3": float(b[1] / se[1]),
        "p_hc3": float(2 * (1 - stats.t.cdf(abs(b[1] / se[1]), n - k))),
        "period_effect_intercept": float(b[0]),
        "coef_d_non_rice_cropped_area_ha": float(b[2]),
        "coef_d_n_crops_grown": float(b[3]),
        "r2": float(r2),
    }
    return out, X, yv


def main():
    res = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "Experiment 6 - two-period within-district irrigation analysis",
        "design": "Convention C; P1 = irrigation 2004-05 / yield Kharif 2004; P2 = irrigation 2011-12 / yield Kharif 2011",
        "cannot_answer": ("is_tn is time-invariant and absorbed by district fixed effects, so the "
                          "region coefficient is inestimable and Experiment 5's incremental "
                          "statistic is not computable in this design."),
        "language": "All results are ASSOCIATIONS; no causal claim is supported.",
        "pre_registered_anchor_t_ha_per_pp": ANCHOR,
    }

    long = build_two_period()
    d = differences(long)
    res["sample"] = {
        "long_rows": int(len(long)), "n_first_differences": int(len(d)),
        "by_region": {k: int(v) for k, v in d["region"].value_counts().items()},
    }
    print(f"long rows {len(long)} | first differences N={len(d)}")
    print("  by region:", d["region"].value_counts().to_dict())
    print(f"  d_irr: mean {d.d_irr.mean():+.2f} sd {d.d_irr.std():.2f} "
          f"range [{d.d_irr.min():+.2f}, {d.d_irr.max():+.2f}]")
    print(f"  d_yield: mean {d.d_yield.mean():+.3f} sd {d.d_yield.std():.3f}")

    # ---------------- primary ----------------
    prim, X, yv = fit_fd(d, "primary")
    t_obs, p_wild = wild_bootstrap_p(X, yv, idx=1)
    prim["t_observed"] = t_obs
    prim["p_wild_bootstrap"] = p_wild
    prim["n_boot"] = N_BOOT
    res["primary"] = prim
    print("\n=== PRIMARY (first difference, N=%d) ===" % prim["n"])
    print(f"  beta_irrigation = {prim['beta_irrigation']:+.5f} t/ha per pp")
    print(f"  HC3 SE {prim['se_hc3']:.5f}  95% CI [{prim['ci95_hc3'][0]:+.5f}, {prim['ci95_hc3'][1]:+.5f}]")
    print(f"  t = {prim['t_hc3']:+.3f}   p(HC3) = {prim['p_hc3']:.4f}   p(wild bootstrap) = {p_wild:.4f}")
    print(f"  period effect (intercept) = {prim['period_effect_intercept']:+.4f} t/ha")
    print(f"  R2 = {prim['r2']:.4f}")

    # ---------------- R1 FD vs two-way FE equivalence ----------------
    both = long.groupby("district")["period"].nunique()
    w = long[long.district.isin(both[both == 2].index)].copy()
    dm = w.copy()
    for c in [TARGET, IRR] + COVS:
        dm[c] = dm[c] - dm.groupby("district")[c].transform("mean")
        dm[c] = dm[c] - dm.groupby("period")[c].transform("mean")
    Xf = np.column_stack([dm[IRR].to_numpy(float), dm[COVS[0]].to_numpy(float),
                          dm[COVS[1]].to_numpy(float)])
    bf, _, _, _, _, _ = ols(Xf, dm[TARGET].to_numpy(float))
    res["R1_fd_vs_twoway_fe"] = {
        "fd_beta": prim["beta_irrigation"], "twoway_fe_beta": float(bf[0]),
        "abs_difference": abs(prim["beta_irrigation"] - float(bf[0])),
        "equivalent": bool(abs(prim["beta_irrigation"] - float(bf[0])) < 1e-8),
    }
    print(f"\nR1 FD vs two-way FE: {prim['beta_irrigation']:+.6f} vs {float(bf[0]):+.6f} "
          f"(equivalent={res['R1_fd_vs_twoway_fe']['equivalent']})")

    # ---------------- R2 alternative outcome: P1 = mean(Kharif 2004,2005) ----------------
    y = pd.read_csv(V2)
    y = y[y.weather_available & y.satellite_available & y.soil_available]
    y = y[(y.season == "Kharif")].copy()
    cov = pd.read_csv(COV); cov["district"] = cov["district"].replace(DISTRICT_ALIASES)
    cov["year"] = cov["year"].astype(int)
    y = y.merge(cov[["state", "district", "year", "season"] + COVS],
                on=["state", "district", "year", "season"], how="left")
    y["du"] = y["district"].str.upper().str.strip()
    alt = long.copy()
    p1alt = (y[y.year.isin([2004, 2005])].groupby("du")[[TARGET] + COVS].mean())
    alt2 = alt.copy()
    for i, r in alt2.iterrows():
        if r["period"] == 1 and r["district"] in p1alt.index:
            alt2.at[i, TARGET] = p1alt.loc[r["district"], TARGET]
            alt2.at[i, COVS[0]] = p1alt.loc[r["district"], COVS[0]]
            alt2.at[i, COVS[1]] = p1alt.loc[r["district"], COVS[1]]
    d2 = differences(alt2)
    r2fit, _, _ = fit_fd(d2, "R2_alt_outcome_P1_mean_2004_2005")
    res["R2_alternative_outcome"] = r2fit
    print(f"R2 alt outcome (P1 = mean Kharif 2004,2005): beta {r2fit['beta_irrigation']:+.5f} "
          f"CI [{r2fit['ci95_hc3'][0]:+.5f}, {r2fit['ci95_hc3'][1]:+.5f}] N={r2fit['n']}")

    # ---------------- R3 leave-one-district-out ----------------
    lodo = []
    for dd in d.index:
        f, _, _ = fit_fd(d.drop(index=dd), f"without_{dd}")
        lodo.append({"district_left_out": dd, "beta": f["beta_irrigation"], "p_hc3": f["p_hc3"]})
    lo = pd.DataFrame(lodo)
    res["R3_leave_one_district_out"] = {
        "n_folds": len(lo), "beta_min": float(lo.beta.min()), "beta_max": float(lo.beta.max()),
        "beta_median": float(lo.beta.median()),
        "n_folds_sign_flip": int((np.sign(lo.beta) != np.sign(prim["beta_irrigation"])).sum()),
        "n_folds_p_below_05": int((lo.p_hc3 < 0.05).sum()),
        "most_influential": lo.reindex(lo.beta.sub(prim["beta_irrigation"]).abs()
                                       .sort_values(ascending=False).index).head(3).to_dict("records"),
    }
    print(f"R3 LODO: beta range [{lo.beta.min():+.5f}, {lo.beta.max():+.5f}] "
          f"sign flips {res['R3_leave_one_district_out']['n_folds_sign_flip']}/{len(lo)} "
          f"| folds p<0.05: {res['R3_leave_one_district_out']['n_folds_p_below_05']}/{len(lo)}")

    # ---------------- R4 AP 2011-12 rounding sensitivity (+/- 500 ha) ----------------
    pan = pd.read_csv(PANEL)
    ap11 = pan[(pan.year == "2011-12") & (pan.region != "Tamil Nadu")]
    sens = {}
    for delta in (-500, 500):
        adj = d.copy()
        for dd in adj.index:
            row = ap11[ap11.canonical_district == dd]
            if row.empty:
                continue
            net = float(row.net_irrigated_area_ha.iloc[0]); sown = float(row.net_area_sown_ha.iloc[0])
            if sown and sown > 0:
                new_pct = (net + delta) / sown * 100
                adj.at[dd, "d_irr"] = adj.at[dd, "d_irr"] + (new_pct - float(row[IRR].iloc[0]))
        f, _, _ = fit_fd(adj, f"rounding_{delta:+d}ha")
        sens[f"{delta:+d}_ha"] = {"beta": f["beta_irrigation"], "ci95_hc3": f["ci95_hc3"]}
        print(f"R4 AP rounding {delta:+d} ha: beta {f['beta_irrigation']:+.5f}")
    res["R4_ap_rounding_sensitivity"] = sens

    # ---------------- R5 TN only (net published directly in both years) ----------------
    tn = d[d.region == "Tamil Nadu"]
    if len(tn) >= 6:
        f, _, _ = fit_fd(tn, "R5_tn_only")
        res["R5_tn_only"] = f
        print(f"R5 TN only (N={f['n']}): beta {f['beta_irrigation']:+.5f} "
              f"CI [{f['ci95_hc3'][0]:+.5f}, {f['ci95_hc3'][1]:+.5f}]")
    else:
        res["R5_tn_only"] = {"status": "insufficient N"}

    # ---------------- pre-registered verdict ----------------
    lo95, hi95 = prim["ci95_hc3"]
    sig = (prim["p_hc3"] < 0.05) and (p_wild < 0.05)
    ci_contains_zero = lo95 <= 0 <= hi95
    ci_contains_anchor = lo95 <= ANCHOR <= hi95
    sign_stable = res["R3_leave_one_district_out"]["n_folds_sign_flip"] == 0

    if sig and prim["beta_irrigation"] > 0 and sign_stable:
        verdict = "MEANINGFUL SUPPORT"
    elif ci_contains_zero and ci_contains_anchor:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "LITTLE OR NO SUPPORT"

    res["verdict"] = {
        "beta": prim["beta_irrigation"], "ci95_hc3": [lo95, hi95],
        "p_hc3": prim["p_hc3"], "p_wild_bootstrap": p_wild,
        "significant_both_methods": bool(sig),
        "ci_contains_zero": bool(ci_contains_zero),
        "ci_contains_regional_gap_anchor": bool(ci_contains_anchor),
        "anchor": ANCHOR, "sign_stable_in_lodo": bool(sign_stable),
        "FINAL": verdict,
    }
    print("\n=== PRE-REGISTERED VERDICT ===")
    print(f"  beta {prim['beta_irrigation']:+.5f}  CI [{lo95:+.5f}, {hi95:+.5f}]")
    print(f"  p(HC3) {prim['p_hc3']:.4f}  p(wild) {p_wild:.4f}")
    print(f"  CI contains 0: {ci_contains_zero}   CI contains anchor {ANCHOR:.4f}: {ci_contains_anchor}")
    print(f"  sign stable across LODO: {sign_stable}")
    print(f"  FINAL: {verdict}")

    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT}")
    return res


if __name__ == "__main__":
    main()
