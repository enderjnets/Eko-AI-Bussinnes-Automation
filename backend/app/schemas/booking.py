from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

from app.models.booking import BookingStatus


class BookingBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    timezone: str = "America/Denver"
    attendee_email: EmailStr
    attendee_name: str = Field(..., min_length=1, max_length=255)
    attendee_phone: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = None
    notes: Optional[str] = None


class BookingCreate(BaseModel):
    lead_id: int
    event_type_id: Optional[int] = None
    start_time: datetime
    title: Optional[str] = None
    notes: Optional[str] = None
    location_type: Optional[str] = "video"


class BookingUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    start_time: Optional[datetime] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None


class BookingResponse(BookingBase):
    id: int
    cal_com_booking_id: Optional[int] = None
    cal_com_event_type_id: Optional[int] = None
    cal_com_uid: Optional[str] = None
    lead_id: int
    status: BookingStatus
    cancellation_reason: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilityRequest(BaseModel):
    event_type_id: int
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class BookingLinkRequest(BaseModel):
    lead_id: int
    event_type_id: Optional[int] = None
    message: Optional[str] = None
