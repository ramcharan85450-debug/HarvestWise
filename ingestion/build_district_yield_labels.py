"""
Builds data/raw/yield_labels/district/{field_id}_yield_labels.csv - the tier
evaluation/label_granularity/run_granularity_sweep.py has been waiting on
since it was written (see training/dataset.py's build_dataset_from_processed
docstring: "district (not yet populated)").

Source: data/raw/external/datagovin/district_yield_rice.csv (data.gov.in
resource 35be999b..., "District-wise, season-wise crop production statistics
from 1997"), filtered to each field's real district and the season that
matches its CROP_CALENDARS entry in ingestion/config.py.

Stated limitation, carried into RESULTS.md rather than hidden: this district
-level source stops in 2013-2014 for these districts (see printed output),
while the real satellite/weather data pulled for these fields runs 2019-2026.
training/dataset.py's _match_yield_label has no exact-year match available
for any real season here, so every season falls back to day-of-year matching
and lands on the SAME nearest available year (2013 or 2014) - unlike the
national and state tiers, which both have real label variation inside the
satellite years. The district tier is therefore a test of spatial resolution
alone, with no temporal variation contribution - a real, different tradeoff
from the other two tiers, not an oversight.

F007 (Punjab wheat) is not covered - district_yield_rice.csv is rice-only -
and is therefore correctly absent from the district tier;
run_granularity_sweep.py already restricts every comparison to fields present
at EVERY tier being compared.

Run:
    python -m ingestion.build_district_yield_labels
"""

import pandas as pd

from ingestion.config import RAW_DIR

SRC = RAW_DIR / "external" / "datagovin" / "district_yield_rice.csv"
OUT_DIR = RAW_DIR / "yield_labels" / "district"

# field_id -> (district name as it appears in SRC, season value in SRC, (month, day) from CROP_CALENDARS)
FIELD_DISTRICT_SEASON = {
    "F001": ("COIMBATORE", "Kharif", (8, 1)),
    "F002": ("COIMBATORE", "Kharif", (8, 1)),
    "F003": ("COIMBATORE", "Kharif", (8, 1)),
    "F004": ("AMRITSAR", "Kharif", (6, 15)),
    "F005": ("BARDHAMAN", "Winter", (7, 1)),  # Bardhaman's "Winter" season = Aman rice, WB's kharif crop
    "F006": ("EAST GODAVARI", "Kharif", (7, 1)),
}


def main():
    src = pd.read_csv(SRC)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for field_id, (district, season, (month, day)) in FIELD_DISTRICT_SEASON.items():
        rows = src[(src.district.str.upper() == district) & (src.season == season)].copy()
        if rows.empty:
            print(f"{field_id}: no rows for {district}/{season} - skipped")
            continue
        rows["season_start_date"] = rows["year"].apply(lambda y: f"{y}-{month:02d}-{day:02d}")
        out = rows[["season_start_date", "yield_t_ha"]].rename(columns={"yield_t_ha": "final_yield_t_ha"})
        out = out.sort_values("season_start_date")
        out_path = OUT_DIR / f"{field_id}_yield_labels.csv"
        out.to_csv(out_path, index=False)
        print(
            f"{field_id}: {district}/{season}, {len(out)} real years "
            f"({out.season_start_date.min()[:4]}-{out.season_start_date.max()[:4]}) -> {out_path}"
        )


if __name__ == "__main__":
    main()
