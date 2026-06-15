# Fase 2 — Diagnóstico estratégico con investigación web — Diseño

**Fecha:** 2026-06-15
**Alcance:** Frontend + backend + migración de DB + integración de IA (web search) + PDF.

## Goal

Un nuevo entregable "Diagnóstico estratégico": el usuario lo genera bajo demanda, una IA (Claude Opus 4.8) investiga en la web la presencia digital, competidores reales, tendencias de mercado y contexto económico/regulatorio de la empresa, y produce un documento de 6 secciones que **contrasta la competencia que el usuario cree tener con la real**. Se ve como una revista y se descarga en PDF. Reemplaza, en la navegación, al viejo "Diagnóstico por área".

## Architecture

El diagnóstico sigue el mismo patrón asíncrono que el plan de 12 meses: un endpoint dispara una task de Celery, que llama a la API de Claude con la **herramienta `web_search` nativa** habilitada (Opus 4.8), parsea la salida estructurada (6 secciones + fuentes citadas) y la persiste en un modelo nuevo `DiagnosticoEstrategico` con estados `generating → active / failed`. El frontend tiene una página dedicada (`/dashboard/diagnostico`, nuevo ítem del sidebar) que hace polling del estado y muestra vacío → generando → vista revista + PDF. Los datos semilla (web + competidores percibidos) se capturan como campos obligatorios en la Etapa 1 del onboarding (en `memory_buffer.company`, sin migración), y una compuerta bloquea la generación si faltan.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async (Base + UUIDMixin + TimestampMixin), Alembic (migración nueva), Celery (`task_session()`), Pydantic v2, anthropic SDK con **web search server-side tool** (`web_search_20260209`), reportlab (PDF).
- IA: `claude-opus-4-8` con `web_search`. Config nueva `DIAGNOSTICO_AI_MODEL` (default `claude-opus-4-8`), separada de `AI_MODEL` (que sigue en sonnet-4-6 para el resto).
- Frontend: Next.js 16 App Router, TypeScript, framer-motion, axios (`@/lib/api`), Tailwind v4.

---

## Componente 1 — Datos semilla en el onboarding (Etapa 1)

**Modificar:** `backend/app/schemas/etapa1.py`, `backend/app/services/ai/memory_buffer.py`, `frontend/src/app/onboarding/etapa-1/...` (el formulario de Etapa 1).

- En `Etapa1Input` agregar:
  - `website: str` — URL de la empresa. Validar formato básico (que parezca URL/dominio). **Obligatorio.**
  - `competitors: list[str]` — nombres de competidores percibidos. **Obligatorio**, mínimo 1, máximo ~10, cada uno string corto.
- En `build_memory_buffer` (memory_buffer.py), mapear ambos a `memory_buffer["company"]` (`website`, `competitors`). Sin migración (JSONB).
- Frontend Etapa 1: agregar un input de URL (web) y un campo de lista de competidores (agregar/quitar chips). Misma validación obligatoria.
- **Compatibilidad hacia atrás:** usuarios que ya completaron el onboarding no tienen estos campos; no se rompen — la compuerta del Componente 6 los pide al intentar generar el diagnóstico.

## Componente 2 — Modelo `DiagnosticoEstrategico` + migración

**Crear:** `backend/app/models/diagnostico_estrategico.py`, una migración Alembic nueva.

- Modelo espejo de `AnnualPlan` (Base, UUIDMixin, TimestampMixin):
  - `user_id: str` (indexado)
  - `status: str` (default `"generating"`; valores `generating | active | failed`)
  - `content: JSONB | None` — el documento: `{ "sections": [{ "key": str, "title": str, "body": str }], "sources": [{ "title": str, "url": str }], "generated_at": str }`
  - `fail_reason: str | None` (p. ej. `"datos"` cuando faltan web/competidores, o `"error"`)
  - timestamps de `TimestampMixin`.
- Un usuario tiene a lo sumo un diagnóstico "vigente"; regenerar reemplaza el anterior (borrar el previo del usuario o marcarlo, igual que el plan se regenera). Decisión de implementación: al generar, eliminar/expirar el diagnóstico previo del usuario y crear uno nuevo en `generating`.
- Migración Alembic crea la tabla `diagnosticos_estrategicos`.

## Componente 3 — Motor de diagnóstico (servicio IA con web search)

**Crear:** `backend/app/services/ai/diagnostico_estrategico.py`. Lógica pura testeable (parseo, ensamblado del prompt, validación de secciones) separada de la llamada de red.

- `build_prompt(memory_buffer)` → arma el prompt del usuario con: nombre, industria, región (ciudad/estado/país), web, y la lista de competidores percibidos. Instruye a la IA a:
  - Investigar en la web la presencia digital real (su sitio, redes), competidores reales en su región/segmento, tendencias de la industria y contexto económico/regulatorio.
  - **Contrastar** los competidores percibidos con los reales (señalar coincidencias, ausencias y puntos ciegos).
  - Devolver **JSON** con las 6 secciones (`resumen_ejecutivo`, `presencia_digital`, `competencia`, `tendencias_mercado`, `contexto_economico`, `conclusiones`) y una lista de `sources` (título + URL de lo que usó).
- `generate_diagnostico(memory_buffer)` (la llamada de red):
  - Cliente `anthropic.Anthropic`, `model = settings.DIAGNOSTICO_AI_MODEL` (`claude-opus-4-8`).
  - `tools=[{"type": "web_search_20260209", "name": "web_search"}]` con un límite de usos (`max_uses` ~6) como guardrail de costo.
  - **No** usar `output_config.format` (structured outputs es incompatible con citations del web search → 400). En su lugar, pedir el JSON en el prompt y parsear el texto final con un extractor de JSON tolerante (como `_extract_json_object` que ya existe en `agents/base.py`).
  - Manejar el loop de tool server-side: si `stop_reason == "pause_turn"`, reenviar para continuar (con un tope de continuaciones, p. ej. 5).
  - `_create_with_retry` para reintentos de red.
  - Parsear → validar que estén las 6 secciones; si llega vacío/ilegible tras reintento, **lanzar** (para que la task lo marque `failed`, no un cascarón) — mismo blindaje que el esqueleto del plan.
- `parse_diagnostico(raw) -> dict` (puro, testeable): extrae las 6 secciones + sources, rellena/normaliza, devuelve el `content` listo para persistir; ante basura, indica fallo.

## Componente 4 — Task de Celery

**Crear/Modificar:** `backend/app/tasks/diagnostico_tasks.py` (nueva), registrar en el worker.

- `generate_diagnostico_task(user_id)`: usa `task_session()` (engine NullPool por task, el fix que ya hicimos), carga el `memory_buffer` del onboarding del usuario, llama al motor, persiste `content` y `status="active"`; ante excepción marca `status="failed"` (con `fail_reason`).
- Blindaje `_expire_if_stale` (si lleva > N min en `generating`, marcar `failed`) — mismo patrón que el plan.

## Componente 5 — API

**Crear:** `backend/app/api/v1/diagnostico/router.py`, registrar el router.

- `POST /api/v1/diagnostico/generate` — compuerta de datos (Componente 6); si pasa, expira el diagnóstico previo, crea uno en `generating`, dispara la task; si la task no se puede encolar, fallback. Devuelve estado.
- `GET /api/v1/diagnostico` — el diagnóstico vigente del usuario (con `content` si `active`).
- `GET /api/v1/diagnostico/status` — `{ status, fail_reason }` para polling.
- `GET /api/v1/diagnostico/pdf` — genera y devuelve el PDF (Componente 8). 404 si no hay diagnóstico `active`.

## Componente 6 — Compuerta de datos (web + competidores)

**Modificar:** `backend/app/services/data_completeness.py` (o función nueva al lado).

- Nueva función `missing_diagnostico_data(memory_buffer)` → lista de faltantes: requiere `company.name`, `company.website` (no vacío) y `company.competitors` (≥ 1). (No exige KPIs — el diagnóstico no los necesita.)
- `POST /diagnostico/generate` la llama; si hay faltantes → 400 con `detail` claro y `fail_reason="datos"`. El frontend lo traduce a "Completa tu web y competidores" con link al onboarding (Etapa 1).

## Componente 7 — Frontend

**Crear:** `frontend/src/app/dashboard/diagnostico/page.tsx`, `frontend/src/lib/diagnostico.ts` (cliente API + tipos).
**Modificar:** `frontend/src/components/ui/Sidebar.tsx` (ítem nuevo), `frontend/src/app/dashboard/page.tsx` (ocultar "Diagnóstico por área").

- **Sidebar:** agregar ítem **"Diagnóstico"** → `/dashboard/diagnostico` (ícono lucide, p. ej. `FileSearch` o `Telescope`). Ubicarlo de forma lógica (p. ej. entre "Plan" y "Compromisos", o tras "Tu consejo").
- **Página `/dashboard/diagnostico`:** estados análogos a la página del plan —
  - `none`: estado vacío con explicación + botón **"Generar diagnóstico"** (avisa que tarda unos minutos porque investiga en la web).
  - `generating`: pantalla de progreso (reusar el patrón/estética de la generación del plan).
  - `failed`: error; si `fail_reason==="datos"` → "Completa tu web y competidores" + link a `/onboarding/etapa-1`; si no → "No se pudo generar" + reintentar.
  - `active`: **vista tipo revista** — las 6 secciones con tipografía cuidada (encabezados, cuerpo legible), la sección "Competencia: percibida vs. real" destacada, y al final las **fuentes citadas** (links). Botón **"Descargar PDF"**.
- **Ocultar "Diagnóstico por área":** quitar del Inicio (`dashboard/page.tsx`) la sección `diagnostic_area_completion` (etapa 4). El resto del Inicio se conserva.

## Componente 8 — PDF del diagnóstico

**Crear:** `backend/app/services/pdf/diagnostico_pdf.py` (patrón de `orden_del_dia_pdf.py`).

- Función que recibe el `content` (6 secciones + fuentes) y arma un PDF legible con reportlab: portada/título, las 6 secciones con encabezados, y la lista de fuentes al final. Devuelve los bytes para el endpoint `GET /diagnostico/pdf`.

---

## Out of scope (NO se toca)

- El `diagnostico_summary` de los 4 agentes en la sesión de consejo (sigue como está; es otra cosa).
- Notificaciones / correo (Fase 4).
- El plan de 12 meses, sesiones, compromisos.

## Decisiones tomadas

- **Disparo:** botón "Generar" + async (Celery), regenerable. (Usuario.)
- **Ubicación:** ítem nuevo "Diagnóstico" en el sidebar + página dedicada; se oculta el viejo "Diagnóstico por área". (Usuario.)
- **Modelo IA:** `claude-opus-4-8` con web search (config `DIAGNOSTICO_AI_MODEL`). (Usuario.)
- **6 secciones** como se listaron. (Usuario.)
- **Campos onboarding:** web + competidores, ambos obligatorios, en `memory_buffer.company` (sin migración).
- **Structured outputs NO** (incompatible con citations); JSON pedido en el prompt + parser tolerante.

## Testing

- **Backend (pytest, red mockeada):**
  - `parse_diagnostico` / `build_prompt`: pura, sin red. Casos: JSON completo, parcial, basura.
  - `missing_diagnostico_data`: faltantes de web/competidores/nombre.
  - Endpoint `generate`: 400 si faltan datos; 200/encola si completo (Celery mockeado, igual que los tests del plan con `AsyncMock` + `dependency_overrides`).
  - Task: con el motor mockeado, verifica transición de estado y persistencia.
- **Frontend (sin suite UI):** `npm run lint` + `npm run build` + smoke manual (generar diagnóstico con una empresa con web+competidores; ver progreso; ver vista revista; descargar PDF; usuario sin esos campos → mensaje a completar onboarding).

## Notas de implementación / riesgos

- **Web search tarda y cuesta:** Opus 4.8 + búsquedas → varios minutos y costo no trivial por diagnóstico. Por eso es async + regenerable + se corre pocas veces. El `max_uses` acota el costo.
- **`pause_turn`:** las herramientas server-side pueden pausar; manejar el reenvío con tope de continuaciones.
- **Citations:** las fuentes vienen como bloques de citación en la respuesta; se pueden extraer de ahí o confiar en la lista `sources` que pedimos en el JSON. Preferir la lista del JSON por simplicidad; si se quiere fidelidad, extraer las citations reales.
- **Migración:** correr Alembic en local apuntando a la DB de prod (como el resto del backend local) requiere cuidado; la migración solo agrega una tabla nueva (no destructiva).
