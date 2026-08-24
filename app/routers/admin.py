from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.appointment import Appointment
from app.models.doctor_profile import DoctorProfile
from app.models.user import User
from app.models.ai_summary import AISummary
from app.models.notification import Notification
from app.schemas.doctor_schema import DoctorCreateRequest, DoctorResponse, DoctorUpdateRequest
from app.schemas.notification_schema import NotificationResponse
from app.services.auth_service import require_role, hash_password
from app.services.background_worker import cleanup_expired_slot_holds, process_medication_reminders, process_notification_retries
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"], dependencies=[Depends(require_role(["admin"]))])


@router.get("/dashboard")
def get_admin_dashboard_metrics(db: Session = Depends(get_db)):
    """Retrieve comprehensive clinic metrics and system health."""
    total_patients = db.query(User).filter(User.role == "patient").count()
    total_doctors = db.query(DoctorProfile).count()
    total_appointments = db.query(Appointment).count()
    
    status_counts = db.query(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status).all()
    status_map = {s[0]: s[1] for s in status_counts}

    urgency_counts = db.query(AISummary.urgency_level, func.count(AISummary.id)).group_by(AISummary.urgency_level).all()
    urgency_map = {u[0]: u[1] for u in urgency_counts if u[0]}

    notifications_pending = db.query(Notification).filter(Notification.status.in_(["pending", "retrying"])).count()
    notifications_failed = db.query(Notification).filter(Notification.status == "failed").count()
    notifications_sent = db.query(Notification).filter(Notification.status == "sent").count()

    conflict_reschedules_needed = db.query(Appointment).filter(Appointment.status == "reschedule_required_leave").count()

    return {
        "total_patients": total_patients,
        "total_doctors": total_doctors,
        "total_appointments": total_appointments,
        "appointment_status_breakdown": status_map,
        "ai_urgency_breakdown": urgency_map,
        "notifications": {
            "sent": notifications_sent,
            "pending_or_retrying": notifications_pending,
            "failed": notifications_failed
        },
        "conflict_reschedules_needed": conflict_reschedules_needed
    }


@router.post("/doctors", response_model=DoctorResponse)
def create_doctor_profile(req: DoctorCreateRequest, db: Session = Depends(get_db)):
    """Admin creates a new Doctor user and associated clinical profile."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role="doctor",
        phone=req.phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    doc_profile = DoctorProfile(
        user_id=user.id,
        specialisation=req.specialisation,
        bio=req.bio,
        working_hours_start=req.working_hours_start,
        working_hours_end=req.working_hours_end,
        slot_duration_minutes=req.slot_duration_minutes
    )
    doc_profile.working_days = req.working_days
    db.add(doc_profile)
    db.commit()
    db.refresh(doc_profile)

    return DoctorResponse(
        id=doc_profile.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        specialisation=doc_profile.specialisation,
        bio=doc_profile.bio,
        working_hours_start=doc_profile.working_hours_start,
        working_hours_end=doc_profile.working_hours_end,
        slot_duration_minutes=doc_profile.slot_duration_minutes,
        working_days=doc_profile.working_days,
        leave_days=doc_profile.leave_days
    )


@router.put("/doctors/{doctor_id}", response_model=DoctorResponse)
def update_doctor_profile(doctor_id: int, req: DoctorUpdateRequest, db: Session = Depends(get_db)):
    """Admin updates doctor working hours, slot duration, or specialisation."""
    doc = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if req.specialisation:
        doc.specialisation = req.specialisation
    if req.bio is not None:
        doc.bio = req.bio
    if req.working_hours_start:
        doc.working_hours_start = req.working_hours_start
    if req.working_hours_end:
        doc.working_hours_end = req.working_hours_end
    if req.slot_duration_minutes:
        doc.slot_duration_minutes = req.slot_duration_minutes
    if req.working_days is not None:
        doc.working_days = req.working_days

    db.commit()
    db.refresh(doc)

    return DoctorResponse(
        id=doc.id,
        user_id=doc.user_id,
        full_name=doc.user.full_name,
        email=doc.user.email,
        phone=doc.user.phone,
        specialisation=doc.specialisation,
        bio=doc.bio,
        working_hours_start=doc.working_hours_start,
        working_hours_end=doc.working_hours_end,
        slot_duration_minutes=doc.slot_duration_minutes,
        working_days=doc.working_days,
        leave_days=doc.leave_days
    )


@router.get("/notifications", response_model=List[NotificationResponse])
def list_system_notifications(
    status_filter: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """View system notification audit log and retry queue."""
    query = db.query(Notification)
    if status_filter:
        query = query.filter(Notification.status == status_filter)
    notifs = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return notifs


@router.post("/notifications/{notification_id}/retry")
def retry_single_notification(notification_id: int, db: Session = Depends(get_db)):
    """Manually force retry of a failed notification."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.status = "pending"
    notif.retry_count = 0
    db.commit()

    success = NotificationService.send_notification_item(db, notif)
    return {"status": "success" if success else "failed", "notification_id": notif.id, "current_status": notif.status}


@router.post("/trigger-background/{task_name}")
def trigger_background_worker_task(task_name: str):
    """Manually trigger background scheduled tasks for testing/demonstration."""
    if task_name == "cleanup-holds":
        cleanup_expired_slot_holds()
        return {"status": "success", "message": "Slot hold cleanup job executed."}
    elif task_name == "medication-reminders":
        process_medication_reminders()
        return {"status": "success", "message": "Medication reminder job executed."}
    elif task_name == "retry-notifications":
        process_notification_retries()
        return {"status": "success", "message": "Notification retry queue executed."}
    else:
        raise HTTPException(status_code=400, detail="Unknown task name")
