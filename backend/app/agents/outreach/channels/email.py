import logging
from typing import Optional

import resend

from app.config import get_settings
from app.models.lead import Lead
from app.utils.ai_client import generate_completion
from app.services.paperclip import on_email_sent, on_email_error

settings = get_settings()
resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)


class EmailOutreach:
    """
    Email outreach channel with AI-generated personalized content.
    """
    
    def __init__(self):
        self.from_email = settings.RESEND_FROM_EMAIL
    
    async def generate_email(
        self,
        lead: Lead,
        campaign_context: str = "",
        tone: str = "professional",
    ) -> dict:
        """
        Generate a personalized email for a lead using AI.
        
        Returns:
            Dict with subject and body
        """
        system_prompt = f"""You are a expert sales copywriter for Eko AI Automation, 
a company that provides AI Voice Agents and automation for small local businesses in Denver, CO.

Your emails are:
- Hyper-personalized (mention specific business details)
- Concise (3-4 short paragraphs max)
- Value-focused (not feature-focused)
- Written in {tone} tone
- Include a soft call-to-action (reply or book a call)
- NEVER generic or templated sounding

The email should feel like it was written specifically for THIS business after research."""

        user_prompt = f"""Write a personalized outreach email to:

Business: {lead.business_name}
Category: {lead.category or 'Local business'}
City: {lead.city or 'Denver'}

What we know about them:
- Website: {lead.website or 'N/A'}
- Description: {lead.description or 'N/A'}
- Pain points detected: {', '.join(lead.pain_points or []) or 'N/A'}
- Trigger events: {', '.join(lead.trigger_events or []) or 'N/A'}
- Review summary: {lead.review_summary or 'N/A'}

Campaign context: {campaign_context or 'General outreach about AI voice agents for small businesses'}

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
"""

        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            json_mode=True,
        )
        
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse email generation response")
            return {
                "subject": f"Quick question about {lead.business_name}",
                "body": f"<p>Hi there,</p><p>I noticed {lead.business_name} and wanted to reach out...</p>",
                "personalization_notes": "Fallback template",
            }
    
    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_id: Optional[int] = None,
        business_name: str = "",
        ai_generated: bool = True,
    ) -> dict:
        """
        Send an email via Resend.
        
        Returns:
            Resend API response
        """
        try:
            params: resend.Emails.SendParams = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": body,
                "tags": [{"name": "lead_id", "value": str(lead_id)}] if lead_id else [],
            }
            
            response = resend.Emails.send(params)
            logger.info(f"Email sent to {to_email}: {response.get('id')}")
            
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
            
            return response
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
        campaign_context: str = "",
    ) -> dict:
        """Generate a personalized email and send it."""
        email_data = await self.generate_email(lead, campaign_context)
        
        response = await self.send(
            to_email=lead.email,
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead.id,
            business_name=lead.business_name,
            ai_generated=True,
        )
        
        return response
