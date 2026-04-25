# Changelog

## [0.5.0] — 2026-04-24

### Calendar Integration + Booking System

#### Backend
- **Booking model** (`app/models/booking.py`) — tracks meetings locally with Cal.com sync
- **Calendar router** (`app/api/v1/calendar.py`):
  - `GET /calendar/event-types` — List Cal.com event types
  - `POST /calendar/availability` — Get available time slots
  - `GET /calendar/bookings` — List bookings with filters (upcoming, by lead, by status)
  - `POST /calendar/bookings` — Create booking for a lead (syncs with Cal.com if configured)
  - `POST /calendar/bookings/{id}/cancel` — Cancel booking locally and on Cal.com
  - `POST /calendar/send-link` — Send booking link via email to a lead
- **CRM integration**: `POST /crm/{lead_id}/send-booking-link` — Send booking link directly from pipeline
- **Webhook handler** (`/webhooks/calcom`) already existed — auto-updates lead to `MEETING_BOOKED` on Cal.com booking

#### Frontend
- **Calendar page** (`frontend/app/calendar/page.tsx`) — View upcoming/all/past meetings, cancel bookings, join video links
- **Navbar** updated with Calendar navigation link
- **API client** updated with `calendarApi` methods

#### Tests
- `tests/test_calendar.py` — Booking model enums, calendar API endpoints, schemas

---

## [0.4.0] — 2026-04-24

### Auth System: JWT + Protected Routes + Multi-tenancy

#### Backend
- **User model** (`app/models/user.py`) with roles: `admin`, `manager`, `agent`
- **JWT security** (`app/core/security.py`): password hashing (bcrypt), access/refresh tokens, `get_current_user` dependency, role-based guards (`get_current_admin`)
- **Auth router** (`app/api/v1/auth.py`):
  - `POST /auth/login` — JWT token pair
  - `POST /auth/register` — Admin-only user creation
  - `POST /auth/refresh` — Token refresh
  - `GET /auth/me` — Current user profile
  - `PATCH /auth/me` — Update profile
  - `GET /auth/users` — List users (admin)
  - `POST /auth/dev-login` — Development bypass (creates admin dev user)
- **Protected routes**: All existing API endpoints now require Bearer token (`leads`, `campaigns`, `crm`, `sequences`, `emails`, `analytics`)
- **Multi-tenancy**: Non-admin users only see leads they own or are assigned to; `owner_id` auto-assigned on lead creation/discovery

#### Frontend
- **Auth context** (`frontend/contexts/AuthContext.tsx`): login state, auto-redirect, token persistence in localStorage
- **Login page** (`frontend/app/login/page.tsx`): email/password form + dev login button
- **API client** (`frontend/lib/api.ts`): Axios interceptors inject Bearer token; auto-redirect to `/login` on 401
- **Navbar** updated: displays current user name/role + logout button
- **Route protection**: Unauthenticated users redirected to `/login`

#### Tests
- `tests/test_auth.py` — Password hashing, JWT encode/decode, token expiration, role-based access control, router endpoints

---

## [0.3.0] — 2026-04-24

### Fase 2 Complete: Email Outreach + CRM Pipeline + Sequences

#### Celery Scheduled Tasks (Implemented)
- **`process_follow_ups`** — Hourly task: finds leads with `next_follow_up_at <= now`, sends AI-generated follow-up emails, records interactions, respects rate limits and cooldowns
- **`enrich_pending_leads`** — Every 30 min: auto-enriches `DISCOVERED` leads via `ResearchAgent`, auto-scores and transitions to `ENRICHED`/`SCORED`
- **`sync_dnc_registry`** — Monthly: marks leads with 3+ bounces as `do_not_contact`, archives opt-outs older than 2 years (CPA Colorado compliance)
- **`generate_daily_report`** — Daily at 8am MT: pipeline summary, new leads, emails sent, conversion rate; logged to Paperclip

#### Email Sequences (Drip Campaigns)
- New models: `EmailSequence`, `SequenceStep`, `SequenceEnrollment`
- New API: `GET/POST/PATCH /api/v1/sequences`, steps CRUD, enroll leads, execute sequences
- Sequence step types: `email`, `wait`, `condition`, `sms`, `call`
- Dry-run mode for testing sequences before live execution
- Auto-advances enrolled leads through steps with configurable delays

#### Infrastructure
- Added `celery-beat` service to `docker-compose.yml` with scheduled tasks
- `celery_app.py` now includes `beat_schedule` with all 4 tasks
- Added missing env vars to docker-compose: `YELP_API_KEY`, `SERPAPI_API_KEY`, `PAPERCLIP_API_KEY`, `CORS_ORIGINS`

#### Tests
- `tests/test_scheduled.py` — Celery task wrappers and async helpers
- `tests/test_sequences.py` — Sequence schemas, models, and API logic

---

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
