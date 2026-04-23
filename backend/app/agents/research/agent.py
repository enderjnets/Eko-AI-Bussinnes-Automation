import logging
from typing import Optional

from app.models.lead import Lead
from app.schemas.lead import LeadEnrichment
from app.utils.ai_client import generate_completion
from app.agents.research.analyzers.website import WebsiteAnalyzer
from app.services.paperclip import on_research_complete

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Research Agent: Enriches lead data with deep research.
    
    Capabilities:
    - Website analysis (tech stack, features, gaps)
    - Review analysis (sentiment, pain points)
    - Gap analysis (what's missing vs competitors)
    - Scoring (urgency + fit)
    """
    
    def __init__(self):
        self.website_analyzer = WebsiteAnalyzer()
    
    async def enrich(self, lead: Lead) -> LeadEnrichment:
        """
        Run full enrichment pipeline on a lead.
        
        Returns:
            LeadEnrichment with all enriched fields
        """
        logger.info(f"ResearchAgent: enriching lead '{lead.business_name}'")
        
        enrichment = LeadEnrichment()
        
        # 1. Website analysis
        website_data = {}
        if lead.website:
            try:
                website_data = await self.website_analyzer.analyze(lead.website)
                enrichment.tech_stack = website_data.get("technologies_detected", [])
                enrichment.social_profiles = website_data.get("social_links", {})
            except Exception as e:
                logger.warning(f"Website analysis failed for {lead.website}: {e}")
        
        # 2. AI-powered gap analysis and scoring
        try:
            ai_analysis = await self._run_ai_analysis(lead, website_data)
            enrichment.review_summary = ai_analysis.get("review_summary")
            enrichment.trigger_events = ai_analysis.get("trigger_events", [])
            enrichment.pain_points = ai_analysis.get("pain_points", [])
            enrichment.urgency_score = ai_analysis.get("urgency_score", 0)
            enrichment.fit_score = ai_analysis.get("fit_score", 0)
            enrichment.scoring_reason = ai_analysis.get("scoring_reason", "")
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
        """Use LLM to analyze the lead and generate insights."""
        
        system_prompt = """You are an expert sales researcher and business analyst. 
Your job is to analyze a local business and determine:
1. Their likely pain points related to AI automation, customer service, and missed calls
2. Trigger events that indicate they need help now
3. An urgency score (0-100) based on how badly they need AI automation
4. A fit score (0-100) based on how well they match our ideal customer profile
5. A brief scoring reason

Return ONLY a valid JSON object with these exact keys:
- review_summary: string (summary of their online presence)
- trigger_events: array of strings
- pain_points: array of strings  
- urgency_score: number 0-100
- fit_score: number 0-100
- scoring_reason: string (1-2 sentences explaining the scores)

Be honest and data-driven. If there's not much info, give moderate scores with explanation."""

        context = f"""Business Name: {lead.business_name}
Category: {lead.category or 'Unknown'}
City: {lead.city or 'Unknown'}
Description: {lead.description or 'N/A'}
Website: {lead.website or 'N/A'}
Phone: {lead.phone or 'N/A'}

Website Analysis:
- Title: {website_data.get('title', 'N/A')}
- Description: {website_data.get('description', 'N/A')}
- Technologies: {', '.join(website_data.get('technologies_detected', [])) or 'None detected'}
- Has Chatbot: {website_data.get('has_chatbot', False)}
- Has Online Booking: {website_data.get('has_booking', False)}
- Has Contact Form: {website_data.get('has_contact_form', False)}
- Social Links: {list(website_data.get('social_links', {}).keys()) or 'None found'}

Source Data: {lead.source_data or {}}
"""

        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=context,
            temperature=0.4,
            json_mode=True,
        )
        
        import json
        try:
            result = json.loads(response)
            # Validate and clamp scores
            result["urgency_score"] = max(0, min(100, float(result.get("urgency_score", 0))))
            result["fit_score"] = max(0, min(100, float(result.get("fit_score", 0))))
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI analysis JSON: {e}")
            return {
                "review_summary": "Analysis incomplete",
                "trigger_events": [],
                "pain_points": [],
                "urgency_score": 50,
                "fit_score": 50,
                "scoring_reason": "Insufficient data for accurate scoring",
            }
