from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SlotHoldRequest(BaseModel):
    doctor_id: int
    appointment_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")               # HH:MM


class SlotHoldResponse(BaseModel):
    appointment_id: int
    doctor_id: int
    appointment_date: str
    start_time: str
    end_time: str
    status: str
    held_until: datetime
    hold_duration_seconds: int


class SymptomIntakeRequest(BaseModel):
    symptoms: str = Field(..., min_length=5, description="Patient symptom description")


class AppointmentConfirmRequest(BaseModel):
    appointment_id: int
    symptoms: str = Field(..., min_length=5, description="Detailed patient symptoms")


class AppointmentRescheduleRequest(BaseModel):
    new_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    new_start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")


class PrescriptionItem(BaseModel):
    medication_name: str
    dosage: str
    frequency: str  # e.g., "Twice Daily", "Once Daily Morning", "Every 8 Hours"
    duration_days: int = 7
    instructions: Optional[str] = None


class ConsultationCompleteRequest(BaseModel):
    clinical_notes: str = Field(..., min_length=5, description="Doctor's clinical findings and diagnosis")
    prescriptions: List[PrescriptionItem] = []
    follow_up_advice: Optional[str] = None


class AISummaryDTO(BaseModel):
    id: Optional[int] = None
    urgency_level: Optional[str] = None
    chief_complaint: Optional[str] = None
    suggested_questions: List[str] = []
    patient_friendly_summary: Optional[str] = None
    medication_schedule: Optional[str] = None
    follow_up_steps: Optional[str] = None
    is_fallback: bool = False

    model_config = ConfigDict(from_attributes=True)


class MedicationItemDTO(BaseModel):
    id: int
    medication_name: str
    dosage: str
    frequency: str
    duration_days: int
    reminder_times: List[str]
    start_date: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    doctor_id: int
    doctor_name: Optional[str] = None
    doctor_specialisation: Optional[str] = None
    appointment_date: str
    start_time: str
    end_time: str
    status: str
    held_until: Optional[datetime] = None
    symptoms_raw: Optional[str] = None
    clinical_notes_raw: Optional[str] = None
    prescription_raw: Optional[str] = None
    google_calendar_event_id: Optional[str] = None
    google_calendar_link: Optional[str] = None
    created_at: datetime
    ai_summary: Optional[AISummaryDTO] = None
    medications: List[MedicationItemDTO] = []

    model_config = ConfigDict(from_attributes=True)
