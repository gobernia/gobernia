# Fase 3B — El Secretario activo (sin infra de correo/S3) — Diseño

**Fecha:** 2026-06-16
**Alcance:** Backend (señal de documento faltante en el análisis de cierre + una alerta nueva) + frontend (avisos push arriba). Reutiliza el cierre de mes, las alertas y las evidencias que ya existen. NO incluye correo real ni lectura de contenido de documentos (esperan a Resend/S3).

## Goal

Hacer al Secretario "activo" mes a mes, con lo que se puede sin infra nueva: (1) **avisos push arriba** (esquina superior derecha) en cualquier página del dashboard, derivados de las alertas que ya existen, para que el usuario se entere de tareas vencidas/por vencer/KPI fuera de meta + que el Secretario revisó su mes; (2) un **análisis de cierre de mes más rico** que toma en cuenta si el usuario subió o no el **documento de sustento** (`required_doc`) de cada tarea, marcando las que no se pueden validar sin él. El correo a responsables y la lectura del contenido de los documentos quedan como enchufes documentados para cuando haya Resend + S3.

## Architecture

Dos cambios pequeños de backend sobre piezas existentes y un componente de frontend. (1) `compute_signals` (en `month_review.py`) gana una señal `tasks_missing_doc` (tareas con `required_doc` pero sin evidencia subida), calculada a partir de los conteos de evidencia que `_run_close` ya puede cargar; el review (LLM + fallback determinista) la factoriza. (2) `compute_alerts` (motor de alertas de Bloque B6) gana una alerta "El Secretario revisó tu mes" cuando el mes cerrado más reciente tiene revisión con propuestas sin aplicar. (3) Un `Notices.tsx` montado en `dashboard/layout.tsx` consume `GET /annual-plan/alertas` y muestra los avisos arriba-derecha, dismissables por sesión.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, anthropic SDK (el review ya usa LLM + fallback). Sin migración (todo derivado/calculado).
- Frontend: Next.js 16 App Router, framer-motion, lucide-react, axios vía `@/lib/api`.

---

## Componente 1 — Señal de documento faltante en el análisis de cierre

**Modificar:** `backend/app/services/ai/month_review.py` (`compute_signals`, `deterministic_review`, el prompt de `run_month_review`), `backend/app/api/v1/annual_plan/router.py` (`_run_close`).

- `compute_signals(tasks, kpi_values, memory_buffer, today, evidence_counts=None)`: agregar el parámetro opcional `evidence_counts: dict | None` (mapa `task_id(str) → conteo`). Calcular y agregar al dict de señales:
  ```
  "tasks_missing_doc": [
     {"title": t.title, "required_doc": t.required_doc}
     for t in tasks if t.required_doc and evidence_counts.get(str(t.id), 0) == 0
  ]
  ```
  (Si `evidence_counts` es None, la lista queda vacía — retrocompatible con los llamados existentes.)
- `_run_close`: dentro del primer bloque `AsyncSessionLocal`, después de cargar `tasks`, cargar los conteos de evidencia por tarea (mismo patrón que `get_plan`: `select(Evidence.action_task_id, func.count()).where(...in_ task_ids).group_by(...)`) y pasarlos a `compute_signals(tasks, kpis, memory_buffer, today, evidence_counts=...)`.
- `deterministic_review(signals, incomplete_task_ids)`: si `signals["tasks_missing_doc"]` no está vacío, agregar al texto/propuestas una nota de que faltan documentos de sustento (p. ej. una propuesta `carry_over_task` o una línea en el `summary` determinista: "N tareas sin su documento de sustento — súbelos para validarlas").
- Prompt de `run_month_review` (el system/user prompt): incluir las `tasks_missing_doc` en el contexto e instruir al Secretario a **marcarlas como no validadas sin su documento**, pesar eso en la calificación, y proponer subir el documento o arrastrar la tarea. (Las señales ya se pasan al prompt; agregar esta lista.)

## Componente 2 — Alerta "El Secretario revisó tu mes"

**Modificar:** `backend/app/services/governance/alerts.py` (`compute_alerts`).

- `compute_alerts` ya deriva alertas del plan (vencidas/por vencer/cobertura/KPI off-track). Agregar una categoría nueva: si el mes cerrado más reciente (status `done`) tiene `review` con **propuestas sin aplicar** (`review.proposals` con algún `applied == False`), emitir una alerta nivel `review`/info con título "El Secretario revisó tu mes" y detalle "N propuestas para tu plan" (link/ancla al plan). Leer la forma real de `review.proposals` (cada propuesta tiene `applied: bool` — se setea en `_run_close`).
- Si no hay revisión con propuestas pendientes, no se emite. (Determinista, sin estado.)

## Componente 3 — Avisos push arriba (frontend)

**Crear:** `frontend/src/components/dashboard/Notices.tsx`. **Modificar:** `frontend/src/app/dashboard/layout.tsx`. **Reusar:** `frontend/src/lib/alerts.ts` (ya tiene el cliente `getAlertas`).

- `Notices.tsx` (client component): al montar, llama `getAlertas()` (`GET /annual-plan/alertas`). Si hay alertas, las muestra como **avisos apilados en la esquina superior derecha** (`fixed top-4 right-4 z-50`), cada uno con su color por nivel (mismo criterio que `AlertsPanel`), texto corto, y botón de cerrar (×).
  - **Dismiss por sesión**: al cerrar un aviso (o "cerrar todos"), guardar en `sessionStorage` que ya se vieron, para no reaparecer en la misma sesión (patrón del `SecretarioWelcome` de Fase 1). Reaparecen en la siguiente visita si siguen vigentes.
  - Si `getAlertas()` falla (no hay plan / 404) → no muestra nada (silencioso).
  - Entrada y salida con `framer-motion` (slide desde la derecha), discreto.
- `dashboard/layout.tsx`: montar `<Notices />` junto al `<Sidebar />` (es `fixed`, no afecta el layout). Aparece en todas las páginas del dashboard.

## Componente 4 — Enchufes documentados (NO se construye código inactivo)

- **Correo a responsables (futuro, requiere Resend):** el modelo `Compromiso` ya tiene `responsable_email` + `token` (link sin login). El punto de enchufe es: cuando se cree/actualice un compromiso (o en un scheduler de recordatorios), enviar el link `/c/{token}` por correo. Se documenta en el spec como el seam; NO se implementa ahora (no hay proveedor).
- **Lectura del contenido del documento (futuro, requiere S3):** hoy el análisis usa *presencia* de evidencia (`evidence_count`). El seam es: en `_run_close`, descargar el archivo de S3 (`Evidence.s3_key` vía `storage`) y pasar el contenido/extracto al prompt del review. NO se implementa ahora (S3 no configurado; el storage degrada sin guardar el archivo).

## Out of scope

- Correo real (Resend/SendGrid) + scheduler de recordatorios +7/+14/+21.
- Leer el contenido real de los documentos (requiere S3).
- Sistema de notificaciones persistido (léído/no-léído con tabla) — se eligió la versión derivada/calculada.

## Decisiones tomadas

- **Sin infra ahora:** construir avisos in-app + análisis enriquecido; correo y lectura de contenido son enchufes documentados. (Usuario.)
- **Avisos = push arriba (esquina superior derecha)**, derivados de las alertas existentes + "Secretario revisó tu mes". Dismiss por sesión. (Usuario.)
- **Análisis enriquecido = presencia del documento requerido** (no su contenido). (Constraint S3.)

## Testing

- **Backend (pytest, puro):**
  - `compute_signals` con `evidence_counts`: arma `tasks_missing_doc` correctamente (tarea con `required_doc` y 0 evidencias → aparece; con evidencia → no; sin `required_doc` → no).
  - `deterministic_review`: cuando hay `tasks_missing_doc`, el review determinista lo refleja (en summary o proposals).
  - `compute_alerts`: emite la alerta "Secretario revisó tu mes" cuando hay mes `done` con propuestas sin aplicar; no la emite si no.
- **Frontend (sin suite UI):** `npm run lint` + `npm run build` + smoke (con un plan con alertas → aparecen los avisos arriba-derecha; cerrar uno no reaparece en la sesión; sin plan → no aparece nada).

## Notas / riesgos

- `_run_close` corre los conteos de evidencia en su propio `AsyncSessionLocal` — agregar la consulta GROUP BY ahí (las `tasks` ya están cargadas en ese bloque).
- Los avisos no deben ser molestos: dismiss por sesión + entrada discreta. Si en smoke se sienten intrusivos, limitar a las alertas críticas (vencidas) y la de revisión.
- Compatibilidad: planes viejos sin `required_doc` en sus tareas → `tasks_missing_doc` vacío, todo sigue igual.
