from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


@router.get("/appointment/{appointment_id}/ics")
def download_ics_file(appointment_id: int, db: Session = Depends(get_db)):
    """Download RFC 5545 iCalendar (.ics) file for universal calendar import."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    ics_content = CalendarService.generate_ics_content(appt)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="appointment-{appt.id}.ics"'}
    )


@router.get("/appointment/{appointment_id}/google-url")
def get_google_calendar_url(appointment_id: int, db: Session = Depends(get_db)):
    """Get 1-click Google Calendar web link."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    url = CalendarService.generate_google_calendar_url(appt)
    return {"google_calendar_url": url}
