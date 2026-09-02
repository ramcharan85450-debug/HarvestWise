"""
Trains the RL harvest-timing policy (PPO, via stable-baselines3) on
historical season trajectories, and saves it as backend/checkpoints/
rl_harvest_policy.zip - the exact filename backend/app/models_registry/
model_loader.py expects, so the API picks it up automatically.

Run (after training/train_forecast_model.py has produced a yield forecast
model, and evaluation/climate_shock_benchmark/build_splits.py has defined
train/test years):
    python -m models.heads.rl_harvest_policy.train_rl
"""

from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env

from ingestion.config import FIELDS
from models.heads.rl_harvest_policy.agronomic_window import agronomic_bounds, window_is_observed
from models.heads.rl_harvest_policy.env import HarvestTimingEnv, SeasonTrajectory
from training.dataset import build_dataset_from_processed, normalize_model_inputs
from training.train_forecast_model import CHECKPOINT_DIR as FORECAST_CHECKPOINT_DIR
from training.train_forecast_model import ForecastModel

CHECKPOINT_DIR = Path(__file__).resolve().parents[3] / "backend" / "checkpoints"


def load_trajectories_from_processed(processed_dir: Path) -> list[SeasonTrajectory]:
    """Replays each real season (data/processed/*_aligned.csv, joined with
    real yield labels via training/dataset.py) through the trained yield
    forecast model to get a per-week (low, median, high) quantile
    trajectory - the same real weekly forecast a farmer using the dashboard
    would see - which the RL policy and the static optimizer are both
    benchmarked against, using the real weekly rainfall from the same
    example rather than a separate weather forecast."""
    ckpt_path = FORECAST_CHECKPOINT_DIR / "fusion_backbone.pt"
    if not ckpt_path.exists():
        raise NotImplementedError(
            f"No trained forecast checkpoint at {ckpt_path} - run "
            "`python -m training.train_forecast_model` first."
        )

    examples = build_dataset_from_processed()
    if not examples:
        raise NotImplementedError("No real season examples found - run ingestion/align_pipeline.py first.")

    model = ForecastModel()
    ckpt = torch.load(ckpt_path, map_location="cpu")
    model.vision_enc.load_state_dict(ckpt["vision_enc"])
    model.weather_enc.load_state_dict(ckpt["weather_enc"])
    model.soil_enc.load_state_dict(ckpt["soil_enc"])
    model.fusion.load_state_dict(ckpt["fusion"])
    model.backbone.load_state_dict(ckpt["backbone"])
    model.head.load_state_dict(torch.load(FORECAST_CHECKPOINT_DIR / "yield_head.pt", map_location="cpu"))
    model.eval()

    crop_by_field = {f["field_id"]: f["crop"] for f in FIELDS}
    trajectories, skipped = [], 0
    with torch.no_grad():
        for ex in examples:
            # Same standardisation the model was trained under - see
            # training/dataset.py's normalize_model_inputs. The RAW
            # ex.weather_x is still used below for rainfall in real mm,
            # which HarvestTimingEnv compares against its 25 mm threshold.
            vision_x, weather_x, soil_x = normalize_model_inputs(ex.vision_x, ex.weather_x, ex.soil_x)
            batch = {
                "vision_x": torch.from_numpy(vision_x).unsqueeze(0),
                "weather_x": torch.from_numpy(weather_x).unsqueeze(0),
                "soil_x": torch.from_numpy(soil_x).unsqueeze(0),
                "growth_stage": torch.from_numpy(ex.growth_stage).unsqueeze(0),
            }
            quantiles, _ = model(batch)  # (1, T, 3) = (low, median, high) per week
            q = quantiles[0].numpy()
            season_len = q.shape[0]

            # Earliest valid harvest comes from the season's own observed
            # phenology (peak NDVI -> IRRI days-after-heading), not from
            # season_len // 2. The old bound had no agronomic meaning and was
            # BINDING: the trained policy returned week 10-12 on almost every
            # season, and week 10 was exactly season_len // 2, so it was
            # emitting its lower bound rather than choosing a week. See
            # models/heads/rl_harvest_policy/agronomic_window.py.
            crop = crop_by_field.get(ex.field_id, "rice")
            if not window_is_observed(ex.vision_x, crop, season_len):
                skipped += 1
                continue
            min_week, _ = agronomic_bounds(ex.vision_x, crop, season_len)

            trajectories.append(
                SeasonTrajectory(
                    weekly_median_yield=q[:, 1].tolist(),
                    weekly_low_yield=q[:, 0].tolist(),
                    weekly_high_yield=q[:, 2].tolist(),
                    weekly_rainfall_mm=ex.weather_x[:, 1].tolist(),  # WEATHER_COLS[1] = precip_mm
                    min_harvest_week=min_week,
                )
            )
    if skipped:
        print(f"  skipped {skipped} season(s) whose agronomic harvest window falls past the observed data")
    return trajectories


def build_synthetic_trajectories(n_trajectories: int = 40, season_len: int = 20, seed: int = 0) -> list[SeasonTrajectory]:
    """Smoke-test trajectories only - lets the RL loop and reward shaping be
    validated end-to-end before real forecast data is wired in."""
    rng = np.random.default_rng(seed)
    trajectories = []
    for _ in range(n_trajectories):
        peak = rng.uniform(3.5, 5.5)
        progress = np.linspace(0.3, 1.0, season_len)
        median = peak * progress + rng.normal(0, 0.05, season_len)
        rainfall = np.clip(rng.normal(15, 12, season_len), 0, None)
        trajectories.append(
            SeasonTrajectory(
                weekly_median_yield=median.tolist(),
                weekly_low_yield=(median * 0.85).tolist(),
                weekly_high_yield=(median * 1.15).tolist(),
                weekly_rainfall_mm=rainfall.tolist(),
                min_harvest_week=season_len // 2,
            )
        )
    return trajectories


def train(
    trajectories: list[SeasonTrajectory],
    total_timesteps: int = 200_000,
    seed: int = 0,
    ent_coef: float = 0.02,
    gamma: float = 1.0,
) -> PPO:
    """ent_coef is not incidental tuning - with stable-baselines3's default
    (ent_coef=0) this policy reliably collapses to "harvest immediately at
    min_harvest_week" before it ever explores waiting, and then never
    recovers. The reason is the reward shape: harvesting pays out the full
    yield (~3.5) while the entire decision-relevant difference between
    harvesting now and waiting for the best week is ~0.05-0.07 (~2%), so the
    advantage signal that distinguishes actions is tiny next to the payout
    that doesn't. An entropy bonus keeps the policy exploring long enough to
    discover that waiting 2-4 weeks pays; it is the standard remedy for
    exactly this premature-collapse failure mode.

    gamma=1.0 (rather than stable-baselines3's default 0.99) because this
    task is episodic with a short bounded horizon (<=10 decisions) and its
    objective is genuinely UNDISCOUNTED total reward - that is what
    HarvestTimingEnv's reward design intends (DELAY_COST_PER_WEEK is meant
    to be the only time penalty) and what both the static optimizer and
    evaluation/statistical_tests/run_rl_vs_static.py measure. At gamma=0.99
    with a ~3.5 payout, discounting silently adds a ~0.035/week penalty on
    waiting - 3.5x the intended delay cost, and larger than the ~0.02/week
    yield gain that makes waiting worthwhile - so the agent optimized a
    different objective than the one being scored and correctly learned to
    always harvest immediately. Worked example (trajectory 0): harvest-now
    scores 3.4827; waiting 3 weeks scores 3.4508 discounted (waiting loses)
    but 3.5570 undiscounted (waiting wins)."""
    env = make_vec_env(lambda: HarvestTimingEnv(trajectories), n_envs=4, seed=seed)
    model = PPO("MlpPolicy", env, verbose=1, seed=seed, ent_coef=ent_coef, gamma=gamma)
    model.learn(total_timesteps=total_timesteps)
    return model


def main():
    try:
        trajectories = load_trajectories_from_processed(Path("data/processed"))
    except NotImplementedError as e:
        print(f"Real trajectories not wired up yet ({e}); training on synthetic smoke-test trajectories instead.")
        trajectories = build_synthetic_trajectories()

    model = train(trajectories)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHECKPOINT_DIR / "rl_harvest_policy.zip"
    model.save(str(out_path))
    print(f"saved RL policy -> {out_path}")


if __name__ == "__main__":
    main()
