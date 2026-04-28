from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.campaign import Campaign, CampaignLead
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter()


@router.get("/pipeline")
async def get_pipeline_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get counts of leads by status for pipeline visualization."""
    result = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
    )
    pipeline = {status.value: 0 for status in LeadStatus}
    for status, count in result.all():
        pipeline[status.value] = count
    
    total_leads = sum(pipeline.values())
    
    return {
        "pipeline": pipeline,
        "total_leads": total_leads,
        "active_campaigns": await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == "active")
        ),
    }


@router.get("/performance")
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get key performance metrics."""
    total_leads = await db.scalar(select(func.count(Lead.id)))
    contacted = await db.scalar(
        select(func.count(Lead.id)).where(Lead.status.in_([
            LeadStatus.CONTACTED, LeadStatus.ENGAGED, LeadStatus.MEETING_BOOKED,
            LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATING, LeadStatus.CLOSED_WON,
        ]))
    )
    closed_won = await db.scalar(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.CLOSED_WON)
    )
    avg_score = await db.scalar(
        select(func.avg(Lead.total_score)).where(Lead.total_score.isnot(None))
    )
    
    conversion_rate = (closed_won / contacted * 100) if contacted else 0
    
    return {
        "total_leads": total_leads,
        "contacted": contacted,
        "closed_won": closed_won,
        "conversion_rate": round(conversion_rate, 2),
        "avg_lead_score": round(avg_score or 0, 2),
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get funnel analytics for a specific campaign."""
    campaign = await db.scalar(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get all leads in this campaign
    lead_ids_result = await db.execute(
        select(CampaignLead.lead_id).where(CampaignLead.campaign_id == campaign_id)
    )
    lead_ids = [row[0] for row in lead_ids_result.all()]

    if not lead_ids:
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "funnel": {
                "leads": 0,
                "emails_sent": 0,
                "emails_opened": 0,
                "emails_clicked": 0,
                "replies": 0,
                "meetings_booked": 0,
                "closed_won": 0,
            },
            "rates": {
                "open_rate": 0,
                "click_rate": 0,
                "reply_rate": 0,
                "meeting_rate": 0,
                "conversion_rate": 0,
            },
        }

    # Count emails sent (interactions with campaign_id in meta)
    emails_sent = await db.scalar(
        select(func.count(Interaction.id))
        .where(Interaction.lead_id.in_(lead_ids))
        .where(Interaction.interaction_type == "email")
        .where(Interaction.direction == "outbound")
        .where(Interaction.email_status == "sent")
    )

    # Count opens (from interactions where email_status = 'opened')
    emails_opened = await db.scalar(
        select(func.count(Interaction.id))
        .where(Interaction.lead_id.in_(lead_ids))
        .where(Interaction.interaction_type == "email")
        .where(Interaction.email_status == "opened")
    )

    # Count clicks
    emails_clicked = await db.scalar(
        select(func.count(Interaction.id))
        .where(Interaction.lead_id.in_(lead_ids))
        .where(Interaction.interaction_type == "email")
        .where(Interaction.email_status == "clicked")
    )

    # Count replies (inbound emails)
    replies = await db.scalar(
        select(func.count(Interaction.id))
        .where(Interaction.lead_id.in_(lead_ids))
        .where(Interaction.interaction_type == "email")
        .where(Interaction.direction == "inbound")
    )

    # Count meetings booked
    meetings_booked = await db.scalar(
        select(func.count(Lead.id))
        .where(Lead.id.in_(lead_ids))
        .where(Lead.status == LeadStatus.MEETING_BOOKED)
    )

    # Count closed won
    closed_won = await db.scalar(
        select(func.count(Lead.id))
        .where(Lead.id.in_(lead_ids))
        .where(Lead.status == LeadStatus.CLOSED_WON)
    )

    total_leads = len(lead_ids)
    open_rate = round((emails_opened / emails_sent * 100), 2) if emails_sent else 0
    click_rate = round((emails_clicked / emails_sent * 100), 2) if emails_sent else 0
    reply_rate = round((replies / emails_sent * 100), 2) if emails_sent else 0
    meeting_rate = round((meetings_booked / total_leads * 100), 2) if total_leads else 0
    conversion_rate = round((closed_won / total_leads * 100), 2) if total_leads else 0

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "funnel": {
            "leads": total_leads,
            "emails_sent": emails_sent or 0,
            "emails_opened": emails_opened or 0,
            "emails_clicked": emails_clicked or 0,
            "replies": replies or 0,
            "meetings_booked": meetings_booked or 0,
            "closed_won": closed_won or 0,
        },
        "rates": {
            "open_rate": open_rate,
            "click_rate": click_rate,
            "reply_rate": reply_rate,
            "meeting_rate": meeting_rate,
            "conversion_rate": conversion_rate,
        },
    }
