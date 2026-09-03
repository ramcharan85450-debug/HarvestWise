"""
Ablation study: imagery-only vs. weather-only vs. fused - shows which
modality is actually contributing, required evidence for the fusion claim
(see project checklist: 'confirm fusion actually helps before proceeding').

Run:
    python -m evaluation.ablation.run_ablation --synthetic
"""

import argparse

import torch
from sklearn.metrics import r2_score
from torch.utils.data import DataLoader, random_split

from models.heads.yield_forecast_head import pinball_loss
from training.dataset import SeasonDataset, build_dataset_from_processed, build_synthetic_dataset
from training.train_forecast_model import ForecastModel, train_one_epoch


def zero_modality(batch: dict, modality: str) -> dict:
    batch = dict(batch)
    if modality == "vision":
        batch["vision_x"] = torch.zeros_like(batch["vision_x"])
    elif modality == "weather":
        batch["weather_x"] = torch.zeros_like(batch["weather_x"])
    elif modality == "soil":
        # Added for evaluation/experiments/run_experiment1.py, which needs a
        # weather+satellite-only configuration (soil excluded) alongside the
        # vision/weather-only ones this file already supported. Same
        # zero-out convention, same architecture and parameter count as
        # every other variant - only the input is masked, nothing about the
        # model changes.
        batch["soil_x"] = torch.zeros_like(batch["soil_x"])
    return batch


class AblatedLoader:
    """Wraps a DataLoader, zeroing one or more modalities' input on every batch."""

    def __init__(self, loader: DataLoader, zero_out: "str | list[str] | None"):
        self.loader = loader
        self.zero_out = [zero_out] if isinstance(zero_out, str) else (zero_out or [])

    def __iter__(self):
        for batch in self.loader:
            for modality in self.zero_out:
                batch = zero_modality(batch, modality)
            yield batch

    def __len__(self):
        return len(self.loader)

    @property
    def dataset(self):
        return self.loader.dataset


@torch.no_grad()
def evaluate_r2(model: ForecastModel, loader) -> float:
    model.eval()
    preds, targets = [], []
    for batch in loader:
        quantiles, _ = model(batch)
        preds.extend(quantiles[:, -1, 1].tolist())  # last-week median prediction
        targets.extend(batch["final_yield"].tolist())
    return r2_score(targets, preds)


def run_variant(name: str, zero_out: str | None, train_ds, val_ds, epochs: int, seeds: int) -> dict:
    r2_scores = []
    for seed in range(seeds):
        torch.manual_seed(seed)
        train_loader = AblatedLoader(DataLoader(train_ds, batch_size=8, shuffle=True), zero_out)
        val_loader = AblatedLoader(DataLoader(val_ds, batch_size=8), zero_out)

        model = ForecastModel()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        for _ in range(epochs):
            train_one_epoch(model, train_loader, optimizer)

        r2_scores.append(evaluate_r2(model, val_loader))

    mean_r2 = sum(r2_scores) / len(r2_scores)
    spread = f" (range {min(r2_scores):.3f} to {max(r2_scores):.3f} over {seeds} seeds)" if seeds > 1 else ""
    print(f"{name:>20}:  val R2 = {mean_r2:.3f}{spread}")
    return {"variant": name, "r2": mean_r2, "r2_scores": r2_scores}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--synthetic-n", type=int, default=60)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seeds", type=int, default=1, help="Repeat each variant this many times (different init) and average, to reduce single-run noise.")
    args = parser.parse_args()

    examples = build_synthetic_dataset(n_examples=args.synthetic_n) if args.synthetic else build_dataset_from_processed()
    dataset = SeasonDataset(examples)
    val_len = max(1, int(0.25 * len(dataset)))
    train_ds, val_ds = random_split(dataset, [len(dataset) - val_len, val_len])

    results = [
        run_variant("imagery-only", zero_out="weather", train_ds=train_ds, val_ds=val_ds, epochs=args.epochs, seeds=args.seeds),
        run_variant("weather-only", zero_out="vision", train_ds=train_ds, val_ds=val_ds, epochs=args.epochs, seeds=args.seeds),
        run_variant("fused", zero_out=None, train_ds=train_ds, val_ds=val_ds, epochs=args.epochs, seeds=args.seeds),
    ]

    print("\nSummary:")
    for r in results:
        print(f"  {r['variant']:>15}: R2 = {r['r2']:.3f}")


if __name__ == "__main__":
    main()
