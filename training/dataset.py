"""
Turns data/processed/{field_id}_aligned.csv (built by ingestion/align_pipeline.py)
into per-season training examples for the yield forecast model.

Needs one more real-data file per field that ingestion/ doesn't fetch
automatically (no public API covers it): data/raw/yield_labels/{field_id}_yield_labels.csv
with columns `season_start_date,final_yield_t_ha`, sourced from USDA NASS /
your state agriculture portal / your own case-study records - see the
project's Phase 1 data-acquisition notes. Until that file exists, use
build_synthetic_dataset() below to smoke-test the training loop.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from ingestion.config import CROP_CALENDARS, FIELDS, PROCESSED_DIR, RAW_DIR

YIELD_LABELS_DIR = RAW_DIR / "yield_labels"

SOIL_COLS = ["phh2o", "soc", "clay", "sand", "nitrogen"]
WEATHER_COLS = ["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"]


@dataclass
class SeasonExample:
    field_id: str
    vision_x: np.ndarray  # (T, 4) -> [ndvi, ndvi_delta, evi, ndwi]
    weather_x: np.ndarray  # (T, 4)
    soil_x: np.ndarray  # (5,)
    growth_stage: np.ndarray  # (T,)
    final_yield: float
    season_start_date: str | None = None  # ISO date; used by the climate-shock benchmark to split by year


def _segment_seasons(aligned: pd.DataFrame, season_length_weeks: int) -> list[pd.DataFrame]:
    """Splits one field's continuous weekly record into season-length chunks,
    aligned to growth_stage resets (a drop back near 0 marks a new season)."""
    reset_idx = [0] + [
        i for i in range(1, len(aligned)) if aligned["growth_stage"].iloc[i] < aligned["growth_stage"].iloc[i - 1] - 0.5
    ]
    reset_idx.append(len(aligned))

    seasons = []
    for start, end in zip(reset_idx[:-1], reset_idx[1:]):
        chunk = aligned.iloc[start:end]
        if len(chunk) >= season_length_weeks // 2:  # keep partial seasons if reasonably complete
            seasons.append(chunk)
    return seasons


def _pad_or_truncate(arr: np.ndarray, length: int) -> np.ndarray:
    if len(arr) >= length:
        return arr[:length]
    pad_width = [(0, length - len(arr))] + [(0, 0)] * (arr.ndim - 1)
    return np.pad(arr, pad_width, mode="edge")


def _match_yield_label(labels: pd.DataFrame, season_start: pd.Timestamp, tolerance_days: int = 45) -> pd.DataFrame:
    """Prefers an exact year-aware match (season_start within `tolerance_days`
    of the label's actual date) - used when the label file has genuinely
    year-varying real figures (e.g. national Kharif rice yield by year, see
    data/raw/yield_labels/README.md). Falls back to day-of-year matching,
    ignoring calendar year, only when no year-specific match exists - for a
    single repeating district-level label used as a static approximation."""
    abs_diff = (labels["season_start_date"] - season_start).abs().dt.days
    exact = labels[abs_diff < tolerance_days]
    if not exact.empty:
        return exact

    def doy_diff(label_date: pd.Timestamp) -> int:
        diff = abs(label_date.dayofyear - season_start.dayofyear)
        return min(diff, 365 - diff)

    diffs = labels["season_start_date"].apply(doy_diff)
    candidates = labels[diffs < 30]
    if candidates.empty:
        return candidates
    # among same-day-of-year matches, prefer the chronologically nearest year
    # (e.g. a season with no yet-published label falls back to the most
    # recent known year's figure, not an arbitrary row)
    year_diff = (candidates["season_start_date"].dt.year - season_start.year).abs()
    return candidates.loc[year_diff.sort_values().index]


def build_dataset_from_processed(
    season_length_weeks: int = 20, granularity: str | None = None
) -> list[SeasonExample]:
    """granularity selects which tier of yield labels to attach:

        None        data/raw/yield_labels/*.csv          (default; the mixed
                    tier the project has always used - national figures for
                    F001-F003, state figures for F004-F007)
        "national"  data/raw/yield_labels/national/*.csv
        "state"     data/raw/yield_labels/state/*.csv
        "district"  data/raw/yield_labels/district/*.csv (not yet populated)

    The tiers exist for evaluation/label_granularity/, which measures how
    model accuracy responds to label spatial resolution while holding the
    fields, the satellite/weather/soil inputs and the models fixed. The
    difference is large and real: the national tier labels the Punjab rice
    field at 2.62 t/ha where the state tier labels the same field-season at
    4.37 t/ha.

    A field with no labels at the requested tier is SKIPPED rather than
    raising, so a tier covers only the fields it genuinely has figures for -
    filling gaps with a coarser stand-in would destroy the very contrast the
    sweep is measuring. The default (None) tier still raises, preserving the
    original behaviour that catches a missing label file during training.
    """
    examples: list[SeasonExample] = []
    labels_dir = YIELD_LABELS_DIR if granularity is None else YIELD_LABELS_DIR / granularity

    for field in FIELDS:
        aligned_path = PROCESSED_DIR / f"{field['field_id']}_aligned.csv"
        labels_path = labels_dir / f"{field['field_id']}_yield_labels.csv"
        if not aligned_path.exists():
            continue
        if not labels_path.exists():
            if granularity is not None:
                continue
            raise FileNotFoundError(
                f"Missing {labels_path}. Add real per-season yield labels before training "
                "(see this module's docstring), or use build_synthetic_dataset() to smoke-test."
            )

        aligned = pd.read_csv(aligned_path, parse_dates=["week"])
        labels = pd.read_csv(labels_path, parse_dates=["season_start_date"])
        cal = CROP_CALENDARS[field["crop"]]

        for chunk in _segment_seasons(aligned, cal["season_length_weeks"]):
            season_start = chunk["week"].iloc[0]
            match = _match_yield_label(labels, season_start)
            if match.empty:
                continue
            final_yield = float(match.iloc[0]["final_yield_t_ha"])

            ndvi = chunk["ndvi"].to_numpy()
            ndvi_delta = np.diff(ndvi, prepend=ndvi[0])
            evi = chunk["evi"].to_numpy() if "evi" in chunk.columns else np.zeros_like(ndvi)
            ndwi = chunk["ndwi"].to_numpy() if "ndwi" in chunk.columns else np.zeros_like(ndvi)
            vision_x = _pad_or_truncate(np.stack([ndvi, ndvi_delta, evi, ndwi], axis=1), season_length_weeks)

            # A season containing an unfilled satellite gap is DROPPED, not
            # trained on. ingestion/align_pipeline.py only interpolates runs of
            # up to MAX_INTERPOLATION_WEEKS, so a NaN here means that stretch of
            # the season was genuinely never observed. Previously the gap filler
            # had no length limit and produced a flat line at the last observed
            # value, which trained exactly like real data - F001's 2022 season
            # was NDVI 0.30 for all 20 weeks. Losing a season is the honest
            # outcome; keeping a fabricated one is not.
            if np.isnan(vision_x).any():
                continue
            weather_x = _pad_or_truncate(chunk[WEATHER_COLS].to_numpy(), season_length_weeks)
            soil_x = chunk[SOIL_COLS].iloc[0].to_numpy() if all(c in chunk.columns for c in SOIL_COLS) else np.zeros(5)
            growth_stage = _pad_or_truncate(chunk["growth_stage"].to_numpy(), season_length_weeks)

            examples.append(
                SeasonExample(
                    field_id=field["field_id"],
                    vision_x=vision_x.astype(np.float32),
                    weather_x=weather_x.astype(np.float32),
                    soil_x=soil_x.astype(np.float32),
                    growth_stage=growth_stage.astype(np.float32),
                    final_yield=final_yield,
                    season_start_date=season_start.date().isoformat(),
                )
            )

    _impute_missing_soil(examples)
    return examples


def _impute_missing_soil(examples: list[SeasonExample]) -> None:
    """Fills a field's missing SoilGrids values (a genuine no-data pixel, e.g.
    F001/Sulur - see data/raw/soil/soil_properties.csv) with the mean of the
    other real fields' soil vectors, in place, so NaNs don't propagate into
    the loss. Documented imputation, not a fabricated reading."""
    soil_stack = np.stack([ex.soil_x for ex in examples]) if examples else np.empty((0, 5))
    if not np.isnan(soil_stack).any():
        return
    col_mean = np.nanmean(soil_stack, axis=0)
    for ex in examples:
        if np.isnan(ex.soil_x).any():
            ex.soil_x = np.where(np.isnan(ex.soil_x), col_mean, ex.soil_x).astype(np.float32)


def build_synthetic_dataset(
    n_examples: int = 60,
    season_length_weeks: int = 20,
    seed: int = 0,
    weather_coupling: bool = False,
) -> list[SeasonExample]:
    """Generates two crop archetypes, not one - a real gap found once real
    wheat data (F007, Punjab) was added alongside rice: a model pretrained
    on only one generic (rice-like) synthetic curve/yield-range performed
    *worse* than a naive baseline once evaluated against a real holdout that
    mixed rice (~2.7-3.4 t/ha) and wheat (~4.2-4.7 t/ha), because it never
    saw a wheat-shaped curve or yield range during pretraining. The model
    has no explicit crop-type input, so it must infer crop identity from
    the vision/weather pattern itself - these two archetypes are built to
    be genuinely distinguishable that way (paddy's standing-water NDWI
    signature and warm kharif weather vs. wheat's drier NDWI and cool rabi
    weather), the same way a real field's signal would differ.

    weather_coupling
    ----------------
    OFF by default, because turning it on made real-holdout accuracy strictly
    worse. The flag exists so that result stays reproducible rather than
    becoming an undocumented dead end, and it is the most important negative
    result the project has.

    The motivation was sound. With coupling off, the label is drawn by
    rng.uniform() independently of the weather and vegetation generated beside
    it, so - holding crop identity constant, within the rice archetype alone -
    the label correlates with NOTHING: temperature -0.039, rainfall -0.020,
    peak NDVI +0.021. Since synthetic examples supply ~91% of the gradient
    signal at the default mix (300 synthetic vs 28 real), there is no
    weather-to-yield relationship available to learn, and the loss-optimal fit
    is "predict the archetype's mean".

    Turning coupling on applies bounded, correctly-signed agronomic stress
    (drought and heat reduce yield; the canopy visibly weakens with it) to
    both the label and the NDVI trajectory. It works as intended on the
    synthetic set: within-rice correlations become temperature -0.328,
    rainfall +0.424, peak NDVI +0.707.

    It does not transfer. Measured on the 28 real season examples:

        generator    n_syn   real-holdout MAE   corr(pred, actual)
        uncoupled      300         0.532         ~0 (near-constant preds)
        coupled        300         0.931         -
        coupled       3000         1.391         +0.078  (bias -1.32)

    Raising n_syn removed the overfitting (train 0.128 vs val 0.138), so the
    model genuinely learned the synthetic relationship - and real accuracy got
    monotonically WORSE as it did. The conclusion is uncomfortable but clear:
    the uncoupled model's apparently-good 0.532 is a mean-predictor in
    disguise (predictions spanned 2.93-3.15 against actuals spanning
    2.73-4.75), and coupling did not fix the model, it revealed that the
    synthetic prior contradicts the real labels.

    The likely cause is label granularity, not the generator. The real labels
    are national and state-level annual averages (see
    data/raw/yield_labels/README.md) while the inputs describe specific
    healthy irrigated fields. A vigorous canopy genuinely implies a high yield
    for THAT field, but the label it is trained against is a regional mean
    reflecting input use, variety and area-weighting across a whole state. No
    synthetic prior reconciles those. Field-level yield labels would - which
    makes them, rather than architecture work, the highest-value data item
    after real harvest outcomes.
    """
    rng = np.random.default_rng(seed)
    years = list(range(2016, 2025))
    examples = []
    for i in range(n_examples):
        year = years[i % len(years)]
        crop_type = "rice" if i % 2 == 0 else "wheat"
        progress = np.linspace(0.05, 1.0, season_length_weeks)

        # Season-level climate anomalies, used only when weather_coupling=True.
        # See this function's docstring for the measured outcome of that
        # experiment - it is OFF by default because it made real-holdout
        # accuracy worse, not better.
        rain_ratio = float(np.clip(rng.normal(1.0, 0.30), 0.25, 1.9))
        heat_delta = float(rng.normal(0.0, 2.5))

        if crop_type == "rice":
            # Real national Kharif rice yield (Economic Survey 2025-26,
            # Table 1.17) is 2.7-2.9 t/ha; the unstressed potential spans
            # rainfed/low-input up to high-productivity irrigated (e.g.
            # Punjab rice, ~4+ t/ha), and stress below pulls it down.
            yield_potential = rng.uniform(2.8, 4.8)
            base_temp, base_precip = 26.0, 6.0
            heat_tolerance_c = 2.0
            ndvi_base, ndvi_amp = 0.15, 0.55
            # standing water in a paddy field - NDWI baseline shifted positive
            ndwi_base, ndwi_amp = 0.0, 0.3
        else:
            # Real Punjab wheat yield (see data/raw/yield_labels/README.md,
            # F007) is 4.2-4.7 t/ha.
            yield_potential = rng.uniform(4.0, 5.8)
            base_temp, base_precip = 16.0, 1.5
            heat_tolerance_c = 2.5
            ndvi_base, ndvi_amp = 0.10, 0.60
            # no standing water in a rabi wheat field - NDWI stays negative
            ndwi_base, ndwi_amp = -0.5, 0.2

        # Agronomic stress response: monotone, bounded, and applied to BOTH
        # the yield label and the canopy trajectory, so vegetation vigour and
        # yield move together the way they do in a real season. Drought costs
        # more than an equivalent excess (a crop tolerates a wet year better
        # than a failed monsoon), and heat only bites past a crop-specific
        # tolerance. The coefficients are illustrative rather than calibrated
        # against a crop-growth model - the point is that a real, learnable,
        # correctly-signed relationship exists, not that its magnitude is
        # authoritative. State that wherever synthetic pretraining is described.
        water_stress = float(
            np.clip(1.0 - 0.60 * max(0.0, 1.0 - rain_ratio) - 0.30 * max(0.0, rain_ratio - 1.35), 0.30, 1.0)
        )
        heat_stress = float(
            np.clip(1.0 - 0.10 * max(0.0, heat_delta - heat_tolerance_c) - 0.02 * max(0.0, heat_delta), 0.40, 1.0)
        )
        if not weather_coupling:
            # Uncoupled (default). Reproduces the original generator: the
            # label is drawn independently of the season's weather, and the
            # yield ranges are the ones that bracket the real data directly
            # rather than being a pre-stress potential.
            rain_ratio, heat_delta = 1.0, 0.0
            water_stress = heat_stress = 1.0
            yield_potential = rng.uniform(1.8, 4.0) if crop_type == "rice" else rng.uniform(3.2, 5.2)

        canopy_vigor = water_stress * heat_stress
        peak = yield_potential * canopy_vigor

        # A stressed season produces a visibly weaker canopy, so peak NDVI
        # carries real information about the label instead of being noise.
        ndvi = np.clip(
            ndvi_base + ndvi_amp * (0.55 + 0.45 * canopy_vigor) * np.sin(progress * np.pi), 0, 1
        ) + rng.normal(0, 0.02, season_length_weeks)
        # NDWI tracks the season's water availability as well as the crop type.
        ndwi = np.clip(
            ndwi_base + 0.15 * (rain_ratio - 1.0) + ndwi_amp * np.sin(progress * np.pi)
            + rng.normal(0, 0.03, season_length_weeks),
            -1,
            1,
        )

        ndvi_delta = np.diff(ndvi, prepend=ndvi[0])
        evi = np.clip(ndvi * 0.9 + rng.normal(0, 0.02, season_length_weeks), 0, 1)
        # The weather series must actually express the anomalies the stress
        # factors were computed from, otherwise the relationship is unlearnable
        # from the model's inputs. precip is mm/DAY, matching the corrected
        # units in ingestion/weather_fetch.py's to_daily_csv.
        season_precip = base_precip * rain_ratio
        weather = np.stack(
            [
                base_temp + heat_delta + rng.normal(0, 3, season_length_weeks),
                np.clip(rng.normal(season_precip, season_precip * 0.8, season_length_weeks), 0, None),
                60 + 8 * (rain_ratio - 1.0) + rng.normal(0, 8, season_length_weeks),
                1.5 + rng.normal(0, 0.6, season_length_weeks),
            ],
            axis=1,
        )
        # Soil must be drawn on the SAME SCALE as real SoilGrids values, in
        # SOIL_COLS order [phh2o, soc, clay, sand, nitrogen]. This was
        # previously rng.normal(0, 1, 5) - i.e. values near zero - while real
        # fields feed the encoder values like [70, 219, 283, 490, 199]. A
        # network pretrained on ~N(0,1) inputs and then evaluated on inputs
        # ~500x larger is being asked to extrapolate far outside its training
        # distribution, and it was a direct cause of the deep model losing to
        # Random Forest on real data: tree splits are scale-invariant, so the
        # baselines were unaffected by the same bug. Ranges below bracket the
        # real values observed across the 7 fields in
        # data/raw/soil/soil_properties.csv.
        soil = np.array(
            [
                rng.uniform(55, 85),    # phh2o  (pH * 10)
                rng.uniform(120, 340),  # soc    (dg/kg)
                rng.uniform(150, 400),  # clay   (g/kg)
                rng.uniform(350, 620),  # sand   (g/kg)
                rng.uniform(110, 300),  # nitrogen (cg/kg)
            ]
        )
        month_day = "08-01" if crop_type == "rice" else "11-01"
        examples.append(
            SeasonExample(
                field_id=f"SYN{i:03d}",
                vision_x=np.stack([ndvi, ndvi_delta, evi, ndwi], axis=1).astype(np.float32),
                weather_x=weather.astype(np.float32),
                soil_x=soil.astype(np.float32),
                growth_stage=progress.astype(np.float32),
                final_yield=float(peak),
                season_start_date=f"{year}-{month_day}",
            )
        )
    return examples


# Input standardisation, as (center, scale) per feature in the same column
# order the encoders receive. Without this the network is fed soil values in
# the hundreds (sand ~490 g/kg) alongside NDVI in [0, 1] - a ~1000x spread
# across features, which badly conditions gradients and lets the largest-
# magnitude inputs dominate regardless of how informative they are. The
# classical baselines in evaluation/baselines/ are unaffected by that (tree
# splits are scale-invariant), which is exactly why they beat the deep model
# on real data until this was added.
#
# These are FIXED, documented physical constants rather than statistics
# fitted on a dataset, so the identical transform applies to synthetic and
# real examples, there is no train/test leakage, and no normalisation state
# has to be persisted alongside a checkpoint for inference to stay correct.
VISION_NORM = [(0.45, 0.25), (0.0, 0.08), (0.35, 0.25), (0.0, 0.30)]  # ndvi, ndvi_delta, evi, ndwi
WEATHER_NORM = [(25.0, 8.0), (5.0, 8.0), (65.0, 15.0), (2.0, 1.0)]  # temp_c, precip_mm, humidity_pct, wind_speed_ms
SOIL_NORM = [(70.0, 10.0), (220.0, 70.0), (280.0, 80.0), (480.0, 90.0), (200.0, 60.0)]  # SOIL_COLS order


def _standardize(arr: np.ndarray, norm: list[tuple[float, float]]) -> np.ndarray:
    centers = np.array([c for c, _ in norm], dtype=np.float32)
    scales = np.array([s for _, s in norm], dtype=np.float32)
    return ((arr - centers) / scales).astype(np.float32)


def normalize_model_inputs(vision_x: np.ndarray, weather_x: np.ndarray, soil_x: np.ndarray):
    """Applies the standardisation above. MUST be used everywhere model
    inputs are built - SeasonDataset below and
    models/heads/rl_harvest_policy/train_rl.py's trajectory replay both call
    it, so a checkpoint trained here stays valid there. Note it deliberately
    does NOT touch raw physical values used for decision logic elsewhere
    (e.g. rainfall in mm compared against HarvestTimingEnv's 25 mm risk
    threshold, which must stay in real units)."""
    return (
        _standardize(vision_x, VISION_NORM),
        _standardize(weather_x, WEATHER_NORM),
        _standardize(soil_x, SOIL_NORM),
    )


class SeasonDataset(Dataset):
    def __init__(self, examples: list[SeasonExample]):
        self.examples = examples

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int):
        ex = self.examples[idx]
        vision_x, weather_x, soil_x = normalize_model_inputs(ex.vision_x, ex.weather_x, ex.soil_x)
        return {
            "vision_x": torch.from_numpy(vision_x),
            "weather_x": torch.from_numpy(weather_x),
            "soil_x": torch.from_numpy(soil_x),
            "growth_stage": torch.from_numpy(ex.growth_stage),
            "final_yield": torch.tensor(ex.final_yield, dtype=torch.float32),
        }
