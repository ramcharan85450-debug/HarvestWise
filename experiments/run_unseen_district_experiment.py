"""
Unseen-district generalization experiment for the district-level dataset.

THE QUESTION: can a model trained on some agricultural districts predict
yield in districts it has never seen? Not "can it predict a held-out year
in a district it already memorized" - this project's own Experiment 1
already showed that a soil-only control matched a full multimodal model on
the field-level data, i.e. the model was reading location identity rather
than agronomy. This experiment is built to expose that failure mode if it
is still present at district scale, rather than to hide it.

DESIGN
------
* 561 fully-aligned district-season examples (see training/district_dataset.py
  for what "fully aligned" means and which 307 rows are excluded and why).
* Districts, not rows, are split. The same district never appears on both
  sides of any split.
* 5 deterministic repeated grouped splits (seeds 42-46). Within a seed,
  every configuration sees the IDENTICAL split, so configurations differ
  only in which feature columns they receive.
* Scaler fit on training rows only, per (seed, configuration).
* Early stopping and checkpoint selection on validation loss only.
* Six configurations: baseline (train mean), weather-only, satellite-only,
  weather+satellite, soil-only (the mandatory shortcut control), and full
  multimodal.

The leakage audit runs FIRST and the experiment refuses to train if any
check fails.

Run:
    python -m experiments.run_unseen_district_experiment
    python -m experiments.run_unseen_district_experiment --audit-only
"""

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from training.district_dataset import (
    FORBIDDEN_AS_FEATURES,
    METADATA_COLS,
    SATELLITE_FEATURES,
    SOIL_FEATURES,
    TARGET_COL,
    WEATHER_FEATURES,
    build_split_datasets,
    features_for,
    load_district_examples,
    split_summary,
    stratified_group_split,
    verify_disjoint,
)
from training.district_model import TrainMeanBaseline
from training.district_train import metrics, predict, train_model

EXPERIMENTS_DIR = Path(__file__).resolve().parent
FIGURES_DIR = EXPERIMENTS_DIR / "figures" / "unseen_district"
AUDIT_PATH = EXPERIMENTS_DIR / "UNSEEN_DISTRICT_LEAKAGE_AUDIT.md"
RESULTS_JSON = EXPERIMENTS_DIR / "unseen_district_results.json"

SEEDS = [42, 43, 44, 45, 46]
CONFIGS = [
    ("baseline", "Baseline (train mean)"),
    ("weather_only", "A - Weather only"),
    ("satellite_only", "B - Satellite only"),
    ("weather_satellite", "C - Weather + Satellite"),
    ("soil_only", "D - Soil only (control)"),
    ("full_multimodal", "E - Full multimodal"),
]
# Hyperparameters actually passed to train_model(). Chosen once, before any
# results were seen, and identical for every configuration and every seed -
# no per-configuration tuning, and nothing selected using test data.
TRAIN_HPARAMS = {
    "epochs": 300,
    "batch_size": 32,
    "lr": 1e-3,
    "weight_decay": 1e-4,
    "patience": 30,
    "hidden_dims": (32, 16),
    "dropout": 0.2,
}
# Recorded in the reproducibility JSON alongside the above; not arguments.
TRAIN_SETTINGS = {**TRAIN_HPARAMS, "loss": "MSELoss", "optimizer": "Adam"}


# --------------------------------------------------------------------------
# Leakage audit (Phase 9). Runs before any training.
# --------------------------------------------------------------------------
def run_leakage_audit(df, report) -> tuple[bool, list[dict], dict]:
    checks: list[dict] = []
    evidence: dict = {}

    # 1 & 2: district disjointness, for every seed.
    disjoint_all = True
    per_seed = {}
    for seed in SEEDS:
        splits = stratified_group_split(df, seed)
        v = verify_disjoint(splits)
        per_seed[seed] = v
        if not v["disjoint"]:
            disjoint_all = False
    evidence["disjointness_per_seed"] = per_seed
    checks.append({
        "id": 1,
        "check": "No overlapping districts between TRAIN and TEST",
        "passed": all(not per_seed[s]["train_test_overlap"] for s in SEEDS),
        "detail": f"Checked all {len(SEEDS)} seeds; train∩test was empty in every one.",
    })
    checks.append({
        "id": 2,
        "check": "No overlapping districts between VALIDATION and TEST",
        "passed": all(not per_seed[s]["val_test_overlap"] for s in SEEDS),
        "detail": f"Checked all {len(SEEDS)} seeds; val∩test was empty in every one. "
                  f"(train∩val was also empty in every seed.)",
    })

    # 3: scaler fitted on training rows only.
    splits = stratified_group_split(df, SEEDS[0])
    train_rows = int(df["group"].isin(splits["train"]).sum())
    _, _, _, scaler = build_split_datasets(df, splits, features_for("full_multimodal"))
    checks.append({
        "id": 3,
        "check": "Scalers fit ONLY on training data",
        "passed": scaler.fitted_on == "train" and scaler.n_fit_rows == train_rows,
        "detail": f"StandardScaler.fitted_on='{scaler.fitted_on}', fitted on {scaler.n_fit_rows} rows, "
                  f"which equals the training split's row count ({train_rows}). "
                  f"build_split_datasets() computes the scaler from the training frame and then "
                  f"applies that same fitted object to val and test.",
    })

    # 4: imputers.
    all_feats = WEATHER_FEATURES + SATELLITE_FEATURES + SOIL_FEATURES
    n_nan = int(df[all_feats].isna().sum().sum())
    checks.append({
        "id": 4,
        "check": "Imputers fit ONLY on training data",
        "passed": n_nan == 0,
        "detail": f"No imputation is performed anywhere in this pipeline, because none is needed: "
                  f"the {len(df)} fully-aligned examples contain {n_nan} missing values across all "
                  f"{len(all_feats)} features. Rows lacking any modality were excluded up front "
                  f"(counted in the exclusion report) rather than imputed. Vacuously satisfied.",
    })

    # 5: baseline mean from training labels only.
    tr_ds, _, te_ds, _ = build_split_datasets(df, splits, features_for("baseline"))
    bl = TrainMeanBaseline().fit(tr_ds.y, split_name="train")
    train_mean = float(tr_ds.y.mean().item())
    test_mean = float(te_ds.y.mean().item())
    checks.append({
        "id": 5,
        "check": "Baseline mean computed ONLY from training labels",
        "passed": bl.fitted_on == "train" and bl.n_fit_labels == len(tr_ds) and abs(bl.mean_ - train_mean) < 1e-9,
        "detail": f"TrainMeanBaseline.fit() received {bl.n_fit_labels} labels (= training rows) and produced "
                  f"{bl.mean_:.4f} t/ha, exactly the training-label mean. The test split's own mean is "
                  f"{test_mean:.4f} t/ha and is never read during fitting - the two differ, confirming the "
                  f"baseline is not secretly the test mean.",
    })

    # 6: test never used for early stopping.
    #
    # Checked structurally rather than by grepping the source text: an
    # earlier version of this audit searched train_model()'s source for the
    # string "test" and failed on its own docstring, which explains that no
    # test data is used. The real guarantee is the function signature (it
    # accepts no test dataset, so it cannot read one) plus the AST of its
    # body (no name containing "test" is referenced in executable code).
    import ast
    import inspect

    from training import district_train

    sig = inspect.signature(district_train.train_model)
    has_test_param = any("test" in p.lower() for p in sig.parameters)

    body = ast.parse(inspect.getsource(district_train.train_model)).body[0]
    body_nodes = [n for n in body.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    referenced_names = {
        n.id.lower() for stmt in body_nodes for n in ast.walk(stmt) if isinstance(n, ast.Name)
    } | {
        n.attr.lower() for stmt in body_nodes for n in ast.walk(stmt) if isinstance(n, ast.Attribute)
    }
    test_refs = sorted(n for n in referenced_names if "test" in n)

    # And the positive half: early stopping must actually key on validation.
    stopping_uses_val = "val_loss" in referenced_names and "best_val" in referenced_names

    checks.append({
        "id": 6,
        "check": "Test data never used for early stopping / checkpoint selection",
        "passed": (not has_test_param) and (not test_refs) and stopping_uses_val,
        "detail": f"train_model()'s signature is ({', '.join(sig.parameters)}) - it accepts no test dataset, "
                  f"so it is structurally incapable of reading one. An AST walk of its executable body "
                  f"(docstring excluded) finds {len(test_refs)} referenced name(s) containing 'test' "
                  f"({test_refs or 'none'}), and confirms early stopping keys on `val_loss`/`best_val`. "
                  f"The test split is touched exactly once per (seed, configuration), by the caller, after "
                  f"training returns.",
    })

    # 7, 8, 9: forbidden features.
    used_feature_cols = sorted(set(WEATHER_FEATURES + SATELLITE_FEATURES + SOIL_FEATURES))
    target_in_features = TARGET_COL in used_feature_cols
    source_cols = [c for c in used_feature_cols if "source" in c or "url" in c.lower()]
    id_cols = [c for c in used_feature_cols if c in {"state", "district", "canonical_district_name", "district_id"}]
    evidence["feature_columns_used"] = used_feature_cols
    checks.append({
        "id": 7,
        "check": "Target not included as a feature",
        "passed": not target_in_features,
        "detail": f"Target column is '{TARGET_COL}'. The {len(used_feature_cols)} feature columns across all "
                  f"configurations are {used_feature_cols} - the target is not among them. "
                  f"training/district_dataset.assert_no_forbidden_features() raises at dataset construction "
                  f"if it ever were.",
    })
    checks.append({
        "id": 8,
        "check": "Source URLs / provenance strings not used as features",
        "passed": not source_cols,
        "detail": f"No feature column contains a source or URL ({source_cols or 'none found'}). "
                  f"yield_source_url, weather_source, satellite_source and soil_source are all in "
                  f"FORBIDDEN_AS_FEATURES. This matters concretely here: Tamil Nadu's rows cite different "
                  f"source URLs than Andhra Pradesh's, so a source string is a perfect region fingerprint.",
    })
    checks.append({
        "id": 9,
        "check": "District / state identifiers not used as features",
        "passed": not id_cols,
        "detail": f"No feature column is an identifier ({id_cols or 'none found'}). state, district, "
                  f"canonical_district_name and district_id are all in FORBIDDEN_AS_FEATURES and are kept "
                  f"as metadata only. Additionally `year` and `season` are excluded despite being ordinary "
                  f"columns: in this dataset every Tamil Nadu example is 'Whole Year' in 2019/2024 while "
                  f"every AP/Telangana example is Kharif/Rabi in 1999-2012, so either column would identify "
                  f"the region perfectly and defeat the unseen-district design.",
    })

    all_passed = all(c["passed"] for c in checks) and disjoint_all
    return all_passed, checks, evidence


def write_audit(passed: bool, checks: list[dict], evidence: dict, df, report) -> None:
    lines = [
        "# Unseen-district evaluation — leakage audit",
        "",
        f"Generated by `experiments/run_unseen_district_experiment.py` on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        "This audit runs **before** any model is trained. The experiment script refuses to train if any "
        "check below fails.",
        "",
        f"**Overall: {'PASS' if passed else 'FAIL'} — {sum(c['passed'] for c in checks)} of {len(checks)} checks passed.**",
        "",
        "## Checks",
        "",
    ]
    for c in checks:
        lines += [
            f"### {c['id']}. {c['check']} — {'PASS' if c['passed'] else 'FAIL'}",
            "",
            c["detail"],
            "",
        ]

    lines += ["## Per-seed district disjointness (the core guarantee)", "",
              "| Seed | Train districts | Val districts | Test districts | train∩test | val∩test | train∩val |",
              "|---|---|---|---|---|---|---|"]
    for seed, v in evidence["disjointness_per_seed"].items():
        lines.append(
            f"| {seed} | {v['train_districts']} | {v['val_districts']} | {v['test_districts']} | "
            f"{len(v['train_test_overlap'])} | {len(v['val_test_overlap'])} | {len(v['train_val_overlap'])} |"
        )

    lines += [
        "",
        "## Feature columns actually used (all configurations combined)",
        "",
        "```",
        "\n".join(evidence["feature_columns_used"]),
        "```",
        "",
        f"{len(evidence['feature_columns_used'])} environmental features in total. Every other column in "
        f"`data/processed/district_multimodal_examples.csv` is either the target, metadata, provenance, or "
        f"data-quality bookkeeping, and is listed in `FORBIDDEN_AS_FEATURES` with a stated reason in "
        f"`training/district_dataset.py`'s module docstring.",
        "",
        "## Dataset used",
        "",
        f"- Collected rows in the aligned CSV: **{report.total_collected}**",
        f"- Used (fully aligned: real weather AND satellite AND soil): **{report.used}**",
        f"- Excluded: **{report.excluded}**",
        f"- Missing values remaining in the used subset's features: "
        f"**{report.reasons.get('_feature_nans_remaining_in_used_subset', 'n/a')}**",
    ]
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Experiment
# --------------------------------------------------------------------------
def run_experiments(df) -> tuple[dict, dict, dict]:
    per_seed_results: dict = {}
    pooled_predictions: dict = {c: {"y_true": [], "y_pred": [], "state": []} for c, _ in CONFIGS}
    split_records: dict = {}

    for seed in SEEDS:
        splits = stratified_group_split(df, seed)
        split_records[seed] = {"groups": splits, "summary": split_summary(df, splits)}
        per_seed_results[seed] = {}

        for config, label in CONFIGS:
            feature_cols = features_for(config)
            train_ds, val_ds, test_ds, scaler = build_split_datasets(df, splits, feature_cols)

            if config == "baseline":
                baseline = TrainMeanBaseline().fit(train_ds.y, split_name="train")
                y_pred = baseline.predict(len(test_ds)).squeeze(1).numpy()
                history = {"selected_by": "n/a (no training)", "train_mean_t_ha": baseline.mean_}
            else:
                model, history = train_model(train_ds, val_ds, seed=seed, **TRAIN_HPARAMS)
                y_pred = predict(model, test_ds)

            y_true = test_ds.y.squeeze(1).numpy()
            m = metrics(y_true, y_pred)
            per_seed_results[seed][config] = {"label": label, "metrics": m, "history_summary": {
                k: history[k] for k in ("best_epoch", "best_val_loss", "epochs_run", "selected_by", "train_mean_t_ha")
                if k in history
            }}

            pooled_predictions[config]["y_true"].extend(y_true.tolist())
            pooled_predictions[config]["y_pred"].extend(np.asarray(y_pred).ravel().tolist())
            pooled_predictions[config]["state"].extend([md["state"] for md in test_ds.metadata])

            r2s = f"{m['r2']:.3f}" if m["r2"] is not None else "n/a"
            print(f"  seed {seed} {label:<28} MAE={m['mae']:.3f} RMSE={m['rmse']:.3f} R2={r2s} (n={m['n']})")

    # Per-state performance on pooled test-fold predictions. Included because
    # "generalizes to unseen districts" can hide a model that works in one
    # region and fails in another - this dataset is 46% Andhra Pradesh, 41%
    # Telangana, 13% Tamil Nadu, so a headline average could be carried
    # entirely by the two large regions.
    per_state = {}
    for config, label in CONFIGS:
        p = pooled_predictions[config]
        yt, yp, st = np.array(p["y_true"]), np.array(p["y_pred"]), np.array(p["state"])
        per_state[config] = {
            state: metrics(yt[st == state], yp[st == state]) for state in sorted(set(p["state"]))
        }

    aggregated = {}
    for config, label in CONFIGS:
        maes = [per_seed_results[s][config]["metrics"]["mae"] for s in SEEDS]
        rmses = [per_seed_results[s][config]["metrics"]["rmse"] for s in SEEDS]
        r2s = [per_seed_results[s][config]["metrics"]["r2"] for s in SEEDS if per_seed_results[s][config]["metrics"]["r2"] is not None]
        aggregated[config] = {
            "label": label,
            "mae_mean": statistics.mean(maes), "mae_std": statistics.stdev(maes),
            "rmse_mean": statistics.mean(rmses), "rmse_std": statistics.stdev(rmses),
            "r2_mean": statistics.mean(r2s) if r2s else None,
            "r2_std": statistics.stdev(r2s) if len(r2s) > 1 else None,
            "n_seeds_with_r2": len(r2s),
            "per_seed_mae": maes,
        }
    return per_seed_results, aggregated, {"splits": split_records, "pooled": pooled_predictions, "per_state": per_state}


def make_figures(aggregated: dict, pooled: dict) -> list[str]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    labels = [aggregated[c]["label"] for c, _ in CONFIGS]
    colors = ["#8c8c8c", "#4c72b0", "#55a868", "#c44e52", "#dd8452", "#8172b3"]

    for metric, ylabel, fname in [
        ("mae", "MAE (t/ha) — lower is better", "unseen_district_mae.png"),
        ("rmse", "RMSE (t/ha) — lower is better", "unseen_district_rmse.png"),
        ("r2", "R² — higher is better", "unseen_district_r2.png"),
    ]:
        means = [aggregated[c][f"{metric}_mean"] for c, _ in CONFIGS]
        stds = [aggregated[c][f"{metric}_std"] for c, _ in CONFIGS]
        if any(m is None for m in means):
            continue
        stds = [0.0 if s is None else s for s in stds]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(range(len(labels)), means, yerr=stds, capsize=5, color=colors, edgecolor="black", linewidth=0.6)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(f"Unseen-district generalization — {metric.upper()}\n"
                     f"mean ± std over {len(SEEDS)} repeated grouped splits (seeds {SEEDS[0]}–{SEEDS[-1]})",
                     fontsize=11)
        if metric == "r2":
            ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        out = FIGURES_DIR / fname
        fig.savefig(out, dpi=200)
        plt.close(fig)
        written.append(str(out.relative_to(EXPERIMENTS_DIR.parent)))

    # Actual vs predicted for the primary environmental model, pooled over
    # every seed's test fold (documented in the report - NOT a cherry-picked
    # best split).
    p = pooled["weather_satellite"]
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    state_colors = {"Andhra Pradesh": "#4c72b0", "Telangana": "#55a868", "Tamil Nadu": "#c44e52"}
    for state in sorted(set(p["state"])):
        idx = [i for i, s in enumerate(p["state"]) if s == state]
        ax.scatter([p["y_true"][i] for i in idx], [p["y_pred"][i] for i in idx],
                   s=18, alpha=0.6, label=state, color=state_colors.get(state, "#777777"))
    lo = min(min(p["y_true"]), min(p["y_pred"])) - 0.2
    hi = max(max(p["y_true"]), max(p["y_pred"])) + 0.2
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, label="perfect prediction")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Actual yield (t/ha)")
    ax.set_ylabel("Predicted yield (t/ha)")
    ax.set_title("Weather + Satellite — actual vs predicted\n"
                 f"test-fold predictions pooled over {len(SEEDS)} repeated grouped splits "
                 f"(n={len(p['y_true'])})", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGURES_DIR / "unseen_district_actual_vs_predicted.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    written.append(str(out.relative_to(EXPERIMENTS_DIR.parent)))
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true", help="Run the leakage audit and stop.")
    args = parser.parse_args()

    df, report = load_district_examples()
    print(f"loaded {report.used} fully-aligned examples "
          f"({report.excluded} of {report.total_collected} excluded)")

    print("\nrunning leakage audit...")
    passed, checks, evidence = run_leakage_audit(df, report)
    write_audit(passed, checks, evidence, df, report)
    for c in checks:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['id']}. {c['check']}")
    print(f"wrote -> {AUDIT_PATH}")

    if not passed:
        raise SystemExit("Leakage audit FAILED - refusing to train. See the audit file for details.")
    if args.audit_only:
        print("\naudit-only mode: stopping before training, as requested.")
        return

    print("\naudit clean. running experiments...\n")
    per_seed, aggregated, extras = run_experiments(df)
    figures = make_figures(aggregated, extras["pooled"])

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "path": "data/processed/district_multimodal_examples.csv",
            "total_collected": report.total_collected,
            "used_fully_aligned": report.used,
            "excluded": report.excluded,
            "exclusion_reasons": report.reasons,
            "target_column": TARGET_COL,
            "n_districts": int(df["group"].nunique()),
            "examples_by_state": {k: int(v) for k, v in df["state"].value_counts().items()},
        },
        "feature_configuration": {
            "weather": WEATHER_FEATURES,
            "satellite": SATELLITE_FEATURES,
            "soil": SOIL_FEATURES,
            "metadata_never_used_as_features": METADATA_COLS,
            "forbidden_as_features": sorted(FORBIDDEN_AS_FEATURES),
        },
        "split_design": {
            "type": "repeated stratified grouped split on (state|canonical_district_name)",
            "stratified_by": "state",
            "val_frac_of_districts": 0.2,
            "test_frac_of_districts": 0.2,
            "seeds": SEEDS,
            "assignments": {str(s): extras["splits"][s] for s in SEEDS},
        },
        "model_configuration": {"class": "training.district_model.DistrictMLP", **{k: (list(v) if isinstance(v, tuple) else v) for k, v in TRAIN_SETTINGS.items()}},
        "training_settings": {k: (list(v) if isinstance(v, tuple) else v) for k, v in TRAIN_SETTINGS.items()},
        "results_per_seed": {str(s): per_seed[s] for s in SEEDS},
        "results_aggregated": aggregated,
        "results_per_state_pooled": extras["per_state"],
        "figures": figures,
        "leakage_audit": {"passed": passed, "checks": checks, "path": str(AUDIT_PATH.relative_to(EXPERIMENTS_DIR.parent))},
        "torch_version": torch.__version__,
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("\n=== aggregated over 5 repeated grouped splits ===")
    for config, label in CONFIGS:
        a = aggregated[config]
        r2 = f"{a['r2_mean']:.3f} ± {a['r2_std']:.3f}" if a["r2_mean"] is not None else "n/a"
        print(f"{label:<28} MAE {a['mae_mean']:.3f} ± {a['mae_std']:.3f}   "
              f"RMSE {a['rmse_mean']:.3f} ± {a['rmse_std']:.3f}   R2 {r2}")
    print(f"\nwrote -> {RESULTS_JSON}")
    print(f"figures -> {FIGURES_DIR}")


if __name__ == "__main__":
    main()
