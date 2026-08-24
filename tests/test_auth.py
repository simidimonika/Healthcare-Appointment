def test_register_and_login_patient(client):
    # Register
    reg_resp = client.post("/api/auth/register", json={
        "email": "newpatient@test.com",
        "password": "Password123!",
        "full_name": "Alice Wonderland",
        "role": "patient",
        "phone": "+1-555-9999"
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["email"] == "newpatient@test.com"

    # Login
    login_resp = client.post("/api/auth/login", json={
        "email": "newpatient@test.com",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert login_data["role"] == "patient"


def test_reject_duplicate_email(client, seed_users):
    resp = client.post("/api/auth/register", json={
        "email": "patient@test.com",  # Already exists in fixture
        "password": "NewPassword123!",
        "full_name": "Duplicate User",
        "role": "patient"
    })
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


def test_get_current_user_profile(client, seed_users):
    token = seed_users["tokens"]["patient"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "patient@test.com"
    assert data["role"] == "patient"
