from pydantic import BaseModel

class CargoResponseDTO(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True  # This tells Pydantic to convert SQLAlchemy models to Pydantic models
