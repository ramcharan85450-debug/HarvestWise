"""
SHAP feature attribution for the Random Forest baseline - not the multimodal
deep model. Random Forest is the more suitable target for two reasons, both
measured, not assumed: (1) it beats XGBoost on MAE in every table in this
project (RESULTS.md S2, S4.3, S5d) and has the lowest seed-to-seed variance
of any model tried, so its predictions are the most stable thing available to
explain; (2) SHAP's TreeExplainer is exact and cheap for tree ensembles,
unlike the attention-based explanations already attempted on the transformer
backbone (see attention_visualization.py), which approximate rather than
exactly attribute.

This project's own rule - a result reported on one seed is not established -
applies here too. Feature importance is computed across the same 5 seeds
used everywhere else, and reported as mean +/- sd per feature, not a single
ranked list from one lucky fit.

Run:
    python -m evaluation.explainability.shap_analysis --seeds 5
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap
from sklearn.ensemble import RandomForestRegressor

from evaluation.baselines.features import FEATURE_NAMES, build_feature_matrix
from training.dataset import build_dataset_from_processed

OUT_DIR = Path(__file__).resolve().parent
RESULTS_PATH = OUT_DIR / "shap_results.json"
PLOT_PATH = OUT_DIR / "shap_feature_importance.png"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    args = parser.parse_args()

    examples = build_dataset_from_processed()
    X, y = build_feature_matrix(examples)
    print(f"{len(examples)} real season examples, {X.shape[1]} features, {args.seeds} seeds")

    # abs(SHAP value) per feature per seed - the magnitude of that feature's
    # contribution to individual predictions, averaged over all examples.
    per_seed = np.zeros((args.seeds, X.shape[1]))
    for seed in range(args.seeds):
        model = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=seed)
        model.fit(X, y)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        per_seed[seed] = np.abs(shap_values).mean(axis=0)

    mean_importance = per_seed.mean(axis=0)
    sd_importance = per_seed.std(axis=0)
    order = np.argsort(-mean_importance)

    print(f"\n{'feature':<20}{'mean |SHAP|':>14}{'sd':>10}")
    print("-" * 44)
    results = []
    for i in order:
        name = FEATURE_NAMES[i]
        print(f"{name:<20}{mean_importance[i]:>14.4f}{sd_importance[i]:>10.4f}")
        results.append({"feature": name, "mean_abs_shap": round(float(mean_importance[i]), 4), "sd": round(float(sd_importance[i]), 4)})

    # Fit one more time at seed 0 (matching random_forest.py's baseline
    # convention) purely to render the summary plot - the ranking reported
    # above is the multi-seed one, this plot just visualizes one real fit.
    model0 = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=0)
    model0.fit(X, y)
    shap_values0 = shap.TreeExplainer(model0).shap_values(X)

    fig, ax = plt.subplots(figsize=(8, 6))
    order0 = np.argsort(mean_importance)
    ax.barh([FEATURE_NAMES[i] for i in order0], mean_importance[order0], xerr=sd_importance[order0], color="#3d7a4f")
    ax.set_xlabel("mean |SHAP value| (t/ha), +/- sd over 5 seeds")
    ax.set_title(f"Random Forest feature importance - {len(examples)} real season examples")
    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=150)
    print(f"\nwrote plot -> {PLOT_PATH}")

    RESULTS_PATH.write_text(json.dumps({"n_examples": len(examples), "seeds": args.seeds, "ranked_features": results}, indent=2))
    print(f"wrote -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
