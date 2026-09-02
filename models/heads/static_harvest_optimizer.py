"""
Static multi-objective harvest-window optimizer - the working baseline built
before the RL policy (models/heads/rl_harvest_policy/), and the fallback the
RL policy is benchmarked against in evaluation/statistical_tests/.

Given the yield forecast curve and a weather forecast, scores every
candidate window by (expected yield - weather risk penalty - delay cost)
and returns the best one. No learning involved - a grid search over
candidate windows, deliberately simple so it's easy to reason about and
hard to get wrong.
"""

from dataclasses import dataclass


@dataclass
class HarvestWindowResult:
    start_week_idx: int
    end_week_idx: int
    expected_yield: float
    score: float


def score_window(
    weekly_median_yield: list[float],
    weekly_rainfall_mm: list[float],
    start_idx: int,
    window_len: int,
    rain_risk_threshold_mm: float = 25.0,
    rain_penalty_per_mm: float = 0.02,
    delay_cost_per_week: float = 0.01,
    delay_from_idx: int = 0,
) -> float:
    """delay_from_idx: the index delay is measured from (default 0 = season
    start). Set this to your search's earliest valid index so delay cost
    means "weeks waited past the earliest valid harvest," not "weeks since
    season start" - the same convention models/heads/rl_harvest_policy/env.py
    uses (it only charges delay for weeks waited past min_harvest_week). A
    mismatched convention between this and the RL env would make any
    RL-vs-static comparison an apples-to-oranges artifact, not a fair
    evaluation - see evaluation/statistical_tests/run_rl_vs_static.py."""
    end_idx = start_idx + window_len
    expected_yield = max(weekly_median_yield[start_idx:end_idx])
    excess_rain = sum(max(0.0, r - rain_risk_threshold_mm) for r in weekly_rainfall_mm[start_idx:end_idx])
    weather_penalty = excess_rain * rain_penalty_per_mm
    delay_penalty = (start_idx - delay_from_idx) * delay_cost_per_week
    return expected_yield - weather_penalty - delay_penalty


def optimize_window(
    weekly_median_yield: list[float],
    weekly_rainfall_mm: list[float],
    window_len_weeks: int = 1,
    search_start_idx: int = 0,
) -> HarvestWindowResult:
    """Tries every window of window_len_weeks starting from search_start_idx
    onward (typically once the yield curve has plateaued) and returns the
    highest-scoring one. Delay cost is measured from search_start_idx, not
    absolute week 0 - see score_window's delay_from_idx docstring."""
    n = len(weekly_median_yield)
    best: HarvestWindowResult | None = None

    for start in range(search_start_idx, n - window_len_weeks + 1):
        score = score_window(weekly_median_yield, weekly_rainfall_mm, start, window_len_weeks, delay_from_idx=search_start_idx)
        if best is None or score > best.score:
            best = HarvestWindowResult(
                start_week_idx=start,
                end_week_idx=start + window_len_weeks,
                expected_yield=max(weekly_median_yield[start : start + window_len_weeks]),
                score=score,
            )

    if best is None:
        raise ValueError("No valid window found - check window_len_weeks against series length.")
    return best
