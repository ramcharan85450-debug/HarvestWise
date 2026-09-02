"""
Runs the HarvestWise Climate-Shock Benchmark: train each model on real
NORMAL field-seasons only, then measure how it holds up on real climate-SHOCK
field-seasons (drought / wet_extreme / heatwave) it never saw.

Labels come from the real ERA5 record via
evaluation/climate_shock_benchmark/derive_labels.py - see build_splits.py.

Run:
    python -m evaluation.climate_shock_benchmark.derive_labels
    python -m evaluation.climate_shock_benchmark.run_climate_shock
"""

import argparse
import json
import statistics
from datetime import date
from pathlib import Path

import torch
from torch.utils.data import DataLoader, random_split

from evaluation.baselines.features import build_feature_matrix
from evaluation.climate_shock_benchmark.build_splits import label_for, split_by_climate
from sklearn.ensemble import RandomForestRegressor
from training.dataset import SeasonDataset, build_dataset_from_processed, build_synthetic_dataset
from training.train_forecast_model import ForecastModel, evaluate, predict_final_yield, train_one_epoch
from xgboost import XGBRegressor

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _mae(preds, actuals) -> float:
    return sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)


def _deep_model_predictions(
    train_examples, test_examples, epochs: int = 80, seed: int = 0, synthetic_n: int = 300
) -> list[float]:
    """Trains the multimodal model on synthetic data plus the real NORMAL
    seasons, then predicts the held-out shock seasons. Synthetic data is
    included because the real normal set alone (~20 seasons) is far too small
    to fit this model from scratch - the same pretrain-then-evaluate setup
    training/train_forecast_model.py uses.

    Uses the same early-stopping protocol as that script (keep the epoch with
    the best VALIDATION loss, where validation is a split of the fit set, never
    the shock test set). Without it this model overfits badly - in the main
    training run, early stopping moved real-holdout MAE from 0.718 to 0.542 -
    so training it here for a fixed epoch count would have handicapped it
    relative to how it is actually trained and reported elsewhere."""
    torch.manual_seed(seed)
    fit_examples = build_synthetic_dataset(n_examples=synthetic_n, seed=seed) + train_examples
    dataset = SeasonDataset(fit_examples)
    val_len = max(1, int(0.2 * len(dataset)))
    train_ds, val_ds = random_split(dataset, [len(dataset) - val_len, val_len])
    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=16)

    model = ForecastModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    best_val, best_state = float("inf"), None
    for _ in range(epochs):
        train_one_epoch(model, train_loader, optimizer)
        val_loss = evaluate(model, val_loader)
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    preds, _ = predict_final_yield(model, test_examples)
    return preds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help=(
            "Number of synthetic-pretraining seeds to average over. A single "
            "seed cannot support a ranking here: on the 28-example real "
            "holdout the deep model's MAE ranges 0.449-1.134 across seeds "
            "(see evaluation/run_model_comparison.py), and this test set is "
            "smaller still."
        ),
    )
    parser.add_argument("--synthetic-n", type=int, default=300)
    args = parser.parse_args()

    examples = build_dataset_from_processed()
    train_examples, test_examples = split_by_climate(examples)

    print(f"real NORMAL seasons (train): {len(train_examples)}")
    print(f"real SHOCK  seasons (test):  {len(test_examples)}")
    for ex in test_examples:
        year = date.fromisoformat(ex.season_start_date).year
        print(f"   {ex.field_id} {year}  [{label_for(ex.field_id, year)}]  actual={ex.final_yield:.3f} t/ha")

    if not test_examples:
        print("\nNo real shock seasons found - nothing to evaluate.")
        return

    actuals = [ex.final_yield for ex in test_examples]
    X_test, _ = build_feature_matrix(test_examples)

    per_seed: dict[str, list[float]] = {
        "Naive baseline": [],
        "Random Forest": [],
        "XGBoost": [],
        "HarvestWise multimodal": [],
    }

    for seed in range(args.seeds):
        # Every model is fit on the SAME data (synthetic + real normal
        # seasons) and scored on the SAME held-out real shock seasons.
        syn = build_synthetic_dataset(n_examples=args.synthetic_n, seed=seed)
        X_fit, y_fit = build_feature_matrix(syn + train_examples)

        naive = sum(y_fit) / len(y_fit)
        per_seed["Naive baseline"].append(_mae([naive] * len(actuals), actuals))

        rf = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=seed).fit(X_fit, y_fit)
        per_seed["Random Forest"].append(_mae(rf.predict(X_test).tolist(), actuals))

        xgb = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=seed).fit(X_fit, y_fit)
        per_seed["XGBoost"].append(_mae(xgb.predict(X_test).tolist(), actuals))

        per_seed["HarvestWise multimodal"].append(
            _mae(_deep_model_predictions(train_examples, test_examples, seed=seed, synthetic_n=args.synthetic_n), actuals)
        )
        print(f"  seed {seed} done")

    summary = {
        name: {
            "mean": statistics.mean(vals),
            "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
        }
        for name, vals in per_seed.items()
    }

    print(f"\n=== Climate-Shock Benchmark: MAE (t/ha), mean over {args.seeds} seeds ===")
    print("Fit on real NORMAL seasons only (+ synthetic pretraining);")
    print("scored on real drought / wet_extreme seasons never seen in training.\n")
    ordered = sorted(summary.items(), key=lambda kv: kv[1]["mean"])
    for name, s in ordered:
        print(f"  {name:<28} MAE={s['mean']:.3f} +/- {s['sd']:.3f}  (range {s['min']:.3f}-{s['max']:.3f})")

    gap = ordered[1][1]["mean"] - ordered[0][1]["mean"]
    pooled_sd = statistics.mean([ordered[0][1]["sd"], ordered[1][1]["sd"]])
    print(f"\nTop-two gap = {gap:.3f} t/ha against a typical seed-to-seed spread of {pooled_sd:.3f} t/ha.")
    if gap < pooled_sd:
        print("The gap is SMALLER than the run-to-run noise: this ranking is NOT established.")

    print(
        f"\nCAVEAT, report this alongside the numbers: the shock test set is only "
        f"{len(test_examples)} real field-seasons, because only that many crossed "
        f"the anomaly thresholds in the ingested ERA5 record. These results are "
        f"indicative, not statistically powered. Widening ingestion/config.py's "
        f"date range and re-running the ERA5 pull is what would make this "
        f"benchmark publication-strength."
    )

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "n_seeds": args.seeds,
                "n_train_normal_seasons": len(train_examples),
                "n_test_shock_seasons": len(test_examples),
                "test_seasons": [
                    {
                        "field_id": ex.field_id,
                        "year": date.fromisoformat(ex.season_start_date).year,
                        "label": label_for(ex.field_id, date.fromisoformat(ex.season_start_date).year),
                        "actual_yield_t_ha": float(ex.final_yield),
                    }
                    for ex in test_examples
                ],
                # Mean over seeds. Kept under the same key the serving layer and
                # leaderboard already read, with the spread alongside it so a
                # consumer cannot quote the mean without seeing the variance.
                "mae_t_ha": {k: round(float(v["mean"]), 4) for k, v in summary.items()},
                "mae_t_ha_spread": {
                    k: {"sd": round(float(v["sd"]), 4), "min": round(float(v["min"]), 4), "max": round(float(v["max"]), 4)}
                    for k, v in summary.items()
                },
            },
            indent=2,
        )
    )
    print(f"wrote -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
