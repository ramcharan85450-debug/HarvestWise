"""
Validates every yield-label file under data/raw/yield_labels/ against the
exact schema training/dataset.py actually requires, plus the extended
metadata columns recommended for new collection (geographic_level,
source_name, source_url_or_id, retrieved_date, original_unit, crop -
see data/raw/yield_labels/COLLECTION_PLAN.md).

Required by the model loader (training/dataset.py, verified by reading
build_dataset_from_processed and _match_yield_label directly, not assumed):
    season_start_date   parsed via pd.read_csv(..., parse_dates=[...])
    final_yield_t_ha     read as float, tonnes per hectare

This script never modifies a yield-label file - it only reports. Extra
columns beyond the two required ones are harmless to training/dataset.py
(pandas carries them, nothing reads them), so the recommended metadata
columns can be added without touching the training code.

Checks, in order:
    1. Missing values in required columns
    2. Duplicate season_start_date within one file
    3. Invalid yields (non-positive, or outside a plausible rice/wheat range)
    4. Unit inconsistencies (original_unit present and not already t/ha-labelled
       as something else; a final_yield_t_ha value implausibly large suggests
       a forgotten kg/ha -> t/ha conversion)
    5. Date problems (unparseable, before 1990, or in the future)
    6. Crop mismatches (the file's field_id must exist in ingestion.config.FIELDS;
       if a crop column is present, it must match that field's configured crop)

Run:
    python -m ingestion.validate_yield_labels
"""

from pathlib import Path

import pandas as pd

from ingestion.config import FIELDS, RAW_DIR

YIELD_LABELS_DIR = RAW_DIR / "yield_labels"
REQUIRED_COLS = ["season_start_date", "final_yield_t_ha"]
RECOMMENDED_COLS = ["geographic_level", "source_name", "source_url_or_id", "retrieved_date", "original_unit", "crop"]
VALID_GEOGRAPHIC_LEVELS = {"field", "district", "state", "national"}

# Plausible bounds for rice/wheat yield in t/ha - generous on purpose, this is
# a sanity check for unit-conversion mistakes (e.g. a kg/ha figure left
# unconverted, which would read as ~2000-4000), not a tight agronomic claim.
PLAUSIBLE_MIN_T_HA = 0.1
PLAUSIBLE_MAX_T_HA = 15.0
UNCONVERTED_KG_HA_THRESHOLD = 50.0  # a t/ha value this large is almost certainly an un-converted kg/ha number

FIELDS_BY_ID = {f["field_id"]: f for f in FIELDS}


def validate_file(path: Path) -> list[str]:
    issues: list[str] = []
    field_id = path.name.replace("_yield_labels.csv", "")

    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [f"could not read file: {e}"]

    # --- schema ---
    missing_required = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_required:
        issues.append(f"missing required column(s): {missing_required} - training/dataset.py will KeyError on this file")
        return issues  # nothing else can be checked meaningfully without these

    present_recommended = [c for c in RECOMMENDED_COLS if c in df.columns]
    missing_recommended = [c for c in RECOMMENDED_COLS if c not in df.columns]
    if missing_recommended:
        issues.append(f"missing recommended metadata column(s) (not required by the model, but loses provenance): {missing_recommended}")

    # --- 1. missing values ---
    for col in REQUIRED_COLS:
        n_null = df[col].isna().sum()
        if n_null:
            issues.append(f"{n_null} missing value(s) in required column '{col}'")
    for col in present_recommended:
        n_null = df[col].isna().sum()
        if n_null:
            issues.append(f"{n_null} missing value(s) in metadata column '{col}'")

    # --- 5. date problems (checked before dedup so bad dates are visible) ---
    parsed = pd.to_datetime(df["season_start_date"], errors="coerce")
    n_unparseable = parsed.isna().sum() - df["season_start_date"].isna().sum()
    if n_unparseable:
        issues.append(f"{n_unparseable} unparseable date(s) in 'season_start_date'")
    valid_dates = parsed.dropna()
    if (valid_dates.dt.year < 1990).any():
        issues.append(f"{(valid_dates.dt.year < 1990).sum()} date(s) before 1990 - implausible for this project")
    if (valid_dates > pd.Timestamp.now()).any():
        issues.append(f"{(valid_dates > pd.Timestamp.now()).sum()} date(s) in the future")

    # --- 2. duplicates ---
    n_dup = df.duplicated(subset=["season_start_date"]).sum()
    if n_dup:
        issues.append(f"{n_dup} duplicate season_start_date row(s) - _match_yield_label will silently pick one via iloc[0]")

    # --- 3. invalid yields ---
    yields = pd.to_numeric(df["final_yield_t_ha"], errors="coerce")
    n_nonnumeric = yields.isna().sum() - df["final_yield_t_ha"].isna().sum()
    if n_nonnumeric:
        issues.append(f"{n_nonnumeric} non-numeric value(s) in 'final_yield_t_ha'")
    valid_yields = yields.dropna()
    n_nonpositive = (valid_yields <= 0).sum()
    if n_nonpositive:
        issues.append(f"{n_nonpositive} non-positive yield value(s)")
    out_of_range = valid_yields[(valid_yields > 0) & ((valid_yields < PLAUSIBLE_MIN_T_HA) | (valid_yields > PLAUSIBLE_MAX_T_HA))]
    if len(out_of_range):
        issues.append(f"{len(out_of_range)} yield value(s) outside the plausible {PLAUSIBLE_MIN_T_HA}-{PLAUSIBLE_MAX_T_HA} t/ha range: {out_of_range.tolist()}")

    # --- 4. unit inconsistencies ---
    unconverted = valid_yields[valid_yields > UNCONVERTED_KG_HA_THRESHOLD]
    if len(unconverted):
        issues.append(f"{len(unconverted)} value(s) above {UNCONVERTED_KG_HA_THRESHOLD} t/ha - almost certainly an un-converted kg/ha or quintal/ha figure: {unconverted.tolist()}")
    if "original_unit" in df.columns:
        units = df["original_unit"].dropna().unique().tolist()
        if len(units) > 1:
            issues.append(f"multiple different original_unit values in one file: {units} - confirm each row was converted with the correct factor")

    # --- 6. crop / field mismatches ---
    if field_id not in FIELDS_BY_ID:
        issues.append(f"field_id '{field_id}' (from filename) is not in ingestion.config.FIELDS - not a recognized field")
    elif "crop" in df.columns:
        configured_crop = FIELDS_BY_ID[field_id]["crop"]
        mismatched = df.loc[df["crop"].notna() & (df["crop"] != configured_crop), "crop"].unique().tolist()
        if mismatched:
            issues.append(f"crop column has value(s) {mismatched} that don't match {field_id}'s configured crop '{configured_crop}'")

    if "geographic_level" in df.columns:
        bad_levels = df.loc[df["geographic_level"].notna() & ~df["geographic_level"].isin(VALID_GEOGRAPHIC_LEVELS), "geographic_level"].unique().tolist()
        if bad_levels:
            issues.append(f"geographic_level has unrecognized value(s) {bad_levels}, expected one of {sorted(VALID_GEOGRAPHIC_LEVELS)}")
        if (df["geographic_level"] == "field").any():
            issues.append(
                "WARNING: geographic_level='field' claims true field-level ground truth - "
                "confirm this is a real per-field measurement, not a district/state average "
                "relabelled as field-level (see COLLECTION_PLAN.md rule 2)"
            )

    return issues


def main():
    all_files = sorted(YIELD_LABELS_DIR.glob("*_yield_labels.csv")) + sorted(YIELD_LABELS_DIR.glob("*/*_yield_labels.csv"))
    if not all_files:
        print(f"No yield-label files found under {YIELD_LABELS_DIR}")
        return

    total_issues = 0
    for path in all_files:
        rel = path.relative_to(YIELD_LABELS_DIR)
        issues = validate_file(path)
        if issues:
            print(f"\n{rel}")
            for issue in issues:
                print(f"  - {issue}")
            total_issues += len(issues)
        else:
            print(f"{rel}: OK")

    print(f"\n{len(all_files)} file(s) checked, {total_issues} issue(s) found.")


if __name__ == "__main__":
    main()
