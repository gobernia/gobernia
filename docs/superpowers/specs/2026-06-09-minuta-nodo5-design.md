# Nodo 5 — Minuta (V1 single-pass) — diseño

Fecha: 2026-06-09
Estado: aprobado para escribir plan de implementación

## Contexto

Implementa el **nodo 5** del doc "Pipeline Consejo + PM": la sesión del consejo produce una
**Minuta** con **3-5 decisiones binarias (A/B/Aplazar)** que el dueño cierra, y cada decisión
cerrada genera un **compromiso**. Es el corazón del ritual mensual.

Decisiones de brainstorming (2026-06-09):
1. **Deliberación:** single-pass — UNA llamada al Chair sobre la agenda del mes produce la Minuta.
   La deliberación multi-agente (4 etapas) queda fuera de V1.
2. **Compromisos:** se guardan DENTRO de la Minuta (no como `ActionTask`), para evitar acoplar al
   `objective_id` de ActionTask y mantener la Minuta autocontenida y read-only. El Nodo 6 (PM) los
   consumirá después.

Reusa: la **agenda** (curada del Chair si existe, si no la determinista), el patrón LLM de
`agenda_chair.chair_curate_agenda` (best-effort + fallback + reconstrucción anti-alucinación), el
patrón de columna JSONB en `MonthlyPlan` (`review`/`covered_themes`/`chair_agenda`), y el helper
`_agenda_estado` (devuelve `(agenda, months, active, active_month)`).

## Alcance V1

Generar la Minuta del mes activo (on-demand + persistida), cerrar decisiones, y verla.

**Fuera de V1:** deliberación multi-agente (briefs/debate), lecturas por agente, desacuerdos
explícitos, la regla "aplazar 3x fuerza decidir", el flujo de compromisos a `ActionTask`/PM
(nodo 6), y que la carta referencie la minuta del mes anterior.

## Backend

### Servicio `app/services/ai/minuta.py`
```
def generate_minuta(agenda_items: list[dict], memory_buffer: dict, period_label: str) -> dict
```
- Toma **hasta los 5 primeros** items de la agenda (3-5 decisiones).
- Si `not settings.ANTHROPIC_API_KEY` o agenda vacía → **fallback determinista** (ver abajo).
- Prompt (molde de `chair_curate_agenda`): `_build_company_context` + `period_label` + los items
  con `id` (índice), titulo, evidencia, racional.
- **System prompt (Chair sesionando):** preside la sesión mensual; por cada tema escribe (1) una
  `sintesis` breve de la deliberación (1-2 frases), (2) una `decision` binaria: una `pregunta`
  clara y dos opciones concretas y accionables `opcion_a` / `opcion_b`. Además una `carta` de
  apertura de ≤120 palabras. NO inventa temas; trabaja solo con los dados. Responde SOLO JSON.
- **Salida esperada del LLM:** `{"carta": str, "temas": {"<id>": {"sintesis": str, "pregunta": str, "opcion_a": str, "opcion_b": str}}}`.
- **Reconstrucción anti-alucinación** (`_rebuild_minuta`): por cada item de la agenda (índice `i`,
  hasta 5), construye un tema:
  ```
  {"id": i, "titulo": item["titulo"],
   "sintesis": <llm.sintesis o item["racional"]>,
   "decision": {"pregunta": <llm.pregunta o "¿Cómo proceder con: {titulo}?">,
                "opcion_a": <llm.opcion_a o "Tomar acción este mes.">,
                "opcion_b": <llm.opcion_b o "Aplazar y monitorear.">,
                "decision_tomada": None},
   "compromiso": None}
  ```
  Devuelve `{"carta": <carta o "">, "temas": [...]}`.
- **Fallback determinista** (sin API key / agenda vacía / cualquier excepción): mismo
  `_rebuild_minuta` pero con `carta=""` y los valores por defecto (sintesis=racional, pregunta/
  opciones genéricas). Para agenda vacía → `{"carta": "", "temas": []}`.

### Persistencia
- Columna `minuta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` en `MonthlyPlan`
  (tras `chair_agenda`). Guarda `{"carta": str, "temas": [...], "generated_at": "<iso>"}`.
- Script `backend/scripts/add_minuta_column.py` (ALTER ADD COLUMN IF NOT EXISTS, patrón existente).

### Esquemas `app/schemas/minuta.py`
```python
class MinutaDecision(BaseModel):
    pregunta: str
    opcion_a: str
    opcion_b: str
    decision_tomada: str | None = None   # "A" | "B" | "aplazar" | None

class MinutaCompromiso(BaseModel):
    descripcion: str
    fecha: str

class MinutaTema(BaseModel):
    id: int
    titulo: str
    sintesis: str
    decision: MinutaDecision
    compromiso: MinutaCompromiso | None = None

class MinutaOut(BaseModel):
    generada: bool
    carta: str
    temas: list[MinutaTema]

class DecisionIn(BaseModel):
    tema_id: int
    decision: str   # "A" | "B" | "aplazar"
```

### Endpoints (`annual_plan/router.py`)
- **`POST /annual-plan/minuta`** (`response_model=MinutaOut`): resuelve plan; `_agenda_estado`;
  `items = active_month.chair_agenda["items"] if (active_month and active_month.chair_agenda) else agenda`;
  `memory_buffer` (onboarding, best-effort) + `period_label`;
  `result = await anyio.to_thread.run_sync(generate_minuta, items, memory_buffer, period_label)`;
  guarda en `active_month.minuta = {**result, "generated_at": date.today().isoformat()}` +
  `_flag_modified`; devuelve `MinutaOut(generada=True, carta=result["carta"], temas=result["temas"])`.
- **`GET /annual-plan/minuta`** (`response_model=MinutaOut`): resuelve plan; `active_month` (helper
  ligero `_active_month`); si tiene `minuta` → `MinutaOut(generada=True, carta, temas)`; si no →
  `MinutaOut(generada=False, carta="", temas=[])`.
- **`POST /annual-plan/minuta/decision`** (`response_model=MinutaOut`, body `DecisionIn`): resuelve
  plan; `active_month`; 404 si no hay `minuta`; busca el tema por `tema_id`; valida `decision ∈
  {"A","B","aplazar"}` (422 si no); set `tema["decision"]["decision_tomada"] = decision`; si "A" →
  `tema["compromiso"] = {"descripcion": opcion_a, "fecha": (today+14d).isoformat()}`; si "B" →
  opcion_b; si "aplazar" → `compromiso = None`; `_flag_modified`; devuelve la `MinutaOut` actualizada.

### Helper ligero
```python
async def _active_month(plan, db) -> MonthlyPlan | None:
    res = await db.execute(select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
    months = list(res.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today())
    return next((m for m in months if m.month_index == active), None)
```

## Frontend

- `lib/minuta.ts`: tipos (`MinutaOut`, `MinutaTema`, …) + `getMinuta()`, `sesionarConsejo()`
  (POST `/minuta`), `cerrarDecision(temaId, decision)` (POST `/minuta/decision`).
- `components/plan/MinutaView.tsx`: si `!generada` → estado vacío + botón **"Sesionar el Consejo"**
  (loading "El consejo está sesionando…"); si `generada` → la **carta** + cada tema con su
  `sintesis`, la `pregunta`, y botones **A / B / Aplazar** (mostrando el texto de cada opción);
  un tema con `decision_tomada` muestra la decisión elegida + el `compromiso` (descripcion + fecha)
  y deshabilita los botones.
- `app/dashboard/plan/page.tsx`: agregar **"minuta"** al toggle (Meses / Tablero de acuerdos /
  Cobertura / **Minuta**) y renderizar `<MinutaView />` en esa rama.

## Pruebas

Backend (pytest):
- `generate_minuta`: fallback sin API key (temas anclados a la agenda, carta="", decisión
  genérica); `_rebuild_minuta` con respuesta LLM mockeada (sintesis/decisión por id, titulo
  original preservado, cap a 5); agenda vacía → `{"carta":"","temas":[]}`.
- Endpoints: `POST /minuta` genera+guarda (monkeypatch `generate_minuta`); `GET /minuta` devuelve
  guardada o `generada=false`; `POST /minuta/decision` A → set decision_tomada + compromiso con
  opcion_a; "aplazar" → sin compromiso; decisión inválida → 422; sin minuta → 404. db mockeada.
- Migración: el script corre idempotente.
- Suite completa verde.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho"

- Botón "Sesionar el Consejo" genera una Minuta (carta + 3-5 temas con decisión), persistida.
- El dueño cierra A/B/Aplazar; A/B generan un compromiso visible en el tema.
- Sin API key / fallo → minuta determinista (no rompe).
- Suite backend verde; build frontend verde; columna `minuta` migrada a prod.

## Riesgos / decisiones abiertas

- Migración aditiva (correr `add_minuta_column.py` en prod antes del deploy).
- Compromisos viven en la Minuta (no en `ActionTask`); el Nodo 6 PM decidirá si migran a un modelo
  propio.
- La Minuta es un snapshot del momento de generación; re-generar la sobrescribe (incluyendo
  decisiones ya cerradas). Aceptable en V1 (el dueño genera una vez por mes); el botón "Sesionar"
  cuando ya hay minuta puede mostrar confirmación en el front (fuera de alcance backend).
