"""
Replays real VDSA SATIndia inputs through the trained yield-forecast model
and RL harvest policy, and compares the model's recommended harvest week
against what real growers actually did.

This is the comparison the project's original 7 fields could never support -
see data/raw/harvest_outcomes/README.md and RESULTS.md section 5b. For the
first time, satellite imagery, weather, and a ground-truth outcome are all
real and co-located: 3 confirmed-geocoded ICRISAT VDSA villages (Kalman,
Kanzara, Shirapur - Solapur/Akola, Maharashtra), with real Landsat pulled for
the village polygon and real ERA5-Land weather for the same point
(ingestion/vdsa_satindia_outcomes.py, ingestion/soil_fetch_ee.py).

Scope, stated plainly: only the WHEAT records are used, not the full 1,238.
The trained forecast model and the RL policy's agronomic window
(models/heads/rl_harvest_policy/agronomic_window.py) were both built for the
project's two crop archetypes - rice and wheat, per training/dataset.py's
build_synthetic_dataset and the CROP_CALENDARS entries in ingestion/config.py.
These 3 villages are rainfed semi-arid Maharashtra - the actual crop mix is
sorghum, soybean, pigeonpea, onion, cotton, chickpea and only secondarily
wheat (120 of 1,238 records). Running sorghum or onion through a model whose
yield scale and phenology were learned from rice/wheat curves would produce a
number, not a valid comparison. Wheat is the one crop here the model has any
right to be evaluated against, so this filters to it rather than diluting the
result with 1,118 out-of-distribution predictions.

Run (after ingestion/vdsa_satindia_outcomes.py, the village soil pull, and
training/train_forecast_model.py / models/heads/rl_harvest_policy/train_rl.py
have all produced their outputs):
    python -m evaluation.outcome_validation.satindia_replay
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ingestion.config import RAW_DIR
from models.heads.rl_harvest_policy.agronomic_window import agronomic_bounds, window_is_observed
from models.heads.rl_harvest_policy.env import HarvestTimingEnv, SeasonTrajectory
from models.heads.static_harvest_optimizer import optimize_window
from training.dataset import SOIL_COLS, normalize_model_inputs
from training.train_forecast_model import CHECKPOINT_DIR as FORECAST_CHECKPOINT_DIR
from training.train_forecast_model import ForecastModel

OUTCOMES_PATH = RAW_DIR / "harvest_outcomes" / "VDSA_SATIndia_named_villages.csv"
SATELLITE_DIR = RAW_DIR / "satellite" / "vdsa_villages"
WEATHER_DIR = RAW_DIR / "weather" / "vdsa_villages"
SOIL_PATH = RAW_DIR / "soil" / "vdsa_villages_soil.csv"
RL_CHECKPOINT = Path(__file__).resolve().parents[2] / "backend" / "checkpoints" / "rl_harvest_policy.zip"

RESULTS_PATH = Path(__file__).resolve().parent / "satindia_replay_results.json"
RECORDS_PATH = Path(__file__).resolve().parent / "satindia_replay_records.csv"

SEASON_WEEKS = 27  # 189 days, covers the longest real wheat sow-to-harvest interval (187d) in this data
MAX_INTERPOLATION_WEEKS = 3  # same cap as ingestion/align_pipeline.py, for the same reason
CROP = "wheat"


def _weekly_village_series(village: str) -> pd.DataFrame:
    """Builds one continuous weekly vision+weather table per village, exactly
    like ingestion/align_pipeline.py's align_field but sourced from the real
    village-level Landsat/ERA5 pulls rather than a field's fixed geometry."""
    sat = pd.read_csv(SATELLITE_DIR / f"{village}_landsat.csv", parse_dates=["date"])
    wx = pd.read_csv(WEATHER_DIR / f"{village}_weather_daily.csv", parse_dates=["date"])

    idx_cols = ["mean_ndvi", "mean_evi", "mean_ndwi"]
    indices_weekly = sat.set_index("date").resample("W")[idx_cols].mean()
    indices_weekly = indices_weekly.rename(columns={c: c.replace("mean_", "") for c in idx_cols})

    weather_weekly = (
        wx.set_index("date")
        .resample("W")
        .agg({"temp_c": "mean", "precip_mm": "sum", "humidity_pct": "mean", "wind_speed_ms": "mean"})
    )

    weekly = weather_weekly.join(indices_weekly, how="left")
    for col in idx_cols:
        col_short = col.replace("mean_", "")
        weekly[col_short] = weekly[col_short].interpolate(limit=MAX_INTERPOLATION_WEEKS, limit_area="inside")
    return weekly


def _plot_window(weekly: pd.DataFrame, sow_date: pd.Timestamp) -> "pd.DataFrame | None":
    """Slices SEASON_WEEKS of weekly data starting at the real sow date.
    Returns None if the window falls outside the pulled range or still has
    unfilled NDVI gaps after the capped interpolation above - same "drop
    rather than fabricate" rule as training/dataset.py."""
    end_date = sow_date + pd.Timedelta(weeks=SEASON_WEEKS)
    window = weekly.loc[(weekly.index >= sow_date) & (weekly.index < end_date)]
    if len(window) < SEASON_WEEKS // 2:
        return None
    if window["ndvi"].isna().any():
        return None
    return window


def build_examples() -> pd.DataFrame:
    outcomes = pd.read_csv(OUTCOMES_PATH, parse_dates=["sow_date", "harvest_date"])
    outcomes["crop_norm"] = outcomes.crop_name.str.strip().str.upper()
    wheat = outcomes[outcomes.crop_norm == "WHEAT"].reset_index(drop=True)

    soil_df = pd.read_csv(SOIL_PATH).set_index("field_id")

    village_weekly = {v: _weekly_village_series(v) for v in wheat.village.unique()}

    rows = []
    dropped_no_window = 0
    for _, rec in wheat.iterrows():
        weekly = village_weekly[rec.village]
        window = _plot_window(weekly, rec.sow_date)
        if window is None:
            dropped_no_window += 1
            continue

        ndvi = window["ndvi"].to_numpy()
        ndvi_delta = np.diff(ndvi, prepend=ndvi[0])
        evi = window["evi"].to_numpy()
        ndwi = window["ndwi"].to_numpy()
        vision_x = np.stack([ndvi, ndvi_delta, evi, ndwi], axis=1).astype(np.float32)

        weather_x = window[["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"]].to_numpy().astype(np.float32)

        days_in = (window.index - rec.sow_date).days.to_numpy()
        growth_stage = np.clip(days_in / (SEASON_WEEKS * 7), 0.0, 1.0).astype(np.float32)

        soil_row = soil_df.loc[rec.village]
        soil_x = soil_row[SOIL_COLS].to_numpy().astype(np.float32)

        if len(vision_x) < SEASON_WEEKS:
            pad = SEASON_WEEKS - len(vision_x)
            vision_x = np.pad(vision_x, [(0, pad), (0, 0)], mode="edge")
            weather_x = np.pad(weather_x, [(0, pad), (0, 0)], mode="edge")
            growth_stage = np.pad(growth_stage, (0, pad), mode="edge")

        rows.append(
            {
                "village": rec.village,
                "hh_key": rec.hh_key,
                "plot_code": rec.PLOT_CO,
                "sow_date": rec.sow_date,
                "real_harvest_date": rec.harvest_date,
                "real_days_to_harvest": int(rec.days_to_harvest),
                "real_yield_t_ha": float(rec.yield_t_ha),
                "vision_x": vision_x,
                "weather_x": weather_x,
                "growth_stage": growth_stage,
                "soil_x": soil_x,
            }
        )

    print(f"{len(rows)} real wheat plot-seasons with a fully-observed satellite window ({dropped_no_window} dropped)")
    return pd.DataFrame(rows)


def load_forecast_model() -> ForecastModel:
    model = ForecastModel()
    ckpt = torch.load(FORECAST_CHECKPOINT_DIR / "fusion_backbone.pt", map_location="cpu")
    model.vision_enc.load_state_dict(ckpt["vision_enc"])
    model.weather_enc.load_state_dict(ckpt["weather_enc"])
    model.soil_enc.load_state_dict(ckpt["soil_enc"])
    model.fusion.load_state_dict(ckpt["fusion"])
    model.backbone.load_state_dict(ckpt["backbone"])
    model.head.load_state_dict(torch.load(FORECAST_CHECKPOINT_DIR / "yield_head.pt", map_location="cpu"))
    model.eval()
    return model


def rl_recommended_week(policy, traj: SeasonTrajectory) -> int:
    env = HarvestTimingEnv([traj])
    obs, _ = env.reset(seed=0)
    week = traj.min_harvest_week
    for _ in range(len(traj.weekly_median_yield)):
        action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        week = info["week"]
        if terminated or truncated:
            break
    return week


def main():
    examples = build_examples()
    if examples.empty:
        raise SystemExit("No usable real wheat plot-seasons - check the village pulls and soil file exist.")

    model = load_forecast_model()

    policy = None
    if RL_CHECKPOINT.exists():
        from stable_baselines3 import PPO

        policy = PPO.load(str(RL_CHECKPOINT))
    else:
        print(f"No RL checkpoint at {RL_CHECKPOINT} - RL columns will be blank, static-optimizer comparison only.")

    records = []
    skipped_unobserved = 0
    with torch.no_grad():
        for _, ex in examples.iterrows():
            vision_x, weather_x, soil_x = normalize_model_inputs(ex.vision_x, ex.weather_x, ex.soil_x)
            batch = {
                "vision_x": torch.from_numpy(vision_x).unsqueeze(0),
                "weather_x": torch.from_numpy(weather_x).unsqueeze(0),
                "soil_x": torch.from_numpy(soil_x).unsqueeze(0),
                "growth_stage": torch.from_numpy(ex.growth_stage).unsqueeze(0),
            }
            quantiles, _ = model(batch)
            q = quantiles[0].numpy()
            season_len = q.shape[0]

            if not window_is_observed(ex.vision_x, CROP, season_len):
                skipped_unobserved += 1
                continue
            min_week, _ = agronomic_bounds(ex.vision_x, CROP, season_len)

            traj = SeasonTrajectory(
                weekly_median_yield=q[:, 1].tolist(),
                weekly_low_yield=q[:, 0].tolist(),
                weekly_high_yield=q[:, 2].tolist(),
                weekly_rainfall_mm=ex.weather_x[:, 1].tolist(),
                min_harvest_week=min_week,
            )

            static_result = optimize_window(
                traj.weekly_median_yield, traj.weekly_rainfall_mm, window_len_weeks=1, search_start_idx=min_week
            )
            static_week = static_result.start_week_idx

            rl_week = rl_recommended_week(policy, traj) if policy is not None else None

            real_week = ex.real_days_to_harvest / 7.0

            records.append(
                {
                    "village": ex.village,
                    "hh_key": ex.hh_key,
                    "plot_code": ex.plot_code,
                    "sow_date": ex.sow_date.date().isoformat(),
                    "real_days_to_harvest": ex.real_days_to_harvest,
                    "real_harvest_week": round(real_week, 2),
                    "real_yield_t_ha": ex.real_yield_t_ha,
                    "min_harvest_week": min_week,
                    "static_recommended_week": static_week,
                    "rl_recommended_week": rl_week,
                    "model_predicted_yield_t_ha_at_static_week": q[static_week, 1],
                    "model_predicted_yield_t_ha_at_rl_week": q[rl_week, 1] if rl_week is not None else None,
                }
            )

    if skipped_unobserved:
        print(f"skipped {skipped_unobserved} plot(s) whose agronomic wheat window falls past the observed satellite data")

    df = pd.DataFrame(records)
    df.to_csv(RECORDS_PATH, index=False)

    df["static_week_error"] = df.static_recommended_week - df.real_harvest_week
    summary = {
        "n_real_wheat_plot_seasons_replayed": len(df),
        "static_vs_real": {
            "mae_weeks": round(float(df.static_week_error.abs().mean()), 2),
            "mean_signed_error_weeks": round(float(df.static_week_error.mean()), 2),
            "within_2_weeks_pct": round(float(100 * (df.static_week_error.abs() <= 2).mean()), 1),
        },
        "model_yield_at_static_week_vs_real": {
            "mae_t_ha": round(float((df.model_predicted_yield_t_ha_at_static_week - df.real_yield_t_ha).abs().mean()), 3),
            "real_mean_t_ha": round(float(df.real_yield_t_ha.mean()), 3),
            "predicted_mean_t_ha": round(float(df.model_predicted_yield_t_ha_at_static_week.mean()), 3),
        },
    }
    if df.rl_recommended_week.notna().any():
        df["rl_week_error"] = df.rl_recommended_week - df.real_harvest_week
        summary["rl_vs_real"] = {
            "mae_weeks": round(float(df.rl_week_error.abs().mean()), 2),
            "mean_signed_error_weeks": round(float(df.rl_week_error.mean()), 2),
            "within_2_weeks_pct": round(float(100 * (df.rl_week_error.abs() <= 2).mean()), 1),
        }
        summary["model_yield_at_rl_week_vs_real"] = {
            "mae_t_ha": round(float((df.model_predicted_yield_t_ha_at_rl_week - df.real_yield_t_ha).abs().mean()), 3),
        }

    print(json.dumps(summary, indent=2))
    RESULTS_PATH.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote per-record -> {RECORDS_PATH}")
    print(f"wrote summary -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
