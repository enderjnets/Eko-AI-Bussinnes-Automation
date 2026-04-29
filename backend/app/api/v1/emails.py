from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.user import User
from app.agents.outreach.channels.email import EmailOutreach
from app.core.security import get_current_user
from app.services.reply_analyzer import analyze_email_reply, determine_status_from_intent
from app.services.email_reply_agent import generate_ai_reply, get_conversation_history

router = APIRouter()


@router.post("/{lead_id}/send")
async def send_email_to_lead(
    lead_id: int,
    subject: str,
    body: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a personalized email to a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")
    
    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked as do-not-contact")
    
    email_outreach = EmailOutreach()
    response = await email_outreach.send(
        to_email=lead.email,
        subject=subject,
        body=body,
        lead_id=lead_id,
    )
    
    return {"status": "sent", "message_id": response.get("id")}


@router.post("/{lead_id}/generate-and-send")
async def generate_and_send_email(
    lead_id: int,
    campaign_context: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a personalized email using AI and send it."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")
    
    email_outreach = EmailOutreach()
    response = await email_outreach.generate_and_send(
        lead=lead,
        campaign_context=campaign_context,
    )
    
    return {"status": "sent", "message_id": response.get("id")}


# ---------------------------------------------------------------------------
# Inbox & Reply Handling
# ---------------------------------------------------------------------------

@router.get("/inbox")
async def get_inbox(
    status: Optional[str] = None,  # "unread", "read", "all"
    lead_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get inbound email replies (the inbox).
    
    Returns interactions with direction='inbound' and interaction_type='email',
    enriched with lead info and AI analysis.
    """
    query = (
        select(Interaction, Lead)
        .join(Lead, Interaction.lead_id == Lead.id)
        .where(Interaction.interaction_type == "email")
        .where(Interaction.direction == "inbound")
        .order_by(desc(Interaction.created_at))
    )
    
    if lead_id:
        query = query.where(Interaction.lead_id == lead_id)
    
    if status == "unread":
        from sqlalchemy import or_
        query = query.where(
            or_(
                Interaction.meta.is_(None),
                Interaction.meta.op("?")("read") == False,
            )
        )
    elif status == "read":
        query = query.where(Interaction.meta.op("?")("read") == True)
    
    # Count total
    count_query = query.with_only_columns(
        select(Interaction.id).where(Interaction.interaction_type == "email").where(Interaction.direction == "inbound").correlate(Lead).subquery().columns.id
    )
    # Simpler count
    count_result = await db.execute(
        select(Interaction).where(Interaction.interaction_type == "email").where(Interaction.direction == "inbound")
    )
    total = len(count_result.scalars().all())
    
    result = await db.execute(query.offset(offset).limit(limit))
    items = []
    for interaction, lead in result.all():
        meta = interaction.meta or {}
        items.append({
            "id": interaction.id,
            "lead_id": lead.id,
            "lead_name": lead.business_name,
            "lead_email": lead.email,
            "lead_status": lead.status.value if lead.status else None,
            "subject": interaction.subject,
            "content": interaction.content,
            "sentiment": meta.get("sentiment"),
            "intent": meta.get("intent"),
            "summary": meta.get("summary"),
            "next_action": meta.get("next_action"),
            "priority": meta.get("priority", "medium"),
            "key_points": meta.get("key_points", []),
            "read": meta.get("read", False),
            "auto_status_changed": meta.get("auto_status_changed", False),
            "previous_status": meta.get("previous_status"),
            "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
        })
    
    return {
        "total": total,
        "items": items,
        "unread_count": sum(1 for i in items if not i["read"]),
    }


@router.post("/{interaction_id}/mark-read")
async def mark_reply_read(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an inbound email as read."""
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    meta = interaction.meta or {}
    meta["read"] = True
    meta["read_at"] = datetime.utcnow().isoformat()
    interaction.meta = meta
    
    await db.commit()
    return {"status": "marked_as_read"}


class SimulateReplyRequest(BaseModel):
    lead_id: int
    subject: str
    body: str
    from_email: Optional[str] = None
    auto_analyze: bool = True


@router.post("/simulate-reply")
async def simulate_reply(
    data: SimulateReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulate an inbound email reply (for demos/testing).
    Creates an Interaction record and optionally runs AI analysis + auto-status-update.
    """
    result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Find the most recent outbound email to this lead for context
    last_email_result = await db.execute(
        select(Interaction)
        .where(Interaction.lead_id == data.lead_id)
        .where(Interaction.interaction_type == "email")
        .where(Interaction.direction == "outbound")
        .order_by(desc(Interaction.created_at))
        .limit(1)
    )
    last_email = last_email_result.scalar_one_or_none()
    
    # AI analysis
    analysis = {}
    if data.auto_analyze:
        analysis = await analyze_email_reply(
            reply_text=data.body,
            lead_name=lead.business_name,
            business_name=lead.business_name,
            previous_email_subject=last_email.subject if last_email else None,
        )
    
    # Determine status change
    new_status = None
    previous_status = None
    if data.auto_analyze and lead.status:
        previous_status = lead.status.value
        new_status_value = determine_status_from_intent(
            analysis.get("intent", ""),
            previous_status,
        )
        if new_status_value:
            try:
                lead.status = LeadStatus(new_status_value)
            except ValueError:
                new_status_value = None
    
    # Create interaction
    meta = {
        "simulated": True,
        "sentiment": analysis.get("sentiment"),
        "intent": analysis.get("intent"),
        "summary": analysis.get("summary"),
        "next_action": analysis.get("next_action"),
        "priority": analysis.get("priority", "medium"),
        "key_points": analysis.get("key_points", []),
        "read": False,
        "auto_status_changed": new_status_value is not None,
        "previous_status": previous_status,
        "new_status": new_status_value,
    }
    
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="email",
        direction="inbound",
        subject=data.subject,
        content=data.body,
        meta=meta,
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    
    return {
        "status": "created",
        "interaction_id": interaction.id,
        "analysis": analysis,
        "status_changed": new_status_value is not None,
        "previous_status": previous_status,
        "new_status": new_status_value,
    }


# ---------------------------------------------------------------------------
# AI Email Reply Agent
# ---------------------------------------------------------------------------

class AIReplyRequest(BaseModel):
    tone: str = "professional"  # professional, friendly, assertive, consultative
    max_length: str = "medium"  # short, medium, long
    custom_instructions: Optional[str] = None


@router.post("/{interaction_id}/ai-reply")
async def generate_ai_email_reply(
    interaction_id: int,
    data: AIReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an AI-powered reply to an inbound email.
    Returns the generated reply with metadata.
    """
    # Get the inbound interaction
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    
    # Get the lead
    result = await db.execute(
        select(Lead).where(Lead.id == interaction.lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get conversation history
    conversation = await get_conversation_history(lead.id, db, limit=10)
    
    # Generate AI reply
    reply = await generate_ai_reply(
        lead=lead,
        inbound_email=interaction,
        conversation_history=conversation,
        tone=data.tone,
        max_length=data.max_length,
        custom_instructions=data.custom_instructions,
    )
    
    # Store the generated reply in the interaction meta for later reference
    meta = interaction.meta or {}
    meta["ai_reply"] = {
        "subject": reply["subject"],
        "body": reply["body"],
        "tone": reply["tone"],
        "confidence": reply["confidence"],
        "suggested_next_action": reply["suggested_next_action"],
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": current_user.id,
    }
    interaction.meta = meta
    await db.commit()
    
    return {
        "status": "generated",
        "interaction_id": interaction.id,
        "lead_id": lead.id,
        "lead_name": lead.business_name,
        "reply": reply,
    }


class SendReplyRequest(BaseModel):
    subject: str
    body: str
    send_email: bool = True


@router.post("/{interaction_id}/send-reply")
async def send_email_reply(
    interaction_id: int,
    data: SendReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a reply email to a lead. Can be used with AI-generated or manually written replies.
    """
    # Get the inbound interaction
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    
    # Get the lead
    result = await db.execute(
        select(Lead).where(Lead.id == interaction.lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")
    
    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked as do-not-contact")
    
    message_id = None
    if data.send_email:
        email_outreach = EmailOutreach()
        response = await email_outreach.send(
            to_email=lead.email,
            subject=data.subject,
            body=data.body,
            lead_id=lead.id,
        )
        message_id = response.get("id")
    
    # Create outbound interaction record
    outbound = Interaction(
        lead_id=lead.id,
        interaction_type="email",
        direction="outbound",
        subject=data.subject,
        content=data.body,
        email_message_id=message_id,
        meta={
            "reply_to": interaction_id,
            "sent_by_user": current_user.id,
            "sent_at": datetime.utcnow().isoformat(),
            "ai_generated": (interaction.meta or {}).get("ai_reply") is not None,
        },
    )
    db.add(outbound)
    
    # Update lead's last_contact_at
    lead.last_contact_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(outbound)
    
    return {
        "status": "sent" if data.send_email else "draft_saved",
        "interaction_id": outbound.id,
        "message_id": message_id,
        "lead_id": lead.id,
    }


@router.get("/{interaction_id}/conversation")
async def get_email_conversation(
    interaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full email conversation thread for a lead."""
    result = await db.execute(
        select(Interaction).where(Interaction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    
    conversation = await get_conversation_history(interaction.lead_id, db, limit=50)
    
    return {
        "lead_id": interaction.lead_id,
        "items": [
            {
                "id": i.id,
                "direction": i.direction,
                "subject": i.subject,
                "content": i.content,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "meta": i.meta or {},
            }
            for i in conversation
        ],
    }
