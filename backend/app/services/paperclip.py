"""
Paperclip client — AI Company Control Plane integration.

Cada operación importante del sistema genera un issue en Paperclip
para trazabilidad completa del pipeline de ventas.

Company: Eko AI Business Automation (EKO)
"""

import os
import logging
from typing import Optional

import requests

from app.config import get_settings

settings = get_settings()

PAPERCLIP_API = settings.PAPERCLIP_API_URL or "http://100.88.47.99:3100"
COMPANY_ID = settings.PAPERCLIP_COMPANY_ID or "a5151f95-51cd-4d2d-a35b-7d7cb4f4102e"
PAPERCLIP_API_KEY = settings.PAPERCLIP_API_KEY

HEADERS = {
    "Authorization": f"Bearer {PAPERCLIP_API_KEY}",
    "Content-Type": "application/json",
}
TIMEOUT = 10

log = logging.getLogger(__name__)


def _create_issue(
    title: str,
    description: str,
    priority: str = "medium",
    status: str = "todo",
) -> Optional[str]:
    """Create a Paperclip issue. Returns issue ID or None."""
    if not PAPERCLIP_API_KEY:
        log.debug("Paperclip not configured, skipping issue creation")
        return None

    try:
        r = requests.post(
            f"{PAPERCLIP_API}/api/companies/{COMPANY_ID}/issues",
            json={
                "title": title,
                "description": description,
                "priority": priority,
                "status": status,
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.ok:
            issue = r.json()
            identifier = issue.get("identifier", "?")
            log.info(f"📋 Paperclip: {identifier} — {title}")
            return issue.get("id")
        else:
            log.warning(f"Paperclip issue creation failed: {r.status_code} {r.text}")
    except Exception as e:
        log.debug(f"Paperclip unavailable: {e}")
    return None


def _update_issue(
    issue_id: Optional[str],
    status: Optional[str] = None,
    comment: Optional[str] = None,
):
    """Update issue status or add comment."""
    if not issue_id or not PAPERCLIP_API_KEY:
        return

    try:
        if status:
            requests.patch(
                f"{PAPERCLIP_API}/api/issues/{issue_id}",
                json={"status": status},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
        if comment:
            requests.post(
                f"{PAPERCLIP_API}/api/issues/{issue_id}/comments",
                json={"body": comment},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
    except Exception:
        pass


# =============================================================================
# EVENT-SPECIFIC HOOKS (called from agents & API routers)
# =============================================================================


def on_discovery_complete(
    query: str,
    city: str,
    leads_found: int,
    leads_created: int,
):
    """Called when DiscoveryAgent finishes a search."""
    return _create_issue(
        title=f"🔍 Discovery: {leads_found} leads found for '{query}' in {city}",
        description=f"## Discovery Run\n- Query: `{query}`\n- City: {city}\n- Leads found: {leads_found}\n- Leads created (new): {leads_created}\n\nStatus: done",
        priority="low" if leads_found < 10 else "medium",
        status="done",
    )


def on_research_complete(
    lead_id: int,
    business_name: str,
    urgency_score: float,
    fit_score: float,
    pain_points: list,
):
    """Called when ResearchAgent enriches a lead."""
    total_score = (urgency_score + fit_score) / 2
    priority = "high" if total_score >= 70 else "medium" if total_score >= 50 else "low"

    pain_text = "\n".join(f"- {p}" for p in (pain_points or [])) or "N/A"

    return _create_issue(
        title=f"🔬 Research: {business_name} scored {total_score:.0f}/100",
        description=f"## Enrichment Results\n- Lead ID: {lead_id}\n- Business: {business_name}\n- Urgency: {urgency_score:.0f}/100\n- Fit: {fit_score:.0f}/100\n- **Total: {total_score:.0f}/100**\n\n### Pain Points\n{pain_text}",
        priority=priority,
        status="done",
    )


def on_email_sent(
    lead_id: int,
    business_name: str,
    email: str,
    subject: str,
    ai_generated: bool = True,
):
    """Called when OutreachAgent sends an email."""
    return _create_issue(
        title=f"📧 Email sent to {business_name}",
        description=f"## Outreach\n- Lead ID: {lead_id}\n- To: {email}\n- Subject: `{subject}`\n- AI-generated: {'Yes' if ai_generated else 'No'}\n\nStatus: sent",
        priority="medium",
        status="done",
    )


def on_email_error(
    lead_id: int,
    business_name: str,
    email: str,
    error: str,
):
    """Called when email sending fails."""
    return _create_issue(
        title=f"❌ Email failed: {business_name}",
        description=f"## Error\n- Lead ID: {lead_id}\n- To: {email}\n- Error: `{error}`\n\nAction needed: verify email deliverability",
        priority="high",
        status="todo",
    )


def on_lead_status_change(
    lead_id: int,
    business_name: str,
    old_status: str,
    new_status: str,
):
    """Called when a lead moves to a significant pipeline stage."""
    significant_transitions = {
        "scored": ("medium", "Lead scored and ready for outreach"),
        "contacted": ("medium", "First contact made"),
        "engaged": ("high", "Lead responded — active conversation"),
        "meeting_booked": ("high", "Meeting scheduled"),
        "proposal_sent": ("high", "Proposal delivered"),
        "closed_won": ("high", "🎉 DEAL CLOSED"),
        "closed_lost": ("medium", "Deal lost — schedule reactivation"),
    }

    if new_status not in significant_transitions:
        return None

    prio, desc = significant_transitions[new_status]
    return _create_issue(
        title=f"🔄 Pipeline: {business_name} → {new_status}",
        description=f"## Status Change\n- Lead ID: {lead_id}\n- Business: {business_name}\n- From: `{old_status}`\n- To: `{new_status}`\n\n{desc}",
        priority=prio,
        status="done" if new_status in ["closed_won", "closed_lost"] else "in_progress",
    )


def on_campaign_launched(
    campaign_id: int,
    campaign_name: str,
    target_city: str,
    lead_count: int,
):
    """Called when a campaign is launched."""
    return _create_issue(
        title=f"🚀 Campaign launched: {campaign_name}",
        description=f"## Campaign\n- ID: {campaign_id}\n- Name: {campaign_name}\n- Target: {target_city}\n- Leads: {lead_count}\n\nStatus: active",
        priority="medium",
        status="in_progress",
    )


def on_system_alert(
    alert_type: str,
    details: str,
    priority: str = "high",
):
    """Called for system alerts/errors."""
    return _create_issue(
        title=f"⚠️ {alert_type}",
        description=f"## Alert\n{details}\n\nTime: auto-generated",
        priority=priority,
        status="todo",
    )
