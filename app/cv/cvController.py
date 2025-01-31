import asyncio
from concurrent.futures import ThreadPoolExecutor 
from contextlib import contextmanager
import os
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, File, Query, UploadFile, BackgroundTasks, HTTPException, status
from requests import Session
from db.session import SessionLocal

from app.auth.authDTO import UserToken
from app.auth.authService import get_user_current
from app.cv.cvService import fetch_background_check_result, get_token, process_batch, process_existing_vitae_records
from app.cv.vitaeOfferDTO import CVitaeResponseDTO, CampaignRequestDTO, UpdateVitaeOfferStatusDTO, VitaeOfferResponseDTO
from app.deps import get_db
from models.models import Cargo, Company, Offer, CVitae, OfferSkill, Skill, UserEnum, VitaeOffer
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from app.utils.thread_manager import ThreadPoolManager

cvRouter = APIRouter()
cvRouter.tags = ['CV']
thread_pool_manager = ThreadPoolManager(max_workers=5)

@cvRouter.post("/offers/upload-cvs/", status_code=201, response_model=None)
async def upload_cvs(
    companyId: int,
    offerId: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
):
    """
    Asynchronous endpoint to process and upload CVs for a given offer and company.
    """

    if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")

    # Check if the offer exists and is active
    offer = db.query(Offer).filter(Offer.id == offerId).first()
    if not offer or not offer.active:
        raise HTTPException(status_code=404, detail="Offer not found or is inactive")

    # Check if the company exists
    company = db.query(Company).filter(Company.id == companyId).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company_name = company.name.replace(" ", "_").lower()  # Normalize the company name for S3 path

    # Check if the offer has associated skills
    offer_skills = db.query(Skill).join(OfferSkill).filter(OfferSkill.offerId == offerId).all()
    if not offer_skills:
        raise HTTPException(status_code=404, detail="No skills found for the given offer.")
    skills_list = [skill.name for skill in offer_skills]

    # Extract offer details
    city_offer = offer.city
    age_offer = offer.age
    genre_offer = offer.gender
    experience_offer = offer.experience_years

    # Split files into batches
    file_batches = [files[i:i + 5] for i in range(0, len(files), 5)]

    async def process_files(batch):
        """
        Process a batch of files asynchronously.
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(
                executor,
                process_batch,
                batch,
                companyId,
                company_name,
                offerId,
                skills_list,
                city_offer,
                age_offer,
                genre_offer,
                experience_offer,
                db
            )

    async def process_batches_with_delay():
        """
        Asynchronously process all batches with a delay between each batch.
        """
        for batch in file_batches:
            await process_files(batch)  # Process the current batch
            await asyncio.sleep(3)  # Add a 2-second delay before the next batch

    # Process all batches with delay
    # await process_batches_with_delay()
    task_id = thread_pool_manager.submit_task(process_batches_with_delay)

    return {"detail": "Processing files", "task": task_id}



@cvRouter.get("/background-check/{cvitae_id}")
async def background_check(cvitae_id: int, db: Session = Depends(get_db), userToken: UserToken = Depends(get_user_current), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Perform a background check for a CVitae record using TusDatos API.
    """
    if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit, UserEnum.admin]:
            raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")
    # Fetch the CVitae record by ID
    cvitae = db.query(CVitae).filter(CVitae.Id == cvitae_id).first()
    if not cvitae:
        raise HTTPException(status_code=404, detail="CVitae record not found")

    # Map candidate_dni_type to valid TusDatos types
    dni_type_mapping = {
        "Cédula de Ciudadania": "CC",
        "cedula": "CC",
        "Cedula de extranjeria": "CE",
        None: "CC",
        "": "CC"
    }
    dni_type = dni_type_mapping.get(cvitae.candidate_dni_type, "CC")

    # Sanitize the candidate_dni to remove dots, dashes, and spaces
    sanitized_dni = (
        "".join(filter(str.isdigit, str(cvitae.candidate_dni))) if cvitae.candidate_dni else None
    )

    # Prepare the data for the POST request based on candidate_dni or candidate_name
    if sanitized_dni:
        data_post = {
            "doc": int(sanitized_dni),
            "typedoc": dni_type,
            "force": True
        }
    else:
        data_post = {
            "doc": cvitae.candidate_name,
            "typedoc": "NOMBRE"
        }

    tusDatosUser = os.getenv("tusDatosUser")
    tusDatosSecret = os.getenv("tusDatosSecret")

    if not tusDatosUser or not tusDatosSecret:
        raise HTTPException(status_code=500, detail="TusDatos credentials are not configured.")

    # Make the initial POST request
    url_post = "https://dash-board.tusdatos.co/api/launch"
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
    try:
        response_data = response_post.json()
        job_id = response_data.get("jobid")
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON response from service. Sent data: {data_post}, Response content: {response_post.text}"
        )

    if not job_id:
        raise HTTPException(
            status_code=500,
            detail=f"Job ID not returned from the service. Sent data: {data_post}, Response content: {response_post.text}"
        )

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
    start_date: Optional[datetime] = None,
    close_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current),
) -> List[VitaeOfferResponseDTO]:
    """
    Get all VitaeOffer records for a given offer ID with details from CVitae and VitaeOffer tables.
    Optionally filter by start_date and close_date.
    """
    try:
        # Validate user permissions
        if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit, UserEnum.admin]:
            raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")
        
        # Validate date filters
        if start_date and close_date:
            if close_date <= start_date:
                raise HTTPException(
                    status_code=400, detail="close_date must be greater than start_date"
                )
        elif start_date or close_date:
            raise HTTPException(
                status_code=400, detail="Both start_date and close_date must be provided together"
            )

        # Build base query
        query = db.query(
            VitaeOffer.id.label("vitae_offer_id"),
            CVitae.candidate_name,
            CVitae.url,
            CVitae.background_check,
            CVitae.candidate_phone,
            CVitae.candidate_mail,
            VitaeOffer.whatsapp_status,
            VitaeOffer.smartdataId,
            VitaeOffer.response_score,
            VitaeOffer.status,
            VitaeOffer.comments,
            VitaeOffer.created_date,
            VitaeOffer.modified_date
        ).join(
            CVitae, CVitae.Id == VitaeOffer.cvitaeId
        ).filter(
            VitaeOffer.offerId == offer_id
        )

        # Apply date filters if provided
        if start_date and close_date:
            query = query.filter(
                VitaeOffer.created_date >= start_date,
                VitaeOffer.created_date <= close_date
            )

        # Execute query
        results = query.all()

        if not results:
            return []

        # Format response
        response = [
            VitaeOfferResponseDTO(
                vitae_offer_id=row.vitae_offer_id,
                candidate_name=row.candidate_name,
                url=row.url,
                background_check=row.background_check,
                candidate_phone=row.candidate_phone,
                candidate_mail=row.candidate_mail,
                smartdataId=row.smartdataId,
                whatsapp_status=row.whatsapp_status,
                response_score=row.response_score,
                status=row.status,
                comments=row.comments,
                created_date=row.created_date,
                modified_date=row.modified_date
            )
            for row in results
        ]

        return response

    except Exception as e:
        print(f"Error fetching CV offers for offer ID {offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching CV offers: {str(e)}")


@cvRouter.put("/cvoffers/{vitae_offer_id}/status", status_code=200)
def update_vitae_offer_status(
    vitae_offer_id: int,
    status_update: UpdateVitaeOfferStatusDTO,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
) -> dict:
    """
    Update the status and comments of a VitaeOffer record by its ID.
    """
    try:
        if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit, UserEnum.admin]:
            raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")
        # Validate the provided status if provided
        allowed_statuses = ['pending', 'hired']
        if status_update.status and status_update.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed statuses are: {', '.join(allowed_statuses)}"
            )

        # Fetch the VitaeOffer record
        vitae_offer = db.query(VitaeOffer).filter(VitaeOffer.id == vitae_offer_id).first()
        if not vitae_offer:
            raise HTTPException(status_code=404, detail=f"VitaeOffer with ID {vitae_offer_id} not found.")

        # Update the status if provided
        if status_update.status:
            vitae_offer.status = status_update.status

        # Update the comments if provided
        if status_update.comments is not None:
            vitae_offer.comments = status_update.comments

        db.commit()
        db.refresh(vitae_offer)

        return {
            "detail": f"VitaeOffer ID {vitae_offer_id} updated successfully",
            "status": vitae_offer.status,
            "comments": vitae_offer.comments
        }

    except Exception as e:
        print(f"Error updating VitaeOffer ID {vitae_offer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while updating the VitaeOffer.")

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

        # Validate and format the candidate_phone
        candidate_phone = campaign_data.candidate_phone.strip()  # Remove whitespace
        if not candidate_phone.startswith("+57"):
            candidate_phone = f"+57{candidate_phone}"

        # Extract the template ID from the environment
        template_id = os.getenv("SDTEMPLATE_ID")
        if not template_id:
            raise HTTPException(status_code=500, detail="Template ID is not configured.")

        # Prepare the payload
        payload = {
            "template_id": int(template_id),
            "receiver": candidate_phone,
            "tags_values": f"{campaign_data.candidate_name},{campaign_data.offer_name},{campaign_data.zone},{campaign_data.salary},{campaign_data.contract},{campaign_data.offerId}"
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
            raise HTTPException(status_code=500, detail=f"Response did not contain a message_id. Response: {response_data}")

        # Update the VitaeOffer record
        vitae_offer.whatsapp_status = "pending_response"
        vitae_offer.smartdataId = message_id

        # Increment the `contacted` count for the related Offer
        offer.contacted += 1

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
        import traceback
        traceback_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"Error: {traceback_str}")  # Log the full traceback
        raise HTTPException(status_code=500, detail=f"Failed to update VitaeOffer record: {str(e)}")

@cvRouter.put("/cvoffers/update-response/")
def update_whatsapp_status(
    smartdataId: str = Query(..., description="The SmartData ID of the VitaeOffer"),
    offerId: int = Query(..., description="The Offer ID associated with the VitaeOffer"),
    userResponse: str = Body(..., description="The user response ('interested' or 'not_interested')"),
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current),
):
    """
    Update the WhatsApp status of a VitaeOffer record based on user response.
    Increment the `interested` field in the related Offer if the user response is 'interested'.
    """
    try:
        # Validate the user's role
        if userToken.role != UserEnum.integrations:
            raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")

        # Fetch the VitaeOffer record
        vitae_offer = db.query(VitaeOffer).filter(
            VitaeOffer.smartdataId == smartdataId,
            VitaeOffer.offerId == offerId,
        ).first()

        # Check if VitaeOffer exists
        if not vitae_offer:
            raise HTTPException(status_code=404, detail="VitaeOffer record not found.")

        # Validate the user response
        if userResponse not in ["interested", "not_interested"]:
            raise HTTPException(status_code=400, detail="Invalid user response.")

        # Update the WhatsApp status
        vitae_offer.whatsapp_status = userResponse

        # If the response is 'interested', increment the 'interested' field in the related Offer
        if userResponse == "interested":
            offer = db.query(Offer).filter(Offer.id == offerId).first()
            if not offer:
                raise HTTPException(status_code=404, detail=f"Offer with ID {offerId} not found.")
            
            # Increment the interested field
            offer.interested += 1  # Since the default is 0 and not nullable, no need to check for None

        db.commit()
        db.refresh(vitae_offer)

        return {"detail": f"WhatsApp status updated to '{userResponse}' for VitaeOffer ID {vitae_offer.id}"}

    except HTTPException as http_exc:
        # Log HTTP exceptions for better context
        print(f"HTTPException: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Log and raise unexpected errors
        db.rollback()
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@cvRouter.get("/task/{task_id}", status_code=200, response_model=None)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
):
    """
    Retrieve the current status of a background task
    """
    status = thread_pool_manager.get_task_status(task_id)
    return {"task": task_id, "status": status}


@cvRouter.get("/companies/{company_id}/cvitae", response_model=List[CVitaeResponseDTO])
def get_cvitae_by_company(
    company_id: int,
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
) -> List[CVitaeResponseDTO]:
    """
    Retrieve all CVitae records for a given company ID along with associated cargo names.
    """
    # Check if the user has valid permissions
    if userToken.role not in [UserEnum.admin, UserEnum.company, UserEnum.company_recruit, UserEnum.super_admin]:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Query CVitae records by company ID
    cvitae_records = db.query(CVitae).filter(CVitae.companyId == company_id).all()

    if not cvitae_records:
        raise HTTPException(status_code=404, detail=f"No CVitae records found for company ID {company_id}")

    # Retrieve associated cargo names for each CVitae record
    cvitae_ids = [record.Id for record in cvitae_records]
    cargo_names_map = (
        db.query(VitaeOffer.cvitaeId, Cargo.name)
        .join(Offer, Offer.id == VitaeOffer.offerId)
        .join(Cargo, Cargo.id == Offer.cargoId)
        .filter(VitaeOffer.cvitaeId.in_(cvitae_ids))
        .distinct()
        .all()
    )

    # Map CVitae ID to associated cargo names
    cvitae_to_cargos = {}
    for cvitae_id, cargo_name in cargo_names_map:
        if cvitae_id not in cvitae_to_cargos:
            cvitae_to_cargos[cvitae_id] = []
        cvitae_to_cargos[cvitae_id].append(cargo_name)

    # Format the response
    response = [
        CVitaeResponseDTO(
            id=record.Id,  # Include CVitae ID
            candidate_name=record.candidate_name,
            url=record.url,
            candidate_city=record.candidate_city,
            associated_cargos=cvitae_to_cargos.get(record.Id, [])  # Return cargo names or an empty list
        )
        for record in cvitae_records
    ]

    return response


@cvRouter.post("/offers/process-existing-cvs/", status_code=200, response_model=None)
async def process_existing_cvs(
    offerId: int,
    cvitae_ids: List[int],
    db: Session = Depends(get_db),
    userToken: UserToken = Depends(get_user_current)
):
    """
    Process existing CVitae records by their IDs and create/update associated VitaeOffer records.
    """

    # Validate user permissions
    if userToken.role not in [UserEnum.super_admin, UserEnum.company, UserEnum.company_recruit, UserEnum.admin]:
        raise HTTPException(status_code=403, detail="You do not have permission to access this endpoint.")

    # Check if the offer exists and is active
    offer = db.query(Offer).filter(Offer.id == offerId).first()
    if not offer or not offer.active:
        raise HTTPException(status_code=404, detail="Offer not found or is inactive")

    # Extract skills and offer details
    offer_skills = db.query(Skill).join(OfferSkill).filter(OfferSkill.offerId == offerId).all()
    if not offer_skills:
        raise HTTPException(status_code=404, detail="No skills found for the given offer.")
    skills_list = [skill.name for skill in offer_skills]
    city_offer = offer.city
    age_offer = offer.age
    genre_offer = offer.gender
    experience_offer = offer.experience_years

    # Split `cvitae_ids` into batches of 10
    batches = [cvitae_ids[i:i + 5] for i in range(0, len(cvitae_ids), 5)]

    @contextmanager
    def get_thread_safe_db():
        """
        Context manager to provide a thread-safe session.
        """
        db = SessionLocal()  # Create a new session for each thread
        try:
            yield db
        finally:
            db.close()

    def process_batch(batch, offerId, skills_list, city_offer, age_offer, genre_offer, experience_offer):
        """
        Process a single batch of CVitae records in a thread-safe manner.
        """
        with get_thread_safe_db() as db:
            # Use the updated `process_existing_vitae_records` method to handle the batch
            process_existing_vitae_records(
                cvitae_ids=batch,
                offerId=offerId,
                skills_list=skills_list,
                city_offer=city_offer,
                age_offer=age_offer,
                genre_offer=genre_offer,
                experience_offer=experience_offer,
                db=db
            )

    async def process_batches():
        """
        Asynchronously process all batches using multithreading with delays.
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            for batch in batches:
                # Process the current batch
                await loop.run_in_executor(
                    executor,
                    process_batch,
                    batch,
                    offerId,
                    skills_list,
                    city_offer,
                    age_offer,
                    genre_offer,
                    experience_offer
                )
                # Add a 2-second delay before processing the next batch
                await asyncio.sleep(3)

    # Process all batches asynchronously
    task_id = thread_pool_manager.submit_task(process_batches)
    # await process_batches()

    return {"detail": "Processing existing CVitae records...", "task": task_id}
