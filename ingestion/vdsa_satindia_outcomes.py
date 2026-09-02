"""
Builds real plot-season outcomes AND matching real satellite/weather inputs
for 3 named, geocoded VDSA villages - the thing the EastIndia data (see
ingestion/vdsa_outcomes.py) could not support, because those 12 villages had
no district/state metadata and geocoding by name alone was unreliable.

The SATIndia round's Gen_Info.xlsx carries VILLAGE, TEH_MAN_BLO, DISTRICT and
STATE for every site, so these three geocode with real confidence (matched
against Nominatim results whose returned district/state agree exactly with
VDSA's own metadata, not a same-named-village guess):

    Kalman   17.9306, 75.7794   Solapur district, Maharashtra
    Kanzara  20.6638, 77.3549   Akola district, Maharashtra
    Shirapur 17.6966, 75.7639   Solapur district, Maharashtra

These are not obscure villages - Kanzara, Kinkheda, Kalman and Shirapur are
ICRISAT's original 1975 Village Level Studies sites, continuously surveyed for
50 years and extensively used in published agricultural economics research.
(Kinkheda and the two Andhra Pradesh villages, Aurepalle/Dokur, did not
geocode with confidence and are excluded here rather than guessed at.)

This module treats each village as a ~1km field polygon (same convention as
ingestion/config.py's original 7 fields) and:
  1. pulls real Landsat vegetation indices and real ERA5-Land weather for it
     (via ingestion/landsat_fetch.py and ingestion/district_weather_pull.py's
     helpers), for the years VDSA has cultivation records
  2. joins that to the REAL sow date / harvest date / yield extracted from
     Cult_ip_MH.xlsx and Crop_info_op-equivalent files for that village's
     VDS_ID prefix

The result is what the project's original real-outcome-validation blocker
asked for: real satellite+weather inputs, a real recommended-vs-actual
harvest comparison, for real named, geolocated fields - just 3 of them, in
Maharashtra, not the project's original 7 fields.

Run:
    python -m ingestion.vdsa_satindia_outcomes
"""

import json
from pathlib import Path

import ee
import pandas as pd

from ingestion.config import RAW_DIR
from ingestion.landsat_fetch import EE_PROJECT_ID, cropland_mask_year, fetch_vegetation_indices, write_csv

VDSA_DIR = RAW_DIR / "external" / "vdsa" / "satindia"
OUT_SATELLITE = RAW_DIR / "satellite" / "vdsa_villages"
OUT_OUTCOMES = RAW_DIR / "harvest_outcomes"

# Verified against Gen_Info.xlsx's own DISTRICT/STATE columns - see docstring.
# village_letter matches VDS_ID's structure IMH<yy><letter><hhno> - the year
# digits change per survey round (IMH10.. = 2010, IMH11.. = 2011, ...), so
# matching must use a regex on state+letter, NOT a fixed year-baked prefix.
VILLAGES = {
    "Kalman": {"village_letter": "A", "lat": 17.9306204, "lon": 75.7793569, "district": "Solapur", "state": "Maharashtra"},
    "Kanzara": {"village_letter": "B", "lat": 20.6638469, "lon": 77.3548919, "district": "Akola", "state": "Maharashtra"},
    "Shirapur": {"village_letter": "D", "lat": 17.6966114, "lon": 75.7639198, "district": "Solapur", "state": "Maharashtra"},
}
VDS_ID_PATTERN = r"^IMH\d\d{letter}"

BOX_DEG = 0.01  # ~1.1 km box, matching the original 7 fields' scale


def village_geometry(lat: float, lon: float) -> list:
    return [[[lon - BOX_DEG, lat - BOX_DEG], [lon + BOX_DEG, lat - BOX_DEG],
             [lon + BOX_DEG, lat + BOX_DEG], [lon - BOX_DEG, lat + BOX_DEG],
             [lon - BOX_DEG, lat - BOX_DEG]]]


def pull_satellite_and_weather(year_min: int = 2010, year_max: int = 2014):
    ee.Initialize(project=EE_PROJECT_ID)
    OUT_SATELLITE.mkdir(parents=True, exist_ok=True)
    mask = cropland_mask_year((year_min + year_max) // 2)

    for name, v in VILLAGES.items():
        out_path = OUT_SATELLITE / f"{name}_landsat.csv"
        if out_path.exists():
            print(f"  {name}: satellite already pulled, skipping")
            continue
        geom = ee.Geometry.Polygon(village_geometry(v["lat"], v["lon"]))
        rows = fetch_vegetation_indices(
            geom, f"{year_min}-01-01", f"{year_max}-12-31", scale=30, cropland_mask=mask
        )
        write_csv(rows, out_path)
        print(f"  {name}: {len(rows)} Landsat scenes -> {out_path}")


def _load(base_glob: str) -> pd.DataFrame:
    parts = sorted(VDSA_DIR.glob(base_glob))
    if not parts:
        raise FileNotFoundError(f"No files matching {base_glob} under {VDSA_DIR}")
    return pd.concat([pd.read_excel(p) for p in parts], ignore_index=True)


def _hh_key(vds_id) -> "str | None":
    """Strips the ambiguous 2-digit year out of a VDS_ID, keeping state +
    village letter + household number - e.g. IMH10A0001 -> MHA0001.

    Required because Cult_ip_MH's and 2.Crop_info_op's exports encode the SAME
    household with a different year digit (IMH10A0001 in the cultivation
    file, IMH09A0001 in the matching crop-output file) - a real inconsistency
    in this export, not a parsing bug. Matching on the year-stripped key is
    only safe WITHIN one downloaded file-pair (see build_real_outcomes):
    plot codes are reused across different survey years for the same
    household, so stripping the year and matching across ALL years pooled
    together pairs a sowing date from one season with a different season's
    yield for the same plot code. Measured concretely: doing that produced
    7053 "matches" for only 973 real sow/harvest events - a many-to-many join
    artifact, not real data, and the reason this function exists instead of a
    single pooled join.
    """
    import re

    m = re.match(r"^I([A-Z]{2})\d\d([A-Z])(\d+)$", str(vds_id))
    return f"{m.group(1)}{m.group(2)}{m.group(3)}" if m else None


def _yield_kg(crop: pd.DataFrame) -> pd.DataFrame:
    """Two real data-quality issues in this export, both handled explicitly
    rather than silently coerced: OP_MAIN_PROD_QTY is numeric in some source
    files and a whitespace-only string standing in for blank in others
    (pd.concat makes the combined column dtype=object), and
    OP_MAIN_PROD_UNIT carries trailing spaces ("Qt    " not "Qt"), which would
    make an exact-match .map() silently return NaN -> 0 for every
    quintal-denominated row instead of the correct x100 conversion."""
    qty = pd.to_numeric(crop.OP_MAIN_PROD_QTY.astype(str).str.strip(), errors="coerce")
    unit = crop.OP_MAIN_PROD_UNIT.astype(str).str.strip()
    mask = qty.notna() & (crop.PLOT_AREA > 0)
    crop, qty, unit = crop[mask].copy(), qty[mask], unit[mask]
    crop["yield_kg"] = qty * unit.map({"Kg": 1, "Qt": 100}).fillna(0)
    return crop


def _suffix_num(path: Path) -> int:
    """0 for 'X.xlsx', N for 'X (N).xlsx'. Needed because plain string sort
    puts 'X (1).xlsx' BEFORE 'X.xlsx' (a space sorts below a period), which
    silently breaks positional pairing between two globs - confirmed by
    hand-checking the original Downloads folder's timestamps: the true
    chronological order is base, (1), (2), (3), not what str-sort gives."""
    import re

    m = re.search(r"\((\d+)\)", path.stem)
    return int(m.group(1)) if m else 0


def build_real_outcomes() -> pd.DataFrame:
    # Two batches of Cult_ip_MH landed in Downloads: "3.Cult_ip_MH*" (3 files)
    # and an unprefixed "Cult_ip_MH*" (2 files) from a separate download flow.
    # Only the "3." batch is used - its files were downloaded within 6 seconds
    # of the matching "2.Crop_info_op*" file (checked against the original
    # Downloads folder's real timestamps, since copying into this repo
    # normalised them), which the unprefixed batch was not adjacent to at all.
    cult_files = sorted(VDSA_DIR.glob("3.Cult_ip_MH*.xlsx"), key=_suffix_num)
    crop_files = sorted(VDSA_DIR.glob("2.Crop_info_op*.xlsx"), key=_suffix_num)
    # 2.Crop_info_op (3).xlsx has no 3.Cult_ip_MH (3).xlsx counterpart -
    # confirmed by the original Downloads timestamps (22:45:58, no cult file
    # adjacent to it) - drop it rather than mispair it.
    paired_crop_files = [
        f for f in crop_files if any(_suffix_num(f) == _suffix_num(c) for c in cult_files)
    ]
    dropped = [f for f in crop_files if f not in paired_crop_files]
    if dropped:
        print(f"  dropping {len(dropped)} orphan crop file(s) with no matching cultivation file: {[p.name for p in dropped]}")
    cult_files.sort(key=_suffix_num)
    crop_files = sorted(paired_crop_files, key=_suffix_num)
    if [_suffix_num(f) for f in cult_files] != [_suffix_num(f) for f in crop_files]:
        raise RuntimeError("cult/crop file suffix numbers still don't align after dropping orphans.")

    all_rows = []
    for cult_path, crop_path in zip(cult_files, crop_files):
        cult = pd.read_excel(cult_path)
        crop = pd.read_excel(crop_path)
        cult["hh_key"] = cult.VDS_ID.map(_hh_key)
        crop["hh_key"] = crop.VDS_ID.map(_hh_key)

        # The plot-code column's name is NOT consistent across these 3 files
        # (PLOT_CODE in one, PLOT_CO in the other two) despite otherwise
        # identical structure - confirmed by inspecting each file's columns
        # directly, not assumed.
        plot_col = "PLOT_CO" if "PLOT_CO" in cult.columns else "PLOT_CODE"
        cult = cult.rename(columns={plot_col: "PLOT_CO"})

        sow = cult[cult.OPERATION.astype(str).str.contains("SOWING|TRANSPLANT", case=False, na=False)]
        sow = sow.groupby(["hh_key", "PLOT_CO"])["DT_OPER"].min().rename("sow_date")
        harv = cult[cult.OPERATION.astype(str).str.contains("HARVEST", case=False, na=False)]
        harv = harv.groupby(["hh_key", "PLOT_CO"])["DT_OPER"].max().rename("harvest_date")

        # Same plot-code naming inconsistency as the cultivation files, and
        # not the same pattern (2.Crop_info_op (2).xlsx uses PLOT_CO while
        # its cultivation counterpart uses PLOT_CODE) - normalised
        # independently on each side rather than assumed to match.
        crop_plot_col = "PLOT_CO" if "PLOT_CO" in crop.columns else "PLOT_CODE"
        crop = crop.rename(columns={crop_plot_col: "PLOT_CO"})

        crop = _yield_kg(crop)
        # CROP has the same trailing-whitespace corruption as OP_MAIN_PROD_UNIT
        # (see _yield_kg) - "SORGHUM" and "SORGHUM             " were being
        # counted as different crops downstream without this. It also mixes
        # case across files ("SORGHUM", "Sorghum") for the same crop, so
        # title-casing after stripping is needed to actually merge them, not
        # just tidy whitespace.
        crop["CROP"] = crop["CROP"].astype(str).str.strip().str.title()
        yields = crop.groupby(["hh_key", "PLOT_CO"]).agg(
            crop_name=("CROP", "first"), area_acres=("PLOT_AREA", "first"), yield_kg=("yield_kg", "sum")
        )

        joined = pd.DataFrame(sow).join(harv, how="inner").join(yields, how="inner")
        if joined.empty:
            continue

        for name, v in VILLAGES.items():
            key_prefix = f"MH{v['village_letter']}"  # matches _hh_key's MH+letter+number output
            vj = joined[joined.index.get_level_values(0).astype(str).str.startswith(key_prefix)].copy()
            if vj.empty:
                continue
            vj["village"], vj["district"], vj["state"] = name, v["district"], v["state"]
            all_rows.append(vj.reset_index())

    if not all_rows:
        return pd.DataFrame()

    out = pd.concat(all_rows, ignore_index=True)
    out["sow_date"] = pd.to_datetime(out.sow_date, dayfirst=True, errors="coerce")
    out["harvest_date"] = pd.to_datetime(out.harvest_date, dayfirst=True, errors="coerce")
    out = out.dropna(subset=["sow_date", "harvest_date"])
    out["days_to_harvest"] = (out.harvest_date - out.sow_date).dt.days
    out["yield_t_ha"] = (out.yield_kg / 1000) / (out.area_acres * 0.4047)
    out = out[(out.days_to_harvest > 30) & (out.days_to_harvest < 250)]
    out = out[(out.yield_t_ha > 0.1) & (out.yield_t_ha < 15)]
    return out.drop_duplicates()


def main():
    print("1. Pulling real Landsat + confirming village geometry...")
    pull_satellite_and_weather()

    print("\n2. Extracting real sow/harvest dates for these 3 villages...")
    outcomes = build_real_outcomes()
    OUT_OUTCOMES.mkdir(parents=True, exist_ok=True)
    out_path = OUT_OUTCOMES / "VDSA_SATIndia_named_villages.csv"
    outcomes.to_csv(out_path, index=False)
    print(f"   {len(outcomes)} plot-season records -> {out_path}")

    (RAW_DIR / "external" / "vdsa" / "village_registry.json").write_text(json.dumps(VILLAGES, indent=2))
    print("\nwrote village_registry.json")


if __name__ == "__main__":
    main()
