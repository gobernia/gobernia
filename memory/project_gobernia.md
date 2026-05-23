---
name: Gobernia — Contexto del Proyecto
description: Stack, arquitectura, estado de etapas, URLs de producción y reglas de trabajo
type: project
---

## Stack de producción

| Servicio | URL | Qué hace |
|----------|-----|----------|
| **Vercel** (frontend) | https://frontend-gamma-eight-93.vercel.app | Next.js 16 + React 19 |
| **Railway** (backend) | https://goberniagobernia-production.up.railway.app | FastAPI + Python |
| **Supabase** | dyojzlgvwbrbmwghltqg | PostgreSQL + Auth |

Railway service ID: `69bbb590-7f9b-4a12-ba70-01bf3863d354`  
Railway project: `gobernia/gobernia` (project ID: `d75ed427-2253-4147-8db8-269acd23fe26`)

## Arquitectura

- **Frontend**: Next.js 16, React 19, Zustand (localStorage persist), Framer Motion, TailwindCSS 4, `@supabase/ssr`
- **Backend**: FastAPI async, SQLAlchemy async + asyncpg, Supabase PostgreSQL, Anthropic Claude API
- **Auth**: Supabase Auth (email/password). Callback route: `/auth/callback` (intercambia code → session)
- **CORS**: `ALLOWED_ORIGINS` en Railway = `["https://frontend-gamma-eight-93.vercel.app","https://gobernia-liard.vercel.app"]`

## Onboarding — 8 etapas implementadas

Todas las etapas guardan datos en `memory_buffer` (JSONB) del modelo `OnboardingSession`.  
**CRÍTICO**: Siempre usar `flag_modified(session, "memory_buffer")` después de modificar el buffer — SQLAlchemy no detecta cambios en JSONB sin esto.

| Etapa | Descripción | Endpoints |
|-------|-------------|-----------|
| 1 | Info empresa | POST `/{sid}/etapa-1` |
| 2 | Equipo | POST `/{sid}/etapa-2` |
| 3 | Prioridades | POST `/{sid}/etapa-3` |
| 4 | Diagnóstico (preguntas dinámicas) | GET `/{sid}/etapa-4/questions`, POST `/{sid}/etapa-4` |
| 5 | KPIs | GET `/{sid}/etapa-5/kpis`, POST `/{sid}/etapa-5` |
| 6 | Gobierno | GET `/{sid}/etapa-6/items`, POST `/{sid}/etapa-6` |
| 7 | Documentos | POST `/{sid}/etapa-7/upload`, POST `/{sid}/etapa-7/complete` |
| 8 | Visión y agentes | GET `/{sid}/etapa-8/options`, POST `/{sid}/etapa-8` |

Endpoint adicional: `GET /{sid}/summary` → devuelve company_name, governance_score, diagnostic_area_completion

## Features implementadas (mayo 2026)

### Tooltip "¿Qué evalúa?" en etapa-4
- Campo `description: str = ""` agregado a `DiagnosticQuestion` schema
- 33 descripciones en `question_engine.py` (todas las preguntas)
- Frontend: botón "¿Qué evalúa?" con borde visible debajo de cada pregunta
- Tooltip negro aparece en hover/click con la definición

### Skip de preguntas (etapa-4)
- Botón "Saltar" en la navegación
- Respuesta `"skipped"` guardada en `memory_buffer`
- Matrix engine (`build_mefi`, `build_mefe`) ignora respuestas `"skipped"`

### Widget diagnóstico por área (dashboard)
- `build_etapa4_memory` calcula `diagnostic_area_completion` por área
- Dashboard muestra sección "Diagnóstico por área" con barras de progreso
- Color: verde ≥80%, amarillo ≥50%, rojo <50%
- Click en área expande lista de preguntas con respuestas individuales

### Auth flow completo
- Ruta `/auth/callback/route.ts` para intercambiar code → session (PKCE)
- `emailRedirectTo: window.location.origin + "/auth/callback"` en sign-up
- Supabase Site URL configurado a URL de Vercel
- Middleware incluye `/auth/callback` como ruta pública

### Correcciones de infraestructura
- `sqlalchemy[asyncio]` + `greenlet==3.1.1` en requirements.txt
- Railway CORS configurado con URL de Vercel
- Variables de entorno en Vercel: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL

### Base de conocimiento institucional para agentes IA (mayo 2026)
- 8 PDFs en `Contendido/` con frameworks de gobierno corporativo (CCE México, Todd Empresas de Familia)
- Texto extraído con `pdftotext` (poppler) a `Contendido/_extracted/` (gitignored)
- Módulo `backend/app/services/ai/knowledge_base.py` — síntesis estructurada del contenido:
  - `CORE_PRINCIPLES` — 12 principios fundamentales CCE (todos los agentes)
  - `BOARD_BEST_PRACTICES` — integración y operación del Consejo (todos los agentes)
  - `CFO_KNOWLEDGE`, `CSO_KNOWLEDGE`, `CRO_KNOWLEDGE`, `AUDITOR_KNOWLEDGE` — especializado por rol
  - `FAMILY_BUSINESS_KNOWLEDGE` — inyectado solo si `is_family_business=True`
- Integrado en `agents/base.py`: `build_knowledge_for_agent(agent, is_family_business)` se invoca en `run_agent_analysis` y `run_agent_chat`
- ~2,600 tokens por invocación. Prompt cache de Claude minimiza costo en llamadas repetidas
- Decisión: NO usamos RAG/embeddings — Opción C (resumen estructurado). Si se queda corto en el futuro, migrar a Supabase pgvector

### Flujo onboarding desacoplado del sign-up (mayo 2026)
- Sign-up redirige a `/dashboard` (no a etapa-1 forzosamente)
- Dashboard funciona sin onboarding completo. CTAs muestran modal "Configura primero" si no hay datos
- Nueva página `/dashboard/datos` muestra resumen de las 8 etapas con preview pulled de memory_buffer y botón "Editar"/"Completar" por sección
- Etapa pages aceptan `?from=datos`; al guardar regresan a `/dashboard/datos` (en lugar de avanzar a la siguiente etapa)
- Layout `/onboarding/layout.tsx` con `dynamic = "force-dynamic"` para evitar bailout de `useSearchParams`
- **Etapa-1 con pre-población completa** desde memory_buffer.company (incluye `location.{city,state,country}` anidado)
- Etapas 2-8: el redirect funciona pero forms inician vacíos — pendiente agregar pre-población a c/u

### Challenger Agent (5to agente pre-mortem, mayo 2026)
- Invisible al usuario, aplica método pre-mortem a cada análisis antes de mostrarse
- Flujo: agente analiza → Challenger critica → agente revisa → usuario ve revisión
- Detecta: supuestos débiles, riesgos omitidos, recomendaciones vagas, datos ignorados, puntos ciegos, brechas frente a CCE
- Reglas anti-sycophancy: Challenger no inventa problemas; agentes pueden rechazar críticas equivocadas
- Crítica persiste en `board_sessions.agent_critiques` (JSONB) para auditoría
- 3x llamadas LLM por agente; prompt cache de Claude mitiga costo
- Implementado en `agents/base.py`: `run_challenger_critique`, `run_agent_revision`
- Orquestado en `board_sessions/router.py` en endpoint `/analyse`

### Identidad visual + landing redesign (mayo 2026 — WIP local, NO deployado)
- **Fuente self-hosted**: Gabriel Sans (12 woff2 weights) en `frontend/public/fonts/gabriel-sans/`, declarada vía `@font-face` en `globals.css`. Una sola familia para todo el sistema, jerarquía por pesos.
- **Brand tokens** en `globals.css` bajo `:root`: `--gob-navy #142849`, `--gob-charcoal #26282E`, `--gob-ink #0B0E14`, `--gob-bone #F4F1EC`, `--gob-paper #FBF8F3`, `--gob-stone #8E8B84`, `--gob-rule #D9D4CB`, `--gob-muted #6C6A66`.
- **Logo component** `components/ui/GoberniaLogo.tsx` con wordmark GOBERN[IA] (medium 500 + cápsula charcoal radio 0.18em padding 0.22/0.26/0.06). Variantes: default | inverse | ink | line. `GoberniaIcon` para favicon.
- **Middleware** excluye `/fonts/*.woff2|woff|otf|ttf` para que no devuelva 307.

### Landing 1 (`/`) — redesign al estilo interractlabs.com
- **Hero**: `min-h-dvh`, fondo blanco. Headline 3 líneas con pattern dimmer/lighter (`opacity 0.4` vs `1.0`) inline:
  - "Sesión de **consejo**" / "**cada mes,** con cuatro" / "**agentes** de **IA.**"
  - Tamaño `clamp(40px, 6.5vw, 88px)`, weight 300, line-height 0.95, letter-spacing -0.03em
  - Posición top (`pt-32/36/40`), divisor a 50px del texto, CTAs links discretos abajo
  - `HeroWaveLines` component: canvas con ondas en navy alpha bajo, mask `to bottom left` (top-right corner), contenido al section con ResizeObserver
- **Auto-hide header** vía `useAutoHideHeader()` hook — oculta al scroll down, muestra al scroll up. Sin border-bottom.
- **Secciones El equipo / El proceso / Para quién / FAQ / CTA**: layouts portados de la landing-2 (4 columnas sin borde para equipo, números gigantes en el proceso, FAQ widescreen). Títulos todos con patrón bold + light-italic en dos líneas exactas vía `<br/>`.
- **Containers** todos a `max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20`.
- **SEO**: `<title>`, `<meta description>`, `keywords`, `OpenGraph`, `Twitter card` con keywords "consejo de administración con IA", "agentes de IA empresa", "junta directiva virtual", etc.

### Landing 2 (`/landing-2`) — versión alternativa para comparar
- Port de la propuesta dark de Interract pero **fondo blanco**, sin CanvasBackground (sin partículas que siguen cursor), con WaveLines en todo el bg.
- `middleware.ts` la incluye en `PUBLIC_PATHS` para que sea accesible sin login.

### Estado: WIP local
- `tag pre-brand-rebrand` mantiene el último estado pre-rebrand (rollback si se necesita).
- Cambios committed en main pero **NO deployados** a Vercel — el usuario está iterando con `npm run dev` local + `uvicorn` local. Cuando esté listo para producción: `npx vercel --prod --yes` (frontend) y `railway up --detach` (backend).

## Pendiente / próximas mejoras

- Claude API calls async (actualmente síncronas, bloquean el event loop — usar `AsyncAnthropic`)
- Dominio custom para Vercel (en lugar de frontend-gamma-eight-93.vercel.app)
- Sign-in debería detectar si el usuario ya completó onboarding y redirigir a /dashboard vs /onboarding/etapa-X

## Reglas de trabajo

- Deploy backend: `cd backend && railway up --detach`
- Deploy frontend: `cd frontend && npx vercel --prod --yes`
- Env vars backend: `railway variables set KEY=value`
- Env vars frontend: `npx vercel env add KEY production`
- Siempre verificar CORS si hay errores 4xx en producción
