from typing import List, Optional
from pydantic import BaseModel


class PreVisitSummaryGenerateRequest(BaseModel):
    symptoms: str


class PreVisitSummaryResponse(BaseModel):
    urgency_level: str  # 'Low', 'Medium', 'High'
    chief_complaint: str
    suggested_questions: List[str]
    is_fallback: bool = False


class PostVisitSummaryGenerateRequest(BaseModel):
    clinical_notes: str
    prescriptions: Optional[str] = None


class PostVisitSummaryResponse(BaseModel):
    patient_friendly_summary: str
    medication_schedule: str
    follow_up_steps: str
    is_fallback: bool = False
