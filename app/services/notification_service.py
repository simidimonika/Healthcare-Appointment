import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List
from sqlalchemy.orm import Session
from app.config import settings
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger("notification_service")


class NotificationService:
    @staticmethod
    def _send_smtp_email(to_email: str, subject: str, html_body: str) -> bool:
        """Send live email via SMTP / SendGrid."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email

            part = MIMEText(html_body, "html")
            msg.attach(part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
            return True
        except Exception as exc:
            logger.error(f"SMTP email dispatch to {to_email} failed: {exc}")
            raise exc

    @classmethod
    def dispatch_notification(
        cls,
        db: Session,
        recipient: User,
        notification_type: str,
        subject: str,
        body: str,
        appointment_id: Optional[int] = None,
        channel: str = "email"
    ) -> Notification:
        """Create and attempt dispatch of a notification with automatic failure tracking."""
        notif = Notification(
            recipient_id=recipient.id,
            appointment_id=appointment_id,
            notification_type=notification_type,
            channel=channel,
            subject=subject,
            body=body,
            status="pending",
            retry_count=0,
            max_retries=settings.MAX_NOTIFICATION_RETRIES,
            created_at=datetime.utcnow()
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Attempt immediate dispatch
        cls.send_notification_item(db, notif)
        return notif

    @classmethod
    def send_notification_item(cls, db: Session, notif: Notification) -> bool:
        """Attempt to transmit a specific notification."""
        try:
            recipient = notif.recipient
            if not recipient:
                notif.status = "failed"
                notif.error_message = "Recipient user not found"
                db.commit()
                return False

            if settings.EMAIL_BACKEND == "smtp":
                cls._send_smtp_email(recipient.email, notif.subject, notif.body)
            elif settings.EMAIL_BACKEND == "console":
                print(f"\n[EMAIL DISPATCH] To: {recipient.email} | Subject: {notif.subject}\nBody: {notif.body}\n")
            else:
                # Mock backend: Record successful simulation in logs & DB
                logger.info(f"[MOCK EMAIL] To: {recipient.email} | Subject: {notif.subject}")

            notif.status = "sent"
            notif.sent_at = datetime.utcnow()
            notif.error_message = None
            db.commit()
            return True

        except Exception as exc:
            notif.retry_count += 1
            notif.error_message = str(exc)
            if notif.retry_count >= notif.max_retries:
                notif.status = "failed"
            else:
                notif.status = "retrying"
            db.commit()
            return False

    @classmethod
    def retry_pending_notifications(cls, db: Session) -> int:
        """Background retry handler for failed/retrying notifications."""
        failed_notifs = db.query(Notification).filter(
            Notification.status.in_(["pending", "retrying"]),
            Notification.retry_count < Notification.max_retries
        ).all()

        success_count = 0
        for notif in failed_notifs:
            if cls.send_notification_item(db, notif):
                success_count += 1
        return success_count
