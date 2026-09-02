from pydantic import BaseModel


class SeasonOutcome(BaseModel):
    season: str
    recommended_window: str
    actual_harvest_date: str
    actual_yield_t_ha: float
    fixed_date_baseline_yield_t_ha: float
