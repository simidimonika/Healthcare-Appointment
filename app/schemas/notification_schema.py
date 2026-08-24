from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    appointment_id: Optional[int] = None
    notification_type: str
    channel: str
    subject: str
    body: str
    status: str
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationRetryRequest(BaseModel):
    notification_id: int
