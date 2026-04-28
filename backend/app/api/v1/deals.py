from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.deal import Deal, DealStatus
from app.models.lead import Lead
from app.models.user import User
from app.schemas.deal import DealCreate, DealUpdate, DealResponse, DealListResponse, RevenueForecast, DealPipelineSummary
from app.core.security import get_current_user

router = APIRouter()


@router.get("", response_model=DealListResponse)
async def list_deals(
    status: Optional[str] = None,
    lead_id: Optional[int] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    assigned_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List deals with optional filters."""
    query = select(Deal)
    
    if status:
        query = query.where(Deal.status == status)
    if lead_id:
        query = query.where(Deal.lead_id == lead_id)
    if min_value is not None:
        query = query.where(Deal.value >= min_value)
    if max_value is not None:
        query = query.where(Deal.value <= max_value)
    if assigned_to:
        query = query.where(Deal.assigned_to == assigned_to)
    
    # Count total
    count_result = await db.execute(
        select(func.count(Deal.id)).select_from(query.subquery())
    )
    total = count_result.scalar() or 0
    
    query = query.order_by(desc(Deal.updated_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return DealListResponse(total=total, items=items)


@router.post("", response_model=DealResponse)
async def create_deal(
    data: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new deal."""
    # Verify lead exists
    lead_result = await db.execute(select(Lead).where(Lead.id == data.lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    deal = Deal(
        lead_id=data.lead_id,
        name=data.name,
        value=data.value,
        probability=data.probability,
        status=data.status,
        expected_close_date=data.expected_close_date,
        description=data.description,
        notes=data.notes,
        source=data.source,
        assigned_to=data.assigned_to or current_user.email,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: int,
    data: DealUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status in [DealStatus.CLOSED_WON.value, DealStatus.CLOSED_LOST.value]:
            deal.actual_close_date = datetime.utcnow()
    
    for field, val in update_data.items():
        setattr(deal, field, val)
    
    await db.commit()
    await db.refresh(deal)
    return deal


@router.delete("/{deal_id}")
async def delete_deal(
    deal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    await db.delete(deal)
    await db.commit()
    return {"status": "deleted", "id": deal_id}


@router.get("/lead/{lead_id}/deals", response_model=DealListResponse)
async def get_lead_deals(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all deals for a specific lead."""
    result = await db.execute(
        select(Deal).where(Deal.lead_id == lead_id).order_by(desc(Deal.created_at))
    )
    items = result.scalars().all()
    return DealListResponse(total=len(items), items=items)


@router.get("/forecast/revenue", response_model=RevenueForecast)
async def get_revenue_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get revenue forecast based on current pipeline."""
    # Pipeline summary by status
    result = await db.execute(
        select(
            Deal.status,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.value), 0),
            func.coalesce(func.sum(Deal.value * Deal.probability / 100), 0),
        )
        .where(Deal.status.not_in([DealStatus.CLOSED_WON.value, DealStatus.CLOSED_LOST.value]))
        .group_by(Deal.status)
    )
    
    pipeline = []
    total_value = 0
    total_weighted = 0
    
    for status, count, value_sum, weighted_sum in result.all():
        total_value += float(value_sum)
        total_weighted += float(weighted_sum)
        pipeline.append(DealPipelineSummary(
            status=status,
            count=count,
            total_value=float(value_sum),
            weighted_value=float(weighted_sum),
        ))
    
    # Expected revenue this month
    now = datetime.utcnow()
    month_end = now.replace(day=28) + timedelta(days=4)
    month_end = month_end.replace(day=1) - timedelta(days=1)
    
    month_result = await db.execute(
        select(func.coalesce(func.sum(Deal.value * Deal.probability / 100), 0))
        .where(Deal.expected_close_date <= month_end)
        .where(Deal.status.not_in([DealStatus.CLOSED_LOST.value]))
    )
    expected_this_month = float(month_result.scalar() or 0)
    
    # Expected revenue this quarter
    quarter_end_month = ((now.month - 1) // 3 + 1) * 3
    quarter_end = now.replace(month=quarter_end_month, day=28) + timedelta(days=4)
    quarter_end = quarter_end.replace(day=1) - timedelta(days=1)
    
    quarter_result = await db.execute(
        select(func.coalesce(func.sum(Deal.value * Deal.probability / 100), 0))
        .where(Deal.expected_close_date <= quarter_end)
        .where(Deal.status.not_in([DealStatus.CLOSED_LOST.value]))
    )
    expected_this_quarter = float(quarter_result.scalar() or 0)
    
    # Total deals count (open)
    count_result = await db.execute(
        select(func.count(Deal.id)).where(Deal.status.not_in([DealStatus.CLOSED_WON.value, DealStatus.CLOSED_LOST.value]))
    )
    deals_count = count_result.scalar() or 0
    
    # Closed won
    won_result = await db.execute(
        select(func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0))
        .where(Deal.status == DealStatus.CLOSED_WON.value)
    )
    won_count, won_value = won_result.one_or_none() or (0, 0)
    
    # Closed lost
    lost_result = await db.execute(
        select(func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0))
        .where(Deal.status == DealStatus.CLOSED_LOST.value)
    )
    lost_count, lost_value = lost_result.one_or_none() or (0, 0)
    
    return RevenueForecast(
        pipeline=pipeline,
        total_pipeline_value=total_value,
        total_weighted_value=total_weighted,
        expected_revenue_this_month=expected_this_month,
        expected_revenue_this_quarter=expected_this_quarter,
        deals_count=deals_count,
        closed_won_count=won_count or 0,
        closed_won_value=float(won_value or 0),
        closed_lost_count=lost_count or 0,
        closed_lost_value=float(lost_value or 0),
        total_revenue=float(won_value or 0),
    )
