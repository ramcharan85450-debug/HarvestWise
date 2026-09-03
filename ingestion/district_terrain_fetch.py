"""
Experiment 4, Phase B, Category 4 - static terrain covariates per district.

Source: NASA SRTM Digital Elevation Model, 30 m, via Earth Engine
(`USGS/SRTMGL1_003`). This is an authoritative, primary remote-sensing product,
not a redistributed or scraped copy.

Two covariates, both computed over the district's CROPLAND pixels rather than
the whole polygon, so they describe the land the rice is actually grown on
rather than including mountains and cities that no rice crop occupies:

    elevation_m_mean   mean SRTM elevation
    slope_deg_mean     mean slope, from ee.Terrain.slope on the same DEM

WHY THESE ARE COLLECTED, AND THE HAZARD THEY CARRY
---------------------------------------------------
They are candidate explanatory variables for Tamil Nadu's yield advantage -
delta and coastal districts sit low and flat, which is agronomically
associated with irrigated rice. They are NOT assumed to explain anything.

The hazard is the one this project already discovered in Experiment 1: a
STATIC per-district value is a location fingerprint. A model given elevation
can memorise which district it is looking at, exactly as it did with soil.
That is why Phase C2 makes a "static covariates only" control mandatory, and
why these are reported separately from the time-varying agricultural
covariates throughout.

Values are static per district (one row each), so they carry no year and
cannot encode future information.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import date
from pathlib import Path

import ee
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.district_env_pull import _resolve_geometry  # noqa: E402
from ingestion.landsat_fetch import EE_PROJECT_ID, cropland_mask_year  # noqa: E402

REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OUT_DIR = ROOT / "data" / "raw" / "external" / "district_covariates"
OUT_PATH = OUT_DIR / "district_terrain.csv"

DEM_ID = "USGS/SRTMGL1_003"
SOURCE_NAME = "NASA SRTM Digital Elevation 30m (USGS/SRTMGL1_003) via Google Earth Engine"
FIELDS = ["district_id", "state", "canonical_district_name", "elevation_m_mean",
          "slope_deg_mean", "cropland_pixels", "source_name", "source_url",
          "retrieved_date", "status"]


def main():
    ee.Initialize(project=EE_PROJECT_ID)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    reg = pd.read_csv(REGISTRY_PATH)
    reg = reg[reg["latitude"].notna()]

    existing = {}
    if OUT_PATH.exists():
        for r in pd.read_csv(OUT_PATH).to_dict("records"):
            existing[r["district_id"]] = r

    dem = ee.Image(DEM_ID).select("elevation")
    slope = ee.Terrain.slope(dem).rename("slope")
    # 2006 is the midpoint of the 2000-2012 analysis window.
    mask = cropland_mask_year(2006)
    stack = dem.addBands(slope).updateMask(mask)

    rows, t0 = [], time.time()
    for i, rec in enumerate(reg.itertuples(index=False), 1):
        if rec.district_id in existing and existing[rec.district_id].get("status") == "OK":
            rows.append(existing[rec.district_id])
            continue
        try:
            geom = _resolve_geometry(rec)
            stats = stack.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                geometry=geom, scale=100, maxPixels=1e9, bestEffort=True,
            ).getInfo()
            rows.append({
                "district_id": rec.district_id, "state": rec.state,
                "canonical_district_name": rec.canonical_district_name,
                "elevation_m_mean": stats.get("elevation_mean"),
                "slope_deg_mean": stats.get("slope_mean"),
                "cropland_pixels": stats.get("elevation_count"),
                "source_name": SOURCE_NAME, "source_url": f"https://developers.google.com/earth-engine/datasets/catalog/{DEM_ID.replace('/', '_')}",
                "retrieved_date": date.today().isoformat(),
                "status": "OK" if stats.get("elevation_mean") is not None else "NULL_RESULT",
            })
        except Exception as e:
            rows.append({
                "district_id": rec.district_id, "state": rec.state,
                "canonical_district_name": rec.canonical_district_name,
                "elevation_m_mean": None, "slope_deg_mean": None, "cropland_pixels": None,
                "source_name": SOURCE_NAME, "source_url": "",
                "retrieved_date": date.today().isoformat(),
                "status": f"FAILED: {type(e).__name__}: {str(e)[:120]}",
            })
        if i % 10 == 0:
            print(f"  {i}/{len(reg)} | {(time.time()-t0)/60:.1f} min", flush=True)

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in FIELDS})

    ok = sum(1 for r in rows if r.get("status") == "OK")
    print(f"\n{ok}/{len(rows)} districts resolved -> {OUT_PATH}")
    df = pd.DataFrame(rows)
    if ok:
        print(df[df.status == "OK"].groupby("state")[["elevation_m_mean", "slope_deg_mean"]].mean())


if __name__ == "__main__":
    main()
