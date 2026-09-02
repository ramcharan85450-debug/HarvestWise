"""
Runs any trained model against the Climate-Shock Benchmark and writes
results.json in the exact shape backend/app/services/benchmark_service.py's
TODO expects, so swapping placeholder numbers for real ones is a direct
file-read change, no reshaping needed.

Run (after training/train_forecast_model.py and the baselines have been
trained):
    python -m evaluation.climate_shock_benchmark.run_benchmark
"""

import json
from datetime import date
from pathlib import Path
from typing import Callable

from sklearn.metrics import r2_score

from evaluation.climate_shock_benchmark.build_splits import YEAR_LABELS, label_for_year
from training.dataset import SeasonExample

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def evaluate_per_year(examples: list[SeasonExample], predict_fn: Callable[[list[SeasonExample]], list[float]]) -> list[dict]:
    by_year: dict[int, list[SeasonExample]] = {}
    for ex in examples:
        year = date.fromisoformat(ex.season_start_date).year
        by_year.setdefault(year, []).append(ex)

    results = []
    for year in sorted(by_year):
        year_examples = by_year[year]
        if len(year_examples) < 2:
            continue  # R2 needs at least 2 points to be meaningful
        y_true = [ex.final_yield for ex in year_examples]
        y_pred = predict_fn(year_examples)
        label = label_for_year(year)
        results.append(
            {
                "year": f"{year} ({label.replace('_', ' ')})",
                "r2_score": round(float(r2_score(y_true, y_pred)), 3),
                "climate_label": label,
            }
        )
    return results


def save_results(model_name: str, per_year_results: list[dict]):
    existing = {}
    if RESULTS_PATH.exists():
        existing = json.loads(RESULTS_PATH.read_text())
    existing[model_name] = per_year_results
    RESULTS_PATH.write_text(json.dumps(existing, indent=2))
    print(f"wrote benchmark results for '{model_name}' -> {RESULTS_PATH}")


if __name__ == "__main__":
    print(
        "This module is a library - call evaluate_per_year(examples, your_model.predict) "
        "from a script once a trained model exists. See the module docstring for the "
        f"expected years/labels: {YEAR_LABELS}"
    )
