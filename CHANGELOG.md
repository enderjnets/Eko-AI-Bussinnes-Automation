# Changelog

## [0.2.0] — 2026-04-24

### Fase 1 Complete: Discovery + Research + Dashboard

#### Discovery Sources
- **Yelp** — Web scraping source with BeautifulSoup + httpx
- **LinkedIn** — Apify actor integration (`harvestapi/linkedin-company`)
- **Colorado SOS** — Official Colorado Open Data API (Socrata) + Apify fallback
- Multi-source selection UI in DiscoveryForm (Google Maps, Yelp, LinkedIn, Colorado SOS)

#### Semantic Search
- New `POST /api/v1/leads/search` endpoint using pgvector + OpenAI embeddings
- Automatic embedding generation on lead creation and enrichment
- Semantic search toggle in Leads page frontend

#### UX Improvements
- Removed `window.location.reload()` anti-pattern from dashboard
- Added reactive `refreshTrigger` to RecentLeads component
- CORS origins now configurable via `CORS_ORIGINS` env var

#### Tests
- `tests/test_discovery.py` — Google Maps, Yelp, LinkedIn, Colorado SOS sources
- `tests/test_research.py` — ResearchAgent enrichment pipeline

#### Infrastructure
- Added `beautifulsoup4` to requirements
- Added `ApifyClient` service for actor orchestration
- Added `update_lead_embedding` utility for vector search

---

## [0.1.0] — 2026-04-07

### MVP Release
- FastAPI backend with async SQLAlchemy + pgvector
- Next.js 14 frontend with Tailwind CSS
- DiscoveryAgent (Google Maps via Outscraper)
- ResearchAgent (Website analysis + GPT-4o scoring)
- EmailOutreach (Resend + AI-generated templates)
- CRM Pipeline with 10 stages
- Paperclip integration for agent traceability
- Docker Compose setup (PostgreSQL, Redis, backend, frontend, Celery)
