"""
Pulls Landsat NDVI/EVI/NDWI time series for every district in the registry
built by ingestion/district_fields.py.

**Resumable by design.** One CSV per district under
data/raw/satellite/districts/, and a district whose CSV already exists is
skipped. The full 417-district pull is ~10 hours of Earth Engine round trips,
and this project has already had one multi-hour background download die
part-way (the ERA5 backfill, exit code 4, discovered only because the file
count stopped moving). Restarting this script simply continues; nothing is
re-fetched and nothing is lost.

Scale note: reduceRegion runs at 100 m rather than Landsat's native 30 m. A
district is 10^3-10^4 km^2, so a 30 m reduction over the full polygon is both
far slower and pointless - the label it will be matched against is a single
district-wide average. 100 m keeps ~1000x more pixels than the label's own
resolution while making the pull tractable.

Run:
    python -m ingestion.district_landsat_pull --year-min 2000 --year-max 2012
    python -m ingestion.district_landsat_pull --limit 60      # pilot
"""

import argparse
import json
import time
from pathlib import Path

import ee

from ingestion.config import RAW_DIR
from ingestion.landsat_fetch import (
    EE_PROJECT_ID,
    cropland_mask_year,
    fetch_vegetation_indices,
    write_csv,
)

GAUL = "FAO/GAUL_SIMPLIFIED_500m/2015/level2"
REGISTRY = RAW_DIR / "external" / "datagovin" / "district_registry.json"
OUT_DIR = RAW_DIR / "satellite" / "districts"


def district_geometry(gaul_adm2: str) -> "ee.Geometry":
    return (
        ee.FeatureCollection(GAUL)
        .filter(ee.Filter.And(ee.Filter.eq("ADM0_NAME", "India"), ee.Filter.eq("ADM2_NAME", gaul_adm2)))
        .geometry()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year-min", type=int, default=2000)
    parser.add_argument("--year-max", type=int, default=2012)
    parser.add_argument("--limit", type=int, default=None, help="Stop after N districts (pilot runs).")
    parser.add_argument("--scale", type=int, default=100)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ee.Initialize(project=EE_PROJECT_ID)
    registry = json.loads(REGISTRY.read_text())

    start, end = f"{args.year_min}-01-01", f"{args.year_max}-12-31"
    # One mid-period cropland mask, reused for every district and every scene -
    # see cropland_mask_year() for why this is resolved once rather than per
    # image. Without it a district-wide NDVI average is dominated by land that
    # is not the crop the yield label describes.
    mask = cropland_mask_year((args.year_min + args.year_max) // 2)
    done = skipped = failed = 0
    t0 = time.time()

    for rec in registry:
        out_path = OUT_DIR / f"{rec['field_id']}_landsat.csv"
        if out_path.exists():
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break

        try:
            rows = fetch_vegetation_indices(
                district_geometry(rec["gaul_adm2"]), start, end, scale=args.scale, cropland_mask=mask
            )
        except Exception as e:  # EE errors are varied; keep going rather than losing the run
            print(f"  {rec['field_id']} {rec['district']}: {type(e).__name__} {str(e)[:110]}")
            failed += 1
            continue

        if not rows:
            print(f"  {rec['field_id']} {rec['district']}: no usable scenes")
            failed += 1
            continue

        write_csv(rows, out_path)
        done += 1
        if done % 5 == 0:
            rate = (time.time() - t0) / done
            remaining = (len(registry) - skipped - done) * rate / 3600
            print(
                f"  {done} pulled ({skipped} already had CSVs, {failed} failed) "
                f"| {rate:.0f}s/district | ~{remaining:.1f}h left"
            )

    print(f"\npulled {done}, skipped {skipped}, failed {failed} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
