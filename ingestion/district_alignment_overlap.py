"""
Experiment 3, Phase 9 - alignment of the Tamil Nadu overlap-year records.

WHAT THIS WRITES, AND WHAT IT DELIBERATELY DOES NOT TOUCH
---------------------------------------------------------
Experiments 1 and 2 both read
`data/processed/district_multimodal_examples.csv`. Regenerating that file
would silently change the inputs of two completed, committed experiments, so
this module NEVER writes to it. It writes a separate v2 dataset:

    data/processed/district_multimodal_examples_v2.csv

carrying every row the original has PLUS the newly aligned Tamil Nadu
overlap-year rows, with an added `dataset_version` column marking each row
`experiment1_baseline` or `experiment3_overlap_addition` so provenance stays
traceable and the two cohorts can always be separated again.

WHY THE ALIGNMENT LOGIC IS REUSED RATHER THAN REIMPLEMENTED
-----------------------------------------------------------
For the new Tamil Nadu rows to be comparable to the Andhra Pradesh and
Telangana rows they are meant to be contrasted with, they must be aligned by
EXACTLY the same rules: the same season windows, the same 50% window-coverage
floor, the same calendar-year satellite coverage check, the same yield
validity bounds. Rather than copy that loop (and risk it drifting), this
module reuses `ingestion.district_alignment.build_alignment()` unchanged and
only substitutes the set of yield records it consumes, by temporarily
replacing that module's `_load_yield_records`. The substitution is restored
in a `finally` block. No file in `ingestion/district_alignment.py` is edited.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ingestion.district_alignment as da  # noqa: E402

OVERLAP_PATH = (
    ROOT / "data" / "raw" / "external" / "official_yield" / "tamil_nadu_overlap"
    / "tamil_nadu_overlap_apy_clean.csv"
)
OUT_PATH = ROOT / "data" / "processed" / "district_multimodal_examples_v2.csv"
STATS_PATH = ROOT / "data" / "processed" / "district_alignment_v2_stats.json"

BASELINE_TAG = "experiment1_baseline"
NEW_TAG = "experiment3_overlap_addition"


# Captured at import time, BEFORE main() swaps the module attribute. Calling
# da._load_yield_records() inside the replacement would call the replacement
# itself and recurse forever.
_ORIGINAL_LOADER = da._load_yield_records


def _load_with_overlap() -> pd.DataFrame:
    """The original three regional files, plus the new Tamil Nadu overlap
    file, tagged so each row's cohort remains identifiable downstream."""
    base = _ORIGINAL_LOADER()
    base["dataset_version"] = BASELINE_TAG

    extra = pd.read_csv(OVERLAP_PATH)
    extra["_source_region"] = "tamil_nadu_overlap"
    extra["dataset_version"] = NEW_TAG

    combined = pd.concat([base, extra], ignore_index=True)

    # The dedup key used inside build_alignment() is
    # (state, district, crop, season, year). Verify here that the new rows
    # cannot collide with existing ones rather than discovering it as a
    # silent drop later.
    key = ["state", "district", "crop", "season", "year"]
    dupes = combined.duplicated(key).sum()
    if dupes:
        raise ValueError(
            f"{dupes} duplicate (state, district, crop, season, year) key(s) after adding the "
            "overlap file - refusing to proceed, because build_alignment() would drop them "
            "silently and the counts would not mean what they appear to mean."
        )
    return combined


def main():
    original = da._load_yield_records
    da._load_yield_records = _load_with_overlap
    try:
        rows, stats = da.build_alignment()
    finally:
        da._load_yield_records = original

    all_cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in all_cols:
                all_cols.append(k)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in all_cols})

    # build_alignment() constructs each output row from an explicit field list,
    # so a column added to the INPUT frame does not survive into the output.
    # The cohort tag is therefore re-derived here by matching on the same
    # (state, district, crop, season, year) key the aligner itself dedupes on.
    overlap_keys = {
        (r.state, r.district, r.crop, r.season, int(r.year))
        for r in pd.read_csv(OVERLAP_PATH).itertuples(index=False)
    }
    for r in rows:
        key = (r["state"], r["district"], r["crop"], r["season"], int(r["year"]))
        r["dataset_version"] = NEW_TAG if key in overlap_keys else BASELINE_TAG
    if "dataset_version" not in all_cols:
        all_cols.append("dataset_version")
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in all_cols})

    df = pd.DataFrame(rows)
    new = df[df["dataset_version"] == NEW_TAG]
    aligned = new[new.weather_available & new.satellite_available & new.soil_available]

    summary = {
        "counters": stats["counters"],
        "rejection_reasons": stats["rejection_reasons"],
        "new_cohort": {
            "collected": int(len(new)),
            "geometry_matched": int(new["district_id"].astype(str).ne("").sum()),
            "weather_matched": int(new["weather_available"].sum()),
            "satellite_matched": int(new["satellite_available"].sum()),
            "soil_matched": int(new["soil_available"].sum()),
            "fully_aligned": int(len(aligned)),
        },
    }
    STATS_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"total rows written: {len(rows)} -> {OUT_PATH}")
    print("NEW Tamil Nadu overlap cohort:")
    for k, v in summary["new_cohort"].items():
        print(f"  {k:20s} {v}")
    base = df[df["dataset_version"] == BASELINE_TAG]
    base_aligned = base[base.weather_available & base.satellite_available & base.soil_available]
    print(f"baseline cohort fully aligned: {len(base_aligned)} (Experiment 1 had 561)")


if __name__ == "__main__":
    main()
