import logging
from typing import Optional

import resend

from app.config import get_settings
from app.models.lead import Lead, LeadStatus, Interaction
from app.utils.ai_client import generate_completion
from app.services.paperclip import on_email_sent, on_email_error

settings = get_settings()
resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)


# Email templates library — optimized based on 2025-2026 B2B benchmarks
# Key principles: <125 words, <7 word subject lines, value-first, 1 CTA, human tone
EMAIL_TEMPLATES = {
    "initial_outreach": {
        "subject": "Quick question about {business_name}",
        "context": "First contact introducing AI voice agents for small businesses. Keep it under 125 words, mention a specific pain point, and ask for a 15-min call.",
    },
    "follow_up_1": {
        "subject": "Following up — {business_name}",
        "context": "Follow-up after no response. Add brief social proof (one sentence about a similar business we helped). Keep it shorter than the first email.",
    },
    "follow_up_2": {
        "subject": "Last try — {business_name}",
        "context": "Final follow-up before breakup. Offer a valuable resource (case study, tip, or insight) relevant to their industry. No guilt trips.",
    },
    "breakup": {
        "subject": "Cerrando tu archivo — {business_name}",
        "context": "Pattern-interrupt breakup email. Tell them you're closing their file but leave the door open. Unexpected, honest tone. This often gets replies from busy people.",
    },
    "booking_confirmation": {
        "subject": "Confirmed — {business_name}",
        "context": "Post-booking confirmation email. Include Cal.com link, prep questions, and what to expect on the call. Build excitement and reduce no-shows.",
    },
    "meeting_request": {
        "subject": "15 min to show you something — {business_name}",
        "context": "Requesting a short demo call",
    },
    "proposal": {
        "subject": "Your AI automation proposal — {business_name}",
        "context": "Sending pricing and service details",
    },
}


class EmailOutreach:
    """
    Email outreach channel with AI-generated personalized content.
    Integrates with Resend for delivery and tracks opens/clicks/bounces.
    """
    
    def __init__(self):
        self.from_email = settings.RESEND_FROM_EMAIL
    
    async def generate_email(
        self,
        lead: Lead,
        template_key: str = "initial_outreach",
        campaign_context: str = "",
        tone: str = "professional",
    ) -> dict:
        """
        Generate a personalized email for a lead using AI.
        
        Returns:
            Dict with subject, body, personalization_notes
        """
        template = EMAIL_TEMPLATES.get(template_key, EMAIL_TEMPLATES["initial_outreach"])
        
        system_prompt = f"""You are an expert sales copywriter for Eko AI Automation, 
a company that provides AI Voice Agents and automation for small local businesses in Denver, CO.

Your emails are:
- Hyper-personalized (mention specific business details)
- Concise (3-4 short paragraphs max)
- Value-focused (not feature-focused)
- Written in {tone} tone
- Include a soft call-to-action (reply or book a call)
- NEVER generic or templated sounding
- Include an unsubscribe link at the bottom

COMPLIANCE:
- Include "[AI-generated message]" disclosure at the top
- Include unsubscribe: "Reply STOP to opt out"
- Do not make false claims"""

        user_prompt = f"""Write a personalized outreach email using template: {template_key}

Business: {lead.business_name}
Category: {lead.category or 'Local business'}
City: {lead.city or 'Denver'}

What we know about them:
- Website: {lead.website or 'N/A'}
- Description: {lead.description or 'N/A'}
- Pain points detected: {', '.join(lead.pain_points or []) or 'N/A'}
- Trigger events: {', '.join(lead.trigger_events or []) or 'N/A'}
- Review summary: {lead.review_summary or 'N/A'}
- Urgency score: {lead.urgency_score or 'N/A'}

Campaign context: {campaign_context or template['context']}

Our services:
- AI Voice Agent that answers calls 24/7
- Lead capture and qualification
- Automated appointment booking
- Missed call recovery
- Starting at $297/month

Return ONLY a JSON object with:
- subject: string (compelling, not salesy)
- body: string (HTML email body, 3-4 paragraphs, personalized)
- personalization_notes: string (what specific detail you used)
- cta: string (the call-to-action used)
"""

        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            json_mode=True,
        )
        
        import json
        try:
            result = json.loads(response)
            # Add compliance footer
            result["body"] = self._add_compliance_footer(result["body"], lead.id)
            return result
        except json.JSONDecodeError:
            logger.error("Failed to parse email generation response")
            return {
                "subject": template["subject"].format(business_name=lead.business_name),
                "body": self._add_compliance_footer(
                    f"<p>Hi there,</p><p>I noticed {lead.business_name} and wanted to reach out...</p>",
                    lead.id
                ),
                "personalization_notes": "Fallback template",
                "cta": "Reply to learn more",
            }
    
    def _add_compliance_footer(self, body: str, lead_id: int) -> str:
        """Add TCPA/CAN-SPAM compliance footer to email."""
        app_url = settings.APP_URL.rstrip("/")
        footer = f"""
<div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999;">
  <p>[AI-generated message] — Eko AI Automation LLC, Denver, CO</p>
  <p>You're receiving this because your business matches our service area.</p>
  <p><a href="{app_url}/api/v1/webhooks/unsubscribe?lead_id={lead_id}">Unsubscribe</a> | Reply STOP to opt out</p>
</div>
"""
        return body + footer

    def _add_tracking_pixel(self, body: str, lead_id: int, message_id: str) -> str:
        """Add 1x1 transparent tracking pixel for open tracking."""
        app_url = settings.APP_URL.rstrip("/")
        pixel_url = f"{app_url}/api/v1/webhooks/track/open?lead_id={lead_id}&message_id={message_id}"
        pixel = f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:block;width:1px;height:1px;" />'
        return body + pixel
    
    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_id: Optional[int] = None,
        business_name: str = "",
        ai_generated: bool = True,
        tags: Optional[list] = None,
        campaign_id: Optional[int] = None,
    ) -> dict:
        """
        Send an email via Resend with tracking pixel embedded.
        
        Returns:
            Resend API response with message_id
        """
        try:
            email_tags = [{"name": "lead_id", "value": str(lead_id)}] if lead_id else []
            if campaign_id:
                email_tags.append({"name": "campaign_id", "value": str(campaign_id)})
            if tags:
                for tag in tags:
                    email_tags.append({"name": tag, "value": "true"})
            
            # Build body with tracking pixel before sending
            tracking_body = body
            if lead_id:
                # Use lead_id as the message_id for the pixel so we can track opens
                # even without knowing the Resend message_id beforehand
                tracking_body = self._add_tracking_pixel(body, lead_id, f"lead_{lead_id}")
            
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": tracking_body,
                "tags": email_tags,
            }
            
            response = resend.Emails.send(params)
            message_id = response.get("id")
            logger.info(f"Email sent to {to_email}: {message_id}")
            
            # Paperclip: log email sent
            try:
                on_email_sent(
                    lead_id=lead_id or 0,
                    business_name=business_name,
                    email=to_email,
                    subject=subject,
                    ai_generated=ai_generated,
                )
            except Exception:
                pass
            
            return {"id": message_id, "status": "sent"}
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            
            # Paperclip: log email error
            try:
                on_email_error(
                    lead_id=lead_id or 0,
                    business_name=business_name,
                    email=to_email,
                    error=str(e),
                )
            except Exception:
                pass
            
            raise
    
    async def generate_and_send(
        self,
        lead: Lead,
        template_key: str = "initial_outreach",
        campaign_context: str = "",
        campaign_id: Optional[int] = None,
    ) -> dict:
        """Generate a personalized email and send it."""
        email_data = await self.generate_email(
            lead=lead,
            template_key=template_key,
            campaign_context=campaign_context,
        )
        
        response = await self.send(
            to_email=lead.email,
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead.id,
            business_name=lead.business_name,
            ai_generated=True,
            tags=["ai_generated", template_key],
            campaign_id=campaign_id,
        )
        
        return {
            **response,
            "subject": email_data["subject"],
            "personalization_notes": email_data.get("personalization_notes", ""),
            "cta": email_data.get("cta", ""),
        }
    
    async def send_sequence(
        self,
        lead: Lead,
        sequence: list,
    ) -> list:
        """
        Send a sequence of emails to a lead.
        
        Args:
            lead: The lead to send to
            sequence: List of dicts with {template_key, delay_days, campaign_context}
        
        Returns:
            List of send results
        """
        results = []
        for step in sequence:
            result = await self.generate_and_send(
                lead=lead,
                template_key=step.get("template_key", "initial_outreach"),
                campaign_context=step.get("campaign_context", ""),
            )
            results.append(result)
        return results
