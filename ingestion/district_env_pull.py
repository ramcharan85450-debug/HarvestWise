"""
Weather and satellite ingestion for the NEW Southern India district registry
(data/metadata/district_registry.csv, built by
ingestion/district_registry_build.py), as opposed to the older, separate
417-district registry (data/raw/external/datagovin/district_registry.json)
that ingestion/district_weather_pull.py and ingestion/district_landsat_pull.py
already serve. This script exists because the two registries cover only
partially-overlapping districts and year ranges (see
experiments/SOUTHERN_INDIA_COMPATIBILITY_ANALYSIS.md section 4) - reusing the
old scripts unmodified would have silently mixed the two id spaces.

Reuses the SAME underlying fetch functions as the older scripts
(ingestion.district_weather_pull.fetch_district_weather,
ingestion.landsat_fetch.fetch_vegetation_indices/cropland_mask_year,
ingestion.district_landsat_pull.district_geometry) rather than duplicating
their logic - this script is only new orchestration: which districts, which
years, and where to write the output.

Writes to NEW directories, never touching the existing field-level or
old-registry district outputs:
    data/raw/weather/southern_districts/{district_id}_weather_daily.csv
    data/raw/satellite/southern_districts/{district_id}_landsat.csv

Resumable: a district-year whose output already contains that year's data is
skipped (checked by re-reading the existing file, not just its presence) -
running this script twice never re-fetches or duplicates.

Run:
    python -m ingestion.district_env_pull --kind weather --years 2019,2024 --states "Tamil Nadu"
    python -m ingestion.district_env_pull --kind satellite --year-min 2000 --year-max 2012 --states Telangana
"""

import argparse
import csv
import json
import time
from pathlib import Path

import ee
import pandas as pd

from ingestion.district_landsat_pull import district_geometry
from ingestion.district_weather_pull import fetch_district_weather
from ingestion.landsat_fetch import EE_PROJECT_ID, cropland_mask_year, fetch_vegetation_indices

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
WEATHER_OUT = ROOT / "data" / "raw" / "weather" / "southern_districts"
SATELLITE_OUT = ROOT / "data" / "raw" / "satellite" / "southern_districts"
GEOBOUNDARIES_CACHE_DIR = ROOT / "data" / "metadata" / "boundary_sources" / "tn_districts_geoboundaries"


def _resolve_geometry(rec) -> "ee.Geometry":
    """GAUL-matched districts (the majority) resolve via a server-side GAUL
    FeatureCollection filter, as before. The 9 districts resolved by
    ingestion/district_registry_add_geoboundaries.py instead have a cached
    real GeoJSON polygon on disk (fetched from geoBoundaries, not GAUL) -
    those are loaded and turned into an ee.Geometry.Polygon directly, never
    silently routed through the GAUL path with a name that happens to
    coincidentally match something else."""
    if str(rec.geometry_source).startswith("geoBoundaries"):
        cache_path = GEOBOUNDARIES_CACHE_DIR / f"{rec.district_id}_geoboundaries.geojson"
        feat = json.loads(cache_path.read_text(encoding="utf-8"))
        return ee.Geometry(feat["geometry"])
    return district_geometry(rec.canonical_district_name)


def _load_registry(states: list[str] | None) -> pd.DataFrame:
    df = pd.read_csv(REGISTRY_PATH)
    df = df[df["latitude"].notna()]  # only districts with a real boundary match (GAUL or geoBoundaries)
    if states:
        df = df[df["state"].isin(states)]
    return df


def _year_windows(years: list[int] | None, year_min: int | None, year_max: int | None) -> list[tuple[int, int]]:
    """Returns a list of (start_year, end_year) inclusive windows. Explicit
    --years gives one 1-year window per value (so a district's weather file
    for, e.g., Tamil Nadu only ever contains 2019 and 2024, never the
    unneeded years in between); --year-min/--year-max gives one continuous
    window, matching how the older district scripts already work."""
    if years:
        return [(y, y) for y in years]
    return [(year_min, year_max)]


def pull_weather(df: pd.DataFrame, windows: list[tuple[int, int]]) -> dict:
    ee.Initialize(project=EE_PROJECT_ID)
    WEATHER_OUT.mkdir(parents=True, exist_ok=True)
    done, skipped, failed = 0, 0, 0
    t0 = time.time()

    for rec in df.itertuples(index=False):
        out_path = WEATHER_OUT / f"{rec.district_id}_weather_daily.csv"
        existing_years = set()
        if out_path.exists():
            existing = pd.read_csv(out_path, parse_dates=["date"])
            existing_years = set(existing["date"].dt.year.unique())

        all_rows = []
        if out_path.exists():
            all_rows = pd.read_csv(out_path).to_dict("records")

        geom = None
        for y0, y1 in windows:
            if set(range(y0, y1 + 1)).issubset(existing_years):
                skipped += 1
                continue
            if geom is None:
                geom = _resolve_geometry(rec)
            try:
                rows = fetch_district_weather(geom, f"{y0}-01-01", f"{y1}-12-31")
                all_rows.extend(rows)
                done += 1
            except Exception as e:
                print(f"  {rec.district_id} {rec.district} {y0}-{y1}: {type(e).__name__} {str(e)[:100]}")
                failed += 1

        if all_rows:
            all_rows = {r["date"]: r for r in all_rows}.values()  # de-dupe by date
            all_rows = sorted(all_rows, key=lambda r: r["date"])
            with open(out_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["date", "temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"])
                w.writeheader()
                w.writerows(all_rows)
        if (done) % 5 == 0 and done:
            print(f"  {done} pulled ({skipped} already had this window, {failed} failed) | {(time.time()-t0)/max(done,1):.0f}s/pull")

    return {"done": done, "skipped": skipped, "failed": failed}


def pull_satellite(df: pd.DataFrame, windows: list[tuple[int, int]]) -> dict:
    ee.Initialize(project=EE_PROJECT_ID)
    SATELLITE_OUT.mkdir(parents=True, exist_ok=True)
    done, skipped, failed = 0, 0, 0
    t0 = time.time()

    for rec in df.itertuples(index=False):
        out_path = SATELLITE_OUT / f"{rec.district_id}_landsat.csv"
        existing_years = set()
        all_rows = []
        if out_path.exists():
            existing = pd.read_csv(out_path, parse_dates=["date"])
            existing_years = set(existing["date"].dt.year.unique())
            all_rows = pd.read_csv(out_path).to_dict("records")

        geom = None
        for y0, y1 in windows:
            if set(range(y0, y1 + 1)).issubset(existing_years):
                skipped += 1
                continue
            if geom is None:
                geom = _resolve_geometry(rec)
            mid_year = (y0 + y1) // 2
            mask = cropland_mask_year(mid_year)
            try:
                rows = fetch_vegetation_indices(geom, f"{y0}-01-01", f"{y1}-12-31", scale=100, cropland_mask=mask)
                all_rows.extend(rows)
                done += 1
            except Exception as e:
                print(f"  {rec.district_id} {rec.district} {y0}-{y1}: {type(e).__name__} {str(e)[:100]}")
                failed += 1

        if all_rows:
            all_rows = {r["date"]: r for r in all_rows}.values()
            all_rows = sorted(all_rows, key=lambda r: r["date"])
            with open(out_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["date", "mean_ndvi", "mean_evi", "mean_ndwi", "cloud_cover_pct"])
                w.writeheader()
                w.writerows(all_rows)
        if done % 2 == 0 and done:
            print(f"  {done} pulled ({skipped} already had this window, {failed} failed) | {(time.time()-t0)/max(done,1):.0f}s/pull")

    return {"done": done, "skipped": skipped, "failed": failed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["weather", "satellite"], required=True)
    parser.add_argument("--states", default="", help="Comma-separated; empty = all registry states.")
    parser.add_argument("--years", default="", help="Comma-separated explicit years, e.g. 2019,2024.")
    parser.add_argument("--year-min", type=int, default=None)
    parser.add_argument("--year-max", type=int, default=None)
    args = parser.parse_args()

    states = [s.strip() for s in args.states.split(",") if s.strip()] or None
    years = [int(y) for y in args.years.split(",") if y.strip()] or None
    windows = _year_windows(years, args.year_min, args.year_max)

    df = _load_registry(states)
    print(f"{len(df)} districts targeted, windows={windows}")

    if args.kind == "weather":
        result = pull_weather(df, windows)
    else:
        result = pull_satellite(df, windows)

    print(f"\n{args.kind} pull complete: {result}")


if __name__ == "__main__":
    main()
