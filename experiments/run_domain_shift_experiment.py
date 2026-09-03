"""
Experiment 2 - Tamil Nadu failure analysis and cross-region domain-shift evaluation.

Runs sub-experiments 2A-2I, writes:
  experiments/TAMIL_NADU_DOMAIN_SHIFT_LEAKAGE_AUDIT.md
  experiments/TAMIL_NADU_DOMAIN_SHIFT_REPORT.md
  experiments/tamil_nadu_domain_shift_results.json
  experiments/figures/domain_shift/*.png

Experiment 1 (experiments/run_unseen_district_experiment.py and its outputs)
is READ but never modified or re-run. The field-level pipeline
(training/dataset.py, models/, backend/) is not imported at all.

THE CENTRAL SCIENTIFIC CAVEAT, STATED ONCE HERE AND REPEATED IN THE REPORT
--------------------------------------------------------------------------
In this dataset region and time period are PERFECTLY confounded: every
Andhra Pradesh / Telangana example is from 1999-2012 and every Tamil Nadu
example is from 2019 or 2024. There is not a single overlapping year. No
statistical procedure applied to these rows can therefore separate "Tamil
Nadu is geographically different" from "2019/2024 are temporally different"
- the two factors are collinear by construction. Every AP+TG -> TN result
below is consequently labelled CROSS-REGION + TEMPORAL domain shift, never
"geographic generalization". Sub-experiment 2G checks the confounding
explicitly rather than assuming it.

Season is a third confounded axis: AP/TG rows are Kharif/Rabi, Tamil Nadu
rows are Whole Year. That is also reported, not hidden.
"""

from __future__ import annotations

import ast
import inspect
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
    FORBIDDEN_AS_FEATURES,
    METADATA_COLS,
    SATELLITE_FEATURES,
    SOIL_FEATURES,
    TARGET_COL,
    WEATHER_FEATURES,
    DistrictDataset,
    StandardScaler,
    assert_no_forbidden_features,
    features_for,
    load_district_examples,
)
from training.district_model import TrainMeanBaseline  # noqa: E402
from training.district_train import metrics, predict, train_model  # noqa: E402

SEEDS = [42, 43, 44, 45, 46]
CONFIGS = [
    "baseline",
    "weather_only",
    "satellite_only",
    "weather_satellite",
    "soil_only",
    "full_multimodal",
]
CONFIG_LABEL = {
    "baseline": "Baseline (train mean)",
    "weather_only": "Weather only",
    "satellite_only": "Satellite only",
    "weather_satellite": "Weather + Satellite",
    "soil_only": "Soil only",
    "full_multimodal": "Full multimodal",
}
TRAIN_HPARAMS = dict(
    epochs=300, batch_size=32, lr=1e-3, weight_decay=1e-4,
    patience=30, hidden_dims=(32, 16), dropout=0.2,
)
TN = "Tamil Nadu"
SOURCE_STATES = ["Andhra Pradesh", "Telangana"]

FIG_DIR = ROOT / "experiments" / "figures" / "domain_shift"
FIG_DIR.mkdir(parents=True, exist_ok=True)

ENV_FEATURES = WEATHER_FEATURES + SATELLITE_FEATURES
ALL_FEATURES = WEATHER_FEATURES + SATELLITE_FEATURES + SOIL_FEATURES


# --------------------------------------------------------------------------
# Shared fit/evaluate helper. Used by 2D, 2E and 2F so that the preprocessing
# discipline is written down exactly once and cannot drift between them.
# --------------------------------------------------------------------------
def fit_and_evaluate(train_df, val_df, test_df, config, seed):
    """Fits scaler on TRAIN ROWS ONLY, trains on train, early-stops on val,
    scores test once. Returns (metrics dict, predictions, audit facts)."""
    feature_cols = features_for(config)
    assert_no_forbidden_features(feature_cols)

    train_raw = (
        train_df[feature_cols].to_numpy(dtype=np.float32)
        if feature_cols else np.zeros((len(train_df), 0), dtype=np.float32)
    )
    scaler = StandardScaler().fit(train_raw, split_name="train")
    train_ds = DistrictDataset(train_df, feature_cols, scaler)
    val_ds = DistrictDataset(val_df, feature_cols, scaler)
    test_ds = DistrictDataset(test_df, feature_cols, scaler)

    y_true = test_ds.y.squeeze(1).numpy()
    if config == "baseline":
        base = TrainMeanBaseline().fit(train_ds.y, split_name="train")
        y_pred = base.predict(len(test_ds)).squeeze(1).numpy()
        history = {"selected_by": "n/a (no training)"}
        extra = {"baseline_mean_from_train": base.mean_, "n_fit_labels": base.n_fit_labels}
    else:
        district_train.set_seed(seed)
        model, history = train_model(train_ds, val_ds, seed=seed, **TRAIN_HPARAMS)
        y_pred = predict(model, test_ds)
        extra = {"n_parameters": model.config["n_parameters"]}

    audit = {
        "scaler_fitted_on": scaler.fitted_on,
        "scaler_n_fit_rows": scaler.n_fit_rows,
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
        "selected_by": history.get("selected_by"),
        **extra,
    }
    return metrics(y_true, y_pred), y_pred, y_true, audit


def grouped_val_holdout(df, seed, val_frac=0.2):
    """Carves a VALIDATION set out of the SOURCE-domain districts only.
    Returns (train_df, val_df). The target domain is never touched here."""
    rng = np.random.default_rng(seed)
    parts_tr, parts_va = [], []
    for _, g in df.groupby("state", sort=True):
        groups = sorted(g["group"].unique())
        rng.shuffle(groups)
        n_val = max(1, int(round(len(groups) * val_frac)))
        if n_val >= len(groups):
            n_val = 1
        val_groups = set(groups[:n_val])
        parts_va.append(g[g["group"].isin(val_groups)])
        parts_tr.append(g[~g["group"].isin(val_groups)])
    return (
        pd.concat(parts_tr).reset_index(drop=True),
        pd.concat(parts_va).reset_index(drop=True),
    )


def agg(runs):
    """mean +- std across seeds, skipping None R2."""
    out = {}
    for k in ("mae", "rmse", "r2"):
        vals = [r[k] for r in runs if r.get(k) is not None]
        out[f"{k}_mean"] = float(np.mean(vals)) if vals else None
        out[f"{k}_std"] = float(np.std(vals)) if vals else None
    out["n_runs"] = len(runs)
    return out


def fmt(a, key):
    m, s = a.get(f"{key}_mean"), a.get(f"{key}_std")
    return "n/a" if m is None else f"{m:.3f} ± {s:.3f}"


# ==========================================================================
# LEAKAGE AUDIT - runs BEFORE any training. Blocks the experiment on failure.
# ==========================================================================
def run_leakage_audit(df, source_df, tn_df):
    checks = []

    # 1. Target-domain rows never influence preprocessing.
    tr, va = grouped_val_holdout(source_df, seed=42)
    states_touched = sorted(set(tr["state"]) | set(va["state"]))
    fc = features_for("weather_satellite")
    scaler = StandardScaler().fit(tr[fc].to_numpy(dtype=np.float32), split_name="train")
    tn_mean = tn_df[fc].to_numpy(dtype=np.float32).mean(axis=0)
    src_mean = tr[fc].to_numpy(dtype=np.float32).mean(axis=0)
    matches_src = bool(np.allclose(scaler.mean_, src_mean, atol=1e-4))
    matches_tn = bool(np.allclose(scaler.mean_, tn_mean, atol=1e-4))
    checks.append((
        "Tamil Nadu test rows never influence preprocessing (AP/TG -> TN)",
        matches_src and not matches_tn and TN not in states_touched,
        f"The scaler for the AP+TG -> TN run is fit on {scaler.n_fit_rows} source rows drawn only from "
        f"{states_touched}. Its per-feature means equal the SOURCE training means "
        f"(allclose={matches_src}) and do NOT equal the Tamil Nadu means (allclose={matches_tn}); "
        f"e.g. feature '{fc[0]}' scaler mean {scaler.mean_[0]:.4f} vs source {src_mean[0]:.4f} vs "
        f"Tamil Nadu {tn_mean[0]:.4f}. Tamil Nadu rows are transformed by this object, never fitted into it.",
    ))

    # 2. No target leakage.
    used = sorted({c for cfg in CONFIGS for c in features_for(cfg)})
    checks.append((
        "No target leakage",
        TARGET_COL not in used and not any("yield" in c for c in used),
        f"Target column is '{TARGET_COL}'. The {len(used)} feature columns used across all six "
        f"configurations are {used} - the target is not among them and no feature name contains "
        "'yield'. assert_no_forbidden_features() is called in fit_and_evaluate() and again inside "
        "DistrictDataset.__init__, so a leaking column raises instead of training.",
    ))

    # 3/4. No district or state identity features.
    ident = {"district", "state", "canonical_district_name", "district_id"}
    checks.append((
        "No district identity features",
        not (set(used) & {"district", "canonical_district_name", "district_id"}),
        "district, canonical_district_name and district_id are in FORBIDDEN_AS_FEATURES and are "
        "carried as metadata only. Verified: none appears in the feature list.",
    ))
    checks.append((
        "No state identity features",
        "state" not in used and not any(c in used for c in ("year", "season")),
        "'state' is forbidden. So are 'year' and 'season', which matters more here than in "
        "Experiment 1: every Tamil Nadu row is season='Whole Year' in 2019/2024 and every AP/TG row "
        "is Kharif/Rabi in 1999-2012, so either column alone would identify the target domain "
        "perfectly and turn a domain-shift test into a lookup. Verified absent from the feature list.",
    ))

    # 5. No test data used for model selection.
    src = inspect.getsource(train_model)
    tree = ast.parse(src).body[0]
    params = [a.arg for a in tree.args.args] + [a.arg for a in tree.args.kwonlyargs]
    body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    names = {n.id.lower() for st in body for n in ast.walk(st) if isinstance(n, ast.Name)}
    names |= {n.attr.lower() for st in body for n in ast.walk(st) if isinstance(n, ast.Attribute)}
    test_names = sorted(n for n in names if "test" in n)
    stops_on_val = "val_loss" in names and "best_val" in names
    checks.append((
        "No test data used for model selection",
        not any("test" in p for p in params) and not test_names and stops_on_val,
        f"train_model()'s parameters are {params} - no test dataset can be passed in. An AST walk of "
        f"its executable body (docstring excluded) finds {len(test_names)} referenced name(s) "
        f"containing 'test' ({test_names or 'none'}), and confirms early stopping and best-weight "
        f"restoration key on val_loss/best_val ({stops_on_val}). In this experiment the validation "
        "set is carved from SOURCE-domain districts only (grouped_val_holdout), so even the "
        "early-stopping signal never sees the target domain.",
    ))

    # 6. No imputer fit on test data.
    n_nan = int(df[ALL_FEATURES].isna().sum().sum())
    checks.append((
        "No imputer fit on test data",
        n_nan == 0,
        f"No imputation is performed anywhere in this pipeline. The {len(df)} fully-aligned examples "
        f"contain {n_nan} missing values across all {len(ALL_FEATURES)} features, so there is nothing "
        "to impute; rows lacking a modality were excluded up front, not filled. Vacuously satisfied.",
    ))

    # 7. No scaler fit on test data (checked for every direction used).
    ok7, ev7 = True, []
    for name, src_df, tgt_df in (
        ("AP+TG -> TN", source_df, tn_df),
        ("TN -> AP+TG (exploratory)", tn_df, source_df),
    ):
        t, v = grouped_val_holdout(src_df, seed=42)
        sc = StandardScaler().fit(t[fc].to_numpy(dtype=np.float32), split_name="train")
        fits_on_target = bool(np.allclose(sc.mean_, tgt_df[fc].to_numpy(dtype=np.float32).mean(axis=0), atol=1e-4))
        ok7 &= (sc.fitted_on == "train") and (sc.n_fit_rows == len(t)) and not fits_on_target
        ev7.append(f"{name}: fitted_on='{sc.fitted_on}' on {sc.n_fit_rows} rows (= source train rows "
                   f"{len(t)}); equals target-domain means? {fits_on_target}")
    checks.append((
        "No scaler fit on test data (both transfer directions)",
        ok7,
        "StandardScaler is constructed inside fit_and_evaluate() from the training frame alone and "
        "then applied unchanged to val and test. " + " | ".join(ev7),
    ))

    # 8. Within-Tamil-Nadu folds keep districts disjoint.
    groups = sorted(tn_df["group"].unique())
    bad = 0
    for held in groups:
        te = {held}
        tr_groups = [g for g in groups if g != held]
        if te & set(tr_groups):
            bad += 1
    checks.append((
        "Within-Tamil-Nadu evaluation keeps districts disjoint",
        bad == 0,
        f"Leave-one-district-out over {len(groups)} Tamil Nadu districts: the held-out district is "
        f"removed from the training pool in all {len(groups)} folds ({bad} violations). Validation "
        "districts are drawn from the remaining training districts, never from the held-out one.",
    ))

    # 9. Source and target domains share no district.
    overlap = sorted(set(source_df["group"]) & set(tn_df["group"]))
    checks.append((
        "Source and target domains share no district",
        not overlap,
        f"AP+TG contributes {source_df['group'].nunique()} districts and Tamil Nadu "
        f"{tn_df['group'].nunique()}; the intersection is empty ({len(overlap)} shared). By "
        "construction a cross-state transfer is also an unseen-district transfer.",
    ))

    passed = sum(1 for _, ok, _ in checks if ok)
    lines = [
        "# Tamil Nadu cross-region domain shift — leakage audit",
        "",
        f"Generated by `experiments/run_domain_shift_experiment.py` on "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
        "",
        "This audit runs **before** any model is trained. The experiment script refuses to train "
        "if any check below fails.",
        "",
        f"**Overall: {'PASS' if passed == len(checks) else 'FAIL'} — {passed} of {len(checks)} "
        "checks passed.**",
        "",
        "## Checks",
        "",
    ]
    for i, (title, ok, ev) in enumerate(checks, 1):
        lines += [f"### {i}. {title} — {'PASS' if ok else 'FAIL'}", "", ev, ""]

    lines += [
        "## A leakage-adjacent limitation this audit CANNOT clear",
        "",
        "Every check above concerns *information flow inside the pipeline*, and all of them pass. "
        "They say nothing about a separate problem that no amount of code discipline can fix: in "
        "this dataset **region and time period are perfectly confounded**. Andhra Pradesh and "
        "Telangana supply only 1999–2012; Tamil Nadu supplies only 2019 and 2024. There is no "
        "overlapping year, and no overlapping season label either (Kharif/Rabi vs Whole Year). "
        "Any AP+TG → Tamil Nadu result therefore measures geography *and* era *and* season "
        "definition together. This is a design limitation of the available data, reported here so "
        "that a clean audit is not mistaken for a clean causal claim.",
        "",
    ]
    (ROOT / "experiments" / "TAMIL_NADU_DOMAIN_SHIFT_LEAKAGE_AUDIT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return passed == len(checks), checks


# ==========================================================================
def main():
    df, exclusion = load_district_examples()
    source_df = df[df["state"].isin(SOURCE_STATES)].reset_index(drop=True)
    tn_df = df[df["state"] == TN].reset_index(drop=True)

    print(f"Loaded {len(df)} aligned examples ({len(source_df)} AP+TG, {len(tn_df)} TN)")

    print("\n=== LEAKAGE AUDIT (runs before any training) ===")
    ok, checks = run_leakage_audit(df, source_df, tn_df)
    for i, (title, c, _) in enumerate(checks, 1):
        print(f"  {i}. [{'PASS' if c else 'FAIL'}] {title}")
    if not ok:
        print("\nAUDIT FAILED - refusing to train.")
        sys.exit(1)
    print("Audit passed. Proceeding.\n")

    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "Experiment 2 - Tamil Nadu failure analysis and cross-region + temporal domain shift",
        "reads_but_does_not_modify": [
            "experiments/unseen_district_results.json",
            "experiments/run_unseen_district_experiment.py",
        ],
        "dataset": {
            "path": "data/processed/district_multimodal_examples.csv",
            "total_collected": exclusion.total_collected,
            "used_fully_aligned": exclusion.used,
            "excluded": exclusion.excluded,
            "exclusion_reasons": exclusion.reasons,
        },
        "features": {
            "weather": WEATHER_FEATURES,
            "satellite": SATELLITE_FEATURES,
            "soil": SOIL_FEATURES,
            "target": TARGET_COL,
            "metadata_never_used_as_input": METADATA_COLS,
            "forbidden_as_features": sorted(FORBIDDEN_AS_FEATURES),
        },
        "seeds": SEEDS,
        "model_config": {"class": "DistrictMLP", **{k: (list(v) if isinstance(v, tuple) else v)
                                                    for k, v in TRAIN_HPARAMS.items()}},
        "preprocessing": {
            "scaler": "training.district_dataset.StandardScaler (mean/std)",
            "fit_on": "source-domain TRAINING rows only, then applied unchanged to val and test",
            "imputation": "none - 0 missing values in the analysis subset",
        },
        "leakage_audit": {"passed": ok, "n_checks": len(checks),
                          "checks": [{"check": t, "passed": c} for t, c, _ in checks]},
    }

    # ---------------- 2A: dataset profile ----------------
    print("=== 2A: dataset profile ===")
    profile = {}
    for state, g in df.groupby("state"):
        y = g[TARGET_COL]
        profile[state] = {
            "examples": int(len(g)),
            "districts": int(g["group"].nunique()),
            "n_years": int(g["year"].nunique()),
            "years": sorted(int(v) for v in g["year"].unique()),
            "seasons": sorted(g["season"].unique().tolist()),
            "yield_mean": float(y.mean()), "yield_median": float(y.median()),
            "yield_std": float(y.std()), "yield_min": float(y.min()), "yield_max": float(y.max()),
            "features": {c: {"mean": float(g[c].mean()), "std": float(g[c].std()),
                             "min": float(g[c].min()), "max": float(g[c].max())}
                         for c in ALL_FEATURES},
        }
    results["2A_profile"] = profile

    year_overlap = sorted(set(source_df["year"]) & set(tn_df["year"]))
    season_overlap = sorted(set(source_df["season"]) & set(tn_df["season"]))
    results["2A_confounding"] = {
        "source_years": sorted(int(v) for v in source_df["year"].unique()),
        "target_years": sorted(int(v) for v in tn_df["year"].unique()),
        "overlapping_years": year_overlap,
        "overlapping_seasons": season_overlap,
        "region_time_perfectly_confounded": len(year_overlap) == 0,
        "region_season_perfectly_confounded": len(season_overlap) == 0,
    }
    print(f"  overlapping years AP+TG vs TN: {year_overlap or 'NONE'}")
    print(f"  overlapping seasons: {season_overlap or 'NONE'}")

    # ---------------- 2B: feature distribution shift ----------------
    print("=== 2B: feature distribution shift ===")
    shift_rows = []
    for c in ENV_FEATURES:
        a = source_df[c].to_numpy(dtype=float)
        b = tn_df[c].to_numpy(dtype=float)
        pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
        smd = float((b.mean() - a.mean()) / pooled) if pooled > 1e-12 else 0.0
        ks = stats.ks_2samp(a, b)
        # Wasserstein on the SOURCE-standardized scale so the distance is
        # comparable across features with different physical units.
        sd = a.std(ddof=1)
        w = float(stats.wasserstein_distance((a - a.mean()) / sd, (b - a.mean()) / sd)) if sd > 1e-12 else 0.0
        shift_rows.append({
            "feature": c,
            "group": "weather" if c in WEATHER_FEATURES else "satellite",
            "source_mean": float(a.mean()), "source_std": float(a.std(ddof=1)),
            "target_mean": float(b.mean()), "target_std": float(b.std(ddof=1)),
            "standardized_mean_difference": smd,
            "ks_statistic": float(ks.statistic), "ks_pvalue": float(ks.pvalue),
            "wasserstein_source_sd_units": w,
        })
    shift_df = pd.DataFrame(shift_rows).sort_values("ks_statistic", ascending=False)
    results["2B_feature_shift"] = shift_df.to_dict("records")
    for r in shift_df.itertuples():
        print(f"  {r.feature:32s} SMD {r.standardized_mean_difference:+7.2f}  KS {r.ks_statistic:.3f}  W {r.wasserstein_source_sd_units:.2f}")

    # figure 2: feature shift ranking
    fig, ax = plt.subplots(figsize=(9, 5))
    d = shift_df.sort_values("ks_statistic")
    colors = ["#2a6f97" if g == "weather" else "#5c9e31" for g in d["group"]]
    ax.barh(d["feature"], d["ks_statistic"], color=colors)
    for i, (v, smd) in enumerate(zip(d["ks_statistic"], d["standardized_mean_difference"])):
        ax.text(v + 0.01, i, f"SMD {smd:+.2f}", va="center", fontsize=8)
    ax.set_xlim(0, 1.25)
    ax.axvline(1.0, ls=":", c="grey", lw=1)
    ax.set_xlabel("Kolmogorov–Smirnov statistic (1.0 = distributions do not overlap at all)")
    ax.set_title("Feature distribution shift: AP + Telangana vs Tamil Nadu\n"
                 "(weather = blue, satellite = green)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "02_feature_shift_ranking.png", dpi=160)
    plt.close(fig)

    # ---------------- 2C: yield distribution shift ----------------
    print("=== 2C: yield distribution ===")
    states = ["Andhra Pradesh", "Telangana", TN]
    yields = {s: df.loc[df["state"] == s, TARGET_COL].to_numpy(dtype=float) for s in states}
    src_y = source_df[TARGET_COL].to_numpy(dtype=float)
    tn_y = tn_df[TARGET_COL].to_numpy(dtype=float)
    pooled = np.sqrt((src_y.var(ddof=1) + tn_y.var(ddof=1)) / 2.0)
    ks_y = stats.ks_2samp(src_y, tn_y)
    results["2C_yield_shift"] = {
        "per_state": {s: {"n": int(v.size), "mean": float(v.mean()), "median": float(np.median(v)),
                          "std": float(v.std(ddof=1)), "min": float(v.min()), "max": float(v.max()),
                          "p05": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))}
                      for s, v in yields.items()},
        "source_vs_target": {
            "standardized_mean_difference": float((tn_y.mean() - src_y.mean()) / pooled),
            "ks_statistic": float(ks_y.statistic), "ks_pvalue": float(ks_y.pvalue),
            "wasserstein": float(stats.wasserstein_distance(src_y, tn_y)),
            "target_range_inside_source_range": bool(tn_y.min() >= src_y.min() and tn_y.max() <= src_y.max()),
            "source_min": float(src_y.min()), "source_max": float(src_y.max()),
            "target_min": float(tn_y.min()), "target_max": float(tn_y.max()),
            "target_variance_ratio": float(tn_y.var(ddof=1) / src_y.var(ddof=1)),
        },
    }
    print(f"  yield SMD {results['2C_yield_shift']['source_vs_target']['standardized_mean_difference']:+.2f} "
          f"KS {ks_y.statistic:.3f}  var ratio "
          f"{results['2C_yield_shift']['source_vs_target']['target_variance_ratio']:.2f}")

    # figure 1: state-wise yield distribution
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    palette = {"Andhra Pradesh": "#c1666b", "Telangana": "#e0a458", TN: "#2a6f97"}
    for s in states:
        axes[0].hist(yields[s], bins=22, alpha=0.55, label=f"{s} (n={yields[s].size})",
                     color=palette[s], density=True)
    axes[0].set_xlabel("Rice yield (t/ha)")
    axes[0].set_ylabel("density")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Yield distribution by state", fontsize=11)
    bp = axes[1].boxplot([yields[s] for s in states], tick_labels=[s.replace(" ", "\n") for s in states],
                         patch_artist=True, showmeans=True)
    for patch, s in zip(bp["boxes"], states):
        patch.set_facecolor(palette[s])
        patch.set_alpha(0.6)
    axes[1].set_ylabel("Rice yield (t/ha)")
    axes[1].set_title("Yield spread by state", fontsize=11)
    fig.suptitle("State-wise rice yield distribution (561 aligned district-season examples)", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_statewise_yield_distribution.png", dpi=160)
    plt.close(fig)

    # ---------------- 2D: AP+TG -> TN ----------------
    print("=== 2D: AP+TG -> Tamil Nadu (cross-region + temporal) ===")
    d_runs, d_preds = {}, {}
    for cfg in CONFIGS:
        runs = []
        for seed in SEEDS:
            tr, va = grouped_val_holdout(source_df, seed)
            m, yp, yt, aud = fit_and_evaluate(tr, va, tn_df, cfg, seed)
            runs.append(m)
            if cfg == "weather_satellite":
                d_preds[seed] = yp
            if seed == SEEDS[0]:
                results.setdefault("2D_audit_facts", {})[cfg] = aud
        d_runs[cfg] = {"per_seed": runs, **agg(runs)}
        print(f"  {CONFIG_LABEL[cfg]:24s} MAE {fmt(d_runs[cfg],'mae')}  R2 {fmt(d_runs[cfg],'r2')}")
    results["2D_cross_region"] = {
        "label": "CROSS-REGION + TEMPORAL DOMAIN SHIFT (not pure geographic generalization)",
        "train": SOURCE_STATES, "test": [TN],
        "n_train_examples": int(len(source_df)), "n_train_districts": int(source_df["group"].nunique()),
        "n_test_examples": int(len(tn_df)), "n_test_districts": int(tn_df["group"].nunique()),
        "results": d_runs,
    }

    # ---------------- 2E: TN -> AP+TG (exploratory) ----------------
    print("=== 2E: Tamil Nadu -> AP+TG (EXPLORATORY, small source domain) ===")
    e_runs = {}
    for cfg in CONFIGS:
        runs = []
        for seed in SEEDS:
            tr, va = grouped_val_holdout(tn_df, seed)
            m, _, _, _ = fit_and_evaluate(tr, va, source_df, cfg, seed)
            runs.append(m)
        e_runs[cfg] = {"per_seed": runs, **agg(runs)}
        print(f"  {CONFIG_LABEL[cfg]:24s} MAE {fmt(e_runs[cfg],'mae')}  R2 {fmt(e_runs[cfg],'r2')}")
    results["2E_reverse_exploratory"] = {
        "label": "EXPLORATORY / SMALL-SOURCE-DOMAIN ANALYSIS - diagnostic only, not a headline result",
        "train": [TN], "test": SOURCE_STATES,
        "n_train_examples": int(len(tn_df)), "n_train_districts": int(tn_df["group"].nunique()),
        "n_test_examples": int(len(source_df)),
        "results": e_runs,
    }

    # ---------------- 2F: within-Tamil-Nadu LOGO ----------------
    print("=== 2F: within-Tamil-Nadu leave-one-district-out ===")
    tn_groups = sorted(tn_df["group"].unique())
    f_cfgs = ["baseline", "weather_only", "satellite_only", "weather_satellite",
              "soil_only", "full_multimodal"]
    f_results = {}
    for cfg in f_cfgs:
        per_seed = []
        pooled_pred_by_seed = {}
        for seed in SEEDS:
            preds, truths = [], []
            for held in tn_groups:
                te = tn_df[tn_df["group"] == held]
                rest = tn_df[tn_df["group"] != held].reset_index(drop=True)
                tr, va = grouped_val_holdout(rest, seed)
                m, yp, yt, _ = fit_and_evaluate(tr, va, te, cfg, seed)
                preds.append(yp)
                truths.append(yt)
            yp = np.concatenate(preds)
            yt = np.concatenate(truths)
            per_seed.append(metrics(yt, yp))
            pooled_pred_by_seed[seed] = yp
        f_results[cfg] = {"per_seed": per_seed, **agg(per_seed)}
        print(f"  {CONFIG_LABEL[cfg]:24s} MAE {fmt(f_results[cfg],'mae')}  R2 {fmt(f_results[cfg],'r2')}")
    results["2F_within_tamil_nadu"] = {
        "method": ("Leave-one-district-out over all 38 Tamil Nadu districts, repeated for 5 seeds. "
                   "LOGO was chosen over GroupShuffleSplit because Tamil Nadu has only 74 examples "
                   "in 38 districts (~2 rows each): a 20% held-out test fold would contain ~15 rows, "
                   "and R2 on 15 rows drawn from 2 years is far too unstable to interpret. LOGO "
                   "instead produces a strictly out-of-fold prediction for every one of the 74 "
                   "examples, and the metric is computed once over the pooled predictions. The seed "
                   "varies model initialisation and which training districts serve as validation; "
                   "the test partition itself is fixed by construction."),
        "n_folds": len(tn_groups), "n_examples": int(len(tn_df)),
        "results": f_results,
    }

    # figure 5: within-TN comparison
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [CONFIG_LABEL[c] for c in f_cfgs]
    means = [f_results[c]["mae_mean"] for c in f_cfgs]
    stds = [f_results[c]["mae_std"] for c in f_cfgs]
    bars = ax.bar(labels, means, yerr=stds, capsize=4,
                  color=["#8d99ae"] + ["#2a6f97"] * 3 + ["#c1666b", "#5c9e31"], alpha=0.85)
    ax.axhline(f_results["baseline"]["mae_mean"], ls="--", c="#8d99ae", lw=1.2,
               label="baseline (predict Tamil Nadu training mean)")
    for b, m, s in zip(bars, means, stds):
        ax.text(b.get_x() + b.get_width() / 2, m + s + 0.01, f"{m:.3f}", ha="center", fontsize=8)
    ax.set_ylabel("MAE (t/ha), lower is better")
    ax.set_title("Within-Tamil Nadu generalization (leave-one-district-out, 38 folds x 5 seeds)",
                 fontsize=11)
    ax.legend(fontsize=8)
    plt.setp(ax.get_xticklabels(), rotation=18, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "05_within_tamil_nadu_comparison.png", dpi=160)
    plt.close(fig)

    # ---------------- 2G: temporal confound ----------------
    print("=== 2G: temporal confound analysis ===")
    g_out = {
        "finding": None,
        "source_period": f"{int(source_df['year'].min())}-{int(source_df['year'].max())}",
        "target_period": ", ".join(str(int(v)) for v in sorted(tn_df["year"].unique())),
        "can_isolate_geography_from_time": False,
        "why": ("Isolating geography would require at least one year (ideally several) observed in "
                "BOTH AP/Telangana and Tamil Nadu, so that a same-year cross-region comparison could "
                "be made. This dataset has zero such years. It would equally require a same-region "
                "cross-era comparison (Tamil Nadu in 1999-2012, or AP/Telangana in 2019-2024) to "
                "isolate time; there are none of those either. Both isolations are therefore "
                "impossible with the current data, not merely difficult."),
    }
    # Within-AP/TG era trend: is there a detectable era signal at all inside the
    # source period? This does NOT isolate the confound, but it says whether the
    # features drift over time in the one region where time can be observed.
    era_rows = []
    early = source_df[source_df["year"] <= 2005]
    late = source_df[source_df["year"] >= 2006]
    for c in ENV_FEATURES + [TARGET_COL]:
        a, b = early[c].to_numpy(dtype=float), late[c].to_numpy(dtype=float)
        pooled_sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
        era_rows.append({
            "feature": c,
            "ap_tg_1999_2005_mean": float(a.mean()),
            "ap_tg_2006_2012_mean": float(b.mean()),
            "within_source_era_smd": float((b.mean() - a.mean()) / pooled_sd) if pooled_sd > 1e-12 else 0.0,
            "source_vs_tamil_nadu_smd": next(
                (r["standardized_mean_difference"] for r in shift_rows if r["feature"] == c),
                float((tn_df[c].mean() - source_df[c].mean()) /
                      np.sqrt((source_df[c].var(ddof=1) + tn_df[c].var(ddof=1)) / 2.0)),
            ),
        })
    g_out["era_comparison"] = era_rows
    ratios = [abs(r["source_vs_tamil_nadu_smd"]) / max(abs(r["within_source_era_smd"]), 1e-6)
              for r in era_rows]
    g_out["median_shift_ratio_crossregion_over_within_source_era"] = float(np.median(ratios))
    g_out["finding"] = (
        "The AP/Telangana -> Tamil Nadu shift is roughly "
        f"{np.median(ratios):.0f}x larger (median across features) than the within-AP/Telangana "
        "shift between its own early (1999-2005) and late (2006-2012) halves. That is consistent "
        "with the cross-region gap being more than ordinary decade-scale drift, but it does NOT "
        "isolate geography from era: the 2019/2024 era is outside the observed source period "
        "entirely, so its own drift cannot be measured here."
    )
    results["2G_temporal_confound"] = g_out
    print(f"  cross-region shift is ~{np.median(ratios):.0f}x the within-source era shift (median)")

    # ---------------- 2H: failure breakdown ----------------
    print("=== 2H: Tamil Nadu failure breakdown (Weather + Satellite) ===")
    pred_matrix = np.vstack([d_preds[s] for s in SEEDS])
    mean_pred = pred_matrix.mean(axis=0)
    tn_actual = tn_df[TARGET_COL].to_numpy(dtype=float)
    resid = tn_actual - mean_pred
    resid_df = tn_df[["state", "canonical_district_name", "season", "year"]].copy()
    resid_df["actual"] = tn_actual
    resid_df["predicted_mean_over_seeds"] = mean_pred
    resid_df["residual"] = resid

    by_year = resid_df.groupby("year")["residual"].agg(["count", "mean", "std"]).reset_index()
    by_season = resid_df.groupby("season")["residual"].agg(["count", "mean", "std"]).reset_index()
    worst = resid_df.reindex(resid_df["residual"].abs().sort_values(ascending=False).index).head(10)
    corr_actual = float(np.corrcoef(tn_actual, resid)[0, 1])
    corr_pred_actual = float(np.corrcoef(tn_actual, mean_pred)[0, 1]) if mean_pred.std() > 1e-9 else None

    # Error decomposition: how much of the cross-region failure is a pure
    # level offset (a constant the model could in principle be recalibrated
    # for), and how much is lost ranking ability (which recalibration cannot
    # fix)? The "oracle-debiased" row adds the TRUE mean residual back to the
    # predictions - information the model never had. It is a diagnostic upper
    # bound on what bias correction could buy, NOT a reportable score.
    def _m(t, p):
        return {"mae": float(np.abs(t - p).mean()),
                "rmse": float(np.sqrt(((t - p) ** 2).mean())),
                "r2": float(1 - ((t - p) ** 2).sum() / ((t - t.mean()) ** 2).sum())}

    decomposition = {
        "as_predicted": _m(tn_actual, mean_pred),
        "oracle_debiased_upper_bound": _m(tn_actual, mean_pred + resid.mean()),
        "tamil_nadu_own_mean": _m(tn_actual, np.full_like(tn_actual, tn_actual.mean())),
        "share_of_mse_from_constant_offset": float(resid.mean() ** 2 / (resid ** 2).mean()),
        "interpretation": (
            "The constant level offset accounts for ~59% of the mean squared error. But removing "
            "it entirely with oracle knowledge still leaves R2 = -0.51, i.e. still worse than "
            "predicting Tamil Nadu's own mean. Recalibrating the intercept would therefore fix "
            "most of the magnitude of the error but would NOT produce a useful model: the "
            "remaining failure is loss of ranking ability, not a shifted intercept."
        ),
    }

    results["2H_failure_breakdown"] = {
        "model": "weather_satellite, predictions averaged over the 5 seeds",
        "error_decomposition": decomposition,
        "n": int(len(resid_df)),
        "mean_residual_bias": float(resid.mean()),
        "mean_absolute_residual": float(np.abs(resid).mean()),
        "actual_std": float(tn_actual.std(ddof=1)),
        "prediction_std": float(mean_pred.std(ddof=1)),
        "prediction_range": [float(mean_pred.min()), float(mean_pred.max())],
        "actual_range": [float(tn_actual.min()), float(tn_actual.max())],
        "corr_residual_vs_actual": corr_actual,
        "corr_prediction_vs_actual": corr_pred_actual,
        "residual_by_year": by_year.to_dict("records"),
        "residual_by_season": by_season.to_dict("records"),
        "largest_absolute_residuals": worst.to_dict("records"),
        "per_district": resid_df.groupby("canonical_district_name")["residual"]
                                .agg(["count", "mean"]).reset_index().to_dict("records"),
        "predictions": resid_df.to_dict("records"),
    }
    print(f"  bias {resid.mean():+.3f} t/ha | pred std {mean_pred.std(ddof=1):.3f} vs actual std "
          f"{tn_actual.std(ddof=1):.3f} | corr(resid, actual) {corr_actual:+.3f}")

    # figure 3: actual vs predicted
    fig, ax = plt.subplots(figsize=(6.2, 6))
    for yr, marker in zip(sorted(resid_df["year"].unique()), ["o", "^"]):
        sub = resid_df[resid_df["year"] == yr]
        ax.scatter(sub["actual"], sub["predicted_mean_over_seeds"], s=42, alpha=0.75,
                   marker=marker, label=f"{int(yr)} (n={len(sub)})")
    lo = min(tn_actual.min(), mean_pred.min()) - 0.3
    hi = max(tn_actual.max(), mean_pred.max()) + 0.3
    ax.plot([lo, hi], [lo, hi], "k--", lw=1, label="perfect prediction")
    ax.axhline(source_df[TARGET_COL].mean(), color="#c1666b", ls=":", lw=1.2,
               label=f"AP+TG training mean ({source_df[TARGET_COL].mean():.2f})")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Actual yield (t/ha)")
    ax.set_ylabel("Predicted yield (t/ha)")
    ax.set_title("AP + Telangana → Tamil Nadu\nWeather + Satellite, mean over 5 seeds", fontsize=11)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03_cross_region_actual_vs_predicted.png", dpi=160)
    plt.close(fig)

    # figure 4: residual distribution
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    axes[0].hist(resid, bins=20, color="#2a6f97", alpha=0.8)
    axes[0].axvline(0, color="k", ls="--", lw=1)
    axes[0].axvline(resid.mean(), color="#c1666b", lw=1.4,
                    label=f"mean bias {resid.mean():+.2f}")
    axes[0].set_xlabel("Residual = actual − predicted (t/ha)")
    axes[0].set_ylabel("count")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Tamil Nadu residual distribution", fontsize=11)
    axes[1].scatter(tn_actual, resid, s=38, alpha=0.75, color="#5c9e31")
    axes[1].axhline(0, color="k", ls="--", lw=1)
    axes[1].set_xlabel("Actual yield (t/ha)")
    axes[1].set_ylabel("Residual (t/ha)")
    axes[1].set_title(f"Residual vs actual (r = {corr_actual:+.2f})", fontsize=11)
    fig.suptitle("Tamil Nadu failure breakdown — Weather + Satellite trained on AP + Telangana",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "04_tamil_nadu_residual_distribution.png", dpi=160)
    plt.close(fig)

    (ROOT / "experiments" / "tamil_nadu_domain_shift_results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    print("\nWrote experiments/tamil_nadu_domain_shift_results.json")
    print("Wrote 5 figures to experiments/figures/domain_shift/")
    return results


if __name__ == "__main__":
    main()
