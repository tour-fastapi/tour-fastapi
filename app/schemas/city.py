from pydantic import BaseModel

class CityCreate(BaseModel):
    name: str

class CityOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
