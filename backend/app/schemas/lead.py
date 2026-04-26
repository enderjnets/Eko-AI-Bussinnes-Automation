from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

from app.models.lead import LeadStatus, LeadSource


class LeadBase(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LeadCreate(LeadBase):
    source: LeadSource = LeadSource.MANUAL
    source_data: Optional[dict] = None
    tags: Optional[list] = None
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    business_name: Optional[str] = None
    category: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: Optional[LeadStatus] = None
    urgency_score: Optional[float] = Field(None, ge=0, le=100)
    fit_score: Optional[float] = Field(None, ge=0, le=100)
    do_not_contact: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[list] = None
    assigned_to: Optional[str] = None


class LeadEnrichment(BaseModel):
    tech_stack: Optional[list] = None
    social_profiles: Optional[dict] = None
    review_summary: Optional[str] = None
    trigger_events: Optional[list] = None
    pain_points: Optional[list] = None
    urgency_score: Optional[float] = Field(None, ge=0, le=100)
    fit_score: Optional[float] = Field(None, ge=0, le=100)
    scoring_reason: Optional[str] = None
    # Extended enrichment fields
    email: Optional[str] = None
    website_real: Optional[str] = None
    services: Optional[list] = None
    pricing_info: Optional[str] = None
    business_hours: Optional[str] = None
    about_text: Optional[str] = None
    team_names: Optional[list] = None
    proposal_suggestion: Optional[str] = None


class LeadResponse(LeadBase):
    id: int
    source: LeadSource
    status: LeadStatus
    source_data: Optional[dict]
    tech_stack: Optional[list]
    social_profiles: Optional[dict]
    review_summary: Optional[str]
    trigger_events: Optional[list]
    pain_points: Optional[list]
    urgency_score: Optional[float]
    fit_score: Optional[float]
    total_score: Optional[float]
    scoring_reason: Optional[str]
    # Extended enrichment fields
    website_real: Optional[str] = None
    services: Optional[list] = None
    pricing_info: Optional[str] = None
    business_hours: Optional[str] = None
    about_text: Optional[str] = None
    team_names: Optional[list] = None
    proposal_suggestion: Optional[str] = None
    email_opened_count: int
    email_clicked_count: int
    call_count: int
    last_contact_at: Optional[datetime]
    next_follow_up_at: Optional[datetime]
    do_not_contact: bool
    assigned_to: Optional[str]
    tags: Optional[list]
    notes: Optional[str]
    distance_km: Optional[float] = None  # Computed when lat/lng reference provided
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    total: int
    items: List[LeadResponse]
    page: int
    page_size: int


class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="Business category or search term")
    city: str = Field(..., description="City to search in")
    state: Optional[str] = "CO"
    radius_miles: Optional[int] = Field(25, ge=1, le=100)
    max_results: Optional[int] = Field(50, ge=1, le=500)
    sources: Optional[List[str]] = Field(["google_maps"], description="Sources to search: google_maps, yelp, linkedin, colorado_sos")
    campaign_id: Optional[int] = None


class LeadSearchRequest(BaseModel):
    query: str = Field(..., description="Semantic search query")
    limit: Optional[int] = Field(20, ge=1, le=100)
    status: Optional[LeadStatus] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
