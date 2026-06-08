# Bloque B2 — Calendario de Cobertura + Orden del Día (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Segundo sub-proyecto del Motor de Cobertura del Consejo (Bloque B). B1 ya entregó la
entidad `BoardTheme` (Temas del Consejo, con `type` permanente|cobertura|emergente,
`every_n_sessions`, `active`, `order_index`) y su catálogo por defecto sembrado por plan.

B2 construye el **motor determinista** que computa qué temas tocan en cada sesión (mes) y
arma la **orden del día** de cada mes, con los datos del plan enganchados.

Decisiones acordadas en brainstorming:
- Orden del día = **determinista + datos del plan** (sin IA).
- Distribución de cobertura = **balanceada** (arranque escalonado; evaluaciones anuales al
  cierre del año).
- **Cadencia mensual fija = 12 sesiones** (cada `MonthlyPlan` es una sesión; de B1).

## Alcance de B2

- Computar el **calendario de cobertura**: qué temas (permanentes + cobertura) están
  programados en cada una de las 12 sesiones, de forma determinista a partir de los temas
  **activos** del plan.
- Exponer la **orden del día** de cada mes: temas programados agrupados + los objetivos/KPIs
  de ese mes (que ya existen de A).
- Mostrarla en el dashboard, en el detalle de cada mes.

**Fuera de alcance de B2** (van en sub-proyectos siguientes): registrar/solicitar Acuerdos y
Evidencias (B3), reprogramar pendientes (B3), el semáforo del Tablero de Cobertura (B4), el
PDF (B5), las alertas (B6) y la inyección de temas **emergentes** (capa posterior; requiere
detección de desviaciones).

## Modelo de datos

**No se agrega tabla.** La orden del día es **derivada** (temas activos + regla de
distribución + objetivos del mes). Se computa al leer. Ventaja: si el dueño edita
frecuencias/temas en B1, el calendario se actualiza solo.

*(Nota de futuro: cuando lleguen Acuerdos/emergentes en B3 se persistirá un snapshot de la
orden del día al "celebrar" la sesión. Eso es fuera de B2.)*

## La regla de distribución (determinista)

Sesiones = `month_index` 1..12. Solo se consideran temas con `active = true`.

- **Permanentes** (`type=permanente`, `every_n_sessions=1`): programados en **todas** las
  sesiones 1..12.
- **Cobertura** (`type=cobertura`): se agrupan por `every_n_sessions` (N); dentro de cada
  grupo se ordenan por `order_index` y se enumeran con índice `i` (0-based):
  - **N ∈ {2, 3, 6}** (bimestral/trimestral/semestral): el tema con índice `i` se programa en
    las sesiones `s ∈ 1..12` donde `(s - 1) % N == i % N`.
  - **N = 12** (anual): se ancla al **cierre del año**: el tema con índice `i` se programa en
    la sesión `12 - i` (es decir, el primer anual del grupo en la sesión 12, el segundo en la
    11, etc.). Si `12 - i < 1` (más de 12 anuales, caso irreal) el tema no se programa.
- **Emergentes** (`type=emergente`): no se programan en B2 (lista vacía).

Resultado con el catálogo por defecto de B1 (sirve de verificación en las pruebas):

| Tema | Tipo | N | Sesiones |
|------|------|---|----------|
| (los 5 permanentes) | permanente | 1 | 1–12 |
| Talento y sucesión | cobertura | 2 | 1,3,5,7,9,11 |
| Tecnología y ciberseguridad | cobertura | 2 | 2,4,6,8,10,12 |
| Auditoría | cobertura | 3 | 1,4,7,10 |
| Cumplimiento normativo | cobertura | 3 | 2,5,8,11 |
| ESG / Sostenibilidad | cobertura | 3 | 3,6,9,12 |
| Planeación estratégica | cobertura | 6 | 1,7 |
| Evaluación del Director General | cobertura | 12 | 12 |
| Evaluación del Consejo | cobertura | 12 | 11 |

(Los `order_index` del catálogo: evaluacion_dg=11, evaluacion_consejo=12 → en el grupo anual
i=0 es evaluacion_dg → sesión 12; i=1 es evaluacion_consejo → sesión 11.)

Temas de cobertura personalizados (que el dueño agregue en B1) entran a su grupo de
frecuencia por `order_index` y extienden el escalonado con la misma regla.

## Motor (backend)

`backend/app/services/governance/coverage_calendar.py`:

- `theme_sessions(themes: list[BoardTheme], total_sessions: int = 12) -> dict[str, list[int]]`
  Devuelve, por `str(theme.id)`, la lista ordenada de sesiones (1..total) en que está
  programado, aplicando la regla anterior solo a temas `active`. Determinista, sin DB.
- `scheduled_for_session(themes, month_index) -> dict[str, list[BoardTheme]]`
  Devuelve `{"permanente": [...], "cobertura": [...]}` con los temas activos programados en
  esa sesión (usando `theme_sessions`). Orden estable por `order_index`.

## API

Nuevo endpoint en el router de annual-plan:

`GET /annual-plan/months/{month_index}/orden-del-dia`

- Resuelve el plan activo del usuario (igual que los demás endpoints); 404 si no hay plan o
  el `month_index` no existe.
- Carga los temas (`active`) del plan y la `MonthlyPlan` de ese `month_index` con sus
  `objectives`.
- Responde `OrdenDelDiaOut`:
  ```
  {
    "month_index": int,
    "period_year": int,
    "period_month": int,
    "permanent_themes": [ ThemeRef, ... ],
    "coverage_themes":  [ ThemeRef, ... ],   // los programados ese mes
    "objectives":       [ ObjectiveOut, ... ]  // objetivos del mes (con KPIs)
  }
  ```
- Esquema en `backend/app/schemas/orden_del_dia.py`: `ThemeRef` = `{key: str, label: str,
  every_n_sessions: int | None}` (los permanentes traen `every_n_sessions=1`) y
  `OrdenDelDiaOut`. Reutiliza `ObjectiveOut` existente de `app/schemas/annual_plan.py`.

## Frontend

En el detalle de cada mes de `/dashboard/plan`, una sección **"Orden del día"**:

- Temas programados, agrupados (Permanentes / Cobertura), como lista legible (label +, para
  cobertura, la frecuencia en lenguaje natural reutilizando `FREQ_LABEL` de `lib/boardThemes.ts`).
- Bajo el bloque, un resumen compacto de los **objetivos del mes** (título + sus KPIs) — vista
  de lectura, no el editor (la gestión de objetivos/tareas se queda donde está).
- `frontend/src/lib/ordenDelDia.ts` (tipos + `getOrdenDelDia(monthIndex)`).
- Componente `frontend/src/components/plan/OrdenDelDiaPanel.tsx`, montado **al inicio** del
  detalle del mes (`MonthDetail`), de modo que la agenda se lea primero, encima del contenido
  existente del mes.

*(El botón "Descargar PDF" es B5 — no entra aquí.)*

## Pruebas

Backend (pytest):
- Unit de `theme_sessions` con el catálogo por defecto: permanentes en 1–12; bimestrales
  escalonados (impares/pares); trimestrales 3-way (1,4,7,10 / 2,5,8,11 / 3,6,9,12);
  semestral 1,7; anuales en 12 y 11; temas `active=false` excluidos; un tema de cobertura
  personalizado se ubica en su grupo de frecuencia.
- Unit de `scheduled_for_session` para un par de sesiones (p.ej. sesión 1 vs sesión 2).
- Integración del endpoint (db mockeada, patrón existente): la orden del día del mes N
  devuelve temas programados + objetivos del mes; 404 si no hay plan.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B2

- El motor computa el calendario determinista correcto (verificado contra el catálogo por
  defecto en pruebas).
- El endpoint devuelve la orden del día por mes (temas + objetivos).
- El dueño ve la orden del día de cada mes en `/dashboard/plan`.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas (para sub-proyectos siguientes)

- Persistencia/snapshot de la orden del día al "celebrar" la sesión → B3.
- Inyección de temas emergentes (requiere detección de desviaciones sobre señales de KPI) →
  capa posterior (con B6/alertas).
- Enganche fino de cada permanente a su fuente de datos (riesgos del diagnóstico, etc.): B2
  engancha los **objetivos/KPIs del mes**; un mapeo más fino por tema se puede afinar después.
