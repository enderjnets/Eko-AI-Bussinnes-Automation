import json
import logging
from typing import Optional

from app.models.lead import Lead
from app.schemas.lead import LeadEnrichment
from app.utils.ai_client import generate_completion
from app.agents.research.analyzers.website import WebsiteAnalyzer
from app.agents.research.finder import WebsiteFinder
from app.services.paperclip import on_research_complete

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Research Agent: Enriches lead data with deep research.

    Capabilities:
    - Find real business website (via search engines)
    - Website analysis (tech stack, features, gaps, services, pricing)
    - Extract contact info (emails, social profiles, team names)
    - AI-powered gap analysis and scoring
    - Generate personalized proposal suggestions
    """

    def __init__(self):
        self.website_analyzer = WebsiteAnalyzer()
        self.website_finder = WebsiteFinder()

    async def enrich(self, lead: Lead) -> LeadEnrichment:
        """
        Run full enrichment pipeline on a lead.

        Returns:
            LeadEnrichment with all enriched fields
        """
        logger.info(f"ResearchAgent: enriching lead '{lead.business_name}'")

        enrichment = LeadEnrichment()

        # 1. Find real website if we only have Yelp/social URL
        website_url = lead.website
        if not website_url or "yelp.com" in website_url or "facebook.com" in website_url:
            try:
                found = await self.website_finder.find_website(
                    lead.business_name, lead.city or "", lead.state or ""
                )
                if found:
                    enrichment.website_real = found
                    website_url = found
                    logger.info(f"Found real website for {lead.business_name}: {found}")
            except Exception as e:
                logger.warning(f"Website finder failed for {lead.business_name}: {e}")

        # 2. Website analysis
        website_data = {}
        if website_url:
            try:
                website_data = await self.website_analyzer.analyze(website_url)
                enrichment.tech_stack = website_data.get("technologies_detected", [])
                enrichment.social_profiles = website_data.get("social_links", {})
                enrichment.services = website_data.get("services", [])
                enrichment.pricing_info = website_data.get("pricing_info")
                enrichment.business_hours = website_data.get("hours")
                enrichment.about_text = website_data.get("about_text")
                enrichment.team_names = website_data.get("team_names", [])

                # Use email found on website if lead has none
                if not lead.email and website_data.get("email_found"):
                    enrichment.email = website_data.get("email_found")

            except Exception as e:
                logger.warning(f"Website analysis failed for {website_url}: {e}")

        # 3. AI-powered analysis and proposal generation
        try:
            ai_analysis = await self._run_ai_analysis(lead, website_data)
            enrichment.review_summary = ai_analysis.get("review_summary")
            enrichment.trigger_events = ai_analysis.get("trigger_events", [])
            enrichment.pain_points = ai_analysis.get("pain_points", [])
            enrichment.urgency_score = ai_analysis.get("urgency_score", 0)
            enrichment.fit_score = ai_analysis.get("fit_score", 0)
            enrichment.scoring_reason = ai_analysis.get("scoring_reason", "")
            enrichment.proposal_suggestion = ai_analysis.get("proposal_suggestion", "")
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")

        # Paperclip: log research completion
        try:
            on_research_complete(
                lead_id=lead.id,
                business_name=lead.business_name,
                urgency_score=enrichment.urgency_score or 0,
                fit_score=enrichment.fit_score or 0,
                pain_points=enrichment.pain_points,
            )
        except Exception:
            pass

        return enrichment

    async def _run_ai_analysis(self, lead: Lead, website_data: dict) -> dict:
        """Use LLM to analyze the lead and generate insights + proposal."""

        system_prompt = """You are an expert sales researcher, business analyst, and proposal writer for an AI automation agency called "Eko AI".

Your job is to deeply analyze a local business and produce a complete assessment that will be used to create a personalized sales proposal.

Analyze the following and return ONLY a valid JSON object with these exact keys:
- review_summary: string (2-3 sentence summary of their online presence, brand positioning, and perceived quality)
- trigger_events: array of strings (specific events or signals that indicate they need AI automation NOW)
- pain_points: array of strings (specific operational problems they likely face that AI can solve)
- urgency_score: number 0-100 (how badly they need help right now based on missing tech, negative signals, etc.)
- fit_score: number 0-100 (how well they match our ideal customer: local service business, high-touch, repeat customers)
- scoring_reason: string (1-2 sentences explaining why you gave those scores)
- proposal_suggestion: string (A 3-5 paragraph personalized proposal pitch. Address the business by name. Mention specific pain points we discovered, reference their services, and explain exactly how Eko AI can help them: missed call AI, appointment booking automation, follow-up sequences, review generation, and CRM pipeline. Be persuasive, specific, and professional.)

Be concise. Keep proposal_suggestion to 3 paragraphs max so it fits in JSON."""

        context = f"""Business Name: {lead.business_name}
Category: {lead.category or 'Unknown'}
City: {lead.city or 'Unknown'}
State: {lead.state or 'Unknown'}
Phone: {lead.phone or 'N/A'}
Current Website: {lead.website or 'N/A'}
Real Website Found: {website_data.get('url', 'N/A')}
Description: {lead.description or 'N/A'}

Website Analysis Results:
- Title: {website_data.get('title', 'N/A')}
- Meta Description: {website_data.get('description', 'N/A')}
- Technologies Used: {', '.join(website_data.get('technologies_detected', [])) or 'None detected'}
- Has Chatbot / Live Chat: {website_data.get('has_chatbot', False)}
- Has Online Booking: {website_data.get('has_booking', False)}
- Has Contact Form: {website_data.get('has_contact_form', False)}
- Has E-commerce: {website_data.get('has_ecommerce', False)}
- Has Blog: {website_data.get('has_blog', False)}
- Has Newsletter: {website_data.get('has_newsletter', False)}
- Has Online Ordering: {website_data.get('has_online_ordering', False)}
- Services Listed: {', '.join(website_data.get('services', [])) or 'None extracted'}
- Pricing Info: {website_data.get('pricing_info', 'N/A')}
- Business Hours: {website_data.get('hours', 'N/A')}
- About Text: {website_data.get('about_text', 'N/A')[:400] if website_data.get('about_text') else 'N/A'}
- Team/Owners: {', '.join(website_data.get('team_names', [])) or 'N/A'}
- Social Links: {list(website_data.get('social_links', {}).keys()) or 'None found'}
- Email Found on Site: {website_data.get('email_found', 'N/A')}

Source Platform: {lead.source or 'Unknown'}
Raw Source Data: {lead.source_data or {}}
"""

        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=context,
            temperature=0.5,
            max_tokens=4000,
            json_mode=True,
        )

        try:
            # Try direct parse first
            result = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            # Try to extract JSON block from markdown or reasoning text
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse extracted JSON: {e}")
                    result = None
            else:
                logger.error(f"No JSON block found in AI response")
                result = None

        if result:
            # Validate and clamp scores
            result["urgency_score"] = max(0, min(100, float(result.get("urgency_score", 0))))
            result["fit_score"] = max(0, min(100, float(result.get("fit_score", 0))))
            return result

        logger.error("AI analysis returned no valid JSON, using fallback")
        return {
            "review_summary": "Analysis incomplete due to parsing error",
            "trigger_events": [],
            "pain_points": [],
            "urgency_score": 50,
            "fit_score": 50,
            "scoring_reason": "Insufficient data for accurate scoring",
            "proposal_suggestion": f"We would love to help {lead.business_name} streamline their operations with AI automation. Contact us to learn more.",
        }
