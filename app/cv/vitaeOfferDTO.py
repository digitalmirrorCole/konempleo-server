from datetime import date
from pydantic import BaseModel
from typing import Optional

class VitaeOfferResponseDTO(BaseModel):
    vitae_offer_id: int
    candidate_name: Optional[str]
    url: Optional[str]
    background_check: Optional[bool]
    background_date: Optional[date] = None
    candidate_phone: Optional[str]
    candidate_mail: Optional[str]
    smartdataId : Optional[str]
    whatsapp_status: Optional[str]
    response_score: Optional[float]
    status: Optional[str]
    comments: Optional[str]

class UpdateVitaeOfferStatusDTO(BaseModel):
    status: Optional[str]  # Status is now optional
    comments: Optional[str]  # New field for comments

class CampaignRequestDTO(BaseModel):
    candidate_phone: str
    candidate_name: str
    offer_name: str
    zone: str
    salary: str
    contract: str
    offerId: int
    vitae_offer_id: int 