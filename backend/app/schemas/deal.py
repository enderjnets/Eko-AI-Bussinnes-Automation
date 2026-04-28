from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DealBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: float = Field(default=0, ge=0)
    probability: int = Field(default=20, ge=0, le=100)
    status: str = Field(default="prospecting")
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    assigned_to: Optional[str] = None


class DealCreate(DealBase):
    lead_id: int


class DealUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    value: Optional[float] = Field(default=None, ge=0)
    probability: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None
    expected_close_date: Optional[datetime] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None
    assigned_to: Optional[str] = None
    lost_reason: Optional[str] = None


class DealResponse(DealBase):
    id: int
    lead_id: int
    lost_reason: Optional[str]
    actual_close_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DealListResponse(BaseModel):
    total: int
    items: list[DealResponse]


class DealPipelineSummary(BaseModel):
    status: str
    count: int
    total_value: float
    weighted_value: float


class RevenueForecast(BaseModel):
    pipeline: list[DealPipelineSummary]
    total_pipeline_value: float
    total_weighted_value: float
    expected_revenue_this_month: float
    expected_revenue_this_quarter: float
    deals_count: int
    # Closed deals
    closed_won_count: int
    closed_won_value: float
    closed_lost_count: int
    closed_lost_value: float
    total_revenue: float
