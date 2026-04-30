import base64
import hmac
import hashlib
import json
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Request, Depends, Query, Response
from sqlalchemy import select, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.campaign import Campaign
from app.models.phone_call import PhoneCall
from app.models.booking import Booking, BookingStatus
from app.config import get_settings
from app.services.reply_analyzer import analyze_email_reply, determine_status_from_intent
from app.services.email_reply_agent import generate_ai_reply, get_conversation_history
from app.agents.outreach.channels.email import EmailOutreach
from app.services.sales_brief_generator import generate_sales_brief
from app.templates.emails.ender_notification import render_ender_notification, render_booking_block
from app.utils.calendar_links import generate_google_calendar_link
from app.services.eko_rog_notifier import (
    notify_eko_rog,
    format_booking_notification,
    format_call_notification,
)

try:
    from standardwebhooks.webhooks import Webhook as SvixWebhook, WebhookVerificationError
except ImportError:
    SvixWebhook = None
    WebhookVerificationError = Exception

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
            
            # Do NOT create Interaction records for tracking events
            # (opened, clicked, sent, delivered) — they are not conversation messages
            # and pollute the thread with empty bubbles.
    
    return {"status": "ok"}


@router.post("/calcom")
async def calcom_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Cal.com webhooks for booking events.
    
    Creates/updates local Booking records and generates AI sales briefs.
    """
    payload = await request.json()
    event_type = payload.get("triggerEvent")
    data = payload.get("payload", {})
    
    # Extract attendee email
    attendees = data.get("attendees", [])
    attendee_email = attendees[0].get("email") if attendees else None
    
    if not attendee_email:
        return {"status": "ok", "note": "no_attendee_email"}
    
    result = await db.execute(select(Lead).where(Lead.email == attendee_email))
    lead = result.scalar_one_or_none()
    
    if not lead:
        return {"status": "ok", "note": "lead_not_found"}
    
    # Record interaction
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="meeting",
        direction="inbound",
        subject=f"Meeting {event_type}",
        meta=payload,
    )
    db.add(interaction)
    
    if event_type == "BOOKING_CREATED":
        lead.status = LeadStatus.MEETING_BOOKED
        
        # Extract booking details from Cal.com payload
        cal_booking_id = data.get("bookingId") or data.get("id")
        cal_uid = data.get("uid")
        event_type_id = data.get("eventTypeId")
        title = data.get("title", f"Meeting with {lead.business_name}")
        start_time_raw = data.get("startTime")
        end_time_raw = data.get("endTime")
        location = data.get("location")
        
        # Parse ISO datetimes
        start_time = None
        end_time = None
        try:
            if start_time_raw:
                start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            if end_time_raw:
                end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
        except Exception:
            logger.exception("Failed to parse booking times")
        
        # Create local booking
        booking = Booking(
            lead_id=lead.id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            timezone="America/Denver",
            attendee_email=attendee_email,
            attendee_name=attendees[0].get("name", lead.business_name or "Unknown"),
            attendee_phone=lead.phone,
            location=location,
            location_type="video" if location and ("zoom" in location.lower() or "meet" in location.lower()) else None,
            cal_com_booking_id=cal_booking_id,
            cal_com_event_type_id=event_type_id,
            cal_com_uid=cal_uid,
            status=BookingStatus.CONFIRMED,
            meta={"calcom_payload": data},
        )
        db.add(booking)
        await db.flush()  # get booking.id
        
        # Generate AI sales brief asynchronously
        try:
            booking_context = {
                "title": title,
                "start_time": str(start_time) if start_time else None,
                "location": location,
            }
            sales_brief = await generate_sales_brief(lead, booking_context)
            booking.notes = sales_brief
            booking.meta = {**(booking.meta or {}), "sales_brief": sales_brief}
        except Exception:
            logger.exception("Failed to generate sales brief")
    
    elif event_type == "BOOKING_CANCELLED":
        cal_booking_id = data.get("bookingId") or data.get("id")
        if cal_booking_id:
            result = await db.execute(
                select(Booking).where(Booking.cal_com_booking_id == cal_booking_id)
            )
            booking = result.scalar_one_or_none()
            if booking:
                booking.status = BookingStatus.CANCELLED
                booking.cancellation_reason = "Cancelled via Cal.com"
    
    elif event_type == "BOOKING_RESCHEDULED":
        cal_booking_id = data.get("bookingId") or data.get("id")
        start_time_raw = data.get("startTime")
        end_time_raw = data.get("endTime")
        if cal_booking_id:
            result = await db.execute(
                select(Booking).where(Booking.cal_com_booking_id == cal_booking_id)
            )
            booking = result.scalar_one_or_none()
            if booking:
                try:
                    if start_time_raw:
                        booking.start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
                    if end_time_raw:
                        booking.end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
                    # If it was cancelled, set back to confirmed
                    if booking.status == BookingStatus.CANCELLED:
                        booking.status = BookingStatus.CONFIRMED
                        booking.cancellation_reason = None
                except Exception:
                    logger.exception("Failed to parse rescheduled times")
    
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
            .where(cast(Interaction.meta["vapi_call_id"], String) == vapi_call_id)
        )
        interaction = result.scalar_one_or_none()
    
    if message_type == "end-of-call-report":
        return await _handle_end_of_call(call_data, lead, interaction, db)
    elif message_type == "status-update":
        return await _handle_status_update(call_data, lead, interaction, db)
    elif message_type == "conversation-update":
        return await _handle_conversation_update(call_data, lead, interaction, db)
    elif message_type == "tool-calls":
        return await _handle_tool_calls(payload, call_data, db)

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

    # Find booking created during this call (if any)
    booking = None
    if lead:
        booking_result = await db.execute(
            select(Booking)
            .where(Booking.lead_id == lead.id)
            .order_by(Booking.created_at.desc())
            .limit(1)
        )
        booking = booking_result.scalar_one_or_none()
        # Only use if created in the last hour
        if booking and booking.created_at:
            from datetime import timedelta
            if datetime.utcnow() - booking.created_at > timedelta(hours=1):
                booking = None

    # Notify Ender
    if phone_call:
        await _notify_ender_of_call(call_data, lead, phone_call, booking)

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


async def _handle_tool_calls(payload: dict, call_data: dict, db: AsyncSession):
    """Process VAPI function tool calls (e.g. book_demo)."""
    tool_calls = payload.get("message", {}).get("toolCalls", []) or payload.get("toolCalls", [])
    if not tool_calls:
        return {"results": []}

    results = []
    customer = call_data.get("customer", {})
    customer_number = customer.get("number", "")
    customer_name = customer.get("name", "")

    # Find lead by phone
    lead = None
    if customer_number:
        result = await db.execute(select(Lead).where(Lead.phone == customer_number))
        lead = result.scalar_one_or_none()

    for tc in tool_calls:
        tc_id = tc.get("id")
        tc_type = tc.get("type")
        func = tc.get("function", {})
        func_name = func.get("name")
        args_str = func.get("arguments", "{}")

        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}

        if func_name == "book_demo":
            result_msg = await _process_book_demo_tool(
                args=args,
                lead=lead,
                customer_number=customer_number,
                customer_name=customer_name,
                db=db,
            )
            results.append({"toolCallId": tc_id, "result": result_msg})
        else:
            results.append({"toolCallId": tc_id, "result": f"Unknown function: {func_name}"})

    return {"results": results}


async def _process_book_demo_tool(
    args: dict,
    lead: Lead,
    customer_number: str,
    customer_name: str,
    db: AsyncSession,
) -> str:
    """Create a booking from VAPI book_demo tool call and notify Ender."""
    date_str = args.get("date", "")
    time_str = args.get("time", "")
    contact_method = args.get("contact_method", "phone_callback")
    caller_name = args.get("caller_name", customer_name or "Unknown")
    business_name = args.get("business_name", lead.business_name if lead else "Unknown")
    phone = args.get("phone", customer_number)
    notes = args.get("notes", "")

    # Parse datetime
    start_time = None
    end_time = None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Denver")
        start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        end_time = start_time + timedelta(minutes=15)
    except Exception as e:
        logger.warning(f"Failed to parse booking datetime: {e}")
        return f"I'm sorry, I didn't catch the date or time. Could you repeat that? You said {date_str} at {time_str}."

    # Create or update lead
    if not lead and phone:
        lead = Lead(
            business_name=business_name,
            phone=phone,
            source="manual",
            status=LeadStatus.DISCOVERED,
            notes=f"Inbound call demo request. Contact: {caller_name}",
            source_data={"inbound_source": "vapi_inbound"},
        )
        db.add(lead)
        await db.flush()
        await db.refresh(lead)

    # Create booking
    booking = Booking(
        lead_id=lead.id if lead else None,
        title=f"Demo — {business_name}",
        description=f"Demo booked via inbound call.\nMethod: {contact_method}\nNotes: {notes}",
        start_time=start_time,
        end_time=end_time,
        timezone="America/Denver",
        attendee_email=lead.email or "",
        attendee_name=caller_name,
        attendee_phone=phone,
        location="Zoom" if contact_method == "zoom" else f"Phone callback: {phone}",
        location_type="video" if contact_method == "zoom" else "phone",
        status=BookingStatus.CONFIRMED,
        meta={
            "source": "vapi_inbound",
            "contact_method": contact_method,
            "caller_name": caller_name,
            "business_name": business_name,
            "vapi_notes": notes,
        },
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)

    # Update lead status
    if lead:
        lead.status = LeadStatus.MEETING_BOOKED
        lead.last_contact_at = datetime.utcnow()

    # Create interaction
    interaction = Interaction(
        lead_id=lead.id if lead else None,
        interaction_type="call",
        direction="inbound",
        subject=f"Demo booked via voice — {business_name}",
        content=f"Date: {date_str} {time_str} MT\nMethod: {contact_method}\nNotes: {notes}",
        meta={
            "source": "vapi_tool_call",
            "tool": "book_demo",
            "booking_id": booking.id,
        },
    )
    db.add(interaction)
    await db.commit()

    # Generate Google Calendar link
    calendar_link = ""
    try:
        calendar_link = generate_google_calendar_link(
            title=f"Demo — {business_name}",
            start_time=start_time,
            end_time=end_time,
            description=f"Demo with {caller_name} from {business_name}.\nPhone: {phone}\nMethod: {contact_method}\nNotes: {notes}",
            location=booking.location or "",
            timezone="America/Denver",
        )
    except Exception:
        logger.exception("Failed to generate calendar link")

    # Notify Ender
    try:
        await _notify_ender_of_booking(
            lead=lead,
            booking=booking,
            caller_name=caller_name,
            business_name=business_name,
            phone=phone,
            contact_method=contact_method,
            notes=notes,
            calendar_link=calendar_link,
        )
    except Exception:
        logger.exception("Failed to notify Ender of booking")

    # Return message for the AI to say
    time_12h = start_time.strftime("%I:%M %p")
    date_human = start_time.strftime("%A, %B %d")
    return f"Perfect, I've booked your demo for {date_human} at {time_12h} Mountain Time. Looking forward to speaking with you!"


async def _notify_ender_of_booking(
    lead: Lead,
    booking: Booking,
    caller_name: str,
    business_name: str,
    phone: str,
    contact_method: str,
    notes: str,
    calendar_link: str,
):
    """Send Ender a rich notification email about an inbound demo booking."""
    email = EmailOutreach()
    start_fmt = booking.start_time.strftime("%Y-%m-%d %I:%M %p") if booking.start_time else "N/A"
    end_fmt = booking.end_time.strftime("%I:%M %p") if booking.end_time else "N/A"

    booking_block = render_booking_block(
        start_time=start_fmt,
        end_time=end_fmt,
        timezone="America/Denver",
        calendar_link=calendar_link or "#",
    )

    # Build a simple summary
    summary = (
        f"<strong>{caller_name}</strong> from <strong>{business_name}</strong> booked a demo via inbound call. "
        f"Phone: {phone}. Method: {contact_method}."
    )
    if notes:
        summary += f"<br/><br/>Notas adicionales: {notes}"

    pain_points = lead.pain_points if lead else []
    services = lead.services if lead else []

    body = render_ender_notification(
        business_name=business_name,
        duration="N/A (live booking)",
        interest_level="HIGH",
        language="Spanish/English",
        call_date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        summary=summary,
        transcript="[Booking created during live call — transcript available in end-of-call report]",
        recording_url="#",
        lead_url=f"{settings.FRONTEND_URL}/leads/{lead.id}" if lead else "#",
        pain_points=pain_points,
        services=services,
        booking_block=booking_block,
    )

    await email.send(
        to_email=settings.ENDER_NOTIFICATION_EMAIL,
        subject=f"📞 Demo booked — {business_name}",
        body=body,
        lead_id=lead.id if lead else None,
        business_name=business_name,
        ai_generated=False,
    )

    # Notify Eko Rog via Telegram
    try:
        rog_msg = format_booking_notification(
            business_name=business_name,
            caller_name=caller_name,
            phone=phone,
            date_str=booking.start_time.strftime("%Y-%m-%d") if booking and booking.start_time else "N/A",
            time_str=booking.start_time.strftime("%I:%M %p") if booking and booking.start_time else "N/A",
            contact_method=contact_method,
            notes=notes,
            calendar_link=calendar_link,
        )
        await notify_eko_rog(rog_msg)
    except Exception:
        logger.exception("Failed to notify Eko Rog of booking")


async def _notify_ender_of_call(
    call_data: dict,
    lead: Lead,
    phone_call: PhoneCall,
    booking: Booking = None,
):
    """Send Ender a rich notification email after an inbound call ends."""
    try:
        summary = call_data.get("summary", "")
        transcript = call_data.get("transcript", "")
        recording_url = call_data.get("recordingUrl", "")
        duration_seconds = call_data.get("durationSeconds", 0)
        duration_str = f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}"

        pain_points = lead.pain_points if lead else []
        services = lead.services if lead else []

        # Detect language from transcript
        language = "Spanish"
        if transcript:
            spanish_words = ["hola", "gracias", "por favor", "buenos", "días", "está", "cómo", "qué", "sí", "no"]
            english_words = ["hello", "thanks", "please", "good", "morning", "how", "what", "yes", "no", "thank"]
            t_lower = transcript.lower()
            spanish_count = sum(1 for w in spanish_words if w in t_lower)
            english_count = sum(1 for w in english_words if w in t_lower)
            if english_count > spanish_count:
                language = "English"
            elif spanish_count > english_count:
                language = "Spanish"
            else:
                language = "Mixed"

        booking_block = ""
        calendar_link = ""
        if booking:
            try:
                calendar_link = generate_google_calendar_link(
                    title=booking.title,
                    start_time=booking.start_time,
                    end_time=booking.end_time,
                    description=booking.description or "",
                    location=booking.location or "",
                    timezone=booking.timezone or "America/Denver",
                )
            except Exception:
                logger.exception("Failed to generate calendar link for call notification")
            start_fmt = booking.start_time.strftime("%Y-%m-%d %I:%M %p") if booking.start_time else "N/A"
            end_fmt = booking.end_time.strftime("%I:%M %p") if booking.end_time else "N/A"
            booking_block = render_booking_block(
                start_time=start_fmt,
                end_time=end_fmt,
                timezone=booking.timezone or "America/Denver",
                calendar_link=calendar_link or "#",
            )

        body = render_ender_notification(
            business_name=lead.business_name if lead else "Unknown",
            duration=duration_str,
            interest_level=phone_call.interest_level or "NONE",
            language=language,
            call_date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            summary=summary or "No summary provided.",
            transcript=transcript or "No transcript available.",
            recording_url=recording_url or "#",
            lead_url=f"{settings.FRONTEND_URL}/leads/{lead.id}" if lead else "#",
            pain_points=pain_points,
            services=services,
            booking_block=booking_block,
        )

        email = EmailOutreach()
        await email.send(
            to_email=settings.ENDER_NOTIFICATION_EMAIL,
            subject=f"📞 Inbound call — {lead.business_name if lead else 'Unknown'} ({phone_call.interest_level or 'N/A'})",
            body=body,
            lead_id=lead.id if lead else None,
            business_name=lead.business_name if lead else "Unknown",
            ai_generated=False,
        )

        # Notify Eko Rog via Telegram
        try:
            rog_msg = format_call_notification(
                business_name=lead.business_name if lead else "Unknown",
                duration=duration_str,
                interest_level=phone_call.interest_level or "NONE",
                summary=summary or "No summary provided.",
                recording_url=recording_url or "",
                lead_url=f"{settings.FRONTEND_URL}/leads/{lead.id}" if lead else "",
            )
            await notify_eko_rog(rog_msg)
        except Exception:
            logger.exception("Failed to notify Eko Rog of call")
    except Exception:
        logger.exception("Failed to send end-of-call notification to Ender")


# ---------------------------------------------------------------------------
# Resend Inbound Email Webhook
# ---------------------------------------------------------------------------

async def _verify_svix_signature(payload_bytes: bytes, svix_id: str, svix_timestamp: str, svix_signature: str) -> bool:
    """Verify Svix webhook signature (used by Resend).
    
    Uses standardwebhooks library if available, otherwise falls back to custom implementation.
    """
    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        logger.warning("RESEND_WEBHOOK_SECRET not set, skipping signature verification")
        return True
    
    # Use standardwebhooks library if available (more reliable)
    if SvixWebhook is not None:
        try:
            wh = SvixWebhook(secret)
            # Map svix-* headers to webhook-* headers expected by standardwebhooks
            headers = {
                "webhook-id": svix_id,
                "webhook-timestamp": svix_timestamp,
                "webhook-signature": svix_signature,
            }
            payload_str = payload_bytes.decode("utf-8") if isinstance(payload_bytes, bytes) else payload_bytes
            wh.verify(payload_str, headers)
            return True
        except WebhookVerificationError as e:
            logger.warning(f"Svix webhook verification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in svix verification: {e}")
            return False
    
    # Fallback to custom implementation
    try:
        if not svix_signature.startswith("v1,"):
            logger.warning(f"Invalid svix signature format: {svix_signature}")
            return False
        
        received_sig = svix_signature[3:]
        
        secret_bytes = secret.encode("utf-8")
        if secret.startswith("whsec_"):
            try:
                secret_bytes = base64.b64decode(secret[6:])
            except Exception:
                # If base64 decode fails, use the raw secret bytes
                secret_bytes = secret[6:].encode("utf-8")
        
        # Correct signed content format: "<id>.<timestamp>.<body>"
        signed_content = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + payload_bytes
        
        expected_sig = hmac.new(
            secret_bytes,
            signed_content,
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.b64encode(expected_sig).decode("utf-8")
        
        return hmac.compare_digest(expected_sig_b64, received_sig)
    except Exception as e:
        logger.error(f"Error verifying svix webhook signature: {e}")
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
    
    # Verify Svix signature (Resend uses Svix for webhooks)
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")
    
    if settings.RESEND_WEBHOOK_SECRET and svix_signature:
        if not await _verify_svix_signature(payload_bytes, svix_id, svix_timestamp, svix_signature):
            logger.warning("Invalid Svix webhook signature")
            return Response(status_code=401, content="Invalid signature")
    elif settings.RESEND_WEBHOOK_SECRET:
        logger.warning("Missing Svix signature headers")
        return Response(status_code=401, content="Missing signature")
    
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
    smtp_message_id = data.get("message_id", "")  # SMTP Message-ID for threading
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
        "smtp_message_id": smtp_message_id,
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
    
    # --- AUTO-REPLY MODE ---
    import os
    auto_reply_enabled = os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
    intent = analysis.get("intent", "")
    body_lower = body_for_analysis.lower()
    interest_keywords = ["interesa", "interesada", "interesado", "cómo funciona", "como funciona", "cuánto cuesta", "cuanto cuesta", "precio", "precios", "demo", "llamada", "reunión", "reunion", "agendar", "saber más", "me gustaría", "me gustaria"]
    has_interest_keywords = any(kw in body_lower for kw in interest_keywords)
    should_auto_reply = intent in ("interested", "needs_info") or (intent == "unclear" and has_interest_keywords)
    
    if auto_reply_enabled and should_auto_reply:
        try:
            # Refresh lead and interaction for auto-reply
            await db.refresh(lead)
            await db.refresh(interaction)
            
            # Get conversation history
            conversation = await get_conversation_history(lead.id, db, limit=10)
            
            # Generate AI reply
            reply = await generate_ai_reply(
                lead=lead,
                inbound_email=interaction,
                conversation_history=conversation,
                tone="friendly",
                max_length="medium",
            )
            
            # Send email
            email = EmailOutreach()
            smtp_msg_id = meta.get("smtp_message_id")
            response = await email.send(
                to_email=lead.email,
                subject=reply["subject"],
                body=reply["body"],
                lead_id=lead.id,
                business_name=lead.business_name,
                ai_generated=True,
                headers={"In-Reply-To": smtp_msg_id} if smtp_msg_id else None,
            )
            
            # Record outbound interaction
            outbound = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="outbound",
                subject=reply["subject"],
                content=reply["body"],
                ai_summary="Auto-generated reply",
                email_message_id=response.get("id"),
                meta={
                    "auto_replied": True,
                    "suggested_meeting": reply.get("suggested_meeting"),
                    "booking_link": reply.get("booking_link"),
                },
            )
            db.add(outbound)
            await db.commit()
            
            logger.info(f"Auto-reply sent to lead {lead.id}: {reply['subject']}")
        except Exception:
            logger.exception("Auto-reply failed")
    
    return {
        "status": "processed",
        "lead_id": lead.id,
        "interaction_id": interaction.id,
        "intent": analysis.get("intent"),
        "priority": analysis.get("priority"),
    }
