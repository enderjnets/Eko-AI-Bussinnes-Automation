import logging
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select, func, delete, update, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.landing_page import LandingPage
from app.models.landing_page_visit import LandingPageVisit
from app.models.lead import Lead, LeadSource, Interaction
from app.models.user import User
from app.models.booking import Booking
from app.models.deal import Deal
from app.models.phone_call import PhoneCall
from app.models.setting import AppSetting
from app.schemas.landing_page import (
    LandingPageCreate,
    LandingPageUpdate,
    LandingPageResponse,
    LandingPageListResponse,
    LandingPageGenerateRequest,
    LandingPageAnalyticsResponse,
    LandingPageAnalytics,
)
from app.services.landing_page_generator import LandingPageGenerator
from app.core.security import get_current_user, get_current_user_optional
from app.services.tenant_context import get_tenant_context_optional, TenantContext

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_session_id(request: Request) -> str:
    """Extract or create a session ID from request cookies/headers."""
    sid = request.cookies.get("eko_sid")
    if not sid:
        sid = str(uuid.uuid4())
    return sid


def _hash_ip(ip: str) -> str:
    """Hash IP address for privacy."""
    return hashlib.sha256(ip.encode()).hexdigest()


async def _track_visit(
    db: AsyncSession,
    landing_page_id: int,
    session_id: str,
    ip_hash: Optional[str],
    user_agent: Optional[str],
    referrer: Optional[str],
):
    """Background task: record a visit."""
    try:
        visit = LandingPageVisit(
            landing_page_id=landing_page_id,
            session_id=session_id,
            ip_hash=ip_hash,
            user_agent=user_agent,
            referrer=referrer,
        )
        db.add(visit)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to track visit: {e}")
        await db.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Public + utility routes (NO auth, MUST be declared before /{landing_page_id}
# so FastAPI's order-sensitive routing doesn't shadow them).
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/track")
async def track_visit(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    *,
    lp_id: int = Query(..., alias="lp_id"),
    sid: Optional[str] = Query(None, alias="sid"),
):
    """Tracking pixel — returns a 1x1 transparent GIF."""
    if not sid:
        sid = _get_session_id(request)

    ip = request.client.host if request.client else ""
    background_tasks.add_task(
        _track_visit,
        db,
        lp_id,
        sid,
        _hash_ip(ip) if ip else None,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )

    # 1x1 transparent GIF
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif, media_type="image/gif")


@router.get("/random")
async def serve_random_landing_page(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to a random landing page from the pool."""
    result = await db.execute(
        select(LandingPage)
        .where(LandingPage.is_random_pool == True)
        .order_by(func.random())
        .limit(1)
    )
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="No landing pages in random pool")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/lp/{lp.slug}")


@router.get("/public/active", response_class=HTMLResponse)
async def serve_active_landing_page(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Serve the currently active landing page."""
    result = await db.execute(
        select(LandingPage).where(LandingPage.is_active == True).limit(1)
    )
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="No active landing page found")

    sid = _get_session_id(request)
    ip = request.client.host if request.client else ""
    background_tasks.add_task(
        _track_visit,
        db,
        lp.id,
        sid,
        _hash_ip(ip) if ip else None,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )

    html = lp.html_content.replace("{landing_page_id}", str(lp.id))
    return HTMLResponse(content=html)


@router.get("/public/{slug}", response_class=HTMLResponse)
async def serve_public_landing_page(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Serve a public landing page by slug."""
    result = await db.execute(select(LandingPage).where(LandingPage.slug == slug))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    # Track visit in background
    sid = _get_session_id(request)
    ip = request.client.host if request.client else ""
    background_tasks.add_task(
        _track_visit,
        db,
        lp.id,
        sid,
        _hash_ip(ip) if ip else None,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )

    # Inject landing_page_id into tracking pixel and hidden form field
    html = lp.html_content
    html = html.replace("{landing_page_id}", str(lp.id))

    return HTMLResponse(content=html)


# ─────────────────────────────────────────────────────────────────────────────
# Admin endpoints (auth required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=LandingPageListResponse)
async def list_landing_pages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Optional[TenantContext] = Depends(get_tenant_context_optional),
):
    """List all landing pages for the current workspace."""
    query = select(LandingPage)
    if tenant and tenant.workspace_id:
        query = query.where(
            or_(
                LandingPage.workspace_id == tenant.workspace_id,
                LandingPage.workspace_id.is_(None),
            )
        )
    query = query.order_by(desc(LandingPage.created_at))
    result = await db.execute(query)
    items = result.scalars().all()
    return LandingPageListResponse(items=items, total=len(items))


@router.get("/compare")
async def compare_landing_pages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Optional[TenantContext] = Depends(get_tenant_context_optional),
):
    """Compare analytics across all landing pages."""
    query = select(LandingPage)
    if tenant and tenant.workspace_id:
        query = query.where(
            or_(
                LandingPage.workspace_id == tenant.workspace_id,
                LandingPage.workspace_id.is_(None),
            )
        )
    query = query.order_by(desc(LandingPage.created_at))
    result = await db.execute(query)
    pages = result.scalars().all()

    if not pages:
        return []

    page_ids = [p.id for p in pages]

    # Aggregate visits per page
    visits_result = await db.execute(
        select(
            LandingPageVisit.landing_page_id,
            func.count().label("total_visits"),
            func.count(func.distinct(LandingPageVisit.session_id)).label("unique_visits"),
        )
        .where(LandingPageVisit.landing_page_id.in_(page_ids))
        .group_by(LandingPageVisit.landing_page_id)
    )
    visits_map = {
        row.landing_page_id: {
            "total_visits": row.total_visits or 0,
            "unique_visits": row.unique_visits or 0,
        }
        for row in visits_result.all()
    }

    # Aggregate form fills (leads) per page
    leads_result = await db.execute(
        select(
            Lead.landing_page_id,
            func.count().label("form_fills"),
        )
        .where(Lead.landing_page_id.in_(page_ids))
        .group_by(Lead.landing_page_id)
    )
    leads_map = {row.landing_page_id: row.form_fills or 0 for row in leads_result.all()}

    # Aggregate bookings per landing_page_id
    bookings_per_lp = await db.execute(
        select(
            Lead.landing_page_id,
            func.count().label("bookings"),
        )
        .join(Booking, Booking.lead_id == Lead.id)
        .where(Lead.landing_page_id.in_(page_ids))
        .group_by(Lead.landing_page_id)
    )
    bookings_map = {row.landing_page_id: row.bookings or 0 for row in bookings_per_lp.all()}

    # Aggregate deals closed per page
    deals_result = await db.execute(
        select(
            Lead.landing_page_id,
            func.count().label("deals"),
        )
        .join(Deal, Deal.lead_id == Lead.id)
        .where(Lead.landing_page_id.in_(page_ids))
        .where(Deal.status == "closed_won")
        .group_by(Lead.landing_page_id)
    )
    deals_map = {row.landing_page_id: row.deals or 0 for row in deals_result.all()}

    # Aggregate inbound email replies per landing_page_id
    email_replies_result = await db.execute(
        select(
            Lead.landing_page_id,
            func.count().label("c"),
        )
        .select_from(Interaction)
        .join(Lead, Interaction.lead_id == Lead.id)
        .where(Lead.landing_page_id.in_(page_ids))
        .where(Interaction.direction == "inbound")
        .where(Interaction.interaction_type == "email")
        .group_by(Lead.landing_page_id)
    )
    email_replies_map = {row.landing_page_id: row.c or 0 for row in email_replies_result.all()}

    # Aggregate calls made per landing_page_id
    calls_result = await db.execute(
        select(
            Lead.landing_page_id,
            func.count().label("c"),
        )
        .select_from(PhoneCall)
        .join(Lead, PhoneCall.lead_id == Lead.id)
        .where(Lead.landing_page_id.in_(page_ids))
        .group_by(Lead.landing_page_id)
    )
    calls_map = {row.landing_page_id: row.c or 0 for row in calls_result.all()}

    compare_items = []
    for p in pages:
        v = visits_map.get(p.id, {"total_visits": 0, "unique_visits": 0})
        form_fills = leads_map.get(p.id, 0)
        unique_visits = v["unique_visits"]
        conversion_rate = round((form_fills / unique_visits * 100), 2) if unique_visits > 0 else 0.0
        compare_items.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "is_active": p.is_active,
            "is_random_pool": p.is_random_pool,
            "analytics": {
                "total_visits": v["total_visits"],
                "unique_visits": unique_visits,
                "form_fills": form_fills,
                "conversion_rate": conversion_rate,
                "email_replies": email_replies_map.get(p.id, 0),
                "calls_made": calls_map.get(p.id, 0),
                "bookings_created": bookings_map.get(p.id, 0),
                "deals_closed": deals_map.get(p.id, 0),
            },
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return compare_items


def _workspace_match(model_col, workspace_id):
    """Build a NULL-safe workspace filter.

    Postgres `NULL == NULL` returns NULL, not TRUE, so an `==` filter would
    silently miss rows whose workspace_id is NULL when lp.workspace_id is also
    NULL. This helper handles both branches explicitly.
    """
    if workspace_id is None:
        return model_col.is_(None)
    return or_(model_col == workspace_id, model_col.is_(None))


@router.post("", response_model=LandingPageResponse, status_code=201)
async def create_landing_page(
    data: LandingPageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Optional[TenantContext] = Depends(get_tenant_context_optional),
):
    """Create a new landing page (manual or from prompt)."""
    workspace_id = tenant.workspace_id if tenant else None

    # Check slug uniqueness within the same workspace scope
    existing = await db.execute(
        select(LandingPage)
        .where(LandingPage.slug == data.slug)
        .where(_workspace_match(LandingPage.workspace_id, workspace_id))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' already exists")

    lp = LandingPage(
        workspace_id=workspace_id,
        name=data.name,
        slug=data.slug,
        prompt=data.prompt,
        html_content=data.html_content,
        css_content=data.css_content,
        js_content=data.js_content,
        is_active=data.is_active,
        is_random_pool=data.is_random_pool,
        ai_model=data.ai_model,
        ai_provider=data.ai_provider,
        created_by=current_user.email,
    )
    db.add(lp)
    await db.commit()
    await db.refresh(lp)

    # If activating, deactivate others in the same workspace scope
    if lp.is_active:
        await db.execute(
            update(LandingPage)
            .where(LandingPage.id != lp.id)
            .where(_workspace_match(LandingPage.workspace_id, lp.workspace_id))
            .values(is_active=False)
        )
        await db.commit()

    return lp


@router.get("/{landing_page_id}", response_model=LandingPageResponse)
async def get_landing_page(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a landing page by ID."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")
    return lp


@router.patch("/{landing_page_id}", response_model=LandingPageResponse)
async def update_landing_page(
    landing_page_id: int,
    data: LandingPageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a landing page."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    # Check slug uniqueness if changing, scoped to the same workspace
    if data.slug and data.slug != lp.slug:
        existing = await db.execute(
            select(LandingPage)
            .where(LandingPage.slug == data.slug)
            .where(_workspace_match(LandingPage.workspace_id, lp.workspace_id))
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' already exists")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lp, key, value)

    lp.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(lp)

    # If activating, deactivate others in the same workspace scope
    if data.is_active:
        await db.execute(
            update(LandingPage)
            .where(LandingPage.id != lp.id)
            .where(_workspace_match(LandingPage.workspace_id, lp.workspace_id))
            .values(is_active=False)
        )
        await db.commit()
        await db.refresh(lp)

    return lp


@router.delete("/{landing_page_id}", status_code=204)
async def delete_landing_page(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a landing page and its visits."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    # Delete dependent visits first to avoid FK violations on non-CASCADE schemas
    await db.execute(
        delete(LandingPageVisit).where(LandingPageVisit.landing_page_id == landing_page_id)
    )
    await db.delete(lp)
    await db.commit()
    return None


@router.post("/{landing_page_id}/generate", response_model=LandingPageResponse)
async def generate_landing_page(
    landing_page_id: int,
    data: LandingPageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate landing page content with AI."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    prompt = data.prompt or lp.prompt or "Generate a modern, high-converting landing page for Eko AI."

    # Read Cal.com settings dynamically
    cal_username = "ender-ocando-lfxtkn"
    cal_event = "15min"
    try:
        cal_user_setting = await db.execute(
            select(AppSetting).where(AppSetting.key == "cal_com_username")
        )
        cal_user_row = cal_user_setting.scalar_one_or_none()
        if cal_user_row and cal_user_row.value:
            cal_username = cal_user_row.value

        cal_event_setting = await db.execute(
            select(AppSetting).where(AppSetting.key == "cal_com_event_slug")
        )
        cal_event_row = cal_event_setting.scalar_one_or_none()
        if cal_event_row and cal_event_row.value:
            cal_event = cal_event_row.value
    except Exception:
        pass
    cal_com_link = f"https://cal.com/{cal_username}/{cal_event}"

    generator = LandingPageGenerator()

    try:
        generated = await generator.generate(
            custom_prompt=prompt,
            landing_page_id=lp.id,
            provider=data.provider or lp.ai_provider,
            model=data.model or lp.ai_model,
            cal_com_link=cal_com_link,
        )
    except Exception as e:
        logger.error(f"Generation failed for landing page {landing_page_id}: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

    lp.html_content = generated["html_content"]
    lp.css_content = generated.get("css_content")
    lp.js_content = generated.get("js_content")
    lp.generation_metadata = generated["metadata"]
    lp.prompt = prompt
    lp.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(lp)
    return lp


@router.post("/{landing_page_id}/activate", response_model=LandingPageResponse)
async def activate_landing_page(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate a landing page as the primary one."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    lp.is_active = True
    await db.commit()

    # Deactivate others in the same workspace scope (NULL-safe)
    await db.execute(
        update(LandingPage)
        .where(LandingPage.id != lp.id)
        .where(_workspace_match(LandingPage.workspace_id, lp.workspace_id))
        .values(is_active=False)
    )
    await db.commit()
    await db.refresh(lp)
    return lp


@router.get("/{landing_page_id}/preview")
async def preview_landing_page(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return HTML for preview in an iframe."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    return HTMLResponse(content=lp.html_content)


@router.get("/{landing_page_id}/analytics", response_model=LandingPageAnalyticsResponse)
async def get_landing_page_analytics(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed analytics for a landing page."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    # Unique visits
    unique_visits = await db.scalar(
        select(func.count(func.distinct(LandingPageVisit.session_id)))
        .where(LandingPageVisit.landing_page_id == landing_page_id)
    )

    # Total visits
    total_visits = await db.scalar(
        select(func.count()).where(LandingPageVisit.landing_page_id == landing_page_id)
    )

    # Form fills (leads from this landing page)
    form_fills = await db.scalar(
        select(func.count()).where(Lead.landing_page_id == landing_page_id)
    )

    # Email replies (inbound interactions from leads of this LP)
    email_replies = await db.scalar(
        select(func.count())
        .select_from(Interaction)
        .join(Lead, Interaction.lead_id == Lead.id)
        .where(Lead.landing_page_id == landing_page_id)
        .where(Interaction.direction == "inbound")
        .where(Interaction.interaction_type == "email")
    )

    # Calls made
    calls_made = await db.scalar(
        select(func.count())
        .select_from(PhoneCall)
        .join(Lead, PhoneCall.lead_id == Lead.id)
        .where(Lead.landing_page_id == landing_page_id)
    )

    # Bookings
    bookings_created = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .join(Lead, Booking.lead_id == Lead.id)
        .where(Lead.landing_page_id == landing_page_id)
    )

    # Deals closed
    deals_closed = await db.scalar(
        select(func.count())
        .select_from(Deal)
        .join(Lead, Deal.lead_id == Lead.id)
        .where(Lead.landing_page_id == landing_page_id)
        .where(Deal.status == "closed_won")
    )

    conversion_rate = (form_fills / unique_visits * 100) if unique_visits > 0 else 0.0

    # Time series: visits per day last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    time_series_result = await db.execute(
        select(
            func.date(LandingPageVisit.created_at).label("date"),
            func.count().label("visits"),
        )
        .where(LandingPageVisit.landing_page_id == landing_page_id)
        .where(LandingPageVisit.created_at >= thirty_days_ago)
        .group_by(func.date(LandingPageVisit.created_at))
        .order_by(func.date(LandingPageVisit.created_at))
    )
    time_series = [{"date": str(row.date), "visits": row.visits} for row in time_series_result.all()]

    # Leads generated
    leads_result = await db.execute(
        select(Lead.id, Lead.business_name, Lead.email, Lead.status, Lead.total_score, Lead.created_at)
        .where(Lead.landing_page_id == landing_page_id)
        .order_by(desc(Lead.created_at))
        .limit(50)
    )
    leads = [
        {
            "id": row.id,
            "business_name": row.business_name,
            "email": row.email,
            "status": row.status.value if row.status else None,
            "score": row.total_score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in leads_result.all()
    ]

    analytics = LandingPageAnalytics(
        total_visits=total_visits or 0,
        unique_visits=unique_visits or 0,
        form_fills=form_fills or 0,
        email_replies=email_replies or 0,
        calls_made=calls_made or 0,
        bookings_created=bookings_created or 0,
        deals_closed=deals_closed or 0,
        conversion_rate=round(conversion_rate, 2),
    )

    return LandingPageAnalyticsResponse(
        landing_page_id=lp.id,
        name=lp.name,
        slug=lp.slug,
        analytics=analytics,
        time_series=time_series,
        leads=leads,
    )


@router.post("/{landing_page_id}/clone", response_model=LandingPageResponse)
async def clone_landing_page(
    landing_page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone an existing landing page."""
    result = await db.execute(select(LandingPage).where(LandingPage.id == landing_page_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Landing page not found")

    new_slug = f"{lp.slug}-copy"
    # Ensure unique slug within the same workspace
    suffix = 1
    base_slug = new_slug
    while True:
        existing = await db.execute(
            select(LandingPage)
            .where(LandingPage.slug == new_slug)
            .where(_workspace_match(LandingPage.workspace_id, lp.workspace_id))
        )
        if not existing.scalar_one_or_none():
            break
        suffix += 1
        new_slug = f"{base_slug}-{suffix}"

    new_lp = LandingPage(
        workspace_id=lp.workspace_id,
        name=f"{lp.name} (Copy)",
        slug=new_slug,
        prompt=lp.prompt,
        html_content=lp.html_content,
        css_content=lp.css_content,
        js_content=lp.js_content,
        is_active=False,
        is_random_pool=lp.is_random_pool,
        ai_model=lp.ai_model,
        ai_provider=lp.ai_provider,
        generation_metadata=lp.generation_metadata,
        created_by=current_user.email,
    )
    db.add(new_lp)
    await db.commit()
    await db.refresh(new_lp)
    return new_lp
