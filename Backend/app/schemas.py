# app/schemas.py
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class UserCreate(BaseModel):
    """Anonymous signup: the user chooses a unique ID (can be anything,
    e.g. 'anonymous123'); internally everything is keyed on the numeric
    user.id, so the chosen ID is only a login handle."""
    participant_id: str
    password: str
    first_name: Optional[str] = None

    @field_validator("participant_id")
    @classmethod
    def normalize_participant_id(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("participant_id must be at least 3 characters")
        if len(v) > 32:
            raise ValueError("participant_id must be at most 32 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_not_too_short(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 4:
            raise ValueError("password must be at least 4 characters")
        return v


class UserLogin(BaseModel):
    participant_id: str
    password: str

    @field_validator("participant_id")
    @classmethod
    def normalize_participant_id(cls, v: str) -> str:
        return v.strip()


class UserResponse(BaseModel):
    id: int
    participant_code: str
    full_name_fa: Optional[str] = None
    created_at: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    degree: Optional[str] = None
    examGoal: Optional[str] = None
    studyHoursPerWeek: Optional[int] = None

    class Config:
        orm_mode = True