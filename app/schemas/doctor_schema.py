from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class DoctorCreateRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    full_name: str
    phone: Optional[str] = None
    specialisation: str
    bio: Optional[str] = None
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    slot_duration_minutes: int = 30
    working_days: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


class DoctorUpdateRequest(BaseModel):
    specialisation: Optional[str] = None
    bio: Optional[str] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    slot_duration_minutes: Optional[int] = None
    working_days: Optional[List[str]] = None


class DoctorLeaveRequest(BaseModel):
    leave_dates: List[str] = Field(..., description="List of ISO date strings YYYY-MM-DD")
    reason: Optional[str] = None


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    specialisation: str
    bio: Optional[str] = None
    working_hours_start: str
    working_hours_end: str
    slot_duration_minutes: int
    working_days: List[str]
    leave_days: List[str]

    model_config = ConfigDict(from_attributes=True)


class TimeSlot(BaseModel):
    start_time: str
    end_time: str
    is_available: bool
    is_held_by_me: bool = False
    status_reason: Optional[str] = None


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    specialisation: str
    date: str
    is_working_day: bool
    is_on_leave: bool
    slot_duration_minutes: int
    slots: List[TimeSlot]
