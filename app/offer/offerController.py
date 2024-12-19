from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from sqlalchemy import func

from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.deps import get_db
from app.offer.offerDTO import Offer, OfferCreateDTO, OfferUpdateDTO, OfferWithVitaeCount
from models.models import Cargo, Company, CompanyOffer, OfferSkill, Skill, UserEnum, Users, VitaeOffer
from models.models import Offer as OfferModel

offerRouter = APIRouter()
offerRouter.tags = ['Offer']


@offerRouter.post("/offers/", response_model=Offer)
def create_offer(
    offer_in: OfferCreateDTO, 
    skills: List[int], 
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
):
    """
    Create a new offer and associate it with the provided skills and the offer owner.
    """
    # Ensure that the current user is a company user
    if userToken.role not in [UserEnum.company_recruit, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    # Check if the company exists
    offerCompanyId = offer_in.companyId
    company = db.query(Company).filter(Company.id == offerCompanyId).first()
    if not company:
        raise HTTPException(status_code=400, detail=f"Invalid company ID: {offer_in.companyId}")
    
    # Check if the company exists
    offerCargoId = offer_in.cargoId
    cargo = db.query(Cargo).filter(Cargo.id == offerCargoId).first()
    if not cargo:
        raise HTTPException(status_code=400, detail=f"Invalid cargo ID: {offer_in.companyId}")

    # Check if the current active offers will exceed the total offers
    if company.totaloffers + 1 > company.availableoffers:
        raise HTTPException(status_code=400, detail="Cannot create new offer. Active offers exceed the total allowed offers for this company.") 

    # Prepare offer data
    offer_data = offer_in.dict()
    offer_data.pop('companyId', None)  # Remove companyId, we'll handle this later

    try:
        # Create the Offer
        new_offer = OfferModel(**offer_data)
        new_offer.offer_owner = userToken.id  # Associate the user as offer_owner
        db.add(new_offer)
        db.flush()  # Flush to get the new offer's ID

        # Associate skills with the offer
        for skill_id in skills:
            skill = db.query(Skill).filter(Skill.id == skill_id).first()
            if not skill:
                raise HTTPException(status_code=400, detail=f"Invalid skill ID: {skill_id}")

            offer_skill = OfferSkill(offerId=new_offer.id, skillId=skill.id)
            db.add(offer_skill)

        # Associate the offer with the company
        company_offer = CompanyOffer(offerId=new_offer.id, companyId=offerCompanyId)
        db.add(company_offer)

        # Increment the company's activeoffers
        company.activeoffers += 1
        company.totaloffers += 1
        company.availableoffers = company.availableoffers -1
        db.add(company)

        # Commit the transaction to save everything
        db.commit()

        # Refresh the new offer to return updated data
        db.refresh(new_offer)

        return new_offer
    
    except HTTPException as e:
        raise e  # Re-raise the HTTPException for invalid skill or user ID

    except Exception as e:
        db.rollback()  # Rollback in case of errors
        raise HTTPException(status_code=500, detail=f"An error occurred while creating the offer: {str(e)}")



@offerRouter.put("/offers/{offer_id}", response_model=Offer)
def update_offer(
    offer_id: int,
    offer_update: OfferUpdateDTO,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
):
    """
    Update specific fields in an offer: assigned_cvs, whatsapp_message, and disabled status.
    """

    # Ensure that the current user is a company user
    if userToken.role not in [UserEnum.company_recruit, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Fetch the offer by ID
    offer = db.query(OfferModel).filter(OfferModel.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    try:
        # Update the allowed fields if they are provided
        if offer_update.assigned_cvs is not None:
            offer.assigned_cvs = offer_update.assigned_cvs
        if offer_update.whatsapp_message is not None:
            offer.whatsapp_message = offer_update.whatsapp_message
        if offer_update.disabled is not None:
            offer.disabled = offer_update.disabled

        # Commit the updates to the database
        db.commit()
        db.refresh(offer)

        return offer

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while updating the offer: {str(e)}")


@offerRouter.get("/offers/company/details/{company_id}", response_model=List[OfferWithVitaeCount])
def get_offers_by_company(company_id: int, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    """
    Get offers for a given company and count the number of associated VitaeOffer records for each offer.
    """

    if userToken.role not in [UserEnum.super_admin, UserEnum.admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Check if the company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Query offers associated with the company and count associated VitaeOffer records
    offers_with_vitae_count = db.query(
        OfferModel, 
        func.count(VitaeOffer.id).label('vitae_offer_count')
    ).join(
        CompanyOffer, CompanyOffer.offerId == OfferModel.id
    ).outerjoin(
        VitaeOffer, VitaeOffer.offerId == OfferModel.id
    ).filter(
        CompanyOffer.companyId == company_id
    ).group_by(
        OfferModel.id
    ).all()

    # Format the response with the offer data and vitae_offer_count
    result = []
    for offer, vitae_offer_count in offers_with_vitae_count:
        offer_dict = offer.__dict__.copy()  # Convert the offer object to a dictionary
        offer_dict['vitae_offer_count'] = vitae_offer_count
        result.append(OfferWithVitaeCount(**offer_dict))
    
    return result

@offerRouter.get("/offers/owner/", response_model=List[OfferWithVitaeCount])
def get_offers_by_owner(db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    """
    Get offers for a given offer owner and count the number of associated VitaeOffer records for each offer.
    """

    # Ensure only super_admin or company users can access this
    if userToken.role not in [UserEnum.super_admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    current_user_id = userToken.id

    # Check if the offer owner exists
    owner = db.query(Users).filter(Users.id == current_user_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Offer owner not found")

    # Query offers associated with the given offer_owner and count associated VitaeOffer records
    offers_with_vitae_count = db.query(
        OfferModel, 
        func.count(VitaeOffer.id).label('vitae_offer_count')
    ).outerjoin(
        VitaeOffer, VitaeOffer.offerId == OfferModel.id
    ).filter(
        OfferModel.offer_owner == current_user_id
    ).group_by(
        OfferModel.id
    ).all()

    # Format the response with the offer data and vitae_offer_count
    result = []
    for offer, vitae_offer_count in offers_with_vitae_count:
        offer_dict = offer.__dict__.copy()  # Convert the offer object to a dictionary
        offer_dict['vitae_offer_count'] = vitae_offer_count
        result.append(OfferWithVitaeCount(**offer_dict))
    
    return result

@offerRouter.get("/offers/details/{offer_id}", response_model=OfferWithVitaeCount)
def get_offer_by_id(
    offer_id: int, 
    db: Session = Depends(get_db), 
    userToken: UserToken = Depends(get_user_current)
) -> OfferWithVitaeCount:
    """
    Get a specific offer by its ID and count the associated VitaeOffer records.
    """

    # Check user permissions
    if userToken.role not in [UserEnum.super_admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="You do not have permission to view this offer.")

    # Query to fetch the offer and count associated VitaeOffer records
    offer_with_vitae_count = db.query(
        OfferModel,
        func.count(VitaeOffer.id).label("vitae_offer_count")
    ).outerjoin(
        VitaeOffer, VitaeOffer.offerId == OfferModel.id
    ).filter(
        OfferModel.id == offer_id
    ).group_by(
        OfferModel.id
    ).first()

    if not offer_with_vitae_count:
        raise HTTPException(status_code=404, detail="Offer not found")

    # Unpack the query result
    offer, vitae_offer_count = offer_with_vitae_count

    # Prepare the response
    offer_dict = offer.__dict__.copy()  # Convert the offer object to a dictionary
    offer_dict["vitae_offer_count"] = vitae_offer_count

    return OfferWithVitaeCount(**offer_dict)