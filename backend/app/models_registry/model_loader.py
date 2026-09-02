"""
Single point of contact between the API layer and the trained model files.

Loads the checkpoints written by training/train_forecast_model.py and
models/heads/rl_harvest_policy/train_rl.py, and caches them for the process
lifetime so each request is a forward pass, not a re-load from disk.

Everything here degrades honestly: if a checkpoint or a heavy optional
dependency (torch, stable-baselines3) is missing, the loader returns None and
the calling service says so in its response rather than substituting an
invented number.
"""

from functools import lru_cache
from pathlib import Path

from app.config import MODEL_CHECKPOINT_DIR

# The two checkpoints that real inference genuinely requires. Both are written
# by a single run of `python -m training.train_forecast_model`.
REQUIRED_CHECKPOINTS = {
    "fusion_backbone": "fusion_backbone.pt",
    "yield_head": "yield_head.pt",
}

# Present-if-trained, but the API is still fully real without them: the
# harvest-window service falls back to models/heads/static_harvest_optimizer.py,
# which is a deterministic grid search needing no checkpoint at all.
OPTIONAL_CHECKPOINTS = {
    "rl_harvest_policy": "rl_harvest_policy.zip",  # stable-baselines3 save format
}

EXPECTED_CHECKPOINTS = {**REQUIRED_CHECKPOINTS, **OPTIONAL_CHECKPOINTS}


def available_checkpoints() -> dict[str, bool]:
    return {
        name: (MODEL_CHECKPOINT_DIR / filename).exists()
        for name, filename in EXPECTED_CHECKPOINTS.items()
    }


def models_are_live() -> bool:
    """True once the forecast model can actually be loaded and run.

    This deliberately checks REQUIRED_CHECKPOINTS only. It previously required
    a `static_optimizer_config.json` that no training script ever writes -
    the static optimizer is pure code with documented default coefficients,
    it has nothing to serialise - so this predicate could never become true
    and every service stayed on placeholder logic even with real trained
    checkpoints sitting in backend/checkpoints/.
    """
    return all((MODEL_CHECKPOINT_DIR / f).exists() for f in REQUIRED_CHECKPOINTS.values())


def checkpoint_path(name: str) -> Path:
    if name not in EXPECTED_CHECKPOINTS:
        raise KeyError(f"Unknown checkpoint '{name}'. Expected one of {list(EXPECTED_CHECKPOINTS)}.")
    return MODEL_CHECKPOINT_DIR / EXPECTED_CHECKPOINTS[name]


@lru_cache(maxsize=1)
def load_forecast_model():
    """Returns the trained ForecastModel in eval mode, or None if it cannot be
    loaded. Cached: the checkpoint is ~570 KB and reloading it per request
    would dominate response time.

    Imports are deliberately inside the function - torch is a heavy optional
    dependency of the serving layer, and the API must still start (and report
    models_live=false) on a machine that only has the light requirements
    installed.
    """
    if not models_are_live():
        return None
    try:
        import torch

        from training.train_forecast_model import ForecastModel
    except ImportError:
        return None

    model = ForecastModel()
    ckpt = torch.load(checkpoint_path("fusion_backbone"), map_location="cpu")
    model.vision_enc.load_state_dict(ckpt["vision_enc"])
    model.weather_enc.load_state_dict(ckpt["weather_enc"])
    model.soil_enc.load_state_dict(ckpt["soil_enc"])
    model.fusion.load_state_dict(ckpt["fusion"])
    model.backbone.load_state_dict(ckpt["backbone"])
    model.head.load_state_dict(torch.load(checkpoint_path("yield_head"), map_location="cpu"))
    model.eval()
    return model


@lru_cache(maxsize=1)
def load_rl_policy():
    """Returns the trained PPO harvest-timing policy, or None if the
    checkpoint or stable-baselines3 is unavailable. Callers fall back to the
    static optimizer, which is the same baseline the RL policy is measured
    against in evaluation/statistical_tests/run_rl_vs_static.py."""
    path = checkpoint_path("rl_harvest_policy")
    if not path.exists():
        return None
    try:
        from stable_baselines3 import PPO
    except ImportError:
        return None
    return PPO.load(str(path), device="cpu")
