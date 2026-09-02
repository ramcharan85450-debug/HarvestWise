"""
Climate-Shock Benchmark results service.

Reads evaluation/climate_shock_benchmark/results.json - the actual output of
`python -m evaluation.climate_shock_benchmark.run_climate_shock` - so every
number this endpoint serves is reproducible by re-running that command.

This previously returned a hardcoded R^2 table (0.91 on normal years, 0.79 on
shock years, five models ranked in a tidy order) that no evaluation run ever
produced. Those numbers were also flattering in exactly the direction the
project's claims point, and the real ones are not: on the current 4-season
shock test set Random Forest (MAE 0.17) beats the multimodal model (MAE 0.43).
Serving the real result is the whole point - a benchmark whose leaderboard is
written by hand measures nothing.

The metric is MAE in t/ha, not R^2, because that is what the benchmark
actually computes. R^2 over 4 test points would be dominated by the variance
of those 4 points and is not a meaningful summary at this sample size.
"""

from app.config import CLIMATE_SHOCK_RESULTS
from app.services.data_service import load_json
from app.services.errors import RealDataUnavailable

_MISSING = (
    f"No benchmark results at {CLIMATE_SHOCK_RESULTS}. Run "
    "`python -m evaluation.climate_shock_benchmark.derive_labels` then "
    "`python -m evaluation.climate_shock_benchmark.run_climate_shock`."
)


def _results() -> dict:
    data = load_json(CLIMATE_SHOCK_RESULTS)
    if not data:
        raise RealDataUnavailable(_MISSING)
    return data


def get_climate_stress_results() -> list[dict]:
    """The real held-out climate-shock seasons, each with the ERA5-derived
    label that put it in the test set (see
    evaluation/climate_shock_benchmark/derive_labels.py)."""
    data = _results()
    return [
        {
            "season": f"{s['field_id']} {s['year']}",
            "label": s["label"],
            "actual_yield_t_ha": float(s["actual_yield_t_ha"]),
        }
        for s in data.get("test_seasons", [])
    ]


def get_leaderboard() -> list[dict]:
    """Every model scored on the same held-out shock seasons, best (lowest
    MAE) first. n_test_seasons is carried on every row deliberately: at n=4
    the ordering is indicative, not statistically powered, and a leaderboard
    that hides its sample size invites exactly the overclaim this benchmark
    exists to prevent."""
    data = _results()
    mae = data.get("mae_t_ha", {})
    if not mae:
        raise RealDataUnavailable(_MISSING)

    n_test = int(data.get("n_test_shock_seasons", 0))
    n_train = int(data.get("n_train_normal_seasons", 0))
    return [
        {
            "model": name,
            "mae_shock_t_ha": round(float(value), 4),
            "n_test_seasons": n_test,
            "n_train_seasons": n_train,
        }
        for name, value in sorted(mae.items(), key=lambda kv: kv[1])
    ]
