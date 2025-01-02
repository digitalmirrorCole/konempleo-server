from concurrent.futures import ThreadPoolExecutor 
import os
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, FastAPI, BackgroundTasks, HTTPException
from requests import Session

from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.cv.cvService import fetch_background_check_result, get_token, process_batch
from app.cv.vitaeOfferDTO import CampaignRequestDTO, VitaeOfferResponseDTO
from app.deps import get_db
from models.models import Company, Offer, CVitae, OfferSkill, Skill, UserEnum, VitaeOffer
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

cvRouter = APIRouter()
cvRouter.tags = ['CV']

@cvRouter.post("/offers/upload-cvs/", status_code=201, response_model=None)
def upload_cvs(
    companyId: int, 
    offerId: int, 
    files: List[UploadFile] = File(...), 
    db: Session = Depends(get_db)  # Pass an active session here
):
    company = db.query(Company).filter(Company.id == companyId).first()
    offer = db.query(Offer).filter(Offer.id == offerId).first()

    if not company or not offer:
        raise HTTPException(status_code=404, detail="Company or Offer not found")

    offer_skills = db.query(Skill).join(OfferSkill).filter(OfferSkill.offerId == offerId).all()
    if not offer_skills:
        raise HTTPException(status_code=404, detail="No skills found for the given offer.")
    skills_list = [skill.name for skill in offer_skills]

    city_offer = offer.city
    age_offer = offer.age
    genre_offer = offer.gender
    experience_offer = offer.experience_years

    file_batches = [files[i:i+10] for i in range(0, len(files), 10)]

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                process_batch, 
                batch, 
                companyId, 
                offerId, 
                skills_list, 
                city_offer, 
                age_offer, 
                genre_offer, 
                experience_offer, 
                db  # Pass the active session directly
            ) 
            for batch in file_batches
        ]

    for future in futures:
        future.result()

    return {"detail": "All files processed successfully"}


@cvRouter.get("/background-check/{cvitae_id}")
async def background_check(cvitae_id: int, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Perform a background check for a CVitae record using TusDatos API.
    """
    # Fetch the CVitae record by ID
    cvitae = db.query(CVitae).filter(CVitae.Id == cvitae_id).first()
    if not cvitae:
        raise HTTPException(status_code=404, detail="CVitae record not found")

    # Prepare the data for the POST request based on candidate_dni or candidate_name
    url_post = "https://dash-board.tusdatos.co/api/launch"
    if cvitae.candidate_dni:
        data_post = {
            "doc": int(cvitae.candidate_dni),
            "typedoc": cvitae.candidate_dni_type,
            "force": True
        }
    else:
        data_post = {
            "doc": cvitae.candidate_name,
            "typedoc": "NOMBRE"
        }

    tusDatosUser= os.getenv("tusDatosUser")
    tusDatosSecret= os.getenv("tusDatosSecret")

    # Make the initial POST request
    try:
        response_post = requests.post(
            url_post,
            auth=HTTPBasicAuth(tusDatosUser, tusDatosSecret),
            json=data_post
        )
        response_post.raise_for_status()  # Raise exception for bad status
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error in external request: {str(e)}")

    # Get the jobId from the response
    response_data = response_post.json()
    job_id = response_data.get("jobId")
    if not job_id:
        raise HTTPException(status_code=500, detail="Job ID not returned from the service")

    # Save the jobId and the current date in the CVitae record
    cvitae.tusdatos_id = job_id
    cvitae.background_date = datetime.utcnow()
    db.add(cvitae)
    db.commit()

    # Schedule the background task to fetch the result after a minute
    background_tasks.add_task(fetch_background_check_result, job_id, cvitae_id, db)

    return {"jobId": job_id, "message": "Background check initiated, results will be fetched after a minute."}


@cvRouter.get("/cvoffers/{offer_id}", status_code=200, response_model=List[VitaeOfferResponseDTO])
def get_cvoffers_by_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
) -> List[VitaeOfferResponseDTO]:
    """
    Get all VitaeOffer records for a given offer ID with details from CVitae and VitaeOffer tables.
    """
    try:
        # Query to get the VitaeOffer records for the given offer ID
        results = db.query(
            VitaeOffer.id.label("vitae_offer_id"),
            CVitae.candidate_name,
            CVitae.url,
            CVitae.background_check,
            CVitae.candidate_phone,
            CVitae.candidate_mail,
            VitaeOffer.whatsapp_status,
            VitaeOffer.response_score,
            VitaeOffer.status
        ).join(
            CVitae, CVitae.id == VitaeOffer.cvitaeId
        ).filter(
            VitaeOffer.offerId == offer_id
        ).all()

        if not results:
            raise HTTPException(status_code=404, detail=f"No CV offers found for offer ID {offer_id}")

        # Format the response
        response = [
            VitaeOfferResponseDTO(
                vitae_offer_id=row.vitae_offer_id,
                candidate_name=row.candidate_name,
                url=row.url,
                background_check=row.background_check,
                candidate_phone=row.candidate_phone,
                candidate_mail=row.candidate_mail,
                whatsapp_status=row.whatsapp_status,
                response_score=row.response_score,
                status=row.status
            )
            for row in results
        ]

        return response

    except Exception as e:
        print(f"Error fetching CV offers for offer ID {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching CV offers.")


from pydantic import BaseModel
from fastapi import HTTPException, status

# Request DTO for updating the status
class UpdateVitaeOfferStatusDTO(BaseModel):
    status: str

@cvRouter.put("/cvoffers/{vitae_offer_id}/status", status_code=200)
def update_vitae_offer_status(
    vitae_offer_id: int,
    status_update: UpdateVitaeOfferStatusDTO,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Update the status of a VitaeOffer record by its ID.
    """
    try:
        # Validate the provided status
        allowed_statuses = ['pending', 'hired']
        if status_update.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed statuses are: {', '.join(allowed_statuses)}"
            )

        # Fetch the VitaeOffer record
        vitae_offer = db.query(VitaeOffer).filter(VitaeOffer.id == vitae_offer_id).first()
        if not vitae_offer:
            raise HTTPException(status_code=404, detail=f"VitaeOffer with ID {vitae_offer_id} not found.")

        # Update the status
        vitae_offer.status = status_update.status
        db.commit()
        db.refresh(vitae_offer)

        return {"detail": f"VitaeOffer ID {vitae_offer_id} status updated to {status_update.status}"}

    except Exception as e:
        print(f"Error updating status for VitaeOffer ID {vitae_offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while updating the status.")

@cvRouter.post("/cvoffers/send-message/")
def send_campaign(
    campaign_data: CampaignRequestDTO,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
):
    try:
        # Check if the user has the required role
        if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit]:
            raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")

        # Check if the VitaeOffer record exists
        vitae_offer = db.query(VitaeOffer).filter(VitaeOffer.id == campaign_data.vitae_offer_id).first()
        if not vitae_offer:
            raise HTTPException(status_code=404, detail=f"VitaeOffer record with ID {campaign_data.vitae_offer_id} not found.")

        # Check if the offerId exists and matches the VitaeOffer record
        if vitae_offer.offerId != campaign_data.offerId:
            raise HTTPException(
                status_code=400,
                detail=f"Mismatch: VitaeOffer record with ID {campaign_data.vitae_offer_id} is not associated with offer ID {campaign_data.offerId}."
            )

        offer = db.query(Offer).filter(Offer.id == campaign_data.offerId).first()
        if not offer:
            raise HTTPException(status_code=404, detail=f"Offer with ID {campaign_data.offerId} not found.")

        # Get the token
        token = get_token()
        print(f"+57{campaign_data.candidate_phone}")
        # Extract the template ID from the environment
        template_id = os.getenv("SDTEMPLATE_ID")
        if not template_id:
            raise HTTPException(status_code=500, detail="Template ID is not configured.")

        # Prepare the payload
        payload = {
            "template_id": int(template_id),
            "receiver": f"+57{campaign_data.candidate_phone}",
            "tags_values": f"{campaign_data.candidate_name},{campaign_data.offer_name},{campaign_data.zone},{campaign_data.salary},{campaign_data.contract}"
        }

        # Make the POST request
        url = "https://botai.smartdataautomation.com/massive-campaigns/template/whatsapp/message"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        # Parse the response
        response_data = response.json()

        # Extract the message_id and update the smartdataId
        message_id = response_data.get("message_id")
        if not message_id:
            raise HTTPException(status_code=500, detail="Response did not contain a message_id.")

        # Update the VitaeOffer record
        vitae_offer.whatsapp_status = "pending_response"
        vitae_offer.smartdataId = message_id
        db.commit()
        db.refresh(vitae_offer)

        return {
            "detail": "Message sent successfully, WhatsApp status and SmartdataId updated",
            "response": response_data
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to send campaign: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")  # Log the error
        raise HTTPException(status_code=500, detail=f"Failed to update VitaeOffer record: {str(e)}")
