"""
Soil properties from ISRIC SoilGrids via Earth Engine.

Replaces ingestion/soil_fetch.py's REST path, which was silently returning
nulls: of the project's 7 fields, only F002 and F003 ever got real values.
The other five - including Punjab, West Bengal and Andhra Pradesh - were being
filled by training/dataset.py's impute_missing_soil with the MEAN OF THE TWO
COIMBATORE FIELDS, so five fields in four states were all training on
Coimbatore soil. That is not a localized no-data pixel as previously assumed:
the REST endpoint returns HTTP 200 with every value null for points that Earth
Engine resolves fine, so the fault was in the query, not the coverage.

Via Earth Engine, 6 of the 7 fields resolve. F005 (Burdwan) still lands on a
no-data pixel and is handled by BUFFER_FALLBACK_M below.

Unit note - nitrogen needs rescaling, the rest do not. Measured against the
values the REST API did return:

    property   REST    Earth Engine    ratio
    phh2o        69              70    1.01
    clay        255             253    0.99
    sand        512             508    0.99
    soc         242             262    1.08
    nitrogen    216            2201   10.2

So the Earth Engine nitrogen band is on a 10x scale relative to the REST
values that training/dataset.py's SOIL_NORM constants were derived from.
Dividing by 10 keeps every previously-trained normalisation constant valid;
changing SOIL_NORM instead would silently invalidate existing checkpoints.

Run:
    python -m ingestion.soil_fetch_ee
"""

import argparse
import csv
import json

import ee

from ingestion.config import FIELDS, RAW_DIR
from ingestion.landsat_fetch import EE_PROJECT_ID

SOIL_DIR = RAW_DIR / "soil"
PROPERTIES = ["phh2o", "soc", "clay", "sand", "nitrogen"]
DEPTH = "0-5cm"

# Applied after reduction, per the unit note above.
SCALE_CORRECTION = {"nitrogen": 0.1}

# If a geometry lands entirely on no-data, retry against a buffered version.
# SoilGrids has genuine gaps (waterbodies, urban cores); widening the query is
# an honest way to get a real nearby value, unlike substituting another
# region's soil.
BUFFER_FALLBACK_M = [0, 2000, 10000]

SOIL_IMAGE = None


def soil_image() -> "ee.Image":
    global SOIL_IMAGE
    if SOIL_IMAGE is None:
        SOIL_IMAGE = ee.Image.cat(
            [
                ee.Image(f"projects/soilgrids-isric/{p}_mean").select(f"{p}_{DEPTH}_mean")
                for p in PROPERTIES
            ]
        )
    return SOIL_IMAGE


def fetch_soil(geometry, scale: int = 250) -> dict:
    """Mean soil properties over `geometry`, retrying with progressively larger
    buffers if the region is all no-data. Returns {} if every attempt fails,
    so the caller can record a genuine gap rather than a fabricated value."""
    geom = geometry if isinstance(geometry, ee.Geometry) else ee.Geometry.Polygon(geometry)
    img = soil_image()

    for buffer_m in BUFFER_FALLBACK_M:
        region = geom.buffer(buffer_m) if buffer_m else geom
        stats = img.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=scale, maxPixels=1e9, bestEffort=True
        ).getInfo()
        values = {p: stats.get(f"{p}_{DEPTH}_mean") for p in PROPERTIES}
        if all(v is not None for v in values.values()):
            return {
                p: round(v * SCALE_CORRECTION.get(p, 1.0), 2)
                for p, v in values.items()
            } | {"buffer_m": buffer_m}
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--districts", action="store_true", help="Fetch for the district registry instead of FIELDS.")
    args = parser.parse_args()

    ee.Initialize(project=EE_PROJECT_ID)

    if args.districts:
        from ingestion.district_landsat_pull import district_geometry

        registry = json.loads((RAW_DIR / "external" / "datagovin" / "district_registry.json").read_text())
        targets = [(r["field_id"], r["district"], district_geometry(r["gaul_adm2"])) for r in registry]
        out_path = SOIL_DIR / "district_soil_properties.csv"
    else:
        targets = [(f["field_id"], f["name"], f["geometry"]) for f in FIELDS]
        out_path = SOIL_DIR / "soil_properties_ee.csv"

    rows, missing = [], []
    for fid, name, geom in targets:
        vals = fetch_soil(geom)
        if not vals:
            missing.append(fid)
            print(f"  {fid} {name[:30]:<30} NO DATA at any buffer")
            continue
        rows.append({"field_id": fid, **{p: vals[p] for p in PROPERTIES}, "buffer_m": vals["buffer_m"]})
        if len(rows) % 25 == 0:
            print(f"  {len(rows)} fetched")

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["field_id", *PROPERTIES, "buffer_m"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} with real soil, {len(missing)} without {missing}")
    print(f"wrote -> {out_path}")


if __name__ == "__main__":
    main()
