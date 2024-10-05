from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
import os
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, FastAPI, BackgroundTasks
from requests import Session

from app.cv.cvService import fetch_background_check_result, process_batch
from app.deps import get_db
from models.models import Company, Offer, CVitae, OfferSkill, Skill
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
    db: Session = Depends(get_db)
):
    """
    Upload CV files, process in batches of 10, analyze with GPT-4-turbo-128k, and save results.
    """
    company = db.query(Company).filter(Company.id == companyId).first()
    offer = db.query(Offer).filter(Offer.id == offerId).first()

    if not company or not offer:
        raise HTTPException(status_code=404, detail="Company or Offer not found")

    # Fetch the offer skills
    offer_skills = db.query(Skill).join(OfferSkill).filter(OfferSkill.offerId == offerId).all()
    if not offer_skills:
        raise HTTPException(status_code=404, detail="No skills found for the given offer.")
    skills_list = [skill.name for skill in offer_skills]

    # Split files into batches of 10
    file_batches = [files[i:i+10] for i in range(0, len(files), 10)]

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_batch, batch, companyId, offerId, skills_list, db) for batch in file_batches]

    # Wait for all batches to complete
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

