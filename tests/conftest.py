import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.services.auth_service import hash_password, create_access_token

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_users(db_session):
    # Admin
    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("AdminPass123!"),
        full_name="Admin User",
        role="admin"
    )
    # Patient
    patient = User(
        email="patient@test.com",
        hashed_password=hash_password("PatientPass123!"),
        full_name="Test Patient",
        role="patient"
    )
    # Doctor
    doctor_user = User(
        email="doctor@test.com",
        hashed_password=hash_password("DoctorPass123!"),
        full_name="Dr. Test Specialist",
        role="doctor"
    )
    db_session.add_all([admin, patient, doctor_user])
    db_session.commit()

    doc_profile = DoctorProfile(
        user_id=doctor_user.id,
        specialisation="Cardiology",
        bio="Cardiology specialist.",
        working_hours_start="09:00",
        working_hours_end="17:00",
        slot_duration_minutes=30
    )
    db_session.add(doc_profile)
    db_session.commit()

    admin_token = create_access_token({"sub": str(admin.id), "role": "admin", "email": admin.email})
    patient_token = create_access_token({"sub": str(patient.id), "role": "patient", "email": patient.email})
    doctor_token = create_access_token({"sub": str(doctor_user.id), "role": "doctor", "email": doctor_user.email})

    return {
        "admin": admin,
        "patient": patient,
        "doctor": doctor_user,
        "doctor_profile": doc_profile,
        "tokens": {
            "admin": admin_token,
            "patient": patient_token,
            "doctor": doctor_token
        }
    }
