from datetime import datetime, timedelta
from app.models.appointment import Appointment
from app.models.notification import Notification


def test_doctor_leave_conflict_and_patient_notification(client, seed_users, db_session):
    doc_id = seed_users["doctor_profile"].id
    patient = seed_users["patient"]
    patient_token = seed_users["tokens"]["patient"]
    doctor_token = seed_users["tokens"]["doctor"]

    leave_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")

    # 1. Patient books a slot on leave_date
    hold_resp = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doc_id, "appointment_date": leave_date, "start_time": "11:00"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    appt_id = hold_resp.json()["appointment_id"]

    confirm_resp = client.post(
        "/api/appointments/confirm",
        json={"appointment_id": appt_id, "symptoms": "High blood pressure monitoring"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"

    # 2. Doctor sets leave for leave_date
    leave_resp = client.post(
        f"/api/doctors/{doc_id}/leave",
        json={"leave_dates": [leave_date], "reason": "Attending Cardiology Conference"},
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert leave_resp.status_code == 200
    leave_data = leave_resp.json()
    assert leave_data["conflicts_count"] == 1
    assert leave_data["affected_appointments"][0]["appointment_id"] == appt_id

    # 3. Check appointment status transitioned to reschedule_required_leave
    appt_record = db_session.query(Appointment).filter(Appointment.id == appt_id).first()
    assert appt_record.status == "reschedule_required_leave"

    # 4. Check notification was dispatched to patient
    notif = db_session.query(Notification).filter(
        Notification.recipient_id == patient.id,
        Notification.notification_type == "doctor_leave_conflict",
        Notification.appointment_id == appt_id
    ).first()
    assert notif is not None
    assert "Doctor on Leave" in notif.subject

    # 5. Patient reschedules to day after leave
    new_date = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
    resched_resp = client.post(
        f"/api/appointments/{appt_id}/reschedule",
        json={"new_date": new_date, "new_start_time": "11:00"},
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert resched_resp.status_code == 200
    assert resched_resp.json()["status"] == "confirmed"
    assert resched_resp.json()["appointment_date"] == new_date
