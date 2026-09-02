"""
Phenology-aware cross-attention fusion.

Growth stage (0=planting, 1=maturity, from ingestion/align_pipeline.py) is
embedded into a query that attends over the two modality embeddings
(vision, weather) as key/value tokens. The resulting attention weights are
exactly the "how much to trust imagery vs. weather at this point in the
season" signal described in the project architecture - returned alongside
the fused embedding so evaluation/explainability/attention_visualization.py
can plot them.
"""

import torch
import torch.nn as nn


class PhenologyAwareFusion(nn.Module):
    def __init__(self, embed_dim: int = 64, num_heads: int = 4):
        super().__init__()
        self.stage_query = nn.Sequential(
            nn.Linear(1, 32),
            nn.GELU(),
            nn.Linear(32, embed_dim),
        )
        self.attn = nn.MultiheadAttention(embed_dim, num_heads=num_heads, batch_first=True)
        self.soil_proj = nn.Linear(embed_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        vision_emb: torch.Tensor,
        weather_emb: torch.Tensor,
        soil_emb: torch.Tensor,
        growth_stage: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        vision_emb, weather_emb: (batch, seq_len, embed_dim)
        soil_emb: (batch, embed_dim) - constant per field, broadcast across weeks
        growth_stage: (batch, seq_len) in [0, 1]
        Returns: (fused_emb (batch, seq_len, embed_dim), attn_weights (batch, seq_len, 2))
        """
        b, t, d = vision_emb.shape

        query = self.stage_query(growth_stage.unsqueeze(-1))  # (b, t, d)
        modality_stack = torch.stack([vision_emb, weather_emb], dim=2)  # (b, t, 2, d)

        query_flat = query.reshape(b * t, 1, d)
        kv_flat = modality_stack.reshape(b * t, 2, d)

        attn_out, attn_weights = self.attn(query_flat, kv_flat, kv_flat, need_weights=True)
        fused = attn_out.view(b, t, d)
        attn_weights = attn_weights.view(b, t, 2)  # [vision_weight, weather_weight] per week

        fused = fused + self.soil_proj(soil_emb).unsqueeze(1)
        fused = self.norm(fused)

        return fused, attn_weights
