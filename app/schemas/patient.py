from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PatientBase(BaseModel):
    full_name: str
    phone_number: str
    age: Optional[int] = None
    gender: Optional[str] = None
    language: str = "English"
    disease: str
    doctor_name: Optional[str] = None
    expected_refill_date: Optional[date] = None
    is_active: bool = True


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True