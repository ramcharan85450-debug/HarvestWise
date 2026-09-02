"""
Domain-adversarial training for cross-climate-zone generalization (the
adopted-infrastructure piece, not a claimed novelty - see project notes:
this technique already exists in prior work like ADANN).

A gradient-reversal layer flips the sign of the gradient flowing back from a
"which climate year-type is this?" classifier, so the backbone is pushed to
produce features that a climate-domain classifier CANNOT tell apart -
i.e. features that generalize across normal/drought/heatwave/shifted-monsoon
years rather than overfitting to one.
"""

import torch
import torch.nn as nn
from torch.autograd import Function


class _GradientReversal(Function):
    @staticmethod
    def forward(ctx, x: torch.Tensor, lambda_: float):
        ctx.lambda_ = lambda_
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):
        return -ctx.lambda_ * grad_output, None


def gradient_reversal(x: torch.Tensor, lambda_: float = 1.0) -> torch.Tensor:
    return _GradientReversal.apply(x, lambda_)


class ClimateDomainClassifier(nn.Module):
    """Predicts which climate-year type (normal / drought / heatwave /
    shifted-monsoon) a season's pooled backbone representation came from.
    Trained adversarially against the backbone via gradient_reversal()."""

    def __init__(self, embed_dim: int = 64, num_domains: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, num_domains),
        )

    def forward(self, pooled_season_embed: torch.Tensor, lambda_: float = 1.0) -> torch.Tensor:
        reversed_embed = gradient_reversal(pooled_season_embed, lambda_)
        return self.net(reversed_embed)
