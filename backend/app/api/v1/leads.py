import logging
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadListResponse, DiscoveryRequest, LeadSearchRequest
from app.agents.discovery.agent import DiscoveryAgent
from app.agents.research.agent import ResearchAgent
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
    """Return counts of leads by enrichment status."""
    discovered = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.DISCOVERED)
    )
    enriched = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.ENRICHED)
    )
    scored = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.SCORED)
    )
    return {
        "discovered": discovered,
        "enriched": enriched,
        "scored": scored,
        "total": discovered + enriched + scored,
    }

def _haversine_km(lat1: float, lng1: float, lat2: Optional[float], lng2: Optional[float]) -> Optional[float]:
    """Calculate Haversine distance in km. Returns None if lat2/lng2 are missing."""
    if lat2 is None or lng2 is None:
        return None
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List leads with optional filtering, geo-sorting and smart ranking."""
    query = select(Lead)

    # Non-admin users only see their own leads
    if not current_user.is_superuser and current_user.role.value != "admin":
        query = query.where(
            (Lead.owner_id == current_user.id) | (Lead.assigned_to == current_user.email)
        )

    if status:
        query = query.where(Lead.status == status)
    if city:
        query = query.where(Lead.city.ilike(f"%{city}%"))
    if search:
        query = query.where(Lead.business_name.ilike(f"%{search}%"))

    # Count total before pagination / sorting
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Determine if we need to fetch all items for Python-side geo sorting
    needs_geo_sort = lat is not None and lng is not None and sort_by in ("distance", "score_distance")

    if needs_geo_sort:
        # Fetch all filtered leads (capped at 2000 for performance)
        query = query.limit(2000)
        result = await db.execute(query)
        leads = list(result.scalars().all())

        # Compute distance for each lead
        for lead in leads:
            lead.distance_km = _haversine_km(lat, lng, lead.latitude, lead.longitude)

        # Sort
        if sort_by == "distance":
            leads.sort(key=lambda l: (l.distance_km if l.distance_km is not None else float("inf"), - (l.total_score or 0)))
        elif sort_by == "score_distance":
            # Primary: higher score first; Secondary: closer distance first
            leads.sort(key=lambda l: (- (l.total_score or 0), l.distance_km if l.distance_km is not None else float("inf")))

        # Python-side pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_leads = leads[start:end]

        return LeadListResponse(
            total=total,
            items=paginated_leads,
            page=page,
            page_size=page_size,
        )

    # Standard SQL-side sorting (no geo reference)
    if sort_by == "score":
        query = query.order_by(Lead.total_score.desc().nulls_last(), Lead.created_at.desc())
    elif sort_by == "score_distance" and (lat is None or lng is None):
        # Fallback to score-only if lat/lng missing
        query = query.order_by(Lead.total_score.desc().nulls_last(), Lead.created_at.desc())
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
    
    for field, value in update_data.items():
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
        "total_found": len(leads_data),
        "new_leads": len(created_leads),
        "duplicates_skipped": len(leads_data) - len(created_leads),
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
        .order_by(distance_expr)
        .limit(request.limit)
    )

    if request.status:
        query = query.where(Lead.status == request.status)
    if request.min_score is not None:
        query = query.where(Lead.total_score >= request.min_score)

    result = await db.execute(query)
    rows = result.all()

    # Filter by similarity threshold (cosine distance < 0.5 means fairly similar)
    items = []
    for lead, distance in rows:
        if distance < 0.5:
            items.append(lead)

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
    result = await db.execute(
        select(Lead).where(
            Lead.status.in_([LeadStatus.DISCOVERED, LeadStatus.ENRICHED])
        )
    )
    leads = result.scalars().all()

    # Run in background so the HTTP request returns immediately
    background_tasks.add_task(_enrich_leads_batch, leads, db)

    return {
        "message": f"Enrichment started for {len(leads)} leads in the background",
        "total": len(leads),
    }


async def _enrich_leads_batch(leads: list, db: AsyncSession):
    """Background task: enrich a batch of leads."""
    agent = ResearchAgent()
    enriched_count = 0
    failed_count = 0

    for lead in leads:
        try:
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
            logger.error(f"Failed to enrich lead {lead.id} ({lead.business_name}): {e}")
            failed_count += 1

    await db.commit()
    logger.info(f"Batch enrichment complete: {enriched_count} enriched, {failed_count} failed")
