from fastapi import APIRouter

from app.schemas.field_schema import Field
from app.services.data_service import list_fields

router = APIRouter(tags=["fields"])


@router.get("/fields", response_model=list[Field])
def get_fields():
    return list_fields()
