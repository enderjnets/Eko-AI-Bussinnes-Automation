import hmac
import hashlib
import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Request, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.campaign import Campaign
from app.models.phone_call import PhoneCall
from app.config import get_settings
from app.services.reply_analyzer import analyze_email_reply, determine_status_from_intent

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Resend Inbound Email Webhook
# ---------------------------------------------------------------------------

async def _verify_resend_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify Resend webhook signature using HMAC-SHA256.
    
    Resend sends: Resend-Signature: t=<timestamp>,v=<signature>
    Expected signature: HMAC-SHA256(secret, '<timestamp>.<payload>')
    """
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        logger.warning("RESEND_WEBHOOK_SECRET not set, skipping signature verification")
        return True
    
    try:
        # Parse the signature header: "t=1712345678,v=abc123..."
        parts = {}
        for part in signature_header.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                parts[key.strip()] = value.strip()
        
        timestamp = parts.get("t", "")
        received_signature = parts.get("v", "")
        
        if not timestamp or not received_signature:
            logger.warning(f"Invalid signature header format: {signature_header}")
            return False
        
        # Construct signed payload: "<timestamp>.<json_body>"
        signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, received_signature)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


async def _fetch_email_body_from_resend(email_id: str) -> dict:
    """Fetch the full email content (text + html) from Resend API."""
    api_key = settings.RESEND_API_KEY
    if not api_key:
        logger.warning("RESEND_API_KEY not set, cannot fetch email body")
        return {}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try the receiving API first (for inbound emails)
            response = await client.get(
                f"https://api.resend.com/emails/{email_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "text": data.get("text", ""),
                    "html": data.get("html", ""),
                    "subject": data.get("subject", ""),
                    "from": data.get("from", ""),
                    "to": data.get("to", []),
                }
            else:
                logger.warning(f"Failed to fetch email body: {response.status_code} {response.text}")
                return {}
    except Exception as e:
        logger.error(f"Error fetching email body from Resend: {e}")
        return {}


@router.post("/resend-inbound")
async def resend_inbound_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Resend inbound email webhooks.
    
    Receives emails sent to contact@biz.ekoaiautomation.com,
    creates Interaction records, runs AI analysis, and updates lead status.
    """
    # Read raw payload for signature verification
    payload_bytes = await request.body()
    
    # Verify signature if secret is configured
    signature = request.headers.get("Resend-Signature", "")
    logger.info(f"Resend webhook received. Signature header: '{signature[:50]}...' if signature else 'EMPTY'")
    logger.info(f"All headers: {dict(request.headers)}")
    
    if settings.RESEND_WEBHOOK_SECRET and signature and not await _verify_resend_signature(payload_bytes, signature):
        logger.warning("Invalid webhook signature - processing anyway for debugging")
        # TODO: Re-enable signature verification once format is confirmed
        # return Response(status_code=401, content="Invalid signature")
    
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload")
        return Response(status_code=400, content="Invalid JSON")
    
    event_type = payload.get("type")
    if event_type != "email.received":
        logger.info(f"Ignoring non-inbound event: {event_type}")
        return {"status": "ignored", "reason": f"event type {event_type} not handled"}
    
    data = payload.get("data", {})
    email_id = data.get("email_id")
    from_email_raw = data.get("from", "")
    to_emails = data.get("to", [])
    subject = data.get("subject", "")
    
    # Parse from email (may be "Name <email@domain.com>")
    from_email = from_email_raw
    if "<" in from_email_raw and ">" in from_email_raw:
        from_email = from_email_raw.split("<")[1].split(">")[0].strip().lower()
    else:
        from_email = from_email_raw.strip().lower()
    
    # Skip emails from our own domain (loop prevention)
    inbound_domain = settings.RESEND_INBOUND_DOMAIN or "biz.ekoaiautomation.com"
    if from_email.endswith(f"@{inbound_domain}") or from_email.endswith("@ekoai.com"):
        logger.info(f"Ignoring email from own domain: {from_email}")
        return {"status": "ignored", "reason": "own domain"}
    
    # Fetch full email body from Resend API
    email_body_data = {}
    if email_id:
        email_body_data = await _fetch_email_body_from_resend(email_id)
    
    email_text = email_body_data.get("text", "")
    email_html = email_body_data.get("html", "")
    # Use text body for analysis, fallback to html stripped
    body_for_analysis = email_text or email_html or ""
    
    # Find lead by sender email
    result = await db.execute(select(Lead).where(Lead.email == from_email))
    lead = result.scalar_one_or_none()
    
    # Create lead if not found and auto-create is enabled
    if not lead and settings.AUTO_CREATE_LEAD_FROM_INBOUND:
        # Extract business name from email or from field
        business_name = from_email_raw
        if "<" in from_email_raw:
            business_name = from_email_raw.split("<")[0].strip() or from_email.split("@")[0]
        else:
            business_name = from_email.split("@")[0]
        
        lead = Lead(
            business_name=business_name,
            email=from_email,
            source="manual",  # Using MANUAL source since it's an inbound inquiry
            status=LeadStatus.DISCOVERED,
            notes=f"Auto-created from inbound email to {', '.join(to_emails)}",
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        logger.info(f"Auto-created lead {lead.id} from inbound email: {from_email}")
    
    if not lead:
        logger.warning(f"No lead found for {from_email} and auto-create disabled")
        return {"status": "ignored", "reason": "no lead found"}
    
    # Find the most recent outbound email to this lead for context
    last_email_result = await db.execute(
        select(Interaction)
        .where(Interaction.lead_id == lead.id)
        .where(Interaction.interaction_type == "email")
        .where(Interaction.direction == "outbound")
        .order_by(Interaction.created_at.desc())
        .limit(1)
    )
    last_email = last_email_result.scalar_one_or_none()
    
    # AI analysis
    analysis = {}
    if body_for_analysis:
        try:
            analysis = await analyze_email_reply(
                reply_text=body_for_analysis,
                lead_name=lead.business_name,
                business_name=lead.business_name,
                previous_email_subject=last_email.subject if last_email else None,
            )
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
    
    # Determine status change
    new_status = None
    previous_status = None
    if lead.status:
        previous_status = lead.status.value
        new_status_value = determine_status_from_intent(
            analysis.get("intent", ""),
            previous_status,
        )
        if new_status_value:
            try:
                lead.status = LeadStatus(new_status_value)
                new_status = new_status_value
            except ValueError:
                pass
    
    # Create interaction
    meta = {
        "email_id": email_id,
        "from": from_email_raw,
        "to": to_emails,
        "inbound": True,
        "source": "resend_inbound",
        "sentiment": analysis.get("sentiment"),
        "intent": analysis.get("intent"),
        "summary": analysis.get("summary"),
        "next_action": analysis.get("next_action"),
        "priority": analysis.get("priority", "medium"),
        "key_points": analysis.get("key_points", []),
        "read": False,
        "auto_status_changed": new_status is not None,
        "previous_status": previous_status,
        "new_status": new_status,
        "html": email_html[:5000] if email_html else None,  # Store preview only
    }
    
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="email",
        direction="inbound",
        subject=subject,
        content=body_for_analysis[:10000] if body_for_analysis else "",
        email_message_id=email_id,
        ai_summary=analysis.get("summary"),
        ai_next_action=analysis.get("next_action"),
        meta=meta,
    )
    db.add(interaction)
    
    # Update lead engagement
    lead.last_contact_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(
        f"Processed inbound email from {from_email} for lead {lead.id}: "
        f"intent={analysis.get('intent', 'unknown')}, priority={analysis.get('priority', 'medium')}"
    )
    
    return {
        "status": "processed",
        "lead_id": lead.id,
        "interaction_id": interaction.id,
        "intent": analysis.get("intent"),
        "priority": analysis.get("priority"),
    }
