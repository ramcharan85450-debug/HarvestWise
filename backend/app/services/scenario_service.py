"""
Climate 'what-if' scenario service - real counterfactual inference.

Perturbs the real weather tensor the forecast conditions on and re-runs the
trained model, which is the same counterfactual mechanism the Climate-Shock
Benchmark rests on (evaluation/climate_shock_benchmark/). The response is
therefore the model's actual sensitivity to a warmer or drier season, not a
hand-tuned stress curve applied to the output.

The previous implementation multiplied the forecast by a closed-form
`stress_factor` fitted to nothing. It would have produced a smooth, confident
climate-response plot for a model that might have no such response at all -
which, on a project whose headline claim is climate adaptivity, is the single
most misleading thing this API could have served.
"""

from app.services.data_service import season_weeks
from app.services.forecast_service import forecast_quantiles, run_model
from app.services.harvest_service import MIN_HARVEST_FRACTION, _interval_confidence, _rl_choice

# training/dataset.py's WEATHER_COLS order: temp_c, precip_mm, humidity_pct, wind_speed_ms
TEMP_COL, PRECIP_COL = 0, 1


def _perturbed_weather(weather_x, temp_shift_c: float, rainfall_change_pct: float):
    import numpy as np

    perturbed = np.array(weather_x, copy=True)
    perturbed[:, TEMP_COL] += temp_shift_c
    perturbed[:, PRECIP_COL] = np.clip(perturbed[:, PRECIP_COL] * (1 + rainfall_change_pct / 100.0), 0, None)
    return perturbed.astype(np.float32)


def _points(quantiles, weeks) -> list[dict]:
    return [
        {
            "week": weeks[i],
            "yield_low": round(float(quantiles[i][0]), 3),
            "yield_median": round(float(quantiles[i][1]), 3),
            "yield_high": round(float(quantiles[i][2]), 3),
        }
        for i in range(len(quantiles))
    ]


def _harvest_week_under(quantiles, rainfall) -> int:
    """Re-runs the harvest decision on a perturbed trajectory so the reported
    window shift is the policy's real response to the scenario."""
    median = quantiles[:, 1].tolist()
    low = quantiles[:, 0].tolist()
    high = quantiles[:, 2].tolist()
    min_week = int(len(median) * MIN_HARVEST_FRACTION)

    week = _rl_choice(median, low, high, rainfall, min_week)
    if week is not None:
        return week

    from models.heads.static_harvest_optimizer import optimize_window

    return optimize_window(median, rainfall, window_len_weeks=1, search_start_idx=min_week).start_week_idx


def get_scenario(field_id: str, temp_shift_c: float, rainfall_change_pct: float) -> dict:
    baseline_quantiles, example = forecast_quantiles(field_id)
    weeks = season_weeks(field_id) or [example.season_start_date] * len(baseline_quantiles)

    scenario_weather = _perturbed_weather(example.weather_x, temp_shift_c, rainfall_change_pct)
    scenario_quantiles = run_model(example, weather_x=scenario_weather)

    baseline_rain = example.weather_x[:, PRECIP_COL].tolist()
    scenario_rain = scenario_weather[:, PRECIP_COL].tolist()

    baseline_week = _harvest_week_under(baseline_quantiles, baseline_rain)
    scenario_week = _harvest_week_under(scenario_quantiles, scenario_rain)

    scenario_confidence = _interval_confidence(
        float(scenario_quantiles[scenario_week][0]),
        float(scenario_quantiles[scenario_week][1]),
        float(scenario_quantiles[scenario_week][2]),
    )

    return {
        "field_id": field_id,
        "temp_shift_c": temp_shift_c,
        "rainfall_change_pct": rainfall_change_pct,
        "baseline_forecast": _points(baseline_quantiles, weeks),
        "scenario_forecast": _points(scenario_quantiles, weeks),
        "scenario_confidence": scenario_confidence,
        # Weekly resolution: one week of shift = 7 days. The model and policy
        # have no sub-weekly resolution, so a day-level number here would be
        # false precision.
        "scenario_window_shift_days": int((scenario_week - baseline_week) * 7),
    }
