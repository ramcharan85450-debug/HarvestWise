"""
Counterfactual explanation service - real sensitivity analysis.

Answers "why this week?" by binary-searching the smallest rainfall value at
the recommended week that flips the recommendation, using the shared
implementation in evaluation/explainability/counterfactual_explainer.py so the
explanation shown on the dashboard is produced by the same code path as the
one reported in the write-up.

The recommendation being probed is the real one: the trained PPO policy where
available, otherwise the static multi-objective optimizer - the identical
function harvest_service.py serves from, so the explanation always describes
the window the user was actually shown.
"""

from app.services.data_service import season_weeks
from app.services.errors import RealDataUnavailable
from app.services.forecast_service import forecast_quantiles
from app.services.harvest_service import MIN_HARVEST_FRACTION, _rl_choice


def get_explanation(field_id: str) -> dict:
    from evaluation.explainability.counterfactual_explainer import explain_rainfall_sensitivity
    from models.heads.rl_harvest_policy.env import HarvestTimingEnv
    from models.heads.static_harvest_optimizer import optimize_window

    quantiles, example = forecast_quantiles(field_id)
    median = quantiles[:, 1].tolist()
    low = quantiles[:, 0].tolist()
    high = quantiles[:, 2].tolist()
    rainfall = example.weather_x[:, 1].tolist()  # precip_mm, real units
    min_week = int(len(median) * MIN_HARVEST_FRACTION)

    if min_week >= len(median) - 1:
        raise RealDataUnavailable(f"Season for '{field_id}' is too short to explain a harvest window.")

    def recommend(weekly_median: list[float], weekly_rain: list[float]) -> tuple[int, int]:
        week = _rl_choice(weekly_median, low, high, weekly_rain, min_week)
        if week is None:
            week = optimize_window(
                weekly_median, weekly_rain, window_len_weeks=1, search_start_idx=min_week
            ).start_week_idx
        return (week, week + 1)

    result = explain_rainfall_sensitivity(
        weekly_median_yield=median,
        weekly_rainfall_mm=rainfall,
        recommend_fn=recommend,
        search_start_idx=min_week,
    )

    baseline_week = result.baseline_window[0]
    weeks = season_weeks(field_id)
    week_label = weeks[baseline_week] if weeks and baseline_week < len(weeks) else f"week {baseline_week}"

    flipped = result.perturbed_window != result.baseline_window
    if flipped:
        shift_weeks = result.perturbed_window[0] - baseline_week
        summary = (
            f"The recommended harvest week ({week_label}) is rainfall-sensitive: "
            f"real forecast rainfall that week is {result.original_value} mm, and "
            f"changing it to {result.threshold_value} mm moves the recommendation "
            f"{abs(shift_weeks)} week(s) {'later' if shift_weeks > 0 else 'earlier'}. "
            f"The harvest-risk threshold in the reward is "
            f"{HarvestTimingEnv.RAIN_RISK_THRESHOLD_MM} mm."
        )
    else:
        summary = (
            f"The recommended harvest week ({week_label}) is NOT rainfall-driven: "
            f"no rainfall value in the searched range flips it, so the choice is "
            f"driven by the predicted yield curve rather than by weather risk. "
            f"Real forecast rainfall that week is {result.original_value} mm, "
            f"against a {HarvestTimingEnv.RAIN_RISK_THRESHOLD_MM} mm risk threshold."
        )

    return {
        "field_id": field_id,
        "summary": summary,
        "driving_factor": result.driving_factor if flipped else "predicted_yield_curve",
        "threshold_mm": float(HarvestTimingEnv.RAIN_RISK_THRESHOLD_MM),
        "forecast_mm": float(result.original_value),
    }
