# Plan: Kanban Column Pagination + Lazy Loading

## Contexto
El KanbanBoard ahora está virtualizado en el frontend, pero sigue cargando **todos los leads** en una sola petición (`page_size: 2000`). Con 480 leads actuales esto no es crítico, pero escalará mal cuando la base crezca.

## Objetivo
Cada columna del Kanban debe cargar sus leads de forma independiente y paginada, igual que Jira/Trello. El usuario hace scroll en una columna y se cargan más leads de esa etapa específica.

---

## Opciones evaluadas

| Opción | Esfuerzo | Impacto | Escalabilidad |
|--------|----------|---------|---------------|
| A. Memoización con React.memo | 30 min | Medio (evita re-renders) | No resuelve carga de red |
| B. Validar transiciones en Lead Detail | 1 h | Medio (mejora UX) | No resuelve performance |
| C. **Paginación por columna (elegida)** | 3-4 h | **Alto** | **Resuelve red + DOM** |

**Por qué C es la mejor:** Ataca el problema de raíz. La virtualización ya optimizó el DOM; la paginación optimizará la red y el uso de memoria en el cliente.

---

## Arquitectura

### Backend (FastAPI)

Reutilizar el endpoint existente `GET /api/v1/leads` que ya acepta `status`, `page`, `page_size`.

Cambios mínimos requeridos:
1. **Ninguno en el endpoint** — ya soporta `?status=X&page=N&page_size=50`.
2. **Opcional: índice compuesto** en `(status, created_at)` o `(status, id)` para que la query sea O(1) en vez de sequential scan.

### Frontend (Next.js)

```
KanbanBoard
├── Column 1 (discovered)    → useInfiniteQuery({ status: "discovered" })
├── Column 2 (enriched)      → useInfiniteQuery({ status: "enriched" })
├── Column 3 (scored)        → useInfiniteQuery({ status: "scored" })
...
```

Cada columna es autónoma:
- Mantiene su propia lista de leads
- Mantiene su propio estado de scroll + virtualizer
- Solicita página N cuando el usuario scrollea cerca del final

---

## Fases de implementación

### Fase 1 — Backend: índice de base de datos (30 min)
- Agregar migración Alembic con índice compuesto `(status, id)` en `leads`.
- Verificar plan de ejecución de query con `EXPLAIN`.

### Fase 2 — Hook reusable `useColumnLeads` (45 min)
- Crear `frontend/hooks/useColumnLeads.ts` usando `@tanstack/react-query`.
- Configurar `getNextPageParam` para extraer `next_page` de la respuesta.
- Mantener cache por status (staleTime: 2 min).

### Fase 3 — Refactor KanbanColumn (90 min)
- Reemplazar el array `stageLeads` prop por el resultado del hook.
- Integrar `useVirtualizer` con lista que crece dinámicamente.
- Detectar cuando el virtualizer se acerca al final (`scrollElement.scrollTop + offset > threshold`) y llamar `fetchNextPage()`.
- Mostrar skeleton mientras carga la siguiente página.

### Fase 4 — Invalidación inteligente (30 min)
- Cuando un lead se mueve de columna A a B:
  - Invalidate query de A (para que desaparezca del DOM virtualizado).
  - Invalidate query de B (para que aparezca al tope o según orden).
- Evitar el `loadLeads()` global masivo que existe hoy.

### Fase 5 — Lead Detail & Transitions (45 min)
- Aprovechar la misma query para mostrar transiciones válidas en el sidebar.
- Deshabilitar etapas no permitidas según `VALID_TRANSITIONS`.

### Fase 6 — Testing + build (30 min)
- Probar movimiento de leads entre columnas con paginación parcial.
- Verificar que `npm run build` y `tsc --noEmit` pasen limpio.

---

## Trade-offs

| Pro | Contra |
|-----|--------|
| Carga inicial instantánea (solo ~50 leads × 13 columnas como máximo) | Más complejo que un solo `useEffect` |
| Scroll infinito por columna, UX profesional | Requiere `@tanstack/react-query` ya instalado — hay que usar su API de infinite queries |
| Cache independiente por columna | Movimiento de leads requiere invalidar 2 caches en vez de 1 lista global |
| Escalable a 100k+ leads | Necesita índice en BD para no degradar |

---

## Alternativa rápida (si quieres algo hoy)

Si el esfuerzo de 3-4h parece mucho, la **Fase 5 sola** (validar transiciones en Lead Detail) es 45 min de trabajo puro y mejora la UX de inmediato. La paginación puede esperar hasta que tengas >1000 leads.

---

## Estado actual del repo
- `main` tiene virtualización del Kanban (commit `0699017`).
- `@tanstack/react-query` ya está en `package.json` pero no se usa aún en el Kanban.
- El backend ya soporta `status`, `page`, `page_size` en `GET /leads`.
