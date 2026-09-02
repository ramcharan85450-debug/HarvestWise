"""
Yield forecast service - real inference.

Runs the field's latest real aligned season (satellite + weather + soil, built
by ingestion/align_pipeline.py) through the trained encoders -> phenology
fusion -> spatio-temporal backbone -> quantile yield head, and returns the
predicted (low, median, high) per week.

The quantile head is trained with pinball loss at QUANTILES = 0.1/0.5/0.9, so
the low/high bounds returned here are genuine predicted quantiles, not the
median scaled by a fixed +/-15% the way the previous placeholder produced
them. That distinction matters wherever the interval is used as an uncertainty
claim.
"""

from app.models_registry.model_loader import load_forecast_model
from app.services.data_service import latest_season_example, season_weeks
from app.services.errors import RealDataUnavailable


def run_model(example, vision_x=None, weather_x=None, soil_x=None):
    """Runs one SeasonExample through the trained model and returns its (T, 3)
    quantile array. The three array arguments override the example's own
    inputs, which is how scenario_service perturbs weather without having to
    rebuild a SeasonExample."""
    model = load_forecast_model()
    if model is None:
        raise RealDataUnavailable(
            "No trained forecast checkpoint loaded. Run "
            "`python -m training.train_forecast_model` to write "
            "backend/checkpoints/{fusion_backbone.pt,yield_head.pt}."
        )

    import torch

    from training.dataset import normalize_model_inputs

    # Same standardisation the checkpoint was trained under. Importing the
    # shared function rather than re-deriving the constants is what keeps a
    # served forecast numerically identical to the evaluated one.
    vision_n, weather_n, soil_n = normalize_model_inputs(
        example.vision_x if vision_x is None else vision_x,
        example.weather_x if weather_x is None else weather_x,
        example.soil_x if soil_x is None else soil_x,
    )
    batch = {
        "vision_x": torch.from_numpy(vision_n).unsqueeze(0),
        "weather_x": torch.from_numpy(weather_n).unsqueeze(0),
        "soil_x": torch.from_numpy(soil_n).unsqueeze(0),
        "growth_stage": torch.from_numpy(example.growth_stage).unsqueeze(0),
    }
    with torch.no_grad():
        quantiles, _ = model(batch)
    return quantiles[0].numpy()


def forecast_quantiles(field_id: str):
    """Returns the raw (T, 3) quantile array plus the SeasonExample it came
    from. Shared with the harvest, explain and scenario services so all four
    endpoints describe the same underlying forecast."""
    example = latest_season_example(field_id)
    if example is None:
        raise RealDataUnavailable(
            f"No processed real season for field '{field_id}'. Run "
            "`python -m ingestion.align_pipeline` and ensure a matching row "
            "exists in data/raw/yield_labels/."
        )
    return run_model(example), example


def get_forecast(field_id: str) -> list[dict]:
    quantiles, example = forecast_quantiles(field_id)
    weeks = season_weeks(field_id) or [example.season_start_date] * len(quantiles)

    return [
        {
            "week": weeks[i],
            "yield_low": round(float(quantiles[i][0]), 3),
            "yield_median": round(float(quantiles[i][1]), 3),
            "yield_high": round(float(quantiles[i][2]), 3),
        }
        for i in range(len(quantiles))
    ]
