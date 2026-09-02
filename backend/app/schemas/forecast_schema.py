from pydantic import BaseModel


class ForecastPoint(BaseModel):
    week: str  # ISO date string
    yield_low: float
    yield_median: float
    yield_high: float
