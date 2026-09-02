from fastapi import APIRouter, HTTPException, Query

from app.schemas.scenario_schema import ScenarioResult
from app.services.data_service import get_field
from app.services.scenario_service import get_scenario

router = APIRouter(tags=["scenario"])


@router.get("/scenario/{field_id}", response_model=ScenarioResult)
def get_scenario_route(
    field_id: str,
    temp_shift_c: float = Query(0.0, ge=0.0, le=4.0, description="Temperature increase in degrees C"),
    rainfall_change_pct: float = Query(0.0, ge=-40.0, le=20.0, description="Rainfall change in percent"),
):
    if get_field(field_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown field_id '{field_id}'")
    return get_scenario(field_id, temp_shift_c, rainfall_change_pct)
