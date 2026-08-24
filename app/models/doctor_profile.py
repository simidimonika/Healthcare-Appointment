import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    specialisation = Column(String(100), nullable=False, index=True)
    bio = Column(Text, nullable=True)
    working_hours_start = Column(String(10), nullable=False, default="09:00")
    working_hours_end = Column(String(10), nullable=False, default="17:00")
    slot_duration_minutes = Column(Integer, nullable=False, default=30)
    
    # Store working days and leave days as JSON strings
    _working_days = Column("working_days", Text, default='["Monday","Tuesday","Wednesday","Thursday","Friday"]')
    _leave_days = Column("leave_days", Text, default='[]')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")

    @property
    def working_days(self):
        try:
            return json.loads(self._working_days) if self._working_days else []
        except Exception:
            return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    @working_days.setter
    def working_days(self, value):
        self._working_days = json.dumps(value) if isinstance(value, list) else value

    @property
    def leave_days(self):
        try:
            return json.loads(self._leave_days) if self._leave_days else []
        except Exception:
            return []

    @leave_days.setter
    def leave_days(self, value):
        self._leave_days = json.dumps(value) if isinstance(value, list) else value
