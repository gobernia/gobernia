# Motor de Orden del Día por Señales (nodo 4) — V1 determinista (diseño)

Fecha: 2026-06-09
Estado: aprobado para escribir plan de implementación

## Contexto

Implementa el **nodo 4** del doc "Especificación Pipeline Consejo + PM v1.0": el Motor de Orden
del Día que detecta señales, las puntúa y arma una **Agenda priorizada** de 5-7 temas con racional
y evidencia. Es "la pieza más sensible del producto".

Decisiones de brainstorming (2026-06-09):
1. **Módulo:** nodo 4 (Motor de Orden del Día por señales).
2. **Cobertura ↔ señales:** FUSIONAR — un solo artefacto donde los temas de cobertura
   programados del mes y las señales detectadas entran como candidatos, se puntúan juntos y
   salen los 5-7 más importantes.
3. **Chair IA:** NO en V1 — núcleo determinista primero (scorer + plantillas). El Chair (LLM) es
   la capa siguiente.
4. **Ubicación:** panel "Agenda del mes" arriba de `/dashboard/plan`, como vista principal; las
   Alertas (B6) quedan debajo; el toggle Meses/Tablero/Cobertura queda como detalle de apoyo.

Construye **sobre lo existente**: los detectores con datos hoy son los que ya calculan B6
(Alertas) y B4 (Cobertura). El Motor añade la capa de **scoring + ranking + artefacto Agenda**.

## Alcance V1

Calculado **en vivo** (sin persistencia ni migración), igual que Alertas/Cobertura. Apunta al
**mes activo** (`compute_active_month_index`).

**Fuera de V1:** Chair IA (curaduría + prosa); detectores sin datos hoy (EventoExternoPróximo,
DecisiónVencida, SeñalBlanda, IniciativaEstancada con "días sin update"); flag "diferido" que
arrastra temas de bajo score al siguiente mes (requiere persistencia); aprendizaje de pesos por
cliente (§8.3).

## EstadoMes — fuentes de datos (todas ya existen)

- **Temas programados del mes activo:** `scheduled_for_session(themes, active_index)` (B2) →
  permanentes + cobertura de esa sesión.
- **Estado de cobertura por tema:** `coverage_rows(themes, months, active_index)` (B4) → `estado`
  ∈ `en_tiempo|riesgo|atrasado|critico` por tema (key).
- **KPIs:** `review["signals"]["kpis"]` del **último mes `done`** (lista de
  `{label, value, target, unit, on_track}`).
- **Acuerdos:** tareas del plan (`ActionTask` con `.status`, `.due_date`, `.title`).

## Servicio puro `app/services/governance/agenda_engine.py`

```
def build_agenda(scheduled_themes, coverage_rows, kpi_signals, tasks, today, max_items=7) -> list[dict]
```

### Detectores → candidatos

1. **DesviaciónKPI** (por cada KPI con `on_track is False`): un candidato.
   - `score_base = 30`.
   - evidencia: `"{label}: {value}{unit} (meta {target}{unit})"` (omite unidad/meta si son None).
   - `area="kpi"`, `urgencia="media"`, racional: `"Entra porque {label} está fuera de objetivo."`
2. **CompromisoVencido** (acuerdos con `status != "completada"` y `due_date < today`): **un solo
   candidato agregado** si N>0.
   - `score = 20 + 10 * min(N-1, 2)` → N=1→20, N=2→30, N≥3→40.
   - evidencia: hasta 3 títulos de acuerdos vencidos con su fecha.
   - `area="acuerdo"`, `urgencia="alta"`, racional: `"Entra porque hay {N} acuerdo(s) vencido(s) sin validar."`
3. **CompromisoPorVencer** (acuerdos no completados con `today <= due_date <= today+7`): **un
   candidato agregado** si N>0.
   - `score = 10 + 5 * min(N-1, 2)` → 10/15/20.
   - `area="acuerdo"`, `urgencia="media"`, racional: `"Entra porque {N} acuerdo(s) vence(n) en los próximos 7 días."`
4. **TemaDeCobertura** (por cada tema en `scheduled_themes`): un candidato.
   - `score_base = 10`; boost por estado (de `coverage_rows`): `atrasado → +10` (20),
     `critico → +20` (30); `en_tiempo`/`riesgo` → sin boost (10).
   - evidencia: si atrasado/crítico → `"{label}: {realizadas} de {esperadas} revisiones — {Estado}"`;
     si no → `"Programado para esta sesión."`
   - `area="cobertura"`, `urgencia` = `alta` si crítico, `media` si atrasado, `baja` si no;
     racional: `"Entra porque toca cubrir {label} este mes"` (+ `" y va atrasado ({realizadas}/{esperadas})."` si atrasado/crítico, si no `"."`).

### Scoring, orden y filtros (§5.2–5.3)

- Reúne todos los candidatos; **ordena por `score` desc** (estable).
- **Filtro máx. 7 temas** (`max_items`); el resto se descarta en V1 (sin "diferido").
- Asigna `orden = 1..N`.
- `impacto`: `alto` si `score >= 25`, `medio` si `>= 15`, `bajo` si menos.
- Cada item lleva `racional` (plantilla) y `evidencia` (lista de strings textual).

### Forma del item (dict)

```
{
  "orden": int, "titulo": str, "area": str, "detector": str,
  "impacto": str, "urgencia": str, "racional": str,
  "evidencia": list[str], "score": float
}
```

## Esquema y endpoint

`app/schemas/agenda.py`:
```python
class AgendaItem(BaseModel):
    orden: int
    titulo: str
    area: str
    detector: str
    impacto: str
    urgencia: str
    racional: str
    evidencia: list[str]
    score: float
```

`GET /annual-plan/agenda` (en `annual_plan/router.py`):
- Resuelve el plan (`_current_plan`); 404 si no hay.
- Carga meses (`selectinload(objectives)`) → tareas (`_tasks_by_objective`) → temas.
- `active = compute_active_month_index(plan.start_date, date.today())`.
- `scheduled = scheduled_for_session(themes, active)`.
- `rows = coverage_rows(themes, months, active)`.
- `kpi_signals` = del último mes `done` con `review` (igual que en `/alertas`).
- `agenda = build_agenda(scheduled, rows, kpi_signals, tasks, date.today())`.
- Devuelve `[AgendaItem(**a) for a in agenda]`.

## Frontend

- `lib/agenda.ts`: tipo `AgendaItem` + `getAgenda()`.
- `components/plan/AgendaPanel.tsx`: lista priorizada; cada tema muestra `orden`, `titulo`, chips
  de `impacto`/`urgencia` (color sobrio), `racional`, y la `evidencia`. Si no hay temas →
  "Sin temas priorizados este mes". Fetch en mount.
- Montado **al inicio de la vista activa** de `/dashboard/plan`, ARRIBA del `AlertsPanel` (la
  Agenda es lo primero; las Alertas quedan debajo; luego el toggle).

## Pruebas

Backend (pytest):
- `build_agenda` unit: cada detector dispara (KPI off-track, acuerdo vencido, por vencer, tema de
  cobertura), el scoring ordena correctamente, el boost de cobertura atrasado/crítico, el cap de
  máx. 7, la evidencia presente, y el caso vacío (lista vacía).
- Endpoint `/agenda`: 200 con la lista priorizada (db mockeada con el patrón existente).
- Suite completa verde, sin regresiones.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho"

- `GET /annual-plan/agenda` devuelve 5-7 temas priorizados con racional + evidencia, fusionando
  cobertura y señales.
- El panel "Agenda del mes" aparece arriba del plan como vista principal.
- Suite backend verde; build frontend verde.

## Riesgos / decisiones abiertas

- Sin migración (cálculo en vivo).
- Pesos V1 adaptados a las señales disponibles (no son los exactos del §5.2 porque faltan
  fuentes); se reajustarán cuando entren más detectores y el aprendizaje por cliente.
- Solapamiento intencional con Alertas (B6): la Agenda "absorbe" las mismas señales pero
  priorizadas; ambas conviven en V1 (Agenda = qué priorizar; Alertas = lista factual).
