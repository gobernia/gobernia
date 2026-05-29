# Diseño — Subproyecto E: Revisión de fin de mes

**Fecha:** 2026-05-29
**Estado:** Aprobado para planificación
**Depende de:** backend del plan de 12 meses (en `main`: `AnnualPlan/MonthlyPlan/Objective`, `MonthlyPlan.review` reservado, agentes `run_agent_analysis`/`run_challenger_critique`/`run_agent_revision`, `kpi_engine`) y del frontend A.2 (la página `/dashboard/plan`, en la rama `feat/plan-12-meses-frontend`, sobre la cual esta rama está apilada).

## Objetivo

Cerrar el ciclo del plan: al final de cada mes el consejo revisa el avance, **califica** ("vas bien / vas mal / vas muy mal") y **propone ajustes** al mes siguiente. Convierte el plan de una foto estática en algo que se corrige con la realidad — alineado con la métrica del brief: *"medimos empresas que cumplen objetivos estratégicos"*.

## Decisiones de diseño (brainstorming)

1. **Disparador:** botón manual **"Cerrar mes y revisar"** en el mes activo. Sin cron/Redis (no hay infra aún); el cierre automático queda fuera de alcance.
2. **Calificación:** **híbrida** — se calculan señales objetivas (% tareas completadas, tareas atrasadas, avance de KPIs vs benchmark) y se pasan a los **4 agentes + Challenger**, que asignan la calificación (`bien`/`mal`/`muy_mal`) y escriben el porqué + las propuestas.
3. **Alcance del ajuste:** **solo el mes siguiente** (N+1).
4. **Aplicación:** los cambios se **proponen**; el usuario los **aprueba** uno por uno. Nada se aplica sin su OK.
5. **KPIs:** se **capturan al cerrar el mes** (los `kpi_refs` de los objetivos del mes); el grade usa tareas + avance de KPIs.
6. **Arquitectura:** la revisión corre **síncrona**, reutilizando el patrón probado del endpoint `/analyse` (libera la conexión a DB, corre los agentes en `anyio.to_thread`, reabre para persistir). Sin infra nueva. El frontend muestra la animación `AgentsCollaboration` mientras espera.

## Flujo "Cerrar mes"

En `/dashboard/plan`, el mes con `status == "active"` muestra el botón **"Cerrar mes y revisar"**:

1. **Captura de KPIs:** modal que lista los KPIs del mes (unión de `kpi_refs` de sus objetivos) y pide el valor actual de cada uno.
2. `POST /annual-plan/months/{month_index}/close` con `{ kpis: {label: value} }`.
3. **Backend:**
   - Calcula **señales** del mes: `tasks_total`, `tasks_completed`, `tasks_overdue` (due_date < hoy y status != completada), `completion_pct`; y por KPI: `value` (capturado), `target` (benchmark de `kpi_engine` desde el `memory_buffer` del onboarding), `on_track` (bool).
   - Corre **4 agentes + Challenger** con un prompt de "revisión de mes" (contexto: empresa, foco del mes, objetivos, señales) → cada agente opina; el Challenger cuestiona; se sintetiza: `grade` ∈ {bien, mal, muy_mal}, `summary` (narrativa del consejo) y `proposals` (cambios al mes N+1).
   - Persiste en `MonthlyPlan.review` (JSONB). Marca el mes `done` y el siguiente `active`.
   - Devuelve el `review`.
4. **Frontend:** muestra **banner de calificación** + resumen del consejo + lista de **propuestas** con botón **"Aplicar"** por cada una.
5. **Aplicar propuesta:** materializa el cambio en el mes N+1 (crear objetivo/tarea, o arrastrar tarea incompleta) y marca la propuesta como `applied` en el `review`.

## Tipos de propuesta (cada una = cambio concreto al mes N+1)

- `carry_over_task` — mover una tarea incompleta del mes N al mes N+1. Campos: `task_id`, `reason`.
- `new_objective` — nuevo objetivo en N+1. Campos: `title`, `description`, `kpi_refs`, `reason`.
- `new_task` — nueva tarea bajo un objetivo de N+1. Campos: `objective_id` (del mes N+1; si el objetivo aún no existe, el usuario primero aplica el `new_objective`), `title`, `owner`, `priority`, `kpi_ref`, `reason`.

Cada propuesta lleva `id` (uuid string) y `applied: bool`. Aplicar es idempotente (si ya está `applied`, no duplica).

## Modelo de datos

No requiere migración: usa `MonthlyPlan.review` (JSONB, ya existe). Forma:

```json
{
  "grade": "bien | mal | muy_mal",
  "closed_at": "ISO-8601",
  "signals": {
    "tasks_total": 5, "tasks_completed": 3, "tasks_overdue": 1, "completion_pct": 60,
    "kpis": [{"label": "Razón corriente", "value": 1.2, "target": 1.5, "unit": "x", "on_track": false}]
  },
  "summary": "narrativa del consejo",
  "by_agent": {"CFO": "...", "CSO": "...", "CRO": "...", "Auditor": "..."},
  "proposals": [
    {"id": "uuid", "type": "carry_over_task", "task_id": "uuid", "reason": "...", "applied": false},
    {"id": "uuid", "type": "new_objective", "title": "...", "description": "...", "kpi_refs": [], "reason": "...", "applied": false}
  ]
}
```

El cierre de un mes solo se permite si el mes está `active` (un mes `done` ya tiene `review`; reabrir queda fuera de alcance).

## Servicios y lógica (backend)

- `app/services/ai/month_review.py` (nuevo):
  - `compute_signals(month, kpi_values, kpi_templates) -> dict` — puro, testeable: cuenta tareas/atrasos/% y arma la lista de KPIs con `on_track` (compara valor vs benchmark según dirección del KPI que ya maneja `kpi_engine`).
  - `parse_review(raw, ...) -> dict` — normaliza la respuesta del LLM a `{grade, summary, by_agent, proposals}`; `grade` se clampa a {bien, mal, muy_mal}; cada proposal se valida y se le asigna `id`/`applied=false`; tipos desconocidos se descartan.
  - `run_month_review(month, signals, memory_buffer) -> dict` — corre los agentes + Challenger (reusando funciones de `agents/base.py`) con el prompt de revisión; sin API key, cae a un review determinista (grade por `completion_pct`: ≥80 bien, 50–79 mal, <50 muy_mal; proposals = arrastrar tareas incompletas).
- Endpoint de cierre y de aplicar propuesta en `app/api/v1/annual_plan/router.py` (mismo router del plan), reutilizando el patrón síncrono de `/analyse` (`anyio.to_thread` + reabrir sesión para persistir).

## Endpoints (API)

- `POST /annual-plan/months/{month_index}/close` — body `{ kpis: {label: number} }`. Valida que el mes sea del usuario y esté `active`. Corre la revisión, persiste `review`, marca mes `done` y siguiente `active`. Responde el `MonthlyPlanOut` del mes cerrado (con `review`) + el `active_month_index` nuevo.
- `POST /annual-plan/months/{month_index}/apply-proposal` — body `{ proposal_id }`. Materializa la propuesta en el mes N+1 (crea objetivo/tarea o mueve tarea), marca `applied=true` en el `review` del mes N. Responde el `review` actualizado. (Internamente reutiliza la lógica de creación de objetivos/tareas ya existente.)

## Frontend

Extiende `/dashboard/plan` (componentes bajo `components/plan/`):
- **Botón "Cerrar mes y revisar"** en el detalle del mes activo (`MonthDetail`).
- `CloseMonthModal` — captura de KPIs del mes (inputs numéricos por `kpi_ref`); al enviar, llama al endpoint y muestra la **animación** `AgentsCollaboration` mientras corre.
- `MonthReviewPanel` — banner de calificación (verde/ámbar/rojo para bien/mal/muy_mal) + resumen del consejo + lista de propuestas con botón "Aplicar" (deshabilitado/checked si `applied`).
- En `MonthTimeline`, los meses cerrados muestran su calificación (un punto/etiqueta de color).
- Tipos y funciones API nuevas en `lib/annualPlan.ts`: `closeMonth(monthIndex, kpis)`, `applyProposal(monthIndex, proposalId)`, y tipos `MonthReview`/`Proposal`.

## Manejo de errores

- Cerrar un mes que no está `active` → 409 con mensaje claro.
- Fallo del LLM / parseo → review determinista (no rompe el cierre); el mes igual se cierra con grade calculado por métricas.
- Aplicar una propuesta ya aplicada → no-op idempotente.
- Reusar el patrón de `/analyse` para no bloquear el event loop ni disparar el statement-timeout de Supabase.

## Pruebas

- **Unit:** `compute_signals` (conteos, % , overdue, on_track por dirección de KPI); `parse_review` (clamp de grade, validación/normalización de proposals, descarte de tipos desconocidos, review determinista sin API key).
- **Integración:** `POST /close` con DB mockeada (patrón `dependency_overrides`) — 200 con review, 409 si no está activo; `POST /apply-proposal` marca `applied` y crea la entidad. Agentes mockeados (sin red).
- **Frontend:** verificación manual local (sembrar plan, cerrar mes, ver calificación + propuestas, aplicar una, confirmar en el mes siguiente).

## Fuera de alcance (otros subproyectos / iteraciones)

- Cierre automático por cron (necesita infra Redis/worker).
- Entregables-archivo por tarea (subproyecto C); aquí el avance se mide por status de tarea + KPIs capturados.
- Reabrir un mes ya cerrado / editar un review.
- Re-planear todos los meses restantes (se decidió solo N+1).
- Recordatorios (D), Secretario/orden del día (B), confeti/emails (F).
