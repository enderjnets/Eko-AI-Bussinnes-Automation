

## [0.7.8] — 2026-05-18

### Landing Pages — Celery Worker FK Fix + Generator E2E Verified

Causa raíz: el worker de Celery (`backend/app/tasks/scheduled.py`) NO importaba el modelo `LandingPage`. Cuando un lead se creaba desde una landing page, el FK `leads.landing_page_id → landing_pages.id` no podía resolverse en el registro de SQLAlchemy del worker, abortando con:

```
Foreign key associated with column 'leads.landing_page_id' could not find
table 'landing_pages' with which to generate a foreign key to target column 'id'
```

**Consecuencia silenciosa**: el lead se creaba correctamente vía `/api/v1/leads/public`, se auto-enrollaba en la nurture sequence, PERO el task `enrich_and_welcome_lead` crasheaba — sin enrichment, sin score, **sin email de AI Analysis al cliente**. Los leads que vienen sin landing_page_id (manual, scraped, etc.) funcionaban sin problema porque no tocaban ese FK.

#### CRITICAL fix

- `backend/app/tasks/scheduled.py`: agregados imports `LandingPage` y `LandingPageVisit` (mismo patrón que `Payment` ya tenía con comentario "needed for Lead mapper resolution")

#### Verificación E2E (live ROG)

Generación con Kimi-for-coding (1 LLM call ~40s) — 4 niches en paralelo:

| LP | Niche | HTML | Keys | Status |
|---|---|---|---|---|
| 9 | Restaurante Miami | 16.0 KB | 56/56 | ✓ |
| 10 | Clínica Dental LA | 16.2 KB | 56/56 | ✓ |
| 11 | Gym Boutique | 16.0 KB | 56/56 | ✓ |
| 12 | Spa Beverly Hills | 16.2 KB | 56/56 | ✓ |

Cada niche tiene copy ÚNICO y contextual:

- **Clínica**: "Insurance Verification", "Automated Recalls", testimonial "Spanish-speaking patients love booking via WhatsApp"
- **Gym**: "Churn Prediction", "Milestone Celebrations", testimonial "100th class automatically congratulated"
- **Spa**: "Brand-Voice Booking", "Gift Card Sales 24/7", testimonial "International guests love multilingual support"

#### Pipeline submit→email verificado

Submit en LP 9 (Restaurante) y LP 12 (Spa) con form-encoded body:

```
Lead 612 (Fix Verifier, LP 9):
  - Form submit:         POST /api/v1/leads/public → 201 created
  - Celery enrichment:   started → score 78.5 → status SCORED
  - AI Analysis email:   "Your AI automation analysis for Fix Verifier" sent
  - Nurture sequence:    advanced to 2026-05-21

Lead 613 (Sofia Beverly, LP 12):
  - Form submit:         POST /api/v1/leads/public → 201 created
  - Celery enrichment:   started → score 80.0 → status SCORED
  - AI Analysis email:   "Your AI automation analysis for Sofia Beverly" sent
  - Landing page visit:  recorded in landing_page_visits
```

#### Form schema (verificado en los 4 niches)

```html
<form class="hero-form" action="/api/v1/leads/public?landing_page_id={LP_ID}" method="POST">
  <input type="text"  name="first_name" placeholder="First Name" required>
  <input type="text"  name="last_name"  placeholder="Last Name"  required>
  <input type="email" name="email"      placeholder="Email"      required>
  <input type="tel"   name="phone"      placeholder="Phone"      required>
  <input type="url"   name="website"    placeholder="Website"    required>
  <button type="submit">Get Your Free AI Analysis</button>
</form>
```

#### Memoria

Nueva memoria `feedback_celery_model_imports.md`: cualquier modelo cuyas FKs apunten a tablas de modelos NO importados en `scheduled.py` causarán el mismo bug silencioso. Patrón a copiar: `from app.models.X import X  # noqa: F401 - needed for Y.x_id FK resolution`.


## [0.7.7] — 2026-05-18

### Landing Pages — Route Ordering Fix + Compare Enrichment

Causa raíz: en `backend/app/api/v1/landing_pages.py` las rutas se registraban en orden incorrecto. El path-param `GET /{landing_page_id}` (línea 235) se declaraba ANTES de `GET /track`, `GET /random` y `GET /public/active` (líneas 611-662). FastAPI evalúa rutas en orden de registro, así que cualquier request a `/track` era capturada por `/{landing_page_id}` con `landing_page_id="track"` — y como ese endpoint requiere auth, devolvía **401 Unauthorized** antes incluso de intentar parsear "track" como int. Resultado: el tracking pixel JAMÁS persistía visitas, los analytics siempre mostraban 0 visitas, y el random pool nunca funcionó.

#### CRITICAL fix
- **Rutas concretas movidas ANTES de `/{landing_page_id}`** en `landing_pages.py` — orden nuevo: `/track`, `/random`, `/public/active`, `/public/{slug}`, `/`, `/compare`, `POST /`, luego path-params
- **Visit tracking confirmado**: 3 pixels lp_id=8 → 3 rows nuevas en `landing_page_visits` (37→40 verificado en DB)
- **`/random`** ahora redirige a `/lp/{slug}` (SEO-friendly via nginx) en vez de `/landing?lp=`

#### Fix `/compare`
- Agregadas aggregations `email_replies` (Interaction inbound + email) y `calls_made` (PhoneCall join Lead) por landing_page_id
- Frontend Compare tab ya esperaba estos campos en `LandingPage.analytics` (líneas 44-53 de page.tsx) — ahora se renderizan con valores reales

#### Fix `workspace_id` NULL-safety
- En Postgres `NULL == NULL` devuelve NULL, no TRUE → la lógica "deactivate others in same workspace" silenciosamente fallaba si lp.workspace_id era NULL
- Nuevo helper `_workspace_match(model_col, workspace_id)` que usa `IS NULL` cuando aplica
- Aplicado en `create_landing_page`, `update_landing_page`, `activate_landing_page`, `clone_landing_page` y los slug-uniqueness checks

#### Fix slug uniqueness
- Antes: check global → bloqueaba el slug `"test"` para todos los workspaces
- Ahora: scoped al workspace propio (o NULL si no hay tenant) — workspaces distintos pueden reutilizar slugs

#### Fix DELETE
- `delete_landing_page` ahora borra explícitamente `landing_page_visits` antes de borrar la página (evita FK violation si el modelo no tiene CASCADE)

#### Impacto
- Visit tracking ahora persiste en DB → analytics reflejan visitas reales
- Compare tab muestra email_replies y calls_made (antes `undefined`)
- `/random` y `/public/active` finalmente funcionan (eran dead code)
- Multi-workspace deactivate-others ya no falla silenciosamente

#### Memoria
- Nueva memoria `feedback_fastapi_route_order.md`: "rutas concretas ANTES de path-params en routers FastAPI" — regla de oro confirmada con producción rota durante ~3 semanas


## [0.7.6] — 2026-05-18

### Content Studio — Unified Buffer Snapshot + Rate-limit Banner

Causa raíz: cada uno de los 4 tabs (Publicaciones, Calendario, Analytics, Monitoreo) llamaba a la API GraphQL de Buffer independientemente. PostsList re-fetcheaba en cada filtro y PostCalendar en cada cambio de mes — agotando la cuota free de Buffer (100 calls/15min y 100/día) con sólo navegar el dashboard. Cuando Buffer respondía 429, los 4 tabs se rompían silenciosamente.

#### Nuevo
- **`lib/buffer.ts`** — cliente GraphQL central con 5min fresh + 24h stale + sticky rate-limit hint que corta-circuita llamadas siguientes
- **`/content-api/buffer-snapshot`** — un solo endpoint que devuelve `{channels, posts, limits, rate_limited, rate_limit:{window,reset_at}}` en una sola query GraphQL para que los 4 tabs compartan un fetch
- **`hooks/useBufferData`** — caché compartida module-level + pub/sub para sincronizar todos los componentes
- **`RateLimitBanner`** — banner global que muestra countdown preciso al reset (lee `retry-after` header, no `window:"24h"` engañoso del body)

#### Fix
- **PostsList**: filtro por status ahora es client-side (sin re-fetch); delete/edit optimistas patcheando caché local
- **PostCalendar**: navegación de mes sin re-fetch (usa la misma snapshot que los otros tabs)
- **AnalyticsDashboard**: clase `text-gold` (no existe en Tailwind) reemplazada por `text-yellow-300`; charts muestran "Sin datos" elegantemente en vez de crashear
- **BufferStatus**: empty state amigable cuando no hay canales en caché
- **PipelineHistory**: infiere `completed` por presencia de `scripts[]/produced[]/uploaded[]` (la columna "Content" mostraba "—" aunque generaba scripts correctamente)
- **`/content-api/pipelines`**: pasa arrays compactos de stages para soportar la inferencia anterior

#### Impacto
- Buffer API consumption: 5+ calls por dashboard load → **1 call compartida** (caché 5min)
- Cuando rate-limited: corta-circuita instant, evita quemar más quota
- E2E verificado: 4 tabs renderizan correctamente bajo Buffer 429 activo con countdown real (6m, no 24h)

---

## [0.7.5] — 2026-05-17

### Content Studio Pipeline — Video Fixes + Login Repair + Buffer Caching

#### Pipeline / Content Studio
- **Multi-scene scripts**: `content_creator.py` now generates 4 VIDEO_PROMPTs for shorts and 6 for longs (was 1 and 3)
- **ASS Subtitles**: Replaced SRT with ASS format — DejaVu Sans 28px, bottom-centered, black semi-transparent background box
- **Crossfade Transitions**: Added `crossfade_clips()` using ffmpeg `xfade` filter with 0.8s fade between clips. Fallback to concat demuxer if xfade fails
- **End Frame CTA**: Added `create_end_frame()` using ffmpeg `drawtext` with business name, address, special offer, and price. Duration dynamically calculated to fill remaining audio time
- **Edge-TTS Fallback**: Added `edge-tts>=6.1.0` to requirements.txt. ElevenLabs returns 401, MiniMax TTS returns no audio — Edge-TTS (`es-MX-JorgeNeural`) successfully generates Spanish audio
- **Test Production**: Produced and uploaded short (29.9s, 8.0MB) and long (79.0s, 22.2MB) videos with FLUX + Ken Burns

#### Frontend Fixes
- **Login Repair**: Frontend container moved from default `bridge` network to `eko-ai-bussinnes-automation_default` Docker network so it can resolve `eko-backend`
- **Buffer API Caching**: Added 30-second in-memory cache to `/content-api/posts`, `/content-api/buffer-posts`, `/content-api/limits` routes to avoid Buffer rate limiting
- **Container Mounts**: Added `output/` and `config/` volume mounts to frontend container for local API endpoints (`/pipelines`, `/stats`)
- **TypeScript Fix**: Fixed `for...of` iteration over `Map.keys()` by using `Array.from()` in `api-cache.ts`

#### Auto-publisher
- **Dynamic Video Discovery**: Auto-publisher script now reads actual pipeline JSON outputs instead of hardcoded video URLs
- Detects connected Buffer channels automatically
- Publishes to correct platforms based on video tags

---
# Changelog

## [0.6.1] — 2026-04-29

### Full Sales Cycle Demo — X3nails & Spa / Margie

#### Voice & Inbound
- **VAPI inbound assistant** (`vapi_client.py`) — Created "Eva" assistant with Rachel voice, Claude Sonnet, Deepgram nova-2 transcriber, `book_demo` function tool, bound to `+1-256-364-1727`
- **VAPI webhooks** (`webhooks.py`) — `tool-calls` creates Booking + notifies Ender; `end-of-call-report` logs call data + sends rich summary email + Telegram alert
- **Outbound calls** (`voice_agent.py`) — `POST /voice-agent/calls` with custom assistant, first message auto-generation

#### Email & Auto-Reply
- **Demo invite template** (`templates/emails/demo_invite.py`) — Professional HTML with VAPI phone CTA + booking link CTA
- **Ender notification template** (`templates/emails/ender_notification.py`) — Rich HTML with lead snapshot, pain points, transcript, recording link, calendar link
- **Auto-reply AI** (`email_reply_agent.py`) — Generates contextual English replies with both phone number (`+1-256-364-1727`) and `/book-demo` link CTAs
- **Svix webhook fix** (`webhooks.py`) — Replaced custom signature verification with `standardwebhooks` library; fixed signed content format (`id.timestamp.body`)
- **Resend inbound processing** (`webhooks.py`) — Full inbound email webhook with AI intent analysis, auto-reply, status transitions

#### Booking & Calendar
- **Public booking page** (`main.py`) — `/book-demo` serves inline HTML form with date picker, time slots (9:00–16:30 MT), prefills via query params
- **Calendar links** (`utils/calendar_links.py`) — Google Calendar `.ics` generator for "Add to Calendar" buttons
- **Booking endpoint fix** (`calendar.py`) — Added missing `Interaction` import for `/book-demo` POST

#### Notifications
- **Eko Rog Telegram notifier** (`services/eko_rog_notifier.py`) — Sends booking/call alerts to `@EkoBit_Rog_bot`
- **Sales brief generator** (`services/sales_brief_generator.py`) — AI-generated sales brief on booking creation

#### Infrastructure
- **Docker Compose** — Added `APP_URL`, `FRONTEND_URL`, `ENVIRONMENT`, `CORS_ORIGINS`, `VAPI_*`, `TELEGRAM_*`, `AUTO_REPLY_ENABLED` env vars to all services
- **Config** (`config.py`) — Added `AUTO_REPLY_ENABLED`, VAPI IDs, Telegram config, notification email
- **Frontend build** — `NEXT_PUBLIC_API_URL` set to `https://ender-rog.tail25dc73.ts.net`

---

## [0.6.0] — 2026-04-25

### Enrichment Pipeline Hardening

#### Backend
- **Celery worker fix** — Resolved `InvalidRequestError` by creating `app/models/__init__.py` and importing all models in `celery_app.py` before app initialization
- **Commit-per-lead enrichment** — Both scheduled `enrich_pending_leads` (every 30 min) and manual `enrich-all` endpoint now commit after each individual lead, enabling real-time UI progress tracking
- **Kimi JSON parsing** — Replaced fragile greedy regex with robust `_extract_json()` in `ResearchAgent`:
  - Fast path: direct `json.loads()` for clean responses
  - Markdown stripping: unwraps ` ```json ... ``` ` code blocks
  - Brace counting with string/escape awareness: finds balanced `{}` pairs while respecting JSON string literals
  - Eliminates fallback 50/50 scores from truncated or malformed JSON
- **WebsiteFinder hardening** (`app/agents/research/analyzers/website.py`):
  - Blocks URLs ending in `.pdf`, containing `.gov/`, or `.mil/` to avoid wasting enrichment cycles on government/military documents
  - Prevents CO SOS delinquent records from triggering irrelevant `.gov` PDF scrapes
- **Yelp Fusion pagination** — Added offset pagination so requesting >50 results (up to 200) correctly chains multiple API calls (50 per call) instead of silently capping
- **Discovery deduplication** — Fixed `AttributeError: 'NoneType' object has no attribute 'lower'` when LinkedIn or Colorado SOS return leads with null `city` or `business_name`
- **DiscoveryResponse schema** (`app/schemas/lead.py`) — New `DiscoveryResponse` with `total_found`, `new_leads`, `duplicates_skipped`, `items`. Updated `POST /discover` endpoint to return this instead of `LeadListResponse`, fixing 500 validation errors
- **Cal.com auth fix** (`app/services/cal_com.py`) — Switched from Bearer header to query param (`?apiKey=`) for Cal.com API compatibility
- **Email unsubscribe URL** (`app/agents/outreach/channels/email.py`) — Fixed hardcoded `localhost` unsubscribe link
- **AI client hardening** (`app/utils/ai_client.py`) — Added explicit "Your response must be ONLY valid JSON" instruction to Kimi prompts when `json_mode=True`
- **Docker Compose** — Added `KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`, `KIMI_EMBEDDING_MODEL`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `CAL_COM_API_KEY` to all services

#### Frontend
- **Leads pagination** (`frontend/app/leads/page.tsx`) — Added page state with Previous/Next buttons, 100 leads per page
- **Enrichment progress bar** — Real-time progress indicator with polling every 10s, showing processed count, pending count, and percentage
- **DiscoveryForm dropdowns** (`frontend/components/DiscoveryForm.tsx`) — Converted city, state, and max_results to `<select>` menus:
  - 30 Colorado cities pre-populated
  - All 50 US states + DC
  - max_results options: 10, 25, 50, 100, 200
- **Discovery fetch workaround** — Replaced axios with native `fetch()` for `/discover` POST to avoid axios preflight CORS "Network Error" when selecting multiple sources
- **API URL consistency** — Replaced hardcoded `http://10.0.0.240:8001` fetch calls in `leads/page.tsx` with relative `/api/v1/...` paths (Next.js rewrites)

#### Infrastructure / DevEx
- **Frontend Dockerfile** — `NEXT_PUBLIC_API_URL` set to `http://10.0.0.240:8001`
- **Backend config** — `KIMI_BASE_URL` default updated to `https://api.kimi.com/coding/v1`, `KIMI_MODEL` default to `kimi-for-coding`
- **Lead model** — Added missing fields: `review_summary`, `trigger_events`, `pain_points`, `scoring_reason`, `proposal_suggestion`

---

## [0.6.2] — 2026-04-25

### Pipeline Fix — Complete Visibility + Valid Transitions + Interaction Tracking

#### Backend
- **Score 0 validity** (`app/tasks/scheduled.py`, `app/api/v1/leads.py`) — Changed `if lead.urgency_score and lead.fit_score:` to `is not None` checks in 3 places. Defunct businesses with 0/0 scores now correctly transition to `SCORED` instead of getting stuck in `ENRICHED`
- **PATCH transition validation** (`app/api/v1/leads.py`) — `update_lead` endpoint now validates status changes against `VALID_TRANSITIONS` from CRM router. Prevents jumping `discovered` → `closed_won`. Also records an `Interaction` with transition metadata
- **Rate limiter fix** (`app/api/v1/crm.py`) — `_check_contact_rate_limit` now filters `direction="outbound"` so inbound email clicks/opens don't falsely count against the daily limit
- **CRM email interactions** (`app/api/v1/crm.py`) — `contact_lead` now creates an `Interaction` record with channel, template, AI-generated flag, and message_id before committing

#### Frontend
- **KanbanBoard: 13 complete stages** (`frontend/components/KanbanBoard.tsx`) — Added missing `active`, `at_risk`, `churned` stages. Customer lifecycle leads no longer disappear from the pipeline
- **Valid transition arrows** — Replaced broken index-based movement with explicit valid-transition buttons. Backward/forward arrows only appear for transitions allowed by the backend state machine
- **Load all leads** — `page_size: 9999` ensures the Kanban shows every lead regardless of total count
- **User feedback on errors** — Invalid transitions now show an `alert()` with the backend message instead of failing silently in console

#### Pipeline Empty Kanban Fix (v0.6.1-hotfix)
- **page_size limit** (`app/api/v1/leads.py`) — Increased from 100 to 5000. KanbanBoard requesting 9999 caused 422 validation error, leaving pipeline completely empty.
- **Email validation** (`app/schemas/lead.py`) — Changed `EmailStr` to `str` in `LeadBase`. Discovery sources (CO SOS, Yelp) produced corrupt emails like `K@48G9-.BYBGNPTUT` that caused Pydantic `ValidationError` and 500 errors on large fetches.
- **KanbanBoard sync** (`frontend/components/KanbanBoard.tsx`) — `page_size` adjusted from 9999 to 5000 to match backend limit.

---

## [0.5.1] — 2026-04-24

### Fixed: AI Provider Routing (Kimi Integration)

#### Backend
- **Docker Compose env vars**: Added `AI_PROVIDER`, `KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`, `KIMI_EMBEDDING_MODEL`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `CAL_COM_API_KEY` to `backend`, `celery-worker`, and `celery-beat` services.
- **Config defaults** (`app/config.py`): Changed `KIMI_BASE_URL` default from Moonshot (`https://api.moonshot.cn/v1`) to Kimi Code API (`https://api.kimi.com/coding/v1`); changed `KIMI_MODEL` default to `kimi-for-coding`.
- **AI client** (`app/utils/ai_client.py`):
  - Added fallback to `reasoning_content` when `content` is empty (required for `kimi-for-coding` model).
  - Fixed `TypeError` in `generate_embedding`: `SentenceTransformer.encode()` does not accept `convert_to_list`; now uses `.tolist()`.
- **Embeddings alignment**: `sentence-transformers` (`all-MiniLM-L6-v2`) generates 384-dim embeddings, matching `Lead.Vector(384)` in the database schema.

---

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
