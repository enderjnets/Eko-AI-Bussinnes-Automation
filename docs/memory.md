# Project Memory — Eko AI Business Automation

**Last updated**: 2026-04-24  
**Current version**: 0.3.0  
**Current phase**: Fase 2 ✅ Complete

---

## What was done (this session)

### Fase 2: Email Outreach + CRM Pipeline + Sequences — COMPLETED

#### Code changes
- **Celery scheduled tasks** (4 tasks implemented, previously all `pass` stubs):
  - `process_follow_ups` — Hourly auto-follow-up engine
  - `enrich_pending_leads` — Every 30 min auto-enrichment
  - `sync_dnc_registry` — Monthly bounce/DNC cleanup
  - `generate_daily_report` — Daily 8am MT analytics report
- **Email Sequences** (drip campaigns):
  - New models: `EmailSequence`, `SequenceStep`, `SequenceEnrollment`
  - New API: CRUD sequences, steps, enrollments, execute with dry-run
  - Step types: email, wait, condition, sms, call
- **Docker Compose**: Added `celery-beat` service, missing env vars
- **Celery beat schedule**: All 4 tasks scheduled in `celery_app.py`

#### Tests
- `tests/test_scheduled.py` — Celery task wrappers + async helpers
- `tests/test_sequences.py` — Sequence schemas, models, API

#### Infra changes
- `docker-compose.yml`: Added `celery-beat`, `YELP_API_KEY`, `SERPAPI_API_KEY`, `PAPERCLIP_API_KEY`, `CORS_ORIGINS`
- `celery_app.py`: Added `beat_schedule` configuration

#### Git
- Version bumped: 0.2.0 → 0.3.0
- CHANGELOG.md updated

#### Paperclip
- Issue **EKO-16** created: `Fase 2 Complete — Email Outreach + CRM Pipeline + Sequences`
- Status: `done`

---

## What was done (previous session)

### Fase 1: Discovery + Research + Dashboard — COMPLETED

- 4 discovery sources: Google Maps, Yelp, LinkedIn, Colorado SOS
- Semantic search with pgvector + OpenAI embeddings
- Frontend improvements: source toggles, semantic search, reactive refresh
- `test_discovery.py` + `test_research.py`

---

## Known issues / next steps

### Blockers for production
| Item | Status | Notes |
|------|--------|-------|
| Colorado SOS | ✅ Working | Official Open Data API |
| Yelp Fusion | ✅ Working | 500 req/day free tier |
| LinkedIn (SerpApi) | ✅ Working | 100 searches/month free tier |
| Google Maps | ⏳ Deferred | Outscraper requires payment. Deferred to later phase |
| Docker | ⚠️ Down | Colima/Docker Desktop not running locally |
| pytest | ⚠️ Blocked | Python 3.14 incompatible with pydantic-core wheels |
| OpenAI API Key | ❌ Placeholder | Required for enrichment, embeddings, AI email gen |
| Resend API Key | ❌ Placeholder | Required for actual email delivery |

### Next priorities (Fase 3)
1. Voice AI integration (Retell / Vapi)
2. Calendar integration (Cal.com webhooks already exist)
3. Authentication system (JWT)
4. Production deployment hardening

---

## Environment

### API Keys configured locally
- `APIFY_API_KEY`: ✅ Configured in `.env`
- `PAPERCLIP_API_KEY`: ✅ Configured in `.env`
- `YELP_API_KEY`: ✅ Configured (free tier)
- `SERPAPI_API_KEY`: ✅ Configured (100 searches/month free)
- `OUTSCRAPER_API_KEY`: ❌ Not configured
- `OPENAI_API_KEY`: ❌ Not configured
- `RESEND_API_KEY`: ❌ Not configured

### Services status
| Service | URL | Status |
|---------|-----|--------|
| Paperclip UI | http://100.88.47.99:3100 | ✅ Online |
| Paperclip API | http://100.88.47.99:3100/api | ✅ Online |
| Eko Backend | http://localhost:8000 | ❌ Not running |
| Eko Frontend | http://localhost:3000 | ❌ Not running |
| PostgreSQL | localhost:5432 | ❌ Not running |
| Redis | localhost:6379 | ❌ Not running |

---

## Quick commands

```bash
# Start Docker infrastructure
colima start  # or Docker Desktop
cd ~/Eko-AI-Bussinnes-Automation
docker-compose up -d

# Verify
curl http://localhost:8000/health

# Run tests (inside Docker or after deps installed)
cd backend && pytest tests/ -v
```
