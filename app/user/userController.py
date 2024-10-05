from sqlite3 import IntegrityError
import traceback
from fastapi import APIRouter, Body, Depends, HTTPException
from app.auth.authDTO import UserToken
from app.auth.authService import get_password_hash, get_user_current
from app.user.userService import userServices
from app.user.userDTO import User, UserAdminCreateDTO, UserCreateDTO, UserCreateResponseDTO, UserInsert, UserUpdateDTO
from sqlalchemy.orm import Session
from app import deps
from typing import List

from models.models import CompanyUser, UserEnum, Users


userRouter = APIRouter()
userRouter.tags = ['User']

@userRouter.post("/user/admin/", status_code=201, response_model=UserCreateResponseDTO)
def create_user(
    *, user_in: UserAdminCreateDTO, db: Session = Depends(deps.get_db), userToken: UserToken = Depends(get_user_current)
) -> dict:
    
    """
    Create a new admin user in the database.
    """  
    if userToken.role != UserEnum.super_admin :
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    if user_in.role not in [UserEnum.super_admin, UserEnum.admin]:
        raise HTTPException(status_code=400, detail="The user role must be either super_admin or admin.")
    
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

@userRouter.put("/user/{user_id}", response_model=None)
def update_user(
    user_id: int,
    user_in: UserUpdateDTO = Body(...),
    db: Session = Depends(deps.get_db),
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Update an existing user in the database.
    """
    # Ensure only authorized users can update (e.g., super_admin or user themselves)
    if userToken.role != UserEnum.super_admin and userToken.id != user_id:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Fetch the user by ID
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Dynamically update fields if they are provided
    fields_to_update = ['fullname', 'email', 'phone', 'role']
    for field in fields_to_update:
        value = getattr(user_in, field, None)
        if value is not None:
            setattr(user, field, value)

    # Commit the changes
    try:
        db.commit()
        db.refresh(user)
        return {"msg": "User updated successfully"}
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error occurred while updating the user.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="An error occurred while updating the user.")


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

@userRouter.get("/users/company/{company_id}", status_code=200, response_model=List[User])
def get_users_by_company(
    company_id: int, 
    db: Session = Depends(deps.get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Get all users associated with a given company.
    """
    # Check if the requesting user has the required permissions
    if userToken.role not in [UserEnum.super_admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    try:
        # Query to get all users related to the given company
        users = db.query(Users).join(CompanyUser).filter(CompanyUser.companyId == company_id).all()

        if not users:
            raise HTTPException(status_code=404, detail=f"No users found for company ID: {company_id}")

        return users

    except Exception as e:
        print(f"Error occurred while fetching users for company ID {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching users for the company")
