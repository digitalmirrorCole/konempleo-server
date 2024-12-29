from pydantic import BaseModel
from typing import Optional

class VitaeOfferResponseDTO(BaseModel):
    vitae_offer_id: int
    candidate_name: str
    url: Optional[str]
    background_check: Optional[bool]
    candidate_phone: Optional[str]
    candidate_mail: Optional[str]
    whatsapp_status: Optional[str]
    response_score: Optional[float]
    status: Optional[str]

class UpdateVitaeOfferStatusDTO(BaseModel):
    status: str
