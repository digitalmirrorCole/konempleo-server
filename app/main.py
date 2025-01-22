import os
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.responses import FileResponse
import yappi

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

app = FastAPI(
    title='DeepTalent API',
    description=description,
    version='0.0.1',
    summary='REST API for deepTalent'
)

aws_key = os.getenv("AWS_KEY")
aws_secret_key = os.getenv("AWS_SECRET_KEY")
bucket_name = os.getenv("BUCKET_NAME")

if not aws_key or not aws_secret_key or not bucket_name:
    logger.error("AWS credentials or bucket name are missing!")
else:
    # Log partial values for debugging
    logger.info(f"AWS_KEY: {aws_key}***")
    logger.info(f"AWS_SECRET_KEY: {aws_secret_key}***")

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


# Start profiling when the application starts
@app.on_event("startup")
async def start_profiling():
    print("Starting Yappi profiling...")
    yappi.set_clock_type("wall")  # Options: 'wall', 'cpu'
    yappi.start()

# Stop profiling and save data when the application stops
@app.on_event("shutdown")
async def stop_profiling():
    print("Stopping Yappi profiling...")
    yappi.stop()
    save_yappi_profile("profiling_data.prof")

def save_yappi_profile(file_name: str):
    # Save profiling results to a .prof file
    yappi.get_func_stats().save(file_name, type="pstat")
    print(f"Yappi profiling data saved to {file_name}")

# Optional: Expose an endpoint to download profiling data
@app.get("/download-profile")
async def download_profile():
    yappi.stop()
    save_yappi_profile("profiling_data.prof")
    return {"message": "Profiling data saved to profiling_data.prof"}

# Endpoint to download the profiling data file
@app.get("/download-profile-file", response_class=FileResponse)
async def download_profile_file():
    file_path = "profiling_data.prof"
    # yappi.stop()  # Ensure profiling is stopped
    # save_yappi_profile(file_path)  # Save the profiling data
    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename="profiling_data.prof"
    )
