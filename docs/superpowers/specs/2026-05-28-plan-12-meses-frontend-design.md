# Diseño — Subproyecto A, parte 2: Frontend del Plan de 12 meses

**Fecha:** 2026-05-28
**Estado:** Aprobado para planificación
**Depende de:** backend del plan de 12 meses (ya en `main`: modelos, API REST, generación). Spec backend: `docs/superpowers/specs/2026-05-28-plan-12-meses-design.md`.

## Objetivo

Construir la interfaz para que el dueño vea y edite su plan estratégico de 12 meses
generado al cerrar el onboarding: pantalla de generación, diagnóstico, y la vista anual
(tira de tiempo + mes enfocado con objetivos→tareas), manteniendo la identidad de marca.

## Decisiones de diseño (brainstorming)

1. **Una sola ruta inteligente `/dashboard/plan`** que maneja todos los estados (igual que
   la página de plan por-sesión existente): sin-plan (404) → CTA generar; generando →
   animación + polling; falló → error + reintentar; activo → el plan.
2. **Post-onboarding:** al cerrar etapa-8, el frontend redirige a `/dashboard/plan` (que ya
   estará en estado "generando" porque el backend encoló la generación). Se agrega además
   una **tarjeta de entrada** al plan en el dashboard.
3. **Layout 12 meses:** tira de tiempo horizontal (mes activo marcado, scroll en móvil) +
   detalle del mes enfocado debajo.
4. **Dentro del mes:** objetivos agrupados; cada objetivo muestra sus KPIs y sus tareas
   como filas (responsable, fecha, prioridad). Click en tarea → drawer de edición.
5. **Diagnóstico:** sección colapsable al tope de la página activa, con el resumen de los
   4 agentes.
6. **Edición:** objetivos (crear/editar/borrar) y tareas (crear bajo objetivo, editar/borrar
   vía drawer). Updates optimistas, como en la página de sesión.
7. **Prueba local:** script de sembrado que inserta un plan de muestra (status `active`)
   sin IA ni Celery, para iterar la UI.

## Restricción del entorno

`frontend/AGENTS.md` advierte que esta versión de Next.js (16.x) tiene cambios de API/
convenciones respecto al conocimiento previo. **Antes de escribir código de frontend, leer
la guía relevante en `frontend/node_modules/next/dist/docs/`** y respetar las convenciones
del proyecto (App Router, los patrones ya usados en `dashboard/sesion/[id]/plan/page.tsx`).

## Rutas y estados

`frontend/src/app/dashboard/plan/page.tsx` — página cliente que:
- Al montar: `GET /annual-plan`. Según el resultado:
  - **404** → estado "sin plan": CTA "Generar plan" → `POST /annual-plan/generate` → pasa a "generando".
  - **status `generating`** → pantalla de generación + *polling* a `GET /annual-plan/status`
    cada 2.5s; al volverse `active`, recarga `GET /annual-plan` y muestra el plan.
  - **status `failed`** → error + botón "Reintentar" (`POST /annual-plan/generate`).
  - **status `active`** → render del plan.
- Onboarding `etapa-8/page.tsx`: al completar, `router.push("/dashboard/plan")` (en lugar de ir al dashboard).
- `dashboard/page.tsx`: tarjeta/enlace "Plan estratégico" → `/dashboard/plan`.

## Componentes (archivos enfocados)

Todos bajo `frontend/src/components/plan/` salvo la página.

- `app/dashboard/plan/page.tsx` — orquesta estados, carga, polling, y las mutaciones (crear/editar/borrar objetivos y tareas con updates optimistas).
- `components/plan/AgentsCollaboration.tsx` — **extracción** de la animación de agentes que
  hoy vive dentro de `dashboard/sesion/[id]/page.tsx`, a un componente compartido. La página
  de sesión se actualiza para importarlo desde aquí (mejora puntual, sin cambiar su
  comportamiento). Acepta un `label`/copy opcional para el contexto de generación del plan.
- `components/plan/DiagnosticoPanel.tsx` — sección colapsable; recibe `diagnostico_summary`
  (texto con formato `**Agente:** resumen`) y lo renderiza legible.
- `components/plan/MonthTimeline.tsx` — tira horizontal de 12 meses; props: `months`,
  `activeIndex`, `selectedIndex`, `onSelect`. Marca visualmente el mes activo (status
  `active`) y el seleccionado; estados done/locked con estilo sutil.
- `components/plan/MonthDetail.tsx` — encabezado del mes (nombre + foco) y la lista de
  `ObjectiveCard`. Botón "agregar objetivo".
- `components/plan/ObjectiveCard.tsx` — título del objetivo (editable inline), KPIs (badges
  de `kpi_refs`), sus tareas como `TaskRow`, botón "+ tarea", y borrar objetivo.
- `components/plan/TaskRow.tsx` — fila compacta (título, responsable, fecha, prioridad,
  KPI); click → abre el drawer.
- `components/plan/TaskDrawer.tsx` — drawer lateral de edición de tarea (título, estado,
  prioridad, responsable, fecha límite, KPI, etiquetas, borrar), reusando el lenguaje visual
  del `TaskEditor` existente.

## Capa de datos

`frontend/src/lib/annualPlan.ts` — tipos TypeScript (`AnnualPlan`, `MonthlyPlan`, `Objective`,
`Task`) y funciones que envuelven `api` (axios existente):
- `getAnnualPlan()` → `GET /annual-plan`
- `getAnnualPlanStatus()` → `GET /annual-plan/status`
- `generateAnnualPlan()` → `POST /annual-plan/generate`
- `createObjective(body)` / `updateObjective(id, patch)` / `deleteObjective(id)`
- `createTask(body)` → `POST /annual-plan/tasks`
- `updateTask(id, patch)` → `PATCH /tasks/{id}` (endpoint existente)
- `deleteTask(id)` → `DELETE /tasks/{id}` (endpoint existente)

El cliente `api` ya inyecta el token Supabase vía interceptor (`lib/api.ts`).

## Manejo de errores

- Carga inicial: 404 → estado sin-plan (no es error); otros → mensaje "No se pudo cargar el plan" + reintentar.
- Polling: si `/status` devuelve `failed` → estado fallo con reintento; si la red falla, se reintenta en el siguiente tick.
- Mutaciones: update optimista; si la llamada falla, se recarga el plan para revertir (patrón ya usado en la página de sesión).

## Prueba local (sembrado)

`backend/scripts/seed_sample_annual_plan.py` — inserta directamente vía `AsyncSessionLocal`
un `AnnualPlan` (status `active`, `diagnostico_summary` de muestra) con 12 `MonthlyPlan`
(mes 1 `active`, resto `locked`), 2 objetivos por algunos meses y 2-3 `action_tasks` por
objetivo, para un `user_id` dado (argumento o el usuario de prueba). No usa IA ni Celery.

Flujo de prueba: correr el seed → `cd backend && venv/bin/uvicorn app.main:app --port 8000 --reload`
→ `cd frontend && npm run dev` → entrar a `/dashboard/plan` con el usuario sembrado y
ver/editar el plan.

## Estilo

Blanco/negro/gris; `--gob-navy`/`--gob-bone` para activo y botones; `framer-motion` para
transiciones; iconos `lucide-react`; contenedor fluido y responsive (la tira de meses hace
scroll horizontal en móvil). Consistente con `dashboard/sesion/[id]/plan/page.tsx`.

## Verificación

El frontend no tiene framework de tests automatizados. La verificación es **manual en local**:
sembrar datos, levantar front+back, y comprobar: render del plan, navegación entre meses,
edición de objetivo/tarea (persistencia tras recargar), creación/borrado, estado vacío y
de error, y responsive en ancho móvil. La pantalla de "generando" se valida dejando un plan
en status `generating` (el seed puede crear uno aparte o se ajusta el status manualmente).

## Fuera de alcance (otros subproyectos)

- Tablero Monday con columnas de estado y confeti (C/F).
- Recordatorios IA (D).
- Agente Secretario / orden del día PDF (B).
- UI de revisión de fin de mes — el campo `MonthlyPlan.review` se muestra solo si existe,
  sin UI de edición (E).
- Edición de valores de KPI (los `kpi_refs` se muestran como etiquetas de referencia).
