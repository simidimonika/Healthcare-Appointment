from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.doctor_profile import DoctorProfile
from app.schemas.auth_schema import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account (patient, doctor, or admin)."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )

    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        phone=req.phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    doctor_profile_id = None
    if req.role == "doctor":
        doc_prof = DoctorProfile(
            user_id=user.id,
            specialisation=req.specialisation or "General Medicine",
            bio=req.bio or "Dedicated healthcare practitioner."
        )
        db.add(doc_prof)
        db.commit()
        db.refresh(doc_prof)
        doctor_profile_id = doc_prof.id

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "email": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        doctor_profile_id=doctor_profile_id
    )


@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Log in with email and password to receive JWT token."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    doctor_id = user.doctor_profile.id if user.doctor_profile else None
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "email": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        doctor_profile_id=doctor_id
    )


@router.post("/token", response_model=TokenResponse)
def login_oauth2(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 compatible token endpoint."""
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    doctor_id = user.doctor_profile.id if user.doctor_profile else None
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "email": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        doctor_profile_id=doctor_id
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Retrieve profile details of current authenticated user."""
    doc_id = current_user.doctor_profile.id if current_user.doctor_profile else None
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        phone=current_user.phone,
        created_at=current_user.created_at,
        doctor_profile_id=doc_id
    )


@router.post("/demo-switch/{role}", response_model=TokenResponse)
def demo_switch_role(role: str, db: Session = Depends(get_db)):
    """Convenient 1-click switcher for demoing Patient, Doctor, or Admin personas."""
    if role not in ["patient", "doctor", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid demo role")

    user = db.query(User).filter(User.role == role).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"No demo user with role '{role}' found. Run seed_data.py")

    doc_id = user.doctor_profile.id if user.doctor_profile else None
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "email": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        doctor_profile_id=doc_id
    )
