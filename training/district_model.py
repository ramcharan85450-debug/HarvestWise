"""
The district-level regression model: a deliberately small MLP.

This is a SEPARATE model from models/ (the field-level fusion backbone,
phenology cross-attention and quantile head). Nothing here touches that
architecture or its checkpoints.

WHY SMALL, DOCUMENTED RATHER THAN ASSUMED
-----------------------------------------
The district dataset has 561 examples and at most 12 features. Under the
unseen-district split roughly 340 examples reach training. A large network
on 340 rows and 12 columns would fit the training districts almost exactly
and tell us nothing about generalization to new districts, which is the
entire question being asked. The default below has

    12 -> 32 -> 16 -> 1

which is ~950 parameters for the widest (full multimodal) configuration -
comfortably fewer than the number of training rows, and small enough that
the result reflects the signal in the features rather than the capacity of
the network. `hidden_dims` is a constructor argument rather than a
hardcoded constant so the same class serves the 3-feature satellite-only
configuration without a second model definition.

ARCHITECTURE
------------
    Input(n_features)
      -> Linear(n_features, 32) -> ReLU -> Dropout(p)
      -> Linear(32, 16)         -> ReLU -> Dropout(p)
      -> Linear(16, 1)

Dropout is applied after each hidden activation (not after the output).
No batch normalization: with batches this small its running statistics are
noisy, and it would also mix information across examples within a batch,
which complicates the leakage story for no accuracy benefit at this scale.
"""

import torch
import torch.nn as nn


class DistrictMLP(nn.Module):
    def __init__(self, n_features: int, hidden_dims: tuple[int, ...] = (32, 16), dropout: float = 0.2):
        super().__init__()
        if n_features < 1:
            raise ValueError(
                "DistrictMLP needs at least one feature. The `baseline` configuration "
                "predicts the training mean and must not be routed through this model."
            )
        layers: list[nn.Module] = []
        prev = n_features
        for h in hidden_dims:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)
        self.config = {
            "n_features": n_features,
            "hidden_dims": list(hidden_dims),
            "dropout": dropout,
            "n_parameters": sum(p.numel() for p in self.parameters()),
        }

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TrainMeanBaseline:
    """Predicts the mean of the TRAINING labels for every row.

    Not a torch module on purpose - it has no parameters to learn and no
    input to read, which makes it structurally impossible for it to see a
    test feature. `fit` records how many labels it averaged so the audit can
    confirm the mean came from the training split alone.
    """

    def __init__(self) -> None:
        self.mean_: float | None = None
        self.n_fit_labels: int | None = None
        self.fitted_on: str | None = None

    def fit(self, y_train: torch.Tensor, split_name: str = "train") -> "TrainMeanBaseline":
        self.mean_ = float(y_train.mean().item())
        self.n_fit_labels = int(y_train.numel())
        self.fitted_on = split_name
        return self

    def predict(self, n_rows: int) -> torch.Tensor:
        if self.mean_ is None:
            raise RuntimeError("TrainMeanBaseline.predict() called before fit().")
        return torch.full((n_rows, 1), self.mean_, dtype=torch.float32)
