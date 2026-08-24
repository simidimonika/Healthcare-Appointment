# ClinicPulse AI - Healthcare Appointment & Follow-up Manager

> An enterprise-grade, high-concurrency Healthcare Appointment and Follow-up Management Platform built in **Python (FastAPI)** with an eye-catching **Dark Theme SPA**, LLM-powered symptom triage & clinical summaries, double-booking prevention, automated doctor leave conflict handling, and Google Calendar synchronization.

---

## 🌟 Key Features

### 👤 1. Patient Portal
- **Doctor Directory & Filtering**: Search certified specialists by name and specialty chips (Cardiology, Dermatology, Neurology, General Medicine, etc.).
- **Interactive Time-Slot Picker**: Real-time slot availability with visual hold indicators.
- **5-Minute Slot Hold**: Prevents double-booking and cart collisions while filling symptom intake forms.
- **AI Pre-Visit Triage**: Analyzes patient symptoms to determine urgency level (**Low / Medium / High**), extracts chief complaint, and provides suggested clinical questions for the doctor.
- **1-Click Google Calendar & .ICS Sync**: Direct calendar integration upon booking confirmation.
- **Post-Visit Care & Medication Reminders**: View doctor's clinical findings, AI patient-friendly summary, and track active medication reminder schedules.

### 🩺 2. Doctor Portal
- **Consultation Queue**: View daily appointments prioritized by AI urgency badges.
- **Pre-Visit Clinical Intelligence**: Review patient chief complaint and AI-suggested questions before starting the visit.
- **Prescription & Consultation Builder**: Enter clinical notes and structured prescription items (dosage, frequency, duration).
- **AI Post-Visit Summary**: Converts clinical notes into plain English instructions, medication regimens, and lifestyle follow-ups.
- **Doctor Leave Management**: Register leaves with automated conflict detection, patient notification dispatch, and 1-click reschedule links.

### 👑 3. Admin Operations & System Health
- **Clinic Intelligence Dashboard**: Real-time stats on appointments, active doctors, registered patients, and urgency distribution.
- **Doctor Profile Management**: Create new physicians, configure working hours (09:00 - 17:00), slot durations, and practice days.
- **Notification Retry Queue**: Monitor email dispatch statuses (`pending`, `sent`, `retrying`, `failed`) and trigger manual retries.
- **Background Worker Simulator**: Manually trigger slot hold purges, medication reminders, and retry queues on demand.

---

## 🏗️ Architecture & Database Schema

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │1     1│  DoctorProfile  │1     *│   Appointment   │
│-----------------│◄──────│-----------------│◄──────│-----------------│
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ email (UQ)      │       │ user_id (FK)    │       │ patient_id (FK) │
│ hashed_password │       │ specialisation  │       │ doctor_id (FK)  │
│ full_name       │       │ working_hours   │       │ appointment_date│
│ role            │       │ slot_duration   │       │ start/end_time  │
│ phone           │       │ working_days    │       │ status          │
└────────┬────────┘       │ leave_days      │       │ held_until      │
         │                └─────────────────┘       │ symptoms_raw    │
         │1                                         │ clinical_notes  │
         │                                          │ prescription_raw│
         │*                                         └────────┬────────┘
┌────────┴────────┐                                          │1
│  Notification   │                                          │
│-----------------│                                          │1
│ id (PK)         │                                 ┌────────┴────────┐
│ recipient_id(FK)│                                 │    AISummary    │
│ notif_type      │                                 │-----------------│
│ channel         │                                 │ id (PK)         │
│ status          │                                 │ appointment_id  │
│ retry_count     │                                 │ urgency_level   │
│ body            │                                 │ chief_complaint │
└─────────────────┘                                 │ suggested_quest │
                                                    │ patient_summary │
                                                    │ med_schedule    │
                                                    │ is_fallback     │
                                                    └─────────────────┘
```

---

## 🤖 LLM Prompts & Graceful Fallback Handling

The platform integrates **Google Gemini** (`gemini-1.5-flash`) and **OpenAI** (`gpt-4o-mini`) with built-in heuristic fallback:

### 1. Pre-Visit Symptom Analysis Prompt
```text
Analyse these symptoms and return: urgency level (Low / Medium / High), chief complaint, and three suggested questions for the doctor. Symptoms: <symptoms>
```
- **Output JSON Schema**:
  ```json
  {
    "urgency_level": "Low | Medium | High",
    "chief_complaint": "string",
    "suggested_questions": ["Question 1", "Question 2", "Question 3"]
  }
  ```

### 2. Post-Visit Patient Summary Prompt
```text
Convert these clinical notes into a patient-friendly summary with medication schedule and follow-up steps: <notes>
```
- **Output JSON Schema**:
  ```json
  {
    "patient_friendly_summary": "Plain-English clinical breakdown",
    "medication_schedule": "Clear dosage and frequency guide",
    "follow_up_steps": "Precautions and next appointment guidance"
  }
  ```

### 🛡️ Graceful LLM Failure Strategy
If API keys are missing, network connectivity drops, or rate limits are reached, the system automatically engages a **rule-based clinical heuristic engine**, setting `is_fallback = true` while keeping all booking and consultation workflows completely uninterrupted.

---

## 📅 Google Calendar & Multi-Channel Notifications

### 1. 1-Click Direct Calendar URL
Constructs a RFC-compliant URL opening directly in Google Calendar:
```
https://calendar.google.com/calendar/render?action=TEMPLATE&text=...&dates=...&details=...
```

### 2. RFC 5545 iCalendar (`.ics`) Export
Universally downloadable endpoint at `/api/calendar/appointment/{id}/ics` compatible with Google Calendar, Apple Calendar, and Outlook.

### 3. Google Calendar API (OAuth 2.0)
To enable server-to-server sync:
1. Create a project in Google Cloud Console.
2. Enable the **Google Calendar API**.
3. Create an OAuth 2.0 Web Client ID and set redirect URI: `http://localhost:8000/api/calendar/oauth2callback`.
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ installed
- Git

### 1. Clone & Setup Environment
```bash
git clone <repository_url>
cd healthcare_platform

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Optionally add your `GEMINI_API_KEY` or `OPENAI_API_KEY` for live AI generation. The application runs out of the box with heuristic fallbacks if no keys are supplied).*

### 3. Seed Database & Run Server
```bash
# Start server (seeds initial demo data automatically on first launch)
python run.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🔑 Demo Personas & Credentials

You can use the **Top Instant Persona Switcher Bar** in the UI or log in with:

| Role | Email | Password | Details |
|---|---|---|---|
| 👤 **Patient** | `patient@clinicpulse.health` | `PatientPass123!` | Sarah Chen (Book, symptoms, calendar) |
| 🩺 **Doctor** | `doctor@clinicpulse.health` | `DoctorPass123!` | Dr. Marcus Vance (Cardiologist) |
| 👑 **Admin** | `admin@clinicpulse.health` | `AdminPass123!` | System Superadmin (Metrics, queue) |

---

## 🧪 Running Automated Tests

Run the full pytest test suite:
```bash
pytest tests/ -v
```

---

## 📖 API Documentation

Interactive OpenAPI / Swagger documentation is available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/auth/register` | POST | Public | Register new patient, doctor, or admin |
| `/api/auth/login` | POST | Public | Authenticate user & get JWT token |
| `/api/auth/demo-switch/{role}` | POST | Public | Instant 1-click demo persona switcher |
| `/api/doctors` | GET | Public | List doctors with specialization filters |
| `/api/doctors/{id}/availability` | GET | Public | Real-time slot availability & hold status |
| `/api/doctors/{id}/leave` | POST | Doctor / Admin | Add doctor leave & trigger conflict notifications |
| `/api/appointments/hold` | POST | Patient | Place 5-minute atomic slot hold |
| `/api/appointments/confirm` | POST | Patient | Confirm booking with symptom intake |
| `/api/appointments/{id}/complete`| POST | Doctor | Submit clinical notes & generate post-visit AI care plan |
| `/api/admin/dashboard` | GET | Admin | System health metrics & analytics |
| `/api/admin/notifications` | GET | Admin | Audit notification queue & retry logs |
| `/api/calendar/appointment/{id}/ics` | GET | Public | Download RFC 5545 `.ics` calendar file |

---

## 🐳 Docker & Cloud Deployment

### Docker Deployment
```bash
docker build -t clinicpulse-healthcare .
docker run -p 8000:8000 clinicpulse-healthcare
```

### Cloud Hosting (Render / Railway / Vercel)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python run.py` or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment**: Set `PORT=8000`, `DATABASE_URL=sqlite:///./healthcare.db` (or PostgreSQL URI).
