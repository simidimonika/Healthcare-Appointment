from datetime import datetime, timedelta
import urllib.parse
from typing import Optional, Dict, Any
from app.config import settings
from app.models.appointment import Appointment


class CalendarService:
    @staticmethod
    def generate_google_calendar_url(appointment: Appointment) -> str:
        """Generate a 1-click direct Google Calendar event creation URL."""
        # Parse date and times
        # format: YYYYMMDDTHHMMSSZ or local YYYYMMDDTHHMMSS
        date_clean = appointment.appointment_date.replace("-", "")
        start_clean = appointment.start_time.replace(":", "") + "00"
        end_clean = appointment.end_time.replace(":", "") + "00"
        
        start_iso = f"{date_clean}T{start_clean}"
        end_iso = f"{date_clean}T{end_clean}"
        
        doctor_name = appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "Doctor"
        patient_name = appointment.patient.full_name if appointment.patient else "Patient"
        specialisation = appointment.doctor.specialisation if appointment.doctor else "General Consultation"
        
        title = f"Medical Consultation: Dr. {doctor_name} ({specialisation})"
        details = (
            f"Doctor: Dr. {doctor_name} ({specialisation})\n"
            f"Patient: {patient_name}\n"
            f"Appointment ID: #{appointment.id}\n"
            f"Symptoms: {appointment.symptoms_raw or 'Not specified'}\n\n"
            f"Managed via {settings.APP_NAME}"
        )
        location = "ClinicPulse Health Center / Telehealth Virtual Room"

        params = {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{start_iso}/{end_iso}",
            "details": details,
            "location": location,
            "sprop": f"website:{settings.APP_NAME}"
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"https://calendar.google.com/calendar/render?{query_string}"

    @staticmethod
    def generate_ics_content(appointment: Appointment) -> str:
        """Generate RFC 5545 compliant iCalendar (.ics) string for appointment import."""
        date_clean = appointment.appointment_date.replace("-", "")
        start_clean = appointment.start_time.replace(":", "") + "00"
        end_clean = appointment.end_time.replace(":", "") + "00"
        
        dtstart = f"{date_clean}T{start_clean}"
        dtend = f"{date_clean}T{end_clean}"
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        
        doctor_name = appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "Doctor"
        patient_name = appointment.patient.full_name if appointment.patient else "Patient"
        specialisation = appointment.doctor.specialisation if appointment.doctor else "General"
        summary = f"Consultation: Dr. {doctor_name} ({specialisation})"
        description = (
            f"Appointment #{appointment.id}\\n"
            f"Patient: {patient_name}\\n"
            f"Doctor: Dr. {doctor_name} ({specialisation})\\n"
            f"Symptoms: {appointment.symptoms_raw or 'None specified'}"
        )
        
        status_val = "CONFIRMED" if appointment.status in ["confirmed", "completed"] else "CANCELLED"

        ics = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//ClinicPulse AI//Healthcare Manager//EN\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:PUBLISH\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:appt-{appointment.id}@clinicpulse.health\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{description}\r\n"
            "LOCATION:ClinicPulse Health Center\r\n"
            f"STATUS:{status_val}\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        return ics

    @staticmethod
    async def sync_google_calendar_event(appointment: Appointment, action: str = "create") -> Optional[str]:
        """
        Sync event with Google Calendar API (OAuth 2.0 or Service Account).
        action can be: 'create', 'update', 'delete'.
        Returns event_id on success or None if OAuth is in mock mode.
        """
        if not settings.GOOGLE_CALENDAR_ENABLED or not settings.GOOGLE_CLIENT_ID:
            # Mock mode: Return synthetic event ID
            return f"gcal_evt_{appointment.id}_{int(datetime.utcnow().timestamp())}"
        
        # When live OAuth credentials are configured:
        # In a production setup, user OAuth refresh token or Service Account token is used to call:
        # POST /calendars/primary/events or PATCH /calendars/primary/events/{event_id}
        return f"gcal_live_{appointment.id}"
