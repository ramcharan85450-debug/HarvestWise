"""
Plots the phenology-aware fusion gate's attention weights (models/fusion/
phenology_attention.py returns them alongside the fused embedding) across
a season - the evidence for the "fusion weights conditioned on growth stage,
visualized" novelty item.
"""

import matplotlib.pyplot as plt
import numpy as np


def plot_attention_over_season(attn_weights: np.ndarray, growth_stage: np.ndarray, out_path: str, field_label: str = ""):
    """attn_weights: (T, 2) -> columns are [vision_weight, weather_weight].
    growth_stage: (T,) in [0, 1]."""
    fig, ax1 = plt.subplots(figsize=(8, 4))

    weeks = np.arange(len(growth_stage))
    ax1.stackplot(
        weeks,
        attn_weights[:, 0],
        attn_weights[:, 1],
        labels=["vision (imagery)", "weather"],
        colors=["#2F6E52", "#35647F"],
        alpha=0.85,
    )
    ax1.set_xlabel("Week of season")
    ax1.set_ylabel("Fusion attention weight")
    ax1.set_ylim(0, 1)
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(weeks, growth_stage, color="#A9782B", linestyle="--", linewidth=1.5, label="growth stage")
    ax2.set_ylabel("Growth stage (0=planting, 1=maturity)")
    ax2.set_ylim(0, 1)

    ax1.set_title(f"Phenology-aware fusion weights{' — ' + field_label if field_label else ''}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"saved -> {out_path}")
