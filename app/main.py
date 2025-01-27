import os
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.responses import FileResponse, JSONResponse
import yappi
from starlette.middleware.base import BaseHTTPMiddleware

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

class LimitRequestSizeMiddleware(BaseHTTPMiddleware):
    def _init_(self, app, max_body_size: int):
        super()._init_(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request, call_next):
        # Check if the request body exceeds the limit
        if request.headers.get("content-length") and int(request.headers["content-length"]) > self.max_body_size:
            return JSONResponse(
                {"detail": "Payload too large"}, status_code=413
            )
        return await call_next(request)

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
    file_name = "profiling_data.prof"
    
    # Stop profiling and save the data to a file
    yappi.stop()
    save_yappi_profile(file_name)
    
    # Return the saved file as a response for direct download
    return FileResponse(
        path=file_name,
        filename=file_name,
        media_type='application/octet-stream'
    )
