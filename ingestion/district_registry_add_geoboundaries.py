"""
Extends data/metadata/district_registry.csv with a SECOND, clearly-labeled
boundary source for the 9 Tamil Nadu districts that ingestion/
district_registry_build.py could not match in FAO GAUL (CHENGALPATTU,
KALLAKURICHI, KRISHNAGIRI, MAYILADUTHURAI, RANIPET, TENKASI, TIRUPATHUR,
TIRUPPUR, TIRUVARUR - all real districts formed 2004-2021, after GAUL's own,
inconsistent boundary vintage - see district_registry_build.py's docstring).

Source: geoBoundaries (https://www.geoboundaries.org), India ADM2, ODbL 1.0
license. Confirmed via the geoBoundaries API metadata (not assumed):
boundaryYearRepresented = 2021, sourceDataUpdateDate = 2023-01-19,
underlying data from India's own Local Government Directory
(lgdirectory.gov.in, Ministry of Panchayati Raj) and Pathways Data Pvt Ltd.
This is the "internationally recognized administrative boundary dataset"
option named in the task that requested this recovery - not GAUL, not a
guess, and not silently blended with the GAUL-matched rows (see
`geometry_source` below, which names the source explicitly and differently
per row, on purpose).

Matching: same normalized-name-plus-documented-alias discipline as
district_registry_build.py - no fuzzy matching. Two aliases were needed:
"CHENGALPATTU" -> "Chengalputtu" (spelling variant) and "TIRUVARUR" ->
"Thiruvarur" (transliteration variant, same "Th" vs "T" pattern already
documented for Thiruvallur in the GAUL match). The other 7 matched on their
plain normalized name.

**These 9 districts' registry rows use a DIFFERENT boundary source than the
other 53 rows in this file.** Anyone joining across the full registry should
be aware final geometries are not from one uniform source - documented here
and in each row's geometry_source column rather than hidden by giving every
row the same-looking source label.

Run:
    python -m ingestion.district_registry_add_geoboundaries
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
GEOBOUNDARIES_PATH = ROOT / "data" / "metadata" / "boundary_sources" / "geoboundaries_IND_ADM2.geojson"
CACHE_DIR = ROOT / "data" / "metadata" / "boundary_sources" / "tn_districts_geoboundaries"
RETRIEVED_DATE = "2026-09-04"

ALIASES = {
    "chengalpattu": ("Chengalputtu", "Spelling variant of the same district (source spells it 'Chengalpattu', geoBoundaries spells it 'Chengalputtu')."),
    "tiruvarur": ("Thiruvarur", "Transliteration variant ('Th' vs 'T'), same pattern already documented for Thiruvallur in the GAUL-matched rows."),
}

TARGET_DISTRICTS = [
    "CHENGALPATTU", "KALLAKURICHI", "KRISHNAGIRI", "MAYILADUTHURAI",
    "RANIPET", "TENKASI", "TIRUPATHUR", "TIRUPPUR", "TIRUVARUR",
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def _centroid(coords) -> tuple[float, float]:
    """Simple mean-of-vertices centroid, same approximation method already
    used elsewhere in this project (ingestion/weather_fetch.py's
    _bbox_for_field, ingestion/soil_fetch.py's _centroid) - for the registry/
    documentation column only. The REAL polygon (cached per-district below)
    is what any future weather/satellite fetch must use for spatial
    aggregation, not this centroid."""
    pts = [pt for ring in coords for pt in ring]
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def main():
    data = json.loads(GEOBOUNDARIES_PATH.read_text(encoding="utf-8"))
    by_norm = {_norm(f["properties"]["shapeName"]): f for f in data["features"]}

    registry_rows = list(csv.DictReader(open(REGISTRY_PATH, encoding="utf-8")))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    resolved, still_missing = [], []
    for row in registry_rows:
        if row["state"] != "Tamil Nadu" or row["district"] not in TARGET_DISTRICTS:
            continue
        if row["latitude"]:
            continue  # already has a boundary (shouldn't happen for these 9, but don't overwrite if so)

        key = _norm(row["district"])
        feat, alias_note = by_norm.get(key), ""
        if feat is None and key in ALIASES:
            gb_name, justification = ALIASES[key]
            feat = by_norm.get(_norm(gb_name))
            alias_note = f"Matched via documented alias '{gb_name}': {justification}"

        if feat is None:
            still_missing.append(row["district"])
            continue

        lon, lat = _centroid(feat["geometry"]["coordinates"])
        cache_path = CACHE_DIR / f"{row['district_id']}_geoboundaries.geojson"
        cache_path.write_text(json.dumps(feat), encoding="utf-8")

        row["canonical_district_name"] = feat["properties"]["shapeName"]
        row["latitude"] = round(lat, 5)
        row["longitude"] = round(lon, 5)
        row["geometry_source"] = (
            f"geoBoundaries (geoboundaries.org), India ADM2, boundaryYearRepresented=2021, "
            f"sourceDataUpdateDate=2023-01-19, underlying source: India Local Government Directory "
            f"(lgdirectory.gov.in) + Pathways Data Pvt Ltd, license ODbL 1.0, retrieved {RETRIEVED_DATE}. "
            f"NOT the same source as this registry's GAUL-matched rows - see this row's "
            f"administrative_boundary_notes. Cached feature: {cache_path.relative_to(ROOT)}"
        )
        row["geometry_version"] = "geoBoundaries 2021-represented release (build 2023-12-12), shapeID=" + feat["properties"]["shapeID"]
        notes = [
            "Resolved via geoBoundaries (an internationally-recognized open administrative boundary "
            "dataset, not FAO GAUL) because this district was formed after GAUL's boundary vintage "
            "and has no GAUL entry (see district_registry_build.py's own docstring on this)."
        ]
        if alias_note:
            notes.append(alias_note)
        row["administrative_boundary_notes"] = " | ".join(notes)
        resolved.append(row["district"])

    with open(REGISTRY_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=registry_rows[0].keys())
        w.writeheader()
        w.writerows(registry_rows)

    print(f"Resolved via geoBoundaries: {resolved}")
    print(f"Still no boundary source: {still_missing}")
    print(f"Updated -> {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
