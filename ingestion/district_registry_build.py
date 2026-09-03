"""
Builds data/metadata/district_registry.csv: one row per real district that
appears in the three Southern India official yield collections
(data/raw/external/official_yield/{andhra_pradesh,telangana,tamil_nadu}/),
matched to a real administrative boundary source (FAO GAUL) wherever a match
genuinely exists.

This is a NEW, separate registry from data/raw/external/datagovin/
district_registry.json (the older, Kharif-only, 2000-2012-scoped registry
built by ingestion/district_fields.py for a different, national dataset). It
does not modify or replace that file - see
experiments/SOUTHERN_INDIA_COMPATIBILITY_ANALYSIS.md section 4 for why the
two registries cover different, only partially-overlapping district sets.

Matching is NORMALIZED-NAME ONLY, plus a short, individually-justified alias
table for documented spelling/renaming differences (never a fuzzy matcher -
see ingestion/district_fields.py's own docstring for why: a fuzzy match risks
silently pairing a district with its neighbour). A district with no match,
and no documented alias, is written to the registry with an explicit
"no boundary source available" note rather than guessed or dropped.

GAUL data-quality finding (see ADMIN_BOUNDARY_NOTES below): FAO GAUL
"FAO/GAUL_SIMPLIFIED_500m/2015/level2" is named for its 2015 release/
publication year, not a verified 2015 administrative snapshot. Empirically,
it is missing several Tamil Nadu districts formed well before 2015
(Krishnagiri, 2004; Tiruppur, 2009), which means its actual boundary vintage
is older and inconsistent across features, not uniformly "as of 2015". It
also has no separate "Telangana" ADM1 entity at all - Telangana's 10
districts appear under ADM1_NAME="Andhra Pradesh", because Telangana's 2014
formation did not change any individual district's own boundary, only its
state-level grouping, and GAUL has not been updated with the new grouping.
Both facts are recorded per-row in administrative_boundary_notes, not
silently corrected.

Run:
    python -m ingestion.district_registry_build
"""

import csv
import re
from pathlib import Path

import ee
import pandas as pd

from ingestion.landsat_fetch import EE_PROJECT_ID

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "metadata" / "district_registry.csv"
YIELD_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "external" / "official_yield"
GAUL_COLLECTION = "FAO/GAUL_SIMPLIFIED_500m/2015/level2"
RETRIEVED_DATE = "2026-09-04"

# Documented aliases only - each one is a real, individually verifiable
# spelling variant or official rename, not a fuzzy guess. Key = normalized
# source district name, value = (GAUL ADM2_NAME to match, justification).
ALIASES = {
    "kadapa": ("Cuddapah", "Renamed from Cuddapah to Kadapa in 2011 (Andhra Pradesh govt notification); GAUL predates the rename."),
    "spsrnellore": ("Nellore", "Renamed from Nellore to Sri Potti Sriramulu (SPSR) Nellore in 2008; GAUL predates the rename."),
    "visakhapatanam": ("Vishakhapatnam", "Spelling/transliteration variant of the same district (source spells it 'Visakhapatanam', GAUL spells it 'Vishakhapatnam')."),
    "thenilgiris": ("Nilgiris", "Source includes the article 'The', GAUL's ADM2_NAME does not."),
    "sivagangai": ("Sivaganga", "Transliteration variant (trailing 'i')."),
    "tiruchirapalli": ("Tiruchchirappalli", "Transliteration variant (consonant doubling)."),
    "tiruvallur": ("Thiruvallur", "Transliteration variant ('Th' vs 'T')."),
    "tirunelveli": ("Tirunelveli Kattabo", "GAUL's own ADM2_NAME field is truncated at 20 characters to 'Tirunelveli Kattabo' (verified directly from the GAUL feature - not this script's truncation), apparently from 'Tirunelveli Kattabomman', a real alternate official name Tirunelveli district used c. 2008-2011."),
}

# Districts confirmed to have NO GAUL 2015 match under either the plain
# normalized name or a documented alias - all are real districts formed
# after GAUL's actual (inconsistent, pre-2015) boundary vintage. Listed here
# so the registry-build run below can assert this list didn't silently grow
# or shrink without review.
EXPECTED_NO_MATCH = {
    ("Tamil Nadu", "CHENGALPATTU"),
    ("Tamil Nadu", "KALLAKURICHI"),
    ("Tamil Nadu", "KRISHNAGIRI"),
    ("Tamil Nadu", "MAYILADUTHURAI"),
    ("Tamil Nadu", "RANIPET"),
    ("Tamil Nadu", "TENKASI"),
    ("Tamil Nadu", "TIRUPATHUR"),
    ("Tamil Nadu", "TIRUPPUR"),
    # Tiruvarur is a genuinely old district (since 1991) with no plausible
    # spelling variant in GAUL's 29-district Tamil Nadu list either - another
    # data point for this module's finding that GAUL's boundary vintage is
    # inconsistent, not uniformly "as of 2015".
    ("Tamil Nadu", "TIRUVARUR"),
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def _load_target_districts() -> pd.DataFrame:
    """One row per distinct (state, district) actually present in the three
    clean yield CSVs - the registry only needs to cover districts these
    collections actually use, not every district in India."""
    frames = []
    for region_dir in ("andhra_pradesh", "telangana", "tamil_nadu"):
        path = YIELD_DIR / region_dir / f"{region_dir}_apy_clean.csv"
        df = pd.read_csv(path)
        frames.append(df[["state", "district"]].drop_duplicates())
    combined = pd.concat(frames, ignore_index=True).drop_duplicates().sort_values(["state", "district"])
    return combined.reset_index(drop=True)


def build_registry() -> list[dict]:
    ee.Initialize(project=EE_PROJECT_ID)
    fc = ee.FeatureCollection(GAUL_COLLECTION).filter(ee.Filter.eq("ADM0_NAME", "India"))
    info = fc.select(["ADM1_NAME", "ADM2_NAME"]).getInfo()["features"]
    gaul_by_norm: dict[str, list[tuple[str, str]]] = {}
    for feat in info:
        p = feat["properties"]
        gaul_by_norm.setdefault(_norm(p["ADM2_NAME"]), []).append((p["ADM1_NAME"], p["ADM2_NAME"]))

    targets = _load_target_districts()
    rows = []
    unmatched = []

    for i, rec in enumerate(targets.itertuples(index=False)):
        state, district = rec.state, rec.district
        key = _norm(district)
        gaul_matches = gaul_by_norm.get(key)
        alias_note = ""

        if not gaul_matches and key in ALIASES:
            alias_gaul_name, justification = ALIASES[key]
            gaul_matches = gaul_by_norm.get(_norm(alias_gaul_name))
            alias_note = f"Matched via documented alias '{alias_gaul_name}': {justification}"

        district_id = f"SD{i:03d}"

        if not gaul_matches:
            unmatched.append((state, district))
            rows.append(
                {
                    "district_id": district_id,
                    "state": state,
                    "district": district,
                    "canonical_district_name": district.title(),
                    "geographic_level": "district",
                    "latitude": "",
                    "longitude": "",
                    "geometry_source": "NONE - no FAO GAUL 2015 match, no documented alias",
                    "geometry_version": "",
                    "administrative_boundary_notes": (
                        "No boundary source available. This district has no match in "
                        f"{GAUL_COLLECTION} under its plain name or any documented alias. "
                        "Most likely cause: the district was created after GAUL's actual "
                        "(inconsistent, not uniformly 2015) boundary vintage - see this "
                        "file's module docstring. Historical boundary reconstruction was "
                        "not attempted rather than guessed. Weather/satellite matching is "
                        "NOT POSSIBLE for this district until a real boundary source is "
                        "found."
                    ),
                }
            )
            continue

        gaul_adm1, gaul_adm2 = gaul_matches[0]
        geom = ee.FeatureCollection(GAUL_COLLECTION).filter(
            ee.Filter.And(ee.Filter.eq("ADM0_NAME", "India"), ee.Filter.eq("ADM2_NAME", gaul_adm2))
        ).geometry()
        centroid = geom.centroid(maxError=1).coordinates().getInfo()
        lon, lat = centroid[0], centroid[1]

        notes = []
        if alias_note:
            notes.append(alias_note)
        if gaul_adm1 != state:
            notes.append(
                f"GAUL's own ADM1_NAME for this district is '{gaul_adm1}', not '{state}'. "
                + (
                    "This district is one of Telangana's 10 districts; GAUL 2015 has no "
                    "separate 'Telangana' ADM1 entity, so it groups this district under the "
                    "pre-2014 undivided Andhra Pradesh. The district's own boundary is "
                    "unaffected by the 2014 state split (only the state-level grouping "
                    "changed), so the polygon itself is usable, but yield records for years "
                    "before June 2014 must not be described as contemporaneous Telangana-"
                    "state statistics on the strength of this geometry match - see "
                    "data/raw/external/official_yield/telangana/source_metadata.md."
                    if state == "Telangana"
                    else "Reason not otherwise documented; treat the state-level grouping with caution."
                )
            )
        if len(gaul_matches) > 1:
            notes.append(
                f"WARNING: {len(gaul_matches)} GAUL districts share this normalized name "
                f"({gaul_matches}); the first was used. Verify manually before relying on this row."
            )

        rows.append(
            {
                "district_id": district_id,
                "state": state,
                "district": district,
                "canonical_district_name": gaul_adm2,
                "geographic_level": "district",
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "geometry_source": f"FAO GAUL Simplified 500m, {GAUL_COLLECTION}, ADM2 polygon centroid (polygon itself used for spatial aggregation in the weather/satellite pipelines, not stored in this CSV)",
                "geometry_version": "GAUL 2015 release (see module docstring: boundary vintage is NOT reliably 2015 for every feature)",
                "administrative_boundary_notes": " | ".join(notes) if notes else "No known boundary issue for this district.",
            }
        )

    assert set(unmatched) == EXPECTED_NO_MATCH, (
        f"Unmatched-district set changed since this script was last reviewed.\n"
        f"New/changed: {set(unmatched) ^ EXPECTED_NO_MATCH}\n"
        f"Update EXPECTED_NO_MATCH (and re-check for a legitimate alias) before proceeding."
    )
    return rows


def main():
    rows = build_registry()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "district_id", "state", "district", "canonical_district_name", "geographic_level",
        "latitude", "longitude", "geometry_source", "geometry_version", "administrative_boundary_notes",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    matched = sum(1 for r in rows if r["latitude"] != "")
    print(f"{len(rows)} districts total, {matched} with a real GAUL match, {len(rows) - matched} with no boundary source")
    print(f"wrote -> {OUT_PATH}")


if __name__ == "__main__":
    main()
