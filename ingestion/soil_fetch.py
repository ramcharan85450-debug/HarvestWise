"""
Pulls static soil properties per field centroid from ISRIC SoilGrids (free,
no API key needed). Soil doesn't change week to week, so this is a one-time
lookup per field, not a time series.

Run:
    python -m ingestion.soil_fetch
"""

import csv

import requests

from ingestion.config import FIELDS, RAW_DIR

SOIL_DIR = RAW_DIR / "soil"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ["phh2o", "soc", "clay", "sand", "nitrogen"]
DEPTH = "0-5cm"


def _centroid(geometry: list) -> tuple[float, float]:
    lons = [pt[0] for ring in geometry for pt in ring]
    lats = [pt[1] for ring in geometry for pt in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def fetch_soil(field: dict) -> dict:
    lon, lat = _centroid(field["geometry"])
    params = {
        "lon": lon,
        "lat": lat,
        "property": PROPERTIES,
        "depth": DEPTH,
        "value": "mean",
    }
    resp = requests.get(SOILGRIDS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    row = {"field_id": field["field_id"], "lon": lon, "lat": lat}
    for layer in data["properties"]["layers"]:
        prop_name = layer["name"]
        depths = layer["depths"]
        matching = next((d for d in depths if d["label"] == DEPTH), depths[0] if depths else None)
        row[prop_name] = matching["values"]["mean"] if matching else None
    return row


def main():
    rows = [fetch_soil(field) for field in FIELDS]
    out_path = SOIL_DIR / "soil_properties.csv"
    fieldnames = list(rows[0].keys()) if rows else ["field_id"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
