"""Discovery source using Yelp Fusion API (official, free tier available)."""

from typing import List, Dict, Optional
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

YELP_FUSION_BASE_URL = "https://api.yelp.com/v3"


class YelpSource:
    """Discovery source using Yelp Fusion API.

    Get a free API key at: https://www.yelp.com/developers/v3/manage_app
    Free tier: 500 requests/day.
    """

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.YELP_API_KEY or ""
        self.client = httpx.AsyncClient(
            base_url=YELP_FUSION_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def search(
        self,
        query: str,
        city: str,
        state: Optional[str] = "CO",
        radius_miles: int = 25,
        max_results: int = 50,
    ) -> List[Dict]:
        """Search for businesses on Yelp."""
        if not self.api_key:
            logger.warning("Yelp Fusion API key not configured. Get one free at https://www.yelp.com/developers/v3/manage_app")
            return []

        location = f"{city}, {state}"
        radius_meters = min(int(radius_miles * 1609.34), 40000)  # Max 40km
        limit = min(max_results, 50)  # Yelp max per request

        logger.info(f"Yelp Fusion search: '{query}' in {location}")

        try:
            resp = await self.client.get(
                "/businesses/search",
                params={
                    "term": query,
                    "location": location,
                    "radius": radius_meters,
                    "limit": limit,
                    "sort_by": "best_match",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            businesses = data.get("businesses", [])
        except Exception as e:
            logger.error(f"Yelp Fusion API error: {e}")
            return []

        leads = []
        for biz in businesses:
            lead = self._normalize_business(biz)
            if lead:
                leads.append(lead)

        logger.info(f"Yelp Fusion returned {len(leads)} leads")
        return leads

    def _normalize_business(self, biz: Dict) -> Optional[Dict]:
        """Normalize Yelp Fusion business data to Lead format."""
        name = biz.get("name", "").strip()
        if not name:
            return None

        # Location
        location = biz.get("location", {})
        address_parts = location.get("display_address", [])
        address = ", ".join(address_parts) if address_parts else None
        city = location.get("city") or None
        state = location.get("state") or None
        zip_code = location.get("zip_code") or None
        country = location.get("country") or "US"

        # Coordinates
        coordinates = biz.get("coordinates", {})
        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")

        # Categories
        categories = biz.get("categories", [])
        category = categories[0].get("title") if categories else None

        # Rating / reviews
        rating = biz.get("rating")
        review_count = biz.get("review_count")
        description_parts = []
        if rating is not None:
            description_parts.append(f"{rating} stars on Yelp")
        if review_count:
            description_parts.append(f"{review_count} reviews")
        description = " | ".join(description_parts) if description_parts else None

        return {
            "business_name": name,
            "category": category,
            "description": description,
            "email": None,
            "phone": biz.get("phone") or biz.get("display_phone") or None,
            "website": biz.get("url") or None,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            "source": "yelp",
            "source_data": biz,
        }
