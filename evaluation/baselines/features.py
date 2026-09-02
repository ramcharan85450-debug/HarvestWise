"""
Flattens a SeasonExample (training/dataset.py) into a fixed-length feature
vector for the classical ML baselines (Random Forest, XGBoost), which - unlike
the deep model - can't consume a raw weekly sequence directly.
"""

import numpy as np

from training.dataset import SeasonExample

FEATURE_NAMES = [
    "ndvi_mean", "ndvi_max", "ndvi_std", "ndvi_at_flowering",
    "evi_mean", "evi_max", "ndwi_mean", "ndwi_min",
    "temp_mean", "temp_max", "precip_total", "precip_max_week", "humidity_mean", "wind_mean",
    "soil_ph", "soil_soc", "soil_clay", "soil_sand", "soil_nitrogen",
]


def flatten(example: SeasonExample) -> np.ndarray:
    ndvi = example.vision_x[:, 0]
    evi = example.vision_x[:, 2]
    ndwi = example.vision_x[:, 3]
    weather = example.weather_x
    stage = example.growth_stage

    flowering_idx = int(np.argmin(np.abs(stage - 0.5)))

    return np.array(
        [
            ndvi.mean(), ndvi.max(), ndvi.std(), ndvi[flowering_idx],
            evi.mean(), evi.max(), ndwi.mean(), ndwi.min(),
            weather[:, 0].mean(), weather[:, 0].max(), weather[:, 1].sum(), weather[:, 1].max(),
            weather[:, 2].mean(), weather[:, 3].mean(),
            *example.soil_x,
        ],
        dtype=np.float32,
    )


def build_feature_matrix(examples: list[SeasonExample]) -> tuple[np.ndarray, np.ndarray]:
    X = np.stack([flatten(ex) for ex in examples])
    y = np.array([ex.final_yield for ex in examples], dtype=np.float32)
    return X, y
