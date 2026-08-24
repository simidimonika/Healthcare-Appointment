import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    medication_name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)  # e.g., "Once daily", "Twice daily", "Every 8 hours"
    duration_days = Column(Integer, nullable=False, default=7)
    _reminder_times = Column("reminder_times", Text, default='["09:00","21:00"]')
    
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    status = Column(String(50), nullable=False, default="active")  # 'active', 'completed', 'paused'
    
    last_reminder_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="medications")
    patient = relationship("User", back_populates="medications")

    @property
    def reminder_times(self):
        try:
            return json.loads(self._reminder_times) if self._reminder_times else ["09:00"]
        except Exception:
            return ["09:00"]

    @reminder_times.setter
    def reminder_times(self, value):
        self._reminder_times = json.dumps(value) if isinstance(value, list) else value
