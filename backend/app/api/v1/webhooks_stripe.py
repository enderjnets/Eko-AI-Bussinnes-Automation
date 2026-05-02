"""Stripe webhook handler."""

import json
import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus
from app.models.deal import Deal, DealStatus
from app.models.payment import Payment, PaymentStatus
from app.agents.outreach.channels.email import EmailOutreach
from app.config import get_settings

settings = get_settings()
router = APIRouter()
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping verification")
        # In dev, allow unverified payloads for testing
        try:
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info(f"Stripe webhook: {event_type} — {data.get('id', 'no-id')}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)
    elif event_type == "checkout.session.expired":
        await _handle_checkout_expired(data, db)
    elif event_type == "charge.refunded":
        await _handle_refund(data, db)
    else:
        logger.info(f"Unhandled Stripe event: {event_type}")

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict, db: AsyncSession):
    """Process successful checkout — activate customer + send onboarding email."""
    metadata = session.get("metadata", {})
    lead_id = int(metadata.get("lead_id", 0))
    plan = metadata.get("plan", "unknown")
    session_id = session.get("id")

    if not lead_id:
        logger.error("No lead_id in session metadata")
        return

    # Find or create payment record
    result = await db.execute(
        select(Payment).where(Payment.stripe_checkout_session_id == session_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        # Create payment record if not found
        payment = Payment(
            lead_id=lead_id,
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=session.get("payment_intent"),
            amount_cents=session.get("amount_total", 0),
            currency=session.get("currency", "usd"),
            plan_name=plan,
            status=PaymentStatus.COMPLETED,
            meta={
                "customer_email": session.get("customer_email"),
                "plan": plan,
                "session_data": {
                    "customer": session.get("customer"),
                    "amount_total": session.get("amount_total"),
                },
            },
        )
        db.add(payment)
    else:
        payment.status = PaymentStatus.COMPLETED
        payment.stripe_payment_intent_id = session.get("payment_intent")
        payment.completed_at = datetime.utcnow()

    # Update lead to ACTIVE
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead:
        lead.status = LeadStatus.ACTIVE
        lead.payment_plan = plan
        lead.subscription_status = "active"
        # Update source_data to record payment
        if lead.source_data is None:
            lead.source_data = {}
        lead.source_data["payment"] = {
            "plan": plan,
            "paid_at": datetime.utcnow().isoformat(),
            "amount_cents": session.get("amount_total"),
            "session_id": session_id,
        }

        # Update deal to CLOSED_WON
        deal_result = await db.execute(
            select(Deal).where(Deal.lead_id == lead.id).order_by(Deal.created_at.desc())
        )
        deal = deal_result.scalar_one_or_none()
        if deal:
            deal.status = DealStatus.CLOSED_WON
            deal.value = (session.get("amount_total", 0)) / 100.0
            deal.actual_revenue = deal.value
            if deal.meta is None:
                deal.meta = {}
            deal.meta["paid_at"] = datetime.utcnow().isoformat()
            deal.meta["plan"] = plan

        # Send onboarding welcome email
        try:
            await _send_onboarding_email(lead)
        except Exception as e:
            logger.error(f"Failed to send onboarding email: {e}")

    await db.commit()
    logger.info(f"Lead {lead_id} activated — plan: {plan}")


async def _handle_checkout_expired(session: dict, db: AsyncSession):
    """Mark payment as abandoned."""
    session_id = session.get("id")
    result = await db.execute(
        select(Payment).where(Payment.stripe_checkout_session_id == session_id)
    )
    payment = result.scalar_one_or_none()
    if payment and payment.status == PaymentStatus.PENDING:
        payment.status = PaymentStatus.ABANDONED
        await db.commit()
        logger.info(f"Payment {payment.id} marked abandoned")


async def _handle_refund(charge: dict, db: AsyncSession):
    """Process refund."""
    payment_intent = charge.get("payment_intent")
    if not payment_intent:
        return

    result = await db.execute(
        select(Payment).where(Payment.stripe_payment_intent_id == payment_intent)
    )
    payment = result.scalar_one_or_none()
    if payment:
        payment.status = PaymentStatus.REFUNDED
        if payment.meta is None:
            payment.meta = {}
        payment.meta["refunded_at"] = datetime.utcnow().isoformat()
        payment.meta["refund_amount_cents"] = charge.get("amount_refunded", 0)
        await db.commit()
        logger.info(f"Payment {payment.id} marked refunded")


async def _send_onboarding_email(lead: Lead):
    """Send welcome onboarding email to new customer."""
    email = EmailOutreach()

    context = f"""
    El cliente {lead.business_name or lead.name} acaba de completar el pago para Eko AI.
    Plan contratado: {lead.payment_plan or 'Starter'}.
    Mensaje a enviar: Bienvenida como cliente, próximos pasos del onboarding,
    link al portal de cliente, y contacto directo con el equipo de implementación.
    """

    await email.generate_and_send(
        lead=lead,
        template_key="welcome_onboarding",
        campaign_context=context,
    )

    logger.info(f"Onboarding email sent to {lead.email}")
