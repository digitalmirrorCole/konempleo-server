from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from sqlalchemy import func

from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.deps import get_db
from app.offer.offerDTO import Offer, OfferCreateDTO, OfferUpdateDTO, OfferWithVitaeCount
from models.models import Company, CompanyOffer, OfferSkill, Skill, UserEnum, Users, VitaeOffer
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
    if userToken.role != UserEnum.company:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")
    
    # Check if the company exists
    offerCompanyId = offer_in.companyId
    company = db.query(Company).filter(Company.id == offerCompanyId).first()
    if not company:
        raise HTTPException(status_code=400, detail=f"Invalid company ID: {offer_in.companyId}")

    # Check if the offer owner (user) exists
    offer_owner_user = db.query(Users).filter(Users.id == offer_in.offer_owner).first()
    if not offer_owner_user:
        raise HTTPException(status_code=400, detail=f"Invalid offer owner user ID: {offer_in.offer_owner}")

    # Prepare offer data
    offer_data = offer_in.dict()
    offer_data.pop('companyId', None)  # Remove companyId, we'll handle this later

    try:
        # Create the Offer
        new_offer = OfferModel(**offer_data)
        new_offer.offer_owner = offer_owner_user.id  # Associate the user as offer_owner
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
def update_offer(offer_id: int, offer: OfferUpdateDTO, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    # Logic to update an offer
    pass

@offerRouter.get("/offers/company/details/{company_id}", response_model=List[OfferWithVitaeCount])
def get_offers_by_company(company_id: int, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    """
    Get offers for a given company and count the number of associated VitaeOffer records for each offer.
    """

    if userToken.role not in [UserEnum.super_admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Check if the company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Query offers associated with the company and count associated VitaeOffer records
    offers_with_vitae_count = db.query(
        Offer, 
        func.count(VitaeOffer.id).label('vitae_offer_count')
    ).join(
        CompanyOffer, CompanyOffer.offerId == Offer.id
    ).outerjoin(
        VitaeOffer, VitaeOffer.offerId == Offer.id
    ).filter(
        CompanyOffer.companyId == company_id
    ).group_by(
        Offer.id
    ).all()

    # Format the response with the offer data and vitae_offer_count
    result = []
    for offer, vitae_offer_count in offers_with_vitae_count:
        offer_dict = offer.__dict__.copy()  # Convert the offer object to a dictionary
        offer_dict['vitae_offer_count'] = vitae_offer_count
        result.append(OfferWithVitaeCount(**offer_dict))
    
    return result

@offerRouter.get("/offers/owner/{offer_owner}", response_model=List[OfferWithVitaeCount])
def get_offers_by_owner(offer_owner: int, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current)):
    """
    Get offers for a given offer owner and count the number of associated VitaeOffer records for each offer.
    """

    # Ensure only super_admin or company users can access this
    if userToken.role not in [UserEnum.super_admin, UserEnum.company]:
        raise HTTPException(status_code=403, detail="No tiene los permisos para ejecutar este servicio")

    # Check if the offer owner exists
    owner = db.query(Users).filter(Users.id == offer_owner).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Offer owner not found")

    # Query offers associated with the given offer_owner and count associated VitaeOffer records
    offers_with_vitae_count = db.query(
        Offer, 
        func.count(VitaeOffer.id).label('vitae_offer_count')
    ).outerjoin(
        VitaeOffer, VitaeOffer.offerId == Offer.id
    ).filter(
        Offer.offer_owner == offer_owner
    ).group_by(
        Offer.id
    ).all()

    # Format the response with the offer data and vitae_offer_count
    result = []
    for offer, vitae_offer_count in offers_with_vitae_count:
        offer_dict = offer.__dict__.copy()  # Convert the offer object to a dictionary
        offer_dict['vitae_offer_count'] = vitae_offer_count
        result.append(OfferWithVitaeCount(**offer_dict))
    
    return result
