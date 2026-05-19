export const CURRENT_VERSION = "0.7.6";

export interface VersionEntry {
  version: string;
  date: string;
  title: string;
  changes: string[];
}

export const CHANGELOG: VersionEntry[] = [
  {
    version: "0.7.6",
    date: "2026-05-18",
    title: "Content Studio — Unified Buffer Snapshot + Rate-limit Banner",
    changes: [
      "Fix: 4 tabs de Content Studio (Publicaciones, Calendario, Analytics, Monitoreo) rotos por Buffer 429",
      "New: /content-api/buffer-snapshot — un solo endpoint con {channels, posts, limits} en una query GraphQL",
      "New: hook useBufferData con caché module-level + pub/sub para compartir datos entre los 4 tabs",
      "New: RateLimitBanner con countdown preciso (lee retry-after header, no window:24h del body)",
      "New: lib/buffer.ts cliente unificado con 5min fresh + 24h stale + rate-limit hint pegajoso",
      "Fix: PostsList filtra client-side (sin re-fetch por filtro)",
      "Fix: PostCalendar sin re-fetch al cambiar mes",
      "Fix: AnalyticsDashboard text-gold inválido reemplazado por text-yellow-300; charts muestran 'Sin datos' elegante",
      "Fix: BufferStatus empty state amigable cuando no hay caché",
      "Fix: PipelineHistory infiere status 'completed' por presencia de scripts[]/produced[] (columna Content ya no muestra '—')",
      "Reduce Buffer API consumption: 5+ calls por dashboard load → 1 call compartida (caché 5min)",
    ],
  },
  {
    version: "0.7.5",
    date: "2026-05-17",
    title: "Content Studio Pipeline — Video Fixes + Login Repair + Buffer Caching",
    changes: [
      "Fix: frontend login container conectado a red Docker correcta (eko-ai-bussinnes-automation_default)",
      "Fix: API caching de 30s en /content-api/posts, /buffer-posts, /limits para evitar rate limit de Buffer",
      "Fix: auto-publisher script lee videos reales del pipeline output (no hardcodeados)",
      "Fix: frontend container mounts output/ y config/ para endpoints locales (pipelines, stats)",
      "Fix: TypeScript build error en api-cache.ts (for...of Map.keys -> Array.from)",
      "Content Studio: 4 escenas por short + 6 por long con múltiples VIDEO_PROMPTs",
      "Content Studio: subtítulos ASS con DejaVu Sans, fondo negro semitransparente, bottom-centered",
      "Content Studio: crossfade transitions xfade 0.8s entre clips",
      "Content Studio: end frame CTA dinámico con nombre, dirección, oferta, precio",
      "Content Studio: Edge-TTS fallback (es-MX-JorgeNeural) para TTS en español",
      "Pipeline: prueba real generó short (29.9s) + long (79.0s) con FLUX + Ken Burns",
    ],
  },
  {
    version: "0.7.4",
    date: "2026-05-13",
    title: "Landing Page Builder v2 — UI + Generation + SEO",
    changes: [
      "Landing Pages: Navbar agregado para navegación completa",
      "Landing Pages: card 'Landing Page en Uso' con preview thumbnail y stats",
      "Landing Pages: card fallback 'Sistema' cuando no hay páginas dinámicas",
      "Landing Pages: botón 'Generate with AI' prominente y siempre visible",
      "Landing Pages: 4 templates de prompt pre-cargados (Restaurante, Clínica, Gym, Spa)",
      "Landing Pages: tabs Pages / Compare con comparación A/B de conversiones",
      "Fix: generación con IA usa modelo del sistema (evita 400 Bad Request por mismatch de proveedor)",
      "Fix: lista se refresca automáticamente tras crear draft desde 'Generate with AI'",
      "Fix: workspace filter backward compatibility para landing pages legacy",
      "SEO: URLs limpias /lp/{slug} vía nginx rewrite para bots y crawlers",
      "Cal.com link dinámico en HTML generado (lee settings de app)",
    ],
  },
  {
    version: "0.7.3",
    date: "2026-05-11",
    title: "Delete Lead Fix + Celery Stability",
    changes: [
      "Fix: botón Eliminar ahora borra leads correctamente (cascade delete de 7 tablas relacionadas)",
      "Fix: frontend muestra alert() cuando delete falla en vez de silenciar el error",
      "Fix: Celery worker RuntimeError 'Event loop is closed' — migrado a prefork pool + engine recreation",
      "Fix: WebsiteAnalyzer 403 bypass — retry sin User-Agent cuando sitio bloquea bots",
      "Fix: feature flags de website (booking, chatbot, etc.) ahora persisten en Lead model",
    ],
  },
  {
    version: "0.7.2",
    date: "2026-05-10",
    title: "Landing Page Hardening + Feature Flags",
    changes: [
      "Landing page envía Free AI Analysis email inmediatamente tras captura de lead",
      "Fix: hero form recargaba página por falta de e.preventDefault()",
      "Fix: schema PublicLeadCreate ahora acepta website, city, state",
      "Fix: auto-reply con caracteres chinos en español — language detection persistido",
      "Emails de bienvenida ahora crean Interaction record con email_status=sent",
      "Website feature flags persistidos: has_booking, has_chatbot, has_ecommerce, etc.",
    ],
  },
  {
    version: "0.7.1",
    date: "2026-05-05",
    title: "Inbox, DNS, Voice Agent y UX",
    changes: [
      "Inbox agrupado por lead con conteo de mensajes y threading de conversaciones",
      "Webhook de correos entrantes con auto-respuesta IA y keywords en inglés/español",
      "Formateo de emails: texto plano a HTML con párrafos y saltos de línea",
      "Pixel de tracking para apertura de correos",
      "Configuración DNS completa: SPF + DKIM + DMARC para biz.ekoaiautomation.com",
      "Soporte para Google Meet en reservas de demo (alternativa a Zoom)",
      "Manejo de zona horaria en links de calendario (America/Denver)",
      "Fix de RLS/workspace: migración de interacciones legacy a workspace default",
      "Botón de versión + modal de historial de cambios en navbar",
      "Creación manual de leads desde /leads (formulario modal con validación)",
    ],
  },
  {
    version: "0.7.0",
    date: "2026-04-28",
    title: "FASE 8: AI Proposal Generator + Email Reply Agent + VAPI Voice Agent",
    changes: [
      "AI Proposal Generator: generación automática de propuestas personalizadas",
      "Email Reply Agent: respuestas automáticas inteligentes a emails entrantes",
      "VAPI Voice Agent: agente de voz con integración VAPI para llamadas",
    ],
  },
  {
    version: "0.6.1",
    date: "2026-04-26",
    title: "Pipeline Hardening + Full Sales Cycle Demo",
    changes: [
      "Pipeline fix: valid transitions, interaction tracking, score-0 hardening",
      "Full sales cycle demo features",
    ],
  },
  {
    version: "0.6.0",
    date: "2026-04-25",
    title: "Enrichment Pipeline Hardening",
    changes: [
      "Enrichment pipeline hardening y mejoras de estabilidad",
      "Client-side sort fix + autocomplete + deploy hardening",
    ],
  },
  {
    version: "0.5.0",
    date: "2026-04-24",
    title: "Booking System + Cal.com Integration",
    changes: [
      "Sistema de reservas de citas integrado",
      "Integración con Cal.com para scheduling",
      "Webhooks de calendario y recordatorios",
    ],
  },
  {
    version: "0.4.0",
    date: "2026-04-24",
    title: "JWT Auth + Protected Routes + Multi-tenancy",
    changes: [
      "Sistema de autenticación JWT",
      "Rutas protegidas en frontend",
      "Multi-tenancy con workspaces",
    ],
  },
  {
    version: "0.3.0",
    date: "2026-04-24",
    title: "Email Sequences + Celery + CRM Automation",
    changes: [
      "Secuencias de emails automatizadas",
      "Tareas en background con Celery + Redis",
      "Automatización de CRM",
    ],
  },
  {
    version: "0.2.0",
    date: "2026-04-24",
    title: "Outreach + CRM Pipeline Completo",
    changes: [
      "Pipeline completo de outreach",
      "CRM con gestión de leads y deals",
    ],
  },
  {
    version: "0.1.0",
    date: "2026-04-23",
    title: "MVP Scaffolding — Discovery, Research, Outreach, Dashboard",
    changes: [
      "Discovery: búsqueda de negocios en Google Maps, Yelp, LinkedIn",
      "Research: enriquecimiento de leads con IA",
      "Outreach: envío de emails personalizados",
      "Dashboard: panel de control con métricas",
      "Integración con Paperclip AI",
    ],
  },
];
