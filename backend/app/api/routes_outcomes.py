from fastapi import APIRouter, HTTPException

from app.schemas.outcome_schema import SeasonOutcome
from app.services.data_service import get_field
from app.services.outcome_service import get_outcomes

router = APIRouter(tags=["outcomes"])


@router.get("/outcomes/{field_id}", response_model=list[SeasonOutcome])
def get_outcomes_route(field_id: str):
    if get_field(field_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown field_id '{field_id}'")
    return get_outcomes(field_id)
