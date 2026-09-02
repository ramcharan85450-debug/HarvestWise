"""
Harvest-window decision service - real policy inference.

Builds the field's real weekly forecast trajectory (the same
SeasonTrajectory the RL policy was trained on, see
models/heads/rl_harvest_policy/train_rl.py), then asks the trained PPO policy
for a harvest week. If the RL checkpoint or stable-baselines3 is unavailable
it falls back to models/heads/static_harvest_optimizer.py - the deterministic
grid search the RL policy is benchmarked against - and says which one produced
the answer in `recommended_by`, so the dashboard never misattributes a
decision.
"""

from datetime import date, timedelta

from app.models_registry.model_loader import load_rl_policy
from app.services.data_service import season_weeks
from app.services.errors import RealDataUnavailable
from app.services.forecast_service import forecast_quantiles

# Matches models/heads/rl_harvest_policy/train_rl.py: harvest is treated as
# agronomically valid only from the season's midpoint onward. Both the RL env
# and the static optimizer must use the same earliest index or the comparison
# between them is not like-for-like.
MIN_HARVEST_FRACTION = 0.5


def _build_trajectory(field_id: str):
    quantiles, example = forecast_quantiles(field_id)
    return (
        quantiles[:, 1].tolist(),  # median
        quantiles[:, 0].tolist(),  # low
        quantiles[:, 2].tolist(),  # high
        example.weather_x[:, 1].tolist(),  # precip_mm, raw physical units
        int(len(quantiles) * MIN_HARVEST_FRACTION),
    )


def _rl_choice(median, low, high, rainfall, min_week) -> int | None:
    """Steps the trained policy forward from min_week and returns the week it
    chooses to harvest, or None if the policy is unavailable.

    The observation is constructed to match HarvestTimingEnv._obs exactly
    (current low/median/high/rain, normalised week position, then the
    LOOKAHEAD_WEEKS-step forward window of median yield and rainfall). A
    mismatch here would silently feed the policy a differently-shaped input
    than it was trained on and produce a meaningless recommendation.
    """
    policy = load_rl_policy()
    if policy is None:
        return None

    import numpy as np

    from models.heads.rl_harvest_policy.env import HarvestTimingEnv

    k = HarvestTimingEnv.LOOKAHEAD_WEEKS
    n = len(median)

    def lookahead(series, w):
        return [series[min(w + j, n - 1)] for j in range(1, k + 1)]

    week = min_week
    while week < n - 1:
        obs = np.array(
            [
                median[week],
                low[week],
                high[week],
                rainfall[week],
                week / max(1, n - 1),
                *lookahead(median, week),
                *lookahead(rainfall, week),
            ],
            dtype=np.float32,
        )
        action, _ = policy.predict(obs, deterministic=True)
        if int(action) == 1:
            return week
        week += 1
    return n - 1


def _interval_confidence(low: float, median: float, high: float) -> float:
    """A tightness score in (0, 1] derived from the model's own predicted
    0.1-0.9 quantile spread at the chosen week: the narrower the interval
    relative to the median, the higher the score.

    This is explicitly NOT a calibrated probability that the window is
    optimal - the project has no held-out harvest-decision outcomes to
    calibrate one against (data/raw/harvest_outcomes/ is empty). It is a
    monotone readout of the model's stated uncertainty, and should be
    described that way anywhere it is shown or reported.
    """
    if median <= 0:
        return 0.0
    relative_spread = max(0.0, (high - low) / median)
    return round(max(0.0, min(1.0, 1.0 - relative_spread)), 2)


def get_harvest_window(field_id: str) -> dict:
    median, low, high, rainfall, min_week = _build_trajectory(field_id)
    if min_week >= len(median) - 1:
        raise RealDataUnavailable(f"Season for '{field_id}' is too short to search a harvest window.")

    week_idx = _rl_choice(median, low, high, rainfall, min_week)
    if week_idx is not None:
        recommended_by = "RL adaptive policy"
    else:
        from models.heads.static_harvest_optimizer import optimize_window

        result = optimize_window(median, rainfall, window_len_weeks=1, search_start_idx=min_week)
        week_idx = result.start_week_idx
        recommended_by = "Static multi-objective optimizer"

    weeks = season_weeks(field_id)
    if weeks and week_idx < len(weeks):
        window_start = date.fromisoformat(weeks[week_idx])
    else:
        window_start = date.today()
    # The forecast and the policy both operate at weekly resolution, so the
    # recommendation is reported as the full week it selected rather than a
    # narrower band the model has no resolution to justify.
    window_end = window_start + timedelta(days=6)

    return {
        "field_id": field_id,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "confidence": _interval_confidence(low[week_idx], median[week_idx], high[week_idx]),
        "recommended_by": recommended_by,
        "expected_yield_t_ha": round(float(median[week_idx]), 2),
    }
