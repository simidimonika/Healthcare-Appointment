from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.doctor_profile import DoctorProfile
from app.models.user import User
from app.schemas.doctor_schema import (
    DoctorResponse,
    DoctorAvailabilityResponse,
    DoctorLeaveRequest,
    DoctorUpdateRequest,
)
from app.services.auth_service import get_current_user, require_role
from app.services.booking_service import BookingService
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.get("", response_model=List[DoctorResponse])
def list_doctors(
    specialisation: Optional[str] = Query(None, description="Filter by doctor specialisation"),
    search: Optional[str] = Query(None, description="Search name or bio"),
    db: Session = Depends(get_db)
):
    """Retrieve list of available doctors with optional filtering."""
    query = db.query(DoctorProfile).join(User)
    
    if specialisation and specialisation.strip() and specialisation != "All":
        query = query.filter(DoctorProfile.specialisation.ilike(f"%{specialisation.strip()}%"))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.full_name.ilike(term)) | (DoctorProfile.bio.ilike(term)) | (DoctorProfile.specialisation.ilike(term))
        )

    profiles = query.all()
    results = []
    for doc in profiles:
        results.append(DoctorResponse(
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
        ))
    return results


@router.get("/specialisations", response_model=List[str])
def list_specialisations(db: Session = Depends(get_db)):
    """Retrieve distinct list of specialisations."""
    specialisations = db.query(DoctorProfile.specialisation).distinct().all()
    return sorted([s[0] for s in specialisations if s[0]])


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor_by_id(doctor_id: int, db: Session = Depends(get_db)):
    """Retrieve doctor profile details by ID."""
    doc = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

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


@router.get("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def get_doctor_availability(
    doctor_id: int,
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """Retrieve real-time slot availability for a doctor on a specific date."""
    return BookingService.get_doctor_availability(db=db, doctor_id=doctor_id, date_str=date)


@router.post("/{doctor_id}/leave")
def add_doctor_leave(
    doctor_id: int,
    req: DoctorLeaveRequest,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Mark doctor on leave for specified dates.
    Automatically checks for existing bookings, marks them for reschedule, and notifies affected patients.
    """
    doc = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if current_user.role == "doctor" and doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doctors can only manage their own leaves.")

    return LeaveService.set_doctor_leaves(
        db=db,
        doctor_id=doctor_id,
        leave_dates=req.leave_dates,
        reason=req.reason or "Doctor Leave / Absence"
    )


@router.delete("/{doctor_id}/leave/{date_str}")
def delete_doctor_leave(
    doctor_id: int,
    date_str: str,
    current_user: User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    """Remove a previously registered leave date for a doctor."""
    doc = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if current_user.role == "doctor" and doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doctors can only manage their own leaves.")

    updated_leaves = LeaveService.remove_doctor_leave(db=db, doctor_id=doctor_id, date_to_remove=date_str)
    return {"status": "success", "remaining_leave_days": updated_leaves}
