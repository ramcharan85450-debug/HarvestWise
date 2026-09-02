from pydantic import BaseModel


class Explanation(BaseModel):
    field_id: str
    summary: str
    driving_factor: str
    threshold_mm: float
    forecast_mm: float
