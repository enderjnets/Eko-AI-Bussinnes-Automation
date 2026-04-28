from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, Interaction
from app.models.campaign import Campaign
from app.models.phone_call import PhoneCall

router = APIRouter()


@router.post("/resend")
async def resend_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Resend webhooks for email events."""
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})
    
    message_id = data.get("email_id")
    to_email = data.get("to", [None])[0] if isinstance(data.get("to"), list) else data.get("to")
    
    # Find lead by email
    if to_email:
        result = await db.execute(select(Lead).where(Lead.email == to_email))
        lead = result.scalar_one_or_none()
        
        if lead:
            # Update engagement stats
            if event_type == "email.opened":
                lead.email_opened_count += 1
            elif event_type == "email.clicked":
                lead.email_clicked_count += 1
                # If clicked pricing page or booking link, upgrade status
                if lead.status.value == "contacted":
                    lead.status = "engaged"
            
            # Record interaction
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="inbound" if event_type in ["email.opened", "email.clicked"] else "outbound",
                email_status=event_type.replace("email.", ""),
                email_message_id=message_id,
                meta=payload,
            )
            db.add(interaction)
            await db.commit()
    
    return {"status": "ok"}


@router.post("/calcom")
async def calcom_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Cal.com webhooks for booking events."""
    payload = await request.json()
    event_type = payload.get("triggerEvent")
    
    # Extract attendee email
    attendees = payload.get("payload", {}).get("attendees", [])
    attendee_email = attendees[0].get("email") if attendees else None
    
    if attendee_email:
        result = await db.execute(select(Lead).where(Lead.email == attendee_email))
        lead = result.scalar_one_or_none()
        
        if lead:
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="meeting",
                direction="inbound",
                subject=f"Meeting {event_type}",
                meta=payload,
            )
            db.add(interaction)
            
            if event_type == "BOOKING_CREATED":
                from app.models.lead import LeadStatus
                lead.status = LeadStatus.MEETING_BOOKED
            
            await db.commit()
    
    return {"status": "ok"}


@router.get("/unsubscribe")
async def unsubscribe_lead(
    lead_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Unsubscribe a lead from emails (CAN-SPAM compliance)."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if lead:
        lead.do_not_contact = True
        lead.consent_status = "opted_out"
        
        interaction = Interaction(
            lead_id=lead.id,
            interaction_type="email",
            direction="inbound",
            subject="Unsubscribe request",
            content="Lead opted out via unsubscribe link",
        )
        db.add(interaction)
        await db.commit()
        
        return {
            "status": "unsubscribed",
            "message": "You have been unsubscribed from future communications.",
        }
    
    return {"status": "error", "message": "Lead not found"}


@router.get("/track/open")
async def track_email_open(
    lead_id: int = Query(...),
    message_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Track email open via tracking pixel."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if lead:
        lead.email_opened_count += 1
        
        interaction = Interaction(
            lead_id=lead.id,
            interaction_type="email",
            direction="inbound",
            email_status="opened",
            email_message_id=message_id,
        )
        db.add(interaction)
        await db.commit()
    
    # Return 1x1 transparent pixel
    from fastapi.responses import Response
    return Response(
        content=b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b",
        media_type="image/gif",
    )


# ---------------------------------------------------------------------------
# VAPI Webhooks
# ---------------------------------------------------------------------------

@router.post("/vapi")
async def vapi_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle VAPI webhooks for call events.
    
    Events:
    - "end-of-call-report": Call completed, includes transcript, summary, recording
    - "status-update": Call status changed (queued, ringing, in-progress, completed)
    - "conversation-update": Real-time conversation updates
    """
    payload = await request.json()
    message_type = payload.get("message", {}).get("type") or payload.get("type")
    
    # Extract call info
    call_data = payload.get("call") or payload.get("message", {}).get("call")
    if not call_data:
        return {"status": "ignored", "reason": "no call data"}
    
    vapi_call_id = call_data.get("id")
    customer = call_data.get("customer", {})
    customer_number = customer.get("number")
    
    # Find lead by phone number
    lead = None
    if customer_number:
        result = await db.execute(
            select(Lead).where(Lead.phone == customer_number)
        )
        lead = result.scalar_one_or_none()
    
    # Find the interaction record for this call
    interaction = None
    if vapi_call_id:
        result = await db.execute(
            select(Interaction)
            .where(Interaction.interaction_type == "call")
            .where(Interaction.meta["vapi_call_id"].astext == vapi_call_id)
        )
        interaction = result.scalar_one_or_none()
    
    if message_type == "end-of-call-report":
        return await _handle_end_of_call(call_data, lead, interaction, db)
    elif message_type == "status-update":
        return await _handle_status_update(call_data, lead, interaction, db)
    elif message_type == "conversation-update":
        return await _handle_conversation_update(call_data, lead, interaction, db)
    
    return {"status": "ok", "type": message_type}


async def _handle_end_of_call(call_data, lead, interaction, db):
    """Process end-of-call report from VAPI."""
    from datetime import datetime
    
    summary = call_data.get("summary", "")
    transcript = call_data.get("transcript", "")
    recording_url = call_data.get("recordingUrl", "")
    duration_seconds = call_data.get("durationSeconds", 0)
    ended_reason = call_data.get("endedReason", "")
    cost = call_data.get("cost", 0)
    
    # Determine result
    result_map = {
        "customer-ended-call": "COMPLETED",
        "assistant-ended-call": "COMPLETED",
        "voicemail-reached": "VOICEMAIL",
        "no-answer": "NO_ANSWER",
        "busy": "BUSY",
        "failed": "FAILED",
    }
    result = result_map.get(ended_reason, "COMPLETED")
    
    # Determine interest level from summary
    interest_level = "NONE"
    if summary:
        summary_lower = summary.lower()
        if any(w in summary_lower for w in ["interesado", "interesa", "agendar", "reunión", "demo"]):
            interest_level = "HIGH"
        elif any(w in summary_lower for w in ["información", "pensarlo", "considerar", "email"]):
            interest_level = "MEDIUM"
        elif any(w in summary_lower for w in ["no interesa", "no gracias", "baja"]):
            interest_level = "LOW"
    
    # Find or create phone call record
    phone_call = None
    if lead:
        result_query = await db.execute(
            select(PhoneCall)
            .where(PhoneCall.lead_id == lead.id)
            .order_by(PhoneCall.created_at.desc())
            .limit(1)
        )
        phone_call = result_query.scalar_one_or_none()
    
    if phone_call:
        phone_call.result = result
        phone_call.notes = summary or phone_call.notes
        phone_call.interest_level = interest_level
        phone_call.call_duration_seconds = duration_seconds
        phone_call.completed_at = datetime.utcnow()
    elif lead:
        phone_call = PhoneCall(
            lead_id=lead.id,
            result=result,
            notes=summary,
            interest_level=interest_level,
            call_duration_seconds=duration_seconds,
            completed_at=datetime.utcnow(),
        )
        db.add(phone_call)
    
    # Update interaction
    if interaction:
        interaction.call_duration_seconds = duration_seconds
        interaction.call_transcript = transcript
        interaction.call_recording_url = recording_url
        meta = interaction.meta or {}
        meta.update({
            "status": "completed",
            "ended_reason": ended_reason,
            "summary": summary,
            "cost": cost,
            "recording_url": recording_url,
        })
        interaction.meta = meta
    elif lead:
        interaction = Interaction(
            lead_id=lead.id,
            interaction_type="call",
            direction="inbound",
            subject="VAPI Voice Call Completed",
            content=transcript[:2000] if transcript else summary,
            call_duration_seconds=duration_seconds,
            call_transcript=transcript,
            call_recording_url=recording_url,
            meta={
                "vapi_call_id": call_data.get("id"),
                "status": "completed",
                "ended_reason": ended_reason,
                "summary": summary,
                "cost": cost,
            },
        )
        db.add(interaction)
    
    # Update lead status if high interest
    if lead and interest_level == "HIGH" and lead.status.value in ["contacted", "engaged"]:
        lead.status = "meeting_booked"
    
    await db.commit()
    
    return {
        "status": "processed",
        "type": "end-of-call-report",
        "lead_id": lead.id if lead else None,
        "result": result,
        "interest_level": interest_level,
        "duration": duration_seconds,
    }


async def _handle_status_update(call_data, lead, interaction, db):
    """Process status update from VAPI."""
    status = call_data.get("status", "")
    
    if interaction:
        meta = interaction.meta or {}
        meta["vapi_status"] = status
        interaction.meta = meta
        await db.commit()
    
    return {"status": "processed", "type": "status-update", "vapi_status": status}


async def _handle_conversation_update(call_data, lead, interaction, db):
    """Process conversation update from VAPI."""
    return {"status": "processed", "type": "conversation-update"}
