from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile
from requests import Session

from app.cv.cvService import process_file
from app.deps import get_db
from models.models import Company, Offer

cvRouter = APIRouter()
cvRouter.tags = ['CV']

@cvRouter.post("/offers/upload-cvs/", status_code=201, response_model=None)
def upload_cvs(companyId: int, offerId: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Uploads CV files, extracts text, uploads to S3, processes with OpenAI, and saves the data.
    """
    company = db.query(Company).filter(Company.id == companyId).first()
    offer = db.query(Offer).filter(Offer.id == offerId).first()
    """ if not company or not offer:
        raise HTTPException(status_code=404, detail="Company or Offer not found") """

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_file, file, companyId, offerId, db) for file in files]

    for future in futures:
        future.result()

    return {"detail": "All files processed successfully"}