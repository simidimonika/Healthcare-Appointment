from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    
    # Types: booking_confirmation, appointment_reminder, cancellation, doctor_leave_conflict, medication_reminder, reschedule_notice
    notification_type = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False, default="email")  # email, calendar, in_app
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    
    # Status: pending, sent, failed, retrying
    status = Column(String(20), nullable=False, default="pending", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    recipient = relationship("User", back_populates="notifications")
    appointment = relationship("Appointment", back_populates="notifications")
