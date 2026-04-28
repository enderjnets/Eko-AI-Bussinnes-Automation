from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProposalBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    plain_text: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_logo_url: Optional[str] = None


class ProposalCreate(BaseModel):
    deal_id: int
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_logo_url: Optional[str] = None


class ProposalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = None
    plain_text: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_logo_url: Optional[str] = None


class ProposalResponse(BaseModel):
    id: int
    deal_id: int
    title: str
    content: Optional[str] = None
    plain_text: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_logo_url: Optional[str] = None
    status: str
    share_token: Optional[str] = None
    views_count: Optional[int] = None
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    notes: Optional[str] = None
    sent_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProposalList(BaseModel):
    total: int
    items: list[ProposalResponse]


class ProposalGenerateRequest(BaseModel):
    pass


class ProposalPublicView(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    brand_logo_url: Optional[str] = None
    deal_name: Optional[str] = None
    deal_value: Optional[float] = None
    business_name: Optional[str] = None
    status: str
    created_at: datetime
