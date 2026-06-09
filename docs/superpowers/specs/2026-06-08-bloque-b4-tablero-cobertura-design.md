# Bloque B4 — Tablero de Cobertura (marcado manual) (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

Cuarto sub-proyecto del Motor de Cobertura del Consejo. B1 (Temas), B2 (Orden del día),
B3 (Acuerdos+Evidencias) y B3b (Tablero de Acuerdos) ya están en producción.

B4 entrega el **Tablero de Cobertura**: la prueba de que Gobernia gestiona cobertura. Por
tema muestra esperadas vs realizadas + semáforo. Decisión acordada: **realizadas = marcado
manual** — el dueño marca qué temas quedaron cubiertos en cada sesión.

Hechos del codebase:
- `MonthlyPlan` (status `locked|active|done`) — el cierre de mes (E, `_run_close`) marca
  `status="done"`. `compute_active_month_index(start_date, today)` da el mes vigente (1..12).
- B2 `app/services/governance/coverage_calendar.py` → `theme_sessions(themes)` da, por tema
  activo, la lista de sesiones (1..12) en que está programado. Reusable para "esperadas".
- B2 endpoint `GET /annual-plan/months/{m}/orden-del-dia` (`OrdenDelDiaOut`) + panel
  `OrdenDelDiaPanel.tsx` — aquí se agrega el marcado.
- `_load_owned_month(month_index, user_id, db)` ya existe en el router de annual-plan.

## Alcance de B4

Marcar temas como **cubiertos** por mes (desde la Orden del Día) y un **Tablero de Cobertura**
(esperadas vs realizadas + semáforo).

**Fuera de alcance de B4**: ceremonia de "cerrar sesión" con cobertura decisión+evidencia
automática, temas emergentes, PDF (B5), alertas (B6).

## Modelo de datos

Agregar `covered_themes: list[str]` (JSONB, default `[]`) a `MonthlyPlan` — la lista de
**keys de tema** marcados como cubiertos ese mes. **Sin tabla nueva.**

Migración aditiva: `ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS covered_themes JSONB
DEFAULT '[]'::jsonb` vía un script `scripts/add_covered_themes_column.py` (patrón de los ALTER
en `create_annual_plan_tables.py`). `create_all` no altera columnas, por eso un ALTER.

## Endpoints

### Marcar / desmarcar cobertura
`POST /annual-plan/months/{month_index}/coverage` body `{theme_key: str, covered: bool}`:
- Carga el mes del usuario (`_load_owned_month`); 404 si no existe.
- Valida `month_index <= compute_active_month_index(plan.start_date, today)`; si no → 400
  ("No puedes marcar cobertura de una sesión futura"). (Necesita el `plan.start_date`; se
  resuelve el plan del mes.)
- Actualiza `month.covered_themes`: agrega `theme_key` si `covered=true`, lo quita si `false`
  (idempotente; sin duplicados). `flag_modified(month, "covered_themes")` + flush.
- Devuelve `{month_index, covered_themes}` (o 204).

### Orden del día — exponer lo cubierto
Añadir `covered_keys: list[str]` a `OrdenDelDiaOut` (= `month.covered_themes or []`). El panel
usa esto para reflejar los checkboxes.

### Tablero de Cobertura
`GET /annual-plan/cobertura` → lista de `CoverageRow`:
```
{ key, label, type, frecuencia_anual, esperadas, realizadas, estado }
```
- Resuelve el plan activo del usuario (404 si no hay). Carga temas (`active`) y meses (con
  `covered_themes`).
- `sched = theme_sessions(themes)` (de B2). `active = compute_active_month_index(start_date, today)`.
- Por cada tema de tipo `permanente` o `cobertura` (se omiten `emergente`):
  - `frecuencia_anual` = nº total de sesiones programadas (len de su lista en `sched`).
  - `esperadas` = nº de esas sesiones con índice `<= active`.
  - `realizadas` = nº de meses cuyo `covered_themes` contiene `theme.key`.
  - `estado` = semáforo (ver abajo).
- Esquema `app/schemas/coverage.py`: `CoverageRow`.

## Semáforo

`deficit = esperadas - realizadas`:
```
def coverage_status(theme_type: str, deficit: int) -> str:
    if deficit <= 0:
        return "en_tiempo"
    if theme_type == "permanente":      # escala más rápido (cada sesión cuentan)
        return "atrasado" if deficit == 1 else "critico"
    if deficit == 1:
        return "riesgo"
    if deficit == 2:
        return "atrasado"
    return "critico"
```
Estados (4): `en_tiempo` · `riesgo` · `atrasado` · `critico`. (Umbrales ajustables.)

## Frontend

- **Marcado en la Orden del Día** (`OrdenDelDiaPanel.tsx`): cada tema programado
  (permanente/cobertura) lleva un checkbox "Cubierto", reflejando `covered_keys`. Al togglear
  llama a `markCoverage(monthIndex, themeKey, covered)` (optimista) → `POST .../coverage`.
  `lib/ordenDelDia.ts` agrega `covered_keys` al tipo + la función `markCoverage`.
- **Tablero de Cobertura** (`components/plan/CoberturaBoard.tsx`): tabla con Tema ·
  Frecuencia · Esperadas · Realizadas · semáforo (chip de color por estado). `lib/coverage.ts`
  (tipo `CoverageRow` + `getCobertura()`).
- **Pestaña "Cobertura"** en `/dashboard/plan`: extender el toggle existente
  (`boardView: "meses" | "tablero" | "cobertura"`) y renderizar `<CoberturaBoard />` cuando
  esté activa.

## Pruebas

Backend (pytest, db mockeada):
- `coverage_status`: unit de los 4 estados (permanente vs cobertura, varios déficits).
- `cobertura`: con un catálogo y meses con `covered_themes`, verifica esperadas/realizadas/
  estado correctos (incluye un permanente y un cobertura escalonado; respeta mes activo).
- `coverage` (mark): agrega/quita la key; 400 si `month_index > activo`; 404 si no es del
  usuario.
- Suite completa verde, sin regresiones.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B4

- Columna `covered_themes` creada (script corrido en prod cuando se autorice).
- El dueño marca temas como cubiertos desde la Orden del Día.
- `GET /annual-plan/cobertura` devuelve esperadas/realizadas/estado por tema.
- La pestaña "Cobertura" muestra la tabla con semáforo.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas (para sub-proyectos siguientes)

- La cobertura "estricta" (decisión + evidencia por tema, automática al cerrar sesión) queda
  para la ceremonia de cierre de sesión posterior; B4 usa el marcado manual.
- Emergentes no entran al tablero (no tienen calendario).
