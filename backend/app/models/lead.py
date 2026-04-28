from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, JSON, Enum, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class LeadStatus(str, PyEnum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    SCORED = "scored"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    MEETING_BOOKED = "meeting_booked"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    CHURNED = "churned"


class LeadSource(str, PyEnum):
    GOOGLE_MAPS = "google_maps"
    LINKEDIN = "linkedin"
    YELP = "yelp"
    COLORADO_SOS = "colorado_sos"
    MANUAL = "manual"
    REFERRAL = "referral"


class Lead(Base):
    __tablename__ = "leads"

    # Composite index for efficient Kanban column filtering (status + id)
    __table_args__ = (
        Index("ix_leads_status_id", "status", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Basic info
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Contact
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Location
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[Optional[str]] = mapped_column(String(50), default="US")
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    
    # Source & status
    source: Mapped[LeadSource] = mapped_column(Enum(LeadSource), default=LeadSource.MANUAL)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), default=LeadStatus.DISCOVERED, index=True
    )
    source_data: Mapped[Optional[dict]] = mapped_column(JSON)  # Raw data from scraper
    
    # Enrichment data
    tech_stack: Mapped[Optional[list]] = mapped_column(JSON)
    social_profiles: Mapped[Optional[dict]] = mapped_column(JSON)
    review_summary: Mapped[Optional[str]] = mapped_column(Text)
    trigger_events: Mapped[Optional[list]] = mapped_column(JSON)
    pain_points: Mapped[Optional[list]] = mapped_column(JSON)
    
    # Scoring
    urgency_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0)  # 0-100
    fit_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0)  # 0-100
    total_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0)  # composite
    scoring_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    # Extended enrichment (AI-powered research)
    website_real: Mapped[Optional[str]] = mapped_column(String(500))
    services: Mapped[Optional[list]] = mapped_column(JSON)
    pricing_info: Mapped[Optional[str]] = mapped_column(Text)
    business_hours: Mapped[Optional[str]] = mapped_column(Text)
    about_text: Mapped[Optional[str]] = mapped_column(Text)
    team_names: Mapped[Optional[list]] = mapped_column(JSON)
    proposal_suggestion: Mapped[Optional[str]] = mapped_column(Text)
    
    # Brand extraction (from website)
    brand_primary_color: Mapped[Optional[str]] = mapped_column(String(20))
    brand_secondary_color: Mapped[Optional[str]] = mapped_column(String(20))
    brand_logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Engagement tracking
    email_opened_count: Mapped[int] = mapped_column(Integer, default=0)
    email_clicked_count: Mapped[int] = mapped_column(Integer, default=0)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Cold calling
    next_call_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    call_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_call_result: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Compliance
    consent_status: Mapped[Optional[str]] = mapped_column(String(50), default="pending")
    consent_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Vector embedding for semantic search (384 dims for local sentence-transformers)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(384))
    
    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)

    # Metadata
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100))
    tags: Mapped[Optional[list]] = mapped_column(JSON)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction", back_populates="lead", lazy="selectin"
    )
    campaigns: Mapped[List["Campaign"]] = relationship(
        "Campaign", secondary="campaign_leads", back_populates="leads"
    )
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="leads")


class Interaction(Base):
    __tablename__ = "interactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    
    interaction_type: Mapped[str] = mapped_column(String(50))  # email, call, sms, meeting, note
    direction: Mapped[str] = mapped_column(String(20), default="outbound")  # inbound/outbound
    
    # Content
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    content: Mapped[Optional[str]] = mapped_column(Text)
    
    # For emails
    email_status: Mapped[Optional[str]] = mapped_column(String(50))  # sent, delivered, opened, clicked, bounced
    email_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # For calls
    call_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    call_transcript: Mapped[Optional[str]] = mapped_column(Text)
    call_recording_url: Mapped[Optional[str]] = mapped_column(String(500))
    call_sentiment: Mapped[Optional[str]] = mapped_column(String(50))
    
    # AI-generated metadata
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)
    ai_next_action: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    meta: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="interactions")
