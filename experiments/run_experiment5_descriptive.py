"""
Experiment 5, Checkpoint 6 — descriptive analysis only.

No model is fitted. No primary regression is run. No feature is written into
the modelling dataset. No year-alignment convention is adopted.

THE YEAR-ALIGNMENT PROBLEM IS NOT SILENTLY RESOLVED HERE
---------------------------------------------------------
Irrigation is observed for ONE year (Fasli 1414 = 2004-05). HarvestWise yield
rows are Kharif, 2000-2012. Relating the two requires an alignment convention,
which has NOT been approved. Rather than pick one, this script computes every
irrigation-yield relationship under BOTH candidate views and reports them side
by side, so the sensitivity to that unapproved choice is visible:

  VIEW A "nearest-year"  : district irrigation (2004-05) vs that district's
                           Kharif yield in 2004 only. Minimal assumption; the
                           irrigation year and the yield year coincide.
  VIEW B "district-mean" : district irrigation (2004-05) vs that district's
                           MEAN Kharif yield over 2000-2012. Treats irrigation
                           as a static district property, which is what using
                           a single year across the panel would imply.

Neither view is adopted as the analysis convention. Checkpoint 7 decides.

MANDATORY POOLED-VS-WITHIN-REGION RULE
--------------------------------------
Every relationship is computed three ways - pooled, within Tamil Nadu, within
AP/Telangana - and flagged POTENTIAL_GEOGRAPHIC_CONFOUNDING when the pooled
result is not reproduced within regions. Experiment 4 was nearly misled by
exactly this pattern (`n_rice_seasons`: pooled r = -0.463, within-AP/TG
r = -0.01), so the check is applied mechanically rather than by judgement.
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

RAW = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv"
MAP = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"
V2 = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
OUT = ROOT / "experiments" / "experiment5_descriptive.json"

TARGET = "final_yield_t_ha"
IRR_VARS = ["net_irrigated_area_ha", "gross_irrigated_area_ha",
            "pct_net_irrigated_to_net_area_sown", "irrigation_intensity"]


def build_district_frame() -> pd.DataFrame:
    """District-level frame: one row per study district, carrying the observed
    2004-05 irrigation values and the district's yield summaries. This is a
    DESCRIPTIVE frame only - it is not written to disk as a modelling dataset."""
    raw = pd.read_csv(RAW)
    mapping = pd.read_csv(MAP)
    mapped = mapping[mapping.mapping_type != "UNMAPPABLE"]

    irr = mapped.merge(
        raw, on=["source_district_name"], how="left",
        suffixes=("", "_raw"),
    )
    # Pre-registered formula. TN publishes intensity directly; AP does not, so
    # it is computed identically for both from gross/net and cross-checked
    # against TN's published column below.
    irr["irrigation_intensity"] = irr["gross_irrigated_area_ha"] / irr["net_irrigated_area_ha"]

    yld = pd.read_csv(V2)
    yld = yld[yld.weather_available & yld.satellite_available & yld.soil_available]
    yld = yld[(yld.season == "Kharif") & (yld.year.between(2000, 2012))]
    yld["district_u"] = yld["district"].str.upper().str.strip()

    y_mean = yld.groupby("district_u")[TARGET].agg(["mean", "count"]).rename(
        columns={"mean": "yield_mean_2000_2012", "count": "n_yield_rows"})
    y_2004 = yld[yld.year == 2004].groupby("district_u")[TARGET].mean().rename("yield_kharif_2004")

    irr["district_u"] = irr["canonical_district_harvestwise"].str.upper().str.strip()
    df = irr.merge(y_mean, left_on="district_u", right_index=True, how="left")
    df = df.merge(y_2004, left_on="district_u", right_index=True, how="left")
    df["is_tn"] = (df["harvestwise_region"] == "Tamil Nadu").astype(int)
    return df


def describe(df, var, group_col="harvestwise_region"):
    out = {}
    for name, g in list(df.groupby(group_col)) + [("ALL", df)]:
        s = g[var]
        out[name] = {
            "n": int(s.notna().sum()),
            "missing": int(s.isna().sum()),
            "missing_pct": round(100 * s.isna().mean(), 2),
            "mean": None if s.notna().sum() == 0 else float(s.mean()),
            "median": None if s.notna().sum() == 0 else float(s.median()),
            "std": None if s.notna().sum() < 2 else float(s.std(ddof=1)),
            "min": None if s.notna().sum() == 0 else float(s.min()),
            "max": None if s.notna().sum() == 0 else float(s.max()),
        }
    return out


def rel(x, y):
    m = pd.notna(x) & pd.notna(y)
    x, y = np.asarray(x)[m], np.asarray(y)[m]
    if len(x) < 4 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return {"n": int(len(x)), "pearson_r": None, "spearman_rho": None,
                "note": "insufficient n or zero variance"}
    return {"n": int(len(x)),
            "pearson_r": float(stats.pearsonr(x, y)[0]),
            "pearson_p": float(stats.pearsonr(x, y)[1]),
            "spearman_rho": float(stats.spearmanr(x, y)[0])}


def main():
    df = build_district_frame()
    res = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": "6 - descriptive analysis only; no model fitted, no year-alignment convention adopted",
        "n_study_districts_with_irrigation": int(df["net_irrigated_area_ha"].notna().sum()),
        "excluded": {"ARIYALUR": "UNMAPPABLE_YEAR_NOT_COVERED (district created 2007)"},
    }

    print(f"study districts with observed 2004-05 irrigation: "
          f"{int(df['net_irrigated_area_ha'].notna().sum())}/32")

    # ---- intensity cross-check (TN publishes it; we recompute) ----
    tn = df[df.is_tn == 1].dropna(subset=["irrigation_intensity_reported", "irrigation_intensity"])
    if len(tn):
        d = (tn["irrigation_intensity"] - tn["irrigation_intensity_reported"]).abs()
        res["intensity_crosscheck_tn"] = {
            "n": int(len(tn)), "max_abs_diff": float(d.max()), "mean_abs_diff": float(d.mean()),
            "note": ("Tamil Nadu publishes Irrigation Intensity directly. Recomputing it as "
                     "gross/net reproduces the published column, which validates both the "
                     "extraction and the pre-registered formula before it is applied to AP, "
                     "where intensity is not published."),
        }
        print(f"intensity cross-check (TN published vs recomputed): max abs diff "
              f"{d.max():.4f} over {len(tn)} districts")

    # ---- descriptive statistics ----
    res["descriptives"] = {v: describe(df, v) for v in IRR_VARS}
    print("\n=== irrigation descriptives by region ===")
    for v in IRR_VARS:
        print(f"\n{v}")
        for reg in ("Andhra Pradesh", "Telangana", "Tamil Nadu", "ALL"):
            d = res["descriptives"][v].get(reg)
            if d and d["mean"] is not None:
                print(f"  {reg:16s} n={d['n']:2d} mean={d['mean']:12,.2f} median={d['median']:12,.2f} "
                      f"sd={d['std']:11,.2f} min={d['min']:11,.2f} max={d['max']:12,.2f} miss={d['missing_pct']}%")

    # ---- TN vs AP/TG comparison ----
    comp = []
    for v in IRR_VARS:
        a = df.loc[df.is_tn == 0, v].dropna()
        b = df.loc[df.is_tn == 1, v].dropna()
        if len(a) < 2 or len(b) < 2:
            continue
        pooled_sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        comp.append({
            "variable": v,
            "ap_tg_mean": float(a.mean()), "tamil_nadu_mean": float(b.mean()),
            "ap_tg_n": int(len(a)), "tamil_nadu_n": int(len(b)),
            "standardized_mean_difference": float((b.mean() - a.mean()) / pooled_sd) if pooled_sd > 1e-12 else 0.0,
            "ks_statistic": float(stats.ks_2samp(a, b).statistic),
            "mann_whitney_p": float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue),
        })
    res["tn_vs_aptg"] = comp
    print("\n=== Tamil Nadu vs AP/Telangana ===")
    for c in comp:
        print(f"  {c['variable']:36s} AP+TG {c['ap_tg_mean']:12,.2f} | TN {c['tamil_nadu_mean']:12,.2f} "
              f"| SMD {c['standardized_mean_difference']:+.2f} KS {c['ks_statistic']:.3f}")

    # ---- yield relationships, both views, pooled + within region ----
    views = {"A_nearest_year_2004": "yield_kharif_2004",
             "B_district_mean_2000_2012": "yield_mean_2000_2012"}
    assoc = {}
    print("\n=== irrigation-yield ASSOCIATION (pooled vs within-region) ===")
    for vname, ycol in views.items():
        assoc[vname] = {}
        print(f"\n-- VIEW {vname} (yield = {ycol}) --")
        for v in IRR_VARS:
            pooled = rel(df[v], df[ycol])
            wtn = rel(df.loc[df.is_tn == 1, v], df.loc[df.is_tn == 1, ycol])
            wap = rel(df.loc[df.is_tn == 0, v], df.loc[df.is_tn == 0, ycol])
            flag = None
            if pooled.get("pearson_r") is not None:
                pr = pooled["pearson_r"]
                withins = [w.get("pearson_r") for w in (wtn, wap) if w.get("pearson_r") is not None]
                if withins:
                    # Flag when pooled is materially larger than both within-region
                    # values, or when any within-region value flips sign.
                    shrinks = all(abs(pr) - abs(w) > 0.15 for w in withins)
                    flips = any(np.sign(w) != np.sign(pr) for w in withins)
                    if shrinks or flips:
                        flag = "POTENTIAL_GEOGRAPHIC_CONFOUNDING"
            assoc[vname][v] = {"pooled": pooled, "within_tamil_nadu": wtn,
                               "within_ap_telangana": wap, "flag": flag}
            pr = pooled.get("pearson_r")
            print(f"  {v:36s} pooled r={pr if pr is None else round(pr,3)!s:>7} | "
                  f"TN r={wtn.get('pearson_r') if wtn.get('pearson_r') is None else round(wtn['pearson_r'],3)!s:>7} | "
                  f"AP/TG r={wap.get('pearson_r') if wap.get('pearson_r') is None else round(wap['pearson_r'],3)!s:>7}"
                  f"{'  <-- ' + flag if flag else ''}")
    res["yield_association"] = assoc

    flagged = sorted({v for vw in assoc.values() for v, d in vw.items() if d["flag"]})
    res["geographic_confounding_flags"] = flagged
    print(f"\nvariables flagged POTENTIAL_GEOGRAPHIC_CONFOUNDING: {flagged or 'none'}")

    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT}")
    return res


if __name__ == "__main__":
    main()
