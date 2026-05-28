# Diseño — Subproyecto A: Plan estratégico de 12 meses

**Fecha:** 2026-05-28
**Estado:** Aprobado para planificación
**Subproyecto:** A (de la descomposición A–F del nuevo brief de producto)

## Contexto

El brief de producto evoluciona Gobernia de un flujo **reactivo y mensual** (sesión de
consejo → análisis → plan de acción plano) a uno **proactivo y anual con seguimiento
diario**. Al cerrar el onboarding, Gobernia debe producir automáticamente: (1) un
diagnóstico empresarial y (2) un plan estratégico de 12 meses, mes por mes.

Este spec cubre **solo el subproyecto A**: el diagnóstico inicial y el plan de 12 meses
(modelo de datos, generación con IA, API y la vista mínima para verlo/editarlo).

### Decisiones de producto ya tomadas (brainstorming)

1. **Plan anual = maestro; sesión mensual = revisión.** El plan de 12 meses es la fuente
   de verdad. Cada mes, la sesión de consejo no crea un plan nuevo: revisa el avance del
   mes y ajusta/reescribe el mes siguiente (esa lógica de revisión es el subproyecto E).
   El `ActionPlan` por-sesión actual se reemplaza conceptualmente por "el mes N del plan
   anual".
2. **Jerarquía del mes:** Mes → Objetivos (2-4) → Tareas. Los KPIs del mes se asocian a
   los objetivos.
3. **Generación IA:** Diagnóstico (4 agentes + Challenger) → esqueleto anual
   (objetivos + KPIs de los 12 meses) → detalle de tareas por mes.
4. **KPIs:** se reutilizan los del onboarding/`kpi_engine`. El plan los referencia; no se
   inventan metas numéricas nuevas por mes. Las tareas se enlazan a un KPI por "impacto".
5. **Modelo de datos (Enfoque 1):** modelos nuevos `AnnualPlan/MonthlyPlan/Objective` +
   reutilizar la tabla `action_tasks` existente para las tareas (colgando de
   `objective_id`, con `kpi_ref`).
6. **El plan es editable** por el usuario (objetivos y tareas: crear/editar/borrar).

## Modelo de datos

Enfoque 1: tablas nuevas para la estructura anual/mensual/objetivos; las tareas siguen en
`action_tasks` (que ya tiene `owner/priority/due_date/status/tags` y a la que ya se
asocian los `documents`).

```
AnnualPlan            (1 por empresa/usuario)
 ├─ id (uuid), user_id, title
 ├─ start_date (date en que se cerró onboarding)
 ├─ status: generating | active | failed | completed
 ├─ genesis_session_id  → FK board_sessions (sesión que guarda el DIAGNÓSTICO)
 ├─ diagnostico_summary (text)
 └─ timestamps

MonthlyPlan           (12 por AnnualPlan)
 ├─ id (uuid), annual_plan_id (FK, CASCADE)
 ├─ month_index (1..12)
 ├─ period_year, period_month   (calendario real = start_date + (month_index-1))
 ├─ focus (text corto: tema del mes)
 ├─ status: locked | active | done
 ├─ review (JSONB, nullable)     ← reservado para subproyecto E (calificación vas bien/mal)
 └─ timestamps

Objective             (2-4 por MonthlyPlan)
 ├─ id (uuid), monthly_plan_id (FK, CASCADE)
 ├─ title, description
 ├─ kpi_refs (JSONB: lista de ids/labels de KPIs del onboarding)
 ├─ order_index
 └─ timestamps

action_tasks          (EXISTENTE — se agregan 2 columnas)
 ├─ + objective_id (FK objectives, nullable durante migración)
 ├─ + kpi_ref (string, nullable)   ← "impacto KPI"
 └─ (sin cambios: title, description, source_agent, status, priority, owner,
     due_date, tags, order_index; plan_id queda legacy/nullable)
```

### Notas de migración

- Una migración Alembic agrega las 3 tablas nuevas y las 2 columnas a `action_tasks`.
- `action_tasks.plan_id` se vuelve nullable y queda como legacy. Los datos viejos (entorno
  de pruebas, volumen mínimo) no se migran; las tareas nuevas usan `objective_id`.
- El mes activo se computa desde `start_date` y la fecha actual; `MonthlyPlan.status`
  refleja locked/active/done.

## Flujo de generación

Corre en el **worker Celery** (`app/tasks/`), en proceso separado del web server, por lo
que las llamadas síncronas a Anthropic ahí no bloquean el event loop de FastAPI.

Disparador: al completar la **etapa-8** del onboarding se encola
`generate_annual_plan(user_id)`.

1. **Diagnóstico.** Corre los 4 agentes (CFO, CSO, CRO, Auditor) + Challenger sobre el
   `memory_buffer` del onboarding, reutilizando `run_agent_analysis` /
   `run_challenger_critique` / `run_agent_revision`. Se crea un `board_session` "génesis"
   que guarda los análisis; se sintetiza `diagnostico_summary`. Se setea
   `AnnualPlan.genesis_session_id`.
2. **Esqueleto anual.** Una llamada a Claude produce los 12 meses: cada uno con `focus` +
   2-4 objetivos, y para cada objetivo qué KPIs (de los existentes) toca, con progresión
   lógica a lo largo del año. Se crean `MonthlyPlan` + `Objective`.
3. **Detalle de tareas.** Por mes, se generan las tareas de cada objetivo extendiendo
   `plan_generator`: `title`, `owner`, `priority`, `due_date` dentro de la ventana del mes,
   `tags`, `kpi_ref`. Se crean filas en `action_tasks` con `objective_id`.
4. `AnnualPlan.status = active`; `MonthlyPlan` del mes en curso → `active`, el resto
   `locked`.

### Idempotencia y errores

- Cada paso guarda resultados parciales y es reintentable; un retry no duplica filas
  (se verifica existencia por `annual_plan_id` + `month_index` / `objective`).
- Parseo JSON: se reutilizan los helpers `_extract_json_object` / fallbacks existentes.
- Fallo de generación: `AnnualPlan.status = failed` + endpoint de retry.
- Sin `ANTHROPIC_API_KEY`: plan determinista mínimo (consistente con el fallback actual de
  `plan_generator`).

## API (FastAPI, `app/api/v1/annual_plan/`)

- `POST /annual-plan/generate` — encola la generación (se invoca automáticamente al cerrar
  etapa-8; expuesto también para retry manual).
- `GET /annual-plan/status` — `{status, step, progress}` para la pantalla de carga
  (reutiliza la animación `AgentsCollaboration`).
- `GET /annual-plan` — plan completo anidado (meses → objetivos → tareas).
- `GET /annual-plan/months/{month_index}` — un mes.
- `POST/PATCH/DELETE /annual-plan/objectives[/{id}]` — CRUD de objetivos.
- `POST/PATCH/DELETE /annual-plan/tasks[/{id}]` — CRUD de tareas (estado de tarea y subida
  de entregables ya existen vía `action_tasks` + `documents`).

## Frontend (solo lo de A)

- Cierre de onboarding → pantalla "generando tu plan" (reutiliza animación existente) →
  polling a `/annual-plan/status` → redirige al plan cuando `active`.
- **Vista del diagnóstico:** resumen de los 4 agentes (`diagnostico_summary` + génesis).
- **Vista del plan de 12 meses:** navegación por mes, mes actual expandido, objetivos →
  tareas, edición inline (crear/editar/borrar objetivos y tareas).
- *Nota de alcance:* el dashboard diario tipo Monday (con confeti, impacto-KPI visual y
  recordatorios) es el subproyecto C/F. Aquí solo se construye lo necesario para ver y
  editar el plan.

## Pruebas

- **Unit:** parser del esqueleto anual; mapeo de tareas (incl. normalización de `kpi_ref`,
  prioridad, owner); lógica de `due_date` dentro de la ventana del mes; cómputo del mes
  activo desde `start_date`.
- **Integración:** flujo `generate_annual_plan` completo con Anthropic mockeado →
  produce 12 meses con objetivos y tareas anidadas; transiciones de `status`
  (generating → active, y → failed con retry); idempotencia del retry; endpoints CRUD.

## Fuera de alcance (otros subproyectos)

- **B** — Agente Secretario + orden del día (PDF).
- **C** — Dashboard operativo tipo Monday (responsable/fecha/prioridad/impacto-KPI, subida
  de entregables en UI rica).
- **D** — Motor de recordatorios IA (diarios/semanales/vencimiento/riesgo/atraso).
- **E** — Revisión de fin de mes (llena `MonthlyPlan.review`, califica vas bien/mal/muy
  mal, reescribe el mes siguiente).
- **F** — Gamificación (confeti) + emails de cumplimiento.
