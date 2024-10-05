from pydantic import BaseModel
from typing import List

class SkillCreateDTO(BaseModel):
    cargoId: int
    skills: List[str]
