import logging
import math
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Body
from sqlalchemy import select, func, Integer, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadListResponse, DiscoveryRequest, LeadSearchRequest
from app.agents.discovery.agent import DiscoveryAgent
from app.agents.research.agent import ResearchAgent
from app.agents.outreach.channels.email import EmailOutreach, EMAIL_TEMPLATES
from app.services.paperclip import on_lead_status_change, on_system_alert
from app.utils.embedding import update_lead_embedding
from app.utils.ai_client import generate_embedding
from app.core.security import get_current_user
from app.api.v1.crm import VALID_TRANSITIONS

logger = logging.getLogger(__name__)

router = APIRouter()




@router.get("/enrichment-status", response_model=dict)
async def enrichment_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return counts of leads by all statuses."""
    counts = {}
    for s in LeadStatus:
        counts[s.value] = await db.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == s)
        )
    pipeline_total = (
        counts.get(LeadStatus.DISCOVERED.value, 0)
        + counts.get(LeadStatus.ENRICHED.value, 0)
        + counts.get(LeadStatus.SCORED.value, 0)
    )
    return {
        "counts": counts,
        "discovered": counts.get(LeadStatus.DISCOVERED.value, 0),
        "enriched": counts.get(LeadStatus.ENRICHED.value, 0),
        "scored": counts.get(LeadStatus.SCORED.value, 0),
        "total": sum(counts.values()),
        "pipeline_total": pipeline_total,
    }

def _haversine_km(lat1: float, lng1: float, lat2: Optional[float], lng2: Optional[float]) -> Optional[float]:
    """Calculate Haversine distance in km. Returns None if lat2/lng2 are missing."""
    if lat2 is None or lng2 is None:
        return None
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    a = min(1.0, max(0.0, a))  # Clamp to protect against floating-point drift
    c = 2 * math.asin(math.sqrt(a))
    return R * c


@router.get("", response_model=LeadListResponse)
async def list_leads(
    status: Optional[LeadStatus] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
    lat: Optional[float] = Query(None, description="Reference latitude for distance sorting"),
    lng: Optional[float] = Query(None, description="Reference longitude for distance sorting"),
    sort_by: str = Query("score", enum=["score", "distance", "score_distance"]),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum total score filter"),
    max_score: Optional[float] = Query(None, ge=0, le=100, description="Maximum total score filter"),
    has_email: Optional[bool] = Query(None, description="Filter leads with email"),
    has_phone: Optional[bool] = Query(None, description="Filter leads with phone"),
    has_website: Optional[bool] = Query(None, description="Filter leads with website"),
    category: Optional[str] = Query(None, description="Filter by business category"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List leads with optional filtering, geo-sorting and smart ranking."""
    query = select(Lead)

    # Non-admin users see their own leads + public leads (no owner)
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.where(
            (Lead.owner_id == current_user.id) | (Lead.owner_id.is_(None)) | (Lead.assigned_to == current_user.email)
        )

    if status:
        query = query.where(Lead.status == status)
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    if search:
        query = query.where(Lead.business_name.ilike(f"%{search}%"))
    if category:
        query = query.where(Lead.category.ilike(f"%{category}%"))
    if min_score is not None:
        query = query.where(func.coalesce(Lead.total_score, 0) >= min_score)
    if max_score is not None:
        query = query.where(func.coalesce(Lead.total_score, 0) <= max_score)
    if has_email is True:
        query = query.where(Lead.email.isnot(None) & (Lead.email != ''))
    elif has_email is False:
        query = query.where((Lead.email.is_(None)) | (Lead.email == ''))
    if has_phone is True:
        query = query.where(Lead.phone.isnot(None) & (Lead.phone != ''))
    elif has_phone is False:
        query = query.where((Lead.phone.is_(None)) | (Lead.phone == ''))
    if has_website is True:
        query = query.where(Lead.website.isnot(None) & (Lead.website != ''))
    elif has_website is False:
        query = query.where((Lead.website.is_(None)) | (Lead.website == ''))

    # Count total before pagination / sorting
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Contactability score expression (reused for geo and non-geo sorts)
    contact_score = (
        func.coalesce(func.nullif(Lead.email, '').isnot(None).cast(Integer), 0) +
        func.coalesce(func.nullif(Lead.phone, '').isnot(None).cast(Integer), 0) +
        case(
            (Lead.website.isnot(None) & (Lead.website != '') & ~Lead.website.ilike('%yelp.com%'), 1),
            else_=0
        )
    )

    # Geo-sorting: use SQL-side Haversine distance for deterministic, scalable ordering
    needs_geo_sort = lat is not None and lng is not None and sort_by in ("distance", "score_distance")
    if needs_geo_sort:
        lat_rad = func.radians(lat)
        lng_rad = func.radians(lng)
        lead_lat_rad = func.radians(Lead.latitude)
        lead_lng_rad = func.radians(Lead.longitude)
        dlat = lead_lat_rad - lat_rad
        dlng = lead_lng_rad - lng_rad
        a = (
            func.pow(func.sin(dlat / 2), 2) +
            func.cos(lat_rad) * func.cos(lead_lat_rad) * func.pow(func.sin(dlng / 2), 2)
        )
        c = 2 * func.asin(func.sqrt(func.least(1.0, func.greatest(0.0, a))))
        distance_expr = (6371.0 * c).label("distance_km")

        # Only leads with coordinates can be distance-sorted
        query = query.where(Lead.latitude.isnot(None) & Lead.longitude.isnot(None))

        if sort_by == "distance":
            query = query.order_by(distance_expr.asc())
        elif sort_by == "score_distance":
            query = query.order_by(
                contact_score.desc(),
                func.coalesce(Lead.total_score, 0).desc(),
                distance_expr.asc(),
            )

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        leads = list(result.scalars().all())

        # Compute distance_km on the small paginated result set for serialization
        for lead in leads:
            lead.distance_km = _haversine_km(lat, lng, lead.latitude, lead.longitude)

        return LeadListResponse(
            total=total,
            items=leads,
            page=page,
            page_size=page_size,
        )

    # Standard SQL-side sorting (no geo reference)
    if sort_by == "score":
        query = query.order_by(contact_score.desc(), func.coalesce(Lead.total_score, 0).desc(), Lead.created_at.desc())
    elif sort_by == "score_distance" and (lat is None or lng is None):
        # Fallback to score-only if lat/lng missing
        query = query.order_by(contact_score.desc(), func.coalesce(Lead.total_score, 0).desc(), Lead.created_at.desc())
    else:
        query = query.order_by(Lead.created_at.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    leads = result.scalars().all()

    return LeadListResponse(
        total=total,
        items=leads,
        page=page,
        page_size=page_size,
    )


@router.get("/autocomplete/names", response_model=list[str])
async def autocomplete_lead_names(
    q: str = Query(..., min_length=1, description="Search prefix"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return matching business names for autocomplete."""
    query = (
        select(Lead.business_name)
        .where(Lead.business_name.ilike(f"%{q}%"))
        .distinct()
        .limit(limit)
    )
    # Non-admin users only see their own leads
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.where(
            (Lead.owner_id == current_user.id) | (Lead.assigned_to == current_user.email)
        )

    result = await db.execute(query)
    return list(result.scalars().all())


def _check_lead_access(lead: Lead, current_user: User):
    """Raise 403 if the user is not authorized to access this lead.
    Admins/superusers can access any lead. Users can access leads they own
    or that are assigned to them. Public leads (owner_id is None) are visible
    to all authenticated users.
    """
    if current_user.is_superuser or current_user.role.value == "admin":
        return
    if lead.owner_id is None:
        return
    if lead.owner_id == current_user.id:
        return
    if lead.assigned_to and lead.assigned_to == current_user.email:
        return
    raise HTTPException(status_code=403, detail="Not authorized to access this lead")


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_lead_access(lead, current_user)
    return lead


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(
    lead_data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new lead manually."""
    lead = Lead(**lead_data.model_dump(), owner_id=current_user.id)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    lead_update: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_lead_access(lead, current_user)

    update_data = lead_update.model_dump(exclude_unset=True)

    # Validate status transitions if status is being updated
    if "status" in update_data:
        new_status = update_data["status"]
        if isinstance(new_status, str):
            new_status = LeadStatus(new_status)
        allowed = VALID_TRANSITIONS.get(lead.status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition from {lead.status.value} to {new_status.value}. Allowed: {[s.value for s in allowed]}"
            )
        # Record the transition as an interaction
        old_status = lead.status.value
        interaction = Interaction(
            lead_id=lead.id,
            interaction_type="note",
            direction="outbound",
            content=f"Status changed from {old_status} to {new_status.value}",
            meta={"transition": True, "from": old_status, "to": new_status.value, "source": "api_patch"},
        )
        db.add(interaction)

    # Whitelist allowed fields to prevent accidental dynamic attribute creation
    allowed_fields = {c.name for c in Lead.__table__.columns}
    for field, value in update_data.items():
        if field in allowed_fields:
            setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_lead_access(lead, current_user)

    await db.delete(lead)
    await db.commit()
    return None


@router.post("/{lead_id}/enrich", response_model=LeadResponse)
async def enrich_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run research agent to enrich a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_lead_access(lead, current_user)

    research_agent = ResearchAgent()
    enriched = await research_agent.enrich(lead)
    
    # Update lead with enriched data
    for field, value in enriched.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    
    old_status = lead.status.value
    if lead.urgency_score is not None and lead.fit_score is not None:
        lead.total_score = (lead.urgency_score + lead.fit_score) / 2
        lead.status = LeadStatus.SCORED
    else:
        lead.status = LeadStatus.ENRICHED
    
    await db.commit()
    await db.refresh(lead)
    
    # Generate updated embedding with enriched data
    try:
        await update_lead_embedding(lead)
        await db.commit()
    except Exception:
        pass
    
    # Paperclip: log status change
    try:
        on_lead_status_change(
            lead_id=lead.id,
            business_name=lead.business_name,
            old_status=old_status,
            new_status=lead.status.value,
        )
    except Exception:
        pass
    
    return lead


@router.post("/discover", response_model=LeadListResponse, status_code=201)
async def discover_leads(
    request: DiscoveryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run discovery agent to find new leads."""
    agent = DiscoveryAgent()
    leads_data = await agent.discover(
        query=request.query,
        city=request.city,
        state=request.state,
        radius_miles=request.radius_miles,
        max_results=request.max_results,
        sources=request.sources,
    )
    
    created_leads = []
    for lead_data in leads_data:
        # Check for duplicates by business_name + city
        existing = await db.execute(
            select(Lead).where(
                Lead.business_name == lead_data["business_name"],
                Lead.city == lead_data.get("city"),
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        lead = Lead(**lead_data, owner_id=current_user.id)
        if request.campaign_id:
            lead.source_data = {"campaign_id": request.campaign_id}
        db.add(lead)
        created_leads.append(lead)
    
    await db.commit()
    for lead in created_leads:
        await db.refresh(lead)
        # Generate embedding for semantic search (non-blocking to response)
        try:
            await update_lead_embedding(lead)
        except Exception:
            pass
    
    # Save embeddings
    if created_leads:
        await db.commit()
    
    return {
        "total": len(created_leads),
        "page": 1,
        "page_size": len(created_leads),
        "items": created_leads,
    }


@router.post("/search", response_model=LeadListResponse)
async def search_leads(
    request: LeadSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Semantic search over leads using vector similarity."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    # Generate embedding for the search query
    try:
        query_embedding = await generate_embedding(request.query)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    # Build query with cosine distance using pgvector
    distance_expr = Lead.embedding.op("<=>")(query_embedding)
    query = (
        select(Lead, distance_expr.label("distance"))
        .where(Lead.embedding.isnot(None))
        .where(distance_expr < 0.5)  # Filter in SQL, not Python
        .order_by(distance_expr)
        .limit(request.limit)
    )

    # Ownership filter
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.where(
            (Lead.owner_id == current_user.id) | (Lead.assigned_to == current_user.email) | (Lead.owner_id.is_(None))
        )

    if request.status:
        query = query.where(Lead.status == request.status)
    if request.min_score is not None:
        query = query.where(Lead.total_score >= request.min_score)

    result = await db.execute(query)
    rows = result.all()
    items = [lead for lead, distance in rows]

    return LeadListResponse(
        total=len(items),
        items=items,
        page=1,
        page_size=len(items),
    )


@router.post("/enrich-all", response_model=dict)
async def enrich_all_leads(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue enrichment for all discovered/enriched leads without a real website analyzed."""
    query = select(Lead.id).where(
        Lead.status.in_([LeadStatus.DISCOVERED, LeadStatus.ENRICHED])
    )
    # Ownership filter
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.where(
            (Lead.owner_id == current_user.id) | (Lead.assigned_to == current_user.email) | (Lead.owner_id.is_(None))
        )
    result = await db.execute(query)
    lead_ids = [row[0] for row in result.all()]

    # Run in background so the HTTP request returns immediately
    # Pass only IDs — the background task opens its own fresh session
    background_tasks.add_task(_enrich_leads_batch, lead_ids)

    return {
        "message": f"Enrichment started for {len(lead_ids)} leads in the background",
        "total": len(lead_ids),
    }


async def _enrich_leads_batch(lead_ids: list[int]):
    """Background task: enrich a batch of leads. Opens its own DB session."""
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        agent = ResearchAgent()
        enriched_count = 0
        failed_count = 0

        for lead_id in lead_ids:
            try:
                result = await db.execute(select(Lead).where(Lead.id == lead_id))
                lead = result.scalar_one_or_none()
                if not lead:
                    continue

                enriched = await agent.enrich(lead)
                for field, value in enriched.model_dump(exclude_unset=True).items():
                    setattr(lead, field, value)

                if lead.urgency_score is not None and lead.fit_score is not None:
                    lead.total_score = (lead.urgency_score + lead.fit_score) / 2
                    lead.status = LeadStatus.SCORED
                else:
                    lead.status = LeadStatus.ENRICHED

                # Update embedding
                try:
                    await update_lead_embedding(lead)
                except Exception:
                    pass

                enriched_count += 1
            except Exception as e:
                logger.error(f"Failed to enrich lead {lead_id}: {e}")
                failed_count += 1

        await db.commit()
    logger.info(f"Batch enrichment complete: {enriched_count} enriched, {failed_count} failed")


@router.post("/bulk/contact", response_model=dict)
async def bulk_contact_leads(
    lead_ids: List[int] = Body(..., description="List of lead IDs to contact"),
    template: str = Body("initial_outreach", description="Email template key to use"),
    custom_subject: Optional[str] = Body(None, description="Optional custom subject (overrides AI generation)"),
    custom_body: Optional[str] = Body(None, description="Optional custom body (overrides AI generation)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk contact multiple leads via email.
    Only contacts leads in SCORED status with email and do_not_contact=False.
    Rate limited to MAX_CAMPAIGN_EMAILS_PER_BATCH (50) per request.
    """
    from app.api.v1.campaigns import MAX_CAMPAIGN_EMAILS_PER_BATCH

    if len(lead_ids) > MAX_CAMPAIGN_EMAILS_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Max {MAX_CAMPAIGN_EMAILS_PER_BATCH} leads per bulk contact request"
        )
    
    if template not in EMAIL_TEMPLATES:
        template = "initial_outreach"
    
    # Fetch eligible leads
    result = await db.execute(
        select(Lead).where(
            and_(
                Lead.id.in_(lead_ids),
                Lead.status == LeadStatus.SCORED,
                Lead.email.isnot(None),
                Lead.do_not_contact == False,
            )
        )
    )
    leads = result.scalars().all()
    
    if not leads:
        raise HTTPException(
            status_code=400,
            detail="No eligible leads found. Need leads in SCORED status with email."
        )
    
    email_outreach = EmailOutreach()
    sent_count = 0
    failed_count = 0
    results = []
    
    for lead in leads:
        try:
            if custom_subject and custom_body:
                # Manual email
                response = await email_outreach.send(
                    to_email=lead.email,
                    subject=custom_subject,
                    body=custom_body,
                    lead_id=lead.id,
                    business_name=lead.business_name,
                    ai_generated=False,
                )
            else:
                # AI-generated email
                response = await email_outreach.generate_and_send(
                    lead=lead,
                    template_key=template,
                )
            
            # Record interaction
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="outbound",
                subject=response.get("subject", custom_subject or ""),
                content=response.get("body", custom_body or ""),
                email_status="sent",
                email_message_id=response.get("id"),
                meta={
                    "template": template,
                    "ai_generated": not (custom_subject and custom_body),
                    "bulk_contact": True,
                },
            )
            db.add(interaction)
            
            # Update lead status
            lead.status = LeadStatus.CONTACTED
            lead.last_contact_at = datetime.utcnow()
            
            sent_count += 1
            results.append({"lead_id": lead.id, "status": "sent", "message_id": response.get("id")})
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Bulk contact failed for lead {lead.id}: {e}")
            results.append({"lead_id": lead.id, "status": "failed", "error": str(e)})
            
            # Record failed interaction
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="email",
                direction="outbound",
                content=f"Bulk contact FAILED: {str(e)}",
                email_status="bounced",
                meta={"template": template, "bulk_contact": True, "error": str(e)},
            )
            db.add(interaction)
    
    await db.commit()
    
    return {
        "total_requested": len(lead_ids),
        "eligible": len(leads),
        "sent": sent_count,
        "failed": failed_count,
        "results": results,
    }
