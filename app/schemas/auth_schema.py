from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    role: str = Field(default="patient", pattern="^(patient|doctor|admin)$")
    phone: Optional[str] = None
    
    # Optional doctor specific initial fields if role is doctor
    specialisation: Optional[str] = None
    bio: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str
    role: str
    doctor_profile_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    created_at: datetime
    doctor_profile_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
