from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
import secrets

from sqlalchemy import Integer, String, Float, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProposalStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Relations
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), nullable=False, index=True)
    # Public token for proposal page (no auth needed)
    share_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    
    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    plain_text: Mapped[Optional[str]] = mapped_column(Text)
    
    # Brand colors used in the proposal
    brand_primary_color: Mapped[Optional[str]] = mapped_column(String(20))
    brand_secondary_color: Mapped[Optional[str]] = mapped_column(String(20))
    brand_logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Status tracking
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus), default=ProposalStatus.DRAFT, index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Rejection feedback
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Sent by
    sent_by: Mapped[Optional[int]] = mapped_column(Integer)
    
    # View tracking
    views_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
