"""Per-week weather encoder. Embeds each week's aggregated weather features
(temp, precipitation, humidity, wind) - temporal patterns across weeks are
left to models/backbone/, not learned here."""

import torch
import torch.nn as nn


class WeatherEncoder(nn.Module):
    def __init__(self, in_features: int = 4, embed_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 48),
            nn.GELU(),
            nn.Linear(48, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, in_features) -> (batch, seq_len, embed_dim)"""
        return self.net(x)
