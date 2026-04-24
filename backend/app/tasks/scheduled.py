import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_, func

from app.tasks.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.campaign import Campaign, CampaignLead
from app.agents.outreach.channels.email import EmailOutreach
from app.agents.research.agent import ResearchAgent
from app.services.paperclip import on_system_alert, on_email_sent, on_email_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async helpers (Celery tasks are sync; we run async code via asyncio.run)
# ---------------------------------------------------------------------------

async def _process_follow_ups_async():
    """Process leads that need follow-up."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        cooldown = timedelta(hours=24)

        result = await db.execute(
            select(Lead)
            .where(Lead.next_follow_up_at <= now)
            .where(Lead.do_not_contact == False)
            .where(
                Lead.status.not_in([
                    LeadStatus.CLOSED_WON,
                    LeadStatus.CLOSED_LOST,
                    LeadStatus.CHURNED,
                ])
            )
            .where(
                # Don't spam: last contact must be older than cooldown
                (Lead.last_contact_at == None) | (Lead.last_contact_at <= now - cooldown)
            )
            .limit(50)
        )
        leads = result.scalars().all()

        email = EmailOutreach()
        processed = 0
        skipped = 0
        errors = 0

        for lead in leads:
            if not lead.email:
                skipped += 1
                continue

            try:
                # Determine follow-up number from interactions
                follow_up_result = await db.execute(
                    select(func.count(Interaction.id))
                    .where(
                        and_(
                            Interaction.lead_id == lead.id,
                            Interaction.interaction_type == "email",
                        )
                    )
                )
                follow_up_count = follow_up_result.scalar() or 0

                # Pick template based on follow-up count
                if follow_up_count == 0:
                    template_key = "initial_outreach"
                elif follow_up_count == 1:
                    template_key = "follow_up"
                else:
                    template_key = "meeting_request"

                response = await email.generate_and_send(
                    lead=lead,
                    template_key=template_key,
                )

                # Update lead
                lead.last_contact_at = now
                lead.next_follow_up_at = now + timedelta(days=3)

                # Record interaction
                interaction = Interaction(
                    lead_id=lead.id,
                    interaction_type="email",
                    direction="outbound",
                    subject=response.get("subject", "Follow-up"),
                    content=f"Auto follow-up #{follow_up_count + 1} sent",
                    email_status="sent",
                    email_message_id=response.get("id"),
                    metadata={
                        "auto_follow_up": True,
                        "follow_up_number": follow_up_count + 1,
                        "template": template_key,
                    },
                )
                db.add(interaction)
                processed += 1

            except Exception as e:
                logger.error(f"Failed to send follow-up to {lead.business_name}: {e}")
                errors += 1
                # Log error to Paperclip
                try:
                    on_email_error(
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        email=lead.email or "",
                        error=str(e),
                    )
                except Exception:
                    pass

        await db.commit()

        logger.info(
            f"Follow-ups complete: {processed} sent, {skipped} skipped (no email), {errors} errors"
        )
        return {"processed": processed, "skipped": skipped, "errors": errors}


async def _enrich_pending_leads_async():
    """Auto-enrich newly discovered leads that haven't been enriched yet."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lead)
            .where(Lead.status == LeadStatus.DISCOVERED)
            .where(Lead.do_not_contact == False)
            .limit(20)
        )
        leads = result.scalars().all()

        if not leads:
            logger.info("No pending leads to enrich")
            return {"enriched": 0, "skipped": 0}

        agent = ResearchAgent()
        enriched_count = 0
        skipped_count = 0

        for lead in leads:
            try:
                enrichment = await agent.enrich(lead)

                # Update lead with enriched data
                for field, value in enrichment.model_dump(exclude_unset=True).items():
                    setattr(lead, field, value)

                old_status = lead.status.value
                if lead.urgency_score and lead.fit_score:
                    lead.total_score = (lead.urgency_score + lead.fit_score) / 2
                    lead.status = LeadStatus.SCORED
                else:
                    lead.status = LeadStatus.ENRICHED

                enriched_count += 1
                logger.info(f"Enriched lead '{lead.business_name}' → {lead.status.value}")

            except Exception as e:
                logger.warning(f"Failed to enrich lead '{lead.business_name}': {e}")
                skipped_count += 1

        await db.commit()
        logger.info(f"Auto-enrichment complete: {enriched_count} enriched, {skipped_count} skipped")
        return {"enriched": enriched_count, "skipped": skipped_count}


async def _sync_dnc_registry_async():
    """Sync Do-Not-Call / unsubscribe list."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()

        # 1. Mark leads with too many bounced emails as do_not_contact
        bounced_result = await db.execute(
            select(Interaction.lead_id, func.count(Interaction.id).label("bounce_count"))
            .where(Interaction.interaction_type == "email")
            .where(Interaction.email_status == "bounced")
            .group_by(Interaction.lead_id)
            .having(func.count(Interaction.id) >= 3)
        )

        bounced_ids = [row.lead_id for row in bounced_result.all()]
        for lead_id in bounced_ids:
            lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = lead_result.scalar_one_or_none()
            if lead and not lead.do_not_contact:
                lead.do_not_contact = True
                lead.consent_status = "bounced"
                interaction = Interaction(
                    lead_id=lead_id,
                    interaction_type="note",
                    direction="outbound",
                    content="Auto-marked as do-not-contact due to repeated bounces",
                    metadata={"dnc_reason": "bounced", "bounce_count": 3},
                )
                db.add(interaction)
                logger.info(f"DNC sync: marked lead {lead_id} as do-not-contact (bounced)")

        # 2. Clean up old opted_out leads (CPA Colorado: delete after 2 years)
        cutoff = now - timedelta(days=730)
        old_optouts_result = await db.execute(
            select(Lead).where(
                and_(
                    Lead.consent_status == "opted_out",
                    Lead.updated_at <= cutoff,
                )
            )
        )
        old_optouts = old_optouts_result.scalars().all()
        for lead in old_optouts:
            # We don't delete leads for audit trail; just mark as archived
            lead.do_not_contact = True
            lead.tags = (lead.tags or []) + ["archived_dnc"]
            logger.info(f"DNC sync: archived old opt-out lead {lead.id}")

        await db.commit()
        logger.info(f"DNC sync complete: {len(bounced_ids)} bounced, {len(old_optouts)} archived")
        return {"bounced_marked": len(bounced_ids), "old_optouts_archived": len(old_optouts)}


async def _generate_daily_report_async():
    """Generate daily analytics report."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        # Pipeline counts
        pipeline_result = await db.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        pipeline = {status.value: 0 for status in LeadStatus}
        for status, count in pipeline_result.all():
            pipeline[status.value] = count

        # New leads today
        new_leads = await db.scalar(
            select(func.count(Lead.id))
            .where(Lead.created_at >= yesterday_start)
            .where(Lead.created_at < today_start)
        )

        # Emails sent today
        emails_sent = await db.scalar(
            select(func.count(Interaction.id))
            .where(Interaction.interaction_type == "email")
            .where(Interaction.created_at >= yesterday_start)
            .where(Interaction.created_at < today_start)
        )

        # Meetings booked
        meetings_booked = await db.scalar(
            select(func.count(Lead.id))
            .where(Lead.status == LeadStatus.MEETING_BOOKED)
        )

        # Conversion rate
        contacted = sum(
            pipeline.get(s, 0)
            for s in ["contacted", "engaged", "meeting_booked", "proposal_sent", "negotiating", "closed_won"]
        )
        won = pipeline.get("closed_won", 0)
        conversion_rate = round((won / contacted * 100), 2) if contacted else 0

        report = {
            "date": yesterday_start.date().isoformat(),
            "new_leads": new_leads or 0,
            "emails_sent": emails_sent or 0,
            "meetings_booked": meetings_booked or 0,
            "pipeline": pipeline,
            "conversion_rate": conversion_rate,
            "total_leads": sum(pipeline.values()),
        }

        logger.info(f"Daily report generated for {report['date']}: {report}")

        # Paperclip: create report issue
        try:
            from app.services.paperclip import _create_issue
            _create_issue(
                title=f"📊 Daily Report: {report['date']}",
                description=f"""## Daily Summary ({report['date']})

- **New Leads**: {report['new_leads']}
- **Emails Sent**: {report['emails_sent']}
- **Meetings Booked**: {report['meetings_booked']}
- **Total Leads**: {report['total_leads']}
- **Conversion Rate**: {report['conversion_rate']}%

### Pipeline Breakdown
| Stage | Count |
|-------|-------|
| Discovered | {pipeline.get('discovered', 0)} |
| Enriched | {pipeline.get('enriched', 0)} |
| Scored | {pipeline.get('scored', 0)} |
| Contacted | {pipeline.get('contacted', 0)} |
| Engaged | {pipeline.get('engaged', 0)} |
| Meeting Booked | {pipeline.get('meeting_booked', 0)} |
| Proposal Sent | {pipeline.get('proposal_sent', 0)} |
| Negotiating | {pipeline.get('negotiating', 0)} |
| Closed Won | {pipeline.get('closed_won', 0)} |
| Closed Lost | {pipeline.get('closed_lost', 0)} |
""",
                priority="low",
                status="done",
            )
        except Exception:
            pass

        return report


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task
def process_follow_ups():
    """Scheduled task: Process leads that need follow-up. Runs every hour."""
    logger.info("[Celery] Processing follow-ups...")
    try:
        result = asyncio.run(_process_follow_ups_async())
        logger.info(f"[Celery] Follow-ups processed: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Follow-up task failed: {e}")
        raise


@celery_app.task
def enrich_pending_leads():
    """Scheduled task: Auto-enrich newly discovered leads. Runs every 30 minutes."""
    logger.info("[Celery] Auto-enriching pending leads...")
    try:
        result = asyncio.run(_enrich_pending_leads_async())
        logger.info(f"[Celery] Enrichment complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Enrichment task failed: {e}")
        raise


@celery_app.task
def sync_dnc_registry():
    """Scheduled task: Sync Do-Not-Call registry. Runs monthly."""
    logger.info("[Celery] Syncing DNC registry...")
    try:
        result = asyncio.run(_sync_dnc_registry_async())
        logger.info(f"[Celery] DNC sync complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] DNC sync failed: {e}")
        raise


@celery_app.task
def generate_daily_report():
    """Scheduled task: Generate daily analytics report. Runs daily at 8am MT."""
    logger.info("[Celery] Generating daily report...")
    try:
        result = asyncio.run(_generate_daily_report_async())
        logger.info(f"[Celery] Daily report generated: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Daily report failed: {e}")
        raise
