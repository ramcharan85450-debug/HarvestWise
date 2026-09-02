"""
Defines the "HarvestWise Climate-Shock Benchmark" splits: which field-seasons
count as normal vs. climate-shock (drought / wet_extreme / heatwave).

Labels are NOT hand-written. They are derived from this project's real ERA5
growing-season record by evaluation/climate_shock_benchmark/derive_labels.py,
which writes derived_labels.json; this module just loads that file. Run
derive_labels.py after any change to the weather data or crop calendars.

(An earlier version of this file shipped a hardcoded YEAR_LABELS dict with
invented entries like 2019: "drought" and a TODO to replace them. Those were
placeholders, never real observations, and any benchmark result computed
against them would have been meaningless - they are gone.)

Labels are keyed by (field_id, year), not by year alone, because climate
shocks are regional: the real record has West Bengal's 2022 season at 53% of
its normal rainfall while Punjab's 2022 was unremarkable. See
derive_labels.py's docstring for the thresholds, provenance and - importantly
- the small-sample limitations that must be reported alongside any result.
"""

import json
from datetime import date
from pathlib import Path

LABELS_PATH = Path(__file__).resolve().parent / "derived_labels.json"

NORMAL_LABEL = "normal"


def _load_labels() -> dict[str, dict[str, str]]:
    if not LABELS_PATH.exists():
        raise FileNotFoundError(
            f"{LABELS_PATH} not found - run `python -m evaluation.climate_shock_benchmark.derive_labels` "
            "to derive the benchmark's labels from the real ERA5 record."
        )
    return json.loads(LABELS_PATH.read_text())["fields"]


FIELD_YEAR_LABELS = _load_labels()


def label_for(field_id: str, year: int) -> str:
    """Real climate label for one field-season, or 'unknown' if that season
    was excluded (e.g. truncated by the end of the weather record)."""
    return FIELD_YEAR_LABELS.get(field_id, {}).get(str(year), "unknown")


def label_for_year(year: int) -> str:
    """Back-compat helper for callers that only have a year. Returns the
    majority label across fields for that year - use label_for() instead
    wherever the field is known, since shocks are regional."""
    labels = [per_year[str(year)] for per_year in FIELD_YEAR_LABELS.values() if str(year) in per_year]
    if not labels:
        return "unknown"
    return max(set(labels), key=labels.count)


def split_by_climate(examples: list) -> tuple[list, list]:
    """The benchmark's headline experiment: train on NORMAL field-seasons,
    test on real climate-SHOCK field-seasons, so the test set measures
    generalisation to conditions never seen in training. Seasons labelled
    'unknown' (excluded during derivation) are dropped from both sides
    rather than silently counted as normal."""
    train, test = [], []
    for ex in examples:
        year = date.fromisoformat(ex.season_start_date).year
        label = label_for(ex.field_id, year)
        if label == NORMAL_LABEL:
            train.append(ex)
        elif label != "unknown":
            test.append(ex)
    return train, test
