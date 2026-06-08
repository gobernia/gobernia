# Bloque B1 — Modelo de Gobierno + Temas del Consejo (diseño)

Fecha: 2026-06-08
Estado: aprobado para escribir plan de implementación

## Contexto

El "Motor de Cobertura del Consejo" (Bloque B) reformula el plan de 12 meses: Gobernia
deja de administrar agendas y pasa a garantizar la **cobertura anual de las
responsabilidades del Consejo**. Es un sistema grande que se descompone en 6
sub-proyectos:

- **B1 — Modelo de Gobierno + Temas (este spec)**
- B2 — El Secretario (motor): arma calendario de cobertura, orden del día, reprograma.
- B3 — Acuerdos + Evidencias (tablero tipo Monday, cierre con evidencia).
- B4 — Tablero de Cobertura (esperadas vs realizadas + semáforo).
- B5 — Orden del día (vista + PDF).
- B6 — Alertas sobrias.

Decisión keystone (acordada): **construir sobre lo que hay**. Los meses del plan
(`MonthlyPlan`) se vuelven Sesiones del Consejo; objetivos y KPIs por mes se mantienen;
las "tareas" pasarán a Acuerdos (B3). Cadencia **mensual fija = 12 sesiones**.
Temas: **catálogo por defecto editable**.

## Alcance de B1

B1 es **solo la fundación de datos**: la entidad *Tema del Consejo* (`BoardTheme`), su
catálogo por defecto sembrado por plan, y su gestión (CRUD). Es deterministra (sin IA).

**Fuera de alcance de B1** (van en B2–B6): orden del día, acuerdos, evidencias, el
Secretario, el cálculo/semáforo de cobertura, la inyección de temas emergentes, el PDF y
las alertas. B1 documenta la **fórmula** de cobertura pero NO la implementa (eso es B4).

## Modelo de datos

### Entidad nueva: `BoardTheme` (tabla `board_themes`)

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | UUID (PK) | UUIDMixin |
| `annual_plan_id` | UUID FK → `annual_plans.id` | `ondelete=CASCADE`, index |
| `key` | String(60) | slug estable, ej. `resultados_financieros` |
| `label` | Text | nombre visible |
| `type` | String(20) | `permanente` · `cobertura` · `emergente` |
| `every_n_sessions` | Integer, nullable | frecuencia en sesiones; `null` solo para `emergente` |
| `active` | Boolean, default `true` | activar/desactivar sin borrar |
| `is_default` | Boolean, default `false` | `true` si vino del catálogo sembrado |
| `order_index` | Integer, default `0` | orden de despliegue |
| `created_at` / `updated_at` | timestamp | TimestampMixin |

- Restricción única `(annual_plan_id, key)` para evitar temas duplicados por plan.
- Relación: `AnnualPlan.themes: list["BoardTheme"]` con `cascade="all, delete-orphan"`,
  `order_by=BoardTheme.order_index`.
- Frecuencia (`every_n_sessions`): `1`=cada sesión, `2`=bimestral, `3`=trimestral,
  `6`=semestral, `12`=anual. Validación: entero en `{1,2,3,6,12}` para `permanente`/`cobertura`
  (los permanentes siempre `1`); `null` para `emergente`.

### Catálogo por defecto

Constante en `backend/app/services/governance/default_themes.py`. Se siembra al **crear**
un `AnnualPlan`. `is_default=true` para todos los sembrados.

**Permanentes** (`type=permanente`, `every_n_sessions=1`):

| key | label |
|-----|-------|
| `seguimiento_acuerdos` | Seguimiento de acuerdos |
| `resultados_financieros` | Resultados financieros |
| `resultados_operativos` | Resultados operativos |
| `kpis_estrategicos` | KPIs estratégicos |
| `riesgos_criticos` | Riesgos críticos |

**Cobertura** (`type=cobertura`):

| key | label | every_n_sessions |
|-----|-------|------------------|
| `talento_sucesion` | Talento y sucesión | 2 |
| `tecnologia_ciberseguridad` | Tecnología y ciberseguridad | 2 |
| `auditoria` | Auditoría | 3 |
| `cumplimiento_normativo` | Cumplimiento normativo | 3 |
| `esg` | ESG / Sostenibilidad | 3 |
| `planeacion_estrategica` | Planeación estratégica | 6 |
| `evaluacion_dg` | Evaluación del Director General | 12 |
| `evaluacion_consejo` | Evaluación del Consejo | 12 |

`order_index` se asigna por el orden de esta lista (permanentes 0–4, cobertura 5–12).
Los **emergentes** NO se siembran (los creará el Secretario en B2).

## Siembra (seed)

- Función `seed_default_themes(db, annual_plan_id)` en
  `app/services/governance/theme_seeder.py`: inserta el catálogo si el plan aún no tiene
  temas (idempotente — no duplica si ya existen).
- Se llama de forma **síncrona** al crear el `AnnualPlan`, en ambos puntos donde hoy se
  crea: el hook de etapa-8 (`app/api/v1/onboarding/etapa8.py`) y, por robustez, el
  endpoint `generate` (`app/api/v1/annual_plan/router.py`). Así los temas existen aunque el
  worker de generación no haya corrido (mismo patrón best-effort que el hardening actual).
- Script de backfill `backend/scripts/seed_board_themes.py [annual_plan_id|--all]` para
  poblar planes ya existentes (incluido el plan sembrado de `c.beuvrin@ketingmedia.com`).

## API

Nuevos endpoints REST bajo el router de annual-plan, sobre el **plan activo del usuario**
(se resuelve el `AnnualPlan` del `user_id` igual que los endpoints existentes):

| Método | Ruta | Acción |
|--------|------|--------|
| `GET` | `/annual-plan/themes` | Lista los temas del plan (orden por `type` luego `order_index`). |
| `POST` | `/annual-plan/themes` | Crea un tema propio (`is_default=false`). |
| `PATCH` | `/annual-plan/themes/{theme_id}` | Edita `label`, `every_n_sessions`, `active`, `order_index`. |
| `DELETE` | `/annual-plan/themes/{theme_id}` | Borra el tema. La API permite borrar cualquier tema del plan del usuario; la UI solo ofrece "borrar" para temas propios (`is_default=false`) y "desactivar" para los del catálogo. |

- Esquemas Pydantic en `app/schemas/board_theme.py`: `BoardThemeOut`, `BoardThemeCreate`
  (`label`, `type`, `every_n_sessions`), `BoardThemeUpdate` (todos opcionales).
- Validación: `type` ∈ enum; `every_n_sessions` ∈ `{1,2,3,6,12}` o `null` para emergentes;
  `permanente` fuerza `every_n_sessions=1`. Errores devuelven 422/409 con detalle claro.
- Autorización: el tema debe pertenecer a un `AnnualPlan` cuyo `user_id` == usuario actual,
  si no → 404 (mismo patrón que `_load_owned_month`).

## Fórmula de cobertura (documentada aquí, implementada en B4)

Por tema, a una fecha dada con `S` = nº de sesiones (meses) transcurridas del plan:

- `esperadas_a_la_fecha = floor(S / every_n_sessions)` para cobertura; `= S` para
  permanentes (`every_n_sessions=1`). Emergentes no cuentan para cobertura programada.
- `realizadas` = nº de sesiones donde el tema quedó **cubierto** (decisión + evidencia).
  Esto depende de Acuerdos/Orden del día (B3/B5); en B1 es `0`.
- El semáforo (En tiempo / Riesgo / Atrasado / Crítico) se define en B4 comparando
  `realizadas` vs `esperadas_a_la_fecha`.

## Frontend (B1)

Sección **"Temas del Consejo"** para gestionar el catálogo, dentro de la página del plan
(`/dashboard/plan`) como una sección/pestaña propia (los temas pertenecen al plan).
Funcionalidad mínima:

- Lista agrupada por tipo (Permanentes / Cobertura / Emergentes), con `label` y, para
  cobertura, la frecuencia en lenguaje natural ("cada sesión", "bimestral", "trimestral",
  "semestral", "anual").
- Acciones: cambiar frecuencia (selector), activar/desactivar (toggle), agregar tema propio,
  borrar tema propio.
- Estilo y componentes existentes (marca `--gob-*`, `InfoHint` para explicar "frecuencia de
  revisión"). Lib `frontend/src/lib/boardThemes.ts` con tipos + funciones de API.

## Migración / despliegue

- Alembic `004_board_themes.py` (crea `board_themes` + índice + única).
- Script `backend/scripts/create_board_themes.py` (create_all + fallback ALTER) siguiendo el
  patrón de `create_annual_plan_tables.py`, ya que prod aplica el esquema con create_all.
- Registrar el modelo en `app/models/__init__.py`.

## Pruebas

Backend (pytest, asyncio):
- `seed_default_themes` inserta el catálogo exacto (conteos por tipo, frecuencias correctas)
  y es **idempotente** (segunda llamada no duplica).
- CRUD: crear/editar/borrar con autorización (404 si no es del usuario), validación de
  `type`/`every_n_sessions` (422), `permanente` fuerza `1`.
- Crear un `AnnualPlan` siembra los 13 temas por defecto.

Frontend: `npm run build` y `tsc --noEmit` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho" para B1

- Migración aplicada; `board_themes` existe en prod (Supabase).
- Todo plan nuevo nace con los 13 temas por defecto; backfill corrido para planes existentes.
- El dueño puede ver y editar el catálogo de temas de su plan desde el dashboard.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas (para sub-proyectos siguientes)

- Reconciliación `MonthlyPlan` (sesión) ↔ `BoardSession` (análisis de consejeros): se
  resuelve en **B2** al construir "celebrar sesión".
- B1 aislado es configuración sin pantalla "wow"; el valor se ve apilado con B2/B3.
