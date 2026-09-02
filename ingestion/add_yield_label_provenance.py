"""
One-time retrofit: adds provenance metadata columns (geographic_level,
source_name, source_url_or_id, retrieved_date, original_unit, crop) to the
24 yield-label files that already exist, so every file documents its own
geographic level and source directly rather than only in
data/raw/yield_labels/README.md prose.

Every value written here is taken directly from README.md's already-written,
already-cited sourcing (Economic Survey Table 1.17, CEIC/DES, data.gov.in
resource 35be999b-...) - nothing is invented. `retrieved_date` is left blank
for the default/national/state tiers because their original fetch dates were
never logged at the time and should not be backfilled with a guess; the
district tier's retrieved_date is set because it was built this session and
the date is genuinely known.

This does not change season_start_date or final_yield_t_ha in any file, and
training/dataset.py does not read the new columns - existing training and
evaluation behavior is unaffected. Run ingestion/validate_yield_labels.py
before and after to confirm.

Run (idempotent - re-running just overwrites the same metadata):
    python -m ingestion.add_yield_label_provenance
"""

from pathlib import Path

import pandas as pd

from ingestion.config import FIELDS, RAW_DIR

YIELD_LABELS_DIR = RAW_DIR / "yield_labels"
FIELDS_BY_ID = {f["field_id"]: f for f in FIELDS}

ECON_SURVEY = {
    "source_name": "Government of India, Economic Survey 2025-26, Statistical Appendix, Table 1.17: Yield Per Hectare of Major Crops",
    "source_url_or_id": "https://www.indiabudget.gov.in/economicsurvey/doc/stat/tab1.17.pdf",
    "original_unit": "kg/ha",
}
CEIC = {
    "source_name": "CEIC Data, citing Directorate of Economics and Statistics, Dept. of Agriculture & Farmers Welfare, Govt. of India",
    "source_url_or_id": "https://www.ceicdata.com (aggregator - primary source desagri.gov.in/aps.dac.gov.in unreachable from this environment, see README.md)",
    "original_unit": "t/ha",
}
DATAGOVIN_DISTRICT = {
    "source_name": "data.gov.in - District-wise, season-wise crop production statistics from 1997 (Ministry of Agriculture and Farmers Welfare)",
    "source_url_or_id": "35be999b-0208-4354-b557-f6ca9a5355de",
    "original_unit": "t/ha",
}

# (tier_dir_or_None, field_id) -> (geographic_level, source_dict, retrieved_date_or_None)
PROVENANCE = {}
for fid in ["F001", "F002", "F003"]:
    PROVENANCE[(None, fid)] = ("national", ECON_SURVEY, None)
    PROVENANCE[("national", fid)] = ("national", ECON_SURVEY, None)
for fid in ["F004", "F005", "F006", "F007"]:
    PROVENANCE[(None, fid)] = ("state", CEIC, None)
    PROVENANCE[("state", fid)] = ("state", CEIC, None)
    PROVENANCE[("national", fid)] = ("national", ECON_SURVEY, None)
for fid in ["F001", "F002", "F003", "F004", "F005", "F006"]:
    PROVENANCE[("district", fid)] = ("district", DATAGOVIN_DISTRICT, "2026-09-02")


def annotate(path: Path, tier: "str | None", field_id: str) -> bool:
    key = (tier, field_id)
    if key not in PROVENANCE:
        print(f"  SKIP {path} - no known provenance entry for tier={tier}, field_id={field_id}")
        return False

    geographic_level, source, retrieved_date = PROVENANCE[key]
    df = pd.read_csv(path)
    df["geographic_level"] = geographic_level
    df["source_name"] = source["source_name"]
    df["source_url_or_id"] = source["source_url_or_id"]
    df["original_unit"] = source["original_unit"]
    df["retrieved_date"] = retrieved_date
    df["crop"] = FIELDS_BY_ID[field_id]["crop"]
    df.to_csv(path, index=False)
    return True


def main():
    n = 0
    for path in sorted(YIELD_LABELS_DIR.glob("*_yield_labels.csv")):
        field_id = path.stem.replace("_yield_labels", "")
        if annotate(path, None, field_id):
            n += 1
    for tier_dir in ["national", "state", "district"]:
        for path in sorted((YIELD_LABELS_DIR / tier_dir).glob("*_yield_labels.csv")):
            field_id = path.stem.replace("_yield_labels", "")
            if annotate(path, tier_dir, field_id):
                n += 1
    print(f"annotated {n} file(s)")


if __name__ == "__main__":
    main()
