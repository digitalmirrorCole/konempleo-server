from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.cargo.cargoDTO import CargoResponseDTO
from app.deps import get_db
from models.models import Cargo, UserEnum


cargoRouter = APIRouter()
cargoRouter.tags = ['Cargo']

@cargoRouter.post("/cargo/", status_code=201, response_model=None)
def create_cargo(
    *, cargos_in: List[str] = Body(...), 
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Create multiple Cargo records in the database in batches.
    """

    # Ensure that only super_admin or admin can create cargo
    if userToken.role not in [UserEnum.super_admin]:
        raise HTTPException(status_code=403, detail="No tienes permisos para ejecutar este servicio")

    batch_size = 100  # Process by batches of 100 cargos
    cargos_to_create = []

    try:
        # Step 1: Get existing cargos in bulk using IN
        existing_cargos = db.query(Cargo.name).filter(Cargo.name.in_(cargos_in)).all()
        existing_cargo_names = {cargo.name for cargo in existing_cargos}  # Create a set for fast lookups

        # Step 2: Iterate through the input cargos and filter out the existing ones
        new_cargos = [name for name in cargos_in if name not in existing_cargo_names]

        # Step 3: Create cargos in batches
        for name in new_cargos:
            new_cargo = Cargo(name=name)
            cargos_to_create.append(new_cargo)

            if len(cargos_to_create) >= batch_size:
                db.bulk_save_objects(cargos_to_create)
                db.commit()
                cargos_to_create.clear()  # Reset the batch

        # Step 4: Save any remaining cargos in the last batch
        if cargos_to_create:
            db.bulk_save_objects(cargos_to_create)
            db.commit()

        return {"detail": "Cargos created successfully"}
    
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"A Cargo with the same name already exists: {str(e)}")
    
    except Exception as e:
        db.rollback()
        print(f"Error occurred while creating cargos: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while creating cargos.")


@cargoRouter.get("/cargo/", status_code=200, response_model=List[CargoResponseDTO])
def get_all_cargos(
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> List[CargoResponseDTO]:
    """
    Retrieve all Cargo records from the database.
    """

    try:
        # Query the database to get all cargos
        cargos = db.query(Cargo).all()

        if not cargos:
            raise HTTPException(status_code=404, detail="No cargos found")

        # Return the list of cargos as a list of Pydantic models
        return cargos

    except Exception as e:
        # Handle unforeseen errors
        print(f"Error occurred while retrieving cargos: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving cargos.")

