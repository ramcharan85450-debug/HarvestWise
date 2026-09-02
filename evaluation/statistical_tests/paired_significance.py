"""
Paired significance test: RL harvest policy vs. static multi-objective
optimizer, evaluated on the SAME held-out season trajectories. This is the
evidence that the RL policy's improvement is real, not noise - required
before claiming it as a novelty contribution (see project novelty checklist).
"""

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class SignificanceResult:
    n_pairs: int
    mean_rl: float
    mean_static: float
    mean_diff: float
    wilcoxon_statistic: float
    p_value: float
    cohens_d: float
    significant_at_05: bool


def compare_policies(rl_outcomes: list[float], static_outcomes: list[float], alpha: float = 0.05) -> SignificanceResult:
    """rl_outcomes[i] and static_outcomes[i] must come from the SAME
    trajectory i (paired), e.g. realized yield under each policy's chosen
    harvest week for the same season."""
    if len(rl_outcomes) != len(static_outcomes):
        raise ValueError("rl_outcomes and static_outcomes must be the same length (paired).")
    if len(rl_outcomes) < 5:
        raise ValueError("Need at least 5 paired trajectories for a meaningful test - aim for 30+.")

    rl = np.array(rl_outcomes)
    static = np.array(static_outcomes)
    diff = rl - static

    statistic, p_value = stats.wilcoxon(rl, static)

    pooled_std = np.sqrt((diff.std(ddof=1) ** 2))
    cohens_d = diff.mean() / pooled_std if pooled_std > 0 else 0.0

    return SignificanceResult(
        n_pairs=len(rl_outcomes),
        mean_rl=float(rl.mean()),
        mean_static=float(static.mean()),
        mean_diff=float(diff.mean()),
        wilcoxon_statistic=float(statistic),
        p_value=float(p_value),
        cohens_d=float(cohens_d),
        significant_at_05=bool(p_value < alpha),
    )
