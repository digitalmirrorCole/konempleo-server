from datetime import datetime
from io import BytesIO
import json
import os
import re
import time
from typing import List
from aiohttp import ClientError
from docx import Document
from fastapi import UploadFile, HTTPException
import openai
from pdf2image import convert_from_bytes
import pytesseract
from requests import Session
import boto3
import fitz
import requests
from requests.auth import HTTPBasicAuth
import traceback

from models.models import CVitae, VitaeOffer 

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# s3_client = boto3.client('s3', aws_access_key_id='your_access_key', aws_secret_access_key='your_secret_key', region_name='your_region')

# AWS S3 Bucket name
BUCKET_NAME = os.getenv("BUCKET_NAME")

s3_client = boto3.client(
    's3',
    aws_access_key_id= os.getenv("AWS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
)

openai.api_key =  os.getenv("OAI_KEY")

def upload_to_s3(file: UploadFile, s3_key: str) -> str:
    """
    Upload a file to S3 and return its URL.
    """
    try:
        # Reset the file pointer before uploading
        file.file.seek(0)

        # Upload file to S3
        s3_client.upload_fileobj(file.file, BUCKET_NAME, s3_key)

        # Construct and return the S3 URL
        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        return s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")

# Helper function to delete a file from S3
def delete_from_s3(url: str):
    """
    Delete a file from S3 using its URL.
    """
    try:
        # Extract bucket name and key from the URL
        match = re.match(r"https://(.+?).s3.amazonaws.com/(.+)", url)
        if not match:
            print(f"Invalid S3 URL: {url}")
            return
        bucket_name, key = match.groups()
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        print(f"Deleted file from S3: {url}")
    except ClientError as e:
        print(f"Failed to delete file from S3: {str(e)}")


def extract_text_from_pdf(file_content: bytes) -> str:
    try:
        # First, try to extract text using PyMuPDF
        with fitz.open(stream=file_content, filetype="pdf") as pdf_doc:
            text = ""
            for page in pdf_doc:
                page_text = page.get_text("text")
                if page_text.strip():  # If text is found, assume it's not an image
                    text += page_text

            # If text was found, return it
            if text.strip():
                return text

        # If no text, assume the PDF has images, so use OCR
        # Convert PDF pages to images
        images = convert_from_bytes(file_content)
        ocr_text = ""

        for image in images:
            try:
                # Use Tesseract for OCR
                ocr_result = pytesseract.image_to_string(image, lang='eng')  # Adjust lang as needed
                ocr_text += ocr_result + "\n"
            finally:
                # Ensure image resources are freed
                image.close()

        return ocr_text.strip()  # Return the OCR text

    except Exception as e:
        return f"An error occurred: {str(e)}"

def extract_text_from_docx(file_content: bytes) -> str:
    doc = Document(BytesIO(file_content))
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def clean_symbols(text):
  return re.sub(r'[^a-záéíóúA-Z0-9\s]', '', text)


def process_batch(
    batch: List[UploadFile],
    companyId: int,
    company_name: str,  # Add company_name as a parameter
    offerId: int,
    skills_list: List[str],
    city_offer: str,
    age_offer: str,
    genre_offer: str,
    experience_offer: int,
    db: Session
):
    try:
        cv_texts = []
        temp_cvitae_records = []

        # Extract text from each CV, upload to S3, and save temporary CVitae records
        for file in batch:
            file_extension = file.filename.split('.')[-1].lower()
            file_name = file.filename

            # Read the file content and reset pointer
            file_content = file.file.read()
            file.file.seek(0)

            # Extract text based on file type
            if file_extension == 'pdf':
                cv_text = extract_text_from_pdf(file_content)
            elif file_extension in ['docx', 'doc']:
                cv_text = extract_text_from_docx(file_content)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")

            cv_texts.append(f"### Candidate #{len(cv_texts) + 1} ###\n{cv_text}")

            # Upload file to S3
            s3_key = f"{company_name}/cvs/{file_name}"
            s3_url = upload_to_s3(file, s3_key)

            # Create a temporary CVitae record with the S3 URL
            temp_cvitae = CVitae(
                url=s3_url,
                companyId=companyId,
                extension=file_extension,
                cvtext=cv_text,
            )
            temp_cvitae_records.append(temp_cvitae)

        # Analyze CVs with GPT and create final records
        analyze_and_update_vitae_offers(
            cv_texts, skills_list, city_offer, age_offer, genre_offer, experience_offer, db, offerId, temp_cvitae_records
        )

    except Exception as e:
        db.rollback()
        print(f"Error processing batch: {str(e)}")
        raise


def analyze_and_update_vitae_offers(
    cv_texts: List[str],
    skills_list: List[str],
    city_offer: str,
    age_offer: str,
    genre_offer: str,
    experience_offer: int,
    db: Session,
    offerId: int,
    cvitae_records: List[CVitae]
):
    try:
        # Prepare the GPT prompt
        skills_list_str = ", ".join(skills_list)
        full_prompt = f"""
        Actúa como un experto en [Reclutamiento, Selección de Personal, Análisis de
        Hojas de Vida]. El objetivo de este super prompt es evaluar y calificar las hojas de
        vida de candidatos con base en una serie de criterios predefinidos. El sistema
        debe identificar las habilidades del candidato y compararlas con las solicitadas,
        calcular un puntaje general basado en diversos factores (habilidades, experiencia,
        tiempo promedio en cada cargo, nivel educativo, entre otros), y finalmente
        entregar un JSON con todos los datos recolectados del candidato.

        Variables Obligatorias:
        Se deben recibir y validar las siguientes variables de la oferta inicial. Si el
        candidato no cumple con alguna de estas cuatro variables (Ciudad, Edad,
        Género, Experiencia), será descartado automáticamente y su estado se
        marcará como “No apto” en el campo Status:
        1. Ciudad (City): Ciudad requerida para que el candidato sea considerado = {city_offer}
        2. Edad (Age): Rango de edad requerido para el candidato = {age_offer}
        3. Género (Genre): Género requerido según los lineamientos de la oferta = {genre_offer}
        4. Experiencia (Experience): Experiencia laboral mínima requerida (en años) = {experience_offer}

        Comparación de Variables Obligatorias:
        Estas comparaciones se deben realizar en el siguiente orden:
        1. Ciudad: Comparar la ciudad de residencia extraída del candidato con
        la ciudad especificada en la oferta. Si no coinciden, el candidato se marcará como
        “No apto”.
        2. Edad: Comparar la edad extraída del candidato con el rango de edad
        especificado en la oferta. Si no se encuentra dentro del rango, el candidato se
        marcará como “No apto”.
        3. Género: Comparar el género del candidato con el género
        especificado en la oferta. Si no coincide, el candidato se marcará como “No
        apto”.
        4. Experiencia: Comparar la experiencia laboral total del candidato con
        la experiencia mínima requerida en la oferta. Si no cumple con el mínimo
        requerido, el candidato se marcará como “No apto”.

        Parámetros a Extraer:
        1. Nombre del candidato: Extrae el nombre completo del candidato
        desde el campo correspondiente en su hoja de vida.
        2. Tipo de Documento: Extrae el Tipo de documento del candidato
        3. Número de identificación (Cédula): Extrae el número de
        identificación del candidato.
        4. Ciudad de residencia: Extrae la ciudad donde reside el candidato y
        compárala con la ciudad requerida en la oferta.
        5. Edad: Extrae la edad del candidato y verifica que esté dentro del
        rango de edad especificado en la oferta.
        6. Género: Extrae el género del candidato y verifica que coincida con el
        género especificado en la oferta.
        7. Experiencia laboral: Extrae los años de experiencia del candidato y
        verifica si cumple con la experiencia mínima requerida en la oferta.
        8. Habilidades encontradas vs Habilidades solicitadas: Compara las
        habilidades descritas en la hoja de vida del candidato con las habilidades
        solicitadas en la plataforma y genera una lista de coincidencias.
        9. Móvil (Teléfono de contacto): Extrae el número móvil del candidato.
        10. Correo electrónico: Extrae el correo electrónico del candidato.
        11. Score: Calcula el puntaje del candidato con base en habilidades,
            experiencia, tiempo promedio en cada cargo, nivel educativo, género, ciudad de
            residencia, entre otros factores.

        Ecuación del Score Final:
        Score HET:
        - H (Habilidades): Evaluar el grado de coincidencia entre las habilidades requeridas y las habilidades del candidato (escala de 0 a 10).
        - E (Experiencia): La experiencia laboral total en años del candidato (normalizada a una escala de 0 a 10).
        - T (Tiempo promedio en cada trabajo): Promedio de duración en meses de cada cargo del candidato (normalizado a una escala de 0 a 10).

        Habilidades Solicitadas:
        Las habilidades solicitadas en esta oferta son las siguientes: {skills_list_str}

        Ejemplo de JSON con los datos de un candidato:
        {{
            "nombre": "Juan Perez",
            "cedula": "80000000",
            "tipo_documento": "CC",
            "ciudad": "Bogota",
            "habilidades_encontradas": ["Habilidad1", "Habilidad2", "Habilidad3"],
            "habilidades_solicitadas": ["Habilidad1", "Habilidad2", "Habilidad3"],
            "genero": "Hombre",
            "movil": "3105555555",
            "correo": "juan@gmail.com",
            "score": 7.8,
            "experiencia_en_anos": 10,
            "tiempo_promedio_en_cada_trabajo": 36,
            "nivel_educativo": "Universitario",
            "edad": 30,
            "status": "Apto"
        }}

        ### Instrucciones:
        A continuación, se presentan los textos completos de los CVs de los candidatos para evaluar. Por cada CV:
        1. Evalúa las variables obligatorias (Ciudad, Edad, Género, Experiencia, habilidades).
        2. **Busca explícitamente palabras o frases en el texto que indiquen habilidades técnicas o blandas.** Comparar estas habilidades extraídas con las habilidades solicitadas y llena los campos "habilidades encontradas" y "habilidades solicitadas".
        3. Extrae la información relevante (nombre, cédula, ciudad, móvil, correo, etc.) y calcula el score final.
        4. Devuelve un único JSON que contenga una lista de candidatos con el estado (apto/no apto) y los datos extraídos en el siguiente formato:



        ### Textos de los CVs para Evaluar:
        {cv_texts}
            """

        # Send the request to GPT
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_prompt}
        ]
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=messages,
            temperature=0
        )
        raw_response = response.choices[0].message.content.strip()

        # Parse GPT response
        try:
            response_json = json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}, Raw response: {raw_response}")
            raise HTTPException(status_code=500, detail="Failed to parse GPT response.")

        candidates = response_json.get("candidatos", [])
        valid_cvitae = []

        # Process each candidate
        for idx, (temp_cvitae, candidate_data) in enumerate(zip(cvitae_records, candidates)):
            # Use fallback values for missing fields
            candidate_name = candidate_data.get("nombre", "name not found")

            candidate_email = candidate_data.get("correo", "email not found")

            # Create CVitae record with valid data
            temp_cvitae.candidate_name = candidate_name
            temp_cvitae.candidate_mail = candidate_email
            temp_cvitae.candidate_dni = candidate_data.get("cedula")
            temp_cvitae.candidate_dni_type = candidate_data.get("tipo_documento")
            temp_cvitae.candidate_city = candidate_data.get("ciudad")
            temp_cvitae.candidate_phone = candidate_data.get("movil")

            db.add(temp_cvitae)
            db.flush()  # Save the record to get an ID

            # Create VitaeOffer record
            vitae_offer = VitaeOffer(
                cvitaeId=temp_cvitae.Id,
                offerId=offerId,
                status="pending",
                ai_response=json.dumps(candidate_data),
                response_score=candidate_data.get("score",0),
            )
            db.add(vitae_offer)

            valid_cvitae.append(temp_cvitae)

        db.commit()

    except Exception as e:
        # Rollback changes and delete S3 files for all temporary CVitae records
        db.rollback()
        print(f"Error analyzing and creating CVitae/VitaeOffer records: {str(e)}")
        for temp_cvitae in cvitae_records:
            delete_from_s3(temp_cvitae.url)  # Delete the file from S3
        raise HTTPException(status_code=500, detail="An error occurred while analyzing and creating records.")


def fetch_background_check_result(job_id: str, cvitae_id: int, db: Session, retry_interval: int = 10, max_retries: int = 10):
    """
    Background task to fetch the background check result every `retry_interval` seconds
    until a definitive status is returned or the `max_retries` is reached.
    """
    url_get = f"https://dash-board.tusdatos.co/api/results/{job_id}"
    tusDatosUser = os.getenv("tusDatosUser")
    tusDatosSecret = os.getenv("tusDatosSecret")
    
    for attempt in range(max_retries):
        try:
            # Make the GET request to fetch the background check result
            response_get = requests.get(url_get, auth=HTTPBasicAuth(tusDatosUser, tusDatosSecret))
            response_get.raise_for_status()
            result_data = response_get.json()
        except requests.RequestException as e:
            print(f"Error fetching result for job ID {job_id}: {str(e)}")
            return

        status = result_data.get("estado")
        hallazgo = result_data.get("hallazgo")  # Should be true or false from service

        # Use a new session for each update
        with db.begin():  # Ensure each operation uses a new transaction
            cvitae = db.query(CVitae).filter(CVitae.Id == cvitae_id).first()
            if cvitae:
                # Update background_check only if hallazgo is not None
                if hallazgo is not None:
                    cvitae.background_check = str(hallazgo).lower()  # Save "true" or "false"
                    cvitae.background_date = datetime.utcnow()
                    print(f"Background check completed for CVitae ID {cvitae_id}. Final Status: {status}, Hallazgo: {hallazgo}")
                    return  # Stop retrying after getting a definitive result
                elif status == "procesando":
                    # Temporary status for "procesando"
                    cvitae.background_check = "No findings"
                    cvitae.background_date = datetime.utcnow()
                else:
                    # Handle unexpected states where hallazgo is None, and status is final
                    cvitae.background_check = "Error in results"
                    cvitae.background_date = datetime.utcnow()
                    print(f"Unexpected state for CVitae ID {cvitae_id}. Status: {status}, Hallazgo: {hallazgo}")
                    return

        print(f"Attempt {attempt + 1}: Status for CVitae ID {cvitae_id}: {status}, Hallazgo: {hallazgo}")

        # If the status is not "procesando", stop retrying even if hallazgo is None
        if status != "procesando":
            print(f"Final status reached for CVitae ID {cvitae_id} but no definitive hallazgo. Status: {status}")
            return

        time.sleep(retry_interval)

    # If max retries are reached
    print(f"Max retries reached for job ID {job_id}. Status for CVitae ID {cvitae_id} remains incomplete.")
    with db.begin():
        cvitae = db.query(CVitae).filter(CVitae.Id == cvitae_id).first()
        if cvitae:
            cvitae.background_check = "Max retries reached"
            cvitae.background_date = datetime.utcnow()




# Cache to store tokens and expiration times
token_cache = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": None
}

def get_token():
    """
    Retrieve a valid access token, refreshing it if necessary.
    """
    current_time = time.time()

    # If the access token is still valid, return it
    if token_cache["access_token"] and token_cache["expires_at"] > current_time:
        return token_cache["access_token"]

    # Retrieve credentials from environment variables
    username = os.getenv("SDUSERNAME")
    password = os.getenv("SDPASSWORD")
    basic_auth_token = os.getenv("SDBASIC_AUTH_TOKEN")

    print(username)
    print(password)
    print(basic_auth_token)

    if not username or not password or not basic_auth_token:
        raise HTTPException(status_code=500, detail="Authentication credentials are not properly configured.")

    # If no valid token, request a new one
    try:
        response = requests.post(
            "https://botai.smartdataautomation.com/api/o/token/",
            headers={
                "Authorization": f"Basic {basic_auth_token}"
            },
            data={
                "username": username,
                "password": password,
                "grant_type": "password"
            }
        )
        response.raise_for_status()
        token_data = response.json()

        # Update the token cache
        token_cache["access_token"] = token_data["access_token"]
        token_cache["refresh_token"] = token_data.get("refresh_token")
        token_cache["expires_at"] = current_time + token_data["expires_in"] - 10  # Buffer for safety

        return token_data["access_token"]

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve token: {str(e)}")

def process_existing_vitae_records(
    cvitae_ids: List[int],
    offerId: int,
    skills_list: List[str],
    city_offer: str,
    age_offer: str,
    genre_offer: str,
    experience_offer: int,
    db: Session
):
    """
    Process existing CVitae records by their IDs and create/update associated VitaeOffer records.
    This does not delete CVitae records on failure.
    """
    try:
        # Fetch CVitae records
        cvitae_records = db.query(CVitae).filter(CVitae.Id.in_(cvitae_ids)).all()
        if not cvitae_records or len(cvitae_records) != len(cvitae_ids):
            raise HTTPException(status_code=404, detail="One or more CVitae records not found.")

        # Prepare cv_texts for GPT processing
        cv_texts = [cv.cvtext for cv in cvitae_records]

        # Prepare the GPT prompt
        skills_list_str = ", ".join(skills_list)
        full_prompt = f"""
        Actúa como un experto en [Reclutamiento, Selección de Personal, Análisis de
        Hojas de Vida]. El objetivo de este super prompt es evaluar y calificar las hojas de
        vida de candidatos con base en una serie de criterios predefinidos. El sistema
        debe identificar las habilidades del candidato y compararlas con las solicitadas,
        calcular un puntaje general basado en diversos factores (habilidades, experiencia,
        tiempo promedio en cada cargo, nivel educativo, entre otros), y finalmente
        entregar un JSON con todos los datos recolectados del candidato.

        Variables Obligatorias:
        Se deben recibir y validar las siguientes variables de la oferta inicial. Si el
        candidato no cumple con alguna de estas cuatro variables (Ciudad, Edad,
        Género, Experiencia), será descartado automáticamente y su estado se
        marcará como “No apto” en el campo Status:
        1. Ciudad (City): Ciudad requerida para que el candidato sea considerado = {city_offer}
        2. Edad (Age): Rango de edad requerido para el candidato = {age_offer}
        3. Género (Genre): Género requerido según los lineamientos de la oferta = {genre_offer}
        4. Experiencia (Experience): Experiencia laboral mínima requerida (en años) = {experience_offer}

        Comparación de Variables Obligatorias:
        Estas comparaciones se deben realizar en el siguiente orden:
        1. Ciudad: Comparar la ciudad de residencia extraída del candidato con
        la ciudad especificada en la oferta. Si no coinciden, el candidato se marcará como
        “No apto”.
        2. Edad: Comparar la edad extraída del candidato con el rango de edad
        especificado en la oferta. Si no se encuentra dentro del rango, el candidato se
        marcará como “No apto”.
        3. Género: Comparar el género del candidato con el género
        especificado en la oferta. Si no coincide, el candidato se marcará como “No
        apto”.
        4. Experiencia: Comparar la experiencia laboral total del candidato con
        la experiencia mínima requerida en la oferta. Si no cumple con el mínimo
        requerido, el candidato se marcará como “No apto”.

        Parámetros a Extraer:
        1. Nombre del candidato: Extrae el nombre completo del candidato
        desde el campo correspondiente en su hoja de vida.
        2. Tipo de Documento: Extrae el Tipo de documento del candidato
        3. Número de identificación (Cédula): Extrae el número de
        identificación del candidato.
        4. Ciudad de residencia: Extrae la ciudad donde reside el candidato y
        compárala con la ciudad requerida en la oferta.
        5. Edad: Extrae la edad del candidato y verifica que esté dentro del
        rango de edad especificado en la oferta.
        6. Género: Extrae el género del candidato y verifica que coincida con el
        género especificado en la oferta.
        7. Experiencia laboral: Extrae los años de experiencia del candidato y
        verifica si cumple con la experiencia mínima requerida en la oferta.
        8. Habilidades encontradas vs Habilidades solicitadas: Compara las
        habilidades descritas en la hoja de vida del candidato con las habilidades
        solicitadas en la plataforma y genera una lista de coincidencias.
        9. Móvil (Teléfono de contacto): Extrae el número móvil del candidato.
        10. Correo electrónico: Extrae el correo electrónico del candidato.
        11. Score: Calcula el puntaje del candidato con base en habilidades,
            experiencia, tiempo promedio en cada cargo, nivel educativo, género, ciudad de
            residencia, entre otros factores.

        Ecuación del Score Final:
        Score HET:
        - H (Habilidades): Evaluar el grado de coincidencia entre las habilidades requeridas y las habilidades del candidato (escala de 0 a 10).
        - E (Experiencia): La experiencia laboral total en años del candidato (normalizada a una escala de 0 a 10).
        - T (Tiempo promedio en cada trabajo): Promedio de duración en meses de cada cargo del candidato (normalizado a una escala de 0 a 10).

        Habilidades Solicitadas:
        Las habilidades solicitadas en esta oferta son las siguientes: {skills_list_str}

        Ejemplo de JSON con los datos de un candidato:
        {{
            "nombre": "Juan Perez",
            "cedula": "80000000",
            "tipo_documento": "CC",
            "ciudad": "Bogota",
            "habilidades_encontradas": ["Habilidad1", "Habilidad2", "Habilidad3"],
            "habilidades_solicitadas": ["Habilidad1", "Habilidad2", "Habilidad3"],
            "genero": "Hombre",
            "movil": "3105555555",
            "correo": "juan@gmail.com",
            "score": 7.8,
            "experiencia_en_anos": 10,
            "tiempo_promedio_en_cada_trabajo": 36,
            "nivel_educativo": "Universitario",
            "edad": 30,
            "status": "Apto"
        }}

        ### Instrucciones:
        A continuación, se presentan los textos completos de los CVs de los candidatos para evaluar. Por cada CV:
        1. Evalúa las variables obligatorias (Ciudad, Edad, Género, Experiencia, habilidades).
        2. **Busca explícitamente palabras o frases en el texto que indiquen habilidades técnicas o blandas.** Comparar estas habilidades extraídas con las habilidades solicitadas y llena los campos "habilidades encontradas" y "habilidades solicitadas".
        3. Extrae la información relevante (nombre, cédula, ciudad, móvil, correo, etc.) y calcula el score final.
        4. Devuelve un único JSON que contenga una lista de candidatos con el estado (apto/no apto) y los datos extraídos en el siguiente formato:



        ### Textos de los CVs para Evaluar:
        {cv_texts}
            """

        # Send the request to GPT
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_prompt}
        ]
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo-16k",
                messages=messages,
                temperature=0
            )

        except openai.error.InvalidRequestError as e:
            print(f"Invalid Request Error: {e}")
            print(f"Response Body: {e.response.json()}")  # Log the body
        except Exception as e:
            print(f"Unhandled Error: {e}")

        raw_response = response.choices[0].message.content.strip()

        # Parse GPT response
        try:
            response_json = json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}, Raw response: {raw_response}")
            raise HTTPException(status_code=500,
                                detail="Failed to parse GPT response.")

        candidates = response_json.get("candidatos", [])

        # Process each candidate
        for idx, (cvitae, candidate_data) in enumerate(zip(cvitae_records,
                                                           candidates)):
            try:
                # Update/Create VitaeOffer record
                vitae_offer = db.query(VitaeOffer).filter(
                    VitaeOffer.cvitaeId == cvitae.Id,
                    VitaeOffer.offerId == offerId
                ).first()

                if vitae_offer:
                    # Update existing VitaeOffer
                    vitae_offer.ai_response = json.dumps(candidate_data)
                    vitae_offer.response_score = candidate_data.get("score", 0)
                    vitae_offer.status = "pending"
                else:
                    # Create new VitaeOffer
                    vitae_offer = VitaeOffer(
                        cvitaeId=cvitae.Id,
                        offerId=offerId,
                        status="pending",
                        ai_response=json.dumps(candidate_data),
                        response_score=candidate_data.get("score", 0),
                    )
                    db.add(vitae_offer)
            except Exception as e:
                print(traceback.format_exc())
                print(f"Error processing: {str(cvitae)}\nError: {str(e)}")

        db.commit()

    except Exception as e:
        # Rollback changes if something goes wrong
        print(traceback.format_exc())
        db.rollback()
        print(f"Error processing existing CVitae records: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing CVitae records.")
