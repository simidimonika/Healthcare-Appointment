from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="patient")  # 'patient', 'doctor', 'admin'
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patient_appointments = relationship("Appointment", back_populates="patient", foreign_keys="Appointment.patient_id")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")
    medications = relationship("MedicationSchedule", back_populates="patient", cascade="all, delete-orphan")
