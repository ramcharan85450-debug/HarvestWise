"""
Experiment 5, Checkpoint 9 — approved robustness tests.

Nothing here changes the primary analysis. The common 378-row sample, the
primary irrigation variable, the >=10 percentage-point threshold and the
Model A/B/C formulas are all unchanged. Every result below is reported,
including the tests that fail or cannot be run.

APPROVED TESTS
  R1  Alternative valid irrigation definitions
  R2  Within-region relationships
  R3  Irrigation source composition
  R4  Symmetric outlier robustness (winsorization, applied to ALL states alike)
  R5  Leave-one-district-out, with explicit examination of Hyderabad
  R6  District-cluster bootstrap CI for the incremental statistic (approved
      as an ADDITIONAL PRECISION ANALYSIS for the pre-specified outcome; it
      does not change the threshold and is not used to select a specification)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.run_experiment5_primary import (  # noqa: E402
    B_COVS, IRR_VAR, TARGET, build_frame, design, ols,
)

OUT = ROOT / "experiments" / "experiment5_robustness.json"
SEED = 20260904
N_BOOT = 2000


def incremental(frame, irr_var=IRR_VAR, target=TARGET):
    """(beta_B - beta_C)/beta_A * 100 on one frame. No clustering needed here;
    R6 supplies the interval."""
    y = frame[target].to_numpy(float)
    bA = float(ols(*design(frame, [])[:1], y)["beta"][1]) if False else None
    XA, _ = design(frame, [])
    XB, _ = design(frame, B_COVS)
    XC, _ = design(frame, B_COVS + [irr_var])
    bA = float(ols(XA, y)["beta"][1])
    bB = float(ols(XB, y)["beta"][1])
    bC = float(ols(XC, y)["beta"][1])
    return bA, bB, bC, ((bB - bC) / bA * 100.0 if abs(bA) > 1e-12 else np.nan)


ALT_VARS = ["net_irrigated_area_ha", "gross_irrigated_area_ha"]


def attach_alternative_irrigation(df: pd.DataFrame) -> pd.DataFrame:
    """Adds the alternative irrigation definitions used ONLY by R1. Attached
    exactly like the primary variable: as a STATIC district-level attribute
    from the same 2004-05 source rows and the same approved mapping table."""
    MAP = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"
    IRR = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv"
    mapping = pd.read_csv(MAP)
    mapping = mapping[mapping.mapping_type != "UNMAPPABLE"]
    irr = pd.read_csv(IRR)[["source_district_name"] + ALT_VARS]
    link = mapping.merge(irr, on="source_district_name", how="left")
    link["district_u"] = link["canonical_district_harvestwise"].str.upper().str.strip()
    out = df.merge(link[["district_u"] + ALT_VARS], on="district_u", how="left")
    # Pre-registered formula; undefined where net area is 0 (Hyderabad).
    out["irrigation_intensity"] = np.where(
        out["net_irrigated_area_ha"] > 0,
        out["gross_irrigated_area_ha"] / out["net_irrigated_area_ha"], np.nan)
    return out


def main():
    df = attach_alternative_irrigation(build_frame())
    base_cols = [TARGET, "is_tn"] + B_COVS + [IRR_VAR]
    common = df.dropna(subset=base_cols).copy()
    assert len(common) == 378, f"expected 378, got {len(common)}"
    res = {"generated_utc": datetime.now(timezone.utc).isoformat(),
           "checkpoint": "9 - approved robustness tests",
           "primary_sample_n": int(len(common)),
           "note": ("Nothing here changes the primary sample, variable, threshold or model "
                    "formulas. All results reported, including failures.")}

    bA0, bB0, bC0, inc0 = incremental(common)
    res["primary_recomputed"] = {"beta_A": bA0, "beta_B": bB0, "beta_C": bC0,
                                 "incremental_pct": inc0}
    print(f"primary: beta_A {bA0:+.4f} beta_B {bB0:+.4f} beta_C {bC0:+.4f} "
          f"incremental {inc0:+.2f} pp")

    # ---------------- R1 alternative irrigation definitions ----------------
    print("\n=== R1: alternative valid irrigation definitions ===")
    r1 = {}
    alts = {
        "pct_net_irrigated_to_net_area_sown": "PRIMARY (pre-registered irrigated_fraction)",
        "net_irrigated_area_ha": "pre-registered fallback (absolute hectares)",
        "gross_irrigated_area_ha": "alternative absolute definition",
        "irrigation_intensity": "gross/net; undefined for Hyderabad (0/0)",
    }
    for var, why in alts.items():
        sub = df.dropna(subset=[TARGET, "is_tn"] + B_COVS + [var]).copy()
        bA, bB, bC, inc = incremental(sub, irr_var=var)
        coefC = float(ols(*(design(sub, B_COVS + [var])[0],), sub[TARGET].to_numpy(float))["beta"][-1])
        r1[var] = {"description": why, "n": int(len(sub)), "beta_A": bA, "beta_B": bB,
                   "beta_C": bC, "incremental_pct": inc, "irrigation_coefficient": coefC}
        print(f"  {var:38s} n={len(sub):3d} incremental {inc:+7.2f} pp  irr_coef {coefC:+.6g}")
    res["R1_alternative_definitions"] = r1

    # ---------------- R2 within-region ----------------
    print("\n=== R2: within-region relationships ===")
    r2 = {}
    for name, sub in (("Tamil Nadu", common[common.is_tn == 1]),
                      ("AP + Telangana", common[common.is_tn == 0])):
        y = sub[TARGET].to_numpy(float)
        # region term is constant within a region, so it is dropped here
        X = np.column_stack([np.ones(len(sub))] + [sub[c].to_numpy(float) for c in B_COVS + [IRR_VAR]])
        f = ols(X, y, sub["district_u"].to_numpy())
        coef = float(f["beta"][-1])
        se_c = float(f["se_cluster"][-1])
        r2[name] = {"n": int(len(sub)), "districts": int(sub["district_u"].nunique()),
                    "irrigation_coefficient": coef, "se_clustered": se_c,
                    "ci95_clustered": [coef - 1.96 * se_c, coef + 1.96 * se_c]}
        print(f"  {name:16s} n={len(sub):3d} G={sub['district_u'].nunique():2d} "
              f"irr_coef {coef:+.6f} (clustered SE {se_c:.6f})")
    res["R2_within_region"] = r2

    # ---------------- R3 source composition ----------------
    print("\n=== R3: irrigation source composition ===")
    res["R3_source_composition"] = {
        "status": "NOT RUN - INVALID BY CONSTRUCTION",
        "reason": ("The two Directorates publish incompatible source taxonomies. Andhra "
                   "Pradesh reports major/medium/minor project canals, tanks split by size, "
                   "public and private lift irrigation, tube wells and open wells; Tamil Nadu "
                   "reports canals, tanks, wells (sole irrigation), supplementary irrigation "
                   "by wells, and other sources. There is no defensible one-to-one mapping "
                   "between the two category sets, so a cross-region comparison of canal, "
                   "tank or well SHARES would compare differently-defined quantities. This "
                   "pre-registered test is reported as not runnable rather than run in an "
                   "invalid form."),
    }
    print("  NOT RUN - the two DES source taxonomies are not comparable (reported, not hidden)")

    # ---------------- R4 symmetric winsorization ----------------
    print("\n=== R4: symmetric outlier robustness ===")
    w = common.copy()
    lo, hi = w[TARGET].quantile(0.01), w[TARGET].quantile(0.99)
    w[TARGET] = w[TARGET].clip(lo, hi)
    n_clip = int((w[TARGET] != common[TARGET]).sum())
    clip_by_state = common.loc[w[TARGET] != common[TARGET], "state"].value_counts().to_dict()
    bA, bB, bC, inc = incremental(w)
    res["R4_winsorization"] = {
        "rule": ("Symmetric 1st/99th percentile winsorization of the TARGET on the pooled "
                 "378-row sample, applied identically to every state. Nothing deleted."),
        "n_clipped": n_clip, "clipped_by_state": {k: int(v) for k, v in clip_by_state.items()},
        "beta_A": bA, "beta_B": bB, "beta_C": bC, "incremental_pct": inc}
    print(f"  clipped {n_clip} values {clip_by_state}")
    print(f"  incremental {inc0:+.2f} -> {inc:+.2f} pp")

    # ---------------- R5 leave-one-district-out ----------------
    print("\n=== R5: leave-one-district-out ===")
    rows = []
    for d in sorted(common["district_u"].unique()):
        sub = common[common.district_u != d]
        bA, bB, bC, inc = incremental(sub)
        rows.append({"district_left_out": d, "n": int(len(sub)),
                     "beta_A": bA, "beta_B": bB, "beta_C": bC, "incremental_pct": inc})
    lodo = pd.DataFrame(rows).sort_values("incremental_pct")
    res["R5_leave_one_district_out"] = {
        "n_folds": len(rows),
        "incremental_min": float(lodo.incremental_pct.min()),
        "incremental_max": float(lodo.incremental_pct.max()),
        "incremental_median": float(lodo.incremental_pct.median()),
        "n_folds_reaching_threshold": int((lodo.incremental_pct >= 10).sum()),
        "n_folds_positive": int((lodo.incremental_pct > 0).sum()),
        "results": rows,
    }
    print(f"  incremental across 31 folds: min {lodo.incremental_pct.min():+.2f}, "
          f"median {lodo.incremental_pct.median():+.2f}, max {lodo.incremental_pct.max():+.2f} pp")
    print(f"  folds reaching the >=10pp threshold: {int((lodo.incremental_pct>=10).sum())}/31")
    hyd = lodo[lodo.district_left_out == "HYDERABAD"]
    if len(hyd):
        h = hyd.iloc[0]
        res["R5_hyderabad"] = {"incremental_without_hyderabad": float(h.incremental_pct),
                               "beta_A": float(h.beta_A), "beta_B": float(h.beta_B),
                               "beta_C": float(h.beta_C),
                               "note": ("Hyderabad publishes net and gross irrigated area of "
                                        "exactly 0 - a real value for an essentially urban "
                                        "district, not missing data.")}
        print(f"  HYDERABAD (published zero-irrigation extreme) removed -> "
              f"incremental {float(h.incremental_pct):+.2f} pp (primary {inc0:+.2f})")
    print("  most influential folds:")
    for r in rows[:0] or list(lodo.head(3).itertuples()) + list(lodo.tail(3).itertuples()):
        print(f"    without {r.district_left_out:16s} incremental {r.incremental_pct:+7.2f} pp")

    # ---------------- R6 district-cluster bootstrap ----------------
    print(f"\n=== R6: district-cluster bootstrap CI ({N_BOOT} reps, districts resampled) ===")
    rng = np.random.default_rng(SEED)
    districts = common["district_u"].unique()
    groups = {d: common[common.district_u == d] for d in districts}
    boots, failed = [], 0
    for _ in range(N_BOOT):
        pick = rng.choice(districts, size=len(districts), replace=True)
        samp = pd.concat([groups[d] for d in pick], ignore_index=True)
        if samp["is_tn"].nunique() < 2:
            failed += 1
            continue
        try:
            _, _, _, inc = incremental(samp)
            if np.isfinite(inc):
                boots.append(inc)
        except Exception:
            failed += 1
    boots = np.array(boots)
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    res["R6_cluster_bootstrap"] = {
        "method": ("Districts resampled with replacement (31 clusters), respecting the "
                   "geographic dependence structure and the static district-level irrigation "
                   "variable. Percentile CI. Reported as an ADDITIONAL PRECISION ANALYSIS for "
                   "the pre-specified outcome; it does not change the threshold and was not "
                   "used to select a specification."),
        "n_reps_requested": N_BOOT, "n_reps_used": int(len(boots)), "n_failed": int(failed),
        "seed": SEED,
        "point_estimate_pct": inc0,
        "bootstrap_mean_pct": float(boots.mean()),
        "ci95_pct": list(ci),
        "pr_incremental_ge_10pct": float((boots >= 10).mean()),
        "pr_incremental_ge_5pct": float((boots >= 5).mean()),
        "pr_incremental_le_0": float((boots <= 0).mean()),
    }
    print(f"  reps used {len(boots)}/{N_BOOT}")
    print(f"  incremental point {inc0:+.2f} pp, bootstrap mean {boots.mean():+.2f}, "
          f"95% CI [{ci[0]:+.2f}, {ci[1]:+.2f}] pp")
    print(f"  P(incremental >= 10pp) = {(boots>=10).mean():.3f}   "
          f"P(>= 5pp) = {(boots>=5).mean():.3f}   P(<= 0) = {(boots<=0).mean():.3f}")

    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT}")
    return res


if __name__ == "__main__":
    main()
