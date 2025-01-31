from datetime import datetime
from typing import Optional
from fastapi import File, UploadFile
from pydantic import BaseModel, EmailStr, Extra, StrictBytes

from app.user.userDTO import UserCreateDTO


class CompanyBase(BaseModel):
    name: str
    sector: str
    document: str
    document_type: str
    city: str
    picture: Optional[str] = None
    activeoffers: Optional[int] = 0
    totaloffers: Optional[int] = 0
    availableoffers: Optional[int] = 0
    active: bool = True
    is_deleted: bool = False
    employees: int

class CompanyCreate(BaseModel):
    name: str
    sector: str
    document: str
    document_type: str
    city: str
    activeoffers: Optional[int] = 0
    totaloffers: Optional[int] = 0
    employees: Optional[int] = 0
    availableoffers: Optional[int] = 0
    konempleo_responsible: int
    responsible_user: UserCreateDTO

class CompanyUpdate(BaseModel,extra = Extra.forbid):
    name: Optional[str] = None
    sector: Optional[str] = None
    document: Optional[str] = None
    document_type: Optional[str] = None
    city: Optional[str] = None
    employees: Optional[int] = None
    activeoffers: Optional[int] = None
    availableoffers: Optional[int] = None
    totaloffers: Optional[int] = None
    konempleo_responsible: Optional[int] = None
    responsible_user: Optional[UserCreateDTO] = None
    is_deleted: Optional[bool] = None
    active: Optional[bool] = None
    
class CompanySoftDelete(BaseModel):
    deleted: bool
    active: bool

# Properties shared by models stored in DB
class CompanyInDBBase(CompanyBase):
    id: int

    class Config:
        orm_mode: True

# Properties shared by models stored in DB
class CompanyInDBBaseWCount(CompanyBase):
    id: int
    cv_count: int
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    total_contacted: int = 0
    total_interested: int = 0

    class Config:
        orm_mode: True

# Properties shared by models stored in DB
class CompanyInDBBaseWCountWRecruiter(CompanyBase):
    id: int
    cv_count: int
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    total_contacted: int = 0
    total_interested: int = 0

    class Config:
        orm_mode: True

# Properties to return to client
class Company(CompanyInDBBase):
    pass

# Properties to return to client
class CompanyWCount(CompanyInDBBaseWCount):
    pass

# Properties to return to client
class CompanyWCountWithRecruiter(CompanyInDBBaseWCountWRecruiter):
    pass

# Properties properties stored in DB
class CompanyInDB(CompanyInDBBase):
    pass
