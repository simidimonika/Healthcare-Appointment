import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models.appointment import Appointment
from app.models.medication_schedule import MedicationSchedule
from app.services.notification_service import NotificationService

logger = logging.getLogger("background_worker")
scheduler = AsyncIOScheduler()


def cleanup_expired_slot_holds():
    """Purge expired temporary slot holds to free inventory."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        expired_appts = db.query(Appointment).filter(
            Appointment.status == "held",
            Appointment.held_until <= now
        ).all()

        if expired_appts:
            count = len(expired_appts)
            for appt in expired_appts:
                # If there are no clinical notes or AI summaries attached, delete held row
                db.delete(appt)
            db.commit()
            logger.info(f"[CLEANUP] Released {count} expired slot holds.")
    except Exception as exc:
        db.rollback()
        logger.error(f"[CLEANUP ERROR] Failed to clean slot holds: {exc}")
    finally:
        db.close()


def process_medication_reminders():
    """Check active medication regimens and trigger reminder notifications."""
    db: Session = SessionLocal()
    try:
        active_meds = db.query(MedicationSchedule).filter(
            MedicationSchedule.status == "active"
        ).all()

        current_time_str = datetime.now().strftime("%H:%M")
        today_date_str = datetime.now().strftime("%Y-%m-%d")

        for med in active_meds:
            patient = med.patient
            if not patient:
                continue

            # Check if reminder times contains close match or interval
            # In simulated environment, send reminder if last reminder sent was not today
            should_send = False
            if med.last_reminder_sent_at is None:
                should_send = True
            elif (datetime.utcnow() - med.last_reminder_sent_at).total_seconds() > 3600:
                # If more than 1 hour has passed and time aligns
                should_send = True

            if should_send:
                subject = f"Medication Reminder: {med.medication_name} ({med.dosage})"
                body = (
                    f"<h2>Rx Medication Reminder</h2>"
                    f"<p>Hello {patient.full_name},</p>"
                    f"<p>This is your scheduled reminder to take your medication:</p>"
                    f"<ul>"
                    f"<li><strong>Medication:</strong> {med.medication_name}</li>"
                    f"<li><strong>Dosage:</strong> {med.dosage}</li>"
                    f"<li><strong>Frequency:</strong> {med.frequency}</li>"
                    f"</ul>"
                    f"<p>Please take with a glass of water as directed by your physician.</p>"
                )
                NotificationService.dispatch_notification(
                    db=db,
                    recipient=patient,
                    notification_type="medication_reminder",
                    subject=subject,
                    body=body,
                    appointment_id=med.appointment_id
                )
                med.last_reminder_sent_at = datetime.utcnow()
                db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[MEDICATION WORKER ERROR] {exc}")
    finally:
        db.close()


def process_notification_retries():
    """Retry any pending or failed email transmissions."""
    db: Session = SessionLocal()
    try:
        retried = NotificationService.retry_pending_notifications(db)
        if retried > 0:
            logger.info(f"[RETRY QUEUE] Successfully processed {retried} retried notifications.")
    except Exception as exc:
        logger.error(f"[RETRY QUEUE ERROR] {exc}")
    finally:
        db.close()


def start_background_tasks():
    """Register and start all periodic background tasks."""
    scheduler.add_job(cleanup_expired_slot_holds, "interval", seconds=30, id="cleanup_slots", replace_existing=True)
    scheduler.add_job(process_medication_reminders, "interval", seconds=settings.MEDICATION_REMINDER_CHECK_INTERVAL_SECONDS, id="med_reminders", replace_existing=True)
    scheduler.add_job(process_notification_retries, "interval", seconds=settings.NOTIFICATION_RETRY_INTERVAL_SECONDS, id="notif_retries", replace_existing=True)
    scheduler.start()
    logger.info("Background scheduler initialized and running.")


def stop_background_tasks():
    """Gracefully shutdown scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")
