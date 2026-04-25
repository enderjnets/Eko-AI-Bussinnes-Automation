from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BookingStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Cal.com IDs
    cal_com_booking_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    cal_com_event_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    cal_com_uid: Mapped[Optional[str]] = mapped_column(String(100))

    # Lead relation
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)

    # Meeting details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Denver")

    # Attendee info (from lead)
    attendee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_phone: Mapped[Optional[str]] = mapped_column(String(50))

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(500))  # video link, address, etc
    location_type: Mapped[Optional[str]] = mapped_column(String(50))  # video, phone, in_person

    # Status & tracking
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.PENDING)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", lazy="selectin")
