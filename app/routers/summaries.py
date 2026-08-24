from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_summary import AISummary
from app.models.appointment import Appointment
from app.schemas.summary_schema import (
    PreVisitSummaryGenerateRequest,
    PreVisitSummaryResponse,
    PostVisitSummaryGenerateRequest,
    PostVisitSummaryResponse,
)
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/summaries", tags=["AI Summaries"])


@router.post("/pre-visit-preview", response_model=PreVisitSummaryResponse)
async def preview_pre_visit_summary(req: PreVisitSummaryGenerateRequest):
    """
    Direct endpoint to preview LLM Pre-Visit symptom triage using the exact prompt:
    'Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. Symptoms: <symptoms>'
    """
    res = await LLMService.generate_pre_visit_summary(req.symptoms)
    return PreVisitSummaryResponse(
        urgency_level=res.get("urgency_level", "Medium"),
        chief_complaint=res.get("chief_complaint", req.symptoms[:100]),
        suggested_questions=res.get("suggested_questions", []),
        is_fallback=res.get("is_fallback", False)
    )


@router.post("/post-visit-preview", response_model=PostVisitSummaryResponse)
async def preview_post_visit_summary(req: PostVisitSummaryGenerateRequest):
    """
    Direct endpoint to preview LLM Post-Visit summary using the exact prompt:
    'Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: <notes>'
    """
    res = await LLMService.generate_post_visit_summary(req.clinical_notes, req.prescriptions or "")
    return PostVisitSummaryResponse(
        patient_friendly_summary=res.get("patient_friendly_summary", req.clinical_notes),
        medication_schedule=res.get("medication_schedule", ""),
        follow_up_steps=res.get("follow_up_steps", ""),
        is_fallback=res.get("is_fallback", False)
    )


@router.get("/appointment/{appointment_id}")
def get_summary_by_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Retrieve saved AI summary for a specific appointment."""
    summary = db.query(AISummary).filter(AISummary.appointment_id == appointment_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="AI Summary not found for this appointment")

    return {
        "id": summary.id,
        "appointment_id": summary.appointment_id,
        "urgency_level": summary.urgency_level,
        "chief_complaint": summary.chief_complaint,
        "suggested_questions": summary.suggested_questions,
        "patient_friendly_summary": summary.patient_friendly_summary,
        "medication_schedule": summary.medication_schedule,
        "follow_up_steps": summary.follow_up_steps,
        "is_fallback": summary.is_fallback,
        "created_at": summary.created_at
    }
