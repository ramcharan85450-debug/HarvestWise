"""
Quantile regression head: from each week's backbone hidden state, predicts
(10th, 50th, 90th) percentile yield - the uncertainty band shown on the
dashboard's yield forecast chart. Trained with pinball (quantile) loss,
not MSE, so the low/high outputs are genuine quantiles rather than an
arbitrary +/-15% band (which is what the placeholder backend logic uses
today - see backend/app/services/forecast_service.py).
"""

import torch
import torch.nn as nn

QUANTILES = (0.1, 0.5, 0.9)


class YieldForecastHead(nn.Module):
    def __init__(self, embed_dim: int = 64, quantiles: tuple[float, ...] = QUANTILES):
        super().__init__()
        self.quantiles = quantiles
        self.net = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, len(quantiles)),
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """hidden_states: (batch, seq_len, embed_dim) -> (batch, seq_len, len(quantiles))"""
        raw = self.net(hidden_states)
        # enforce low <= median <= high by construction (cumulative positive offsets)
        low = raw[..., 0]
        median = low + torch.nn.functional.softplus(raw[..., 1])
        high = median + torch.nn.functional.softplus(raw[..., 2])
        return torch.stack([low, median, high], dim=-1)


def pinball_loss(preds: torch.Tensor, target: torch.Tensor, quantiles: tuple[float, ...] = QUANTILES) -> torch.Tensor:
    """preds: (..., len(quantiles)), target: (...,) - standard quantile/pinball loss."""
    target = target.unsqueeze(-1)
    errors = target - preds
    q = torch.tensor(quantiles, device=preds.device, dtype=preds.dtype)
    loss = torch.maximum(q * errors, (q - 1) * errors)
    return loss.mean()
