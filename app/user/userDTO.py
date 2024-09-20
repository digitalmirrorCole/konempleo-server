from datetime import datetime
from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, EmailStr

from models.models import UserEnum


class UserBase(BaseModel):
    fullname: str
    email: EmailStr
    role: UserEnum
    active: bool

class UserAdminCreateDTO(BaseModel):
    fullname: str
    email: EmailStr
    role: UserEnum
    phone: Optional[str] = None

class UserCreateDTO(BaseModel):
    fullname: str
    email: EmailStr
    role: Optional[UserEnum] = 4
    phone: Optional[str] = None

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