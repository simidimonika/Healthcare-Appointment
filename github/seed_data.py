"""
ClinicPulse AI - Demo Database Seeder
Populates initial sample users, doctor profiles, appointments, AI summaries, and medication schedules.
"""

from datetime import datetime, timedelta
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.models.appointment import Appointment
from app.models.ai_summary import AISummary
from app.models.medication_schedule import MedicationSchedule
from app.models.notification import Notification
from app.services.auth_service import hash_password
from app.services.calendar_service import CalendarService


def seed_database():
    print("[SEEDER] Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).filter(User.email == "admin@clinicpulse.health").first():
            print("[SEEDER] Database already contains seed data. Skipping.")
            return

        print("[SEEDER] Creating administrative and clinical accounts...")

        # 1. Admin User
        admin = User(
            email="admin@clinicpulse.health",
            hashed_password=hash_password("AdminPass123!"),
            full_name="Clinic System Superadmin",
            role="admin",
            phone="+1-555-0100"
        )
        db.add(admin)

        # 2. Patient Users
        patient1 = User(
            email="patient@clinicpulse.health",
            hashed_password=hash_password("PatientPass123!"),
            full_name="Sarah Chen",
            role="patient",
            phone="+1-555-0199"
        )
        patient2 = User(
            email="david.miller@clinicpulse.health",
            hashed_password=hash_password("PatientPass123!"),
            full_name="David Miller",
            role="patient",
            phone="+1-555-0188"
        )
        db.add_all([patient1, patient2])
        db.commit()

        # 3. Doctor Accounts & Profiles
        doctors_data = [
            {
                "email": "doctor@clinicpulse.health",  # Primary demo doctor
                "full_name": "Dr. Marcus Vance",
                "specialisation": "Cardiology",
                "bio": "Board-certified cardiologist specializing in preventive cardiology, hypertension, and arrhythmias with 14 years of clinical practice.",
                "working_hours_start": "09:00",
                "working_hours_end": "17:00",
                "slot_duration_minutes": 30,
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "leave_days": ["2026-08-30"]
            },
            {
                "email": "elena.rostova@clinicpulse.health",
                "full_name": "Dr. Elena Rostova",
                "specialisation": "Dermatology",
                "bio": "Consultant dermatologist with expertise in inflammatory skin conditions, allergy testing, eczema, and dermatosurgery.",
                "working_hours_start": "09:30",
                "working_hours_end": "16:30",
                "slot_duration_minutes": 30,
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "leave_days": []
            },
            {
                "email": "rajiv.patel@clinicpulse.health",
                "full_name": "Dr. Rajiv Patel",
                "specialisation": "Neurology",
                "bio": "Senior neurologist focusing on migraines, neuropathies, sleep disorders, and cognitive health assessments.",
                "working_hours_start": "10:00",
                "working_hours_end": "18:00",
                "slot_duration_minutes": 45,
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday"],
                "leave_days": []
            },
            {
                "email": "sarah.jenkins@clinicpulse.health",
                "full_name": "Dr. Sarah Jenkins",
                "specialisation": "General Medicine",
                "bio": "Primary care physician dedicated to comprehensive holistic health, acute illness management, and lifestyle medicine.",
                "working_hours_start": "08:30",
                "working_hours_end": "16:30",
                "slot_duration_minutes": 30,
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "leave_days": []
            }
        ]

        doc_profiles = []
        for d in doctors_data:
            doc_user = User(
                email=d["email"],
                hashed_password=hash_password("DoctorPass123!"),
                full_name=d["full_name"],
                role="doctor",
                phone="+1-555-0144"
            )
            db.add(doc_user)
            db.commit()

            doc_prof = DoctorProfile(
                user_id=doc_user.id,
                specialisation=d["specialisation"],
                bio=d["bio"],
                working_hours_start=d["working_hours_start"],
                working_hours_end=d["working_hours_end"],
                slot_duration_minutes=d["slot_duration_minutes"]
            )
            doc_prof.working_days = d["working_days"]
            doc_prof.leave_days = d["leave_days"]
            db.add(doc_prof)
            db.commit()
            doc_profiles.append(doc_prof)

        print("[SEEDER] Populating sample appointments, AI triage, and medication regimens...")

        today_str = datetime.now().strftime("%Y-%m-%d")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        past_str = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        # Appointment 1: Active Confirmed Consultation with High Urgency
        appt1 = Appointment(
            patient_id=patient1.id,
            doctor_id=doc_profiles[0].id,  # Dr. Marcus Vance
            appointment_date=tomorrow_str,
            start_time="10:00",
            end_time="10:30",
            status="confirmed",
            symptoms_raw="Experiencing intermittent chest discomfort and shortness of breath when climbing stairs for the past 4 days. Slight dizziness in the mornings.",
            google_calendar_event_id="gcal_seed_101"
        )
        db.add(appt1)
        db.commit()

        ai1 = AISummary(
            appointment_id=appt1.id,
            urgency_level="High",
            chief_complaint="Intermittent chest discomfort and exertional dyspnea",
            is_fallback=False
        )
        ai1.suggested_questions = [
            "Does the chest discomfort radiate to the left arm, jaw, or shoulder blade?",
            "Have you noticed any swelling in your ankles or episodes of sudden sweating?",
            "Are you currently on any beta-blockers, ACE inhibitors, or aspirin?"
        ]
        db.add(ai1)

        # Appointment 2: Completed Consultation with Post-visit AI Care Plan & Medication Reminders
        appt2 = Appointment(
            patient_id=patient1.id,
            doctor_id=doc_profiles[3].id,  # Dr. Sarah Jenkins
            appointment_date=past_str,
            start_time="11:00",
            end_time="11:30",
            status="completed",
            symptoms_raw="Persistent productive cough, low-grade fever (100.2F), and fatigue for 1 week.",
            clinical_notes_raw="Diagnosis: Acute bronchitis with mild bronchospasm. Chest exam shows bilateral scattered wheezing, no crackles. Normal SpO2 at 98%.",
            prescription_raw="Amoxicillin-Clavulanate (625mg) - Twice Daily for 7 days. Take after meals.\nAlbuterol Inhaler (90mcg) - 2 puffs every 6 hours as needed for wheeze."
        )
        db.add(appt2)
        db.commit()

        ai2 = AISummary(
            appointment_id=appt2.id,
            urgency_level="Medium",
            chief_complaint="Productive cough and low-grade fever",
            patient_friendly_summary="You have been diagnosed with acute bronchitis (inflammation of the airways). Your lung oxygen levels are healthy, but your airways are slightly irritated causing wheezing. Rest and hydration will support recovery.",
            medication_schedule="1. Amoxicillin-Clavulanate 625mg: Take 1 tablet twice daily (morning and evening after meals) for a full 7 days.\n2. Albuterol Inhaler: 2 puffs every 6 hours only if you experience wheezing or chest tightness.",
            follow_up_steps="1. Drink at least 2.5L of warm fluids daily.\n2. Use a humidifier at bedtime.\n3. Return for reassessment if fever rises above 101.5F or breathing becomes difficult.",
            is_fallback=False
        )
        ai2.suggested_questions = [
            "What color is the sputum?",
            "Do you have a history of seasonal asthma?",
            "Has the fever persisted throughout the day?"
        ]
        db.add(ai2)

        # Medication Reminders for Patient 1
        med1 = MedicationSchedule(
            appointment_id=appt2.id,
            patient_id=patient1.id,
            medication_name="Amoxicillin-Clavulanate",
            dosage="625mg",
            frequency="Twice Daily",
            duration_days=7,
            start_date=past_str,
            status="active"
        )
        med1.reminder_times = ["09:00", "21:00"]
        db.add(med1)

        # Notifications
        notif1 = Notification(
            recipient_id=patient1.id,
            appointment_id=appt1.id,
            notification_type="booking_confirmation",
            channel="email",
            subject=f"Confirmed: Appointment with Dr. Marcus Vance on {tomorrow_str}",
            body=f"Your cardiology consultation is confirmed for {tomorrow_str} at 10:00 AM.",
            status="sent",
            sent_at=datetime.utcnow()
        )
        notif2 = Notification(
            recipient_id=patient1.id,
            appointment_id=appt2.id,
            notification_type="medication_reminder",
            channel="email",
            subject="Medication Reminder: Amoxicillin-Clavulanate (625mg)",
            body="Reminder to take your morning dose with breakfast.",
            status="sent",
            sent_at=datetime.utcnow()
        )
        db.add_all([notif1, notif2])
        db.commit()

        print("[SEEDER] Database seeding successfully completed!")
        print("=" * 60)
        print("DEMO CREDENTIALS:")
        print("  [Patient] patient@clinicpulse.health     / PatientPass123!")
        print("  [Doctor]  doctor@clinicpulse.health      / DoctorPass123!")
        print("  [Admin]   admin@clinicpulse.health       / AdminPass123!")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"[SEEDER ERROR] {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
