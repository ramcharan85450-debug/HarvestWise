"""
Standalone scoring harness for the HarvestWise Climate-Shock Benchmark -
kept dependency-light (json + sklearn only) so it's usable outside this
project's full repo, the way a released benchmark should be.

Splits are keyed by (field_id, year), not by year alone. That matters: a
drought is a local event, and the same calendar year is a shock season in one
state and an ordinary one in another. The earlier region-wide year_labels.json
could not express that, and its labels were not derived from any climate
record at all.
"""

import json
from pathlib import Path
from typing import Callable

from sklearn.metrics import mean_absolute_error, r2_score

SplitKey = tuple[str, int]


def load_splits(path: str = "splits/field_year_labels.json") -> dict[SplitKey, str]:
    """Returns {(field_id, year): label}, where label is 'normal' or a shock
    type ('drought', 'wet_extreme', 'heatwave')."""
    raw = json.loads(Path(path).read_text())
    return {
        (field_id, int(year)): label
        for field_id, years in raw["fields"].items()
        for year, label in years.items()
    }


def score_model(
    predict_fn: Callable[[list], list[float]],
    examples: list,
    field_year_of_fn: Callable,
    splits: dict[SplitKey, str],
) -> dict:
    """
    predict_fn: takes a list of examples, returns predicted yields (same order)
    examples: your dataset's per-season examples
    field_year_of_fn: extracts (field_id, year) from one example
    splits: output of load_splits()

    Reports MAE alongside R^2, and the sample size behind each. MAE is the
    primary metric: R^2 over a handful of held-out seasons is dominated by the
    variance of those few points, and is reported as None below a minimum
    count rather than as a number that would be quoted without its n.
    """
    MIN_FOR_R2 = 5

    by_bucket: dict[str, list] = {"normal": [], "shock": []}
    for ex in examples:
        label = splits.get(field_year_of_fn(ex))
        if label is None:
            continue  # unlabelled season - excluded, not guessed at
        by_bucket["normal" if label == "normal" else "shock"].append(ex)

    results: dict = {}
    for bucket, bucket_examples in by_bucket.items():
        n = len(bucket_examples)
        results[f"n_{bucket}"] = n
        if n == 0:
            results[f"mae_{bucket}"] = None
            results[f"r2_{bucket}"] = None
            continue

        preds = predict_fn(bucket_examples)
        truth = [getattr(ex, "final_yield", ex) for ex in bucket_examples]
        results[f"mae_{bucket}"] = round(float(mean_absolute_error(truth, preds)), 4)
        results[f"r2_{bucket}"] = round(float(r2_score(truth, preds)), 3) if n >= MIN_FOR_R2 else None

    if results["mae_normal"] is not None and results["mae_shock"] is not None:
        # Positive margin = the model degrades under climate stress. Smaller
        # is better; a negative value means it scored better on shock seasons,
        # which at small n is more likely sampling noise than robustness.
        results["climate_robustness_margin_mae"] = round(
            results["mae_shock"] - results["mae_normal"], 4
        )

    return results
