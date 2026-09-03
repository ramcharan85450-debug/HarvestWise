"""
Experiment 3 analysis - overlap-year confound reduction and sensor comparability.

Consumes:
  data/processed/district_multimodal_examples_v2.csv   (Phase 9 output)
  experiments/sensor_inventory.json                    (Phases 5/7 probe)

Writes:
  experiments/experiment3_results.json
  experiments/figures/experiment3/*.png

Experiments 1 and 2 are read-only inputs here. Their scripts, reports, JSON
results and figures are not touched, and neither is
data/processed/district_multimodal_examples.csv.

THE TWO ISOLATIONS THIS EXPERIMENT MAKES POSSIBLE
--------------------------------------------------
Experiment 2 could not separate geography from era from season, because
Andhra Pradesh/Telangana had only 1999-2012 Kharif/Rabi and Tamil Nadu had
only 2019/2024 Whole Year. Adding Tamil Nadu Kharif 2000-2012 creates two
comparisons that hold all but one factor fixed:

  ISOLATION 1 - GEOGRAPHY.
      train AP+Telangana Kharif 2000-2012  ->  test Tamil Nadu Kharif 2000-2012
      Same years. Same season. Same Landsat era (L5/L7). Only the state
      differs. This is the pure cross-region test Experiment 2 could not run.

  ISOLATION 2 - ERA + SEASON, within one region.
      Tamil Nadu Kharif 2000-2012   vs   Tamil Nadu Whole Year 2019/2024
      Same state, same districts, different era and season definition.

Neither isolation is perfect and the report says so: Isolation 1 still holds
season constant at Kharif only (so it does not license claims about Rabi or
Whole Year), and Isolation 2 varies era and season TOGETHER, so it bounds
their joint contribution rather than separating them from each other.

MODEL POLICY (Phase 11)
-----------------------
No model optimization. The architecture, hyperparameters, seeds and training
loop are taken UNCHANGED from Experiment 1 (training/district_model.py,
training/district_train.py). Nothing is tuned, widened or trained longer. The
point is data validity, not accuracy.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training import district_train  # noqa: E402
from training.district_dataset import (  # noqa: E402
    SATELLITE_FEATURES,
    SOIL_FEATURES,
    TARGET_COL,
    WEATHER_FEATURES,
    DistrictDataset,
    StandardScaler,
    assert_no_forbidden_features,
    features_for,
    group_key,
)
from training.district_model import TrainMeanBaseline  # noqa: E402
from training.district_train import metrics, predict, train_model  # noqa: E402

V2_PATH = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
V1_PATH = ROOT / "data" / "processed" / "district_multimodal_examples.csv"
SENSOR_PATH = ROOT / "experiments" / "sensor_inventory.json"
OUT_JSON = ROOT / "experiments" / "experiment3_results.json"
FIG_DIR = ROOT / "experiments" / "figures" / "experiment3"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [42, 43, 44, 45, 46]
CONFIGS = ["baseline", "weather_only", "satellite_only", "weather_satellite",
           "soil_only", "full_multimodal"]
CONFIG_LABEL = {
    "baseline": "Baseline (train mean)", "weather_only": "Weather only",
    "satellite_only": "Satellite only", "weather_satellite": "Weather + Satellite",
    "soil_only": "Soil only", "full_multimodal": "Full multimodal",
}
# UNCHANGED from Experiment 1. Not tuned here (Phase 11).
TRAIN_HPARAMS = dict(epochs=300, batch_size=32, lr=1e-3, weight_decay=1e-4,
                     patience=30, hidden_dims=(32, 16), dropout=0.2)
ENV = WEATHER_FEATURES + SATELLITE_FEATURES
ALL_FEATURES = ENV + SOIL_FEATURES
SOURCE_STATES = ["Andhra Pradesh", "Telangana"]
TN = "Tamil Nadu"


def load_aligned(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    used = df[df.weather_available & df.satellite_available & df.soil_available].copy()
    used = used.reset_index(drop=True)
    used["group"] = group_key(used)
    return used


def grouped_val_holdout(df, seed, val_frac=0.2):
    """Validation districts carved from the SOURCE domain only."""
    rng = np.random.default_rng(seed)
    tr, va = [], []
    for _, g in df.groupby("state", sort=True):
        groups = sorted(g["group"].unique())
        rng.shuffle(groups)
        n_val = max(1, int(round(len(groups) * val_frac)))
        if n_val >= len(groups):
            n_val = 1
        vg = set(groups[:n_val])
        va.append(g[g["group"].isin(vg)])
        tr.append(g[~g["group"].isin(vg)])
    return pd.concat(tr).reset_index(drop=True), pd.concat(va).reset_index(drop=True)


def fit_and_evaluate(train_df, val_df, test_df, config, seed):
    """Scaler fit on TRAIN rows only; early stopping on val only; test scored once."""
    fc = features_for(config)
    assert_no_forbidden_features(fc)
    raw = (train_df[fc].to_numpy(dtype=np.float32) if fc
           else np.zeros((len(train_df), 0), dtype=np.float32))
    scaler = StandardScaler().fit(raw, split_name="train")
    tr = DistrictDataset(train_df, fc, scaler)
    va = DistrictDataset(val_df, fc, scaler)
    te = DistrictDataset(test_df, fc, scaler)
    y = te.y.squeeze(1).numpy()
    if config == "baseline":
        b = TrainMeanBaseline().fit(tr.y, split_name="train")
        p = b.predict(len(te)).squeeze(1).numpy()
    else:
        district_train.set_seed(seed)
        model, _ = train_model(tr, va, seed=seed, **TRAIN_HPARAMS)
        p = predict(model, te)
    return metrics(y, p), p, y


def agg(runs):
    out = {}
    for k in ("mae", "rmse", "r2"):
        v = [r[k] for r in runs if r.get(k) is not None]
        out[f"{k}_mean"] = float(np.mean(v)) if v else None
        out[f"{k}_std"] = float(np.std(v)) if v else None
    return out


def fmt(a, k):
    m, s = a.get(f"{k}_mean"), a.get(f"{k}_std")
    return "n/a" if m is None else f"{m:.3f} ± {s:.3f}"


def transfer_experiment(source_df, target_df, label):
    """Run all six configurations for one source->target transfer."""
    out = {}
    for cfg in CONFIGS:
        runs = []
        for seed in SEEDS:
            tr, va = grouped_val_holdout(source_df, seed)
            m, _, _ = fit_and_evaluate(tr, va, target_df, cfg, seed)
            runs.append(m)
        out[cfg] = {"per_seed": runs, **agg(runs)}
        print(f"    {CONFIG_LABEL[cfg]:22s} MAE {fmt(out[cfg],'mae')}  R2 {fmt(out[cfg],'r2')}")
    return out


def shift_table(a_df, b_df, cols):
    """SMD / KS / Wasserstein between two frames, per feature."""
    rows = []
    for c in cols:
        a = a_df[c].to_numpy(dtype=float)
        b = b_df[c].to_numpy(dtype=float)
        if len(a) < 2 or len(b) < 2:
            continue
        pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
        ks = stats.ks_2samp(a, b)
        sd = a.std(ddof=1)
        rows.append({
            "feature": c,
            "a_mean": float(a.mean()), "a_std": float(a.std(ddof=1)),
            "b_mean": float(b.mean()), "b_std": float(b.std(ddof=1)),
            "smd": float((b.mean() - a.mean()) / pooled) if pooled > 1e-12 else 0.0,
            "ks": float(ks.statistic),
            "wasserstein_sd_units": (
                float(stats.wasserstein_distance((a - a.mean()) / sd, (b - a.mean()) / sd))
                if sd > 1e-12 else 0.0
            ),
        })
    return rows


def main():
    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "Experiment 3 - overlapping-year recovery and satellite sensor analysis",
        "model_policy": (
            "No model optimization (Phase 11). Architecture, hyperparameters and seeds are "
            "taken unchanged from Experiment 1."
        ),
        "hyperparameters_unchanged_from_experiment1": {
            k: (list(v) if isinstance(v, tuple) else v) for k, v in TRAIN_HPARAMS.items()
        },
        "seeds": SEEDS,
    }

    v2 = load_aligned(V2_PATH)
    v1 = load_aligned(V1_PATH)
    print(f"v1 aligned: {len(v1)}   v2 aligned: {len(v2)}")

    new = v2[v2["dataset_version"] == "experiment3_overlap_addition"]
    old = v2[v2["dataset_version"] == "experiment1_baseline"]

    # ---------- Phase 10: confound reduction ----------
    print("\n=== Phase 10: confound reduction ===")

    def matrix(df):
        return pd.crosstab(df["state"], df["year"])

    src_years_v2 = set(v2[v2.state.isin(SOURCE_STATES)]["year"])
    tn_years_v2 = set(v2[v2.state == TN]["year"])
    src_years_v1 = set(v1[v1.state.isin(SOURCE_STATES)]["year"])
    tn_years_v1 = set(v1[v1.state == TN]["year"])
    src_seasons_v2 = set(v2[v2.state.isin(SOURCE_STATES)]["season"])
    tn_seasons_v2 = set(v2[v2.state == TN]["season"])

    confound = {
        "before": {
            "source_years": sorted(int(x) for x in src_years_v1),
            "tamil_nadu_years": sorted(int(x) for x in tn_years_v1),
            "overlapping_years": sorted(int(x) for x in (src_years_v1 & tn_years_v1)),
            "overlapping_seasons": sorted(
                set(v1[v1.state.isin(SOURCE_STATES)]["season"]) & set(v1[v1.state == TN]["season"])
            ),
        },
        "after": {
            "source_years": sorted(int(x) for x in src_years_v2),
            "tamil_nadu_years": sorted(int(x) for x in tn_years_v2),
            "overlapping_years": sorted(int(x) for x in (src_years_v2 & tn_years_v2)),
            "overlapping_seasons": sorted(src_seasons_v2 & tn_seasons_v2),
        },
        "state_year_matrix_after": matrix(v2).to_dict(),
        "n_aligned_before": int(len(v1)),
        "n_aligned_after": int(len(v2)),
        "new_rows_aligned": int(len(new)),
    }
    results["phase10_confound_reduction"] = confound
    print(f"  overlapping years  before: {confound['before']['overlapping_years'] or 'NONE'}")
    print(f"  overlapping years  after : {confound['after']['overlapping_years'] or 'NONE'}")
    print(f"  overlapping seasons after: {confound['after']['overlapping_seasons'] or 'NONE'}")

    # ---------- ISOLATION 1: geography, era and season held fixed ----------
    overlap_years = sorted(src_years_v2 & tn_years_v2)
    iso1 = None
    if overlap_years and ("Kharif" in src_seasons_v2 & tn_seasons_v2):
        print("\n=== ISOLATION 1: pure geography (same years, same season) ===")
        src = v2[(v2.state.isin(SOURCE_STATES)) & (v2.season == "Kharif")
                 & (v2.year.isin(overlap_years))].reset_index(drop=True)
        tgt = v2[(v2.state == TN) & (v2.season == "Kharif")
                 & (v2.year.isin(overlap_years))].reset_index(drop=True)
        print(f"  train {len(src)} rows / {src['group'].nunique()} districts "
              f"| test {len(tgt)} rows / {tgt['group'].nunique()} districts")
        print(f"  years both sides: {sorted(set(src.year) & set(tgt.year))}")
        if len(tgt) >= 10 and len(src) >= 30:
            res = transfer_experiment(src, tgt, "AP+TG -> TN, Kharif, overlapping years")
            iso1 = {
                "label": ("PURE CROSS-REGION GENERALIZATION - year, season and Landsat era held "
                          "fixed; only the state differs"),
                "train_states": SOURCE_STATES, "test_state": TN, "season": "Kharif",
                "years": [int(y) for y in sorted(set(src.year) & set(tgt.year))],
                "n_train": int(len(src)), "n_train_districts": int(src["group"].nunique()),
                "n_test": int(len(tgt)), "n_test_districts": int(tgt["group"].nunique()),
                "results": res,
                "feature_shift_source_vs_target": shift_table(src, tgt, ENV),
                "yield_shift": {
                    "source_mean": float(src[TARGET_COL].mean()),
                    "target_mean": float(tgt[TARGET_COL].mean()),
                    "smd": float(
                        (tgt[TARGET_COL].mean() - src[TARGET_COL].mean())
                        / np.sqrt((src[TARGET_COL].var(ddof=1) + tgt[TARGET_COL].var(ddof=1)) / 2)
                    ),
                    "ks": float(stats.ks_2samp(src[TARGET_COL], tgt[TARGET_COL]).statistic),
                },
            }
        else:
            iso1 = {"status": "INSUFFICIENT DATA",
                    "n_train": int(len(src)), "n_test": int(len(tgt))}
            print("  INSUFFICIENT DATA for a meaningful run")
    results["isolation1_pure_geography"] = iso1

    # ---------- ISOLATION 2: era + season, within Tamil Nadu ----------
    iso2 = None
    tn_old = v2[(v2.state == TN) & (v2.season == "Kharif")]
    tn_new = v2[(v2.state == TN) & (v2.season == "Whole Year")]
    if len(tn_old) >= 10 and len(tn_new) >= 10:
        print("\n=== ISOLATION 2: era + season within Tamil Nadu ===")
        iso2 = {
            "label": ("ERA + SEASON contrast within ONE region. Varies era and season together, "
                      "so it bounds their JOINT contribution and does not separate them."),
            "cohort_a": {"season": "Kharif", "years": sorted(int(x) for x in set(tn_old.year)),
                         "n": int(len(tn_old)), "districts": int(tn_old["group"].nunique()),
                         "yield_mean": float(tn_old[TARGET_COL].mean()),
                         "yield_std": float(tn_old[TARGET_COL].std(ddof=1))},
            "cohort_b": {"season": "Whole Year", "years": sorted(int(x) for x in set(tn_new.year)),
                         "n": int(len(tn_new)), "districts": int(tn_new["group"].nunique()),
                         "yield_mean": float(tn_new[TARGET_COL].mean()),
                         "yield_std": float(tn_new[TARGET_COL].std(ddof=1))},
            "feature_shift": shift_table(tn_old, tn_new, ENV),
            "yield_smd": float(
                (tn_new[TARGET_COL].mean() - tn_old[TARGET_COL].mean())
                / np.sqrt((tn_old[TARGET_COL].var(ddof=1) + tn_new[TARGET_COL].var(ddof=1)) / 2)
            ),
            "shared_districts": int(len(set(tn_old["group"]) & set(tn_new["group"]))),
        }
        print(f"  Kharif 2000-2012: n={len(tn_old)}  vs  Whole Year 2019/2024: n={len(tn_new)}")
        print(f"  shared districts: {iso2['shared_districts']}  yield SMD {iso2['yield_smd']:+.3f}")
        for r in sorted(iso2["feature_shift"], key=lambda x: -abs(x["smd"]))[:4]:
            print(f"    {r['feature']:32s} SMD {r['smd']:+.2f}  KS {r['ks']:.3f}")
    results["isolation2_era_season_within_region"] = iso2

    # ---------- Phases 5/7: sensor inventory ----------
    sensor = None
    if SENSOR_PATH.exists():
        print("\n=== Phases 5/7: sensor inventory and comparability ===")
        raw = json.loads(SENSOR_PATH.read_text(encoding="utf-8"))
        counts, paired = {}, []
        for rec in raw["results"]:
            s = rec.get("sensors", {})
            if "error" in s:
                continue
            for name, v in s.items():
                if not isinstance(v, dict) or "scenes" not in v:
                    continue
                key = (rec["state"], int(rec["year"]), name)
                counts[key] = counts.get(key, 0) + v["scenes"]
            l5, l7 = s.get("Landsat 5 TM", {}), s.get("Landsat 7 ETM+", {})
            if l5.get("scenes", 0) > 0 and l7.get("scenes", 0) > 0:
                paired.append({
                    "state": rec["state"], "district": rec["district"], "year": rec["year"],
                    "l5_ndvi": l5["ndvi_mean"], "l7_ndvi": l7["ndvi_mean"],
                    "l5_evi": l5["evi_mean"], "l7_evi": l7["evi_mean"],
                    "l5_ndwi": l5["ndwi_mean"], "l7_ndwi": l7["ndwi_mean"],
                    "l5_scenes": l5["scenes"], "l7_scenes": l7["scenes"],
                })
        inventory = [{"state": k[0], "year": k[1], "sensor": k[2], "scenes": v}
                     for k, v in sorted(counts.items())]
        sensor = {"inventory_sample": inventory, "paired_l5_l7": paired,
                  "n_paired_district_years": len(paired)}

        if paired:
            pdf = pd.DataFrame(paired)
            tests = {}
            for idx in ("ndvi", "evi", "ndwi"):
                d = pdf[f"l7_{idx}"] - pdf[f"l5_{idx}"]
                t = stats.ttest_rel(pdf[f"l7_{idx}"], pdf[f"l5_{idx}"])
                w = stats.wilcoxon(pdf[f"l7_{idx}"], pdf[f"l5_{idx}"]) if len(pdf) >= 6 else None
                tests[idx] = {
                    "mean_difference_l7_minus_l5": float(d.mean()),
                    "std_difference": float(d.std(ddof=1)),
                    "cohens_dz": float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 1e-12 else None,
                    "paired_t_p": float(t.pvalue),
                    "wilcoxon_p": float(w.pvalue) if w is not None else None,
                    "n_pairs": int(len(pdf)),
                }
                print(f"  {idx.upper()} L7-L5 diff {d.mean():+.4f} ± {d.std(ddof=1):.4f} "
                      f"(dz={tests[idx]['cohens_dz']:+.2f}, p={t.pvalue:.4f}, n={len(pdf)})")
            sensor["paired_tests"] = tests
            sensor["design_note"] = (
                "Each pair is the SAME district, SAME year, SAME season window, processed "
                "identically - only the mission differs. Geography, time and season are held "
                "fixed by construction, so a difference here IS a sensor effect."
            )
        else:
            sensor["design_note"] = "No district-year had scenes from both Landsat 5 and 7."
    results["phases5_7_sensor"] = sensor

    # ---------- Figures ----------
    print("\n=== figures ===")
    # 1. State x Year coverage heatmap (after)
    mat = pd.crosstab(v2["state"], v2["year"])
    fig, ax = plt.subplots(figsize=(12, 3.2))
    im = ax.imshow(mat.values, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels([int(c) for c in mat.columns], rotation=45, fontsize=8)
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels(mat.index, fontsize=9)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            if v:
                ax.text(j, i, int(v), ha="center", va="center", fontsize=7,
                        color="white" if v > mat.values.max() * 0.6 else "black")
    ax.set_title("State × Year aligned examples AFTER Experiment 3 overlap recovery", fontsize=11)
    fig.colorbar(im, ax=ax, label="examples")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_state_year_coverage_heatmap.png", dpi=160)
    plt.close(fig)

    # 4. Before/after overlap comparison
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.4), sharey=True)
    for ax, d, title in ((axes[0], v1, f"BEFORE (Experiment 1/2) — {len(v1)} aligned"),
                         (axes[1], v2, f"AFTER (Experiment 3) — {len(v2)} aligned")):
        m = pd.crosstab(d["state"], d["year"])
        years = sorted(set(v1["year"]) | set(v2["year"]))
        m = m.reindex(columns=years, fill_value=0)
        ax.imshow(m.values, aspect="auto", cmap="YlGnBu",
                  vmin=0, vmax=max(pd.crosstab(v2["state"], v2["year"]).values.max(), 1))
        ax.set_xticks(range(len(years)))
        ax.set_xticklabels([int(c) for c in years], rotation=45, fontsize=7)
        ax.set_yticks(range(len(m.index)))
        ax.set_yticklabels(m.index, fontsize=8)
        ax.set_title(title, fontsize=10)
    fig.suptitle("Overlap coverage before and after Experiment 3", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "04_before_after_overlap.png", dpi=160)
    plt.close(fig)

    # 2 & 3: sensor figures, only if the probe produced real data
    if sensor and sensor.get("inventory_sample"):
        inv = pd.DataFrame(sensor["inventory_sample"])
        piv = inv.pivot_table(index="state", columns="sensor", values="scenes",
                              aggfunc="sum", fill_value=0)
        fig, ax = plt.subplots(figsize=(8, 4))
        piv.plot(kind="bar", stacked=True, ax=ax, colormap="viridis")
        ax.set_ylabel("scenes (sampled district-years)")
        ax.set_title("Landsat scenes by state and sensor generation (sampled)", fontsize=11)
        plt.setp(ax.get_xticklabels(), rotation=0)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "02_state_sensor_coverage.png", dpi=160)
        plt.close(fig)

    if sensor and sensor.get("paired_l5_l7"):
        pdf = pd.DataFrame(sensor["paired_l5_l7"])
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        for ax, idx in zip(axes, ("ndvi", "evi", "ndwi")):
            ax.scatter(pdf[f"l5_{idx}"], pdf[f"l7_{idx}"], s=45, alpha=0.8, color="#2a6f97")
            lo = min(pdf[f"l5_{idx}"].min(), pdf[f"l7_{idx}"].min())
            hi = max(pdf[f"l5_{idx}"].max(), pdf[f"l7_{idx}"].max())
            pad = (hi - lo) * 0.1 + 1e-6
            ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], "k--", lw=1)
            ax.set_xlabel(f"Landsat 5 {idx.upper()}")
            ax.set_ylabel(f"Landsat 7 {idx.upper()}")
            d = pdf[f"l7_{idx}"] - pdf[f"l5_{idx}"]
            ax.set_title(f"{idx.upper()}  Δ={d.mean():+.4f}", fontsize=10)
        fig.suptitle("Paired same-district, same-year, same-season sensor comparison "
                     "(points on the line = sensors agree)", fontsize=11)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "03_sensor_feature_distribution.png", dpi=160)
        plt.close(fig)

    OUT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote -> {OUT_JSON}")
    print(f"figures -> {FIG_DIR}")
    return results


if __name__ == "__main__":
    main()
