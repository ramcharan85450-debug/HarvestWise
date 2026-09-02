"""
Per-week vision encoder.

Two variants, chosen by what ingestion actually produced:

- VegetationIndexEncoder (default): ingestion/satellite_fetch.py exports
  mean NDVI, EVI, and NDWI per week (cheap on a student Earth Engine quota -
  no image download). NDVI tracks general vegetation vigor, EVI stays
  sensitive in dense canopy where NDVI saturates, and NDWI captures
  vegetation water content - a distinct drought-stress signal neither of the
  other two directly measures. This encoder takes
  [ndvi, ndvi_week_over_week_delta, evi, ndwi] and embeds it with a small
  MLP. This is the honest starting point given the current pipeline.

- TileCNNEncoder: for when ingestion/satellite_fetch.py's export_tile() has
  been used to pull real multispectral GeoTIFF crops (heavier on quota/storage,
  needs a Dataset that loads them - not built yet, see the TODO below). Swap
  it in later without touching the fusion/backbone code, since both encoders
  output the same embed_dim.
"""

import torch
import torch.nn as nn


class VegetationIndexEncoder(nn.Module):
    def __init__(self, in_features: int = 4, embed_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 32),
            nn.GELU(),
            nn.Linear(32, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, in_features) -> (batch, seq_len, embed_dim)"""
        return self.net(x)


class TileCNNEncoder(nn.Module):
    """CNN over raw multispectral tiles. Requires timm and a tile-loading
    Dataset (TODO: build data/processed tile loader once export_tile() output
    has been synced from Google Drive - see ingestion/satellite_fetch.py)."""

    def __init__(self, in_channels: int = 4, embed_dim: int = 64, backbone_name: str = "resnet18"):
        super().__init__()
        import timm

        self.backbone = timm.create_model(
            backbone_name, pretrained=True, in_chans=in_channels, num_classes=0
        )
        self.proj = nn.Linear(self.backbone.num_features, embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, C, H, W) -> (batch, seq_len, embed_dim)"""
        b, t, c, h, w = x.shape
        feats = self.backbone(x.view(b * t, c, h, w))
        feats = self.proj(feats)
        return feats.view(b, t, -1)
