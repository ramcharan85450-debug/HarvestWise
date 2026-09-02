from fastapi import APIRouter, HTTPException

from app.schemas.forecast_schema import ForecastPoint
from app.services.data_service import get_field
from app.services.forecast_service import get_forecast

router = APIRouter(tags=["forecast"])


@router.get("/forecast/{field_id}", response_model=list[ForecastPoint])
def get_forecast_route(field_id: str):
    if get_field(field_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown field_id '{field_id}'")
    return get_forecast(field_id)
