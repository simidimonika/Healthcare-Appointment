import logging
from typing import List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.doctor_profile import DoctorProfile
from app.models.appointment import Appointment
from app.services.notification_service import NotificationService
from app.services.calendar_service import CalendarService

logger = logging.getLogger("leave_service")


class LeaveService:
    @classmethod
    def set_doctor_leaves(
        cls,
        db: Session,
        doctor_id: int,
        leave_dates: List[str],
        reason: str = "Medical Leave / Personal Absence"
    ) -> Dict[str, Any]:
        """
        Mark doctor on leave for specified dates, identify existing bookings,
        update status to reschedule_required_leave, and dispatch automatic notifications.
        """
        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        # Merge new leave dates
        current_leaves = set(doctor.leave_days)
        new_leaves = current_leaves.union(set(leave_dates))
        doctor.leave_days = sorted(list(new_leaves))
        db.commit()

        # Detect conflicting appointments for each added leave date
        affected_appointments: List[Dict[str, Any]] = []
        conflicts = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date.in_(leave_dates),
            Appointment.status.in_(["confirmed", "held"])
        ).all()

        for appt in conflicts:
            # Transition status
            old_status = appt.status
            appt.status = "reschedule_required_leave"
            db.commit()

            # Notify patient immediately
            patient = appt.patient
            doctor_user = doctor.user
            
            subject = f"ACTION REQUIRED: Doctor on Leave - Reschedule Appointment #{appt.id}"
            body = (
                f"<h2>Doctor Schedule Update</h2>"
                f"<p>Dear {patient.full_name},</p>"
                f"<p>We regret to inform you that <strong>Dr. {doctor_user.full_name} ({doctor.specialisation})</strong> "
                f"will be on leave on <strong>{appt.appointment_date}</strong> ({reason}).</p>"
                f"<p>Your appointment originally booked for <strong>{appt.start_time} - {appt.end_time}</strong> has been flagged for rescheduling.</p>"
                f"<p>Please log in to your patient portal to choose an alternate time slot or another physician without any additional charge.</p>"
            )

            NotificationService.dispatch_notification(
                db=db,
                recipient=patient,
                notification_type="doctor_leave_conflict",
                subject=subject,
                body=body,
                appointment_id=appt.id
            )

            affected_appointments.append({
                "appointment_id": appt.id,
                "patient_name": patient.full_name,
                "patient_email": patient.email,
                "appointment_date": appt.appointment_date,
                "slot_time": f"{appt.start_time} - {appt.end_time}",
                "previous_status": old_status
            })

        logger.info(f"Doctor #{doctor_id} leaves updated. {len(affected_appointments)} conflicts resolved.")
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.user.full_name,
            "leave_dates": doctor.leave_days,
            "conflicts_count": len(affected_appointments),
            "affected_appointments": affected_appointments
        }

    @classmethod
    def remove_doctor_leave(cls, db: Session, doctor_id: int, date_to_remove: str) -> List[str]:
        """Remove a leave date for a doctor."""
        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        current_leaves = doctor.leave_days
        if date_to_remove in current_leaves:
            current_leaves.remove(date_to_remove)
            doctor.leave_days = current_leaves
            db.commit()

        return doctor.leave_days
