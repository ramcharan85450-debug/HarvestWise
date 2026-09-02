"""
Learns temporal patterns across the fused weekly embeddings for one field's
season (e.g. "yield tends to drop when a dry spell follows flowering").
A Transformer encoder over the season sequence, with sinusoidal positional
encoding for week-of-season order.
"""

import math

import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, embed_dim: int, max_len: int = 60):
        super().__init__()
        pe = torch.zeros(max_len, embed_dim)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, embed_dim, 2).float() * (-math.log(10000.0) / embed_dim))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class SpatioTemporalBackbone(nn.Module):
    """Causal by default: week t's hidden state attends only to weeks 0..t.

    This is not a stylistic choice, it is what makes the model's output a
    forecast at all. Without the mask, nn.TransformerEncoder does full
    bidirectional attention, so the "week 3 forecast" is computed from
    satellite and weather observations in weeks 4-19 - data that does not
    exist when a grower needs the week 3 answer. Measured on the real F004
    2025 season with the previous bidirectional checkpoint: corrupting only
    the FINAL week's inputs moved the WEEK 0 prediction by 1.3e-3 t/ha, which
    under a causal model must be exactly zero.

    It also explains why that model's weekly curve was almost flat (a 0.9%
    spread across a 20-week season). Every position could see the whole
    season and every position's training target is the same scalar - the
    season's final yield - so emitting one constant value at every week is
    the loss-optimal solution. A flat curve then makes the downstream harvest
    -timing decision meaningless: both the RL policy and the static optimizer
    were choosing a week from a curve that barely varied, leaving the choice
    to the rainfall term and to noise.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        num_layers: int = 3,
        num_heads: int = 4,
        ff_dim: int = 128,
        dropout: float = 0.1,
        causal: bool = True,
    ):
        super().__init__()
        self.causal = causal
        self.pos_encoding = PositionalEncoding(embed_dim)
        layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=ff_dim,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)

    def forward(self, fused_seq: torch.Tensor, key_padding_mask: torch.Tensor | None = None) -> torch.Tensor:
        """
        fused_seq: (batch, seq_len, embed_dim) - output of PhenologyAwareFusion
        key_padding_mask: (batch, seq_len) bool, True at padded positions (for
        fields with a shorter observed history than max_len)
        Returns: (batch, seq_len, embed_dim) - per-week hidden states, used
        by both the yield forecast head (weekly quantiles) and as season
        context for the RL harvest policy's state.
        """
        x = self.pos_encoding(fused_seq)
        attn_mask = None
        if self.causal:
            attn_mask = nn.Transformer.generate_square_subsequent_mask(
                x.size(1), device=x.device, dtype=x.dtype
            )
        return self.encoder(x, mask=attn_mask, src_key_padding_mask=key_padding_mask)
