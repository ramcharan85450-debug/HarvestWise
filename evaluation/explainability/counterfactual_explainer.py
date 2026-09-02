"""
Finds the smallest change to an input that flips a harvest-window
recommendation - "the window moved because rainfall exceeded X mm" instead
of leaving the decision as a black box.

backend/app/services/explain_service.py calls this directly against the real
trained policy, so the explanation shown on the dashboard and the one reported
in the write-up come from the same code path.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class CounterfactualResult:
    baseline_window: tuple[int, int]
    perturbed_window: tuple[int, int]
    driving_factor: str
    threshold_value: float
    original_value: float


def explain_rainfall_sensitivity(
    weekly_median_yield: list[float],
    weekly_rainfall_mm: list[float],
    recommend_fn: Callable[[list[float], list[float]], tuple[int, int]],
    search_start_idx: int,
    rain_threshold_search: tuple[float, float] = (0.0, 60.0),
    tolerance_mm: float = 0.5,
) -> CounterfactualResult:
    """Binary-searches a uniform rainfall-threshold-crossing value at the
    baseline recommended week: how much would rainfall in that week need to
    drop before the recommendation reverts to the yield-only optimum?"""
    baseline_window = recommend_fn(weekly_median_yield, weekly_rainfall_mm)
    week_idx = baseline_window[0]
    original_rain = weekly_rainfall_mm[week_idx]

    lo, hi = rain_threshold_search
    best_flip_value = original_rain

    while hi - lo > tolerance_mm:
        mid = (lo + hi) / 2
        perturbed_rain = weekly_rainfall_mm.copy()
        perturbed_rain[week_idx] = mid
        candidate_window = recommend_fn(weekly_median_yield, perturbed_rain)

        if candidate_window != baseline_window:
            best_flip_value = mid
            if mid < original_rain:
                lo = mid
            else:
                hi = mid
        else:
            if mid < original_rain:
                hi = mid
            else:
                lo = mid

    perturbed_rain = weekly_rainfall_mm.copy()
    perturbed_rain[week_idx] = best_flip_value
    perturbed_window = recommend_fn(weekly_median_yield, perturbed_rain)

    return CounterfactualResult(
        baseline_window=baseline_window,
        perturbed_window=perturbed_window,
        driving_factor="forecasted_rainfall",
        threshold_value=round(best_flip_value, 1),
        original_value=round(original_rain, 1),
    )
