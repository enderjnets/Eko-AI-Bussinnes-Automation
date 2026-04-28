from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PhoneCall(Base):
    """Log of phone calls made to leads."""
    __tablename__ = "phone_calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)

    # Call result
    result: Mapped[str] = mapped_column(String(50))  # CONNECTED, NO_ANSWER, VOICEMAIL, WRONG_NUMBER, BUSY

    # Call details
    notes: Mapped[Optional[str]] = mapped_column(Text)
    interest_level: Mapped[Optional[str]] = mapped_column(String(50))  # HIGH, MEDIUM, LOW, NONE
    next_action: Mapped[Optional[str]] = mapped_column(String(50))  # EMAIL, CALL_AGAIN, CLOSE
    call_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
