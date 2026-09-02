"""Static soil-property encoder. Soil doesn't change week to week (see
ingestion/soil_fetch.py), so this embeds once per field and is broadcast
across every week before fusion."""

import torch
import torch.nn as nn


class SoilEncoder(nn.Module):
    def __init__(self, in_features: int = 5, embed_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 32),
            nn.GELU(),
            nn.Linear(32, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, in_features) -> (batch, embed_dim)"""
        return self.net(x)
