from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.booking import Booking, BookingStatus
from app.models.lead import Lead, LeadStatus
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    AvailabilityRequest,
    BookingLinkRequest,
)
from app.services.cal_com import CalComClient
from app.agents.outreach.channels.email import EmailOutreach
from app.core.security import get_current_user
from app.services.paperclip import on_lead_status_change

router = APIRouter()


@router.get("/event-types")
async def get_event_types(
    current_user: User = Depends(get_current_user),
):
    """Get available Cal.com event types (meeting types)."""
    client = CalComClient()
    try:
        event_types = await client.get_event_types()
        return {"event_types": event_types}
    finally:
        await client.close()


@router.post("/availability")
async def get_availability(
    request: AvailabilityRequest,
    current_user: User = Depends(get_current_user),
):
    """Get available time slots for an event type."""
    client = CalComClient()
    try:
        slots = await client.get_available_slots(
            event_type_id=request.event_type_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"slots": slots}
    finally:
        await client.close()


@router.get("/bookings", response_model=list[BookingResponse])
async def list_bookings(
    status: Optional[BookingStatus] = None,
    lead_id: Optional[int] = None,
    upcoming: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List bookings with optional filtering."""
    query = select(Booking)

    if status:
        query = query.where(Booking.status == status)
    if lead_id:
        query = query.where(Booking.lead_id == lead_id)
    if upcoming:
        now = datetime.utcnow()
        query = query.where(
            and_(Booking.start_time >= now, Booking.status.not_in([BookingStatus.CANCELLED, BookingStatus.NO_SHOW]))
        )

    # Non-admin users only see bookings for their leads
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.join(Lead).where(
            (Lead.owner_id == current_user.id) | (Lead.assigned_to == current_user.email)
        )

    query = query.order_by(Booking.start_time.asc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single booking."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(
    data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a booking for a lead.
    If event_type_id is provided, syncs with Cal.com.
    """
    # Get lead
    result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Validate access
    if not current_user.is_superuser and current_user.role.value != "admin":
        if lead.owner_id != current_user.id and lead.assigned_to != current_user.email:
            raise HTTPException(status_code=403, detail="Not authorized for this lead")

    # Create local booking
    booking = Booking(
        lead_id=data.lead_id,
        title=data.title or f"Meeting with {lead.business_name}",
        start_time=data.start_time,
        end_time=data.start_time + timedelta(minutes=30),  # Default 30 min
        attendee_email=lead.email or "",
        attendee_name=lead.business_name or "Unknown",
        attendee_phone=lead.phone,
        location_type=data.location_type or "video",
        notes=data.notes,
        status=BookingStatus.PENDING,
    )

    # If Cal.com integration is configured, create remote booking
    if data.event_type_id and lead.email:
        client = CalComClient()
        try:
            cal_result = await client.create_booking(
                event_type_id=data.event_type_id,
                start_time=data.start_time.isoformat(),
                attendee_email=lead.email,
                attendee_name=lead.business_name or "Unknown",
                metadata={"lead_id": lead.id, "source": "eko_ai"},
            )
            if "error" not in cal_result:
                booking.cal_com_booking_id = cal_result.get("id")
                booking.cal_com_event_type_id = data.event_type_id
                booking.cal_com_uid = cal_result.get("uid")
                booking.status = BookingStatus.CONFIRMED
                if cal_result.get("location"):
                    booking.location = cal_result.get("location")
        finally:
            await client.close()

    db.add(booking)

    # Update lead status
    old_status = lead.status.value
    lead.status = LeadStatus.MEETING_BOOKED

    # Record interaction
    from app.models.lead import Interaction
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="meeting",
        direction="outbound",
        subject=f"Meeting scheduled: {booking.title}",
        content=data.notes or "Meeting booked via calendar",
        metadata={"booking_id": booking.id, "start_time": booking.start_time.isoformat()},
    )
    db.add(interaction)

    await db.commit()
    await db.refresh(booking)

    # Paperclip
    try:
        on_lead_status_change(
            lead_id=lead.id,
            business_name=lead.business_name,
            old_status=old_status,
            new_status="meeting_booked",
        )
    except Exception:
        pass

    return booking


@router.patch("/bookings/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a booking (status, notes, etc)."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(booking, field, value)

    await db.commit()
    await db.refresh(booking)
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: int,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a booking locally and on Cal.com if applicable."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Cancel on Cal.com if we have a booking ID
    if booking.cal_com_booking_id:
        client = CalComClient()
        try:
            await client.cancel_booking(
                booking_id=booking.cal_com_booking_id,
                reason=reason or "Cancelled by user",
            )
        finally:
            await client.close()

    booking.status = BookingStatus.CANCELLED
    booking.cancellation_reason = reason or "Cancelled"
    await db.commit()
    await db.refresh(booking)
    return booking


@router.post("/send-link")
async def send_booking_link(
    data: BookingLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a Cal.com booking link to a lead via email."""
    result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked as do-not-contact")

    # Build booking link
    # In a real implementation, this would be fetched from Cal.com or configured
    booking_link = f"https://cal.com/eko-ai/demo?email={lead.email}&name={lead.business_name}"

    email = EmailOutreach()
    subject = f"Let's schedule a quick call — {lead.business_name}"
    body = f"""
<p>Hi there,</p>
<p>I'd love to show you how Eko AI can help {lead.business_name} with AI voice agents and automation.</p>
<p><a href="{booking_link}" style="display:inline-block;padding:12px 24px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:6px;">Book a 15-min call</a></p>
<p>Or reply to this email if you prefer a different time.</p>
<p>Best,<br>Eko AI Team</p>
"""

    response = await email.send(
        to_email=lead.email,
        subject=subject,
        body=body,
        lead_id=lead.id,
        business_name=lead.business_name,
        ai_generated=False,
        tags=["booking_link"],
    )

    # Record interaction
    from app.models.lead import Interaction
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="email",
        direction="outbound",
        subject=subject,
        content="Booking link sent",
        email_status="sent",
        email_message_id=response.get("id"),
        metadata={"booking_link": booking_link, "event_type_id": data.event_type_id},
    )
    db.add(interaction)
    await db.commit()

    return {
        "status": "sent",
        "message_id": response.get("id"),
        "booking_link": booking_link,
    }
