"""Stripe Checkout integration for Eko AI subscriptions."""

import logging
from typing import Optional
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead
from app.models.payment import Payment, PaymentStatus, PaymentType
from app.models.deal import Deal, DealStatus
from app.config import get_settings

settings = get_settings()
router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

STRIPE_PLAN_PRICE_MAP = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "growth": settings.STRIPE_PRICE_GROWTH,
    "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
}

PLAN_NAMES = {
    "starter": "Eko AI Starter",
    "growth": "Eko AI Growth",
    "enterprise": "Eko AI Enterprise",
}

SETUP_FEE_CENTS = 49900


class CheckoutSessionRequest(BaseModel):
    lead_id: int
    plan: str  # starter, growth, enterprise
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalSessionRequest(BaseModel):
    lead_id: int
    return_url: Optional[str] = None


class PortalSessionResponse(BaseModel):
    portal_url: str


@router.post("/session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for subscription + setup fee."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    price_id = STRIPE_PLAN_PRICE_MAP.get(request.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Invalid plan or Stripe price not configured: {request.plan}")

    # Get lead
    result = await db.execute(select(Lead).where(Lead.id == request.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email")

    # Find or create Stripe Customer
    customer_id = lead.stripe_customer_id
    if not customer_id:
        try:
            customer = stripe.Customer.create(
                email=lead.email,
                name=lead.business_name or lead.name,
                metadata={"lead_id": str(lead.id), "business_name": lead.business_name or ""},
            )
            customer_id = customer.id
            lead.stripe_customer_id = customer_id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Setup Fee"},
                        "unit_amount": SETUP_FEE_CENTS,
                    },
                    "quantity": 1,
                },
            ],
            subscription_data={
                "metadata": {
                    "lead_id": str(lead.id),
                    "plan": request.plan,
                    "business_name": lead.business_name or "",
                },
            },
            success_url=request.success_url or f"{settings.FRONTEND_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url or f"{settings.FRONTEND_URL}/checkout/cancel",
            metadata={
                "lead_id": str(lead.id),
                "plan": request.plan,
                "business_name": lead.business_name or "",
                "type": "subscription_signup",
            },
        )

        # Record payment intent (setup fee portion tracked in webhook)
        payment = Payment(
            lead_id=lead.id,
            stripe_checkout_session_id=session.id,
            stripe_customer_id=customer_id,
            amount_cents=SETUP_FEE_CENTS,  # will be updated by webhook with actual total
            currency="usd",
            plan_name=request.plan,
            payment_type=PaymentType.SETUP,
            status=PaymentStatus.PENDING,
            meta={
                "plan_name": PLAN_NAMES.get(request.plan, request.plan),
                "stripe_price_id": price_id,
                "setup_cents": SETUP_FEE_CENTS,
            },
        )
        db.add(payment)
        await db.commit()

        return CheckoutSessionResponse(checkout_url=session.url, session_id=session.id)

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(
    request: PortalSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for a lead to manage their subscription."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    result = await db.execute(select(Lead).where(Lead.id == request.lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Lead has no Stripe customer")

    try:
        session = stripe.billing_portal.Session.create(
            customer=lead.stripe_customer_id,
            return_url=request.return_url or f"{settings.FRONTEND_URL}/billing",
        )
        return PortalSessionResponse(portal_url=session.url)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_checkout_session(session_id: str):
    """Retrieve a Stripe Checkout Session status."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "id": session.id,
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total,
            "customer_email": session.customer_email,
            "customer": session.customer,
            "subscription": session.subscription,
            "metadata": session.metadata,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/billing/{lead_id}")
async def get_billing_info(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Get billing info for a lead — plan, subscription status, payment history."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Fetch payments
    from app.models.payment import Payment
    payments_result = await db.execute(
        select(Payment)
        .where(Payment.lead_id == lead_id)
        .order_by(Payment.created_at.desc())
    )
    payments = payments_result.scalars().all()

    # Fetch subscription from Stripe if customer exists
    subscription_info = None
    if lead.stripe_customer_id and settings.STRIPE_SECRET_KEY:
        try:
            subs = stripe.Subscription.list(
                customer=lead.stripe_customer_id,
                status="all",
                limit=1,
            )
            if subs.data:
                sub = subs.data[0]
                subscription_info = {
                    "id": sub.id,
                    "status": sub.status,
                    "current_period_start": sub.current_period_start,
                    "current_period_end": sub.current_period_end,
                    "cancel_at_period_end": sub.cancel_at_period_end,
                    "plan": sub.plan.nickname if sub.plan else None,
                }
        except stripe.error.StripeError as e:
            logger.warning(f"Stripe error fetching subscription: {e}")

    return {
        "lead_id": lead.id,
        "business_name": lead.business_name,
        "email": lead.email,
        "plan": lead.payment_plan,
        "subscription_status": lead.subscription_status,
        "stripe_customer_id": lead.stripe_customer_id,
        "payments": [
            {
                "id": p.id,
                "type": p.payment_type.value if p.payment_type else None,
                "status": p.status.value if p.status else None,
                "amount_cents": p.amount_cents,
                "currency": p.currency,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "billing_period_start": p.billing_period_start.isoformat() if p.billing_period_start else None,
                "billing_period_end": p.billing_period_end.isoformat() if p.billing_period_end else None,
                "receipt_url": p.receipt_url,
                "meta": p.meta,
            }
            for p in payments
        ],
        "subscription": subscription_info,
    }


# ---------------------------------------------------------------------------
# Stripe Product/Price Seed (admin only — run once per environment)
# ---------------------------------------------------------------------------

@router.post("/seed-stripe")
async def seed_stripe_products():
    """Create Eko AI Products and recurring Prices in Stripe. Idempotent — safe to run multiple times.
    
    Returns the Price IDs to save in your .env as STRIPE_PRICE_STARTER/GROWTH/ENTERPRISE.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    plans = [
        {
            "key": "starter",
            "name": "Eko AI Starter",
            "description": "1 Agente IA personalizado, horario comercial, soporte por email.",
            "monthly_cents": 19900,
        },
        {
            "key": "growth",
            "name": "Eko AI Growth",
            "description": "2 Agentes IA, horario extendido, soporte prioritario, dashboard analytics.",
            "monthly_cents": 29900,
        },
        {
            "key": "enterprise",
            "name": "Eko AI Enterprise",
            "description": "Agentes IA ilimitados, 24/7, soporte dedicado, API access.",
            "monthly_cents": 39900,
        },
    ]

    results = []
    for plan in plans:
        try:
            # Search existing product by name to avoid duplicates
            existing_products = stripe.Product.search(
                query=f'name:"{plan["name"]}"',
                limit=1,
            )

            if existing_products.data:
                product = existing_products.data[0]
                logger.info(f"Product '{plan['name']}' already exists: {product.id}")
            else:
                product = stripe.Product.create(
                    name=plan["name"],
                    description=plan["description"],
                    metadata={"plan_key": plan["key"], "source": "eko_ai_seed"},
                )
                logger.info(f"Created product '{plan['name']}': {product.id}")

            # Search existing recurring price for this product
            existing_prices = stripe.Price.list(
                product=product.id,
                type="recurring",
                limit=1,
            )

            if existing_prices.data:
                price = existing_prices.data[0]
                logger.info(f"Price for '{plan['name']}' already exists: {price.id}")
            else:
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=plan["monthly_cents"],
                    currency="usd",
                    recurring={"interval": "month", "interval_count": 1},
                    metadata={"plan_key": plan["key"], "source": "eko_ai_seed"},
                )
                logger.info(f"Created price for '{plan['name']}': {price.id}")

            results.append({
                "plan": plan["key"],
                "product_id": product.id,
                "price_id": price.id,
                "amount_cents": plan["monthly_cents"],
                "status": "ok",
            })

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error seeding {plan['key']}: {e}")
            results.append({
                "plan": plan["key"],
                "error": str(e),
                "status": "error",
            })

    # Build env snippet
    env_snippet = "\n".join(
        f"STRIPE_PRICE_{r['plan'].upper()}={r.get('price_id', '')}"
        for r in results if r["status"] == "ok"
    )

    return {
        "results": results,
        "env_snippet": env_snippet,
        "note": "Copy the env_snippet above into your .env file and restart the backend.",
    }
