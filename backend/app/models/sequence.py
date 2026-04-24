from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, Enum, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SequenceStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class SequenceStepType(str, PyEnum):
    EMAIL = "email"
    WAIT = "wait"
    CONDITION = "condition"
    SMS = "sms"
    CALL = "call"


class EmailSequence(Base):
    """A reusable email sequence (drip campaign) with ordered steps."""
    __tablename__ = "email_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[SequenceStatus] = mapped_column(Enum(SequenceStatus), default=SequenceStatus.DRAFT)

    # Sequence configuration
    entry_criteria: Mapped[Optional[dict]] = mapped_column(JSON)  # e.g. {"status": "scored", "min_score": 50}
    exit_criteria: Mapped[Optional[dict]] = mapped_column(JSON)  # e.g. {"on_reply": True, "on_meeting_booked": True}

    # Stats
    leads_entered: Mapped[int] = mapped_column(Integer, default=0)
    leads_completed: Mapped[int] = mapped_column(Integer, default=0)
    leads_converted: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    steps: Mapped[List["SequenceStep"]] = relationship(
        "SequenceStep", back_populates="sequence", lazy="selectin", order_by="SequenceStep.position"
    )
    enrollments: Mapped[List["SequenceEnrollment"]] = relationship(
        "SequenceEnrollment", back_populates="sequence", lazy="selectin"
    )


class SequenceStep(Base):
    """A single step in an email sequence."""
    __tablename__ = "sequence_steps"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sequence_id: Mapped[int] = mapped_column(ForeignKey("email_sequences.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # Order in sequence

    step_type: Mapped[SequenceStepType] = mapped_column(Enum(SequenceStepType), default=SequenceStepType.EMAIL)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # For email steps
    template_key: Mapped[Optional[str]] = mapped_column(String(100))  # e.g. "initial_outreach", "follow_up"
    subject_template: Mapped[Optional[str]] = mapped_column(String(500))
    body_template: Mapped[Optional[str]] = mapped_column(Text)
    ai_generate: Mapped[bool] = mapped_column(Boolean, default=True)

    # For wait steps
    delay_hours: Mapped[Optional[int]] = mapped_column(Integer, default=24)

    # For condition steps
    condition: Mapped[Optional[dict]] = mapped_column(JSON)  # e.g. {"field": "email_opened", "operator": ">", "value": 0}

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    sequence: Mapped["EmailSequence"] = relationship("EmailSequence", back_populates="steps")


class SequenceEnrollment(Base):
    """Tracks a lead's progress through a sequence."""
    __tablename__ = "sequence_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sequence_id: Mapped[int] = mapped_column(ForeignKey("email_sequences.id"), index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)

    status: Mapped[str] = mapped_column(String(50), default="active")  # active, completed, exited, paused
    current_step_position: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_step_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    sequence: Mapped["EmailSequence"] = relationship("EmailSequence", back_populates="enrollments")
