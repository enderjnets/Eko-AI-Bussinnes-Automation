from typing import List, Dict, Optional
import logging

from app.agents.discovery.sources.google_maps import GoogleMapsSource
from app.services.paperclip import on_discovery_complete

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    """
    Discovery Agent: Finds potential leads from multiple sources.
    
    Currently supports:
    - Google Maps (via Outscraper)
    
    Future sources:
    - LinkedIn
    - Yelp
    - Colorado Secretary of State
    - Job boards
    """
    
    def __init__(self):
        self.google_maps = GoogleMapsSource()
    
    async def discover(
        self,
        query: str,
        city: str,
        state: Optional[str] = "CO",
        radius_miles: int = 25,
        max_results: int = 50,
        sources: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Run discovery across configured sources.
        
        Args:
            query: Business category or search term
            city: Target city
            state: State code (default: CO)
            radius_miles: Search radius
            max_results: Max results per source
            sources: List of source names to use (default: all)
        
        Returns:
            List of normalized lead dictionaries
        """
        sources = sources or ["google_maps"]
        all_leads = []
        
        logger.info(f"DiscoveryAgent: searching '{query}' in {city}, {state}")
        
        if "google_maps" in sources:
            try:
                gmaps_leads = await self.google_maps.search(
                    query=query,
                    city=city,
                    state=state,
                    radius_miles=radius_miles,
                    max_results=max_results,
                )
                all_leads.extend(gmaps_leads)
                logger.info(f"Google Maps returned {len(gmaps_leads)} leads")
            except Exception as e:
                logger.error(f"Google Maps discovery failed: {e}")
        
        # TODO: Add more sources (LinkedIn, Yelp, etc.)
        
        # Deduplicate by business_name + city
        seen = set()
        unique_leads = []
        for lead in all_leads:
            key = (lead.get("business_name", "").lower(), lead.get("city", "").lower())
            if key not in seen and lead.get("business_name"):
                seen.add(key)
                unique_leads.append(lead)
        
        logger.info(f"DiscoveryAgent: {len(unique_leads)} unique leads found")
        
        # Paperclip: log discovery run
        try:
            on_discovery_complete(
                query=query,
                city=city,
                leads_found=len(all_leads),
                leads_created=len(unique_leads),
            )
        except Exception:
            pass  # Never break main flow
        
        return unique_leads
