from fastapi import APIRouter, HTTPException

from app.schemas.harvest_schema import HarvestWindow
from app.services.data_service import get_field
from app.services.harvest_service import get_harvest_window

router = APIRouter(tags=["harvest"])


@router.get("/harvest-window/{field_id}", response_model=HarvestWindow)
def get_harvest_window_route(field_id: str):
    if get_field(field_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown field_id '{field_id}'")
    return get_harvest_window(field_id)
