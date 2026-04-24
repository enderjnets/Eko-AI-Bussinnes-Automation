from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.sequence import SequenceStatus, SequenceStepType


class SequenceStepBase(BaseModel):
    position: int = Field(0, ge=0)
    step_type: SequenceStepType = SequenceStepType.EMAIL
    name: str = Field(..., min_length=1, max_length=255)
    template_key: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    ai_generate: bool = True
    delay_hours: Optional[int] = Field(24, ge=0)
    condition: Optional[dict] = None


class SequenceStepCreate(SequenceStepBase):
    pass


class SequenceStepResponse(SequenceStepBase):
    id: int
    sequence_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSequenceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    entry_criteria: Optional[dict] = None
    exit_criteria: Optional[dict] = None


class EmailSequenceCreate(EmailSequenceBase):
    steps: Optional[List[SequenceStepCreate]] = []


class EmailSequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[SequenceStatus] = None
    entry_criteria: Optional[dict] = None
    exit_criteria: Optional[dict] = None


class EmailSequenceResponse(EmailSequenceBase):
    id: int
    status: SequenceStatus
    leads_entered: int
    leads_completed: int
    leads_converted: int
    steps: List[SequenceStepResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SequenceEnrollmentBase(BaseModel):
    sequence_id: int
    lead_id: int


class SequenceEnrollmentCreate(SequenceEnrollmentBase):
    pass


class SequenceEnrollmentResponse(SequenceEnrollmentBase):
    id: int
    status: str
    current_step_position: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    next_step_at: Optional[datetime] = None
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class SequenceExecuteRequest(BaseModel):
    lead_ids: List[int] = Field(..., min_length=1)
    dry_run: bool = False
