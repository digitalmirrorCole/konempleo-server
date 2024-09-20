from sqlite3 import IntegrityError
import traceback
from fastapi import APIRouter, Depends, HTTPException
from app.auth.authDTO import UserToken
from app.auth.authService import get_password_hash, get_user_current
from app.user.userService import userServices
from app.user.userDTO import User, UserAdminCreateDTO, UserCreateDTO, UserInsert
from sqlalchemy.orm import Session
from app import deps
from typing import List

from models.models import UserEnum


userRouter = APIRouter()
userRouter.tags = ['User']

@userRouter.post("/user/admin/", status_code=201, response_model=None)
def create_user(
    *, user_in: UserAdminCreateDTO, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    
    """
    Create a new admin user in the database.
    """  
    if userToken.role != UserEnum.super_admin :
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    try:
        # Attempt to create the user
        user = userServices.create(
            db=db, 
            obj_in=UserInsert(**{
                'fullname': user_in.fullname,
                'email': user_in.email,
                'password': get_password_hash('deeptalent'),
                'role': user_in.role,
            })
        )
        return user
    
    except IntegrityError as e:
        # Handle database integrity errors (e.g., unique constraint violations)
        db.rollback()  # Rollback the transaction to avoid partial inserts
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    except Exception as e:
        # Handle other unforeseen errors
        print(f"Error occurred in create_user function: {str(e)}")
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An error occurred while creating the user.")
    
@userRouter.post("/user/", status_code=201, response_model=None)
def create_user(
    *, user_in: UserCreateDTO, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    
    """
    Create a new user in the database.
    """  
    if userToken.role != UserEnum.company :
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    try:
        # Attempt to create the user
        user = userServices.create(
            db=db, 
            obj_in=UserInsert(**{
                'fullname': user_in.fullname,
                'email': user_in.email,
                'password': get_password_hash('deeptalent'),
                'role': UserEnum.company_recruit,
            })
        )
        return user
    
    except IntegrityError as e:
        # Handle database integrity errors (e.g., unique constraint violations)
        db.rollback()  # Rollback the transaction to avoid partial inserts
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    except Exception as e:
        # Handle other unforeseen errors
        print(f"Error occurred in create_user function: {str(e)}")
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An error occurred while creating the user.")


@userRouter.get("/users/", status_code=200, response_model=List[User])
def get_users(
    *, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    gets users in the database.
    """
    users = []
    if userToken.role not in [UserEnum.super_admin, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    try:
        users = userServices.get_multi(db=db)
        return users
    
    except Exception as e:
        print(f"Error occurred in create_user function: {str(e)}")
        raise HTTPException(status_code=500, detail="Error Fetching the clients")