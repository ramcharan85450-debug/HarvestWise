"""
Experiment 3, Phases 5 and 7 - Landsat sensor inventory and comparability probe.

WHY A PROBE IS NEEDED AT ALL
----------------------------
The project's stored satellite files
(data/raw/satellite/**/[SD|D]*_landsat.csv) have columns
date,mean_ndvi,mean_evi,mean_ndwi,cloud_cover_pct - and NO sensor column.
ingestion/landsat_fetch.py merges four collections (LT05, LE07, LC08, LC09)
into one ImageCollection and writes only the reduced per-scene means, so the
mission that produced each row was never recorded. Sensor identity therefore
cannot be read off the existing data, and it cannot be uniquely recovered
from the date either, because the missions overlap in time:

    Landsat 5  1984-2012        }  both cover 1999-2012 -> a 2005 scene
    Landsat 7  1999-2022        }  could be either mission
    Landsat 8  2013-            }  both cover 2021+ -> ambiguous
    Landsat 9  2021-            }

Guessing the sensor from the date is exactly what the task forbids. This
module instead RE-QUERIES Earth Engine per collection, so every count and
every index value below is attributed to a mission the archive itself names.

WHAT MAKES THE PHASE 7 COMPARISON VALID
---------------------------------------
Landsat 5 and Landsat 7 both imaged the SAME districts in the SAME years over
the SAME season windows during 1999-2012. That is a genuine natural
experiment: holding district, year and season fixed and varying only the
mission isolates the sensor effect, which is precisely the isolation
Experiment 2 could not achieve for geography vs time. Each district-year is
compared to ITSELF across the two sensors (a paired design), so the
comparison is not contaminated by which districts or which years happened to
be sampled.

Processing is deliberately IDENTICAL to the production pipeline - the same
_harmonized() band renaming, the same SR scale/offset, the same QA_PIXEL
cloud mask, the same cropland mask, the same reduceRegion mean - so any
difference measured here is a difference the real features also carry.
Nothing is corrected or harmonised; this module only measures.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import ee
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.district_env_pull import _resolve_geometry  # noqa: E402
from ingestion.district_season_calendar import season_window  # noqa: E402
from ingestion.landsat_fetch import (  # noqa: E402
    EE_PROJECT_ID,
    LANDSAT_COLLECTIONS,
    MAX_CLOUD_COVER_PCT,
    _harmonized,
    _with_indices,
    cropland_mask_year,
)

REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OUT_PATH = ROOT / "experiments" / "sensor_inventory.json"

SENSOR_NAME = {
    "LANDSAT/LT05/C02/T1_L2": "Landsat 5 TM",
    "LANDSAT/LE07/C02/T1_L2": "Landsat 7 ETM+",
    "LANDSAT/LC08/C02/T1_L2": "Landsat 8 OLI",
    "LANDSAT/LC09/C02/T1_L2": "Landsat 9 OLI-2",
}


def per_sensor_stats(geometry, start: str, end: str, mask, scale: int = 30) -> dict:
    """Per-collection scene count and mean NDVI/EVI/NDWI over one window.

    Identical processing to ingestion.landsat_fetch.fetch_vegetation_indices,
    except that each collection is queried SEPARATELY instead of merged, so
    the mission is known.
    """
    out = {}
    for cid in LANDSAT_COLLECTIONS:
        coll = (
            _harmonized(cid)
            .filterBounds(geometry)
            .filterDate(start, end)
            .filter(ee.Filter.lte("CLOUD_COVER", MAX_CLOUD_COVER_PCT))
            .map(_with_indices)
        )

        def _reduce(image):
            idx = image.select(["NDVI", "EVI", "NDWI"]).updateMask(mask)
            stats = idx.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geometry, scale=scale,
                maxPixels=1e9, bestEffort=True,
            )
            return ee.Feature(None, {
                "date": image.date().format("YYYY-MM-dd"),
                "ndvi": stats.get("NDVI"),
                "evi": stats.get("EVI"),
                "ndwi": stats.get("NDWI"),
            })

        feats = coll.map(_reduce).filter(ee.Filter.notNull(["ndvi"]))
        try:
            rows = [f["properties"] for f in feats.getInfo()["features"]]
        except Exception as e:  # quota / transient - recorded, never faked
            out[SENSOR_NAME[cid]] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            continue
        if not rows:
            out[SENSOR_NAME[cid]] = {"scenes": 0}
            continue
        df = pd.DataFrame(rows)
        out[SENSOR_NAME[cid]] = {
            "scenes": len(df),
            "ndvi_mean": float(df["ndvi"].mean()),
            "evi_mean": float(df["evi"].mean()),
            "ndwi_mean": float(df["ndwi"].mean()),
            "first_date": df["date"].min(),
            "last_date": df["date"].max(),
        }
    return out


def main():
    ee.Initialize(project=EE_PROJECT_ID)
    registry = pd.read_csv(REGISTRY_PATH)

    # A deliberately SMALL, balanced probe. Earth Engine is in restricted
    # (throttled) mode for this project, so this samples districts rather than
    # sweeping all 62 - and the report labels every number below as a sample.
    # Districts are taken in registry order (not chosen by result), 3 per
    # state, to avoid selecting cases that flatter the conclusion.
    plan = []
    for state, years, season in (
        ("Andhra Pradesh", [2002, 2005, 2008, 2011], "Kharif"),
        ("Telangana", [2002, 2005, 2008, 2011], "Kharif"),
        ("Tamil Nadu", [2019, 2024], "Whole Year"),
    ):
        sub = registry[(registry["state"] == state) & registry["latitude"].notna()]
        for _, rec in sub.head(3).iterrows():
            for y in years:
                plan.append((state, rec, y, season))

    results = []
    for i, (state, rec, year, season) in enumerate(plan, 1):
        start, cutoff = season_window(season, year)
        try:
            geom = _resolve_geometry(rec)
            mask = cropland_mask_year(year)
            stats = per_sensor_stats(geom, start.isoformat(), cutoff.isoformat(), mask)
        except Exception as e:
            stats = {"error": f"{type(e).__name__}: {str(e)[:150]}"}
        results.append({
            "state": state,
            "district_id": rec["district_id"],
            "district": rec["canonical_district_name"],
            "year": year,
            "season": season,
            "window_start": start.isoformat(),
            "window_cutoff": cutoff.isoformat(),
            "sensors": stats,
        })
        got = {k: v.get("scenes") for k, v in stats.items() if isinstance(v, dict)}
        print(f"[{i}/{len(plan)}] {state} {rec['canonical_district_name']} {year}: {got}", flush=True)
        time.sleep(0.5)

    OUT_PATH.write_text(json.dumps({
        "note": (
            "Sensor identity is NOT stored in the project's satellite CSVs; these counts come "
            "from re-querying each Landsat collection separately with processing identical to "
            "ingestion/landsat_fetch.py. This is a SAMPLE of districts, not a census."
        ),
        "collections": SENSOR_NAME,
        "max_cloud_cover_pct": MAX_CLOUD_COVER_PCT,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote -> {OUT_PATH}")


if __name__ == "__main__":
    main()
