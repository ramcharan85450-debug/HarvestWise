"""
Derives the Climate-Shock Benchmark's season labels from the project's REAL
ERA5 record (data/raw/weather/*_weather_daily.csv), replacing the fabricated
placeholder labels build_splits.py originally shipped with.

Run:
    python -m evaluation.climate_shock_benchmark.derive_labels

Writes derived_labels.json next to this file, which build_splits.py loads.

Method
------
For each field, the growing season is taken from that field's crop calendar
(ingestion/config.py CROP_CALENDARS), and its total rainfall and mean
temperature are summed/averaged over that window from the real daily ERA5
series. A season is then labelled RELATIVE TO ITS OWN FIELD's multi-year
mean, because absolute rainfall differs by an order of magnitude across the
regions in this dataset (Punjab rabi wheat ~150 mm vs. Andhra Pradesh kharif
rice ~1200 mm) - a single global mm threshold would label entire regions as
permanently "drought" and is meaningless here. For the same reason labels are
per (field_id, year), not per year: the real record shows West Bengal's 2022
season at 53% of its normal rainfall while Punjab's 2022 was unremarkable, so
one global label per year would be simply wrong.

Thresholds (documented, deliberately simple, applied uniformly):
    drought      : season rainfall < 75% of that field's mean
    wet_extreme  : season rainfall > 130% of that field's mean
    heatwave     : season mean temperature > field mean + 1.0 C
    normal       : none of the above

LIMITATIONS - state these wherever benchmark results are reported:
  * Only 4 seasons per field are available (START_DATE 2022 - END_DATE 2025),
    so each field's "normal" baseline is estimated from the same handful of
    seasons being classified against it. This is a weak baseline; a proper
    climatology uses 20-30 years. Widening ingestion/config.py's date range
    and re-running the ERA5 pull is the real fix.
  * Seasons whose window extends past END_DATE are EXCLUDED, not labelled.
    They look artificially dry purely because the record stops mid-season
    (e.g. F007's Nov 2025 - Apr 2026 wheat season shows 1.8 mm, which is
    truncation, not drought). Excluding them avoids inventing a shock year
    out of a data-coverage gap.
  * ERA5 rainfall here is sampled at 2 steps/day and scaled to daily totals
    (see ingestion/weather_fetch.py), so absolute mm are right-magnitude but
    biased high at drier sites. Labels depend on RATIOS within a field, which
    is far more robust to that bias than absolute values would be.
"""

import json
from pathlib import Path

import pandas as pd

from ingestion.config import CROP_CALENDARS, END_DATE, FIELDS, RAW_DIR

OUTPUT_PATH = Path(__file__).resolve().parent / "derived_labels.json"

DROUGHT_RATIO = 0.75
WET_EXTREME_RATIO = 1.30
HEATWAVE_DELTA_C = 1.0
MIN_SEASON_DAYS = 30


def season_climate(field: dict) -> dict[int, dict]:
    """Real per-season rainfall total and mean temperature for one field.
    Seasons running past END_DATE are omitted (see module docstring)."""
    cal = CROP_CALENDARS[field["crop"]]
    path = RAW_DIR / "weather" / f"{field['field_id']}_weather_daily.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    data_end = pd.Timestamp(END_DATE)

    seasons = {}
    for year in sorted(df["date"].dt.year.unique()):
        start = pd.Timestamp(year=year, month=cal["planting_month"], day=cal["planting_day"])
        end = start + pd.Timedelta(weeks=cal["season_length_weeks"])
        if end > data_end:
            continue  # truncated by the end of the record - not a real shock
        window = df[(df["date"] >= start) & (df["date"] < end)]
        if len(window) < MIN_SEASON_DAYS:
            continue
        seasons[int(year)] = {
            "rain_mm": float(window["precip_mm"].sum()),
            "temp_c": float(window["temp_c"].mean()),
        }
    return seasons


def label_seasons(seasons: dict[int, dict]) -> dict[int, str]:
    if not seasons:
        return {}
    mean_rain = sum(s["rain_mm"] for s in seasons.values()) / len(seasons)
    mean_temp = sum(s["temp_c"] for s in seasons.values()) / len(seasons)

    labels = {}
    for year, s in seasons.items():
        ratio = s["rain_mm"] / mean_rain if mean_rain else 1.0
        if ratio < DROUGHT_RATIO:
            label = "drought"
        elif ratio > WET_EXTREME_RATIO:
            label = "wet_extreme"
        elif s["temp_c"] > mean_temp + HEATWAVE_DELTA_C:
            label = "heatwave"
        else:
            label = "normal"
        labels[year] = label
    return labels


def main():
    out = {"_method": "derived from real ERA5 growing-season anomalies; see derive_labels.py docstring", "fields": {}}
    print(f"{'field':<7}{'year':<6}{'rain_mm':>10}{'ratio':>8}{'temp_C':>8}  label")
    for field in FIELDS:
        seasons = season_climate(field)
        labels = label_seasons(seasons)
        mean_rain = sum(s["rain_mm"] for s in seasons.values()) / len(seasons) if seasons else 0.0
        out["fields"][field["field_id"]] = {str(y): labels[y] for y in sorted(labels)}
        for year in sorted(seasons):
            s = seasons[year]
            ratio = s["rain_mm"] / mean_rain if mean_rain else 0.0
            print(f"{field['field_id']:<7}{year:<6}{s['rain_mm']:>10.1f}{ratio:>8.2f}{s['temp_c']:>8.1f}  {labels[year]}")

    OUTPUT_PATH.write_text(json.dumps(out, indent=2))
    counts: dict[str, int] = {}
    for per_year in out["fields"].values():
        for label in per_year.values():
            counts[label] = counts.get(label, 0) + 1
    print(f"\nlabel counts: {counts}")
    print(f"wrote -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
