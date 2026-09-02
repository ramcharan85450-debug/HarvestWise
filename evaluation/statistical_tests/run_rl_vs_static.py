"""
Generates paired RL-vs-static-optimizer outcomes on the same real season
trajectories (replayed through the trained yield forecast model, see
models/heads/rl_harvest_policy/train_rl.py's load_trajectories_from_processed),
then runs the paired significance test - the real evidence needed before
claiming the RL harvest policy as a novelty contribution.

Run (after training/train_forecast_model.py and
models/heads/rl_harvest_policy/train_rl.py have both produced checkpoints):
    python -m evaluation.statistical_tests.run_rl_vs_static
"""

from pathlib import Path

from stable_baselines3 import PPO

from evaluation.statistical_tests.paired_significance import compare_policies
from models.heads.rl_harvest_policy.env import HarvestTimingEnv
from models.heads.rl_harvest_policy.train_rl import CHECKPOINT_DIR, load_trajectories_from_processed
from models.heads.static_harvest_optimizer import optimize_window


def static_outcome(traj) -> float:
    result = optimize_window(traj.weekly_median_yield, traj.weekly_rainfall_mm, window_len_weeks=1, search_start_idx=traj.min_harvest_week)
    return result.score


def rl_outcome(policy: PPO, traj) -> float:
    env = HarvestTimingEnv([traj])
    obs, _ = env.reset(seed=0)
    total_reward = 0.0
    for _ in range(len(traj.weekly_median_yield)):
        action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(int(action))
        total_reward += reward
        if terminated or truncated:
            break
    return total_reward


def main():
    policy_path = CHECKPOINT_DIR / "rl_harvest_policy.zip"
    if not policy_path.exists():
        raise RuntimeError(f"No RL policy at {policy_path} - run `python -m models.heads.rl_harvest_policy.train_rl` first.")

    trajectories = load_trajectories_from_processed(Path("data/processed"))
    policy = PPO.load(str(policy_path))

    rl_outcomes = [rl_outcome(policy, t) for t in trajectories]
    static_outcomes = [static_outcome(t) for t in trajectories]

    print(f"Paired real outcomes across {len(trajectories)} real season trajectories:")
    for i, (rl, st) in enumerate(zip(rl_outcomes, static_outcomes)):
        print(f"  trajectory {i:>2}: RL={rl:.3f}  static={st:.3f}  diff={rl - st:+.3f}")

    if len(trajectories) < 5:
        print(
            f"\nOnly {len(trajectories)} paired trajectories - too few for "
            "scipy.stats.wilcoxon (needs 5+). Report the raw paired outcomes "
            "above honestly rather than a fabricated p-value."
        )
        return

    result = compare_policies(rl_outcomes, static_outcomes)
    print(
        f"\n=== Paired significance test: RL vs. static harvest-timing optimizer ===\n"
        f"n_pairs={result.n_pairs}\n"
        f"mean RL outcome={result.mean_rl:.4f}  mean static outcome={result.mean_static:.4f}\n"
        f"mean difference (RL - static)={result.mean_diff:+.4f}\n"
        f"Wilcoxon statistic={result.wilcoxon_statistic:.3f}  p-value={result.p_value:.4f}\n"
        f"Cohen's d={result.cohens_d:.3f}\n"
        f"significant at alpha=0.05: {result.significant_at_05}\n"
        f"NOTE: only {result.n_pairs} real paired trajectories - a real but small\n"
        f"sample; treat significance/effect-size as indicative, not conclusive,\n"
        f"until more real seasons are added."
    )


if __name__ == "__main__":
    main()
