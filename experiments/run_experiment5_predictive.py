"""
Experiment 5, Checkpoint 11 — approved predictive transfer test (7 arms).

Train: Andhra Pradesh + Telangana (239 rows, 20 districts)
Test : Tamil Nadu (139 rows, 11 districts), district overlap 0
Seeds: 42-46. Hyperparameters UNCHANGED from Experiment 1. Nothing tuned.

Arm 7 (`static_only_with_irrigation`) is the mandatory shortcut control
imposed by the Checkpoint 10 leakage audit: irrigation is numerically a
one-to-one district identifier (31 distinct values across 31 districts, zero
within-district variation), and Experiment 4's `static_only` arm does not
contain it, so only arm 7 can separate "irrigation carries agronomic signal"
from "irrigation is a static district-level shortcut".

INTERPRETATION RULE, FIXED BEFORE RUNNING
  If arm 4 improves but arm 7 performs comparably or better, the result is
  classified as POTENTIAL STATIC GEOGRAPHIC SHORTCUT BEHAVIOUR, not as
  evidence that irrigation provides genuine transferable predictive signal.

A predictive result does NOT overturn the Checkpoint 8/9 explanatory null,
which is the pre-specified primary outcome.
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
    B_COVS, IRR_VAR, TARGET, build_frame,
)
from training import district_train  # noqa: E402
from training.district_dataset import (  # noqa: E402
    SATELLITE_FEATURES, SOIL_FEATURES, WEATHER_FEATURES,
    DistrictDataset, StandardScaler, group_key,
)
from training.district_model import TrainMeanBaseline  # noqa: E402
from training.district_train import metrics, predict, train_model  # noqa: E402

OUT = ROOT / "experiments" / "experiment5_predictive_results.json"
SEEDS = [42, 43, 44, 45, 46]
TRAIN_HPARAMS = dict(epochs=300, batch_size=32, lr=1e-3, weight_decay=1e-4,
                     patience=30, hidden_dims=(32, 16), dropout=0.2)
ENV = WEATHER_FEATURES + SATELLITE_FEATURES
STATIC = ["elevation_m_mean", "slope_deg_mean"]

ARMS = {
    "1_baseline": [],
    "2_weather_satellite": ENV,
    "3_weather_satellite_exp4_covariates": ENV + B_COVS,
    "4_weather_satellite_exp4_covariates_irrigation": ENV + B_COVS + [IRR_VAR],
    "5_static_only": STATIC,
    "6_soil_only": SOIL_FEATURES,
    "7_static_only_with_irrigation": STATIC + [IRR_VAR],
}


def grouped_val_holdout(df, seed, val_frac=0.2):
    """Validation districts carved from the SOURCE region only."""
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


def fit_eval(train_df, val_df, test_df, cols, seed):
    """Scaler and median imputation fit on TRAIN rows only."""
    if cols:
        med = train_df[cols].median()
        tr_x, va_x, te_x = train_df.copy(), val_df.copy(), test_df.copy()
        for d in (tr_x, va_x, te_x):
            for c in cols:
                d[c] = d[c].fillna(med[c])
        raw = tr_x[cols].to_numpy(dtype=np.float32)
    else:
        tr_x, va_x, te_x = train_df, val_df, test_df
        raw = np.zeros((len(train_df), 0), dtype=np.float32)
    scaler = StandardScaler().fit(raw, split_name="train")
    tr = DistrictDataset(tr_x, cols, scaler)
    va = DistrictDataset(va_x, cols, scaler)
    te = DistrictDataset(te_x, cols, scaler)
    y = te.y.squeeze(1).numpy()
    if not cols:
        b = TrainMeanBaseline().fit(tr.y, split_name="train")
        p = b.predict(len(te)).squeeze(1).numpy()
    else:
        district_train.set_seed(seed)
        model, _ = train_model(tr, va, seed=seed, **TRAIN_HPARAMS)
        p = predict(model, te)
    return metrics(y, p)


def main():
    df = build_frame()
    needed = [TARGET, "is_tn"] + B_COVS + [IRR_VAR]
    common = df.dropna(subset=needed).reset_index(drop=True).copy()
    common["group"] = group_key(common)
    if len(common) != 378:
        raise SystemExit(f"REFUSING TO RUN: expected 378 rows, got {len(common)}")

    src = common[common.is_tn == 0].reset_index(drop=True)
    tgt = common[common.is_tn == 1].reset_index(drop=True)
    overlap = len(set(src["group"]) & set(tgt["group"]))
    if overlap:
        raise SystemExit(f"REFUSING TO RUN: {overlap} districts appear in both train and test")

    print(f"train {len(src)} rows / {src['group'].nunique()} districts | "
          f"test {len(tgt)} rows / {tgt['group'].nunique()} districts | overlap {overlap}")

    results = {}
    for name, cols in ARMS.items():
        runs = []
        for seed in SEEDS:
            tr, va = grouped_val_holdout(src, seed)
            runs.append(fit_eval(tr, va, tgt, cols, seed))
        maes = [r["mae"] for r in runs]
        r2s = [r["r2"] for r in runs if r["r2"] is not None]
        results[name] = {
            "features": cols, "n_features": len(cols), "per_seed": runs,
            "mae_mean": float(np.mean(maes)), "mae_std": float(np.std(maes)),
            "rmse_mean": float(np.mean([r["rmse"] for r in runs])),
            "r2_mean": float(np.mean(r2s)), "r2_std": float(np.std(r2s)),
        }
        print(f"  {name:46s} MAE {np.mean(maes):.3f} ± {np.std(maes):.3f}   "
              f"R2 {np.mean(r2s):+.3f} ± {np.std(r2s):.3f}")

    base = results["1_baseline"]["mae_mean"]
    a3 = results["3_weather_satellite_exp4_covariates"]["mae_mean"]
    a4 = results["4_weather_satellite_exp4_covariates_irrigation"]["mae_mean"]
    a5 = results["5_static_only"]["mae_mean"]
    a7 = results["7_static_only_with_irrigation"]["mae_mean"]

    irrigation_gain = a3 - a4  # positive = irrigation improved MAE
    arm7_beats_arm4 = a7 <= a4
    arm7_beats_baseline = a7 < base

    if irrigation_gain <= 0:
        verdict = ("NO PREDICTIVE IMPROVEMENT FROM IRRIGATION - adding irrigation did not "
                   "reduce MAE relative to arm 3.")
    elif arm7_beats_arm4:
        verdict = ("POTENTIAL STATIC GEOGRAPHIC SHORTCUT BEHAVIOUR - arm 4 improved, but the "
                   "static-only-with-irrigation control (arm 7) performed comparably or better, "
                   "so the gain is not evidence of genuine transferable irrigation signal.")
    else:
        verdict = ("Irrigation improved arm 4 AND the static-only-with-irrigation control did "
                   "not match it. Consistent with genuine transferable signal, subject to the "
                   "anachronism caveat below.")

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint": "11 - approved predictive transfer, 7 arms",
        "design": {"train": ["Andhra Pradesh", "Telangana"], "test": ["Tamil Nadu"],
                   "n_train": int(len(src)), "n_test": int(len(tgt)),
                   "train_districts": int(src["group"].nunique()),
                   "test_districts": int(tgt["group"].nunique()),
                   "district_overlap": int(overlap), "seeds": SEEDS,
                   "hyperparameters_unchanged_from_experiment1": {
                       k: (list(v) if isinstance(v, tuple) else v)
                       for k, v in TRAIN_HPARAMS.items()}},
        "arms": results,
        "interpretation": {
            "irrigation_mae_gain_arm3_minus_arm4": float(irrigation_gain),
            "arm7_mae": a7, "arm4_mae": a4, "arm5_mae": a5, "baseline_mae": base,
            "arm7_comparable_or_better_than_arm4": bool(arm7_beats_arm4),
            "arm7_beats_baseline": bool(arm7_beats_baseline),
            "verdict": verdict,
            "anachronism_caveat": (
                "117 of 378 rows (31.0%) pair a yield observation with an irrigation figure "
                "measured in a LATER year (2004-05). Any predictive result carries this "
                "anachronism, which is not admissible in a genuine forecasting setting."),
            "primacy_rule": (
                "This predictive result does NOT overturn the Checkpoint 8/9 explanatory null, "
                "which is the pre-specified primary outcome."),
        },
    }
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nirrigation MAE gain (arm3 - arm4): {irrigation_gain:+.4f}")
    print(f"arm 7 comparable/better than arm 4: {arm7_beats_arm4}")
    print(f"VERDICT: {verdict}")
    print(f"\nwrote -> {OUT}")
    return out


if __name__ == "__main__":
    main()
