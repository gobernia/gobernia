# Plan a 3 años: Camino + Timeline + tareas explicadas — Diseño

**Fecha:** 2026-06-22
**Alcance:** Rediseñar la experiencia del plan estratégico a 3 años: entrada desde la **vista FODA**, generación **informada por FODA + metas priorizadas**, **tareas explicadas** (qué es / cómo hacerlo / tiempo / dificultad, generadas bajo demanda) y una **UI nueva con dos vistas** (Camino enfocado en el mes en curso · Timeline panorámico) que **reemplaza** el kanban actual de `/dashboard/plan`. Reutiliza el motor de plan a 3 años (Fase 3A) y el sistema de estados/evidencias que ya existen.

## Goal

Que el dueño, tras su FODA, genere su **plan a 3 años** alineado a sus prioridades y lo siga de forma clara: un **recorrido mes a mes** que enfoca lo de **este mes** (objetivo + tareas), donde cada tarea se puede **expandir para entender qué es y cómo hacerla** (con tiempo y dificultad), marcarla como hecha, y ver el **panorama completo** (timeline) cuando quiere planear. Sobrio y on-brand, no gamificado.

## Architecture

Reutiliza casi todo lo de Fase 3A (`AnnualPlan → MonthlyPlan → Objective → ActionTask` + hitos + `compute_active_month_index` + el generador async por Celery). Cambios:

- **Entrada + generación:** la vista FODA dispara la generación del plan; el generador recibe además el **FODA + metas** (de `DiagnosticoEstrategico.content`) como contexto, para alinear objetivos/tareas a lo prioritario.
- **Tareas explicadas:** una columna nueva `ActionTask.explicacion` (JSONB) + un endpoint que la **genera bajo demanda** (al expandir una tarea por primera vez) y la cachea.
- **UI:** `/dashboard/plan` se reescribe a **Camino + Timeline** (on-brand), leyendo los mismos datos. El kanban actual se reemplaza.

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Celery, anthropic (Sonnet 4.6 para la explicación de tareas). Columna nueva vía `scripts/alter_*` (NO Alembic).
- Frontend: Next.js 16 App Router, framer-motion, lucide-react. Estilo de marca (`--gob-navy`/`--gob-bone`/`--gob-ink`).

---

## Componente 1 — Generación informada por FODA + metas

**Modificar:** el generador del plan (`backend/app/services/ai/annual_plan_generator.py` / la orquestación en `app/tasks/annual_plan_tasks.py`) para inyectar, además del `memory_buffer`, el **FODA + metas priorizadas** (de `DiagnosticoEstrategico.content["foda"]` y `["metas_orden"]`). El prompt de generación los usa para que objetivos y tareas ataquen las prioridades del dueño y las debilidades/amenazas del FODA. Mismo flujo async (Celery, hitos, N×12 meses, horizonte default 3). Sin rehacer el motor.

**Entrada:** en la vista FODA (`/dashboard/foda`), botón **"Generar mi plan a 3 años"** que llama al endpoint de generación de plan existente (con `horizon_years=3`) y lleva a `/dashboard/plan`. Si ya hay un plan, advierte que se regenera (como hoy).

## Componente 2 — Tareas explicadas (bajo demanda)

**Modificar:** `backend/app/models/action_plan.py` (columna `explicacion`), `backend/app/api/v1/...` (endpoint), `backend/app/services/ai/` (generador de la explicación). **Crear:** `backend/scripts/alter_task_explicacion.py`.

- `ActionTask.explicacion: dict | None` (JSONB) — cache de la explicación. Forma:
  ```
  {"tiempo": "~2 h", "dificultad": "Fácil|Media|Difícil",
   "que_es": "explicación clara, sin tecnicismos",
   "como": ["paso 1", "paso 2", "paso 3"]}
  ```
- Endpoint `POST /tasks/{task_id}/explicacion` (autoriza al dueño de la tarea, patrón `_get_user_task_or_404`): si la tarea ya tiene `explicacion`, la devuelve; si no, la **genera** con Sonnet (contexto: título de la tarea, su objetivo/mes, empresa, KPI) → `{tiempo, dificultad, que_es, como}` (salida estructurada por tool use, como Todd), la **guarda** en la columna y la devuelve. `GET /tasks/{task_id}/explicacion` opcional para leer la cacheada.
- Función pura de generación + parseo testeable (con el LLM mockeado).

## Componente 3 — UI nueva: Camino + Timeline

**Reescribir:** `frontend/src/app/dashboard/plan/page.tsx`. **Reutilizar/ajustar:** componentes del plan. **Crear:** `frontend/src/components/plan/CaminoView.tsx`, `TimelineView.tsx`, `TaskExplained.tsx`. **Cliente:** ampliar `frontend/src/lib/annualPlan.ts` (explicación) .

- **Toggle Camino / Timeline** arriba (estilo de marca, sobrio).
- **Encabezado:** título del plan + barra de progreso "Mes X de 36 · Y% completado" (reutiliza `compute_active_month_index` / el `active_month_index` que ya expone el API).
- **Vista Camino:**
  - **Recorrido de meses**: nodos en fila — meses pasados con ✓, **mes actual resaltado** (más grande, acento navy, sin efectos llamativos), futuros numerados/atenuados. Scroll horizontal si no caben.
  - **Tarjeta "Este mes"**: el **objetivo del mes** (focus) + sus **tareas**. Cada tarea: checkbox (marcar hecha) + título (tachado si hecha) + chevron para **expandir**.
    - Al expandir por primera vez → llama `POST /tasks/{id}/explicacion` (loader breve) → muestra **⏱ tiempo · dificultad · "Qué es" · "Cómo hacerlo" (pasos)**.
  - Contador "X de Y hechas".
- **Vista Timeline:** grid **año × 12 meses**; cada celda coloreada (pasado ✓ / actual resaltado / futuro). Click en un mes → enfoca ese mes (o lo abre). Para planear, no para el día a día.
- **Marcar hecha:** el checkbox usa el **estado de tarea existente** (`PATCH /tasks/{id}` status→`completada`/`validado`) y **respeta el candado de evidencia** (las tareas con `required_doc` siguen necesitando el documento para validarse — se muestra el aviso/chip "Necesita: {doc}" como hoy, y al intentar marcar sin evidencia, el flujo de evidencia que ya existe).

## Out of scope

- Rehacer el motor de generación del plan (se reutiliza Fase 3A).
- Notificaciones nuevas, PDF del plan-camino (futuro).
- Enlazar Todd como entrada por defecto (pendiente separado).
- La "vista revista"/kanban actual se reemplaza; no se mantiene en paralelo.

## Decisiones tomadas

- **Reemplaza** el kanban actual de `/dashboard/plan`, **reutilizando el motor** del plan a 3 años. (Usuario.)
- **Explicación de tareas bajo demanda** (al expandir, cacheada). (Usuario.)
- **Generación informada por FODA + metas**. (Usuario.)
- **Estilo Gobernia, sobrio** — Camino como recorrido claro, no gamificado. (Decisión, alineada a la cancelación previa de gamificación.)
- **Marcar hecha** reutiliza estado + candado de evidencia existentes.

## Testing

- **Backend (pytest, LLM mockeado):** el generador incluye FODA+metas en el prompt; la generación de explicación arma `{tiempo,dificultad,que_es,como}` y el endpoint la cachea (2ª llamada no regenera); autorización de la tarea.
- **Frontend:** `npm run lint` + `npm run build` + smoke (toggle Camino/Timeline; expandir tarea → explicación; marcar hecha; mes actual resaltado; botón "Generar mi plan" desde FODA).

## Notas / riesgos

- **Costo:** la explicación es 1 llamada Sonnet por tarea **solo al abrirla** (cacheada) → barato y acotado. La generación del plan ya existía (no se encarece salvo el contexto extra del FODA, mínimo).
- **Esquema en prod:** correr `scripts/alter_task_explicacion.py` (idempotente, `ADD COLUMN IF NOT EXISTS`) al desplegar, con autorización.
- **Reutilización:** el cálculo de mes activo, los estados de tarea, el candado de evidencia y los hitos ya existen — esto es UI + enriquecimiento, no un motor nuevo.
- **Sobriedad:** el "recorrido" debe verse profesional (acentos navy, tipografía clara), evitando lo lúdico/infantil; coherente con la marca.
