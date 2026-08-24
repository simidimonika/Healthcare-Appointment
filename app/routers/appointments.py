import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.doctor_profile import DoctorProfile
from app.models.user import User
from app.models.ai_summary import AISummary
from app.models.medication_schedule import MedicationSchedule
from app.schemas.appointment_schema import (
    SlotHoldRequest,
    SlotHoldResponse,
    AppointmentConfirmRequest,
    AppointmentRescheduleRequest,
    ConsultationCompleteRequest,
    AppointmentResponse,
    AISummaryDTO,
    MedicationItemDTO,
)
from app.services.auth_service import get_current_user, require_role
from app.services.booking_service import BookingService
from app.services.calendar_service import CalendarService
from app.services.llm_service import LLMService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


def _to_dto(appt: Appointment) -> AppointmentResponse:
    ai_dto = None
    if appt.ai_summary:
        ai_dto = AISummaryDTO(
            id=appt.ai_summary.id,
            urgency_level=appt.ai_summary.urgency_level,
            chief_complaint=appt.ai_summary.chief_complaint,
            suggested_questions=appt.ai_summary.suggested_questions,
            patient_friendly_summary=appt.ai_summary.patient_friendly_summary,
            medication_schedule=appt.ai_summary.medication_schedule,
            follow_up_steps=appt.ai_summary.follow_up_steps,
            is_fallback=appt.ai_summary.is_fallback
        )

    med_dtos = []
    for med in appt.medications:
        med_dtos.append(MedicationItemDTO(
            id=med.id,
            medication_name=med.medication_name,
            dosage=med.dosage,
            frequency=med.frequency,
            duration_days=med.duration_days,
            reminder_times=med.reminder_times,
            start_date=med.start_date,
            status=med.status
        ))

    gcal_link = CalendarService.generate_google_calendar_url(appt) if appt.status in ["confirmed", "completed"] else None

    return AppointmentResponse(
        id=appt.id,
        patient_id=appt.patient_id,
        patient_name=appt.patient.full_name if appt.patient else "Patient",
        patient_email=appt.patient.email if appt.patient else None,
        doctor_id=appt.doctor_id,
        doctor_name=appt.doctor.user.full_name if appt.doctor and appt.doctor.user else "Doctor",
        doctor_specialisation=appt.doctor.specialisation if appt.doctor else None,
        appointment_date=appt.appointment_date,
        start_time=appt.start_time,
        end_time=appt.end_time,
        status=appt.status,
        held_until=appt.held_until,
        symptoms_raw=appt.symptoms_raw,
        clinical_notes_raw=appt.clinical_notes_raw,
        prescription_raw=appt.prescription_raw,
        google_calendar_event_id=appt.google_calendar_event_id,
        google_calendar_link=gcal_link,
        created_at=appt.created_at,
        ai_summary=ai_dto,
        medications=med_dtos
    )


@router.post("/hold", response_model=SlotHoldResponse)
def hold_slot(
    req: SlotHoldRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atomically place a temporary hold on a time slot for 5 minutes."""
    appt = BookingService.hold_slot(
        db=db,
        doctor_id=req.doctor_id,
        appointment_date=req.appointment_date,
        start_time=req.start_time,
        patient_id=current_user.id
    )
    return SlotHoldResponse(
        appointment_id=appt.id,
        doctor_id=appt.doctor_id,
        appointment_date=appt.appointment_date,
        start_time=appt.start_time,
        end_time=appt.end_time,
        status=appt.status,
        held_until=appt.held_until,
        hold_duration_seconds=300
    )


@router.post("/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    req: AppointmentConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm booking from held state. Submits symptoms, generates AI pre-visit summary,
    creates calendar sync, and sends confirmation emails.
    """
    appt = await BookingService.confirm_booking(
        db=db,
        appointment_id=req.appointment_id,
        symptoms=req.symptoms,
        patient_id=current_user.id
    )
    return _to_dto(appt)


@router.get("/patient", response_model=List[AppointmentResponse])
def get_my_patient_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all appointments for the logged-in patient."""
    appts = db.query(Appointment).filter(
        Appointment.patient_id == current_user.id
    ).order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc()).all()
    return [_to_dto(a) for a in appts]


@router.get("/doctor", response_model=List[AppointmentResponse])
def get_my_doctor_appointments(
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    """List all appointments assigned to the logged-in doctor."""
    doc = current_user.doctor_profile
    if not doc and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="User does not have an active doctor profile.")
    
    query = db.query(Appointment)
    if doc:
        query = query.filter(Appointment.doctor_id == doc.id)
    
    appts = query.order_by(Appointment.appointment_date.desc(), Appointment.start_time.asc()).all()
    return [_to_dto(a) for a in appts]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment_detail(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single appointment details with authorization checks."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Authorization
    if current_user.role == "patient" and appt.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if current_user.role == "doctor" and appt.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return _to_dto(appt)


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment_endpoint(
    appointment_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an appointment."""
    appt = await BookingService.cancel_appointment(db=db, appointment_id=appointment_id, user=current_user, reason=reason)
    return _to_dto(appt)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment_endpoint(
    appointment_id: int,
    req: AppointmentRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reschedule an existing or conflict-flagged appointment to a new slot."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == "patient" and appt.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    doctor = appt.doctor
    if req.new_date in doctor.leave_days:
        raise HTTPException(status_code=400, detail="Doctor is on leave on the selected new date.")

    # Check slot availability
    existing_slot = db.query(Appointment).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == req.new_date,
        Appointment.start_time == req.new_start_time,
        Appointment.id != appointment_id,
        Appointment.status.in_(["confirmed", "completed", "held"])
    ).first()

    if existing_slot:
        raise HTTPException(status_code=409, detail="Selected reschedule slot is unavailable.")

    # Update slot
    old_date = appt.appointment_date
    old_time = appt.start_time
    appt.appointment_date = req.new_date
    appt.start_time = req.new_start_time
    appt.end_time = BookingService._add_minutes_to_time(req.new_start_time, doctor.slot_duration_minutes)
    appt.status = "confirmed"
    appt.held_until = None
    db.commit()

    # Sync calendar
    await CalendarService.sync_google_calendar_event(appt, action="update")

    # Notify patient & doctor
    NotificationService.dispatch_notification(
        db=db,
        recipient=appt.patient,
        notification_type="reschedule_notice",
        subject=f"Rescheduled: Appointment with Dr. {doctor.user.full_name}",
        body=f"<p>Your appointment has been successfully rescheduled from {old_date} {old_time} to <strong>{appt.appointment_date} at {appt.start_time}</strong>.</p>",
        appointment_id=appt.id
    )

    return _to_dto(appt)


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
async def complete_consultation(
    appointment_id: int,
    req: ConsultationCompleteRequest,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Doctor completes consultation by submitting clinical notes and prescriptions.
    Triggers AI post-visit patient-friendly summary and creates medication reminder schedules.
    """
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == "doctor" and appt.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doctor can only complete their own appointments.")

    # Format prescriptions string
    rx_lines = []
    for rx in req.prescriptions:
        rx_lines.append(f"{rx.medication_name} ({rx.dosage}) - {rx.frequency} for {rx.duration_days} days. {rx.instructions or ''}")
    prescriptions_str = "\n".join(rx_lines)

    appt.clinical_notes_raw = req.clinical_notes
    appt.prescription_raw = prescriptions_str
    appt.status = "completed"
    db.commit()

    # Generate AI Post-Visit Summary
    post_summary_data = await LLMService.generate_post_visit_summary(
        clinical_notes=req.clinical_notes,
        prescriptions=prescriptions_str
    )

    ai_sum = appt.ai_summary
    if not ai_sum:
        ai_sum = AISummary(appointment_id=appt.id)
        db.add(ai_sum)

    ai_sum.patient_friendly_summary = post_summary_data.get("patient_friendly_summary")
    ai_sum.medication_schedule = post_summary_data.get("medication_schedule")
    ai_sum.follow_up_steps = post_summary_data.get("follow_up_steps")
    ai_sum.is_fallback = post_summary_data.get("is_fallback", False)
    db.commit()

    # Register Medication Schedules for background reminders
    today_iso = datetime.now().strftime("%Y-%m-%d")
    for rx in req.prescriptions:
        reminder_times = ["09:00"]
        freq_lower = rx.frequency.lower()
        if "twice" in freq_lower or "2" in freq_lower or "12" in freq_lower:
            reminder_times = ["09:00", "21:00"]
        elif "three" in freq_lower or "3" in freq_lower or "8" in freq_lower:
            reminder_times = ["08:00", "14:00", "20:00"]
        elif "night" in freq_lower or "bed" in freq_lower:
            reminder_times = ["21:30"]

        med_sched = MedicationSchedule(
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            medication_name=rx.medication_name,
            dosage=rx.dosage,
            frequency=rx.frequency,
            duration_days=rx.duration_days,
            start_date=today_iso,
            status="active"
        )
        med_sched.reminder_times = reminder_times
        db.add(med_sched)

    db.commit()

    # Notify patient with post-visit summary
    body = (
        f"<h2>Post-Visit Care Plan Ready</h2>"
        f"<p>Dear {appt.patient.full_name},</p>"
        f"<p>Dr. {appt.doctor.user.full_name} has finalized your post-visit summary and prescription.</p>"
        f"<p><strong>Summary:</strong><br/>{ai_sum.patient_friendly_summary}</p>"
        f"<p><strong>Medication Schedule:</strong><br/>{ai_sum.medication_schedule}</p>"
        f"<p><strong>Follow-up Instructions:</strong><br/>{ai_sum.follow_up_steps}</p>"
    )
    NotificationService.dispatch_notification(
        db=db,
        recipient=appt.patient,
        notification_type="post_visit_summary",
        subject=f"Post-Visit Care Summary: Appointment #{appt.id}",
        body=body,
        appointment_id=appt.id
    )

    db.refresh(appt)
    return _to_dto(appt)
