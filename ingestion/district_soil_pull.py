"""
Static soil properties per district, for the NEW Southern India district
registry (data/metadata/district_registry.csv) - as opposed to
ingestion/soil_fetch_ee.py --districts, which serves the older, separate
417-district registry.

Uses the ISRIC SoilGrids REST API (no GEE, no auth) at each district's real
GAUL centroid, the same source and mechanism as ingestion/soil_fetch.py.
ingestion/soil_fetch_ee.py's own docstring documents that the REST endpoint
returned null for 5 of the project's 7 field centroids while Earth Engine
resolved 6 of 7 for the same points - so a genuine null here is expected for
some districts, and is recorded as missing, not filled with a neighbour's
value or a fabricated number. A district-scale Earth Engine soil pull
(ingestion/soil_fetch_ee.py --districts, generalized to this new registry)
is the documented follow-up for any district that comes back null here - not
run in this pass, to avoid contending for Earth Engine quota with the
concurrent weather/satellite pulls this same task launched.

Per Experiment 1 / Phase 5 of the district pipeline: soil is fetched and
stored SEPARATELY from weather/satellite, specifically so it can be included
or excluded from a model as an explicit experimental condition (soil-only
control vs weather+satellite vs full multimodal), never silently folded in as
an unrestricted input.

Run:
    python -m ingestion.district_soil_pull
"""

import csv
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OUT_PATH = ROOT / "data" / "raw" / "soil" / "southern_district_soil_properties.csv"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ["phh2o", "soc", "clay", "sand", "nitrogen"]
DEPTH = "0-5cm"


def fetch_soil_rest(lon: float, lat: float) -> dict:
    params = {"lon": lon, "lat": lat, "property": PROPERTIES, "depth": DEPTH, "value": "mean"}
    resp = requests.get(SOILGRIDS_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    row = {}
    for layer in data["properties"]["layers"]:
        prop_name = layer["name"]
        depths = layer["depths"]
        matching = next((d for d in depths if d["label"] == DEPTH), depths[0] if depths else None)
        row[prop_name] = matching["values"]["mean"] if matching else None
    return row


def main():
    df = pd.read_csv(REGISTRY_PATH)
    df = df[df["latitude"].notna()]

    rows, missing = [], []
    for rec in df.itertuples(index=False):
        try:
            vals = fetch_soil_rest(rec.longitude, rec.latitude)
        except Exception as e:
            print(f"  {rec.district_id} {rec.district}: {type(e).__name__} {str(e)[:100]}")
            missing.append(rec.district_id)
            continue
        if all(v is None for v in vals.values()):
            missing.append(rec.district_id)
            print(f"  {rec.district_id} {rec.district}: NULL from REST (all properties None)")
            continue
        rows.append({"district_id": rec.district_id, "district": rec.district, "state": rec.state,
                      "lon": rec.longitude, "lat": rec.latitude, **vals})
        time.sleep(0.3)  # be polite to the public REST endpoint

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["district_id", "district", "state", "lon", "lat", *PROPERTIES]
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} districts with real soil, {len(missing)} null/failed: {missing}")
    print(f"wrote -> {OUT_PATH}")


if __name__ == "__main__":
    main()
