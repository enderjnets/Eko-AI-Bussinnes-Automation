from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.models.proposal import Proposal, ProposalStatus
from app.models.deal import Deal
from app.models.lead import Lead
from app.schemas.proposal import (
    ProposalCreate, ProposalUpdate, ProposalResponse, ProposalList,
    ProposalGenerateRequest, ProposalPublicView
)
from app.services.proposal_generator import generate_proposal_html, extract_brand_for_lead
from app.services.brand_extractor import extract_brand_from_website
from app.api.v1.auth import get_current_user
from app.core.security import get_current_user_optional
from app.models.user import User

router = APIRouter()


@router.post("", response_model=ProposalResponse)
async def create_proposal(
    data: ProposalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new proposal."""
    # Verify deal exists
    deal = await db.scalar(select(Deal).where(Deal.id == data.deal_id))
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Get lead for brand info
    lead = await db.scalar(select(Lead).where(Lead.id == deal.lead_id))
    
    # Extract brand if website available and colors not provided
    primary_color = data.brand_primary_color
    secondary_color = data.brand_secondary_color
    logo_url = data.brand_logo_url
    
    if lead and lead.website and (not primary_color or not secondary_color):
        p, s, l = await extract_brand_for_lead(lead.website)
        if not primary_color and p:
            primary_color = p
        if not secondary_color and s:
            secondary_color = s
        if not logo_url and l:
            logo_url = l
    
    proposal = Proposal(
        deal_id=data.deal_id,
        title=data.title,
        content=data.content or "",
        plain_text=data.plain_text or "",
        brand_primary_color=primary_color,
        brand_secondary_color=secondary_color,
        brand_logo_url=logo_url,
        status=ProposalStatus.DRAFT,
        sent_by=current_user.id,
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.get("", response_model=ProposalList)
async def list_proposals(
    status: Optional[ProposalStatus] = Query(None),
    deal_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List proposals with filters."""
    query = select(Proposal).options(selectinload(Proposal.deal)).order_by(desc(Proposal.created_at))
    
    if status:
        query = query.where(Proposal.status == status)
    if deal_id:
        query = query.where(Proposal.deal_id == deal_id)
    if search:
        query = query.where(
            or_(
                Proposal.title.ilike(f"%{search}%"),
                Proposal.plain_text.ilike(f"%{search}%"),
            )
        )
    
    total = await db.scalar(select(Proposal).where(query.whereclause).with_only_columns([Proposal.id])) or 0
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    proposals = result.scalars().all()
    
    return ProposalList(items=list(proposals), total=total)


@router.get("/public/{token}", response_model=ProposalPublicView)
async def get_public_proposal(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a public proposal by its share token."""
    proposal = await db.scalar(
        select(Proposal).options(selectinload(Proposal.deal)).where(Proposal.share_token == token)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status == ProposalStatus.DRAFT and not current_user:
        raise HTTPException(status_code=403, detail="This proposal is not yet public")
    
    # Get lead info
    lead = None
    if proposal.deal:
        lead = await db.scalar(select(Lead).where(Lead.id == proposal.deal.lead_id))
    
    # Update view count if not owner
    if not current_user or (current_user.id != proposal.sent_by):
        proposal.views_count = (proposal.views_count or 0) + 1
        await db.commit()
    
    return ProposalPublicView(
        id=proposal.id,
        title=proposal.title,
        content=proposal.content,
        brand_primary_color=proposal.brand_primary_color,
        brand_secondary_color=proposal.brand_secondary_color,
        brand_logo_url=proposal.brand_logo_url,
        deal_name=proposal.deal.name if proposal.deal else None,
        deal_value=proposal.deal.value if proposal.deal else None,
        business_name=lead.business_name if lead else None,
        status=proposal.status,
        created_at=proposal.created_at,
    )


@router.post("/public/{token}/accept")
async def accept_proposal(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Accept a public proposal."""
    proposal = await db.scalar(
        select(Proposal).options(selectinload(Proposal.deal)).where(Proposal.share_token == token)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status in [ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail=f"Proposal already {proposal.status.value}")
    
    proposal.status = ProposalStatus.ACCEPTED
    proposal.accepted_at = proposal.accepted_at or proposal.updated_at
    
    # Update deal status to negotiation if applicable
    if proposal.deal and proposal.deal.status != "closed_won":
        proposal.deal.status = "negotiation"
    
    await db.commit()
    await db.refresh(proposal)
    return {"status": "accepted", "message": "Proposal accepted successfully"}


@router.post("/public/{token}/reject")
async def reject_proposal(
    token: str,
    feedback: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Reject a public proposal."""
    proposal = await db.scalar(
        select(Proposal).where(Proposal.share_token == token)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status in [ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail=f"Proposal already {proposal.status.value}")
    
    proposal.status = ProposalStatus.REJECTED
    if feedback:
        proposal.notes = f"{proposal.notes or ''}\n\nRejection feedback: {feedback}".strip()
    
    await db.commit()
    await db.refresh(proposal)
    return {"status": "rejected", "message": "Proposal rejected"}


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single proposal."""
    proposal = await db.scalar(
        select(Proposal).options(selectinload(Proposal.deal)).where(Proposal.id == proposal_id)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.patch("/{proposal_id}", response_model=ProposalResponse)
async def update_proposal(
    proposal_id: int,
    data: ProposalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a proposal."""
    proposal = await db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(proposal, field, value)
    
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a proposal."""
    proposal = await db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    await db.delete(proposal)
    await db.commit()
    return {"status": "deleted", "message": "Proposal deleted"}


@router.post("/{proposal_id}/generate")
async def generate_proposal_content(
    proposal_id: int,
    data: ProposalGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate AI proposal content for a proposal."""
    proposal = await db.scalar(
        select(Proposal).options(selectinload(Proposal.deal)).where(Proposal.id == proposal_id)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    deal = proposal.deal
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    lead = await db.scalar(select(Lead).where(Lead.id == deal.lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Extract brand if not already present
    if not proposal.brand_primary_color or not proposal.brand_secondary_color:
        if lead.website:
            p, s, l = await extract_brand_for_lead(lead.website)
            if p and not proposal.brand_primary_color:
                proposal.brand_primary_color = p
            if s and not proposal.brand_secondary_color:
                proposal.brand_secondary_color = s
            if l and not proposal.brand_logo_url:
                proposal.brand_logo_url = l
    
    # Generate proposal HTML
    html_content, plain_text = await generate_proposal_html(
        business_name=lead.business_name,
        category=lead.category,
        description=lead.description,
        pain_points=lead.pain_points or [],
        services=lead.services or [],
        pricing_info=lead.pricing_info,
        about_text=lead.about,
        deal_name=deal.name,
        deal_value=deal.value,
        deal_description=deal.description,
        brand_primary_color=proposal.brand_primary_color,
        brand_secondary_color=proposal.brand_secondary_color,
        brand_logo_url=proposal.brand_logo_url,
    )
    
    proposal.content = html_content
    proposal.plain_text = plain_text
    await db.commit()
    await db.refresh(proposal)
    
    return {"proposal_id": proposal.id, "status": "generated", "content_preview": html_content[:500]}


@router.post("/{proposal_id}/send")
async def send_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a proposal (mark as sent and generate share token)."""
    proposal = await db.scalar(
        select(Proposal).options(selectinload(Proposal.deal)).where(Proposal.id == proposal_id)
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if not proposal.share_token:
        import secrets
        proposal.share_token = secrets.token_urlsafe(32)
    
    proposal.status = ProposalStatus.SENT
    await db.commit()
    await db.refresh(proposal)
    
    # Build public URL
    from app.config import get_settings
    settings = get_settings()
    public_url = f"{settings.FRONTEND_URL or 'http://localhost:3001'}/proposals/public/{proposal.share_token}"
    
    return {
        "status": "sent",
        "share_token": proposal.share_token,
        "public_url": public_url,
        "message": "Proposal sent and public link generated",
    }


@router.post("/{proposal_id}/duplicate", response_model=ProposalResponse)
async def duplicate_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Duplicate an existing proposal."""
    proposal = await db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    new_proposal = Proposal(
        deal_id=proposal.deal_id,
        title=f"{proposal.title} (Copy)",
        content=proposal.content,
        plain_text=proposal.plain_text,
        brand_primary_color=proposal.brand_primary_color,
        brand_secondary_color=proposal.brand_secondary_color,
        brand_logo_url=proposal.brand_logo_url,
        status=ProposalStatus.DRAFT,
        sent_by=current_user.id,
    )
    db.add(new_proposal)
    await db.commit()
    await db.refresh(new_proposal)
    return new_proposal
