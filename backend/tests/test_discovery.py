"""Tests for Discovery agents and sources."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.discovery.agent import DiscoveryAgent
from app.agents.discovery.sources.google_maps import GoogleMapsSource
from app.agents.discovery.sources.yelp import YelpSource
from app.agents.discovery.sources.linkedin import LinkedInSource
from app.agents.discovery.sources.colorado_sos import ColoradoSOSSource


@pytest.fixture
def mock_google_maps_result():
    return {
        "name": "Test Business",
        "address": "123 Main St",
        "city": "Denver",
        "state": "CO",
        "phone": "555-1234",
        "website": "https://test.com",
        "category": "Restaurant",
        "latitude": 39.7392,
        "longitude": -104.9903,
    }


class TestGoogleMapsSource:
    def test_normalize_place_complete(self, mock_google_maps_result):
        source = GoogleMapsSource()
        result = source._normalize_place(mock_google_maps_result)
        assert result["business_name"] == "Test Business"
        assert result["city"] == "Denver"
        assert result["state"] == "CO"
        assert result["phone"] == "555-1234"
        assert result["source"] == "google_maps"

    def test_normalize_place_missing_name(self):
        source = GoogleMapsSource()
        result = source._normalize_place({"address": "123 Main St"})
        assert result is None

    def test_normalize_place_parse_address(self):
        source = GoogleMapsSource()
        place = {
            "name": "Another Biz",
            "full_address": "456 Oak Ave, Boulder, CO 80301",
        }
        result = source._normalize_place(place)
        assert result["city"] == "Boulder"
        assert result["state"] == "CO"


class TestYelpSource:
    def test_normalize_business_complete(self):
        source = YelpSource()
        biz = {
            "name": "Yelp Biz",
            "rating": 4.5,
            "review_count": 120,
            "phone": "+15551234567",
            "display_phone": "(555) 123-4567",
            "url": "https://yelp.com/biz/test",
            "categories": [{"alias": "coffee", "title": "Coffee & Tea"}],
            "location": {
                "display_address": ["789 Pine St", "Denver, CO 80202"],
                "city": "Denver",
                "state": "CO",
                "zip_code": "80202",
                "country": "US",
            },
            "coordinates": {"latitude": 39.7, "longitude": -104.9},
        }
        result = source._normalize_business(biz)
        assert result["business_name"] == "Yelp Biz"
        assert result["category"] == "Coffee & Tea"
        assert result["phone"] == "+15551234567"
        assert result["city"] == "Denver"
        assert result["state"] == "CO"
        assert result["source"] == "yelp"
        assert "4.5 stars" in result["description"]

    def test_normalize_business_missing_name(self):
        source = YelpSource()
        result = source._normalize_business({"rating": 5.0})
        assert result is None

    def test_no_api_key_returns_empty(self):
        source = YelpSource(api_key="")
        import asyncio
        result = asyncio.run(source.search("restaurants", "Denver"))
        assert result == []


class TestDiscoveryAgent:
    @pytest.mark.asyncio
    async def test_deduplication(self):
        agent = DiscoveryAgent()
        agent.google_maps = AsyncMock()
        agent.google_maps.search.return_value = [
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Unique", "city": "Denver", "source": "google_maps"},
        ]

        results = await agent.discover("restaurants", "Denver", sources=["google_maps"])
        assert len(results) == 2
        names = [r["business_name"] for r in results]
        assert "Dup" in names
        assert "Unique" in names

class TestLinkedInSource:
    def test_normalize_company_complete(self):
        source = LinkedInSource()
        company = {
            "companyName": "LinkedIn Corp",
            "industry": "Software",
            "about": "Professional networking platform",
            "companyUrl": "https://linkedin.com",
            "linkedinUrl": "https://linkedin.com/company/linkedin",
            "locations": [{"city": "Sunnyvale", "state": "CA", "country": "US"}],
            "employeeCount": 20000,
        }
        result = source._normalize_company(company)
        assert result["business_name"] == "LinkedIn Corp"
        assert result["category"] == "Software"
        assert result["city"] == "Sunnyvale"
        assert result["state"] == "CA"
        assert result["source"] == "linkedin"
        assert result["source_data"]["employee_count"] == 20000

    def test_normalize_company_missing_name(self):
        source = LinkedInSource()
        result = source._normalize_company({"industry": "Tech"})
        assert result is None

    def test_normalize_company_flat_location(self):
        source = LinkedInSource()
        company = {
            "name": "Flat Co",
            "city": "Denver",
            "state": "CO",
            "country": "US",
            "industry": "Consulting",
        }
        result = source._normalize_company(company)
        assert result["city"] == "Denver"
        assert result["state"] == "CO"


class TestDiscoveryAgent:
    @pytest.mark.asyncio
    async def test_deduplication(self):
        agent = DiscoveryAgent()
        agent.google_maps = AsyncMock()
        agent.google_maps.search.return_value = [
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Unique", "city": "Denver", "source": "google_maps"},
        ]

        results = await agent.discover("restaurants", "Denver", sources=["google_maps"])
        assert len(results) == 2
        names = [r["business_name"] for r in results]
        assert "Dup" in names
        assert "Unique" in names

class TestColoradoSOSSource:
    def test_normalize_entity_complete(self):
        source = ColoradoSOSSource()
        entity = {
            "entity_name": "Acme LLC",
            "entity_type": "Limited Liability Company",
            "status": "Good Standing",
            "document_number": "20201234567",
            "formation_date": "01/15/2020",
            "principal_address": "123 Main St, Denver, CO 80202",
        }
        result = source._normalize_entity(entity)
        assert result["business_name"] == "Acme LLC"
        assert result["category"] == "Limited Liability Company"
        assert result["state"] == "CO"
        assert result["source"] == "colorado_sos"
        assert "Good Standing" in result["description"]
        assert result["source_data"]["document_number"] == "20201234567"

    def test_normalize_entity_missing_name(self):
        source = ColoradoSOSSource()
        result = source._normalize_entity({"status": "Good Standing"})
        assert result is None

    def test_normalize_entity_flat_fields(self):
        source = ColoradoSOSSource()
        entity = {
            "name": "Flat LLC",
            "entityType": "LLC",
            "entityStatus": "Active",
            "city": "Boulder",
            "state": "CO",
        }
        result = source._normalize_entity(entity)
        assert result["business_name"] == "Flat LLC"
        assert result["city"] == "Boulder"

    def test_parse_result_row_valid(self):
        source = ColoradoSOSSource()
        from bs4 import BeautifulSoup
        html = """
        <tr>
            <td>Test Biz</td>
            <td>20201234567</td>
            <td>Good Standing</td>
            <td>Corporation</td>
            <td>01/01/2020</td>
        </tr>
        """
        row = BeautifulSoup(html, "html.parser").tr
        result = source._parse_result_row(row)
        assert result is not None
        assert result["entity_name"] == "Test Biz"
        assert result["document_number"] == "20201234567"

    def test_parse_result_row_header(self):
        source = ColoradoSOSSource()
        from bs4 import BeautifulSoup
        html = """
        <tr>
            <th>Business Name</th>
            <th>Document Number</th>
        </tr>
        """
        row = BeautifulSoup(html, "html.parser").tr
        result = source._parse_result_row(row)
        assert result is None


class TestDiscoveryAgent:
    @pytest.mark.asyncio
    async def test_deduplication(self):
        agent = DiscoveryAgent()
        agent.google_maps = AsyncMock()
        agent.google_maps.search.return_value = [
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Dup", "city": "Denver", "source": "google_maps"},
            {"business_name": "Unique", "city": "Denver", "source": "google_maps"},
        ]

        results = await agent.discover("restaurants", "Denver", sources=["google_maps"])
        assert len(results) == 2
        names = [r["business_name"] for r in results]
        assert "Dup" in names
        assert "Unique" in names

    @pytest.mark.asyncio
    async def test_multiple_sources(self):
        agent = DiscoveryAgent()
        agent.google_maps = AsyncMock()
        agent.yelp = AsyncMock()
        agent.linkedin = AsyncMock()
        agent.colorado_sos = AsyncMock()
        agent.google_maps.search.return_value = [
            {"business_name": "GM", "city": "Denver", "source": "google_maps"},
        ]
        agent.yelp.search.return_value = [
            {"business_name": "Yelp", "city": "Denver", "source": "yelp"},
        ]
        agent.linkedin.search.return_value = [
            {"business_name": "Linked", "city": "Denver", "source": "linkedin"},
        ]
        agent.colorado_sos.search.return_value = [
            {"business_name": "SOS", "city": "Denver", "source": "colorado_sos"},
        ]

        results = await agent.discover("restaurants", "Denver", sources=["google_maps", "yelp", "linkedin", "colorado_sos"])
        assert len(results) == 4
        result_sources = [r["source"] for r in results]
        assert "google_maps" in result_sources
        assert "yelp" in result_sources
        assert "linkedin" in result_sources
        assert "colorado_sos" in result_sources
