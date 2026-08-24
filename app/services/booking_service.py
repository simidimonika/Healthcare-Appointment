from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.config import settings
from app.models.appointment import Appointment
from app.models.doctor_profile import DoctorProfile
from app.models.ai_summary import AISummary
from app.models.user import User
from app.schemas.doctor_schema import TimeSlot, DoctorAvailabilityResponse
from app.services.calendar_service import CalendarService
from app.services.llm_service import LLMService
from app.services.notification_service import NotificationService


class BookingService:
    @staticmethod
    def _add_minutes_to_time(time_str: str, minutes: int) -> str:
        """Helper to calculate slot end time."""
        t = datetime.strptime(time_str, "%H:%M")
        t_end = t + timedelta(minutes=minutes)
        return t_end.strftime("%H:%M")

    @classmethod
    def get_doctor_availability(
        cls,
        db: Session,
        doctor_id: int,
        date_str: str,
        current_user_id: Optional[int] = None
    ) -> DoctorAvailabilityResponse:
        """Compute slot availability for a doctor on a specific date with real-time hold detection."""
        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        # Parse date and day of week
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = target_date.strftime("%A")
        is_working_day = day_name in doctor.working_days
        is_on_leave = date_str in doctor.leave_days

        if not is_working_day or is_on_leave:
            return DoctorAvailabilityResponse(
                doctor_id=doctor.id,
                doctor_name=doctor.user.full_name,
                specialisation=doctor.specialisation,
                date=date_str,
                is_working_day=is_working_day,
                is_on_leave=is_on_leave,
                slot_duration_minutes=doctor.slot_duration_minutes,
                slots=[]
            )

        # Generate theoretical time slots
        slots: List[TimeSlot] = []
        current_time = datetime.strptime(doctor.working_hours_start, "%H:%M")
        end_work_time = datetime.strptime(doctor.working_hours_end, "%H:%M")
        duration = timedelta(minutes=doctor.slot_duration_minutes)

        # Query all active or held appointments on this date
        now = datetime.utcnow()
        active_appts = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date_str,
            Appointment.status.in_(["confirmed", "completed", "held"])
        ).all()

        # Map active appointments by start_time
        booked_map: Dict[str, Appointment] = {}
        for appt in active_appts:
            if appt.status in ["confirmed", "completed"]:
                booked_map[appt.start_time] = appt
            elif appt.status == "held":
                # Check if hold is still valid
                if appt.held_until and appt.held_until > now:
                    booked_map[appt.start_time] = appt

        while current_time + duration <= end_work_time:
            s_time = current_time.strftime("%H:%M")
            e_time = (current_time + duration).strftime("%H:%M")

            is_available = True
            is_held_by_me = False
            status_reason = None

            if s_time in booked_map:
                appt = booked_map[s_time]
                if appt.status in ["confirmed", "completed"]:
                    is_available = False
                    status_reason = "Booked"
                elif appt.status == "held":
                    if current_user_id and appt.patient_id == current_user_id:
                        is_available = True
                        is_held_by_me = True
                        status_reason = "Held by you"
                    else:
                        is_available = False
                        status_reason = "Temporarily Held by another patient"

            slots.append(TimeSlot(
                start_time=s_time,
                end_time=e_time,
                is_available=is_available,
                is_held_by_me=is_held_by_me,
                status_reason=status_reason
            ))

            current_time += duration

        return DoctorAvailabilityResponse(
            doctor_id=doctor.id,
            doctor_name=doctor.user.full_name,
            specialisation=doctor.specialisation,
            date=date_str,
            is_working_day=is_working_day,
            is_on_leave=is_on_leave,
            slot_duration_minutes=doctor.slot_duration_minutes,
            slots=slots
        )

    @classmethod
    def hold_slot(
        cls,
        db: Session,
        doctor_id: int,
        appointment_date: str,
        start_time: str,
        patient_id: int
    ) -> Appointment:
        """
        Atomically reserve a slot for 5 minutes to prevent race conditions and double bookings.
        """
        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        # Verify leave
        if appointment_date in doctor.leave_days:
            raise HTTPException(status_code=400, detail="Doctor is on leave on this date.")

        now = datetime.utcnow()
        held_until = now + timedelta(minutes=settings.SLOT_HOLD_TTL_MINUTES)
        end_time = cls._add_minutes_to_time(start_time, doctor.slot_duration_minutes)

        # Check existing booking or active hold
        existing = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.start_time == start_time
        ).with_for_update(nowait=False).first() if not settings.DATABASE_URL.startswith("sqlite") else db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appointment_date,
            Appointment.start_time == start_time
        ).first()

        if existing:
            if existing.status in ["confirmed", "completed"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This slot is already booked.")
            
            if existing.status == "held":
                # Check if hold is active and held by someone else
                if existing.held_until and existing.held_until > now and existing.patient_id != patient_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This slot is currently held by another patient. Please wait or choose another slot."
                    )
                # Take over or refresh hold
                existing.patient_id = patient_id
                existing.status = "held"
                existing.held_until = held_until
                db.commit()
                db.refresh(existing)
                return existing
            
            # If cancelled or conflict status, reuse record
            existing.patient_id = patient_id
            existing.status = "held"
            existing.held_until = held_until
            db.commit()
            db.refresh(existing)
            return existing

        # Create new held appointment
        appt = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status="held",
            held_until=held_until
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)
        return appt

    @classmethod
    async def confirm_booking(
        cls,
        db: Session,
        appointment_id: int,
        symptoms: str,
        patient_id: int
    ) -> Appointment:
        """
        Confirm an appointment from held status, generate AI pre-visit summary, sync calendar, and dispatch emails.
        """
        appt = db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.patient_id == patient_id
        ).first()

        if not appt:
            raise HTTPException(status_code=404, detail="Appointment reservation not found")

        now = datetime.utcnow()
        if appt.status != "held":
            if appt.status == "confirmed":
                return appt
            raise HTTPException(status_code=400, detail=f"Cannot confirm appointment with status: {appt.status}")

        if appt.held_until and appt.held_until < now:
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Slot hold expired. Please select the slot again.")

        # Update appointment details
        appt.symptoms_raw = symptoms
        appt.status = "confirmed"
        appt.held_until = None
        db.commit()
        db.refresh(appt)

        # Generate AI Pre-Visit Summary
        try:
            ai_data = await LLMService.generate_pre_visit_summary(symptoms)
            ai_summary = AISummary(
                appointment_id=appt.id,
                urgency_level=ai_data.get("urgency_level", "Medium"),
                chief_complaint=ai_data.get("chief_complaint", symptoms[:100]),
                is_fallback=ai_data.get("is_fallback", False)
            )
            ai_summary.suggested_questions = ai_data.get("suggested_questions", [])
            db.add(ai_summary)
            db.commit()
        except Exception as exc:
            # Fallback if unhandled
            fallback = LLMService._heuristic_pre_visit_summary(symptoms)
            ai_summary = AISummary(
                appointment_id=appt.id,
                urgency_level=fallback["urgency_level"],
                chief_complaint=fallback["chief_complaint"],
                is_fallback=True
            )
            ai_summary.suggested_questions = fallback["suggested_questions"]
            db.add(ai_summary)
            db.commit()

        # Google Calendar sync
        gcal_event_id = await CalendarService.sync_google_calendar_event(appt, action="create")
        appt.google_calendar_event_id = gcal_event_id
        db.commit()

        # Dispatch confirmation emails
        doctor_user = appt.doctor.user
        patient_user = appt.patient
        gcal_url = CalendarService.generate_google_calendar_url(appt)

        patient_body = (
            f"<h2>Appointment Confirmed!</h2>"
            f"<p>Dear {patient_user.full_name},</p>"
            f"<p>Your consultation with <strong>Dr. {doctor_user.full_name} ({appt.doctor.specialisation})</strong> is confirmed.</p>"
            f"<p><strong>Date:</strong> {appt.appointment_date}<br/>"
            f"<strong>Time:</strong> {appt.start_time} - {appt.end_time}</p>"
            f"<p><a href='{gcal_url}' style='background:#10b981;color:#fff;padding:10px 18px;text-decoration:none;border-radius:6px;display:inline-block;'>Add to Google Calendar</a></p>"
        )
        NotificationService.dispatch_notification(
            db=db,
            recipient=patient_user,
            notification_type="booking_confirmation",
            subject=f"Confirmed: Appointment with Dr. {doctor_user.full_name} on {appt.appointment_date}",
            body=patient_body,
            appointment_id=appt.id
        )

        doctor_body = (
            f"<h2>New Patient Booking</h2>"
            f"<p>Dear Dr. {doctor_user.full_name},</p>"
            f"<p>A new appointment has been booked by <strong>{patient_user.full_name}</strong>.</p>"
            f"<p><strong>Date:</strong> {appt.appointment_date} at {appt.start_time} - {appt.end_time}<br/>"
            f"<strong>Chief Complaint:</strong> {appt.ai_summary.chief_complaint if appt.ai_summary else 'See portal'}<br/>"
            f"<strong>Urgency:</strong> {appt.ai_summary.urgency_level if appt.ai_summary else 'Medium'}</p>"
        )
        NotificationService.dispatch_notification(
            db=db,
            recipient=doctor_user,
            notification_type="booking_confirmation",
            subject=f"New Booking: {patient_user.full_name} ({appt.appointment_date} {appt.start_time})",
            body=doctor_body,
            appointment_id=appt.id
        )

        db.refresh(appt)
        return appt

    @classmethod
    async def cancel_appointment(
        cls,
        db: Session,
        appointment_id: int,
        user: User,
        reason: Optional[str] = None
    ) -> Appointment:
        """Cancel an appointment and notify both parties."""
        appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")

        # Authorization check
        if user.role == "patient" and appt.patient_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment")
        if user.role == "doctor" and appt.doctor.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment")

        old_status = appt.status
        appt.status = "cancelled_by_patient" if user.role == "patient" else "cancelled_by_doctor"
        db.commit()

        # Update Google Calendar
        await CalendarService.sync_google_calendar_event(appt, action="delete")

        # Dispatch cancellation notifications
        doctor_user = appt.doctor.user
        patient_user = appt.patient
        canceller = "Patient" if user.role == "patient" else "Doctor"

        subject = f"Cancelled: Appointment #{appt.id} on {appt.appointment_date}"
        body = (
            f"<p>The appointment scheduled on <strong>{appt.appointment_date} at {appt.start_time}</strong> "
            f"has been cancelled by the {canceller}.</p>"
            f"<p>Reason: {reason or 'No specific reason provided'}</p>"
        )
        NotificationService.dispatch_notification(db, patient_user, "cancellation", subject, body, appt.id)
        NotificationService.dispatch_notification(db, doctor_user, "cancellation", subject, body, appt.id)

        db.refresh(appt)
        return appt
