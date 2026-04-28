# Project Memory — Eko AI Business Automation

**Last updated**: 2026-04-28
**Current version**: 0.7.0
**Current phase**: FASE 8 — AI Proposal Generator + Voice & Email Reply Agents ✅ Complete

---

## What was done (this session)

### v0.7.0 — FASE 8: AI Proposal Generator + Email Reply Agent + VAPI Voice Agent — COMPLETED

#### Phase 1 — Proposal Engine
- **Model `proposals`** — New PostgreSQL table with share_token, brand colors, content, status tracking
- **Brand Extractor** (`services/brand_extractor.py`) — Scrapes lead websites to extract primary/secondary colors and logo URL
- **AI Proposal Generator** (`services/proposal_generator.py`) — Generates personalized HTML proposals using lead context + deal info + brand colors
- **API endpoints** (`/api/v1/proposals`):
  - CRUD, generate AI content, send (creates public link), duplicate
  - Public endpoints: `GET /public/{token}`, `POST /public/{token}/accept`, `POST /public/{token}/reject`
- **Frontend**:
  - `/proposals` — List with stats, filters, search
  - `/proposals/[id]` — Editor with HTML preview / raw HTML / plain text tabs, color pickers, AI generate button
  - `/proposals/public/[token]` — Public page for clients with Accept/Reject buttons
- **Navbar + Dashboard** — Added Propuestas quick-access card

#### Phase 2 — AI Email Reply Agent
- **Service** (`services/email_reply_agent.py`) — Context-aware reply generation using lead history, conversation thread, tone selection (professional/friendly/assertive/consultative)
- **API endpoints** (`/api/v1/emails`):
  - `POST /{interaction_id}/ai-reply` — Generates AI reply, stores in interaction meta
  - `POST /{interaction_id}/send-reply` — Sends approved reply via Resend, creates outbound interaction
  - `GET /{interaction_id}/conversation` — Full email thread for context
- **Frontend Inbox** — "Responder con IA" button opens modal with tone/length selectors, conversation preview, editable AI response, send/regenerate

#### Phase 3 — VAPI Voice Agent
- **VAPI Client** (`services/vapi_client.py`) — Create calls, list calls, create/update assistants, build sales assistant prompts
- **API endpoints** (`/api/v1/voice-agent`):
  - `POST /calls` — Initiates outbound call to lead via VAPI with custom instructions
  - `GET /calls` — Lists call history with interest levels
  - `GET /calls/{id}` — Detail with VAPI call data
  - `POST /assistants` — Creates VAPI voice assistant
- **Webhook** (`/webhooks/vapi`) — Receives `end-of-call-report`, `status-update`, `conversation-update`; updates PhoneCall records with transcripts, summaries, interest levels
- **Frontend `/voice-agent`** — Stats cards, call list with result badges, modal to start calls with lead search + custom instructions
- **Navbar + Dashboard** — Added Voice Agent quick-access card

#### Pipeline Kanban Fix
- **Root cause**: `@tanstack/react-virtual` v3 collapsed viewport to 0px in flex columns with `max-h` + `flex-1`
- **Fix**: Removed virtualizer entirely; replaced with simple scroll + `.map()` + "Cargar más" pagination button
- **Auth fix**: Non-admin users now see public leads (`owner_id IS NULL`) in pipeline
- **DB migration**: Added missing `brand_primary_color`, `brand_secondary_color`, `brand_logo_url` columns to `leads` table

#### Database Snapshot (v0.7.0)
| Status | Count |
|--------|-------|
| DISCOVERED | 19 |
| ENRICHED | 29 |
| SCORED | 478 |
| ENGAGED | 1 |
| **Total** | **527** |

---

### v0.6.7 — Complete US Cities Dataset from Census Bureau — COMPLETED

#### DiscoveryForm All States Expanded
- Generated city dataset from **US Census Bureau 2019 population data** (~19,500 places)
- **Top 30 cities per state** by population
- All states and cities **sorted alphabetically**
- Cleaned census suffixes: removed "city", "town", "CDP", "balance", "borough", etc.
- Fixed special cases: Nashville, Louisville, Lexington, Augusta, Macon, Butte, Winston-Salem, etc.
- Total: **51 states + DC = ~1,415 cities**

---

### v0.6.6 — Added Greenwood Village + expanded Colorado cities — COMPLETED

#### DiscoveryForm Colorado Cities
- Added 15 more Colorado cities: Highlands Ranch, Parker, Castle Rock, Littleton, Englewood, Arvada, Brighton, Commerce City, Wheat Ridge, Greenwood Village, Lafayette, Louisville, Golden, Durango, Montrose
- Colorado now has 30 cities total (was 15)

---

### v0.6.5 — Discovery City Dropdowns for All 51 States — COMPLETED

#### DiscoveryForm City Dropdowns (All States)
- Created `frontend/lib/us-cities.ts` with **~600 cities** across all 51 US states + DC
- Each state has 10-15 of its most populous/well-known cities
- City dropdown now dynamically updates for **any** state selected
- State change handler resets city to the first city of the newly selected state
- Fallback to free-text input if a state has no entries (defensive)

---

### v0.6.4 — Discovery Dynamic City Field — COMPLETED

#### DiscoveryForm City Field
- **Colorado selected** → `<select>` dropdown with 30 Colorado cities
- **Any other state selected** → `<input type="text">` free-text field for city
- **State change handler** resets city to `"Denver"` when switching to Colorado, or `""` when switching to another state
- Prevents impossible combinations like "Denver, California"

---

### v0.6.3 — Discovery Dropdowns + Pipeline Enum Fix + Leads Geo-Crash Fix — COMPLETED

#### Discovery Dropdowns (Homepage)
- **City** — Converted to `<select>` with 30 Colorado cities (Aurora, Boulder, Denver, etc.)
- **State** — Converted to `<select>` with all 50 US states + DC
- **Max results** — Converted to `<select>` with options `[10, 25, 50, 100, 200]`
- These were documented in v0.6.0 changelog but never actually implemented

#### Pipeline Kanban Fix (Empty Columns)
- **Root cause**: SQLAlchemy `Enum` stores Python enum **names** (`DISCOVERED`) in PostgreSQL native enum, not **values** (`discovered`). When `useColumnLeads` sent `?status=discovered`, the backend query `Lead.status == status` generated `WHERE status = 'discovered'` which is invalid in the PG enum.
- **Fix**: Changed all backend `Lead.status` comparisons to use `.name` (`status.name`, `LeadStatus.DISCOVERED.name`) across:
  - `backend/app/api/v1/leads.py` (list, enrichment_status, search)
  - `backend/app/api/v1/analytics.py` (contacted count, closed_won count)
  - `backend/app/tasks/scheduled.py` (enrichment task, daily reports)
- **Frontend hardening**: Added `error` state to `KanbanColumn` — API failures now show "Error cargando leads" instead of silently showing "No leads"

#### `/leads` Page No Results Fix
- **Root cause**: Backend `_haversine_km` used `math.asin(math.sqrt(a))` without clamping `a` to `[0, 1]`. Floating-point drift produced `a > 1`, causing `ValueError` → HTTP 500.
- **Fix**: Clamped `a = min(1.0, max(0.0, a))` in both backend and frontend haversine functions
- **Frontend improvements**:
  - `needsClientSort` now used correctly (was dead code)
  - Added visible `error` state instead of silently swallowing API failures
  - Fixed `useEffect` dependencies to include `search` and `semanticMode`

---

### v0.6.2 — Client-Side Sort Fix + Autocomplete + Deploy — COMPLETED

#### Backend
- **Autocomplete endpoint** — Added `GET /leads/autocomplete/names?q={query}&limit=8` for business name suggestions
- **Client-side sort fallback** — Backend `sort_by` param deployed but frontend also sorts client-side as reliable fallback for score/distance/score_distance modes
- **Haversine distance** — Added client-side Haversine calculation for distance-based sorting

#### Frontend
- **Search autocomplete** — Debounced (250ms) dropdown with matching business names; click sets search + triggers query
- **Client-side sort** — Reliable sort for `score` (desc), `distance` (asc + score tiebreak), `score_distance` (score desc + distance asc)
- **Temporary page_size workaround** — Loads 500 leads when sorting by distance/score_distance for meaningful client-side pagination
- **HQ address configurable** — Saved to `localStorage`, geocoded via Nominatim

#### Deploy / Infrastructure Fix
- **Docker Compose networking** — Fixed `NEXT_PUBLIC_API_URL` to `http://eko-backend:8000` for internal Docker communication
- **Frontend build** — Rebuilt with correct API URL so Next.js rewrites proxy `/api/*` to backend container instead of `localhost:8000`
- **Login restored** — Frontend can now reach backend through internal Docker network; login returns 401 for wrong password (correct behavior)

#### Database Snapshot (v0.6.2)
| Status | Count |
|--------|-------|
| DISCOVERED | ~400 |
| ENRICHED | ~8 |
| SCORED | ~72 |
| **Total** | **480** |

---

### v0.6.1 — Kanban Virtualization + Column Pagination — COMPLETED

#### Backend
- **Kanban pagination index** — Added SQLAlchemy index `(status, id)` on `Lead` model for efficient column pagination
- **Geo-sorting** — Extended `GET /leads` with `lat`, `lng`, `sort_by` params; Haversine distance calculation; `distance_km` in `LeadResponse`

#### Frontend
- **Virtualization** — Installed `@tanstack/react-virtual`, extracted `KanbanColumn`, dynamic measurement, `contain: strict`
- **Per-column infinite pagination** — `useColumnLeads.ts` with `useInfiniteQuery` (50/page per column), scroll-triggered `fetchNextPage`, per-column cache invalidation on lead move
- **QueryProvider fix** — Created `"use client"` `QueryProvider.tsx` to fix Next.js 14 "Only plain objects can be passed to Client Components" error

---

### v0.6.0 — Enrichment Pipeline Hardening — COMPLETED

#### Backend
- **Celery worker fix** — Resolved `InvalidRequestError: expression 'User' failed to locate a name` by creating `app/models/__init__.py`
- **Commit-per-lead** — Both `enrich_pending_leads` and `enrich-all` commit after each lead for real-time UI progress
- **Kimi JSON parsing** — Robust `_extract_json()` with fast path → markdown stripping → brace counting
- **WebsiteFinder hardening** — Blocks `.pdf`, `.gov/`, `.mil/` URLs
- **Yelp pagination** — Offset pagination for 200 results (50 per call)
- **Discovery deduplication** — Fixed `AttributeError` on null city/business_name
- **Cal.com auth fix** — Switched to query param `?apiKey=`

#### Frontend
- **Leads pagination** — Added `page` state + Previous/Next buttons
- **Enrichment progress bar** — Polling every 10s
- **Discovery dropdowns** — `<select>` menus for city/state/max_results
- **API URL consistency** — Relative `/api/v1/...` paths via Next.js rewrites

---

## Previous phases

### v0.5.1 — Kimi Integration (2026-04-24)
### v0.5.0 — Calendar Integration + Booking System (2026-04-24)
### v0.4.0 — Auth System (2026-04-24)
### v0.3.0 — Email Outreach + CRM Pipeline + Sequences (2026-04-24)
### v0.2.0 — Discovery + Research + Dashboard (2026-04-24)

---

## Known issues / next steps

### Blockers for production
| Item | Status | Notes |
|------|--------|-------|
| Colorado SOS | ✅ Working | Official Open Data API |
| Yelp Fusion | ✅ Working | 500 req/day free tier |
| LinkedIn (SerpApi) | ✅ Working | 100 searches/month free tier |
| Auth system | ✅ Working | JWT + RBAC + protected routes |
| Calendar / Booking | ✅ Working | Cal.com integration |
| Kimi AI | ✅ Working | `kimi-for-coding` + sentence-transformers |
| Celery Worker | ✅ Working | Enrichment, follow-ups, DNC sync |
| Docker | ✅ Running | All 6 containers up |
| Proposals (AI) | ✅ Working | Brand extraction + public pages |
| Email Reply Agent | ✅ Working | Context-aware AI replies |
| VAPI Voice Agent | ✅ Working | Outbound calls + webhooks |
| Google Maps | ⏳ Deferred | Outscraper requires payment |
| pytest | ⚠️ Blocked | Python 3.14 incompatible with pydantic-core |
| OpenAI API Key | ❌ Placeholder | Kimi replaces OpenAI |
| Resend API Key | ❌ Placeholder | Required for actual email delivery |
| Cal.com API Key | ❌ Placeholder | Required for live calendar sync |
| VAPI API Key | ❌ Placeholder | Required for live voice calls |

### Frontend gaps identified
1. **Campaign "Create" button** — Dead/non-functional
2. **Calendar "Create Booking"** — Only list + cancel exist
3. **Lead detail TypeScript** — Build passes but audit flagged potential issues

### Next priorities (Fase 9+)
1. Production deployment hardening
2. Analytics dashboard enhancements
3. Fix campaign creation flow
4. Add calendar booking creation UI
5. WhatsApp/SMS integration
6. Advanced proposal templates (industry-specific)

---

## Environment

### API Keys configured
- `KIMI_API_KEY`: ✅ Configured
- `YELP_API_KEY`: ✅ Configured (free tier)
- `SERPAPI_API_KEY`: ✅ Configured
- `PAPERCLIP_API_KEY`: ✅ Configured
- `OUTSCRAPER_API_KEY`: ❌ Placeholder
- `OPENAI_API_KEY`: ❌ Not configured
- `RESEND_API_KEY`: ⚠️ Needs verification (for sending)
- `RESEND_WEBHOOK_SECRET`: ⚠️ Needs configuration in Resend Dashboard
- `CAL_COM_API_KEY`: ❌ Not configured

### Services status (PC ROG @ 100.88.47.99)
| Service | URL | Status |
|---------|-----|--------|
| Paperclip UI | http://100.88.47.99:3100 | ✅ Online |
| Paperclip API | http://100.88.47.99:3100/api | ✅ Online |
| Eko Backend | http://100.88.47.99:8001 | ✅ Running |
| Eko Frontend | http://100.88.47.99:3001 | ✅ Running |
| PostgreSQL | 100.88.47.99:5433 | ✅ Running (healthy) |
| Redis | 100.88.47.99:6380 | ✅ Running (healthy) |
| Celery Worker | — | ✅ Active |
| Celery Beat | — | ✅ Active |

---

## Inbound Email Configuration

### Domain Setup
- **Domain**: `ekoaiautomation.com` (GoDaddy)
- **Subdomain for inbound**: `biz.ekoaiautomation.com` (Resend)
- **Receiving email**: `contact@biz.ekoaiautomation.com`
- **Webhook URL**: `http://100.88.47.99:8000/api/v1/webhooks/resend-inbound`

### DNS Records (GoDaddy)
Add these records in GoDaddy DNS for `ekoaiautomation.com`:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| MX | biz | `inbound-smtp.us-east-1.amazonaws.com` | 600 |
| TXT | biz | `v=spf1 include:amazonses.com ~all` | 600 |
| TXT | resend._domainkey.biz | `[DKIM key from Resend]` | 600 |

### Resend Dashboard Setup
1. Go to Resend Dashboard → Domains → Add Domain → `biz.ekoaiautomation.com`
2. Copy DNS records and add to GoDaddy
3. Wait for verification (5-30 min)
4. Go to Webhooks → Add Webhook
5. URL: `http://100.88.47.99:8000/api/v1/webhooks/resend-inbound`
6. Event: `email.received`
7. Save the Webhook Secret and add to `.env` as `RESEND_WEBHOOK_SECRET`

### Testing
```bash
# Send test email to contact@biz.ekoaiautomation.com
# Check backend logs
docker compose logs -f backend | grep "inbound"
# Check inbox at http://100.88.47.99:3001/inbox
```

## Quick commands

```bash
# SSH to host
ssh enderj@100.88.47.99

# Start / restart Docker infrastructure
cd ~/Eko-AI-Bussinnes-Automation
docker compose up -d --build

# Verify backend health
curl http://100.88.47.99:8001/health

# Watch Celery worker logs
docker compose logs -f celery-worker

# Database counts
docker exec -i eko-db psql -U eko -d eko_ai -c "SELECT status, COUNT(*) FROM leads GROUP BY status;"

# Run tests (inside Docker or after deps installed)
cd backend && pytest tests/ -v
```
