# Project Memory — Eko AI Business Automation

**Last updated**: 2026-04-26
**Current version**: 0.6.5
**Current phase**: Discovery City Dropdowns for All States ✅ Complete

---

## What was done (this session)

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
| Google Maps | ⏳ Deferred | Outscraper requires payment |
| pytest | ⚠️ Blocked | Python 3.14 incompatible with pydantic-core |
| OpenAI API Key | ❌ Placeholder | Kimi replaces OpenAI |
| Resend API Key | ❌ Placeholder | Required for actual email delivery |
| Cal.com API Key | ❌ Placeholder | Required for live calendar sync |

### Frontend gaps identified
1. **Campaign "Create" button** — Dead/non-functional
2. **Calendar "Create Booking"** — Only list + cancel exist
3. **Lead detail TypeScript** — Build passes but audit flagged potential issues

### Next priorities (Fase 3-4)
1. Voice AI integration (Retell / Vapi)
2. Production deployment hardening
3. Analytics dashboard enhancements
4. Fix campaign creation flow
5. Add calendar booking creation UI

---

## Environment

### API Keys configured
- `KIMI_API_KEY`: ✅ Configured
- `YELP_API_KEY`: ✅ Configured (free tier)
- `SERPAPI_API_KEY`: ✅ Configured
- `PAPERCLIP_API_KEY`: ✅ Configured
- `OUTSCRAPER_API_KEY`: ❌ Placeholder
- `OPENAI_API_KEY`: ❌ Not configured
- `RESEND_API_KEY`: ❌ Not configured
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
