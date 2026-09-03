"""
Aligns raw satellite NDVI, weather, and soil pulls into one weekly table per
field - the single input the model encoders (models/encoders/) train on.

Reads:  data/raw/satellite/{field_id}_ndvi.csv
        data/raw/weather/{field_id}_weather_daily.csv
        data/raw/soil/soil_properties.csv
Writes: data/processed/{field_id}_aligned.csv

Run (after satellite_fetch.py, weather_fetch.py, soil_fetch.py have all run):
    python -m ingestion.align_pipeline
"""

from datetime import date

import pandas as pd

from ingestion.config import CROP_CALENDARS, FIELDS, PROCESSED_DIR, RAW_DIR

SATELLITE_DIR = RAW_DIR / "satellite"

# Longest run of consecutive missing weeks that may be interpolated. Sentinel-2
# revisits every 5 days and Landsat every 16, so a genuine cloud gap of 3 weeks
# is common and bridging it is standard practice; a gap longer than that means
# the season was not observed, and filling it manufactures a flat line that
# looks exactly like real data. Weeks left NaN here cause the affected season
# to be dropped by training/dataset.py rather than trained on.
MAX_INTERPOLATION_WEEKS = 3
WEATHER_DIR = RAW_DIR / "weather"
SOIL_DIR = RAW_DIR / "soil"


def _season_start_for_year(crop: str, year: int) -> pd.Timestamp:
    cal = CROP_CALENDARS[crop]
    return pd.Timestamp(year=year, month=cal["planting_month"], day=cal["planting_day"])


def _growth_stage(dates: pd.Series, crop: str) -> pd.Series:
    """0.0 at planting, 1.0 at the end of the crop calendar's season length,
    computed relative to each date's nearest prior planting date."""
    cal = CROP_CALENDARS[crop]
    season_weeks = cal["season_length_weeks"]

    def stage_for(d: pd.Timestamp) -> float:
        candidates = [_season_start_for_year(crop, d.year), _season_start_for_year(crop, d.year - 1)]
        season_start = max((c for c in candidates if c <= d), default=candidates[-1])
        weeks_in = (d - season_start).days / 7
        return max(0.0, min(1.0, weeks_in / season_weeks))

    return dates.apply(stage_for)


def align_field(field: dict, soil_row: pd.Series | None) -> pd.DataFrame:
    field_id = field["field_id"]

    satellite = pd.read_csv(SATELLITE_DIR / f"{field_id}_ndvi.csv", parse_dates=["date"])
    weather = pd.read_csv(WEATHER_DIR / f"{field_id}_weather_daily.csv", parse_dates=["date"])

    index_cols = [c for c in ("mean_ndvi", "mean_evi", "mean_ndwi") if c in satellite.columns]
    indices_weekly = satellite.set_index("date").resample("W")[index_cols].mean()
    indices_weekly = indices_weekly.rename(columns={c: c.replace("mean_", "") for c in index_cols})

    weather_weekly = (
        weather.set_index("date")
        .resample("W")
        .agg({"temp_c": "mean", "precip_mm": "sum", "humidity_pct": "mean", "wind_speed_ms": "mean"})
    )

    aligned = weather_weekly.join(indices_weekly, how="left")

    # Record which weeks are real observations BEFORE any gap filling, so
    # downstream code and the write-up can state the observed fraction instead
    # of treating interpolated values as data.
    observed = aligned[indices_weekly.columns[0]].notna()

    # Bridge cloud gaps, but only SHORT ones. The previous call was
    # interpolate(limit_direction="both") with no limit, which happily spanned
    # gaps of any length - a season with no clear scene at all came out as a
    # dead-flat line at the last observed value, indistinguishable from real
    # data (F001's 2022 season: NDVI 0.30 for 20 consecutive weeks). Capping
    # the run means a long gap stays NaN and the season is dropped rather than
    # silently invented.
    for col in indices_weekly.columns:
        aligned[col] = aligned[col].interpolate(limit=MAX_INTERPOLATION_WEEKS, limit_area="inside")

    aligned["ndvi_observed"] = observed.astype(int)
    aligned = aligned.reset_index().rename(columns={"date": "week"})

    aligned["field_id"] = field_id
    aligned["crop"] = field["crop"]
    aligned["growth_stage"] = _growth_stage(aligned["week"], field["crop"])

    if soil_row is not None:
        for col in ("phh2o", "soc", "clay", "sand", "nitrogen"):
            if col in soil_row:
                aligned[col] = soil_row[col]

    return aligned


def _load_soil() -> "pd.DataFrame | None":
    """Prefers the Earth Engine SoilGrids pull over the REST one.

    ingestion/soil_fetch.py's REST path returned HTTP 200 with every value
    null for 5 of the 7 fields, so those fields were being filled by
    training/dataset.py's impute_missing_soil with the mean of the two
    Coimbatore fields that did resolve - i.e. Punjab, West Bengal and Andhra
    Pradesh were all training on Coimbatore soil. ingestion/soil_fetch_ee.py
    resolves all 7 with real, regionally-distinct values (Punjab pH 7.8
    alkaline, West Bengal pH 6.3 acidic), so it is used when present and the
    REST file is kept only as a fallback.
    """
    ee_path = SOIL_DIR / "soil_properties_ee.csv"
    rest_path = SOIL_DIR / "soil_properties.csv"
    if ee_path.exists():
        print(f"using Earth Engine soil: {ee_path.name}")
        return pd.read_csv(ee_path)
    if rest_path.exists():
        print(f"WARNING: falling back to REST soil ({rest_path.name}); run soil_fetch_ee for full coverage")
        return pd.read_csv(rest_path)
    return None


def main():
    soil_df = _load_soil()

    for field in FIELDS:
        soil_row = None
        if soil_df is not None:
            match = soil_df[soil_df["field_id"] == field["field_id"]]
            soil_row = match.iloc[0] if not match.empty else None

        try:
            aligned = align_field(field, soil_row)
        except FileNotFoundError as e:
            print(f"Skipping {field['field_id']}: {e}. Run satellite_fetch.py / weather_fetch.py first.")
            continue

        out_path = PROCESSED_DIR / f"{field['field_id']}_aligned.csv"
        aligned.to_csv(out_path, index=False)
        print(f"wrote {len(aligned)} weekly rows -> {out_path}")


if __name__ == "__main__":
    main()
