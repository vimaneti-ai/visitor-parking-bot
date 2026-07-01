"""
Pydantic schemas for API request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegistrationCreate(BaseModel):
    website_url: str = Field(..., description="URL of the visitor parking registration site")
    apartment_name: str = Field(..., min_length=1)
    apartment_number: str = Field(..., min_length=1, max_length=30)
    email: EmailStr

    plate_number: str = Field(..., min_length=1, max_length=20)
    confirm_plate_number: str = Field(..., min_length=1, max_length=20)
    plate_state: str = Field(..., min_length=2, max_length=2)
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int = Field(..., ge=1980, le=2100)
    vehicle_color: str

    days: int = Field(..., ge=1, le=14)

    @field_validator("plate_state")
    @classmethod
    def uppercase_state(cls, v: str) -> str:
        return v.upper()

    @field_validator("plate_number", "confirm_plate_number")
    @classmethod
    def uppercase_plate(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_plate_confirmation(self) -> "RegistrationCreate":
        if self.plate_number != self.confirm_plate_number:
            raise ValueError("plate_number and confirm_plate_number must match")
        return self


class RegistrationAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempted_at: datetime
    status: str
    message: Optional[str] = None
    screenshot_path: Optional[str] = None
    confirmation_text: Optional[str] = None


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    website_url: str
    apartment_name: str
    apartment_number: str
    email: EmailStr
    plate_number: str
    confirm_plate_number: str
    plate_state: str
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str
    days: int
    status: str
    registration_count: int
    first_registered_at: Optional[datetime] = None
    last_registered_at: Optional[datetime] = None
    next_registration_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RegistrationDetailOut(RegistrationOut):
    attempts: list[RegistrationAttemptOut] = []
