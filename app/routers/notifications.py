from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification_schema import NotificationResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/my", response_model=List[NotificationResponse])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List recent notifications for the logged in user."""
    notifs = db.query(Notification).filter(
        Notification.recipient_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(30).all()
    return notifs
