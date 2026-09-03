"""
Extracts Tamil Nadu district-level Rice APY records for the years that
OVERLAP Andhra Pradesh and Telangana (2000-2012, Kharif), from the same
official data.gov.in resource already used for AP and Telangana.

WHY THIS EXISTS (Experiment 3, Strategy A)
------------------------------------------
Experiment 2 established that region, era and season label were perfectly
confounded: AP/Telangana supplied only 1999-2012 Kharif/Rabi, Tamil Nadu only
2019/2024 Whole Year. Zero overlapping years, zero overlapping seasons. That
made it impossible to say whether Tamil Nadu's failure was geographic,
temporal, or seasonal.

This module collects the data that breaks that confound. It does NOT invent
or interpolate anything: the records come from the SAME national resource
(35be999b-0208-4354-b557-f6ca9a5355de, GoI Ministry of Agriculture and
Farmers Welfare via data.gov.in) that already supplied every Andhra Pradesh
and Telangana row, and that file was already downloaded and on disk at
data/raw/external/datagovin/district_yield_rice.csv. Tamil Nadu rows were
simply never extracted from it, because the earlier Tamil Nadu collection
targeted the TN DES Season and Crop Reports (2019/2024) instead.

Because the source, the fetch code, the unit evidence and the derivation
(yield = production / area) are all IDENTICAL to the AP and Telangana path,
the new rows are directly comparable to them - which is the entire point.

WHAT IS AND IS NOT WRITTEN
--------------------------
Written: a new clean CSV under a NEW directory
(data/raw/external/official_yield/tamil_nadu_overlap/). Nothing that
Experiment 1 or Experiment 2 reads is modified. In particular the existing
tamil_nadu/tamil_nadu_apy_clean.csv (the 2019/2024 DES rows) is left exactly
as it is, and the two files are kept SEPARATE rather than merged, so every
row's provenance stays traceable to its own source and retrieval.

DISTRICT NAME ALIASES
---------------------
Five of the 31 district names in the national resource differ in spelling
from the project's district registry. Each is a documented variant, not a
guess, and each is listed explicitly below rather than resolved by fuzzy
matching - a fuzzy matcher would also "successfully" match genuinely
different districts.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NATIONAL_DUMP = ROOT / "data" / "raw" / "external" / "datagovin" / "district_yield_rice.csv"
REGISTRY_PATH = ROOT / "data" / "metadata" / "district_registry.csv"
OUT_DIR = ROOT / "data" / "raw" / "external" / "official_yield" / "tamil_nadu_overlap"

RESOURCE_ID = "35be999b-0208-4354-b557-f6ca9a5355de"
SOURCE_NAME = (
    "District-wise, season-wise crop production statistics - Government of India, "
    "Ministry of Agriculture and Farmers Welfare (via data.gov.in)"
)
SOURCE_URL = f"https://data.gov.in/resource/{RESOURCE_ID}"

# Overlap target: the years AP and Telangana actually have. AP covers
# 1999-2012 and Telangana 1999-2011 in the aligned dataset; Tamil Nadu's rows
# in this resource start at 1998 for Kharif. 2000-2012 is the intersection
# that is also covered by the project's existing 2000-2012 satellite pulls.
YEAR_MIN, YEAR_MAX = 2000, 2012
SEASON = "Kharif"

# Source spelling -> district registry spelling. Every entry is a documented
# variant of the SAME district, verified against the registry's own list.
DISTRICT_ALIASES = {
    # Spelling/transliteration variants of the same name.
    "KANCHIPURAM": "KANCHEEPURAM",
    "SIVAGANGA": "SIVAGANGAI",
    "THIRUVARUR": "TIRUVARUR",
    "TIRUCHIRAPPALLI": "TIRUCHIRAPALLI",
    # Official renaming: Tuticorin is the anglicised colonial-era name of the
    # district officially known as Thoothukudi. Same district, renamed.
    "TUTICORIN": "THOOTHUKUDI",
}


def extract() -> pd.DataFrame:
    df = pd.read_csv(NATIONAL_DUMP)
    tn = df[
        (df["state"] == "Tamil Nadu")
        & (df["year"].between(YEAR_MIN, YEAR_MAX))
        & (df["season"] == SEASON)
    ].copy()

    tn["district"] = tn["district"].replace(DISTRICT_ALIASES)

    out = pd.DataFrame({
        "state": tn["state"],
        "district": tn["district"],
        "crop": tn["crop"],
        "season": tn["season"],
        "year": tn["year"].astype(int),
        "area_ha": tn["area_ha"],
        "production_tonnes": tn["production_t"],
        # Recomputed here from area and production rather than copied, so the
        # relationship is verifiable in this file. Checked against the
        # source-derived column below.
        "final_yield_t_ha": (tn["production_t"] / tn["area_ha"]).round(4),
        "yield_unit": "t/ha",
        "geographic_level": "district",
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "retrieved_date": date.today().isoformat(),
    })
    # The derivation must reproduce the value already in the dump; a mismatch
    # would mean the two paths disagree and must not be silently accepted.
    mismatch = (out["final_yield_t_ha"] - tn["yield_t_ha"]).abs() > 1e-3
    if mismatch.any():
        raise ValueError(
            f"{int(mismatch.sum())} row(s) where production/area disagrees with the "
            "resource's own derived yield - refusing to write."
        )
    return out.sort_values(["district", "year"]).reset_index(drop=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = extract()

    registry = pd.read_csv(REGISTRY_PATH)
    reg_tn = set(registry[registry["state"] == "Tamil Nadu"]["district"])
    unmatched = sorted(set(out["district"]) - reg_tn)

    path = OUT_DIR / "tamil_nadu_overlap_apy_clean.csv"
    out.to_csv(path, index=False)

    print(f"rows: {len(out)}")
    print(f"districts: {out['district'].nunique()}  years: {out['year'].min()}-{out['year'].max()}")
    print(f"seasons: {sorted(out['season'].unique())}")
    print(f"yield range: {out['final_yield_t_ha'].min():.3f} - {out['final_yield_t_ha'].max():.3f} t/ha")
    print(f"districts NOT in registry (would not align): {unmatched or 'none'}")
    print(f"wrote -> {path}")


if __name__ == "__main__":
    main()
