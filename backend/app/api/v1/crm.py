from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.schemas.lead import LeadUpdate, LeadResponse
from app.agents.outreach.channels.email import EmailOutreach
from app.services.paperclip import on_lead_status_change

router = APIRouter()


# Define valid pipeline transitions
VALID_TRANSITIONS = {
    LeadStatus.DISCOVERED: [LeadStatus.ENRICHED, LeadStatus.CONTACTED],
    LeadStatus.ENRICHED: [LeadStatus.SCORED, LeadStatus.CONTACTED],
    LeadStatus.SCORED: [LeadStatus.CONTACTED, LeadStatus.CLOSED_LOST],
    LeadStatus.CONTACTED: [LeadStatus.ENGAGED, LeadStatus.CLOSED_LOST],
    LeadStatus.ENGAGED: [LeadStatus.MEETING_BOOKED, LeadStatus.PROPOSAL_SENT, LeadStatus.CLOSED_LOST],
    LeadStatus.MEETING_BOOKED: [LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATING, LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST],
    LeadStatus.PROPOSAL_SENT: [LeadStatus.NEGOTIATING, LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST],
    LeadStatus.NEGOTIATING: [LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST],
    LeadStatus.CLOSED_WON: [LeadStatus.ACTIVE],
    LeadStatus.CLOSED_LOST: [LeadStatus.DISCOVERED],  # For reactivation
    LeadStatus.ACTIVE: [LeadStatus.AT_RISK],
    LeadStatus.AT_RISK: [LeadStatus.CHURNED, LeadStatus.ACTIVE],
}


# Rate limiting: max 5 contacts per lead per day
MAX_CONTACTS_PER_DAY = 5


async def _check_contact_rate_limit(lead: Lead, db: AsyncSession) -> bool:
    """Check if lead has been contacted too many times today."""
    from sqlalchemy import and_
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(func.count(Interaction.id))
        .where(and_(
            Interaction.lead_id == lead.id,
            Interaction.interaction_type == "email",
            Interaction.created_at >= today_start,
        ))
    )
    count = result.scalar() or 0
    return count < MAX_CONTACTS_PER_DAY


@router.post("/{lead_id}/transition")
async def transition_lead(
    lead_id: int,
    new_status: LeadStatus,
    note: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Move a lead to a new pipeline stage.
    Validates that the transition is allowed.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    current_status = lead.status
    
    # Validate transition
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {current_status.value} to {new_status.value}. Allowed: {[s.value for s in allowed]}"
        )
    
    old_status = lead.status.value
    lead.status = new_status
    
    # Update timestamps based on stage
    if new_status == LeadStatus.CONTACTED:
        lead.last_contact_at = datetime.utcnow()
    elif new_status == LeadStatus.MEETING_BOOKED:
        lead.next_follow_up_at = datetime.utcnow() + timedelta(days=1)
    
    # Record interaction
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="note",
        direction="outbound",
        content=note or f"Status changed from {old_status} to {new_status.value}",
        metadata={"transition": True, "from": old_status, "to": new_status.value},
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(lead)
    
    # Paperclip: log status change
    try:
        on_lead_status_change(
            lead_id=lead.id,
            business_name=lead.business_name,
            old_status=old_status,
            new_status=new_status.value,
        )
    except Exception:
        pass
    
    return lead


@router.post("/{lead_id}/contact")
async def contact_lead(
    lead_id: int,
    channel: str = "email",
    template: Optional[str] = None,
    custom_subject: Optional[str] = None,
    custom_body: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Contact a lead via specified channel.
    Updates status to 'contacted' and records the interaction.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked as do-not-contact")
    
    # Rate limiting
    if not await _check_contact_rate_limit(lead, db):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {MAX_CONTACTS_PER_DAY} contacts per day per lead"
        )
    
    if channel == "email":
        if not lead.email:
            raise HTTPException(status_code=400, detail="Lead has no email")
        
        email = EmailOutreach()
        
        if custom_subject and custom_body:
            # Manual email
            response = await email.send(
                to_email=lead.email,
                subject=custom_subject,
                body=custom_body,
                lead_id=lead.id,
                business_name=lead.business_name,
                ai_generated=False,
            )
        else:
            # AI-generated email
            response = await email.generate_and_send(
                lead=lead,
                template_key=template or "initial_outreach",
            )
        
        # Update status
        if lead.status in [LeadStatus.DISCOVERED, LeadStatus.ENRICHED, LeadStatus.SCORED]:
            old_status = lead.status.value
            lead.status = LeadStatus.CONTACTED
            lead.last_contact_at = datetime.utcnow()
            
            # Paperclip
            try:
                on_lead_status_change(
                    lead_id=lead.id,
                    business_name=lead.business_name,
                    old_status=old_status,
                    new_status="contacted",
                )
            except Exception:
                pass
        
        await db.commit()
        await db.refresh(lead)
        
        return {
            "status": "sent",
            "channel": channel,
            "message_id": response.get("id"),
            "lead": lead,
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"Channel {channel} not yet implemented")


@router.post("/{lead_id}/schedule-follow-up")
async def schedule_follow_up(
    lead_id: int,
    days: int = 3,
    note: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Schedule a follow-up for a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    follow_up_date = datetime.utcnow() + timedelta(days=days)
    lead.next_follow_up_at = follow_up_date
    
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="note",
        direction="outbound",
        content=note or f"Follow-up scheduled for {follow_up_date.isoformat()}",
        metadata={"follow_up_scheduled": True, "days": days},
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(lead)
    
    return {"status": "scheduled", "next_follow_up": follow_up_date, "lead": lead}


@router.get("/pipeline/summary")
async def get_pipeline_summary(db: AsyncSession = Depends(get_db)):
    """Get pipeline summary with counts and conversion metrics."""
    result = await db.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    
    pipeline = {status.value: 0 for status in LeadStatus}
    for status, count in result.all():
        pipeline[status.value] = count
    
    total = sum(pipeline.values())
    
    # Calculate conversion rates
    contacted = pipeline.get("contacted", 0) + pipeline.get("engaged", 0) + pipeline.get("meeting_booked", 0)
    won = pipeline.get("closed_won", 0)
    
    conversion_rate = (won / contacted * 100) if contacted else 0
    
    return {
        "pipeline": pipeline,
        "total_leads": total,
        "conversion_rate": round(conversion_rate, 2),
        "active_campaigns": 0,
    }


@router.get("/follow-ups")
async def get_pending_follow_ups(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get leads that need follow-up."""
    now = datetime.utcnow()
    
    result = await db.execute(
        select(Lead)
        .where(Lead.next_follow_up_at <= now)
        .where(Lead.do_not_contact == False)
        .where(Lead.status.not_in([LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST, LeadStatus.CHURNED]))
        .order_by(Lead.next_follow_up_at)
        .limit(limit)
    )
    
    return result.scalars().all()
