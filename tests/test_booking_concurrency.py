from datetime import datetime, timedelta
import pytest
from app.models.appointment import Appointment


def test_slot_hold_and_double_booking_prevention(client, seed_users, db_session):
    doc_id = seed_users["doctor_profile"].id
    patient_token = seed_users["tokens"]["patient"]
    date_str = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    # 1. Patient 1 holds slot at 10:00
    hold_resp = client.post(
        "/api/appointments/hold",
        json={
            "doctor_id": doc_id,
            "appointment_date": date_str,
            "start_time": "10:00"
        },
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert hold_resp.status_code == 200
    hold_data = hold_resp.json()
    assert hold_data["status"] == "held"
    appt_id = hold_data["appointment_id"]

    # 2. Register Patient 2
    reg_p2 = client.post("/api/auth/register", json={
        "email": "patient2@test.com",
        "password": "Password123!",
        "full_name": "Second Patient",
        "role": "patient"
    })
    p2_token = reg_p2.json()["access_token"]

    # 3. Patient 2 attempts to hold the EXACT SAME slot -> Must be rejected with 409 Conflict
    conflict_resp = client.post(
        "/api/appointments/hold",
        json={
            "doctor_id": doc_id,
            "appointment_date": date_str,
            "start_time": "10:00"
        },
        headers={"Authorization": f"Bearer {p2_token}"}
    )
    assert conflict_resp.status_code == 409
    assert "held by another patient" in conflict_resp.json()["detail"].lower() or "already" in conflict_resp.json()["detail"].lower()

    # 4. Patient 1 confirms booking with symptoms
    confirm_resp = client.post(
        "/api/appointments/confirm",
        json={
            "appointment_id": appt_id,
            "symptoms": "Mild shortness of breath and heart palpitations for 2 days"
        },
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["status"] == "confirmed"
    assert confirm_data["ai_summary"] is not None
    assert confirm_data["ai_summary"]["urgency_level"] in ["Low", "Medium", "High"]

    # 5. After confirmation, Patient 2 attempts to book again -> Must remain rejected
    conflict_resp2 = client.post(
        "/api/appointments/hold",
        json={
            "doctor_id": doc_id,
            "appointment_date": date_str,
            "start_time": "10:00"
        },
        headers={"Authorization": f"Bearer {p2_token}"}
    )
    assert conflict_resp2.status_code == 409


def test_appointment_reschedule_and_cancellation(client, seed_users):
    doc_id = seed_users["doctor_profile"].id
    patient_token = seed_users["tokens"]["patient"]
    date_str = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    # Hold & Confirm
    hold_resp = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doc_id, "appointment_date": date_str, "start_time": "14:00"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    appt_id = hold_resp.json()["appointment_id"]

    confirm_resp = client.post(
        "/api/appointments/confirm",
        json={"appointment_id": appt_id, "symptoms": "Routine annual cardiac checkup"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert confirm_resp.status_code == 200

    # Reschedule to 15:00
    resched_resp = client.post(
        f"/api/appointments/{appt_id}/reschedule",
        json={"new_date": date_str, "new_start_time": "15:00"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert resched_resp.status_code == 200
    assert resched_resp.json()["start_time"] == "15:00"

    # Cancel
    cancel_resp = client.post(
        f"/api/appointments/{appt_id}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled_by_patient"
