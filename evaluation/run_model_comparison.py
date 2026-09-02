"""
Compares the deep multimodal model against classical ML baselines (Random
Forest, XGBoost) and a naive mean-yield baseline, all fit on the same
synthetic pretraining data and scored on the same real held-out season
examples across 4 states and 2 crops.

**Run it with several seeds.** A single run of this comparison is not
trustworthy: the ranking is unstable across draws of the synthetic
pretraining set. Two consecutive single-seed runs put XGBoost at MAE 0.448
and then 0.739 t/ha - a swing far larger than the gaps between models. With
28 real holdout examples, a one-seed table can support almost any conclusion
you want, which is precisely why this script now averages and reports the
spread.

    python -m training.train_forecast_model --mode realistic
    python -m evaluation.run_model_comparison --seeds 5
"""

import argparse
import statistics

import torch
from torch.utils.data import DataLoader, random_split

from evaluation.baselines.random_forest import train_and_eval as rf_train_and_eval
from evaluation.baselines.xgboost_model import train_and_eval as xgb_train_and_eval
from training.dataset import SeasonDataset, build_dataset_from_processed, build_synthetic_dataset
from training.train_forecast_model import (
    ForecastModel,
    evaluate,
    predict_final_yield,
    train_one_epoch,
)


def _mae(preds: list[float], actuals: list[float]) -> float:
    return sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)


def _train_deep(synthetic_train, seed: int, epochs: int):
    """Trains a fresh model for this seed, selecting the best epoch on a
    validation split of the synthetic set only - never on the real holdout,
    which would leak the evaluation set into model selection."""
    torch.manual_seed(seed)
    dataset = SeasonDataset(synthetic_train)
    val_len = max(1, int(0.2 * len(dataset)))
    train_ds, val_ds = random_split(dataset, [len(dataset) - val_len, val_len])
    train_loader = DataLoader(train_ds, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=8)

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
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5, help="Number of synthetic-set seeds to average over.")
    parser.add_argument("--synthetic-n", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()

    real_holdout = build_dataset_from_processed()
    if not real_holdout:
        raise RuntimeError("No real held-out examples found - run ingestion/align_pipeline.py first.")
    actuals = [ex.final_yield for ex in real_holdout]

    results: dict[str, list[float]] = {
        "Naive baseline (predict train-set mean)": [],
        "Random Forest": [],
        "XGBoost": [],
        "HarvestWise multimodal model (ours)": [],
    }

    for seed in range(args.seeds):
        synthetic_train = build_synthetic_dataset(n_examples=args.synthetic_n, seed=seed)

        naive_pred = sum(ex.final_yield for ex in synthetic_train) / len(synthetic_train)
        results["Naive baseline (predict train-set mean)"].append(_mae([naive_pred] * len(actuals), actuals))
        results["Random Forest"].append(rf_train_and_eval(synthetic_train, real_holdout)["mae"])
        results["XGBoost"].append(xgb_train_and_eval(synthetic_train, real_holdout)["mae"])

        model = _train_deep(synthetic_train, seed, args.epochs)
        preds, _ = predict_final_yield(model, real_holdout)
        results["HarvestWise multimodal model (ours)"].append(_mae(preds, actuals))
        print(f"  seed {seed} done")

    print(f"\n=== Model comparison: MAE (t/ha), mean over {args.seeds} seeds ===")
    print(
        f"{len(real_holdout)} real season examples across "
        f"{len({ex.field_id for ex in real_holdout})} fields spanning Tamil Nadu, Punjab,\n"
        "West Bengal and Andhra Pradesh (rice + wheat). See\n"
        "data/raw/yield_labels/README.md for each field's real yield source and\n"
        "its sourcing caveats.\n"
    )
    ordered = sorted(results.items(), key=lambda kv: statistics.mean(kv[1]))
    for name, maes in ordered:
        mean = statistics.mean(maes)
        sd = statistics.stdev(maes) if len(maes) > 1 else 0.0
        print(f"  {name:<40} MAE={mean:.3f} +/- {sd:.3f}  (range {min(maes):.3f}-{max(maes):.3f})")

    best_name, best_maes = ordered[0]
    runner_name, runner_maes = ordered[1]
    gap = statistics.mean(runner_maes) - statistics.mean(best_maes)
    pooled_sd = statistics.mean(
        [statistics.stdev(m) if len(m) > 1 else 0.0 for m in (best_maes, runner_maes)]
    )
    print(
        f"\nTop-two gap = {gap:.3f} t/ha against a typical seed-to-seed spread of "
        f"{pooled_sd:.3f} t/ha."
    )
    if gap < pooled_sd:
        print(
            "The gap is SMALLER than the run-to-run noise: at this sample size the\n"
            "ranking between the top two models is not established. Report it that way."
        )


if __name__ == "__main__":
    main()
