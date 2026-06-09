# Chair IA sobre la Agenda (capa del nodo 4) — diseño

Fecha: 2026-06-09
Estado: aprobado para escribir plan de implementación

## Contexto

Capa de IA encima del Motor de Orden del Día determinista (nodo 4, ya en producción). El doc
§5.4 dice que la **curaduría del Chair** es "la diferencia entre un consejo que se siente real y
uno que se siente Excel": puede subir un tema de bajo score si es estratégico, bajar uno alto si
es ruido estacional, y redacta el racional en prosa. V1 del agenda engine se hizo determinista a
propósito; esta capa añade el Chair.

Decisiones de brainstorming (2026-06-09):
1. **Módulo:** Chair IA sobre la agenda.
2. **Disparo:** botón "Convocar al Chair" (on-demand) + **se persiste** en el mes activo (una
   vez por mes, controla costo). Best-effort: si no hay API key o falla, se queda la determinista.

Patrón existente a seguir: `run_month_review` (`app/services/ai/month_review.py`) — función
**sync**, `if not settings.ANTHROPIC_API_KEY: return <fallback determinista>`, arma prompt con
`_build_company_context(memory_buffer)` (de `app/services/ai/agents/base.py`), llama
`_create_with_retry(client, model=settings.AI_MODEL, max_tokens=..., system=..., messages=[...])`,
y parsea el texto a JSON con fallback. Se invoca desde async vía `anyio.to_thread.run_sync`.

## Alcance

Añadir la curaduría del Chair a la agenda del mes activo, con persistencia y un botón.

**Fuera de alcance:** regenerar automáticamente (solo on-demand); detectar staleness (la agenda
curada es un snapshot read-only, como la minuta del doc; el botón permite re-convocar); el Chair
en otros artefactos (eso es nodo 5).

## Backend

### Servicio `app/services/ai/agenda_chair.py`
```
def chair_curate_agenda(deterministic_agenda: list[dict], memory_buffer: dict, period_label: str) -> dict
```
- Si `not settings.ANTHROPIC_API_KEY` o la agenda viene vacía → `{"carta": "", "items": deterministic_agenda}`.
- Construye el prompt: `_build_company_context(memory_buffer)` + `period_label` + la lista de items
  con un `id` (índice 0-based) y sus campos (titulo, detector, evidencia, score, orden).
- **System prompt (Chair):** preside un consejo; recibe una agenda candidata ya puntuada; su
  trabajo: (1) decidir el ORDEN real de importancia del mes (puede promover/degradar), (2)
  reescribir el `racional` de cada tema en prosa breve y natural (1-2 frases, citando la
  evidencia), (3) escribir una `carta` de apertura de ≤120 palabras. **NO inventa temas ni
  evidencia** — trabaja solo con los temas dados. Responde SOLO JSON.
- **Salida esperada del LLM:** `{"carta": str, "prioridad": [ids en orden], "racionales": {"<id>": str}}`.
- **Reconstrucción robusta (anti-alucinación):**
  - `valid = {0..len-1}`; `orden_final` = ids de `prioridad` que estén en `valid`, sin duplicar,
    + los ids faltantes anexados al final.
  - Para cada id en `orden_final`: toma el item ORIGINAL, asigna `orden = posición+1`, reemplaza
    `racional` por `racionales[str(id)]` si existe (si no, conserva el original). Todo lo demás
    (titulo/area/detector/impacto/urgencia/evidencia/score) intacto.
  - Devuelve `{"carta": <carta parseada o "">, "items": <lista reconstruida>}`.
- Cualquier excepción/parseo inválido → `{"carta": "", "items": deterministic_agenda}` (fallback).

### Persistencia
- Columna `chair_agenda: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` en
  `MonthlyPlan` (`app/models/annual_plan.py`), después de `covered_themes`.
- Script `backend/scripts/add_chair_agenda_column.py` (ALTER TABLE monthly_plans ADD COLUMN IF NOT
  EXISTS chair_agenda JSONB), patrón idéntico a `add_covered_themes_column.py`.
- Se guarda `{"carta": str, "items": [...], "generated_at": "<iso>"}`.

### Endpoints (`annual_plan/router.py`)
- **`GET /annual-plan/agenda`** pasa a `response_model=AgendaOut`:
  - Resuelve plan, calcula `active`, arma la determinista (como hoy).
  - Si el mes activo (`month.month_index == active`) tiene `chair_agenda` → devuelve
    `AgendaOut(curada=True, carta=chair_agenda["carta"], items=chair_agenda["items"])`.
  - Si no → `AgendaOut(curada=False, carta="", items=<determinista>)`.
- **`POST /annual-plan/agenda/chair`** (`response_model=AgendaOut`):
  - Resuelve plan; arma la determinista.
  - Carga `memory_buffer` del onboarding (best-effort, como en el PDF de B5) y `period_label`
    (`_MONTH_NAMES[period_month] + año` del mes activo).
  - `result = await anyio.to_thread.run_sync(chair_curate_agenda, agenda, memory_buffer, period_label)`.
  - Guarda en el mes activo: `month.chair_agenda = {"carta": result["carta"], "items": result["items"], "generated_at": date.today().isoformat()}` + `flag_modified`.
  - Devuelve `AgendaOut(curada=True, carta=result["carta"], items=result["items"])`.

### Esquema `app/schemas/agenda.py`
Agregar:
```python
class AgendaOut(BaseModel):
    curada: bool
    carta: str
    items: list[AgendaItem]
```

## Frontend

- `lib/agenda.ts`: `getAgenda()` devuelve `AgendaOut {curada, carta, items}`; nueva
  `convocarChair(): Promise<AgendaOut>` (POST `/annual-plan/agenda/chair`).
- `AgendaPanel.tsx`:
  - Estado `data: AgendaOut | null` + `convocando: boolean`.
  - Si `data.curada` → muestra la **carta** arriba (bloque destacado) + los items + botón
    **"Actualizar con el Chair"**.
  - Si no → items + botón **"Convocar al Chair"**.
  - El botón llama `convocarChair()` con loading ("El Chair está revisando la agenda…"), y
    reemplaza `data` con el resultado. Errores → noop (se queda lo que había).

## Pruebas

Backend (pytest):
- `chair_curate_agenda`: sin API key → fallback (carta="", items == determinista); la
  reconstrucción con una respuesta de LLM mockeada (monkeypatch del cliente/`_create_with_retry`)
  → verifica reorden por `prioridad`, racional reemplazado, ids faltantes anexados, y que titulo/
  evidencia originales se conservan (anti-alucinación); respuesta inválida → fallback.
- Endpoints: `GET` devuelve `curada=false` sin `chair_agenda` y `curada=true` con ella;
  `POST` (monkeypatch `chair_curate_agenda` para no llamar al LLM real) guarda y devuelve
  `curada=true`. db mockeada con el patrón existente.
- Migración: el script corre sin error (idempotente).
- Suite completa verde.

Frontend: `tsc --noEmit` + `npm run build` verdes; lint limpio en archivos nuevos.

## Criterio de "hecho"

- Botón "Convocar al Chair" en la Agenda; corre la IA, guarda en el mes activo, muestra carta +
  agenda curada (reordenada + racional en prosa).
- Sin API key o con fallo → se mantiene la determinista (no rompe).
- Suite backend verde; build frontend verde; columna `chair_agenda` migrada a prod.

## Riesgos / decisiones abiertas

- Migración aditiva (correr `add_chair_agenda_column.py` en prod antes del deploy).
- La agenda curada es un snapshot (puede quedar desfasada si cambian KPIs/acuerdos); el botón
  permite re-convocar. Aceptable (artefacto read-only del mes, como la minuta).
- Costo: una llamada a Claude por convocatoria (on-demand, no por carga).
