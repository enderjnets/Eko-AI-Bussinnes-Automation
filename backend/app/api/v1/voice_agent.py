from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, Interaction
from app.models.phone_call import PhoneCall
from app.models.user import User
from app.core.security import get_current_user
from app.services.vapi_client import (
    create_call,
    get_call,
    list_calls,
    create_assistant,
    update_assistant,
    build_sales_assistant_prompt,
)
from app.config import get_settings

router = APIRouter()
settings = get_settings()


class StartCallRequest(BaseModel):
    lead_id: int
    assistant_id: Optional[str] = None
    first_message: Optional[str] = None
    custom_instructions: Optional[str] = None
    schedule_now: bool = True


class CreateAssistantRequest(BaseModel):
    name: str
    system_prompt: Optional[str] = None
    first_message: str = "Hola, ¿cómo estás? Te llamo de Eko AI."
    voice_provider: str = "11labs"
    voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    model: str = "gpt-4o"


class UpdateAssistantRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    voice_id: Optional[str] = None


@router.post("/calls")
async def start_voice_call(
    data: StartCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start an outbound voice call to a lead via VAPI."""
    result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.phone:
        raise HTTPException(status_code=400, detail="Lead has no phone number")
    
    if lead.do_not_contact:
        raise HTTPException(status_code=400, detail="Lead is marked as do-not-contact")
    
    # Build custom variables for assistant context
    custom_vars = {
        "business_name": lead.business_name,
        "category": lead.category or "",
        "city": lead.city or "",
        "lead_name": lead.business_name,
    }
    
    # Build first message if not provided
    first_message = data.first_message
    if not first_message:
        first_message = f"Hola, ¿me comunico con {lead.business_name}? Te llamo de Eko AI."
    
    # Override system prompt if custom instructions provided
    assistant_id = data.assistant_id
    if data.custom_instructions and not assistant_id:
        # Create a temporary assistant with custom prompt
        prompt = build_sales_assistant_prompt() + "\n\nINSTRUCCIONES ADICIONALES:\n" + data.custom_instructions
        assistant = await create_assistant(
            name=f"Eko AI - {lead.business_name}",
            system_prompt=prompt,
            first_message=first_message,
        )
        if "error" in assistant:
            raise HTTPException(status_code=500, detail=assistant["error"])
        assistant_id = assistant.get("id")
    
    # Start the call via VAPI
    vapi_response = await create_call(
        phone_number=lead.phone,
        assistant_id=assistant_id,
        lead_id=lead.id,
        name=lead.business_name,
        first_message=first_message if not assistant_id else None,
        custom_variables=custom_vars,
    )
    
    if "error" in vapi_response:
        raise HTTPException(status_code=500, detail=vapi_response["error"])
    
    # Create phone call record
    phone_call = PhoneCall(
        lead_id=lead.id,
        result="SCHEDULED" if not data.schedule_now else "INITIATED",
        notes=f"VAPI call initiated. Assistant: {assistant_id or 'default'}",
        scheduled_at=None if data.schedule_now else None,
    )
    db.add(phone_call)
    
    # Create interaction record
    interaction = Interaction(
        lead_id=lead.id,
        interaction_type="call",
        direction="outbound",
        subject=f"Voice call to {lead.business_name}",
        meta={
            "vapi_call_id": vapi_response.get("id"),
            "vapi_assistant_id": assistant_id,
            "initiated_by": current_user.id,
            "status": "initiated",
        },
    )
    db.add(interaction)
    
    # Update lead
    lead.last_contact_at = __import__("datetime").datetime.utcnow()
    lead.call_attempts = (lead.call_attempts or 0) + 1
    
    await db.commit()
    await db.refresh(phone_call)
    
    return {
        "status": "initiated",
        "phone_call_id": phone_call.id,
        "vapi_call_id": vapi_response.get("id"),
        "lead_id": lead.id,
        "lead_name": lead.business_name,
        "phone": lead.phone,
        "assistant_id": assistant_id,
    }


@router.get("/calls")
async def list_voice_calls(
    lead_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List voice calls with filters."""
    query = select(PhoneCall).order_by(desc(PhoneCall.created_at))
    
    if lead_id:
        query = query.where(PhoneCall.lead_id == lead_id)
    if status:
        query = query.where(PhoneCall.result == status)
    
    total_result = await db.execute(query)
    total = len(total_result.scalars().all())
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    calls = result.scalars().all()
    
    # Enrich with lead info
    enriched = []
    for call in calls:
        lead_result = await db.execute(select(Lead).where(Lead.id == call.lead_id))
        lead = lead_result.scalar_one_or_none()
        enriched.append({
            "id": call.id,
            "lead_id": call.lead_id,
            "lead_name": lead.business_name if lead else None,
            "lead_phone": lead.phone if lead else None,
            "result": call.result,
            "notes": call.notes,
            "interest_level": call.interest_level,
            "next_action": call.next_action,
            "call_duration_seconds": call.call_duration_seconds,
            "scheduled_at": call.scheduled_at.isoformat() if call.scheduled_at else None,
            "completed_at": call.completed_at.isoformat() if call.completed_at else None,
            "created_at": call.created_at.isoformat() if call.created_at else None,
        })
    
    return {"items": enriched, "total": total}


@router.get("/calls/{call_id}")
async def get_voice_call(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific voice call record."""
    result = await db.execute(select(PhoneCall).where(PhoneCall.id == call_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    lead_result = await db.execute(select(Lead).where(Lead.id == call.lead_id))
    lead = lead_result.scalar_one_or_none()
    
    # Get related VAPI call details if available
    vapi_details = None
    interaction_result = await db.execute(
        select(Interaction)
        .where(Interaction.lead_id == call.lead_id)
        .where(Interaction.interaction_type == "call")
        .order_by(desc(Interaction.created_at))
        .limit(1)
    )
    interaction = interaction_result.scalar_one_or_none()
    if interaction and interaction.meta:
        vapi_call_id = interaction.meta.get("vapi_call_id")
        if vapi_call_id:
            vapi_details = await get_call(vapi_call_id)
    
    return {
        "id": call.id,
        "lead_id": call.lead_id,
        "lead_name": lead.business_name if lead else None,
        "lead_phone": lead.phone if lead else None,
        "result": call.result,
        "notes": call.notes,
        "interest_level": call.interest_level,
        "next_action": call.next_action,
        "call_duration_seconds": call.call_duration_seconds,
        "scheduled_at": call.scheduled_at.isoformat() if call.scheduled_at else None,
        "completed_at": call.completed_at.isoformat() if call.completed_at else None,
        "created_at": call.created_at.isoformat() if call.created_at else None,
        "vapi_details": vapi_details,
    }


@router.post("/assistants")
async def create_voice_assistant(
    data: CreateAssistantRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new VAPI voice assistant."""
    system_prompt = data.system_prompt or build_sales_assistant_prompt()
    
    result = await create_assistant(
        name=data.name,
        system_prompt=system_prompt,
        first_message=data.first_message,
        voice_provider=data.voice_provider,
        voice_id=data.voice_id,
        model=data.model,
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "status": "created",
        "assistant": result,
    }


@router.patch("/assistants/{assistant_id}")
async def update_voice_assistant(
    assistant_id: str,
    data: UpdateAssistantRequest,
    current_user: User = Depends(get_current_user),
):
    """Update an existing VAPI voice assistant."""
    updates = {}
    if data.name:
        updates["name"] = data.name
    if data.system_prompt:
        updates["model"] = {"systemPrompt": data.system_prompt}
    if data.first_message:
        updates["firstMessage"] = data.first_message
    if data.voice_id:
        updates["voice"] = {"voiceId": data.voice_id}
    
    result = await update_assistant(assistant_id, updates)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "status": "updated",
        "assistant": result,
    }


@router.get("/config")
async def get_voice_config(
    current_user: User = Depends(get_current_user),
):
    """Get current VAPI configuration status."""
    api_key = settings.VAPI_API_KEY or ""
    return {
        "configured": bool(api_key),
        "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else None,
    }
