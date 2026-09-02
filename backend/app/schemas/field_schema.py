from pydantic import BaseModel


class Field(BaseModel):
    field_id: str
    name: str
    region: str
    crop: str
    area_ha: float
