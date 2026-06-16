# Fase 3A — Plan estratégico a 3 años — Diseño

**Fecha:** 2026-06-16
**Alcance:** Backend (modelo + generador + API) + frontend (rediseño de la página del plan). Reutiliza la estructura de meses/objetivos/tareas y el sistema de evidencias.

## Goal

Convertir el plan de 12 meses en un **plan estratégico de N años (1/2/3, default 3)** con **hitos trimestrales/semestrales/anuales** generados por IA. De los hitos se derivan **tareas mensuales profesionales y medibles**, donde una tarea puede **pedir un documento de sustento** (ej. el estado de resultados del mes) que se sube como evidencia. El dashboard muestra arriba un **roadmap de hitos** y abajo las **tareas del mes en curso** + el orden del día resumido. Las Sesiones y Minutas se ocultan.

## Architecture

Se reutiliza el modelo existente `AnnualPlan → MonthlyPlan → Objective → ActionTask` (para no romper evidencias/compromisos/cierre de mes). Se agregan: `AnnualPlan.horizon_years`, `AnnualPlan.milestones` (JSONB) y `ActionTask.required_doc`. El generador se reescribe para ser **horizonte-aware y trimestre-primero**: genera los hitos del horizonte → por trimestre arma objetivos/tareas profesionales atadas a los hitos/KPIs (con `required_doc` cuando la meta lo amerita) → los distribuye en los 3 meses del trimestre (genera N×12 meses). Corre async (Celery), mismo patrón de estados que hoy. El frontend rediseña `/dashboard/plan`: roadmap de hitos arriba + tareas del mes abajo + orden del día resumido; oculta Sesiones/Minutas del menú.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Celery (`task_session`), anthropic SDK (`_create_with_retry`/`_extract_json_object`, `settings.AI_MODEL`). Columnas nuevas vía **script ALTER idempotente** (patrón `scripts/create_annual_plan_tables.py`, NO Alembic — ver [[prod-schema-no-alembic]]).
- Frontend: Next.js 16 App Router, TypeScript, framer-motion, lucide-react.

---

## Componente 1 — Modelo (columnas nuevas)

**Modificar:** `backend/app/models/annual_plan.py`, `backend/app/models/action_plan.py`. **Crear:** `backend/scripts/alter_plan_3anios.py`.

- `AnnualPlan`:
  - `horizon_years: int` (default 3) — 1, 2 o 3.
  - `milestones: dict | None` (JSONB) — los hitos. Forma:
    ```
    {"items": [
      {"type": "trimestral"|"semestral"|"anual", "year": 1, "period": 1,
       "title": str, "target": str, "kpi_ref": str|null}
    ]}
    ```
    `year` = 1..N; `period` = trimestre 1..4 (trimestral), semestre 1..2 (semestral), o 1 (anual). `target` = meta medible en texto.
- `ActionTask`:
  - `required_doc: str | None` — el documento/dato que la tarea pide para sustentar su meta (ej. "estado de resultados de marzo"); `null` si no requiere.
- **Script `alter_plan_3anios.py`** (idempotente, espejo de `create_annual_plan_tables.py`): `create_all` + `ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS horizon_years INTEGER NOT NULL DEFAULT 3` + `ADD COLUMN IF NOT EXISTS milestones JSONB` + `ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS required_doc TEXT`. Se corre contra prod **solo con autorización del humano** al desplegar.

> **No se agrega tabla nueva de hitos:** los hitos viven en `AnnualPlan.milestones` (JSONB) — son generados por la IA y **de solo lectura** (decisión del usuario: sin edición). El roadmap los lee de ahí.

## Componente 2 — Generador (reescritura horizonte-aware, trimestre-primero)

**Modificar:** `backend/app/services/ai/annual_plan_generator.py` y `backend/app/tasks/annual_plan_tasks.py`.

Nuevo flujo de generación (3 pasos, todos con la IA salvo el calendario):

1. **Hitos del horizonte** — `generate_milestones(memory_buffer, diagnostico, kpi_labels, horizon_years)`: 1 llamada → lista de hitos para los N años (un hito trimestral por cada trimestre = N×4; uno semestral por semestre = N×2; uno anual por año = N), cada uno con `title` + `target` medible (atado a un KPI cuando aplique). Anti-vacío + reintento (igual que el esqueleto actual). Se guardan en `AnnualPlan.milestones`.
2. **Por trimestre → objetivos + tareas profesionales** — `generate_quarter_plan(milestone_trimestral, hitos_relacionados, memory_buffer, kpi_labels, year, quarter)`: por cada trimestre, 1 llamada → objetivos (1-3) y **tareas profesionales, medibles y específicas** (no genéricas), cada tarea con: `title` accionable, `owner` (rol), `priority`, `kpi_ref`, y **`required_doc`** cuando la meta necesita sustento (ej. una meta de margen → "estado de resultados del mes"). El prompt instruye explícitamente: tareas medibles tipo "alcanzar X% de Y", y declarar el documento que las sustenta.
3. **Distribuir en meses** — `distribute_quarter_to_months(quarter_objectives_tasks, year, quarter, start_year, start_month)`: reparte los objetivos/tareas del trimestre en sus **3 meses calendario** (cada tarea cae en un mes con su `due_date`). Reusa los helpers de calendario (`month_calendar`, `due_date_within_month`).

- La task de Celery (`annual_plan_tasks`) orquesta: crea N×12 `MonthlyPlan`, corre los pasos 1→2→3 (los trimestres pueden paralelizarse como ya se hizo con los meses), persiste hitos + objetivos + tareas (con `required_doc`). Mismo blindaje (`task_session`, status, anti-vacío → `failed`).
- **Tareas profesionales:** es un cambio de *prompt* (medibles, atadas a KPI/hito, con documento de sustento), no de estructura. Se documenta en el prompt del paso 2.

## Componente 3 — API / generación

**Modificar:** `backend/app/api/v1/annual_plan/router.py`, `backend/app/schemas/annual_plan.py` (o donde vive el schema de generar).

- `POST /annual-plan/generate` acepta **`horizon_years`** (1/2/3, default 3) en el body. Valida 1≤n≤3. Persiste en `AnnualPlan.horizon_years`. Regenerar reemplaza el plan anterior (igual que hoy).
- `GET /annual-plan` devuelve `horizon_years`, `milestones` y, en cada tarea, `required_doc`. (Extender los schemas de salida `AnnualPlanOut`/`ActionTaskOut`.)
- El resto de endpoints (status, cierre de mes, evidencias, tareas) **sin cambios** — siguen colgando de los meses.

## Componente 4 — Frontend: rediseño de la página del plan

**Modificar:** `frontend/src/app/dashboard/plan/page.tsx`, `frontend/src/lib/annualPlan.ts`, `frontend/src/components/ui/Sidebar.tsx`, `frontend/src/components/plan/MonthDetail.tsx`. **Crear:** `frontend/src/components/plan/MilestoneRoadmap.tsx`.

- **`lib/annualPlan.ts`:** agregar tipos `Milestone` y el campo `milestones` + `horizon_years` en `AnnualPlan`; `required_doc` en `Task`. La generación manda `horizon_years` (selector 1/2/3, default 3) en `generateAnnualPlan`.
- **Roadmap de hitos (`MilestoneRoadmap.tsx`):** arriba de la vista activa del plan. Línea de tiempo de los N años con marcadores **trimestral/semestral/anual**; cada hito muestra `title` + `target` (meta). Solo lectura. El hito anual/semestral destacado.
- **Tareas del mes (reusa `MonthDetail` + el kanban de Fase 0):** abajo del roadmap, las tareas del mes en curso. Cada tarea, cuando tiene `required_doc`, muestra **"Necesita: {required_doc}"** (chip/etiqueta) y el flujo de subir ese documento es el de **evidencias que ya existe** (TaskDrawer); el candado de validación ya impide marcar "lograda" sin evidencia.
- **Orden del día** = resumen de las tareas del mes (debajo). Reusar/ajustar `OrdenDelDiaPanel` para que muestre el **resumen de las tareas del mes** (títulos), no el motor de señales.
- **Selector de horizonte:** al generar el plan (estado vacío), el botón abre un mini-selector **1 / 2 / 3 años** (default 3, "recomendado para tu consejo") antes de disparar la generación.
- **Ocultar Sesiones y Minutas:** quitar del `Sidebar` los ítems "Sesión del mes" (y cualquier acceso a minutas). La página `/dashboard/sesion-del-mes` y la pestaña de minuta quedan en el código pero **sin entrada en el menú** (no se borran — la 3B/decisión futura puede reactivarlas).

## Out of scope (es Fase 3B)

- Notificaciones a responsables (correo / campanita).
- Análisis profundo del Secretario al cierre de mes leyendo evidencias/docs (proponer tareas nuevas / seguir / alertas). El cierre de mes **actual** sigue funcionando como está.

## Decisiones tomadas

- **Horizonte:** elegible 1/2/3, **default 3** (recomendado para consejo). (Usuario.)
- **Reemplaza** la experiencia del plan de 12 meses; **oculta** Sesiones y Minutas. (Usuario.)
- **Navegación:** roadmap de hitos arriba + tareas del mes abajo + orden del día resumido. (Usuario.)
- **Tarea pide documento:** la tarea declara `required_doc` y se sube como **evidencia** (reusa el sistema existente + candado). (Usuario.)
- **Hitos:** generados por IA, **solo lectura** (sin edición). (Usuario.)
- **Modelo:** reusar `AnnualPlan/MonthlyPlan/Objective/ActionTask` + 3 columnas nuevas (sin tabla nueva).

## Testing

- **Backend (pytest, red mockeada):** lógica pura del generador nueva — `parse_milestones`, `generate_quarter_plan` parsing, `distribute_quarter_to_months` (reparto correcto en meses), y que `required_doc` se mapee. Endpoint `generate` con `horizon_years` (valida 1-3; default 3; encola). La task con el generador mockeado (transiciones de estado + N×12 meses creados).
- **Frontend (sin suite UI):** `npm run lint` + `npm run build` + smoke (generar con horizonte 3 → roadmap de hitos + tareas del mes con "Necesita: …"; Sesiones/Minutas ya no en el menú).

## Notas de implementación / riesgos

- **Indexado de meses:** hoy `MonthlyPlan.month_index` es 1..12. Para N años pasa a 1..(N×12) global; `period_year`/`period_month` siguen siendo el calendario real. Hay que generalizar `compute_active_month_index` y la navegación de mes (cap a N×12). Verificar que el cierre de mes y la navegación sigan correctos.
- **Costo/tiempo de generación:** N×4 trimestres × 1 llamada + 1 de hitos. Para 3 años = 12 llamadas de trimestre + 1 = 13 (similar al actual de 12 meses). Paralelizar trimestres como se hizo con los meses.
- **Migración de datos:** los planes existentes (12 meses, sin `horizon_years`/`milestones`) siguen válidos — `horizon_years` default 3, `milestones` null → el roadmap se oculta si no hay hitos. Regenerar produce el formato nuevo.
- **Aplicar columnas en prod:** correr `scripts/alter_plan_3anios.py` (idempotente) en el paso de integración/deploy, con autorización.
