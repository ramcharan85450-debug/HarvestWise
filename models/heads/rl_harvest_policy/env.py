"""
Gymnasium environment simulating one growing season as a sequential
harvest-timing decision. Trained on replayed historical season trajectories
(built from data/processed/*_aligned.csv + the yield forecast head's
weekly predictions - see training/train_rl.py).

Each episode = one field-season. Every week the agent chooses wait or
harvest; waiting accrues a small delay cost, harvesting ends the episode
and pays out the realized yield at that week minus a weather-risk penalty
for any rain forecast during that week above a safe threshold. This is the
same reward shape as models/heads/static_harvest_optimizer.py's scoring
function, so the two are a fair, comparable baseline/challenger pair for
evaluation/statistical_tests/paired_significance.py.
"""

from dataclasses import dataclass

import gymnasium as gym
import numpy as np
from gymnasium import spaces


@dataclass
class SeasonTrajectory:
    weekly_median_yield: list[float]
    weekly_low_yield: list[float]
    weekly_high_yield: list[float]
    weekly_rainfall_mm: list[float]
    min_harvest_week: int = 0  # earliest week harvest is agronomically valid


class HarvestTimingEnv(gym.Env):
    metadata = {"render_modes": []}

    RAIN_RISK_THRESHOLD_MM = 25.0
    RAIN_PENALTY_PER_MM = 0.02
    DELAY_COST_PER_WEEK = 0.01
    LOOKAHEAD_WEEKS = 4  # forecast horizon visible to the agent - see _obs()

    def __init__(self, trajectories: list[SeasonTrajectory]):
        super().__init__()
        if not trajectories:
            raise ValueError("HarvestTimingEnv needs at least one SeasonTrajectory.")
        self.trajectories = trajectories

        # Observation = current week's forecast state (5) + a forward-looking
        # forecast window of median yield and rainfall (2 * LOOKAHEAD_WEEKS).
        #
        # The lookahead is not optional detail - without it the agent is asked
        # "harvest now or wait?" while seeing only the current week, i.e. with
        # no information about whether next week is better, which makes the
        # decision structurally impossible and made an earlier RL-vs-static
        # comparison meaningless (the static optimizer in
        # models/heads/static_harvest_optimizer.py grid-searches the WHOLE
        # season array, so it had full foresight while the agent had none).
        # It is also what the real system actually shows: the yield forecast
        # head predicts a forward weekly curve, and the dashboard displays it,
        # so a deployed agent genuinely has this information.
        self.observation_space = spaces.Box(
            low=-10.0, high=10.0, shape=(5 + 2 * self.LOOKAHEAD_WEEKS,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(2)  # 0 = wait, 1 = harvest

        self._traj: SeasonTrajectory | None = None
        self._week: int = 0
        self._rng = np.random.default_rng()

    def _lookahead(self, series: list[float], w: int) -> list[float]:
        """Next LOOKAHEAD_WEEKS values after week w, edge-padded with the last
        real value once the season runs out (so end-of-season observations
        stay well-defined rather than wrapping or zero-filling, which would
        read as a sudden yield collapse)."""
        n = len(series)
        return [series[min(w + k, n - 1)] for k in range(1, self.LOOKAHEAD_WEEKS + 1)]

    def _obs(self) -> np.ndarray:
        t = self._traj
        w = self._week
        n = len(t.weekly_median_yield)
        return np.array(
            [
                t.weekly_median_yield[w],
                t.weekly_low_yield[w],
                t.weekly_high_yield[w],
                t.weekly_rainfall_mm[w],
                w / max(1, n - 1),
                *self._lookahead(t.weekly_median_yield, w),
                *self._lookahead(t.weekly_rainfall_mm, w),
            ],
            dtype=np.float32,
        )

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._traj = self.trajectories[self._rng.integers(0, len(self.trajectories))]
        self._week = self._traj.min_harvest_week
        return self._obs(), {}

    def step(self, action: int):
        t = self._traj
        n = len(t.weekly_median_yield)
        last_week = n - 1

        if action == 0 and self._week < last_week:
            reward = -self.DELAY_COST_PER_WEEK
            self._week += 1
            terminated = False
        else:
            realized_yield = t.weekly_median_yield[self._week]
            excess_rain = max(0.0, t.weekly_rainfall_mm[self._week] - self.RAIN_RISK_THRESHOLD_MM)
            reward = realized_yield - excess_rain * self.RAIN_PENALTY_PER_MM
            terminated = True

        truncated = False
        return self._obs(), float(reward), terminated, truncated, {"week": self._week}
