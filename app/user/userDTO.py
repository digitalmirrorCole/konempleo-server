from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from models.models import UserEnum


class UserBase(BaseModel):
    fullname: str
    email: EmailStr
    role: UserEnum
    active: bool
    suspended: bool
    phone: Optional[str] = None
    companies: List[str] = []

class UserAdminCreateDTO(BaseModel):
    fullname: str
    email: EmailStr
    role: UserEnum
    phone: Optional[str] = None

class UserCreateResponseDTO(BaseModel):
    fullname: str
    email: str
    role: UserEnum

class UserCreateDTO(BaseModel):
    fullname: str
    email: EmailStr
    role: Optional[UserEnum] = 4
    phone: Optional[str] = None

class UserUpdateDTO(BaseModel):
    fullname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[UserEnum] = None

class UserInsert(BaseModel):
    fullname: str
    email: EmailStr
    password: str
    role: UserEnum

class UserUpdateUser(BaseModel):
    fullname: str

class UserSoftDelete(BaseModel):
    active: bool

# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: int

    class Config:
        orm_mode: True

# Properties to return to client
class User(UserInDBBase):
    pass


# Properties properties stored in DB
class UserInDB(UserInDBBase):
    pass