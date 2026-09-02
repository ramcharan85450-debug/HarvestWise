"""
Central configuration. Reads from environment variables so the same code runs
locally, in Colab-trained-checkpoint mode, and in a future deployment without edits.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# The repository root, i.e. the parent of backend/. Put it on sys.path so the
# serving layer can import the SAME ingestion/, training/ and models/ code the
# research pipeline uses, rather than keeping a second, drifting copy of the
# field registry, the input normalisation constants and the model definition.
# That duplication is exactly how a served forecast silently stops matching the
# forecast the paper reports: the checkpoint is trained under
# training/dataset.py's standardisation, so inference MUST use the same
# function, not a reimplementation of it.
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Where trained model checkpoints live after training (see
# training/train_forecast_model.py and models/heads/rl_harvest_policy/train_rl.py,
# both of which write here directly). model_loader.py checks this path.
MODEL_CHECKPOINT_DIR = Path(os.environ.get("HARVESTWISE_CHECKPOINT_DIR", BASE_DIR / "checkpoints"))

# Real evaluation artefacts. Services read these instead of hardcoding results,
# so a number shown on the dashboard is always traceable to an actual
# evaluation run that can be re-executed.
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
HARVEST_OUTCOMES_DIR = PROJECT_ROOT / "data" / "raw" / "harvest_outcomes"
CLIMATE_SHOCK_RESULTS = PROJECT_ROOT / "evaluation" / "climate_shock_benchmark" / "results.json"

CORS_ALLOW_ORIGINS = os.environ.get("HARVESTWISE_CORS_ORIGINS", "*").split(",")

APP_TITLE = "HarvestWise API"
APP_VERSION = "0.1.0"
