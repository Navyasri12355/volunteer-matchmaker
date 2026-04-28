"""
Authentication request/response schemas.
"""

from pydantic import BaseModel, EmailStr, field_validator

from api.core.passwords import validate_password_strength


class RegisterNGORequest(BaseModel):
    email: EmailStr
    password: str
    org_name: str
    org_registration_number: str
    allowed_categories: list[str]
    custom_subtypes: dict[str, str] = {}

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class RegisterVolunteerRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    age: int = None
    phone: str = None
    city: str = None
    state: str = None
    lat: float = None
    lng: float = None
    willing_to_travel_km: int = 10
    skills: list[str] = []
    preferred_categories: list[str] = []
    strengths: str = None
    past_experience: str = None

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
