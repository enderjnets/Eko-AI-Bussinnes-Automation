from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.lead import Lead, LeadStatus
from app.models.campaign import Campaign
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter()


@router.get("/pipeline")
async def get_pipeline_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get counts of leads by status for pipeline visualization."""
    result = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
    )
    pipeline = {status.value: 0 for status in LeadStatus}
    for status, count in result.all():
        pipeline[status.value] = count
    
    total_leads = sum(pipeline.values())
    
    return {
        "pipeline": pipeline,
        "total_leads": total_leads,
        "active_campaigns": await db.scalar(
            select(func.count(Campaign.id)).where(Campaign.status == "active")
        ),
    }


@router.get("/performance")
async def get_performance_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get key performance metrics."""
    total_leads = await db.scalar(select(func.count(Lead.id)))
    contacted = await db.scalar(
        select(func.count(Lead.id)).where(Lead.status.in_([
            LeadStatus.CONTACTED.name, LeadStatus.ENGAGED.name, LeadStatus.MEETING_BOOKED.name,
            LeadStatus.PROPOSAL_SENT.name, LeadStatus.NEGOTIATING.name, LeadStatus.CLOSED_WON.name,
        ]))
    )
    closed_won = await db.scalar(
        select(func.count(Lead.id)).where(Lead.status == LeadStatus.CLOSED_WON.name)
    )
    avg_score = await db.scalar(
        select(func.avg(Lead.total_score)).where(Lead.total_score.isnot(None))
    )
    
    conversion_rate = (closed_won / contacted * 100) if contacted else 0
    
    return {
        "total_leads": total_leads,
        "contacted": contacted,
        "closed_won": closed_won,
        "conversion_rate": round(conversion_rate, 2),
        "avg_lead_score": round(avg_score or 0, 2),
    }
