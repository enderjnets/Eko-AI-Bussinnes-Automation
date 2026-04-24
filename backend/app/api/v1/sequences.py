from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.sequence import EmailSequence, SequenceStep, SequenceEnrollment, SequenceStatus, SequenceStepType
from app.models.lead import Lead, LeadStatus
from app.schemas.sequence import (
    EmailSequenceCreate,
    EmailSequenceUpdate,
    EmailSequenceResponse,
    SequenceStepCreate,
    SequenceStepResponse,
    SequenceEnrollmentCreate,
    SequenceEnrollmentResponse,
    SequenceExecuteRequest,
)
from app.agents.outreach.channels.email import EmailOutreach
from app.services.paperclip import on_campaign_launched

router = APIRouter()


@router.get("", response_model=list[EmailSequenceResponse])
async def list_sequences(
    status: Optional[SequenceStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailSequence)
    if status:
        query = query.where(EmailSequence.status == status)
    query = query.order_by(EmailSequence.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{sequence_id}", response_model=EmailSequenceResponse)
async def get_sequence(sequence_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailSequence).where(EmailSequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return seq


@router.post("", response_model=EmailSequenceResponse, status_code=201)
async def create_sequence(data: EmailSequenceCreate, db: AsyncSession = Depends(get_db)):
    seq = EmailSequence(
        name=data.name,
        description=data.description,
        entry_criteria=data.entry_criteria,
        exit_criteria=data.exit_criteria,
    )
    db.add(seq)
    await db.commit()
    await db.refresh(seq)

    # Create steps if provided
    for step_data in (data.steps or []):
        step = SequenceStep(sequence_id=seq.id, **step_data.model_dump())
        db.add(step)

    await db.commit()
    await db.refresh(seq)
    return seq


@router.patch("/{sequence_id}", response_model=EmailSequenceResponse)
async def update_sequence(
    sequence_id: int, data: EmailSequenceUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(EmailSequence).where(EmailSequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(seq, field, value)

    await db.commit()
    await db.refresh(seq)
    return seq


@router.post("/{sequence_id}/steps", response_model=SequenceStepResponse, status_code=201)
async def add_sequence_step(
    sequence_id: int, data: SequenceStepCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(EmailSequence).where(EmailSequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    step = SequenceStep(sequence_id=sequence_id, **data.model_dump())
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


@router.delete("/{sequence_id}/steps/{step_id}", status_code=204)
async def delete_sequence_step(
    sequence_id: int, step_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SequenceStep).where(
            SequenceStep.id == step_id,
            SequenceStep.sequence_id == sequence_id,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    await db.delete(step)
    await db.commit()
    return None


@router.post("/{sequence_id}/enroll", response_model=SequenceEnrollmentResponse)
async def enroll_leads(
    sequence_id: int,
    lead_ids: List[int],
    db: AsyncSession = Depends(get_db),
):
    """Enroll leads into a sequence."""
    result = await db.execute(select(EmailSequence).where(EmailSequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    if seq.status != SequenceStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Sequence is not active")

    enrollments = []
    for lead_id in lead_ids:
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            continue

        # Check if already enrolled
        existing = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.sequence_id == sequence_id,
                SequenceEnrollment.lead_id == lead_id,
                SequenceEnrollment.status.in_(["active", "paused"]),
            )
        )
        if existing.scalar_one_or_none():
            continue

        enrollment = SequenceEnrollment(
            sequence_id=sequence_id,
            lead_id=lead_id,
            status="active",
            current_step_position=0,
            next_step_at=datetime.utcnow(),
        )
        db.add(enrollment)
        enrollments.append(enrollment)

    seq.leads_entered += len(enrollments)
    await db.commit()

    for enrollment in enrollments:
        await db.refresh(enrollment)

    return enrollments[0] if enrollments else None


@router.post("/{sequence_id}/execute")
async def execute_sequence(
    sequence_id: int,
    request: SequenceExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute the next step of a sequence for enrolled leads."""
    result = await db.execute(select(EmailSequence).where(EmailSequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Get active enrollments for the requested leads
    enrollments_result = await db.execute(
        select(SequenceEnrollment)
        .where(SequenceEnrollment.sequence_id == sequence_id)
        .where(SequenceEnrollment.lead_id.in_(request.lead_ids))
        .where(SequenceEnrollment.status == "active")
        .where(
            (SequenceEnrollment.next_step_at == None) |
            (SequenceEnrollment.next_step_at <= datetime.utcnow())
        )
    )
    enrollments = enrollments_result.scalars().all()

    if not enrollments:
        return {"executed": 0, "message": "No enrollments ready for next step"}

    # Get steps ordered
    steps_result = await db.execute(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.position)
    )
    steps = steps_result.scalars().all()

    if not steps:
        return {"executed": 0, "message": "Sequence has no steps"}

    email = EmailOutreach()
    executed = 0
    results = []

    for enrollment in enrollments:
        lead_result = await db.execute(select(Lead).where(Lead.id == enrollment.lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead or lead.do_not_contact:
            enrollment.status = "exited"
            await db.commit()
            continue

        # Find current step
        current_step = None
        for step in steps:
            if step.position >= enrollment.current_step_position:
                current_step = step
                break

        if not current_step:
            # Sequence completed
            enrollment.status = "completed"
            enrollment.completed_at = datetime.utcnow()
            seq.leads_completed += 1
            await db.commit()
            continue

        if request.dry_run:
            results.append({
                "lead_id": lead.id,
                "step": current_step.name,
                "would_send": True,
            })
            executed += 1
            continue

        try:
            if current_step.step_type == SequenceStepType.EMAIL:
                template_key = current_step.template_key or "initial_outreach"
                if current_step.ai_generate:
                    response = await email.generate_and_send(
                        lead=lead,
                        template_key=template_key,
                    )
                else:
                    subject = current_step.subject_template or "Hello"
                    body = current_step.body_template or "<p>Hello</p>"
                    response = await email.send(
                        to_email=lead.email,
                        subject=subject,
                        body=body,
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        ai_generated=False,
                    )

                # Update lead status if first contact
                if lead.status in [LeadStatus.DISCOVERED, LeadStatus.ENRICHED, LeadStatus.SCORED]:
                    lead.status = LeadStatus.CONTACTED
                    lead.last_contact_at = datetime.utcnow()

                executed += 1
                results.append({
                    "lead_id": lead.id,
                    "step": current_step.name,
                    "status": "sent",
                    "message_id": response.get("id"),
                })

            elif current_step.step_type == SequenceStepType.WAIT:
                # Just schedule next step
                results.append({
                    "lead_id": lead.id,
                    "step": current_step.name,
                    "status": "waiting",
                    "delay_hours": current_step.delay_hours,
                })

            # Advance to next step
            enrollment.current_step_position = current_step.position + 1
            next_step = None
            for step in steps:
                if step.position > current_step.position:
                    next_step = step
                    break

            if next_step and next_step.step_type == SequenceStepType.WAIT:
                enrollment.next_step_at = datetime.utcnow() + timedelta(hours=next_step.delay_hours or 24)
            elif next_step:
                enrollment.next_step_at = datetime.utcnow()
            else:
                enrollment.status = "completed"
                enrollment.completed_at = datetime.utcnow()
                seq.leads_completed += 1

            await db.commit()

        except Exception as e:
            results.append({
                "lead_id": lead.id,
                "step": current_step.name,
                "status": "error",
                "error": str(e),
            })

    return {
        "executed": executed,
        "total_enrollments": len(enrollments),
        "results": results,
    }
