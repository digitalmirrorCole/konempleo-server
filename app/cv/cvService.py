from http.client import HTTPException
import json
import os
import re
from docx import Document
from fastapi import UploadFile
from openai import OpenAI
from requests import Session
import boto3
import fitz


from models.models import CVitae, VitaeOffer 

# s3_client = boto3.client('s3', aws_access_key_id='your_access_key', aws_secret_access_key='your_secret_key', region_name='your_region')

# AWS S3 Bucket name
BUCKET_NAME = "your_s3_bucket_name"

client = OpenAI(
  api_key= os.getenv("OPENAI_KEY", "none"),
)


""" def upload_to_s3(file: UploadFile, filename: str):
    try:
        s3_client.upload_fileobj(file.file, BUCKET_NAME, filename)
        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
        return s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}") """

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


def process_file(file: UploadFile, companyId: int, offerId: int, db: Session):
    try:
        # Upload to S3
        file_extension = file.filename.split('.')[-1].lower()
        """ s3_filename = f"{companyId}/{file.filename}"
        s3_url = upload_to_s3(file, s3_filename) """

        # Extract text from the file
        if file_extension == 'pdf':
            cv_text = extract_text_from_pdf(file)
        elif file_extension in ['docx', 'doc']:
            cv_text = extract_text_from_docx(file)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")
        
        habilidades = ['manejo','audifonos','responsabilidad']

        response = client.chat.completions.create(
        model="gpt-4",  # Use GPT-4 model
        messages=[
            {"role": "system", "content": "Asume que eres un experto en reclutamiento de empresa."},
            {"role": "user", "content": f"""Asume que eres un experto en reclutamiento de empresa al cual se le ha dado la siguiente hoja de vida: {cv_text}
            Identifica los siguientes datos de la hoja de vida: Nombre del postulante, Correo, Telefono celular, Genero (las posibles opciones de generos son Masculino o Femenino), Nivel educativo (Nivel educativo maximo alcanzado por el postulante), Años de experiencia, Duración promedio en los trabajos (El calculo de la duración promedio en los trabajos se debe realizar haciendo uso de la unidad de tiempo de MES y se debe calcular de la siguiente forma div(<duración total en meses>, <número de trabajos>) ), Habilidades (Se debe comprobar y seleccionar que posee el postulante y que se encuentran en la lista de habilidades).

            The output should be formatted as a JSON instance that conforms to the JSON schema below.

            Here is the output schema:
            {{
                "properties": {{
                    "nombre": {{
                        "title": "Nombre",
                        "description": "Nombre completo del postulante.",
                        "type": "string"
                    }},
                    "correo": {{
                        "title": "Correo",
                        "description": "Correo del postulante.",
                        "type": "string"
                    }},
                    "telefono": {{
                        "title": "Telefono",
                        "description": "Telefono celular del postulante.",
                        "type": "string"
                    }},
                    "genero": {{
                        "description": "Genero del postulante. Los posibles generos son Masculino y Femenino",
                        "allOf": [{{"$ref": "#/definitions/Generos"}}]
                    }},
                    "educacion": {{
                        "description": "Nivel educativo del postulante.",
                        "allOf": [{{"$ref": "#/definitions/Educations"}}]
                    }},
                    "experiencia": {{
                        "title": "Experiencia",
                        "description": "Años totales de experiencia mencionados en la hoja de vida",
                        "type": "number"
                    }},
                    "duracionPromedio": {{
                        "title": "Duracionpromedio",
                        "description": "Duración promedio en los trabajos en meses",
                        "type": "number"
                    }},
                    "habilidades": {{
                        "description": "Lista de habilidades que posee el postulante y que coinciden con los requerimientos del puesto",
                        "type": "array",
                        "items": {{"$ref": "#/definitions/habilidades"}}
                    }}
                }},
                "required": ["nombre", "correo", "telefono", "genero", "educacion", "experiencia", "duracionPromedio", "habilidades"],
                "definitions": {{
                    "Generos": {{
                        "title": "Generos",
                        "description": "An enumeration.",
                        "enum": ["Masculino", "Femenino"],
                        "type": "string"
                    }},
                    "Educations": {{
                        "title": "Educations",
                        "description": "An enumeration.",
                        "enum": ["Preescolar", "Educación Básica Primaria", "Educación Básica media o Bachiller", "Educación Técnica Profesional", "Educación Tecnológica", "Educación Profesional Universitaria", "Especialización", "Maestría", "Doctorado"],
                        "type": "string"
                    }},
                    "habilidades": {{
                        "title": "habilidades",
                        "description": "Lista de habilidades del postulante.",
                        "enum": {json.dumps(habilidades)}
                    }}
                }}
            }}
            """}
            ],
            temperature=0.7
        )

        print(f"{response}")

        # Save CVitae record in the database
        """ cvitae = CVitae(
            url=s3_url,
            companyId=companyId,
            cv_text=cv_text
        )
        db.add(cvitae)
        db.flush()  # To get the CVitae id

        # Create the VitaeOffer record
        vitae_offer = VitaeOffer(
            cvitaeId=cvitae.Id,
            offerId=offerId,
            status='pending'
        )
        db.add(vitae_offer)
        db.flush()  # Get VitaeOffer ID

        # Call OpenAI API to process the extracted text
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=f"Analyze the following CV text and provide a summary and score:\n\n{cv_text}",
            max_tokens=150
        )
        ai_response = response.choices[0].text.strip()
        response_score = float(response.choices[0].logprobs['token_logprobs'][0])  # Mock score calculation

        # Update the VitaeOffer with AI response
        vitae_offer.ai_response = ai_response
        vitae_offer.response_score = response_score
        db.commit() """

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")