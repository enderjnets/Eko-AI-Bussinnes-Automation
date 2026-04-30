from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.campaign import Campaign, CampaignStatus, CampaignLead
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.user import User
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse, CampaignLaunchRequest
from app.agents.outreach.channels.email import EmailOutreach, EMAIL_TEMPLATES
from app.services.paperclip import on_campaign_launched
from app.core.security import get_current_user

router = APIRouter()

# Campaign launch rate limit: max emails per batch to protect domain reputation
MAX_CAMPAIGN_EMAILS_PER_BATCH = 50


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    status: Optional[CampaignStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Campaign)
    if status:
        query = query.where(Campaign.status == status)
    
    query = query.order_by(Campaign.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = Campaign(**data.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/launch", response_model=CampaignResponse)
async def launch_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Launch a campaign: send personalized emails to all eligible leads.
    Only sends to leads in SCORED status with email and do_not_contact=False.
    Respects MAX_CAMPAIGN_EMAILS_PER_BATCH to protect sender reputation.
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status == CampaignStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Campaign already active")
    
    # Fetch eligible leads for this campaign
    leads_result = await db.execute(
        select(Lead)
        .join(CampaignLead, Lead.id == CampaignLead.lead_id)
        .where(
            and_(
                CampaignLead.campaign_id == campaign_id,
                Lead.status == LeadStatus.SCORED,
                Lead.email.isnot(None),
                Lead.do_not_contact == False,
            )
        )
    )
    leads = leads_result.scalars().all()
    
    if not leads:
        raise HTTPException(
            status_code=400,
            detail="No eligible leads found for this campaign. Need leads in SCORED status with email."
        )
    
    # Rate limit: cap batch size
    leads_to_contact = leads[:MAX_CAMPAIGN_EMAILS_PER_BATCH]
    
    email_outreach = EmailOutreach()
    sent_count = 0
    failed_count = 0
    
    for lead in leads_to_contact:
        try:
            # Determine template key: campaign may store template_key in meta or default to initial_outreach
            template_key = "initial_outreach"
            if campaign.meta and isinstance(campaign.meta, dict):
                template_key = campaign.meta.get("template_key", "initial_outreach")
            if template_key not in EMAIL_TEMPLATES:
                template_key = "initial_outreach"
            
            campaign_context = campaign.description or ""
            
            response = await email_outreach.generate_and_send(
                lead=lead,
                template_key=template_key,
                campaign_context=campaign_context,
                campaign_id=campaign.id,
            )
            
            # Record interaction
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="outbound",
                subject=response.get("subject", ""),
                content=response.get("body", ""),
                email_status="sent",
                email_message_id=response.get("id"),
                meta={
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "template": template_key,
                    "ai_generated": True,
                },
            )
            db.add(interaction)
            
            # Update lead status
            lead.status = LeadStatus.CONTACTED
            lead.last_contact_at = datetime.utcnow()
            
            sent_count += 1
            
        except Exception as e:
            failed_count += 1
            # Log error but continue with other leads
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send campaign email to lead {lead.id}: {e}")
            
            # Record failed interaction
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="outbound",
                content=f"Campaign email FAILED: {str(e)}",
                email_status="bounced",
                meta={
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "error": str(e),
                },
            )
            db.add(interaction)
    
    # Update campaign stats
    campaign.status = CampaignStatus.ACTIVE
    campaign.started_at = datetime.utcnow()
    campaign.leads_total = len(leads)
    campaign.leads_contacted = sent_count
    
    await db.commit()
    await db.refresh(campaign)
    
    # Paperclip: log campaign launch
    try:
        on_campaign_launched(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            target_city=campaign.target_city or "Unknown",
            lead_count=campaign.leads_total,
        )
    except Exception:
        pass
    
    return campaign


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = CampaignStatus.PAUSED
    await db.commit()
    await db.refresh(campaign)
    return campaign
