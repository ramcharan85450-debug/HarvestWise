"""
End-to-end training for the yield forecast model: encoders -> phenology
fusion -> spatio-temporal backbone -> quantile yield head. Saves the two
checkpoint files backend/app/models_registry/model_loader.py expects
(fusion_backbone.pt, yield_head.pt), so the API switches from placeholder to
real inference the moment this has run.

Run smoke-test (synthetic data, validates the training loop works):
    python -m training.train_forecast_model --synthetic

Run for real (after ingestion/align_pipeline.py + real yield labels exist):
    python -m training.train_forecast_model
"""

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader, random_split

from models.backbone.spatiotemporal_backbone import SpatioTemporalBackbone
from models.encoders.soil_encoder import SoilEncoder
from models.encoders.vision_encoder import VegetationIndexEncoder
from models.encoders.weather_encoder import WeatherEncoder
from models.fusion.phenology_attention import PhenologyAwareFusion
from models.heads.yield_forecast_head import YieldForecastHead, pinball_loss
from training.dataset import SeasonDataset, build_dataset_from_processed, build_synthetic_dataset

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "backend" / "checkpoints"
EMBED_DIM = 64


class ForecastModel(torch.nn.Module):
    def __init__(self, embed_dim: int = EMBED_DIM):
        super().__init__()
        self.vision_enc = VegetationIndexEncoder(in_features=4, embed_dim=embed_dim)
        self.weather_enc = WeatherEncoder(in_features=4, embed_dim=embed_dim)
        self.soil_enc = SoilEncoder(in_features=5, embed_dim=embed_dim)
        self.fusion = PhenologyAwareFusion(embed_dim=embed_dim)
        self.backbone = SpatioTemporalBackbone(embed_dim=embed_dim)
        self.head = YieldForecastHead(embed_dim=embed_dim)

    def forward(self, batch: dict) -> torch.Tensor:
        v = self.vision_enc(batch["vision_x"])
        w = self.weather_enc(batch["weather_x"])
        s = self.soil_enc(batch["soil_x"])
        fused, attn_weights = self.fusion(v, w, s, batch["growth_stage"])
        hidden = self.backbone(fused)
        quantiles = self.head(hidden)
        return quantiles, attn_weights


def train_one_epoch(model: ForecastModel, loader: DataLoader, optimizer: torch.optim.Optimizer) -> float:
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        quantiles, _ = model(batch)
        target = batch["final_yield"].unsqueeze(1).expand(-1, quantiles.shape[1])
        loss = pinball_loss(quantiles, target)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * quantiles.shape[0]
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model: ForecastModel, loader: DataLoader) -> float:
    model.eval()
    total_loss = 0.0
    for batch in loader:
        quantiles, _ = model(batch)
        target = batch["final_yield"].unsqueeze(1).expand(-1, quantiles.shape[1])
        loss = pinball_loss(quantiles, target)
        total_loss += loss.item() * quantiles.shape[0]
    return total_loss / len(loader.dataset)


@torch.no_grad()
def predict_final_yield(model: ForecastModel, examples: list) -> tuple[list[float], list[float]]:
    """Returns (predicted, actual) final-yield pairs using the last week's
    median quantile as the point forecast."""
    if not examples:
        return [], []
    loader = DataLoader(SeasonDataset(examples), batch_size=len(examples))
    model.eval()
    batch = next(iter(loader))
    quantiles, _ = model(batch)
    preds = quantiles[:, -1, 1].tolist()  # last week, median quantile
    actuals = batch["final_yield"].tolist()
    return preds, actuals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["synthetic", "real", "realistic"],
        default="realistic",
        help=(
            "synthetic: smoke-test on synthetic data only. "
            "real: train directly on real processed data (currently only 12 real "
            "season examples across 3 fields with one repeated yield label - too "
            "few to train a deep model from scratch). "
            "realistic (default): pretrain on synthetic data, then hold out all "
            "real data as a plausibility check (never trained on) and report "
            "predicted-vs-actual against a naive baseline."
        ),
    )
    parser.add_argument("--synthetic-n", type=int, default=300, help="Number of synthetic season examples for pretraining.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    real_examples = build_dataset_from_processed()

    if args.mode == "synthetic":
        train_examples = build_synthetic_dataset()
        holdout_examples = []
    elif args.mode == "real":
        train_examples = real_examples
        holdout_examples = []
    else:  # realistic
        train_examples = build_synthetic_dataset(n_examples=args.synthetic_n)
        holdout_examples = real_examples

    if len(train_examples) < 4:
        raise RuntimeError(f"Only {len(train_examples)} training examples found for mode={args.mode}.")

    if holdout_examples:
        train_mean_yield = sum(ex.final_yield for ex in train_examples) / len(train_examples)
        real_actuals = [ex.final_yield for ex in holdout_examples]
        baseline_mae = sum(abs(train_mean_yield - y) for y in real_actuals) / len(real_actuals)
        print(
            f"real held-out set: {len(holdout_examples)} season examples across "
            f"{len({ex.field_id for ex in holdout_examples})} fields, labeled with "
            f"real year-varying national Kharif rice yield (see "
            f"data/raw/yield_labels/README.md - national, not Coimbatore-specific, "
            f"and only 3-4 real years - small-sample and geographic-granularity "
            f"caveats still apply).\n"
            f"naive baseline (predict {train_mean_yield:.3f} t/ha for everything): MAE={baseline_mae:.3f} t/ha"
        )

    dataset = SeasonDataset(train_examples)
    val_len = max(1, int(0.2 * len(dataset)))
    train_ds, val_ds = random_split(dataset, [len(dataset) - val_len, val_len])
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size)

    model = ForecastModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    # Early stopping / best-checkpoint selection on the VALIDATION split only.
    # This deliberately does NOT select on the real held-out MAE printed
    # below: picking the epoch that happens to score best on the real holdout
    # would leak the evaluation set into model selection and inflate the
    # reported result. The real-holdout number stays a read-only observation.
    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0

    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer)
        val_loss = evaluate(model, val_loader)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch

        msg = f"epoch {epoch:>3}/{args.epochs}  train pinball loss {train_loss:.4f}  val pinball loss {val_loss:.4f}"
        if holdout_examples and epoch % 5 == 0:
            preds, actuals = predict_final_yield(model, holdout_examples)
            mae = sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)
            msg += f"  real-holdout MAE {mae:.3f} t/ha"
        print(msg)

    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"\nrestored best checkpoint from epoch {best_epoch} (val pinball loss {best_val_loss:.4f})")

    if holdout_examples:
        preds, actuals = predict_final_yield(model, holdout_examples)
        final_mae = sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)
        print(
            f"\nfinal real-holdout check: model MAE={final_mae:.3f} t/ha vs "
            f"naive-baseline MAE={baseline_mae:.3f} t/ha "
            f"({'beats' if final_mae < baseline_mae else 'does NOT beat'} the naive baseline)\n"
            f"sample predictions (t/ha): {[round(p, 2) for p in preds[:5]]} "
            f"vs actual {[round(a, 2) for a in actuals[:5]]}"
        )

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "vision_enc": model.vision_enc.state_dict(),
            "weather_enc": model.weather_enc.state_dict(),
            "soil_enc": model.soil_enc.state_dict(),
            "fusion": model.fusion.state_dict(),
            "backbone": model.backbone.state_dict(),
        },
        CHECKPOINT_DIR / "fusion_backbone.pt",
    )
    torch.save(model.head.state_dict(), CHECKPOINT_DIR / "yield_head.pt")
    print(f"saved checkpoints -> {CHECKPOINT_DIR}")


if __name__ == "__main__":
    main()
