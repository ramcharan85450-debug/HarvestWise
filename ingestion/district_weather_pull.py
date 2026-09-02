"""
Daily ERA5-Land weather per district, via Earth Engine.

Why not the existing ingestion/weather_fetch.py: that goes through the
Copernicus CDS queue at roughly 5 minutes per field-year. The district dataset
is 417 districts x 13 years = 5,421 requests, i.e. about 18 days of queuing -
and the CDS backfill for just 7 fields already died once mid-run. Earth
Engine's ECMWF/ERA5_LAND/DAILY_AGGR carries the same reanalysis, pre-aggregated
to daily, with no queue, and the district polygons are already there for the
Landsat pull.

Variables are mapped to the exact column names training/dataset.py's
WEATHER_COLS expects - temp_c, precip_mm, humidity_pct, wind_speed_ms - so the
district data drops into the existing pipeline unchanged.

Unit handling, which is where the CDS path previously went wrong (precipitation
was read as mm/day when ERA5 reports metres, giving 54.6 mm/yr for Punjab
against a ~650 mm/yr climatology, which silently disabled the 25 mm
weather-risk term in both the RL reward and the static optimizer):

    temperature_2m                    K      -> degC   (-273.15)
    total_precipitation_sum           m/day  -> mm/day (x1000)
    dewpoint_temperature_2m           K      -> used with temp for RH
    u/v_component_of_wind_10m         m/s    -> speed = sqrt(u^2+v^2)

Relative humidity is computed from temperature and dewpoint with the Magnus
formula rather than taken from a field ERA5-Land does not provide.

Resumable: one CSV per district, existing files skipped.

Run:
    python -m ingestion.district_weather_pull --year-min 2000 --year-max 2012
"""

import argparse
import csv
import json
import math
import time

import ee

from ingestion.config import RAW_DIR
from ingestion.district_landsat_pull import district_geometry
from ingestion.landsat_fetch import EE_PROJECT_ID

REGISTRY = RAW_DIR / "external" / "datagovin" / "district_registry.json"
OUT_DIR = RAW_DIR / "weather" / "districts"
COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"

BANDS = [
    "temperature_2m",
    "dewpoint_temperature_2m",
    "total_precipitation_sum",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
]


def _relative_humidity(temp_c: float, dew_c: float) -> float:
    """Magnus formula. Returns %, clipped to [0, 100]."""
    a, b = 17.625, 243.04
    num = math.exp((a * dew_c) / (b + dew_c))
    den = math.exp((a * temp_c) / (b + temp_c))
    return max(0.0, min(100.0, 100.0 * num / den))


def fetch_district_weather(geom, start_date: str, end_date: str, scale: int = 11132) -> list[dict]:
    """scale defaults to ERA5-Land's native ~0.1 degree (11132 m) - reducing a
    coarse reanalysis grid at a finer scale would only resample, not add
    information, while costing far more compute."""
    coll = ee.ImageCollection(COLLECTION).filterDate(start_date, end_date).select(BANDS)

    def _reduce(image):
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=scale, maxPixels=1e9, bestEffort=True
        )
        return ee.Feature(
            None,
            {
                "date": image.date().format("YYYY-MM-dd"),
                **{b: stats.get(b) for b in BANDS},
            },
        )

    feats = coll.map(_reduce).filter(ee.Filter.notNull(["temperature_2m"]))
    raw = [f["properties"] for f in feats.getInfo()["features"]]

    rows = []
    for r in raw:
        temp_c = r["temperature_2m"] - 273.15
        dew_c = r["dewpoint_temperature_2m"] - 273.15
        u, v = r["u_component_of_wind_10m"], r["v_component_of_wind_10m"]
        rows.append(
            {
                "date": r["date"],
                "temp_c": round(temp_c, 3),
                "precip_mm": round(r["total_precipitation_sum"] * 1000.0, 3),
                "humidity_pct": round(_relative_humidity(temp_c, dew_c), 2),
                "wind_speed_ms": round(math.sqrt(u * u + v * v), 3),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year-min", type=int, default=2000)
    parser.add_argument("--year-max", type=int, default=2012)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ee.Initialize(project=EE_PROJECT_ID)
    registry = json.loads(REGISTRY.read_text())

    start, end = f"{args.year_min}-01-01", f"{args.year_max}-12-31"
    done = skipped = failed = 0
    t0 = time.time()

    for rec in registry:
        out_path = OUT_DIR / f"{rec['field_id']}_weather_daily.csv"
        if out_path.exists():
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        try:
            rows = fetch_district_weather(district_geometry(rec["gaul_adm2"]), start, end)
        except Exception as e:
            print(f"  {rec['field_id']} {rec['district']}: {type(e).__name__} {str(e)[:110]}")
            failed += 1
            continue
        if not rows:
            failed += 1
            continue
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"])
            w.writeheader()
            w.writerows(rows)
        done += 1
        if done % 5 == 0:
            rate = (time.time() - t0) / done
            print(f"  {done} pulled ({skipped} skipped, {failed} failed) | {rate:.0f}s/district")

    print(f"\npulled {done}, skipped {skipped}, failed {failed} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
