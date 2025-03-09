from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.deps import get_db
from app.skill.skillDTO import SkillCreateDTO
from models.models import Cargo, CargoSkill, OfferSkill, Skill, UserEnum

skillRouter = APIRouter()
skillRouter.tags = ['Skill']

@skillRouter.post("/skills/", status_code=201, response_model=None)
def create_skills(
    *, skill_in: SkillCreateDTO = Body(...),
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Create new skills and associate them with a cargo.
    """

    # Ensure that the cargo exists
    cargo = db.query(Cargo).filter(Cargo.id == skill_in.cargoId).first()
    if not cargo:
        raise HTTPException(status_code=400, detail=f"Invalid cargo ID: {skill_in.cargoId}")

    created_skills = []
    
    try:
        # Step 1: Iterate through the list of skills and create them
        for skill_name in skill_in.skills:
            # Create the Skill
            skill = Skill(name=skill_name)
            db.add(skill)
            db.flush()  # Flush to get the skill ID

            # Create the CargoSkill relationship
            cargo_skill = CargoSkill(
                cargoId=skill_in.cargoId,
                skillId=skill.id
            )
            db.add(cargo_skill)
            
            created_skills.append(skill_name)

        # Commit all changes
        db.commit()

        return {"detail": f"Skills created successfully: {', '.join(created_skills)}"}

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"A skill already exists in the database: {str(e)}")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while creating skills: {str(e)}")


@skillRouter.get("/skills/cargo/{cargo_id}", status_code=200)
def get_skills_by_cargo(
    cargo_id: int,
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Retrieve all skills associated with a given cargoId.
    """

    # Ensure that the cargo exists
    cargo = db.query(Cargo).filter(Cargo.id == cargo_id).first()
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo with ID {cargo_id} not found")

    try:
        # Query to get all skills related to the given cargo
        cargo_skills = db.query(Skill).join(CargoSkill).filter(CargoSkill.cargoId == cargo_id).all()

        if not cargo_skills:
            return {"detail": f"No skills found for cargo ID: {cargo_id}"}

        # Format the response with skill IDs and names
        skills_list = [{"id": skill.id, "name": skill.name} for skill in cargo_skills]
        
        return {"cargo": cargo.name, "skills": skills_list}

    except Exception as e:
        print(f"Error occurred while retrieving skills: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the skills.")


@skillRouter.delete("/skills/{skill_id}/cargo/{cargo_id}", summary="Delete a specific CargoSkill by skill and cargo ID")
def delete_cargo_skill(skill_id: int, cargo_id: int, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    """
    Deletes a CargoSkill record that matches the given skill_id and cargo_id.
    """

    # Check for a matching CargoSkill record
    cargo_skill = db.query(CargoSkill).filter(
        CargoSkill.skillId == skill_id,
        CargoSkill.cargoId == cargo_id
    ).first()

    if not cargo_skill:
        raise HTTPException(status_code=404, detail="No CargoSkill found for the given skill_id and cargo_id.")

    # Delete the CargoSkill record
    db.delete(cargo_skill)
    db.commit()

    return {"detail": "CargoSkill deleted successfully."}
