from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id"), nullable=False, index=True)
    
    appointment_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    start_time = Column(String(5), nullable=False)                      # HH:MM
    end_time = Column(String(5), nullable=False)                        # HH:MM
    
    # Status: 'held', 'confirmed', 'completed', 'cancelled_by_patient', 'cancelled_by_doctor', 'rescheduled', 'reschedule_required_leave'
    status = Column(String(50), nullable=False, default="held", index=True)
    held_until = Column(DateTime, nullable=True)  # Expiration for temporary slot lock
    
    # Clinical Data
    symptoms_raw = Column(Text, nullable=True)
    clinical_notes_raw = Column(Text, nullable=True)
    prescription_raw = Column(Text, nullable=True)
    
    # Google Calendar
    google_calendar_event_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("User", back_populates="patient_appointments", foreign_keys=[patient_id])
    doctor = relationship("DoctorProfile", back_populates="appointments")
    ai_summary = relationship("AISummary", back_populates="appointment", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="appointment", cascade="all, delete-orphan")
    medications = relationship("MedicationSchedule", back_populates="appointment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_date_time", "doctor_id", "appointment_date", "start_time"),
    )
