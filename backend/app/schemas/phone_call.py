from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PhoneCallCreate(BaseModel):
    lead_id: int
    result: str = Field(..., pattern="^(CONNECTED|NO_ANSWER|VOICEMAIL|WRONG_NUMBER|BUSY)$")
    notes: Optional[str] = None
    interest_level: Optional[str] = Field(None, pattern="^(HIGH|MEDIUM|LOW|NONE)$")
    next_action: Optional[str] = Field(None, pattern="^(EMAIL|CALL_AGAIN|CLOSE)$")
    call_duration_seconds: Optional[int] = Field(None, ge=0)
    scheduled_at: Optional[datetime] = None


class PhoneCallResponse(BaseModel):
    id: int
    lead_id: int
    result: str
    notes: Optional[str] = None
    interest_level: Optional[str] = None
    next_action: Optional[str] = None
    call_duration_seconds: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
