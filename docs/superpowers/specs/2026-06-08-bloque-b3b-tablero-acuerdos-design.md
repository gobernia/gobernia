# Bloque B3b — Tablero de Acuerdos (Monday) (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Continuación de B3 (Acuerdos + Evidencias, ya en producción). B3 dejó: `ActionTask` como
acuerdo, entidad `Evidence` ligada a la tarea, y el gate de cierre (no se valida sin
evidencia). B3b agrega la **vista operativa**: el Tablero de Acuerdos tipo Monday.

Hechos del codebase:
- La página `frontend/src/app/dashboard/plan/page.tsx` carga el plan completo
  (`AnnualPlan` con `months[].objectives[].tasks[]`) en memoria y ya tiene `updateTask`
  optimista (`patchTaskLocal` + `updateTask`).
- **dnd-kit ya es dependencia** (lo usa el tablero por sesión `dashboard/sesion/[id]/plan`).
- El gate de B3 vive en `PATCH /tasks/{id}` (409 si se pone `completada` sin evidencia).

## Alcance de B3b

Una vista nueva en `/dashboard/plan` (toggle **"Meses" / "Tablero"**): 3 columnas por estado
con todos los acuerdos del plan como tarjetas, con drag-and-drop entre columnas. Casi todo
frontend; un pequeño añadido backend (`evidence_count`).

**Fuera de alcance de B3b**: reordenar dentro de una columna (solo mover entre columnas),
filtros/búsqueda, el Tablero de Cobertura (B4), PDF (B5), alertas (B6).

## Backend

Agregar `evidence_count: int = 0` al esquema `ActionTaskOut` (`app/schemas/action_plan.py`).

Poblarlo **solo en `GET /annual-plan`** (`get_plan` en `app/api/v1/annual_plan/router.py`):
- Tras reunir todas las tareas del plan, una **sola consulta agrupada** sobre `evidences`:
  `select(Evidence.action_task_id, func.count()).where(Evidence.action_task_id.in_(task_ids)).group_by(Evidence.action_task_id)`
  → mapa `{task_id: count}`.
- Threadear el mapa por los serializadores: `_objective_out(o, tasks, evidence_counts)` →
  `_task_out(t, evidence_count)`. Se añade un parámetro opcional `evidence_counts: dict | None
  = None` a `_objective_out` y `evidence_count: int = 0` a `_task_out`; los demás llamadores
  (get_month, create/update) pasan el default → `evidence_count = 0` (no afecta al Tablero,
  que usa `get_plan`).
- Sin migración (la tabla `evidences` ya existe; el conteo es derivado).

## Frontend

- **Tipo**: agregar `evidence_count: number` a `Task` en `frontend/src/lib/annualPlan.ts`.
- **Toggle** "Meses / Tablero" en la vista `active` de `dashboard/plan/page.tsx` (un estado
  local `boardView: "meses" | "tablero"`), encima del contenido del plan.
- **Componente `AcuerdosBoard`** (`frontend/src/components/plan/AcuerdosBoard.tsx`):
  - Recibe el `plan` (AnnualPlan) + callbacks. Aplana `plan.months[].objectives[].tasks[]` a
    una lista de acuerdos; a cada uno le adjunta el contexto de su mes (`month_index`,
    `period_month`, etc.) para mostrarlo.
  - Agrupa en 3 columnas por `status`: **Pendiente** (`pendiente`) · **En proceso**
    (`en_progreso`) · **Validado** (`completada`).
  - **Drag-and-drop** con dnd-kit (mismo patrón que el tablero por sesión): soltar una
    tarjeta en otra columna llama a un callback `onMoveTask(taskId, newStatus)`.
  - **Gate**: si el destino es `completada` y la tarjeta tiene `evidence_count === 0`, NO se
    mueve; se muestra un aviso breve ("Sube evidencia para validar este acuerdo") y la tarjeta
    vuelve a su columna. (Mismo criterio que el TaskDrawer; evita un request que fallaría 409.)
  - **Tarjeta**: título, responsable (`owner`), etiqueta del mes, punto de color por prioridad,
    e indicador de evidencia (ícono clip + `evidence_count` cuando > 0).
  - **Click** en una tarjeta → `onTaskClick(task)` que abre el `TaskDrawer` existente (la
    página ya tiene esa lógica de drawer; el board la dispara).
- **Integración en la página**: `onMoveTask` reusa el `updateTask` optimista existente
  (`patchTaskLocal(taskId, {status})` + `updateTask(taskId, {status})`, con `loadPlan()` de
  fallback en error — el mismo patrón ya usado para editar tareas). El gate del front evita
  llamar al server cuando no hay evidencia; si aún así llega un 409, el fallback recarga.

## Pruebas

- Backend: test de `get_plan` que verifica `evidence_count` correcto por tarea (mockeando la
  consulta de conteo agrupada). Suite completa verde, sin regresiones.
- Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos. La
  función pura de aplanado/agrupado por estado se puede extraer y testear (opcional).

## Criterio de "hecho" para B3b

- `GET /annual-plan` devuelve `evidence_count` por tarea.
- El dueño ve el Tablero (toggle), mueve acuerdos entre columnas con drag, y no puede soltar
  en "Validado" un acuerdo sin evidencia.
- Las tarjetas muestran el indicador de evidencia; el click abre el drawer.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas (para sub-proyectos siguientes)

- B4 Tablero de Cobertura (semáforo) reusará el `evidence_count`/estado para alimentar el
  "validado = decisión + evidencia".
- Reordenar dentro de columna, filtros y persistencia de orden: posterior si se pide.
