"""
Experiment 4, Phase A - satellite fetch WITH per-row provenance.

WHY A NEW MODULE INSTEAD OF EDITING THE EXISTING WRITER
-------------------------------------------------------
`ingestion/landsat_fetch.py:landsat_collection()` MERGES four Landsat
collections into one ImageCollection before reducing, and its `write_csv`
emits only `date, mean_ndvi, mean_evi, mean_ndwi, cloud_cover_pct`. The
originating mission is therefore discarded, which is exactly the gap
Experiment 3 documented.

Recording provenance requires querying each collection SEPARATELY, which is a
different query shape - not a column added to the existing one. Rather than
change the merged-collection code path (which Experiments 1-3 depend on for
their reported numbers), this module implements the per-collection path and
writes to a NEW directory:

    data/raw/satellite/southern_districts_provenance/{district_id}_landsat_prov.csv

The legacy files under `southern_districts/` are left byte-identical, so every
previously reported metric remains reproducible. Nothing here is a
"harmonization" or a correction: the processing is deliberately IDENTICAL to
the production pipeline (same `_harmonized()` band renaming, same SR scale and
offset, same QA_PIXEL cloud mask, same cropland mask, same `scale=100`
district reduction), so a row produced here is directly comparable to the
legacy row for the same scene - it simply also knows which satellite took it.

PROVENANCE FIELDS, AND WHY NONE OF THEM IS GUESSED
--------------------------------------------------
Every field below is read from the Earth Engine archive itself:

  collection_id        the EE collection the scene was drawn from
  sensor_name          fixed mapping from collection_id (not from the year)
  satellite_platform   likewise
  observation_year     parsed from the scene's own timestamp
  composite_start_date }  the requested fetch window. NOTE: this pipeline does
  composite_end_date   }  NOT composite - each row is ONE scene - so these
                          bound the window the scene was drawn from rather
                          than describing a temporal composite.
  image_count          1 by construction (one row = one scene), recorded
                       explicitly so the absence of compositing is legible
                       rather than implied.
  valid_pixel_count    count of unmasked cropland pixels actually reduced,
                       from the same reduceRegion call as the mean (no extra
                       query, no estimate).
  district_cropland_pixels  the district's total cropland pixel count at the
                       same scale, measured once per district.
  coverage_fraction    valid_pixel_count / district_cropland_pixels.

`sensor_name = MULTI_SENSOR` never occurs in this module, because each row is
sourced from exactly one collection. That value is reserved for the legacy
rows, which genuinely cannot be attributed (see the backfill script).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import ee
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.district_env_pull import _resolve_geometry  # noqa: E402
from ingestion.landsat_fetch import (  # noqa: E402
    EE_PROJECT_ID,
    LANDSAT_COLLECTIONS,
    MAX_CLOUD_COVER_PCT,
    _harmonized,
    _with_indices,
    cropland_mask_year,
)

REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OUT_DIR = ROOT / "data" / "raw" / "satellite" / "southern_districts_provenance"
LOG_PATH = ROOT / "data" / "raw" / "satellite" / "provenance_fetch_log.json"

# collection_id -> (sensor_name, satellite_platform). A fixed property of the
# collection, never inferred from the observation year.
SENSOR_META = {
    "LANDSAT/LT05/C02/T1_L2": ("Landsat 5 TM", "LANDSAT_5"),
    "LANDSAT/LE07/C02/T1_L2": ("Landsat 7 ETM+", "LANDSAT_7"),
    "LANDSAT/LC08/C02/T1_L2": ("Landsat 8 OLI", "LANDSAT_8"),
    "LANDSAT/LC09/C02/T1_L2": ("Landsat 9 OLI-2", "LANDSAT_9"),
}

FIELDNAMES = [
    "date", "mean_ndvi", "mean_evi", "mean_ndwi", "cloud_cover_pct",
    "collection_id", "sensor_name", "satellite_platform", "observation_year",
    "composite_start_date", "composite_end_date", "image_count",
    "valid_pixel_count", "district_cropland_pixels", "coverage_fraction",
]

SCALE = 100  # identical to ingestion/district_env_pull.pull_satellite


def _cropland_pixel_count(geometry, mask, scale: int = SCALE) -> float | None:
    """Total cropland pixels in the district, so coverage_fraction has a real
    denominator instead of an assumed one."""
    try:
        v = mask.rename("crop").updateMask(mask).reduceRegion(
            reducer=ee.Reducer.count(), geometry=geometry, scale=scale,
            maxPixels=1e9, bestEffort=True,
        ).get("crop")
        return float(ee.Number(v).getInfo())
    except Exception:
        return None


def fetch_with_provenance(geometry, start: str, end: str, mask, denom: float | None,
                          scale: int = SCALE) -> tuple[list[dict], dict]:
    """Per-scene indices for each collection separately, tagged with the
    collection that produced them. Returns (rows, per-collection status)."""
    rows: list[dict] = []
    status: dict = {}

    for cid in LANDSAT_COLLECTIONS:
        sensor_name, platform = SENSOR_META[cid]
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
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                geometry=geometry, scale=scale, maxPixels=1e9, bestEffort=True,
            )
            return ee.Feature(None, {
                "date": image.date().format("YYYY-MM-dd"),
                "mean_ndvi": stats.get("NDVI_mean"),
                "mean_evi": stats.get("EVI_mean"),
                "mean_ndwi": stats.get("NDWI_mean"),
                "valid_pixel_count": stats.get("NDVI_count"),
                "cloud_cover_pct": image.get("CLOUD_COVER"),
            })

        try:
            feats = coll.map(_reduce).filter(ee.Filter.notNull(["mean_ndvi"]))
            got = [f["properties"] for f in feats.getInfo()["features"]]
            status[cid] = {"outcome": "OK", "scenes": len(got)}
        except Exception as e:
            # Distinguish a real access/quota failure from a genuinely empty
            # collection - A5 requires these be reported separately.
            status[cid] = {"outcome": "EARTH_ENGINE_ACCESS_FAILURE",
                           "error": f"{type(e).__name__}: {str(e)[:160]}"}
            continue

        if not got:
            status[cid]["outcome"] = "NO_SATELLITE_OBSERVATION_EXISTS"

        for r in got:
            vpc = r.get("valid_pixel_count")
            rows.append({
                "date": r["date"],
                "mean_ndvi": r.get("mean_ndvi"),
                "mean_evi": r.get("mean_evi"),
                "mean_ndwi": r.get("mean_ndwi"),
                "cloud_cover_pct": r.get("cloud_cover_pct"),
                "collection_id": cid,
                "sensor_name": sensor_name,
                "satellite_platform": platform,
                "observation_year": int(r["date"][:4]),
                "composite_start_date": start,
                "composite_end_date": end,
                "image_count": 1,  # one row == one scene; no compositing
                "valid_pixel_count": vpc,
                "district_cropland_pixels": denom,
                "coverage_fraction": (
                    round(vpc / denom, 5) if (vpc is not None and denom) else None
                ),
            })
    return rows, status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", default="Tamil Nadu")
    ap.add_argument("--year-min", type=int, required=True)
    ap.add_argument("--year-max", type=int, required=True)
    ap.add_argument("--max-districts", type=int, default=None,
                    help="Stop after N districts fetched - avoids grinding against a quota.")
    ap.add_argument("--max-failures", type=int, default=5,
                    help="Abort after this many consecutive EE access failures.")
    args = ap.parse_args()

    ee.Initialize(project=EE_PROJECT_ID)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    reg = pd.read_csv(REGISTRY_PATH)
    reg = reg[reg["latitude"].notna()]
    states = [s.strip() for s in args.states.split(",") if s.strip()]
    if states:
        reg = reg[reg["state"].isin(states)]

    start, end = f"{args.year_min}-01-01", f"{args.year_max}-12-31"
    need_years = set(range(args.year_min, args.year_max + 1))

    log = {"windows": {"start": start, "end": end}, "scale": SCALE,
           "districts": [], "fetched": 0, "skipped": 0, "failed": 0,
           "aborted_early": False, "abort_reason": None}
    consecutive_failures = 0
    t0 = time.time()

    for rec in reg.itertuples(index=False):
        out_path = OUT_DIR / f"{rec.district_id}_landsat_prov.csv"

        # RESUMABILITY: skip only if this district already has every year of
        # the requested window, checked by reading the file - not by presence.
        if out_path.exists():
            try:
                have = pd.read_csv(out_path)
                if len(have) and need_years.issubset(set(have["observation_year"].unique())):
                    log["skipped"] += 1
                    log["districts"].append({"district_id": rec.district_id,
                                             "district": rec.canonical_district_name,
                                             "state": rec.state, "outcome": "ALREADY_COMPLETE"})
                    continue
            except Exception:
                pass  # unreadable/partial file -> re-fetch below

        if args.max_districts and log["fetched"] >= args.max_districts:
            log["aborted_early"] = True
            log["abort_reason"] = f"--max-districts {args.max_districts} reached"
            break

        try:
            geom = _resolve_geometry(rec)
            mask = cropland_mask_year((args.year_min + args.year_max) // 2)
            denom = _cropland_pixel_count(geom, mask)
            rows, status = fetch_with_provenance(geom, start, end, mask, denom)
        except Exception as e:
            log["failed"] += 1
            consecutive_failures += 1
            log["districts"].append({"district_id": rec.district_id,
                                     "district": rec.canonical_district_name,
                                     "state": rec.state,
                                     "outcome": "EARTH_ENGINE_ACCESS_FAILURE",
                                     "error": f"{type(e).__name__}: {str(e)[:160]}"})
            print(f"  FAIL {rec.district_id}: {type(e).__name__} {str(e)[:100]}", flush=True)
            if consecutive_failures >= args.max_failures:
                log["aborted_early"] = True
                log["abort_reason"] = (
                    f"{consecutive_failures} consecutive Earth Engine failures - stopping "
                    "safely rather than looping against a quota restriction"
                )
                break
            continue

        access_failed = any(v["outcome"] == "EARTH_ENGINE_ACCESS_FAILURE" for v in status.values())
        if rows:
            rows = sorted(rows, key=lambda r: (r["date"], r["collection_id"]))
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDNAMES)
                w.writeheader()
                w.writerows(rows)
            consecutive_failures = 0
            log["fetched"] += 1
            outcome = "FETCHED_PARTIAL_ACCESS_FAILURE" if access_failed else "FETCHED"
        else:
            outcome = ("EARTH_ENGINE_ACCESS_FAILURE" if access_failed
                       else "NO_SATELLITE_OBSERVATION_EXISTS")
            if access_failed:
                consecutive_failures += 1
                log["failed"] += 1
            else:
                consecutive_failures = 0

        by_sensor = {}
        for r in rows:
            by_sensor[r["sensor_name"]] = by_sensor.get(r["sensor_name"], 0) + 1
        log["districts"].append({
            "district_id": rec.district_id, "district": rec.canonical_district_name,
            "state": rec.state, "outcome": outcome, "scenes": len(rows),
            "scenes_by_sensor": by_sensor,
            "district_cropland_pixels": denom,
            "per_collection_status": status,
        })
        print(f"  {rec.district_id} {rec.canonical_district_name}: {outcome} "
              f"{len(rows)} scenes {by_sensor} | {(time.time()-t0)/60:.1f} min",
              flush=True)

        if consecutive_failures >= args.max_failures:
            log["aborted_early"] = True
            log["abort_reason"] = (
                f"{consecutive_failures} consecutive Earth Engine failures - stopping safely"
            )
            break

    LOG_PATH.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"\nfetched={log['fetched']} skipped={log['skipped']} failed={log['failed']} "
          f"aborted_early={log['aborted_early']}")
    if log["abort_reason"]:
        print(f"abort reason: {log['abort_reason']}")
    print(f"log -> {LOG_PATH}")


if __name__ == "__main__":
    main()
