from datetime import datetime
from http.client import HTTPException
import json
import os
import re
import time
from typing import List
from docx import Document
from fastapi import UploadFile
from openai import OpenAI
import openai
from requests import Session
import boto3
import fitz
import requests
from requests.auth import HTTPBasicAuth


from models.models import CVitae, VitaeOffer 

# s3_client = boto3.client('s3', aws_access_key_id='your_access_key', aws_secret_access_key='your_secret_key', region_name='your_region')

# AWS S3 Bucket name
BUCKET_NAME = "your_s3_bucket_name"

client = OpenAI(
  api_key= os.getenv("OPENAI_KEY", "none"),
)

s3_client = boto3.client(
    's3',
    aws_access_key_id='your_access_key_id',
    aws_secret_access_key='your_secret_access_key'
)


def upload_to_s3(file: UploadFile, filename: str):
    try:
        s3_client.upload_fileobj(file.file, BUCKET_NAME, filename)
        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
        return s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")

def extract_text_from_pdf(file: UploadFile) -> str:
    pdf_doc = fitz.open(stream=file.file.read(), filetype="pdf")
    text = ""
    for page in pdf_doc:
        text += page.get_text("text")
    return text

def extract_text_from_docx(file: UploadFile) -> str:
    doc = Document(file.file)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def clean_symbols(text):
  return re.sub(r'[^a-záéíóúA-Z0-9\s]', '', text)


def process_batch(batch: List[UploadFile], companyId: int, offerId: int, skills_list: List[str], db: Session):
    """
    Process a batch of 10 CV files, send them to GPT-4-turbo-128k, and update the vitae_offer records.
    """
    try:
        cv_texts = []
        cvitae_records = []

        for file in batch:
            file_extension = file.filename.split('.')[-1].lower()

            # Upload to S3
            s3_filename = f"{companyId}/{file.filename}"
            s3_url = upload_to_s3(file, s3_filename)

            # Extract text based on file type
            if file_extension == 'pdf':
                cv_text = extract_text_from_pdf(file)
            elif file_extension in ['docx', 'doc']:
                cv_text = extract_text_from_docx(file)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")

            # Store the CV text for GPT and create the CVitae record
            cv_texts.append(cv_text)
            cvitae = CVitae(
                url=s3_url,
                companyId=companyId,
                cv_text=cv_text
            )
            db.add(cvitae)
            db.flush()  # Get the CVitae ID
            cvitae_records.append(cvitae)

            # Create VitaeOffer record for each CV
            vitae_offer = VitaeOffer(
                cvitaeId=cvitae.Id,
                offerId=offerId,
                status='pending'
            )
            db.add(vitae_offer)

        db.flush()  # Ensure all CVitae and VitaeOffer records are stored in DB

        # Send batch of CV texts to GPT-4-turbo-128k in one request
        messages = [
            {
                "role": "system",
                "content": "You are an expert in recruitment. Analyze the following CV texts and compare them against the required skills for a job offer."
            },
            {
                "role": "user",
                "content": f"CV texts:\n{', '.join(cv_texts)}\nSkills required: {', '.join(skills_list)}"
            }
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4-turbo-128k",
            messages=messages,
            max_tokens=8000  # Adjust as needed for token usage
        )

        # Assume GPT responds with an array of responses for each CV
        gpt_responses = response.choices[0].message['content'].strip().split("\n\n")  # Split individual CV responses

        for idx, cvitae in enumerate(cvitae_records):
            gpt_result = gpt_responses[idx].strip() if idx < len(gpt_responses) else "No response from GPT"
            
            # Mock score calculation, adjust as per actual logic
            response_score = 0.8  # Simplified scoring, replace with proper logic

            # Update the VitaeOffer record with AI response and score
            vitae_offer = db.query(VitaeOffer).filter(VitaeOffer.cvitaeId == cvitae.Id, VitaeOffer.offerId == offerId).first()
            vitae_offer.ai_response = gpt_result
            vitae_offer.response_score = response_score
            vitae_offer.status = 'completed'

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing batch: {str(e)}")


def fetch_background_check_result(job_id: str, cvitae_id: int, db: Session, retry_interval: int = 10, max_retries: int = 10):
    """
    Background task to fetch the background check result every `retry_interval` seconds
    until a status different from "procesando" is returned or the `max_retries` is reached.
    Saves the result after every retry attempt.
    """
    # Fetch the CVitae record by ID
    cvitae = db.query(CVitae).filter(CVitae.Id == cvitae_id).first()
    if not cvitae:
        print(f"CVitae record with ID {cvitae_id} not found")
        return

    url_get = f"https://dash-board.tusdatos.co/api/results/{job_id}"

    tusDatosUser= os.getenv("tusDatosUser")
    tusDatosSecret= os.getenv("tusDatosSecret")
    
    for attempt in range(max_retries):
        try:
            # Make the GET request to fetch the background check result
            response_get = requests.get(url_get, auth=HTTPBasicAuth(tusDatosUser, tusDatosSecret))
            response_get.raise_for_status()
            result_data = response_get.json()
        except requests.RequestException as e:
            print(f"Error fetching result for job ID {job_id}: {str(e)}")
            return

        # Extract relevant fields from the response
        status = result_data.get("estado")
        hallazgo = result_data.get("hallazgo")  # Findings from the response
        
        # Save the result, regardless of whether the status is "procesando"
        cvitae.background_check = f"{hallazgo}"
        cvitae.background_date = datetime.utcnow()  # Update the timestamp for when the background check is saved
        db.commit()
        
        print(f"Attempt {attempt + 1}: Saved status and findings for CVitae ID {cvitae_id}. Status: {status}")

        # If the status is no longer "procesando", exit the loop and stop retrying
        if status != "procesando":
            print(f"Background check completed for CVitae ID {cvitae_id}. Final Status: {status}")
            return  # Exit after saving the final result

        # Wait before the next attempt if status is still "procesando"
        time.sleep(retry_interval)

    # If max retries are reached and status is still "procesando"
    print(f"Max retries reached. Background check for job ID {job_id} is still processing after {max_retries} attempts.")

