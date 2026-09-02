"""
Builds the district-scale field registry: every district that has BOTH a real
data.gov.in yield label and a real administrative polygon in Earth Engine.

This replaces the 7 hand-drawn ~1 km boxes as the project's main dataset. The
boxes were representative squares centred on towns; these are the actual
district boundaries the yield figures are reported for, so the imagery and the
label finally describe the same piece of ground. That correspondence is the
whole point - RESULTS.md section 5 traces every failed result back to inputs
and labels describing different areas.

Matching is normalised (lowercase, letters only) rather than fuzzy: 414 of 535
districts match exactly that way, and a fuzzy matcher risks pairing a district
with its neighbour, which would silently attach the wrong yield to the wrong
imagery - a worse failure than dropping the 121 unmatched districts. Most
unmatched names are districts created after the 2015 boundary snapshot
(Amethi, Alirajpur, Agar Malwa) or transliteration variants (ANUGUL/Angul).

Run:
    python -m ingestion.district_fields --states "Punjab,Tamil Nadu,West Bengal,Andhra Pradesh"
"""

import argparse
import json
import re
from pathlib import Path

import ee
import pandas as pd

from ingestion.config import RAW_DIR

GAUL = "FAO/GAUL_SIMPLIFIED_500m/2015/level2"
EE_PROJECT_ID = "harvestwise-project"
OUT_PATH = RAW_DIR / "external" / "datagovin" / "district_registry.json"
YIELD_CSV = RAW_DIR / "external" / "datagovin" / "district_yield_rice.csv"

# Plausibility bounds for rice yield in t/ha. The source has ~1.2% clearly
# corrupt rows (e.g. Kolhapur 1997: 246,100 t on 1,100 ha = 224 t/ha), which
# are dropped rather than winsorised - a fabricated-looking label is worse
# than a smaller dataset.
MIN_YIELD, MAX_YIELD = 0.3, 12.0


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def load_labels(season: str = "Kharif") -> pd.DataFrame:
    df = pd.read_csv(YIELD_CSV)
    df = df[
        (df.yield_t_ha >= MIN_YIELD)
        & (df.yield_t_ha <= MAX_YIELD)
        & (df.season.str.strip() == season)
    ].copy()
    df["state"] = df.state.str.strip()
    df["district"] = df.district.str.strip()
    return df


def build_registry(states: list[str] | None, year_min: int, year_max: int, max_districts: int | None):
    ee.Initialize(project=EE_PROJECT_ID)

    labels = load_labels()
    labels = labels[(labels.year >= year_min) & (labels.year <= year_max)]
    if states:
        labels = labels[labels.state.isin(states)]

    fc = ee.FeatureCollection(GAUL).filter(ee.Filter.eq("ADM0_NAME", "India"))
    info = fc.select(["ADM1_NAME", "ADM2_NAME"]).getInfo()["features"]
    gaul_by_norm = {}
    for feat in info:
        p = feat["properties"]
        gaul_by_norm.setdefault(_norm(p["ADM2_NAME"]), (p["ADM1_NAME"], p["ADM2_NAME"]))

    registry = []
    for (state, district), grp in labels.groupby(["state", "district"]):
        key = _norm(district)
        if key not in gaul_by_norm:
            continue
        gaul_state, gaul_district = gaul_by_norm[key]
        registry.append(
            {
                "field_id": f"D{len(registry):04d}",
                "state": state,
                "district": district,
                "gaul_adm1": gaul_state,
                "gaul_adm2": gaul_district,
                "crop": "rice_district",
                "years": sorted(int(y) for y in grp.year.unique()),
                "yields_t_ha": {str(int(r.year)): float(r.yield_t_ha) for r in grp.itertuples()},
            }
        )
        if max_districts and len(registry) >= max_districts:
            break

    return registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", default="", help="Comma-separated state filter; empty = all India.")
    parser.add_argument("--year-min", type=int, default=2000)
    parser.add_argument("--year-max", type=int, default=2012, help="2000-2012 = clean Landsat 5 era.")
    parser.add_argument("--max-districts", type=int, default=None)
    args = parser.parse_args()

    states = [s.strip() for s in args.states.split(",") if s.strip()] or None
    registry = build_registry(states, args.year_min, args.year_max, args.max_districts)

    OUT_PATH.write_text(json.dumps(registry, indent=2))
    n_seasons = sum(len(r["years"]) for r in registry)
    print(f"districts matched : {len(registry)}")
    print(f"district-seasons  : {n_seasons}")
    if registry:
        ys = [y for r in registry for y in r["yields_t_ha"].values()]
        print(f"yield range       : {min(ys):.2f}-{max(ys):.2f} t/ha (mean {sum(ys)/len(ys):.2f})")
        print(f"states            : {sorted({r['state'] for r in registry})}")
    print(f"wrote -> {OUT_PATH}")


if __name__ == "__main__":
    main()
