"""
Label-granularity sweep: at what spatial resolution of yield label does
multimodal deep learning start to beat tree ensembles?

This is the project's central experiment. Everything is held fixed - the same
fields, the same real Sentinel-2 / ERA5 / SoilGrids inputs, the same models,
the same seeds - and ONLY the spatial granularity of the yield label changes:

    national  ->  state  ->  district (once available)

Motivation. On this project's data the multimodal model does not beat a naive
mean-predictor (see RESULTS.md S2), and the reason was isolated in RESULTS.md
S5: giving the synthetic pretraining generator a correct weather-to-yield
relationship made real accuracy monotonically WORSE, which points at label
granularity rather than sample size or architecture. That the deep model
underperforms on small agricultural datasets is already published; what is not
established is the granularity THRESHOLD at which multimodal deep learning
becomes worth its cost. This sweep measures it.

The comparison is restricted to fields present at EVERY tier being compared,
so a difference between tiers is a difference in label resolution and not a
difference in which fields were included.

Run:
    python -m evaluation.label_granularity.run_granularity_sweep --seeds 5
"""

import argparse
import json
import statistics
from pathlib import Path

import torch
from torch.utils.data import DataLoader, random_split

from evaluation.baselines.features import build_feature_matrix
from sklearn.ensemble import RandomForestRegressor
from training.dataset import SeasonDataset, build_dataset_from_processed, build_synthetic_dataset
from training.train_forecast_model import ForecastModel, evaluate, predict_final_yield, train_one_epoch
from xgboost import XGBRegressor

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
TIERS = ["national", "state", "district"]


def _mae(preds, actuals) -> float:
    return sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)


def _train_deep(fit_examples, seed: int, epochs: int):
    torch.manual_seed(seed)
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
    return model


def _score_tier(examples, seeds: int, synthetic_n: int, epochs: int) -> dict:
    actuals = [ex.final_yield for ex in examples]
    X_test, _ = build_feature_matrix(examples)
    per_seed: dict[str, list[float]] = {"Naive": [], "Random Forest": [], "XGBoost": [], "HarvestWise": []}

    for seed in range(seeds):
        syn = build_synthetic_dataset(n_examples=synthetic_n, seed=seed)
        X_fit, y_fit = build_feature_matrix(syn)

        naive = sum(y_fit) / len(y_fit)
        per_seed["Naive"].append(_mae([naive] * len(actuals), actuals))
        per_seed["Random Forest"].append(
            _mae(RandomForestRegressor(n_estimators=300, max_depth=8, random_state=seed).fit(X_fit, y_fit).predict(X_test).tolist(), actuals)
        )
        per_seed["XGBoost"].append(
            _mae(XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=seed).fit(X_fit, y_fit).predict(X_test).tolist(), actuals)
        )
        preds, _ = predict_final_yield(_train_deep(syn, seed, epochs), examples)
        per_seed["HarvestWise"].append(_mae(preds, actuals))

    return {
        name: {
            "mean": statistics.mean(v),
            "sd": statistics.stdev(v) if len(v) > 1 else 0.0,
            "min": min(v),
            "max": max(v),
        }
        for name, v in per_seed.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--synthetic-n", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()

    by_tier = {}
    for tier in TIERS:
        ex = build_dataset_from_processed(granularity=tier)
        if ex:
            by_tier[tier] = ex

    if len(by_tier) < 2:
        print(
            f"Only {len(by_tier)} label tier(s) populated ({list(by_tier)}). "
            "A sweep needs at least two.\nPopulate "
            "data/raw/yield_labels/<tier>/<field_id>_yield_labels.csv - the "
            "district tier is the one still missing, and is the highest-value "
            "data item for this experiment."
        )
        return

    # Restrict to fields present at EVERY tier, so a tier-to-tier difference is
    # a difference in label resolution, not in dataset membership.
    common = set.intersection(*({e.field_id for e in ex} for ex in by_tier.values()))
    by_tier = {t: [e for e in ex if e.field_id in common] for t, ex in by_tier.items()}

    print(f"tiers compared: {list(by_tier)}")
    print(f"fields common to all tiers: {sorted(common)}")
    for t, ex in by_tier.items():
        ys = [e.final_yield for e in ex]
        print(f"  {t:<9} n={len(ex):<3} yield {min(ys):.3f}-{max(ys):.3f} t/ha (mean {statistics.mean(ys):.3f})")

    results = {}
    for tier, ex in by_tier.items():
        print(f"\nscoring tier '{tier}' ({len(ex)} examples, {args.seeds} seeds)...")
        results[tier] = _score_tier(ex, args.seeds, args.synthetic_n, args.epochs)

    print(f"\n=== Label-granularity sweep: MAE (t/ha), mean +/- sd over {args.seeds} seeds ===\n")
    models = ["Naive", "Random Forest", "XGBoost", "HarvestWise"]
    header = f"{'tier':<10}" + "".join(f"{m:>24}" for m in models)
    print(header)
    print("-" * len(header))
    for tier in by_tier:
        row = f"{tier:<10}"
        for m in models:
            s = results[tier][m]
            row += f"{s['mean']:>16.3f} +/-{s['sd']:.3f}"
        print(row)

    print("\nDeep-model gap to the best tree ensemble (positive = deep model is worse):")
    for tier in by_tier:
        best_tree = min(results[tier]["Random Forest"]["mean"], results[tier]["XGBoost"]["mean"])
        gap = results[tier]["HarvestWise"]["mean"] - best_tree
        print(f"  {tier:<10} {gap:+.3f} t/ha")
    print(
        "\nThe headline question is whether that gap SHRINKS as label granularity\n"
        "improves. Two tiers give a direction, not a threshold - the district\n"
        "tier is what would turn this into a curve worth publishing."
    )

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "seeds": args.seeds,
                "fields_common_to_all_tiers": sorted(common),
                "n_examples_per_tier": {t: len(ex) for t, ex in by_tier.items()},
                "mae_t_ha": {
                    t: {m: {k: round(float(v), 4) for k, v in s.items()} for m, s in r.items()}
                    for t, r in results.items()
                },
            },
            indent=2,
        )
    )
    print(f"\nwrote -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
