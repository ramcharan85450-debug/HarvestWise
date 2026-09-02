from pydantic import BaseModel


class HarvestWindow(BaseModel):
    field_id: str
    window_start: str  # ISO date
    window_end: str  # ISO date
    confidence: float  # 0-1
    recommended_by: str  # "RL adaptive policy" | "Static multi-objective optimizer"
    expected_yield_t_ha: float
