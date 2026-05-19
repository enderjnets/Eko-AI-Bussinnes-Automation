import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_, func

from app.tasks.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.models.workspace import Workspace, WorkspaceMember  # noqa: F401
from app.models.user import User
from app.models.lead import Lead, LeadStatus, Interaction
from app.models.payment import Payment  # noqa: F401 - needed for Lead mapper resolution
from app.models.landing_page import LandingPage  # noqa: F401 - needed for Lead.landing_page_id FK resolution
from app.models.landing_page_visit import LandingPageVisit  # noqa: F401
from app.models.campaign import Campaign, CampaignLead
from app.models.sequence import EmailSequence, SequenceStep, SequenceEnrollment, SequenceStatus, SequenceStepType
from app.agents.outreach.channels.email import EmailOutreach
from app.templates.emails.outreach_email import render_outreach_email
from app.agents.research.agent import ResearchAgent
from app.services.paperclip import on_system_alert, on_email_sent, on_email_error
from app.utils.ai_client import generate_embedding
from app.utils.geocoding import geocode_address as _geocode_address

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
                    content=response.get("body", ""),
                    email_status="sent",
                    email_message_id=response.get("id"),
                    meta={
                        "auto_follow_up": True,
                        "follow_up_number": follow_up_count + 1,
                        "template": template_key,
                    }
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


async def _execute_sequences_async():
    """Execute pending sequence steps for active enrollments."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        email = EmailOutreach()
        
        # Get active sequences
        seq_result = await db.execute(
            select(EmailSequence).where(EmailSequence.status == SequenceStatus.ACTIVE)
        )
        sequences = seq_result.scalars().all()
        
        total_executed = 0
        total_skipped = 0
        total_errors = 0
        
        for seq in sequences:
            # Get steps ordered
            steps_result = await db.execute(
                select(SequenceStep)
                .where(SequenceStep.sequence_id == seq.id)
                .order_by(SequenceStep.position)
            )
            steps = steps_result.scalars().all()
            
            if not steps:
                continue
            
            # Get enrollments ready for next step
            enrollments_result = await db.execute(
                select(SequenceEnrollment)
                .where(SequenceEnrollment.sequence_id == seq.id)
                .where(SequenceEnrollment.status == "active")
                .where(
                    (SequenceEnrollment.next_step_at == None) |
                    (SequenceEnrollment.next_step_at <= now)
                )
            )
            enrollments = enrollments_result.scalars().all()
            
            for enrollment in enrollments:
                lead_result = await db.execute(
                    select(Lead).where(Lead.id == enrollment.lead_id)
                )
                lead = lead_result.scalar_one_or_none()
                
                if not lead or lead.do_not_contact:
                    enrollment.status = "exited"
                    await db.commit()
                    continue
                
                # Check if lead has progressed beyond contacted (e.g., meeting booked)
                # If so, auto-pause the sequence
                if lead.status in [LeadStatus.MEETING_BOOKED, LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATING, LeadStatus.CLOSED_WON]:
                    enrollment.status = "paused"
                    enrollment.meta = {**(enrollment.meta or {}), "auto_paused_reason": "lead_converted"}
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
                    enrollment.completed_at = now
                    seq.leads_completed += 1
                    await db.commit()
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
                            lead.last_contact_at = now
                        
                        # Record interaction
                        interaction = Interaction(
                            lead_id=lead.id,
                            interaction_type="email",
                            direction="outbound",
                            subject=response.get("subject", ""),
                            content=response.get("body", body or ""),
                            email_status="sent",
                            email_message_id=response.get("id"),
                            meta={
                                "sequence_id": seq.id,
                                "sequence_name": seq.name,
                                "step_position": current_step.position,
                                "template": template_key,
                            },
                        )
                        db.add(interaction)
                        total_executed += 1
                        
                    elif current_step.step_type == SequenceStepType.WAIT:
                        total_skipped += 1
                    
                    # Advance to next step
                    enrollment.current_step_position = current_step.position + 1
                    next_step = None
                    for step in steps:
                        if step.position > current_step.position:
                            next_step = step
                            break
                    
                    if next_step and next_step.step_type == SequenceStepType.WAIT:
                        enrollment.next_step_at = now + timedelta(hours=next_step.delay_hours or 24)
                    elif next_step:
                        enrollment.next_step_at = now
                    else:
                        enrollment.status = "completed"
                        enrollment.completed_at = now
                        seq.leads_completed += 1
                    
                    await db.commit()
                    
                except Exception as e:
                    logger.error(f"Sequence execution failed for lead {lead.id} in sequence {seq.id}: {e}")
                    total_errors += 1
                    # Don't advance step on error — retry next hour
        
        logger.info(f"Sequence execution complete: {total_executed} sent, {total_skipped} skipped, {total_errors} errors")
        return {"executed": total_executed, "skipped": total_skipped, "errors": total_errors}


async def _remind_scheduled_calls_async():
    """Log reminders for scheduled calls that are due today."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59)
        
        result = await db.execute(
            select(Lead)
            .where(Lead.next_call_at >= today_start)
            .where(Lead.next_call_at <= today_end)
            .where(Lead.do_not_contact == False)
            .where(Lead.status.not_in([LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST, LeadStatus.CHURNED]))
            .order_by(Lead.next_call_at)
            .limit(50)
        )
        leads = result.scalars().all()
        
        for lead in leads:
            interaction = Interaction(
                lead_id=lead.id,
                interaction_type="note",
                direction="outbound",
                content=f"Reminder: scheduled call due today for {lead.business_name}",
                meta={"reminder": True, "scheduled_call": True, "phone": lead.phone},
            )
            db.add(interaction)
            logger.info(f"Call reminder: {lead.business_name} ({lead.phone})")
        
        await db.commit()
        return {"reminders_logged": len(leads)}


async def _send_demo_reminders_async():
    """Send reminder emails for upcoming demos (24h and 1h before)."""
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        from app.models.booking import Booking, BookingStatus

        # Window: 23h-25h from now = 24h reminder
        window_24h_start = now + timedelta(hours=23)
        window_24h_end = now + timedelta(hours=25)

        # Window: 0.75h-1.25h from now = 1h reminder
        window_1h_start = now + timedelta(minutes=45)
        window_1h_end = now + timedelta(minutes=75)

        result = await db.execute(
            select(Booking)
            .where(Booking.status == BookingStatus.CONFIRMED)
            .where(Booking.start_time > now)
            .where(
                (Booking.start_time >= window_24h_start) & (Booking.start_time <= window_24h_end) |
                (Booking.start_time >= window_1h_start) & (Booking.start_time <= window_1h_end)
            )
            .limit(50)
        )
        bookings = result.scalars().all()

        email = EmailOutreach()
        sent_count = 0

        for booking in bookings:
            lead_result = await db.execute(select(Lead).where(Lead.id == booking.lead_id))
            lead = lead_result.scalar_one_or_none()
            if not lead or not lead.email:
                continue

            meta = booking.meta or {}
            reminders_sent = meta.get("reminders_sent", [])

            # Determine which reminder to send
            hours_until = (booking.start_time - now).total_seconds() / 3600

            if 23 <= hours_until <= 25 and "24h" not in reminders_sent:
                subject = f"Recordatorio: Tu demo con Eko AI es mañana"
                body = f"""<p>Hola,</p>
<p>Este es un recordatorio de que tienes una <strong>demo con Eko AI</strong> programada para mañana:</p>
<ul>
<li><strong>Fecha:</strong> {booking.start_time.strftime('%A, %d de %B')}</li>
<li><strong>Hora:</strong> {booking.start_time.strftime('%I:%M %p')} ({booking.timezone})</li>
<li><strong>Duración:</strong> 15 minutos</li>
</ul>
<p>En esta demo te mostraremos exactamente cómo un agente de IA puede manejar las llamadas, citas y seguimiento de <strong>{lead.business_name}</strong>.</p>
<p><strong>¿Necesitas reagendar?</strong> <a href="https://cal.com/ender-ocando-lfxtkn/15min">Haz clic aquí</a></p>
<p>¡Nos vemos pronto!<br>Eko AI Team</p>"""
                try:
                    await email.send(
                        to_email=lead.email,
                        subject=subject,
                        body=body,
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        ai_generated=False,
                        tags=["demo_reminder", "24h"],
                    )
                    reminders_sent.append("24h")
                    meta["reminders_sent"] = reminders_sent
                    booking.meta = meta
                    sent_count += 1
                    logger.info(f"Sent 24h reminder for booking {booking.id}")
                except Exception:
                    logger.exception(f"Failed to send 24h reminder for booking {booking.id}")

            elif 0.75 <= hours_until <= 1.25 and "1h" not in reminders_sent:
                subject = f"Tu demo con Eko AI comienza en 1 hora"
                body = f"""<p>Hola,</p>
<p>Tu <strong>demo con Eko AI</strong> comienza en aproximadamente 1 hora:</p>
<ul>
<li><strong>Hora:</strong> {booking.start_time.strftime('%I:%M %p')} ({booking.timezone})</li>
<li><strong>Duración:</strong> 15 minutos</li>
</ul>
<p>Te mostraremos cómo la IA puede automatizar <strong>{lead.business_name}</strong> — llamadas, citas, seguimiento, todo automático.</p>
<p><strong>¿Necesitas reagendar?</strong> <a href="https://cal.com/ender-ocando-lfxtkn/15min">Haz clic aquí</a></p>
<p>¡Nos vemos en un momento!<br>Eko AI Team</p>"""
                try:
                    await email.send(
                        to_email=lead.email,
                        subject=subject,
                        body=body,
                        lead_id=lead.id,
                        business_name=lead.business_name,
                        ai_generated=False,
                        tags=["demo_reminder", "1h"],
                    )
                    reminders_sent.append("1h")
                    meta["reminders_sent"] = reminders_sent
                    booking.meta = meta
                    sent_count += 1
                    logger.info(f"Sent 1h reminder for booking {booking.id}")
                except Exception:
                    logger.exception(f"Failed to send 1h reminder for booking {booking.id}")

        await db.commit()
        return {"reminders_sent": sent_count}


async def _enrich_pending_leads_async(batch_size: int = 100):
    """Auto-enrich newly discovered leads that haven't been enriched yet."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lead)
            .where(Lead.status == LeadStatus.DISCOVERED)
            .where(Lead.do_not_contact == False)
            .limit(batch_size)
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
                if lead.urgency_score is not None and lead.fit_score is not None:
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
                    meta={"dnc_reason": "bounced", "bounce_count": 3},
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
# Backup helpers
# ---------------------------------------------------------------------------

import json
import os
import subprocess
from datetime import datetime

BACKUP_DIR = "/app/backups"


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


async def _backup_database_async():
    """Create a pg_dump backup of the entire database."""
    _ensure_backup_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"eko_ai_backup_{timestamp}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    # Get DB connection details from environment
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://eko:eko_dev_pass@db:5432/eko_ai")
    # Parse asyncpg URL to psycopg2 format for pg_dump
    # e.g. postgresql+asyncpg://eko:eko_dev_pass@db:5432/eko_ai -> postgresql://eko:eko_dev_pass@db:5432/eko_ai
    pg_url = db_url.replace("+asyncpg", "")

    try:
        result = subprocess.run(
            ["pg_dump", "--no-owner", "--no-privileges", "-f", filepath, pg_url],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info(f"Database backup saved: {filepath}")
            return {"success": True, "file": filename, "path": filepath}
        else:
            logger.error(f"pg_dump failed: {result.stderr}")
            return {"success": False, "error": result.stderr}
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return {"success": False, "error": str(e)}


async def _backup_processed_leads_async():
    """Export leads with status != DISCOVERED to JSON (enriched, scored, contacted, etc.)."""
    _ensure_backup_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"processed_leads_{timestamp}.json"
    filepath = os.path.join(BACKUP_DIR, filename)

    async with AsyncSessionLocal() as db:
        # Use raw SQL to avoid ORM mapper dependency issues
        from sqlalchemy import text
        result = await db.execute(
            text("""
                SELECT id, business_name, category, description, email, phone, website,
                       address, city, state, zip_code, country, latitude, longitude,
                       source, status, tech_stack, social_profiles, review_summary,
                       trigger_events, pain_points, urgency_score, fit_score, total_score,
                       scoring_reason, website_real, services, pricing_info, business_hours,
                       about_text, team_names, proposal_suggestion, assigned_to, tags, notes,
                       created_at, updated_at
                FROM leads
                WHERE status != 'DISCOVERED'
                ORDER BY updated_at DESC
            """)
        )
        rows = result.mappings().all()

        leads_data = []
        for row in rows:
            lead_dict = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in dict(row).items()}
            leads_data.append(lead_dict)

        backup = {
            "exported_at": datetime.utcnow().isoformat(),
            "total_processed_leads": len(leads_data),
            "leads": leads_data,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)

        logger.info(f"Processed leads backup saved: {filepath} ({len(leads_data)} leads)")
        return {"success": True, "file": filename, "count": len(leads_data), "path": filepath}


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


@celery_app.task
def backup_database():
    """Scheduled task: Backup entire database with pg_dump. Runs daily at 3am MT."""
    logger.info("[Celery] Running database backup...")
    try:
        result = asyncio.run(_backup_database_async())
        logger.info(f"[Celery] Database backup complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Database backup failed: {e}")
        raise


@celery_app.task
def backup_processed_leads():
    """Scheduled task: Export processed leads (enriched, scored, etc.) to JSON. Runs every 2 hours."""
    logger.info("[Celery] Running processed leads backup...")
    try:
        result = asyncio.run(_backup_processed_leads_async())
        logger.info(f"[Celery] Processed leads backup complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Processed leads backup failed: {e}")
        raise




@celery_app.task
def execute_sequences():
    """Scheduled task: Execute pending sequence steps. Runs every hour."""
    logger.info("[Celery] Executing sequences...")
    try:
        result = asyncio.run(_execute_sequences_async())
        logger.info(f"[Celery] Sequence execution complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Sequence execution failed: {e}")
        raise


@celery_app.task
def remind_scheduled_calls():
    """Scheduled task: Log reminders for calls due today. Runs daily at 9am MT."""
    logger.info("[Celery] Reminding scheduled calls...")
    try:
        result = asyncio.run(_remind_scheduled_calls_async())
        logger.info(f"[Celery] Call reminders complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Call reminders failed: {e}")
        raise


@celery_app.task
def enrich_single_lead(lead_id: int):
    """Enrich a single lead by ID."""
    asyncio.run(_enrich_single_lead_async(lead_id))


@celery_app.task
def send_demo_reminders():
    """Scheduled task: Send demo reminder emails (24h and 1h before). Runs every 15 minutes."""
    logger.info("[Celery] Sending demo reminders...")
    try:
        result = asyncio.run(_send_demo_reminders_async())
        logger.info(f"[Celery] Demo reminders complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Demo reminders failed: {e}")
        raise


@celery_app.task
def send_payment_reminders():
    """Scheduled task: Send payment reminders to past_due subscribers. Runs daily."""
    logger.info("[Celery] Sending payment reminders...")
    try:
        result = asyncio.run(_send_payment_reminders_async())
        logger.info(f"[Celery] Payment reminders complete: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Payment reminders failed: {e}")
        raise


async def _send_payment_reminders_async():
    """Send payment reminder emails to leads that are past_due for > 3 days."""
    from app.agents.outreach.channels.email import EmailOutreach

    async with AsyncSessionLocal() as db:
        three_days_ago = datetime.utcnow() - timedelta(days=3)

        result = await db.execute(
            select(Lead)
            .where(Lead.subscription_status == "past_due")
            .where(Lead.past_due_since <= three_days_ago)
            .where(Lead.do_not_contact == False)
            .limit(50)
        )
        leads = result.scalars().all()

        email = EmailOutreach()
        sent = 0

        for lead in leads:
            try:
                context = f"""
                El cliente {lead.business_name or lead.name} tiene un pago fallido de su suscripción Eko AI.
                Plan: {lead.payment_plan or 'Starter'}.
                Días vencido: {(datetime.utcnow() - (lead.past_due_since or datetime.utcnow())).days}.
                Mensaje a enviar: Recordatorio amable de que el pago mensual sigue pendiente.
                Instrucciones para actualizar método de pago. El servicio seguirá activo durante el periodo de gracia.
                """
                await email.generate_and_send(
                    lead=lead,
                    template_key="payment_failed",
                    campaign_context=context,
                )
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send payment reminder to lead {lead.id}: {e}")

        return {"reminders_sent": sent, "leads_checked": len(leads)}


async def _enrich_single_lead_async(lead_id: int):
    """Async helper to enrich one lead."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            logger.warning(f"Lead {lead_id} not found")
            return
        if lead.status != LeadStatus.DISCOVERED:
            logger.info(f"Lead {lead_id} already processed (status={lead.status})")
            # Still try geocoding if missing coordinates
            if lead.address and (lead.latitude is None or lead.longitude is None):
                try:
                    coords = await _geocode_address(
                        address=lead.address,
                        city=lead.city or "",
                        state=lead.state or "",
                        zip_code=lead.zip_code or "",
                        lead_id=lead_id,
                    )
                    if coords:
                        lead.latitude = coords["lat"]
                        lead.longitude = coords["lng"]
                        await db.commit()
                        logger.info(f"Geocoded lead {lead_id}: {coords['lat']}, {coords['lng']}")
                except Exception as e:
                    logger.warning(f"Geocoding failed for lead {lead_id}: {e}")
            return

        try:
            agent = ResearchAgent()
            enrichment = await agent.enrich(lead)

            for field, value in enrichment.model_dump(exclude_unset=True).items():
                setattr(lead, field, value)

            if lead.urgency_score is not None and lead.fit_score is not None:
                lead.total_score = (lead.urgency_score + lead.fit_score) / 2
                lead.status = LeadStatus.SCORED
            else:
                lead.status = LeadStatus.ENRICHED

            await db.commit()
            logger.info(f"Enriched lead {lead_id} '{lead.business_name}' → {lead.status.value}")
        except Exception as e:
            logger.warning(f"Failed to enrich lead {lead_id}: {e}")


async def _run_lead_pipeline_async(lead_id: int):
    """Run enrichment + initial outreach for a single lead."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            logger.warning(f"Lead {lead_id} not found for pipeline")
            return
        
        # Geocode if missing coordinates
        if lead.address and (lead.latitude is None or lead.longitude is None):
            try:
                coords = await _geocode_address(
                    address=lead.address,
                    city=lead.city or "",
                    state=lead.state or "",
                    zip_code=lead.zip_code or "",
                    lead_id=lead_id,
                )
                if coords:
                    lead.latitude = coords["lat"]
                    lead.longitude = coords["lng"]
                    await db.commit()
                    logger.info(f"Geocoded lead {lead_id}: {coords['lat']}, {coords['lng']}")
            except Exception as e:
                logger.warning(f"Geocoding failed for lead {lead_id}: {e}")

        # Skip if already contacted or beyond
        if lead.status in [LeadStatus.CONTACTED, LeadStatus.ENGAGED, LeadStatus.MEETING_BOOKED, LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATING, LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST]:
            logger.info(f"Lead {lead_id} already contacted (status={lead.status})")
            return

        # Step 1: Enrichment (only if still discovered)
        if lead.status == LeadStatus.DISCOVERED:
            try:
                agent = ResearchAgent()
                enrichment = await agent.enrich(lead)
                for field, value in enrichment.model_dump(exclude_unset=True).items():
                    setattr(lead, field, value)
                if lead.urgency_score is not None and lead.fit_score is not None:
                    lead.total_score = (lead.urgency_score + lead.fit_score) / 2
                    lead.status = LeadStatus.SCORED
                else:
                    lead.status = LeadStatus.ENRICHED
                await db.commit()
                await db.refresh(lead)
                logger.info(f"Enriched lead {lead_id} -> {lead.status.value}")

                # Generate/update embedding with enriched data
                try:
                    embed_text = f"{lead.business_name or ''} {lead.category or ''} {lead.city or ''} {lead.state or ''} {', '.join(lead.services or [])} {lead.about_text or ''}".strip()
                    if embed_text:
                        lead.embedding = await generate_embedding(embed_text)
                        await db.commit()
                        logger.info(f"Generated embedding for lead {lead_id}")
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for lead {lead_id}: {e}")
            except Exception as e:
                logger.warning(f"Pipeline enrichment failed for lead {lead_id}: {e}")
                return

        # Step 2: Initial outreach email (run if enriched, scored, or discovered)
        if lead.email and lead.status in [LeadStatus.DISCOVERED, LeadStatus.ENRICHED, LeadStatus.SCORED]:
            try:
                email = EmailOutreach()
                subject = f"Quick question about {lead.business_name}"
                body = f"Hi {lead.business_name},\n\nI came across your business and wanted to reach out.\n\nBest regards"
                res = await email.send(
                    to_email=lead.email,
                    subject=subject,
                    body=body,
                    lead_id=lead.id,
                    business_name=lead.business_name,
                )
                if lead.status not in [LeadStatus.CONTACTED, LeadStatus.ENGAGED, LeadStatus.MEETING_BOOKED]:
                    lead.status = LeadStatus.CONTACTED
                await db.commit()

                # Record outbound interaction
                try:
                    msg_id = res.get("id") or ""
                    interaction = Interaction(
                        lead_id=lead.id,
                        interaction_type="email",
                        direction="outbound",
                        subject=subject,
                        content=body,
                        email_status="sent",
                        email_message_id=msg_id,
                        meta={"auto_outreach": True, "source": "pipeline"},
                    )
                    db.add(interaction)
                    await db.commit()
                    logger.info(f"Recorded interaction for lead {lead_id}: subject='{subject}', msg_id='{msg_id}'")
                except Exception as ie:
                    await db.rollback()
                    logger.exception(f"Failed to record interaction for lead {lead_id}: {ie}")

                logger.info(f"Sent initial outreach to lead {lead_id}")
            except Exception as e:
                logger.warning(f"Pipeline email failed for lead {lead_id}: {e}")


async def _enrich_and_welcome_lead_async(lead_id: int):
    """Enrich a landing-page lead and send the AI Analysis email."""
    from app.services.lead_analysis_generator import generate_analysis_email
    from app.services.tts_generator import generate_tts_audio, build_voice_script
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            logger.warning(f"[Celery] Lead {lead_id} not found for enrichment")
            return {"status": "not_found"}

        if not lead.email:
            logger.info(f"[Celery] Lead {lead_id} has no email, skipping")
            return {"status": "no_email"}

        # 1. Enrich
        logger.info(f"[Celery] Enriching lead {lead_id} ({lead.business_name})...")
        try:
            research = ResearchAgent()
            enriched = await research.enrich(lead)
            for field, value in enriched.model_dump(exclude_unset=True).items():
                setattr(lead, field, value)
            if lead.urgency_score is not None and lead.fit_score is not None:
                lead.total_score = (lead.urgency_score + lead.fit_score) / 2
                lead.status = LeadStatus.SCORED
            else:
                lead.status = LeadStatus.ENRICHED
            await db.commit()
            await db.refresh(lead)
            logger.info(f"[Celery] Lead {lead_id} enriched. Score: {lead.total_score}")
        except Exception as e:
            logger.error(f"[Celery] Enrichment failed for lead {lead_id}: {e}")
            # Send fallback generic welcome email so lead isn't left hanging
            try:
                outreach = EmailOutreach()
                await outreach.generate_and_send(lead=lead, template_key="nurture_welcome")
                logger.info(f"[Celery] Fallback welcome email sent to lead {lead_id}")
            except Exception as e2:
                logger.error(f"[Celery] Fallback email also failed: {e2}")
            return {"status": "enrichment_failed", "error": str(e)}

        # 1b. Generate voice note (TTS)
        audio_url = None
        try:
            lang = (lead.language or "en").lower()[:2]
            voice_script = build_voice_script(lead, lang=lang)
            audio_path = f"/app/static/audio/lead_{lead_id}.mp3"
            audio_result = await generate_tts_audio(
                text=voice_script,
                language=lang,
                output_path=audio_path,
            )
            if audio_result:
                audio_url = f"https://ender-rog.tail25dc73.ts.net/audio/lead_{lead_id}.mp3"
                logger.info(f"[Celery] TTS audio generated for lead {lead_id}: {audio_url}")
        except Exception as e:
            logger.warning(f"[Celery] TTS generation failed for lead {lead_id}: {e}")

        # 2. Generate analysis HTML
        try:
            analysis_html = generate_analysis_email(lead, audio_url=audio_url)
        except Exception as e:
            logger.error(f"[Celery] Analysis generation failed for lead {lead_id}: {e}")
            analysis_html = ""

        # 3. Wrap in professional email template and send
        try:
            outreach = EmailOutreach()
            lang = (lead.language or "en").lower()[:2]
            if lang == "es":
                subject = f"Tu análisis de automatización para {lead.business_name}"
            else:
                subject = f"Your AI automation analysis for {lead.business_name}"
            app_url = outreach.from_email.split("@")[-1] if "@" in outreach.from_email else "ekoai.io"
            tracking_pixel = outreach._add_tracking_pixel("", lead.id, f"lead_{lead.id}") if hasattr(outreach, "_add_tracking_pixel") else ""
            full_html = render_outreach_email(
                subject=subject,
                email_content=analysis_html,
                unsubscribe_url=f"https://{app_url}/api/v1/webhooks/unsubscribe?lead_id={lead.id}",
                tracking_pixel=tracking_pixel,
            )
            await outreach.send(
                to_email=lead.email,
                subject=subject,
                body=full_html,
                lead_id=lead.id,
                business_name=lead.business_name,
                ai_generated=True,
                tags=["ai_analysis", "landing_page"],
                is_full_html=True,
            )
            logger.info(f"[Celery] AI Analysis email sent to lead {lead_id}")
            
            # Record the email interaction in the database
            try:
                interaction = Interaction(
                    lead_id=lead.id,
                    interaction_type="email",
                    direction="outbound",
                    subject=subject,
                    content=analysis_html[:500] if analysis_html else "",
                    email_status="sent",
                    meta={
                        "source": "landing_page",
                        "ai_generated": True,
                        "audio_url": audio_url,
                        "tags": ["ai_analysis", "landing_page"],
                    },
                )
                db.add(interaction)
                await db.commit()
                logger.info(f"[Celery] Email interaction recorded for lead {lead_id}")
            except Exception as ie:
                await db.rollback()
                logger.exception(f"[Celery] Failed to record email interaction for lead {lead_id}")
        except Exception as e:
            logger.error(f"[Celery] Failed to send analysis email to lead {lead_id}: {e}")
            return {"status": "email_failed", "error": str(e)}

        # 4. Advance nurture sequence enrollment to start next steps in 2 days
        try:
            seq_result = await db.execute(
                select(EmailSequence).where(EmailSequence.name == "Landing Page Nurturing")
            )
            seq = seq_result.scalar_one_or_none()
            if seq:
                enr_result = await db.execute(
                    select(SequenceEnrollment).where(
                        SequenceEnrollment.sequence_id == seq.id,
                        SequenceEnrollment.lead_id == lead.id,
                        SequenceEnrollment.status == "active",
                    )
                )
                enrollment = enr_result.scalar_one_or_none()
                if enrollment:
                    enrollment.next_step_at = datetime.utcnow() + timedelta(days=2)
                    await db.commit()
                    logger.info(f"[Celery] Lead {lead_id} nurture sequence advanced to {enrollment.next_step_at}")
        except Exception as e:
            logger.warning(f"[Celery] Failed to advance nurture sequence for lead {lead_id}: {e}")

        return {"status": "sent", "lead_id": lead_id}


@celery_app.task(bind=True, max_retries=2)
def enrich_and_welcome_lead(self, lead_id: int):
    """Celery task: enrich a landing-page lead and send the AI Analysis email."""
    logger.info(f"[Celery] enrich_and_welcome_lead started for lead {lead_id}")
    try:
        result = asyncio.run(_enrich_and_welcome_lead_async(lead_id))
        logger.info(f"[Celery] enrich_and_welcome_lead complete for {lead_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] enrich_and_welcome_lead failed for {lead_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def run_lead_pipeline(self, lead_id: int):
    """Celery task: enrich lead and send initial outreach email."""
    logger.info(f"[Celery] Running lead pipeline for lead {lead_id}...")
    try:
        result = asyncio.run(_run_lead_pipeline_async(lead_id))
        logger.info(f"[Celery] Lead pipeline complete for {lead_id}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Lead pipeline failed for {lead_id}: {e}")
        raise self.retry(exc=e, countdown=60)
