# Healthcare Platform - System Design & Engineering Architecture

## 1. System Overview
ClinicPulse AI is an asynchronous, high-concurrency healthcare platform built with Python (FastAPI), SQLAlchemy ORM, and an embedded responsive Dark-Theme SPA. The architecture guarantees ACID transaction safety, graceful LLM degradation, reliable multi-channel notifications, and conflict-free calendar synchronization across Patient, Doctor, and Administrative domains.

---

## 2. Double-Booking Prevention & Concurrency Control
Double-booking is prevented through a multi-tier concurrency strategy combining application-level slot leasing and database-level isolation:

1. **Database Isolation & Locking**: 
   - Under SQLite, Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `PRAGMA synchronous=NORMAL` ensure atomic serialized transactions without table locks stalling read operations.
   - Under PostgreSQL, slot holds execute row-level locking via `SELECT ... FOR UPDATE`, ensuring that concurrent read-modify-write operations on the same doctor time-slot are serialized.
2. **Compound Indexing & Uniqueness Guard**:
   - A composite index `idx_doc_date_time` over `(doctor_id, appointment_date, start_time)` accelerates availability computation and enables transactional row locking.
3. **Atomic State Transition**:
   - An appointment transition from available to held/confirmed verifies the condition:
     $$\text{status} \in \{\text{'cancelled'}\} \lor (\text{status} = \text{'held'} \land \text{held\_until} < \text{now})$$
   - If two patients simultaneously request the same slot, the first transaction commits the reservation while the second receives an immediate `409 Conflict` HTTP response, prompting them to select another slot.

---

## 3. Slot Hold Mechanism (TTL Reservation)
To eliminate cart abandonment race conditions and prevent partial booking collisions while a patient fills symptom details, a temporary slot-hold mechanism is implemented:

- **Time-to-Live (TTL)**: When a patient selects an available slot, a record with `status = "held"` and `held_until = now() + 5 minutes` is created.
- **Visual Countdown & Heartbeat**: The client UI displays an active 5-minute countdown timer. Other patients querying doctor availability see the slot marked as `"Temporarily Held"`, disabling duplicate selection.
- **Automated Expired Hold Purge**: An in-process background worker (`APScheduler`) executes every 30 seconds to clean up expired holds where `held_until <= now()`, restoring slot availability without manual intervention.

---

## 4. Doctor Leave Conflict Handling
When a physician or administrator registers scheduled leave, the system executes an automated conflict resolution pipeline:

```
[Doctor Submits Leave Dates] 
           │
           ▼
[Query Active Bookings on Leave Dates]
           │
           ├──► [Atomic Status Update: 'reschedule_required_leave']
           ├──► [Dispatch High-Priority Notification to Patient (Email/In-App)]
           └──► [Generate Direct 1-Click Patient Reschedule Link]
```

1. **Conflict Detection**: The system queries all appointments for the doctor on the requested dates matching `status IN ('confirmed', 'held')`.
2. **Status Transition**: Conflicting appointments are atomically transitioned to `status = 'reschedule_required_leave'`.
3. **Automated Patient Outreach**: High-priority notifications are dispatched to all affected patients detailing the physician's absence and offering a 1-click expedited rescheduling interface.
4. **Audit Metric Tracking**: The Administrative dashboard tracks `conflict_reschedules_needed` in real time until resolved.

---

## 5. Notification Reliability & Failure Handling
Medical notifications (booking confirmations, schedule updates, doctor leaves, and medication reminders) are critical and cannot be lost due to transient network or provider outages:

- **Persistent Queue Storage**: Every notification is persisted in the `notifications` table with status (`pending`, `sent`, `failed`, `retrying`), channel, and attempt counter.
- **Exponential Backoff & Retries**: When an SMTP/SendGrid or Calendar API dispatch fails, the worker increments `retry_count` and updates status to `retrying`. A background job retries failed items up to 3 times with exponential backoff ($2^{\text{attempt}} \times 60\text{s}$).
- **Dead-Letter State & Manual Override**: Notifications exceeding 3 failed attempts are marked as `failed`, logging the exact error trace. Administrators can inspect failed dispatches and trigger manual re-delivery from the Notification Queue console.

---

## 6. LLM Integration & Graceful Failure
Pre-visit symptom triage and post-visit clinical summaries integrate with Google Gemini / OpenAI with built-in heuristic fallback:
- If API keys are absent, rate-limits occur, or external endpoints timeout (>10s), the system intercepts the exception and executes a deterministic clinical rule engine, setting `is_fallback = true`.
- Core user flows never block or throw `500 Internal Server Errors` on LLM outages.
