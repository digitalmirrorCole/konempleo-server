import os
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

import openai

from app.company.companyController import companyRouter
from app.user.userController import userRouter
from app.auth.authController import authRouter
from app.offer.offerController import offerRouter
from app.cv.cvController import cvRouter
from app.cargo.cargoController import cargoRouter
from app.skill.skillController import skillRouter
from app.health.healthController import healthRouter

description = """
All these configurations are suggested in the doc and
are used in the OpenAPI specification and the automatic API docs UIs.

This is a test of the description. 🚀
"""

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("fastapi_logs.log"),  # Log to a file
        logging.StreamHandler()  # Also log to the console
    ]
)

logger = logging.getLogger(__name__)

openai.api_key =  os.getenv("OPENAI_API_KEY")

# Check if OpenAI API key is set
if not openai.api_key:
    logger.error("OpenAI API key is not set or is empty.")
else:
    logger.info(f"Loaded OpenAI API key: {openai.api_key[:5]}...")
    logger.info(f"Loaded OpenAI API key: {openai.api_key}...")

app = FastAPI(
    title='DeepTalent API',
    description=description,
    version='0.0.1',
    summary='REST API for deepTalent'
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request details
    logger.info(f"New request: {request.method} {request.url}")
    
    # Call the next middleware or endpoint
    response = await call_next(request)

    # Log response status
    logger.info(f"Response status: {response.status_code}")
    
    return response

api_router = APIRouter()

app.include_router(companyRouter)
app.include_router(userRouter)
app.include_router(authRouter)
app.include_router(offerRouter)
app.include_router(cvRouter)
app.include_router(cargoRouter)
app.include_router(skillRouter)
app.include_router(healthRouter)
