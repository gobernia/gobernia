# Todd FODA — Plan A: ronda externa (PESTEL) + priorización de metas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tras el diagnóstico, Todd corre una **segunda ronda** (factores externos PESTEL, wizard adaptativo informado por el diagnóstico) y luego presenta una **lista de metas personalizada** que el usuario **ordena por prioridad**; factores externos y ranking quedan persistidos para el FODA (Plan B).

**Architecture:** Reutiliza el motor de Todd (tool use, wizard) con un **banco PESTEL** y el diagnóstico inyectado como contexto. La ronda externa vive en una segunda fila de `todd_sessions` con `phase="externo"`. Las metas las genera Todd (Sonnet) a la medida; el ranking y los factores externos se guardan en `DiagnosticoEstrategico.content`. El FODA y su vista son el Plan B.

**Tech Stack:** FastAPI, SQLAlchemy async, anthropic (Sonnet 4.6, tool use). Next.js 16 App Router, framer-motion. Esquema: columna `phase` en `todd_sessions` vía script `alter_*` (NO Alembic).

## Global Constraints

- **"PESTEL" es término INTERNO** — Todd nunca lo dice al usuario; pregunta por factores del entorno por categoría, sin tecnicismos.
- **Reutiliza el wizard y el motor de Todd** — cambios aditivos; no se rompe la ronda interna ni el diagnóstico.
- **Persistencia:** `todd_sessions` gana columna `phase` (default `"interno"`) vía `scripts/alter_todd_phase.py` (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Factores externos + ranking de metas → `DiagnosticoEstrategico.content` (JSONB, sin migración).
- **Categorías externas:** `PESTEL_CATS = ["politicos","economicos","sociales","tecnologicos","ambiental","legal"]`.
- **SQLAlchemy:** pasar JSONB explícitos al construir (`messages=[]`, `state={}`).
- **Frontend Next.js 16:** client component con `fetch` vía `@/lib/api`.

---

### Task 1: Banco PESTEL + metas base + prompt externo + cobertura genérica

**Files:**
- Create: `backend/app/services/ai/todd/externo.py`
- Modify: `backend/app/services/ai/todd/agent.py` (helper de cobertura genérico)
- Test: `backend/tests/unit/test_todd_externo.py` (crear)

**Interfaces:**
- Produces:
  - `externo.PESTEL_CATS: list[str]`, `externo.PESTEL_BANK: dict[str,list[str]]`, `externo.METAS_BASE: list[str]`
  - `externo.build_externo_prompt(state: dict|None, diagnostico_ctx: str) -> str`
  - `agent.enforce_coverage_against(turn: dict, required: list[str]) -> dict` (y `enforce_coverage` pasa a delegarle con `areas.AREAS`)

- [ ] **Step 1: Tests**

`backend/tests/unit/test_todd_externo.py`:
```python
from app.services.ai.todd import externo
from app.services.ai.todd.agent import enforce_coverage_against


def test_pestel_son_seis_categorias():
    assert externo.PESTEL_CATS == ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]
    assert all(externo.PESTEL_BANK.get(c) for c in externo.PESTEL_CATS)


def test_metas_base_tiene_siete():
    assert len(externo.METAS_BASE) == 7


def test_build_externo_prompt_incluye_pestel_y_diagnostico():
    p = externo.build_externo_prompt({"areas_cubiertas": []}, "DIAGNÓSTICO: márgenes apretados; competidor Wizeline.")
    assert "tecnológic" in p.lower() or "tecnologic" in p.lower()
    assert "Wizeline" in p                      # contexto del diagnóstico inyectado
    assert "oportunidad" in p.lower() and "amenaza" in p.lower()
    assert "PESTEL" not in p                     # término interno, no aparece de cara al modelo-usuario


def test_enforce_coverage_against_bloquea_done_incompleto():
    turn = {"done": True, "state": {"areas_cubiertas": ["politicos"]}}
    out = enforce_coverage_against(turn, externo.PESTEL_CATS)
    assert out["done"] is False


def test_enforce_coverage_against_permite_done_completo():
    turn = {"done": True, "state": {"areas_cubiertas": externo.PESTEL_CATS}}
    assert enforce_coverage_against(turn, externo.PESTEL_CATS)["done"] is True
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_externo.py -q`

- [ ] **Step 3: Cobertura genérica en `agent.py`**

En `backend/app/services/ai/todd/agent.py`, reemplazar `enforce_coverage` por una versión genérica + el wrapper:
```python
def enforce_coverage_against(turn: dict, required: list[str]) -> dict:
    """No permite cerrar (done) sin cubrir todas las áreas/categorías de `required`."""
    if turn.get("done"):
        cubiertas = set((turn.get("state") or {}).get("areas_cubiertas") or [])
        if not set(required).issubset(cubiertas):
            turn["done"] = False
    return turn


def enforce_coverage(turn: dict) -> dict:
    """No permite cerrar sin las 7 áreas internas."""
    return enforce_coverage_against(turn, areas.AREAS)
```
(Esto conserva el comportamiento de `enforce_coverage` actual — los tests internos siguen verdes.)

- [ ] **Step 4: Crear `externo.py`**

`backend/app/services/ai/todd/externo.py`:
```python
"""Fase externa de Todd: banco PESTEL (factores del entorno) + metas base + prompt externo.
'PESTEL' es término interno; Todd no lo menciona al usuario.
"""
import json

PESTEL_CATS = ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]

PESTEL_BANK = {
    "politicos": [
        "Cambios políticos (elecciones, reestructuras de gobierno)",
        "Cambios en poderes o estructura de sindicatos",
        "Afectación de relaciones exteriores por eventos en otros países",
        "Burocracia o corrupción en los procesos de gestión pública",
        "Apoyo al emprendimiento mediante programas sociales",
    ],
    "economicos": [
        "Nuevos impuestos o aranceles",
        "Recesión económica por factores globales o federales",
        "Devaluación del peso vs. dólar u otro tipo de cambio",
        "Transacciones con entidades de recursos de dudosa procedencia",
        "Cambios contables exigidos por dependencias de gobierno",
        "Disputas comerciales que afecten la oferta/demanda",
        "Líneas de crédito que promuevan el crecimiento",
        "Pocas o nulas barreras de entrada para nuevos competidores",
    ],
    "sociales": [
        "Cambios en los hábitos de consumo de la sociedad",
        "Nuevas formas de interacción y comunicación entre personas",
        "Requerimientos de estándares de fiabilidad de productos/servicios",
        "Restricciones en publicidad para difundir contenido",
        "Inseguridad en los traslados de mercancías",
        "Robo de talento capacitado por empresas competidoras",
        "Modas, percepción o tendencias que afecten el consumo",
    ],
    "tecnologicos": [
        "Innovación constante en máquinas o herramientas que optimizan procesos",
        "Desarrollo de nuevos materiales o insumos con mejores beneficios",
        "Actualización de software con más funcionalidades",
        "Obsolescencia de tecnología por avances rápidos",
        "Adquisición de productos/servicios de forma online",
        "Aumento de la delincuencia cibernética",
        "Cambios en los modelos de adquisición de tecnología (leasing) y proveeduría",
    ],
    "ambiental": [
        "Protestas de grupos ambientalistas",
        "Nuevas normas ambientales más estrictas (local o federal)",
        "Aumento de costos de recursos naturales por escasez",
        "Nuevas pandemias o enfermedades",
        "Desastres naturales relacionados con el cambio climático",
    ],
    "legal": [
        "Permisos para la operación de la empresa",
        "Combate a la informalidad de las empresas",
        "Plagio de marca, secretos industriales o invenciones",
        "Corrupción en el otorgamiento de permisos de operación",
        "Demandas por incumplimiento de contratos (servicios, proveedores, empleados)",
        "Cambios en leyes de protección al trabajador",
    ],
}

METAS_BASE = [
    "Conseguir más y mejores clientes",
    "Tener empleados más comprometidos con los objetivos de la empresa",
    "Lograr mayor control de calidad en los procesos",
    "Tener claridad de procesos, funciones, responsabilidades y objetivos",
    "Delegar la dirección, formar un consejo y diversificarse/retirarse",
    "Conocer qué tan bien va respecto al potencial de mercado",
    "Reducir costos y maximizar ganancias/flujos",
]

_CAT_LABEL = {
    "politicos": "Políticos", "economicos": "Económicos", "sociales": "Sociales",
    "tecnologicos": "Tecnológicos", "ambiental": "Ambiental", "legal": "Legal",
}


def build_externo_prompt(state: dict | None, diagnostico_ctx: str) -> str:
    banco = "\n".join(
        f"- {_CAT_LABEL[c]}:\n" + "\n".join(f"    · {item}" for item in PESTEL_BANK[c])
        for c in PESTEL_CATS
    )
    estado_txt = ""
    if state:
        estado_txt = ("\n\nESTADO ACUMULADO ACTUAL (constrúyelo encima, no lo pierdas):\n"
                      + json.dumps(state, ensure_ascii=False))
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Ya entrevistaste a la empresa por dentro "
        "y tienes su diagnóstico. Ahora exploras el ENTORNO EXTERNO: una segunda ronda de preguntas, "
        "cálida y profesional, en español, UNA pregunta a la vez.\n\n"
        "DIAGNÓSTICO DE LA EMPRESA (úsalo para preguntar con foco):\n" + (diagnostico_ctx or "(no disponible)") + "\n\n"
        "Explora los factores del entorno por categoría (políticos, económicos, sociales, tecnológicos, "
        "ambientales, legales) usando el banco de abajo como GUÍA (no obligatorio preguntar todo; salta lo "
        "que no aplique, profundiza lo relevante según el diagnóstico). Clasifica cada factor relevante como "
        "OPORTUNIDAD (juega a favor) o AMENAZA (en contra) en 'state.factores_externos' = "
        "{categoria: [{\"tipo\":\"oportunidad\"|\"amenaza\",\"texto\":\"...\"}]}.\n\n"
        "BANCO DE FACTORES POR CATEGORÍA (guía):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Preguntas concretas, una a la vez. Usa 'single_choice' con 'options' cuando aplique "
        "(p. ej. [\"Sí, nos afecta\",\"Más o menos\",\"No\"]); si no, 'text'.\n"
        "2. NO uses tecnicismos como «PESTEL» ni «análisis del entorno»; habla natural.\n"
        "3. Mantén y DEVUELVE el 'state' completo: marca cada categoría en 'areas_cubiertas' "
        "(usa exactamente: politicos, economicos, sociales, tecnologicos, ambiental, legal) cuando la "
        "exploraste, y acumula 'factores_externos'.\n"
        "4. NUNCA repitas una pregunta ya hecha.\n"
        "5. Pon 'done': true SOLO cuando cubriste las 6 categorías; en ese turno 'message' es un cierre "
        "cálido (avisa que ahora priorizarán sus metas)."
        + estado_txt
    )
```

- [ ] **Step 5: Correr (pasa) + tests internos**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_externo.py tests/unit/test_todd_agent.py tests/unit/test_todd_edit.py -q`
Expected: PASS (la cobertura interna sigue funcionando).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/todd/externo.py backend/app/services/ai/todd/agent.py backend/tests/unit/test_todd_externo.py
git commit -m "feat(todd-foda): banco PESTEL + metas base + prompt externo + cobertura genérica"
```

---

### Task 2: Fase externa en el modelo + motor + endpoints (ronda externa + metas)

**Files:**
- Modify: `backend/app/models/todd_session.py` (columna `phase`)
- Create: `backend/scripts/alter_todd_phase.py`
- Modify: `backend/app/services/ai/todd/externo.py` (`run_externo_turn`, `run_externo_edit`, `generar_metas`)
- Modify: `backend/app/api/v1/todd/router.py` (endpoints externos + metas)
- Modify: `backend/app/schemas/todd.py` (`ToddMetasOut`, `ToddMetasIn`)
- Test: `backend/tests/integration/test_todd_externo_api.py` (crear)

**Interfaces:**
- Consumes: `build_externo_prompt`, `enforce_coverage_against`, `PESTEL_CATS`, `METAS_BASE` (Task 1); `build_anthropic_messages`, `_normalize_turn`, `RESPONSE_TOOL`, `_create_with_retry`, `run_todd_edit`-pattern (agent.py).
- Produces: `run_externo_turn(messages, state, diagnostico_ctx)`, `run_externo_edit(messages, edited_question, new_answer, state, diagnostico_ctx)`, `generar_metas(diagnostico_ctx, state_interno, state_externo) -> list[str]`; endpoints `GET/POST /onboarding/todd/externo`, `POST /onboarding/todd/externo/turn`, `POST /onboarding/todd/externo/edit`, `GET /onboarding/todd/metas`, `POST /onboarding/todd/metas`.

- [ ] **Step 1: Columna `phase` + alter script**

En `backend/app/models/todd_session.py`, agregar (después de `status`):
```python
    phase: Mapped[str] = mapped_column(String(20), nullable=False, default="interno")
```
Crear `backend/scripts/alter_todd_phase.py`:
```python
"""Agrega la columna phase a todd_sessions SIN Alembic (prod usa create_all + ALTER).
Idempotente: ADD COLUMN IF NOT EXISTS.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.alter_todd_phase
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE todd_sessions ADD COLUMN IF NOT EXISTS phase VARCHAR(20) NOT NULL DEFAULT 'interno'"))
    await engine.dispose()
    print("OK: columna phase agregada a todd_sessions")


if __name__ == "__main__":
    asyncio.run(main())
```
(NO correr contra prod en este paso — es al desplegar, con autorización.)

- [ ] **Step 2: Motor externo en `externo.py`**

Agregar a `backend/app/services/ai/todd/externo.py`:
```python
import anthropic
from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.todd.agent import (
    build_anthropic_messages, _normalize_turn, enforce_coverage_against, RESPONSE_TOOL,
)


def _externo_call(messages: list[dict], system: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=system, messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL], tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return enforce_coverage_against(_normalize_turn(parsed), PESTEL_CATS)


def run_externo_turn(messages: list[dict], state: dict | None, diagnostico_ctx: str) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "(sin IA) ¿Qué factores del entorno te preocupan?", "options": None,
                "input": "text", "state": state or {}, "done": False, "reanudar_desde": "continuar"}
    return _externo_call(messages, build_externo_prompt(state, diagnostico_ctx))


def run_externo_edit(messages: list[dict], edited_question: str, new_answer: str,
                     state: dict | None, diagnostico_ctx: str) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Listo, corregido. Sigamos.", "options": None, "input": "text",
                "state": state or {}, "done": False, "reanudar_desde": "rehacer"}
    nota = (f"\n\nEDICIÓN: el usuario corrigió «{edited_question}» → «{new_answer}». Revisa si invalida "
            "respuestas posteriores: 'continuar' si no, 'rehacer' si sí (avisa breve y repregunta).")
    return _externo_call(messages, build_externo_prompt(state, diagnostico_ctx) + nota)


_METAS_TOOL = {
    "name": "proponer_metas",
    "description": "Propone la lista de metas a priorizar, personalizada para la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {"metas": {"type": "array", "items": {"type": "string"}}},
        "required": ["metas"],
    },
}


def generar_metas(diagnostico_ctx: str, state_interno: dict, state_externo: dict) -> list[str]:
    """Todd personaliza la lista de metas (parte de METAS_BASE, ajusta según interno+externo)."""
    if not settings.ANTHROPIC_API_KEY:
        return list(METAS_BASE)
    system = (
        "Eres Todd. Con base en el diagnóstico, los hallazgos internos y los factores externos de la "
        "empresa, propone entre 5 y 8 METAS/retos a priorizar, redactadas en primera persona del dueño "
        "(«Quiero…»). Parte de esta lista base y AJÚSTALA al caso (reformula, prioriza distinto, añade o "
        "quita): " + json.dumps(METAS_BASE, ensure_ascii=False) + ".\n\n"
        "DIAGNÓSTICO:\n" + (diagnostico_ctx or "(n/d)") + "\n"
        "INTERNO:\n" + json.dumps(state_interno or {}, ensure_ascii=False)[:2000] + "\n"
        "EXTERNO:\n" + json.dumps(state_externo or {}, ensure_ascii=False)[:2000]
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=1024, system=system,
        messages=[{"role": "user", "content": "Propón las metas a priorizar."}],
        tools=[_METAS_TOOL], tool_choice={"type": "tool", "name": "proponer_metas"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    metas = (block.input.get("metas") if block and isinstance(block.input, dict) else None) or []
    metas = [str(m) for m in metas if str(m).strip()]
    return metas or list(METAS_BASE)
```

- [ ] **Step 3: Schemas**

En `backend/app/schemas/todd.py`, agregar:
```python
class ToddMetasOut(BaseModel):
    metas: list[str]


class ToddMetasIn(BaseModel):
    orden: list[str]
```

- [ ] **Step 4: Endpoints (router)**

En `backend/app/api/v1/todd/router.py`:

1. Imports: agregar
```python
from app.models.diagnostico_estrategico import DiagnosticoEstrategico  # (ya está)
from app.schemas.todd import ToddMetasOut, ToddMetasIn
from app.services.ai.todd.externo import run_externo_turn, run_externo_edit, generar_metas
```
2. Generalizar `_current` para filtrar por fase:
```python
async def _current(user_id: str, db: AsyncSession, phase: str = "interno") -> ToddSession | None:
    return (await db.execute(
        select(ToddSession).where(ToddSession.user_id == user_id, ToddSession.phase == phase)
        .order_by(ToddSession.created_at.desc())
    )).scalar_one_or_none()
```
(Los endpoints internos existentes llaman `_current(user_id, db)` → fase "interno" por default, sin cambios.)
3. Helper de contexto del diagnóstico:
```python
async def _diagnostico_ctx(user_id: str, db: AsyncSession) -> str:
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    c = (diag.content if diag else {}) or {}
    partes = []
    for s in (c.get("sections") or [])[:3]:
        if s.get("body"):
            partes.append(f"{s.get('title','')}: {s['body'][:600]}")
    fd = c.get("fortalezas_debilidades") or {}
    if fd:
        partes.append("Hallazgos internos: " + json.dumps(fd, ensure_ascii=False)[:1200])
    return "\n".join(partes) or "(sin diagnóstico)"
```
(Agregar `import json` arriba del router si no está.)
4. Endpoints externos (after `todd_edit`):
```python
@router.get("/onboarding/todd/externo", response_model=ToddSessionOut)
async def get_externo(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        return Response(status_code=204)
    return ToddSessionOut(
        status=sess.status, messages=[ToddMessage(**m) for m in (sess.messages or [])],
        done=sess.status == "done",
        areas_cubiertas=list((sess.state or {}).get("areas_cubiertas") or []),
    )


@router.post("/onboarding/todd/externo/turn", response_model=ToddTurnOut)
async def externo_turn(body: ToddTurnIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        sess = ToddSession(user_id=user_id, status="active", phase="externo", messages=[], state={})
        db.add(sess); await db.flush()
    ctx = await _diagnostico_ctx(user_id, db)
    messages = list(sess.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})
    turn = await anyio.to_thread.run_sync(lambda: run_externo_turn(messages, sess.state or {}, ctx))
    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    sess.messages = messages
    sess.state = turn["state"] or sess.state
    if turn["done"]:
        sess.status = "done"
    flag_modified(sess, "messages"); flag_modified(sess, "state")
    await db.commit()
    return ToddTurnOut(message=turn["message"], options=turn["options"], input=turn["input"],
                       done=turn["done"], areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []))


@router.post("/onboarding/todd/externo/edit", response_model=ToddTurnOut)
async def externo_edit(body: ToddEditIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        raise HTTPException(status_code=404, detail="No hay ronda externa activa.")
    messages = list(sess.messages or [])
    i = body.answer_index
    if i < 0 or i >= len(messages) or messages[i].get("role") != "user":
        raise HTTPException(status_code=400, detail="Índice de respuesta inválido.")
    ctx = await _diagnostico_ctx(user_id, db)
    corrected = [dict(m) for m in messages]
    corrected[i] = {"role": "user", "text": body.nueva_respuesta, "options": None}
    edited_question = messages[i - 1].get("text", "") if i > 0 else ""
    turn = await anyio.to_thread.run_sync(
        lambda: run_externo_edit(corrected, edited_question, body.nueva_respuesta, sess.state or {}, ctx))
    if turn.get("reanudar_desde") == "rehacer":
        nuevos = corrected[: i + 1] + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    else:
        nuevos = corrected + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    sess.messages = nuevos
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages"); flag_modified(sess, "state")
    await db.commit()
    return ToddTurnOut(message=turn["message"], options=turn["options"], input=turn["input"],
                       done=turn["done"], areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []))


@router.get("/onboarding/todd/metas", response_model=ToddMetasOut)
async def get_metas(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    interno = await _current(user_id, db, phase="interno")
    externo = await _current(user_id, db, phase="externo")
    ctx = await _diagnostico_ctx(user_id, db)
    metas = await anyio.to_thread.run_sync(lambda: generar_metas(
        ctx, (interno.state if interno else {}) or {}, (externo.state if externo else {}) or {}))
    return ToddMetasOut(metas=metas)


@router.post("/onboarding/todd/metas")
async def save_metas(body: ToddMetasIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="No hay diagnóstico.")
    externo = await _current(user_id, db, phase="externo")
    content = dict(diag.content or {})
    content["factores_externos"] = ((externo.state if externo else {}) or {}).get("factores_externos") or {}
    content["metas_orden"] = [str(m) for m in body.orden]
    diag.content = content
    flag_modified(diag, "content")
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Tests de los endpoints**

`backend/tests/integration/test_todd_externo_api.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_ext"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_externo_turn_crea_sesion_fase_externo(monkeypatch):
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    res_diag = MagicMock(); res_diag.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[res_none, res_diag])
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()
    monkeypatch.setattr("app.api.v1.todd.router.run_externo_turn",
        lambda messages, state, ctx: {"message": "¿Te afectan los cambios fiscales?",
            "options": ["Sí", "No"], "input": "single_choice",
            "state": {"areas_cubiertas": ["economicos"]}, "done": False})
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/externo/turn", json={"answer": None})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["areas_cubiertas"] == ["economicos"]
    assert db.add.called


@pytest.mark.asyncio
async def test_get_metas_devuelve_lista(monkeypatch):
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    res_diag = MagicMock(); res_diag.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)
    # _current(interno), _current(externo), _diagnostico_ctx -> 3 execute
    db.execute = AsyncMock(side_effect=[res, res, res_diag])
    monkeypatch.setattr("app.api.v1.todd.router.generar_metas",
        lambda ctx, i, e: ["Quiero más clientes", "Quiero reducir costos"])
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/todd/metas")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["metas"][0] == "Quiero más clientes"


@pytest.mark.asyncio
async def test_save_metas_guarda_en_content(monkeypatch):
    diag = MagicMock(); diag.content = {"sections": []}
    externo = MagicMock(); externo.state = {"factores_externos": {"economicos": [{"tipo": "amenaza", "texto": "impuestos"}]}}
    rdiag = MagicMock(); rdiag.scalars.return_value.first.return_value = diag
    rext = MagicMock(); rext.scalar_one_or_none.return_value = externo
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[rdiag, rext]); db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/metas", json={"orden": ["Quiero más clientes", "Quiero reducir costos"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert diag.content["metas_orden"][0] == "Quiero más clientes"
    assert diag.content["factores_externos"]["economicos"][0]["texto"] == "impuestos"
```

- [ ] **Step 6: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_externo_api.py tests/integration/test_todd_api.py -q && ./venv/bin/pytest -q`
Expected: PASS (los endpoints internos siguen verdes — `_current` con default "interno" no cambia su comportamiento).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/todd_session.py backend/scripts/alter_todd_phase.py backend/app/services/ai/todd/externo.py backend/app/api/v1/todd/router.py backend/app/schemas/todd.py backend/tests/integration/test_todd_externo_api.py
git commit -m "feat(todd-foda): fase externa (PESTEL) en modelo/motor/endpoints + metas personalizadas"
```

---

### Task 3: Frontend — ronda externa (reusa wizard) + ranking de metas + entrada

**Files:**
- Modify: `frontend/src/lib/todd.ts`
- Create: `frontend/src/app/onboarding/todd/externo/page.tsx`
- Create: `frontend/src/app/onboarding/todd/metas/page.tsx`
- Modify: `frontend/src/app/dashboard/diagnostico/page.tsx` (botón "Continuar al análisis del entorno")
- Test: `npm run lint` + `npm run build`

**Interfaces:**
- Consumes: endpoints externos + metas (Task 2).

- [ ] **Step 1: Cliente — agregar a `frontend/src/lib/todd.ts`**

```typescript
export const PESTEL_CATS = ["politicos", "economicos", "sociales", "tecnologicos", "ambiental", "legal"]

export async function getExternoSession(): Promise<ToddSession | null> {
  const r = await api.get("/onboarding/todd/externo", { validateStatus: s => s === 200 || s === 204 })
  if (r.status === 204) return null
  return r.data as ToddSession
}
export async function sendExternoAnswer(answer: string | null): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/externo/turn", { answer })
  return r.data
}
export async function editExternoAnswer(answerIndex: number, nuevaRespuesta: string): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/externo/edit",
    { answer_index: answerIndex, nueva_respuesta: nuevaRespuesta })
  return r.data
}
export async function getMetas(): Promise<string[]> {
  const r = await api.get<{ metas: string[] }>("/onboarding/todd/metas")
  return r.data.metas
}
export async function saveMetas(orden: string[]): Promise<void> {
  await api.post("/onboarding/todd/metas", { orden })
}
```

- [ ] **Step 2: Pantalla de la ronda externa**

`frontend/src/app/onboarding/todd/externo/page.tsx`: copia EXACTA de `frontend/src/app/onboarding/todd/page.tsx` con estos cambios mínimos:
- Importar `getExternoSession, sendExternoAnswer, editExternoAnswer, PESTEL_CATS` (en vez de los internos `getToddSession/sendToddAnswer/editToddAnswer/TODD_AREAS`).
- Usar `PESTEL_CATS` para la barra de progreso y un `AREA_LABEL` con `{politicos:"Políticos",economicos:"Económicos",sociales:"Sociales",tecnologicos:"Tecnológicos",ambiental:"Ambiental",legal:"Legal"}`.
- En `finish` (cuando `done`), en vez de `closeTodd()` + ir al diagnóstico, navegar a la priorización: `router.push("/onboarding/todd/metas")` (sin llamar a close).
- El resto del componente (wizard, edición con "Atrás", "Procesando…") IDÉNTICO. Renombrar el componente a `ExternoPage`.

(Lee `page.tsx` interno como base y aplica solo esos cambios; mantén toda la lógica del wizard y la edición.)

- [ ] **Step 3: Pantalla de priorización (ranking)**

`frontend/src/app/onboarding/todd/metas/page.tsx`:
```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, ChevronUp, ChevronDown } from "lucide-react"
import { getMetas, saveMetas } from "@/lib/todd"

export default function MetasPage() {
  const router = useRouter()
  const [metas, setMetas] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getMetas().then(m => { setMetas(m); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const move = (i: number, dir: -1 | 1) => {
    setMetas(prev => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  const confirmar = async () => {
    setSaving(true)
    try { await saveMetas(metas); router.push("/dashboard/diagnostico") }
    catch { setSaving(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-4">
        <span className="text-sm font-bold tracking-widest">TODD · GOBERNIA</span>
      </header>
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl space-y-6">
          <div>
            <p className="text-xs font-medium text-gray-400">Todd</p>
            <h2 className="text-lg font-bold leading-snug">Ordena tus retos por prioridad — el 1 es el más importante a resolver.</h2>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Preparando tus metas…
            </div>
          ) : (
            <>
              <ul className="space-y-2">
                {metas.map((m, i) => (
                  <li key={m} className="flex items-center gap-3 border border-gray-100 rounded-xl px-3 py-2.5">
                    <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                    <span className="flex-1 text-sm">{m}</span>
                    <div className="flex flex-col">
                      <button onClick={() => move(i, -1)} disabled={i === 0} className="text-gray-300 hover:text-black disabled:opacity-30"><ChevronUp className="h-4 w-4" /></button>
                      <button onClick={() => move(i, 1)} disabled={i === metas.length - 1} className="text-gray-300 hover:text-black disabled:opacity-30"><ChevronDown className="h-4 w-4" /></button>
                    </div>
                  </li>
                ))}
              </ul>
              <button onClick={confirmar} disabled={saving}
                className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-50">
                {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Guardando…</> : "Confirmar prioridades"}
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
```
(Ranking con botones subir/bajar — simple y sin dependencia de drag externa; el orden final es el de la lista. Plan B leerá `metas_orden`.)

- [ ] **Step 4: Entrada desde el diagnóstico**

En `frontend/src/app/dashboard/diagnostico/page.tsx`, agregar (donde están los botones de acción, cerca de "Regenerar diagnóstico") un enlace a la ronda externa cuando el diagnóstico esté `active`:
```tsx
          <div className="pt-2">
            <a href="/onboarding/todd/externo"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
              Continuar al análisis del entorno →
            </a>
          </div>
```
(Colócalo dentro del bloque que se muestra cuando hay diagnóstico activo, junto a las secciones; READ el archivo para insertarlo en un lugar coherente.)

- [ ] **Step 5: lint + build**

Run: `cd frontend && npm run lint` (por separado) y `cd frontend && npm run build`.
Expected: build exit 0; `lib/todd.ts`, `onboarding/todd/externo/page.tsx`, `onboarding/todd/metas/page.tsx`, `dashboard/diagnostico/page.tsx` sin errores nuevos (grep el output por `externo|metas` para confirmar).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/todd.ts frontend/src/app/onboarding/todd/externo/page.tsx frontend/src/app/onboarding/todd/metas/page.tsx frontend/src/app/dashboard/diagnostico/page.tsx
git commit -m "feat(todd-foda-fe): ronda externa (wizard) + ranking de metas + entrada desde el diagnóstico"
```

---

## Self-Review (cobertura del spec, Plan A)

- **Banco PESTEL (Comp.1)** → Task 1 (`externo.PESTEL_BANK`/`PESTEL_CATS`). ✅
- **Ronda externa adaptativa informada por el diagnóstico (Comp.2)** → Task 1 (`build_externo_prompt` con `diagnostico_ctx`) + Task 2 (`run_externo_turn/edit`, fase `externo`, endpoints) + Task 3 (wizard reutilizado). ✅
- **Priorización adaptativa + ranking (Comp.3)** → Task 2 (`generar_metas` + endpoints metas) + Task 3 (pantalla de ranking). ✅
- **Persistencia sin migración mayor** → columna `phase` vía alter script (patrón del proyecto) + factores/metas en `DiagnosticoEstrategico.content`. ✅
- **FODA + vista (Comp.4/5)** → NO en este plan; es el **Plan B** (lee `content.factores_externos` + `content.metas_orden`). ✔ (fuera de alcance declarado)
- **"PESTEL" término interno** → el prompt no lo menciona (test lo verifica). ✅

Consistencia de tipos: `factores_externos` = `{categoria: [{tipo:"oportunidad"|"amenaza", texto}]}` se acumula en `state` (externo) y se copia a `content.factores_externos` en `save_metas`; `content.metas_orden` = lista ordenada. `run_externo_turn/edit` devuelven el mismo shape de turno que el wizard interno (incluye `reanudar_desde` vía `_normalize_turn`). `enforce_coverage_against(turn, PESTEL_CATS)` reusa la lógica de cobertura. Las `areas_cubiertas` externas usan exactamente las claves de `PESTEL_CATS`.

Puntos a verificar al implementar: que `_current(user_id, db)` por default siga dando la fase interna (no romper los endpoints internos); `import json` en el router; que el `page.tsx` externo sea copia del interno con los 4 cambios indicados (no reescribir la lógica del wizard); correr `alter_todd_phase.py` en prod al desplegar (con autorización).
