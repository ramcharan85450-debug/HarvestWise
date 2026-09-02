from fastapi import APIRouter, HTTPException

from app.schemas.explain_schema import Explanation
from app.services.data_service import get_field
from app.services.explain_service import get_explanation

router = APIRouter(tags=["explain"])


@router.get("/explain/{field_id}", response_model=Explanation)
def get_explanation_route(field_id: str):
    if get_field(field_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown field_id '{field_id}'")
    return get_explanation(field_id)
