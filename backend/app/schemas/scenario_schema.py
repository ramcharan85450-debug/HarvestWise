from pydantic import BaseModel

from app.schemas.forecast_schema import ForecastPoint


class ScenarioResult(BaseModel):
    field_id: str
    temp_shift_c: float
    rainfall_change_pct: float
    baseline_forecast: list[ForecastPoint]
    scenario_forecast: list[ForecastPoint]
    scenario_confidence: float
    scenario_window_shift_days: int
