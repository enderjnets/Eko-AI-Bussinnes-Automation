from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus
from app.models.phone_call import PhoneCall
from app.models.user import User
from app.schemas.phone_call import PhoneCallCreate, PhoneCallResponse
from app.core.security import get_current_user

router = APIRouter()


@router.post("", response_model=PhoneCallResponse)
async def create_phone_call(
    data: PhoneCallCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log a phone call and update lead status."""
    result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    phone_call = PhoneCall(
        lead_id=data.lead_id,
        result=data.result,
        notes=data.notes,
        interest_level=data.interest_level,
        next_action=data.next_action,
        call_duration_seconds=data.call_duration_seconds,
        scheduled_at=data.scheduled_at,
        completed_at=datetime.utcnow(),
    )
    db.add(phone_call)

    # Update lead call tracking
    lead.call_attempts += 1
    lead.call_count += 1
    lead.last_call_result = data.result
    lead.last_contact_at = datetime.utcnow()

    # Handle next action
    if data.next_action == "CALL_AGAIN" and data.scheduled_at:
        lead.next_call_at = data.scheduled_at
    elif data.next_action == "EMAIL":
        lead.next_follow_up_at = datetime.utcnow()
    elif data.next_action == "CLOSE" or data.interest_level == "NONE":
        if lead.status not in [LeadStatus.CLOSED_WON, LeadStatus.MEETING_BOOKED]:
            lead.status = LeadStatus.CLOSED_LOST
    elif data.result == "CONNECTED" and data.interest_level in ["HIGH", "MEDIUM"]:
        if lead.status == LeadStatus.SCORED:
            lead.status = LeadStatus.CONTACTED

    await db.commit()
    await db.refresh(phone_call)
    return phone_call


@router.get("/scheduled", response_model=list[PhoneCallResponse])
async def get_scheduled_calls(
    today: bool = Query(True, description="Only return calls scheduled for today or earlier"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scheduled phone calls."""
    query = select(PhoneCall).where(PhoneCall.result == "SCHEDULED")
    if today:
        now = datetime.utcnow()
        today_end = now.replace(hour=23, minute=59, second=59)
        query = query.where(
            and_(
                PhoneCall.scheduled_at <= today_end,
                PhoneCall.completed_at == None,
            )
        )
    query = query.order_by(PhoneCall.scheduled_at)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/lead/{lead_id}", response_model=list[PhoneCallResponse])
async def get_lead_calls(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all phone calls for a lead."""
    result = await db.execute(
        select(PhoneCall)
        .where(PhoneCall.lead_id == lead_id)
        .order_by(PhoneCall.created_at.desc())
    )
    return result.scalars().all()
