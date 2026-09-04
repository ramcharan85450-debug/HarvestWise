"""
Experiment 5, Checkpoint 8 — approved primary analysis ONLY.

Runs exactly the three pre-registered models on the approved 378-row common
sample. No alternative specification is searched, no variable is added after
seeing results, no transformation or outlier rule is changed.

APPROVED CONVENTIONS
  D-A  Irrigation enters as a STATIC DISTRICT-LEVEL ATTRIBUTE: each district's
       observed 2004-05 / Fasli 1414 value is applied across its 2000-2012
       rows. This is an ASSUMPTION OF APPROXIMATE TEMPORAL STABILITY. The
       irrigation variable is NOT annually observed over 2000-2012 and is
       never described as such.
  D-B  Both plain OLS and district-clustered standard errors are reported.
       Plain SEs exist for comparability with Experiment 4; the PRIMARY
       precision verdict uses the DISTRICT-CLUSTERED SEs, because `is_tn` and
       the irrigation variable are both constant within district, so the
       effective number of independent units is 31 districts, not 378 rows.

LANGUAGE
  Every result is an ASSOCIATION. A fall in the Tamil Nadu coefficient means
  irrigation ACCOUNTS FOR part of the observed regional association. It is not
  evidence that irrigation CAUSED the regional yield difference.
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
TER = ROOT / "data" / "raw" / "external" / "district_covariates" / "district_terrain.csv"
IRR = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv"
MAP = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"
OUT = ROOT / "experiments" / "experiment5_primary_results.json"

TARGET = "final_yield_t_ha"
B_COVS = ["non_rice_cropped_area_ha", "n_crops_grown", "elevation_m_mean", "slope_deg_mean"]
IRR_VAR = "pct_net_irrigated_to_net_area_sown"

# Pre-registered thresholds. Fixed before any Model C coefficient existed.
THRESH_MEANINGFUL = 10.0
THRESH_PARTIAL = 5.0


def build_frame() -> pd.DataFrame:
    df = pd.read_csv(V2)
    df = df[df.weather_available & df.satellite_available & df.soil_available]
    df = df[(df.season == "Kharif") & (df.year.between(2000, 2012))].copy()

    cov = pd.read_csv(COV)
    cov["district"] = cov["district"].replace(DISTRICT_ALIASES)
    cov["year"] = cov["year"].astype(int)
    df = df.merge(cov[["state", "district", "year", "season",
                       "non_rice_cropped_area_ha", "n_crops_grown"]],
                  on=["state", "district", "year", "season"], how="left")

    ter = pd.read_csv(TER)
    ter = ter[ter.status == "OK"][["district_id", "elevation_m_mean", "slope_deg_mean"]]
    df = df.merge(ter, on="district_id", how="left")

    # Irrigation: STATIC district attribute (approved Convention 1).
    mapping = pd.read_csv(MAP)
    mapping = mapping[mapping.mapping_type != "UNMAPPABLE"]
    irr = pd.read_csv(IRR)[["source_district_name", IRR_VAR]]
    link = mapping.merge(irr, on="source_district_name", how="left")
    link["district_u"] = link["canonical_district_harvestwise"].str.upper().str.strip()
    df["district_u"] = df["district"].str.upper().str.strip()
    df = df.merge(link[["district_u", IRR_VAR]], on="district_u", how="left")

    df["is_tn"] = (df["state"] == "Tamil Nadu").astype(int)
    return df


def ols(X: np.ndarray, y: np.ndarray, clusters: np.ndarray | None = None):
    """OLS with plain and (optionally) district-clustered standard errors."""
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    dof = n - k
    sigma2 = float(resid @ resid) / dof
    se_plain = np.sqrt(np.diag(sigma2 * XtX_inv))

    se_cluster = None
    n_clusters = None
    if clusters is not None:
        uniq = np.unique(clusters)
        n_clusters = len(uniq)
        meat = np.zeros((k, k))
        for g in uniq:
            m = clusters == g
            Xg, ug = X[m], resid[m]
            s = Xg.T @ ug
            meat += np.outer(s, s)
        # CR1 finite-sample correction
        c = (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - k))
        V = XtX_inv @ meat @ XtX_inv * c
        se_cluster = np.sqrt(np.diag(V))

    r2 = 1 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum())
    adj_r2 = 1 - (1 - r2) * (n - 1) / dof
    return {"beta": beta, "se_plain": se_plain, "se_cluster": se_cluster,
            "n": n, "k": k, "dof": dof, "n_clusters": n_clusters,
            "r2": r2, "adj_r2": adj_r2}


def summarize(fit, names, idx=1):
    """Coefficient block for the region term (index 1 by construction)."""
    b = float(fit["beta"][idx])
    out = {"coefficient_t_ha": b, "n": fit["n"], "r2": fit["r2"], "adj_r2": fit["adj_r2"]}
    for label, se_arr, dofs in (("plain", fit["se_plain"], fit["dof"]),
                                ("clustered", fit["se_cluster"],
                                 (fit["n_clusters"] - 1) if fit["n_clusters"] else None)):
        if se_arr is None:
            continue
        se = float(se_arr[idx])
        tcrit = stats.t.ppf(0.975, dofs)
        out[f"se_{label}"] = se
        out[f"ci95_{label}"] = [b - tcrit * se, b + tcrit * se]
        out[f"t_{label}"] = b / se if se > 0 else None
        out[f"p_{label}"] = float(2 * (1 - stats.t.cdf(abs(b / se), dofs))) if se > 0 else None
    if fit["n_clusters"]:
        out["n_clusters"] = fit["n_clusters"]
    out["all_coefficients"] = {nm: float(fit["beta"][i]) for i, nm in enumerate(names)}
    return out


def design(frame, cols):
    X = np.column_stack([np.ones(len(frame)), frame["is_tn"].to_numpy(float)]
                        + [frame[c].to_numpy(float) for c in cols])
    names = ["intercept", "is_tn"] + list(cols)
    return X, names


def main():
    df = build_frame()
    needed = [TARGET, "is_tn"] + B_COVS + [IRR_VAR]
    common = df.dropna(subset=needed).copy()
    print(f"common estimation sample: {len(common)} rows, "
          f"{common['district'].nunique()} districts, "
          f"{common['year'].min()}-{common['year'].max()}")
    print(f"  by region: {common['state'].value_counts().to_dict()}")
    if len(common) != 378:
        raise SystemExit(f"REFUSING TO RUN: expected the approved 378-row sample, got {len(common)}.")

    y = common[TARGET].to_numpy(float)
    clusters = common["district_u"].to_numpy()

    fits = {}
    for label, cols in (("A_region_only", []),
                        ("B_region_plus_exp4_covariates", B_COVS),
                        ("C_region_plus_covariates_plus_irrigation", B_COVS + [IRR_VAR])):
        X, names = design(common, cols)
        fits[label] = summarize(ols(X, y, clusters), names)
        f = fits[label]
        print(f"\n{label}: beta_region = {f['coefficient_t_ha']:+.4f}")
        print(f"   plain     SE {f['se_plain']:.4f}  CI [{f['ci95_plain'][0]:+.3f}, {f['ci95_plain'][1]:+.3f}]  p={f['p_plain']:.2e}")
        print(f"   clustered SE {f['se_clustered']:.4f}  CI [{f['ci95_clustered'][0]:+.3f}, {f['ci95_clustered'][1]:+.3f}]  p={f['p_clustered']:.4f}  (G={f['n_clusters']})")
        print(f"   R2 {f['r2']:.4f}  adj R2 {f['adj_r2']:.4f}")

    bA = fits["A_region_only"]["coefficient_t_ha"]
    bB = fits["B_region_plus_exp4_covariates"]["coefficient_t_ha"]
    bC = fits["C_region_plus_covariates_plus_irrigation"]["coefficient_t_ha"]

    incremental = (bB - bC) / bA * 100.0
    exp4_share = (bA - bB) / bA * 100.0
    total_share = (bA - bC) / bA * 100.0

    irr_idx = ["intercept", "is_tn"] + B_COVS + [IRR_VAR]
    irr_coef = fits["C_region_plus_covariates_plus_irrigation"]["all_coefficients"][IRR_VAR]

    # Precision verdict on the CLUSTERED SEs, per approved D-B.
    cl = fits["C_region_plus_covariates_plus_irrigation"]
    ci_w = cl["ci95_clustered"][1] - cl["ci95_clustered"][0]
    region_still_sig = not (cl["ci95_clustered"][0] <= 0 <= cl["ci95_clustered"][1])

    if abs(incremental) >= THRESH_MEANINGFUL:
        band = "MEANINGFUL SUPPORT (threshold met on point estimate)"
    elif abs(incremental) >= THRESH_PARTIAL:
        band = "PARTIAL / SUGGESTIVE SUPPORT"
    else:
        band = "LITTLE OR NO SUPPORT"
    if incremental < 0:
        band = "LITTLE OR NO SUPPORT (coefficient moved the WRONG way)"

    print("\n=== PRIMARY OUTCOME ===")
    print(f"beta_A {bA:+.4f} | beta_B {bB:+.4f} | beta_C {bC:+.4f}")
    print(f"Experiment 4 covariates accounted for : {exp4_share:.2f}% of the original gap")
    print(f"INCREMENTAL IRRIGATION EXPLANATION    : {incremental:.2f} percentage points")
    print(f"Cumulative (covariates + irrigation)  : {total_share:.2f}%")
    print(f"irrigation coefficient ({IRR_VAR}) = {irr_coef:+.6f} t/ha per percentage point")
    print(f"provisional band: {band}")

    # Reproduction check on the original Experiment 4 382-row sample.
    repro = df.dropna(subset=[TARGET, "is_tn"] + B_COVS).copy()
    Xr, nr = design(repro, [])
    a4 = ols(Xr, repro[TARGET].to_numpy(float))
    Xr2, nr2 = design(repro, B_COVS)
    b4 = ols(Xr2, repro[TARGET].to_numpy(float))
    print(f"\nExperiment 4 reproduction on its original {len(repro)} rows: "
          f"beta_A {float(a4['beta'][1]):+.4f} (published +0.825), "
          f"beta_B {float(b4['beta'][1]):+.4f} (published +0.565)")

    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": "8 - approved primary analysis only",
        "conventions": {
            "D-A": ("Irrigation is a STATIC DISTRICT-LEVEL ATTRIBUTE: the observed 2004-05 / "
                    "Fasli 1414 value applied across 2000-2012. This assumes approximate "
                    "temporal stability. The variable is NOT annually observed over 2000-2012."),
            "D-B": ("Plain and district-clustered SEs both reported; the primary precision "
                    "verdict uses the CLUSTERED SEs (G = 31 districts)."),
        },
        "language": ("All results are ASSOCIATIONS. A reduction in the Tamil Nadu coefficient "
                     "means irrigation accounts for part of the observed regional association; "
                     "it is not evidence that irrigation caused the regional yield difference."),
        "sample": {"n": int(len(common)), "districts": int(common["district"].nunique()),
                   "years": [int(common.year.min()), int(common.year.max())],
                   "by_region": {k: int(v) for k, v in common["state"].value_counts().items()},
                   "excluded": "Ariyalur (UNMAPPABLE_YEAR_NOT_COVERED), 4 rows"},
        "models": fits,
        "primary_outcome": {
            "beta_A": bA, "beta_B": bB, "beta_C": bC,
            "experiment4_share_pct": exp4_share,
            "incremental_irrigation_explanation_pct": incremental,
            "cumulative_share_pct": total_share,
            "pre_registered_threshold_pct": THRESH_MEANINGFUL,
            "irrigation_coefficient": irr_coef,
            "irrigation_variable": IRR_VAR,
            "provisional_band": band,
            "region_coefficient_still_excludes_zero_clustered": bool(region_still_sig),
            "clustered_ci_width": float(ci_w),
        },
        "experiment4_reproduction": {
            "n": int(len(repro)),
            "beta_A_reproduced": float(a4["beta"][1]), "beta_A_published": 0.825,
            "beta_B_reproduced": float(b4["beta"][1]), "beta_B_published": 0.565,
        },
    }
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT}")
    return results


if __name__ == "__main__":
    main()
