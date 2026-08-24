import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AISummary(Base):
    __tablename__ = "ai_summaries"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True, nullable=False)
    
    # Pre-visit summary fields
    urgency_level = Column(String(20), nullable=True)  # 'Low', 'Medium', 'High'
    chief_complaint = Column(Text, nullable=True)
    _suggested_questions = Column("suggested_questions", Text, default='[]')
    
    # Post-visit summary fields
    patient_friendly_summary = Column(Text, nullable=True)
    medication_schedule = Column(Text, nullable=True)
    follow_up_steps = Column(Text, nullable=True)
    
    # Metadata & Resilience
    raw_llm_response = Column(Text, nullable=True)
    is_fallback = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointment = relationship("Appointment", back_populates="ai_summary")

    @property
    def suggested_questions(self):
        try:
            return json.loads(self._suggested_questions) if self._suggested_questions else []
        except Exception:
            return []

    @suggested_questions.setter
    def suggested_questions(self, value):
        self._suggested_questions = json.dumps(value) if isinstance(value, list) else value
