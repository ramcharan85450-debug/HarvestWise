"""
Training loop and metrics for the district-level pipeline.

Separate from training/train_forecast_model.py (the field-level trainer);
that module and its checkpoints are untouched.

THE TEST SET IS NEVER CONSULTED DURING TRAINING. Early stopping watches the
VALIDATION loss only, the restored "best" weights are chosen by VALIDATION
loss only, and `evaluate()` is called on the test split exactly once per
(seed, configuration) pair, after training has finished. There is no code
path in this module that reads test labels before that point - see
`train_model()`'s signature: it does not accept a test dataset at all.
"""

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch.utils.data import DataLoader

from training.district_model import DistrictMLP


def set_seed(seed: int) -> None:
    """Deterministic where practical. torch.use_deterministic_algorithms is
    deliberately not forced: on CPU the ops used here (Linear/ReLU/Dropout/
    Adam) are already deterministic given the seeds below, and forcing the
    global flag would raise on unrelated ops elsewhere in the project."""
    torch.manual_seed(seed)
    np.random.seed(seed)


def train_model(
    train_ds,
    val_ds,
    *,
    seed: int,
    epochs: int = 300,
    batch_size: int = 32,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    patience: int = 30,
    hidden_dims: tuple[int, ...] = (32, 16),
    dropout: float = 0.2,
) -> tuple[DistrictMLP, dict]:
    """Trains one model. Returns (model with best-validation weights restored,
    training history).

    NOTE the absence of a `test_ds` parameter: this function cannot see test
    data even accidentally.
    """
    set_seed(seed)
    n_features = train_ds.X.shape[1]
    model = DistrictMLP(n_features, hidden_dims=hidden_dims, dropout=dropout)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.MSELoss()

    generator = torch.Generator()
    generator.manual_seed(seed)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, generator=generator)

    best_val = float("inf")
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    best_epoch = 0
    epochs_without_improvement = 0
    history = {"train_loss": [], "val_loss": []}

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss, n_batches = 0.0, 0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.item())
            n_batches += 1

        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(val_ds.X), val_ds.y).item())

        history["train_loss"].append(epoch_loss / max(n_batches, 1))
        history["val_loss"].append(val_loss)

        # Early stopping and checkpoint selection: VALIDATION loss only.
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    history["best_epoch"] = best_epoch
    history["best_val_loss"] = best_val
    history["epochs_run"] = epoch
    history["selected_by"] = "validation loss only (test set not consulted)"
    return model, history


def predict(model: DistrictMLP, ds) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(ds.X).squeeze(1).numpy()


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE / RMSE / R². R² is undefined when the truth vector has zero
    variance (possible if a tiny test fold happens to hold one district-year
    with a single repeated value); returned as None in that case rather than
    as a misleading number."""
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred)) if y_true.size > 1 and np.var(y_true) > 1e-12 else None
    return {"mae": mae, "rmse": rmse, "r2": r2, "n": int(y_true.size)}
