"""
Experiment 8, step 2: the 1971-2000 Kharif rainfall climatological baseline.

WHY THIS WINDOW. The Experiment 8 pre-registration (section 3.4) fixes the
baseline at 1971-2000 because it shares ZERO years with the 2000-2012 analysis
panel. A normal computed from the panel's own years would contain information
about the very seasons it is used to explain; a strictly prior window cannot.
This is the control that makes `precip_anomaly_z` free of future-year exposure
by construction rather than by argument.

WHAT IS PULLED. For each study district and each year 1971-2000, the Kharif
window total precipitation - i.e. the district-polygon spatial mean of the
summed daily precipitation over 1 June to 30 November of that year. 30 values
per district. The normal is their mean; the scale is their standard deviation.

Only the seasonal TOTAL is retrieved, not 30 years of daily series: the
anomaly is defined on the seasonal total, so pulling ~5,500 daily rows per
district to then sum them would move the same arithmetic client-side at
roughly 180x the transfer cost. Where daily resolution IS needed - the four
intra-seasonal variables - it already exists on disk for 2000-2012 and is not
re-pulled.

Same source, same collection, same unit handling and the same district
polygons as ingestion/district_weather_pull.py, so the baseline and the panel
are measured by one instrument under one method. That is the property whose
absence made Experiment 7 not feasible.

    temperature/precip units: total_precipitation_sum is m/day -> x1000 = mm/day

Resumable: one JSON per district under data/raw/weather/climatology_1971_2000/,
existing files skipped.

Run:
    python -m ingestion.era5_climatology_pull
"""

import argparse
import json
import time
from pathlib import Path

import ee
import pandas as pd

from ingestion.district_env_pull import _resolve_geometry
from ingestion.landsat_fetch import EE_PROJECT_ID

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
PANEL_PATH = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
OUT_DIR = ROOT / "data" / "raw" / "weather" / "climatology_1971_2000"

COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
BAND = "total_precipitation_sum"
SCALE = 11132  # ERA5-Land native ~0.1 degree, matching district_weather_pull.py

BASE_YEAR_MIN = 1971
BASE_YEAR_MAX = 2000
KHARIF_START = (6, 1)   # 1 June
KHARIF_END = (11, 30)   # 30 November - the pre-registered window


def study_district_ids() -> list[str]:
    """The districts the Experiment 8 panel is built from: Kharif rice rows
    with both weather and satellite available, 2000-2012. Read from the
    existing panel rather than re-derived, so the two cannot drift apart."""
    df = pd.read_csv(PANEL_PATH)
    k = df[(df["season"] == "Kharif") & (df["weather_available"]) & (df["satellite_available"])]
    return sorted(k["district_id"].unique())


def kharif_totals(geom, year_min: int, year_max: int) -> dict[int, float]:
    """Server-side: one Kharif-window precipitation total per year, in mm.

    The whole 30-year sequence is computed in Earth Engine and returned in a
    single getInfo call per district - 31 round trips rather than 930."""
    years = ee.List.sequence(year_min, year_max)

    def one_year(y):
        y = ee.Number(y)
        start = ee.Date.fromYMD(y, KHARIF_START[0], KHARIF_START[1])
        end = ee.Date.fromYMD(y, KHARIF_END[0], KHARIF_END[1]).advance(1, "day")
        total_m = (
            ee.ImageCollection(COLLECTION)
            .filterDate(start, end)
            .select(BAND)
            .sum()
        )
        stat = total_m.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=SCALE,
            maxPixels=int(1e9),
            bestEffort=True,
        ).get(BAND)
        n_days = ee.ImageCollection(COLLECTION).filterDate(start, end).size()
        # null-safe: a district-year with no overlapping pixel returns None
        # rather than silently becoming 0. Never convert missing to zero.
        return ee.Algorithms.If(
            ee.Algorithms.IsEqual(stat, None),
            ee.Dictionary({"year": y, "precip_mm": None, "n_days": n_days}),
            ee.Dictionary({"year": y, "precip_mm": ee.Number(stat).multiply(1000.0), "n_days": n_days}),
        )

    raw = ee.List(years.map(one_year)).getInfo()
    return {int(r["year"]): (r["precip_mm"], int(r["n_days"])) for r in raw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year-min", type=int, default=BASE_YEAR_MIN)
    ap.add_argument("--year-max", type=int, default=BASE_YEAR_MAX)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ee.Initialize(project=EE_PROJECT_ID)

    reg = pd.read_csv(REGISTRY_PATH)
    reg = reg[reg["latitude"].notna()]
    wanted = set(study_district_ids())
    reg = reg[reg["district_id"].isin(wanted)]

    # Checked against the full matched frame, BEFORE --limit trims it for a
    # pilot run - otherwise a pilot reports every untouched district as
    # missing geometry, which is a coverage claim rather than a pilot result.
    missing = wanted - set(reg["district_id"])
    if missing:
        print(f"  WARNING - no registry geometry for: {sorted(missing)}")

    if args.limit:
        reg = reg.head(args.limit)
    print(f"study districts to pull: {len(reg)} (of {len(wanted)} in panel)")

    done = skipped = failed = 0
    t0 = time.time()
    for rec in reg.itertuples(index=False):
        out_path = OUT_DIR / f"{rec.district_id}_kharif_climatology.json"
        if out_path.exists():
            skipped += 1
            continue
        try:
            geom = _resolve_geometry(rec)
            totals = kharif_totals(geom, args.year_min, args.year_max)
        except Exception as exc:  # noqa: BLE001 - record and continue, never fabricate
            print(f"  FAIL {rec.district_id} {rec.district}: {type(exc).__name__}: {exc}")
            failed += 1
            continue

        payload = {
            "district_id": rec.district_id,
            "state": rec.state,
            "district": rec.district,
            "canonical_district_name": rec.canonical_district_name,
            "geometry_source": rec.geometry_source,
            "collection_id": COLLECTION,
            "band": BAND,
            "scale_m": SCALE,
            "unit": "mm (total_precipitation_sum m/day x 1000, summed over the window)",
            "window": "1 June - 30 November inclusive",
            "baseline_years": [args.year_min, args.year_max],
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kharif_total_mm": {str(y): v[0] for y, v in sorted(totals.items())},
            "days_in_window": {str(y): v[1] for y, v in sorted(totals.items())},
        }
        out_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        done += 1
        print(f"  {rec.district_id} {rec.district:16s} ok  ({done + skipped}/{len(reg)}, {time.time() - t0:.0f}s)")

    print(f"\ndone={done} skipped={skipped} failed={failed} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
