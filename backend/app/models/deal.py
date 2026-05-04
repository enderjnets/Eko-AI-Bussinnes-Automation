from typing import Optional
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DealStatus(str, PyEnum):
    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Financials
    value: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    probability: Mapped[int] = mapped_column(Integer, default=20)  # 0-100
    
    # Pipeline
    status: Mapped[str] = mapped_column(String(50), default=DealStatus.PROSPECTING.value)
    
    # Dates
    expected_close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Description & notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Source
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "email_campaign", "referral", "inbound"
    
    # Assignment
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Metadata
    lost_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
