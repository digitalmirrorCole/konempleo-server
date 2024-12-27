from typing import Optional
from pydantic import BaseModel
from enum import IntEnum

from models.models import contractEnum, shiftEnum, genderEnum, militaryEnum, licenseEnum, educationEnum


class OfferBase(BaseModel):
    name: str
    duties: Optional[str] = None
    exp_area: Optional[str] = None
    vacants: Optional[int] = None
    contract_type: Optional[contractEnum] = None
    salary: Optional[str] = None
    city: Optional[int] = None
    shift: Optional[shiftEnum] = None
    gender: Optional[genderEnum] = None
    military_notebook: Optional[militaryEnum] = None
    age: Optional[str] = None
    job_type: Optional[str] = None
    license: Optional[licenseEnum] = None
    disabled: Optional[bool] = False
    experience_years: Optional[int] = None
    offer_type: Optional[str] = None
    ed_required: Optional[educationEnum] = None
    cargoId: Optional[int] = None
    filter_questions: Optional[str] = None
    assigned_cvs: Optional[int] = 0
    whatsapp_message: Optional[str] = None
    active = Optional[bool] = True

# DTO for creating an Offer
class OfferCreateDTO(OfferBase):
    companyId: int
    pass

class OfferWithVitaeCount(OfferBase):
    id: int
    vitae_offer_count: int

# DTO for updating an Offer
class OfferUpdateDTO(BaseModel):
    assigned_cvs: Optional[int] = None
    active: Optional[bool] = None

class OfferSoftDelete(BaseModel):
    active: bool

# Properties shared by models stored in DB
class OfferInDBBase(OfferBase):
    id: int

    class Config:
        orm_mode = True

# Properties to return to client
class Offer(OfferInDBBase):
    pass

# Properties stored in DB
class OfferInDB(OfferInDBBase):
    pass
