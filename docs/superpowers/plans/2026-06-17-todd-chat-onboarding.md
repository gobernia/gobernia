# Todd — Chat de onboarding (captura + persistencia + UI) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un chat conversacional con el secretario Todd que reemplaza el onboarding de 8 pasos: conduce una entrevista adaptativa (Sonnet, turno a turno, con cobertura de las 7 áreas), persiste la conversación, y al cerrar escribe el `memory_buffer` que la app ya usa + marca el onboarding completo.

**Architecture:** Tabla nueva `todd_sessions` (transcript + estado). Lógica pura del agente (prompt + parseo + mapeo a memory_buffer) separada de la llamada de red. Endpoints REST para conversar/retomar/cerrar. Pantalla de chat en el frontend. El diagnóstico combinado (Opus + web) es el Plan 2 — aquí, al cerrar, solo se deja el hook (TODO marcado) y se marca el onboarding completo.

**Tech Stack:** FastAPI, SQLAlchemy async, anthropic SDK (Sonnet 4.6 = `settings.AI_MODEL`, vía `_create_with_retry` en thread con `anyio`). Next.js 16 App Router, framer-motion, axios (`@/lib/api`). Esquema en prod por script `create_*` (NO Alembic).

## Global Constraints

- **Esquema sin Alembic:** la tabla nueva se crea con `scripts/create_todd_sessions.py` (`Base.metadata.create_all`), corrido en prod solo con autorización del humano.
- **No romper downstream:** al cerrar, Todd debe escribir `OnboardingSession.memory_buffer` con la MISMA estructura que hoy consume la app (`company`, `kpis`, `vision`, `governance`, `ai_context`) y `completed_stages=[1..8]` + `completed_at`, para que el plan/saludo/etc. sigan funcionando.
- **Modelo del chat:** Sonnet 4.6 (`settings.AI_MODEL`). El diagnóstico (Opus) NO es parte de este plan.
- **El formulario de 8 pasos NO se borra** (queda como fallback).
- **Frontend Next.js 16:** leer `node_modules/next/dist/docs/` si se usa cualquier API de Next; aquí es un client component con `fetch` vía `@/lib/api`.
- **SQLAlchemy:** los defaults de columna NO aplican al construir el objeto en Python; pasar `messages=[]`, `state={}` explícitos al crear.

---

### Task 1: Modelo `ToddSession` + script de creación de tabla

**Files:**
- Create: `backend/app/models/todd_session.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/scripts/create_todd_sessions.py`
- Test: `backend/tests/unit/test_todd_session_model.py`

**Interfaces:**
- Produces: `ToddSession(Base, UUIDMixin, TimestampMixin)` con columnas `user_id: str`, `status: str` (`active`/`done`), `messages: list` (JSONB), `state: dict` (JSONB).

- [ ] **Step 1: Test del modelo**

`backend/tests/unit/test_todd_session_model.py`:
```python
from app.models.todd_session import ToddSession


def test_todd_session_construye_con_defaults_explicitos():
    s = ToddSession(user_id="u1", status="active", messages=[], state={})
    assert s.user_id == "u1"
    assert s.status == "active"
    assert s.messages == []
    assert s.state == {}


def test_todd_session_tablename():
    assert ToddSession.__tablename__ == "todd_sessions"
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_session_model.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Crear el modelo**

`backend/app/models/todd_session.py`:
```python
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class ToddSession(Base, UUIDMixin, TimestampMixin):
    """Entrevista conversacional de onboarding con Todd: transcript + estado acumulado."""
    __tablename__ = "todd_sessions"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # messages: lista de {"role": "todd"|"user", "text": str, "options": [str]|None}
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # state: estado acumulado por Todd (company, kpis, vision, governance, areas_cubiertas, hallazgos, narrative)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

> Confirmar en `app/models/base.py` que existen `Base`, `UUIDMixin`, `TimestampMixin` (los usan annual_plan, diagnostico, etc.). Usar el mismo import.

- [ ] **Step 4: Registrar el modelo**

En `backend/app/models/__init__.py`, agregar el import y el `__all__` (junto a los demás):
```python
from app.models.todd_session import ToddSession  # noqa: F401
```
y añadir `"ToddSession"` a la lista `__all__`.

- [ ] **Step 5: Script de creación de tabla**

`backend/scripts/create_todd_sessions.py`:
```python
"""Crea la tabla todd_sessions SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_todd_sessions
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: tabla todd_sessions creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_session_model.py -q && ./venv/bin/pytest -q`
Expected: PASS. (NO correr el script create contra prod en este paso — eso es al desplegar, con autorización.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/todd_session.py backend/app/models/__init__.py backend/scripts/create_todd_sessions.py backend/tests/unit/test_todd_session_model.py
git commit -m "feat(todd): modelo ToddSession + script create_todd_sessions"
```

---

### Task 2: Lógica pura del agente (banco de áreas + prompt + parseo + mapeo)

**Files:**
- Create: `backend/app/services/ai/todd/__init__.py` (vacío)
- Create: `backend/app/services/ai/todd/areas.py`
- Create: `backend/app/services/ai/todd/agent.py`
- Test: `backend/tests/unit/test_todd_agent.py`

**Interfaces:**
- Produces:
  - `areas.AREAS: list[str]` = `["estrategia","comercial","operativo","rh","financiero","legal","familiar"]`
  - `areas.AREA_BANK: dict[str, list[str]]` (afirmaciones por área).
  - `areas.ESSENTIALS: list[str]` (datos que sí debe obtener).
  - `agent.build_system_prompt() -> str`
  - `agent.build_anthropic_messages(messages: list[dict]) -> list[dict]`
  - `agent.parse_turn(raw: str) -> dict` → `{"message": str, "options": list[str]|None, "input": "text"|"single_choice", "state": dict, "done": bool}`
  - `agent.enforce_coverage(turn: dict) -> dict` (no permite `done` sin las 7 áreas)
  - `agent.state_to_memory_buffer(state: dict) -> dict`

- [ ] **Step 1: Tests de la lógica pura**

`backend/tests/unit/test_todd_agent.py`:
```python
import json
from app.services.ai.todd import areas
from app.services.ai.todd.agent import (
    build_system_prompt, build_anthropic_messages, parse_turn,
    enforce_coverage, state_to_memory_buffer,
)


def test_areas_son_siete():
    assert areas.AREAS == ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]
    assert all(areas.AREA_BANK.get(a) for a in areas.AREAS)


def test_system_prompt_incluye_banco_y_esenciales():
    p = build_system_prompt()
    assert "estrategia" in p.lower() and "financiero" in p.lower()
    assert "JSON" in p
    # menciona al menos un dato esencial
    assert "competidor" in p.lower() or "industria" in p.lower()


def test_build_anthropic_messages_antepone_kickoff_y_alterna():
    history = [
        {"role": "todd", "text": "Hola, soy Todd. ¿Cómo se llama tu empresa?"},
        {"role": "user", "text": "Keting Media"},
    ]
    msgs = build_anthropic_messages(history)
    assert msgs[0]["role"] == "user"            # kickoff
    assert msgs[1] == {"role": "assistant", "content": "Hola, soy Todd. ¿Cómo se llama tu empresa?"}
    assert msgs[2] == {"role": "user", "content": "Keting Media"}
    # alternancia válida y termina en user
    roles = [m["role"] for m in msgs]
    assert roles[-1] == "user"
    for a, b in zip(roles, roles[1:]):
        assert a != b


def test_build_anthropic_messages_vacio_solo_kickoff():
    msgs = build_anthropic_messages([])
    assert len(msgs) == 1 and msgs[0]["role"] == "user"


def test_parse_turn_json_valido():
    raw = json.dumps({
        "message": "¿Tienen misión y visión por escrito?",
        "options": ["Sí", "Más o menos", "No"],
        "input": "single_choice",
        "state": {"company": {"name": "Keting Media"}, "areas_cubiertas": ["estrategia"]},
        "done": False,
    })
    t = parse_turn(raw)
    assert t["message"].startswith("¿Tienen")
    assert t["options"] == ["Sí", "Más o menos", "No"]
    assert t["input"] == "single_choice"
    assert t["state"]["company"]["name"] == "Keting Media"
    assert t["done"] is False


def test_parse_turn_basura_devuelve_defaults_seguros():
    t = parse_turn("esto no es json")
    assert isinstance(t["message"], str)
    assert t["options"] is None
    assert t["input"] == "text"
    assert t["state"] == {}
    assert t["done"] is False


def test_enforce_coverage_bloquea_done_sin_las_7_areas():
    turn = {"done": True, "state": {"areas_cubiertas": ["estrategia", "comercial"]}}
    assert enforce_coverage(turn)["done"] is False


def test_enforce_coverage_permite_done_con_las_7():
    turn = {"done": True, "state": {"areas_cubiertas": areas.AREAS}}
    assert enforce_coverage(turn)["done"] is True


def test_state_to_memory_buffer_mapea_estructura_de_la_app():
    state = {
        "company": {"name": "Keting Media", "industry": "Apps"},
        "kpis": {"financieros": [{"label": "Margen neto", "current_value": 6}]},
        "vision": {"statement": "Crecer 3 años"},
        "governance": {"score": 55, "level": "En desarrollo"},
        "narrative": "Resumen.",
        "hallazgos": {"estrategia": [{"tipo": "fortaleza", "texto": "Tiene visión"}]},
        "areas_cubiertas": areas.AREAS,
    }
    mb = state_to_memory_buffer(state)
    assert mb["company"]["name"] == "Keting Media"
    assert mb["kpis"]["financieros"][0]["label"] == "Margen neto"
    assert mb["vision"]["statement"] == "Crecer 3 años"
    assert mb["governance"]["score"] == 55
    assert mb["ai_context"]["company_narrative"] == "Resumen."
    assert mb["hallazgos"]["estrategia"][0]["tipo"] == "fortaleza"
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_agent.py -q`
Expected: FAIL (módulos no existen).

- [ ] **Step 3: Crear `areas.py`**

`backend/app/services/ai/todd/__init__.py`: archivo vacío.

`backend/app/services/ai/todd/areas.py`:
```python
"""Banco de referencia del diagnóstico (las 7 áreas y sus afirmaciones) + datos esenciales.
Las afirmaciones son una GUÍA opcional: Todd decide cuáles tocar según la conversación.
"""

AREAS = ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]

AREA_BANK = {
    "estrategia": [
        "Cuenta con sistemas que facilitan la administración de información (ERP, MRP, CRM)",
        "Confía en la información de sus sistemas para la toma de decisiones",
        "Tiene una planeación estratégica, misión y visión",
        "Tiene proyecciones anuales de ingreso, costo y gasto",
        "Cuenta con un consejo (consultivo/administración) que evalúa los resultados de la dirección general",
        "Tiene un tablero de indicadores para medir y monitorear el cumplimiento de objetivos",
        "Tiene claridad financiera sobre el uso de utilidades e inversiones de la empresa",
    ],
    "comercial": [
        "Tiene bien identificado su nicho de mercado",
        "Tiene bien identificados a los participantes en la toma de decisión",
        "Conoce y satisface los insights de los tomadores de decisión",
        "Cuenta con una propuesta de valor clara",
        "Tiene pulverizada su venta (no concentrada en pocos clientes)",
        "Cuenta con listas de precios y descuentos claras",
        "Tiene identidad corporativa (marca y logo) clara y reconocida",
        "Realiza estrategias publicitarias o de prospección",
        "Cuenta con un programa de desarrollo comercial (distribuidores, vendedores, etc.)",
        "Tiene pensado diversificar o ampliar su cartera de productos/servicios",
        "Tiene pensado expandir su cobertura geográfica en el corto/mediano plazo",
        "Cuenta con programas para evitar perder o dejar de atender clientes actuales",
        "Cuenta con programas que premian la lealtad de sus clientes",
    ],
    "operativo": [
        "Cuenta con alguna certificación de sus procesos (ISO, NOMs, FDA, etc.)",
        "Tiene mapeados e identificados sus principales procesos",
        "Está libre de cuellos de botella",
        "Tiene inventarios óptimos y bien contabilizados",
        "Considera que los precios de compra a proveedores son los mejores",
        "Cuenta con un programa de desarrollo y evaluación de proveedores",
        "Cuenta con indicadores para medir el desempeño de sus procesos",
        "Considera su sistema de distribución óptimo (entregas a tiempo y completas)",
        "Cuenta con maquinaria, equipo o tecnología para ser más eficiente",
        "Usa al menos el 60% de su capacidad instalada",
    ],
    "rh": [
        "Tiene un proceso formal de reclutamiento y contratación",
        "Tiene una rotación baja o en el promedio de la industria",
        "Tiene sueldos en el promedio o por encima de la industria",
        "Tiene un esquema de compensación ligado al desempeño",
        "Tiene claridad sobre las funciones y responsabilidades de todo su personal",
        "Cuenta con manuales de operación, funciones y perfiles de puestos",
        "Tiene un plan DNC (detección de necesidades de capacitación)",
        "Tiene un plan de desarrollo y crecimiento dentro de la empresa",
    ],
    "financiero": [
        "Revisa el estado de resultados del negocio (P&L)",
        "Lleva el estado de resultado contable en tiempo y forma ante las instituciones correspondientes",
        "Tiene claro y bien valuado su Balance General",
        "Tiene claro el método de costeo directo por producto / unidad de negocio",
        "Tiene presupuesto y control presupuestal (contralor)",
        "Cuenta con un índice de apalancamiento financiero por debajo de 2",
        "Es sujeto de crédito o posee créditos bancarios",
        "Tiene una reserva de capital para poder crecer",
        "Tiene ganancias reales iguales o por encima del promedio de la industria",
    ],
    "legal": [
        "Está libre de requerimientos fiscales y al corriente en el pago de impuestos",
        "Está libre de requerimientos legales, demandas y otros procesos",
        "Tiene protegido su conocimiento (marca registrada, fórmulas, patentes)",
    ],
    "familiar": [
        "Tiene claramente definidas y se cumplen las responsabilidades de los familiares que trabajan en la empresa",
        "Está libre de conflictos familiares que pongan en riesgo la continuidad de la empresa",
        "Tiene claramente separadas las finanzas familiares de las de la empresa",
        "Tiene claro el proceso de sucesión",
    ],
}

# Datos que Todd SÍ debe obtener (la app los consume después).
ESSENTIALS = [
    "Nombre de la empresa (company.name)",
    "Industria / sector (company.industry)",
    "Sitio web (company.website)",
    "Competidores que el usuario cree tener (company.competitors)",
    "Si es empresa familiar (company.is_family_business)",
    "Algunos KPIs clave con su valor si los tiene (kpis)",
    "Visión a 3 años (vision.statement)",
]
```

- [ ] **Step 4: Crear `agent.py`**

`backend/app/services/ai/todd/agent.py`:
```python
"""Agente conversacional de Todd: prompt, parseo y mapeo a memory_buffer.
Lógica pura (sin red) salvo run_todd_turn (la llamada a Sonnet).
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.todd import areas

_OUTPUT_SCHEMA = """{
  "message": "lo que Todd le dice al usuario (una sola pregunta o cierre)",
  "options": ["opción 1", "opción 2"] | null,
  "input": "text" | "single_choice",
  "state": {
    "company": {"name": "...", "industry": "...", "website": "...", "competitors": ["..."],
                "is_family_business": true, "employees": 0, "annual_revenue": "...", "years_operating": 0},
    "kpis": {"categoria": [{"label": "...", "current_value": 0, "benchmark": 0, "unit": "...", "alert": "..."}]},
    "vision": {"statement": "..."},
    "governance": {"score": 0, "level": "..."},
    "narrative": "resumen breve de la empresa que vas armando",
    "areas_cubiertas": ["estrategia", "..."],
    "hallazgos": {"estrategia": [{"tipo": "fortaleza|debilidad|parcial", "texto": "..."}]}
  },
  "done": false
}"""


def build_system_prompt() -> str:
    banco = "\n".join(
        f"- {a.upper()}:\n" + "\n".join(f"    · {item}" for item in items)
        for a, items in areas.AREA_BANK.items()
    )
    esenciales = "\n".join(f"  - {e}" for e in areas.ESSENTIALS)
    return (
        "Eres Todd, el secretario del consejo de Gobernia. Conduces el ONBOARDING como una "
        "ENTREVISTA conversacional, cálida y profesional, en español. Haces UNA pregunta a la vez.\n\n"
        "Tu objetivo: entender bien la empresa para un diagnóstico completo, cubriendo las 7 áreas. "
        "Tienes LIBERTAD para decidir qué preguntar: usa el banco de referencia de abajo como GUÍA "
        "(no es obligatorio preguntar todo), salta lo que no aplique o puedas inferir, y profundiza "
        "cuando una respuesta lo amerite. Cada respuesta que obtengas, clasifícala como fortaleza, "
        "debilidad o parcial en el área correspondiente (en 'hallazgos').\n\n"
        "DATOS QUE SÍ DEBES OBTENER (la plataforma los necesita):\n" + esenciales + "\n\n"
        "BANCO DE REFERENCIA POR ÁREA (guía opcional):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Una sola pregunta por turno. Si la respuesta es acotada, ofrécela como 'single_choice' "
        "con 'options' (p. ej. Sí / Más o menos / No); si es abierta, usa 'text'.\n"
        "2. Actualiza y DEVUELVE el 'state' acumulado en cada turno (no pierdas lo ya capturado). "
        "Marca un área en 'areas_cubiertas' cuando ya la exploraste lo suficiente.\n"
        "3. No repitas lo que ya sabes. Sé natural, no un checklist frío.\n"
        "4. Pide algunos KPIs con número si el usuario los tiene; si no, regístralos cualitativos y NO insistas.\n"
        "5. Pon 'done': true SOLO cuando ya cubriste las 7 áreas y tienes los datos esenciales; en ese "
        "turno, 'message' es un cierre cálido (avisa que prepararás el diagnóstico).\n"
        "6. Responde ÚNICAMENTE con un objeto JSON válido con esta forma exacta (sin texto fuera del JSON):\n"
        + _OUTPUT_SCHEMA
    )


def build_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Antepone un kickoff de usuario y mapea el transcript (todd->assistant, user->user).
    Garantiza que la lista empiece y termine en 'user' (requisito de la API)."""
    out = [{"role": "user", "content": "Conduce la entrevista de onboarding según tus reglas."}]
    for m in messages:
        role = "assistant" if m.get("role") == "todd" else "user"
        out.append({"role": role, "content": m.get("text", "")})
    return out


def parse_turn(raw: str) -> dict:
    """Normaliza la respuesta del LLM a un turno seguro. Ante basura, defaults inocuos."""
    parsed = _extract_json_object(raw) or {}
    state = parsed.get("state")
    if not isinstance(state, dict):
        state = {}
    options = parsed.get("options")
    if not (isinstance(options, list) and options):
        options = None
    input_type = parsed.get("input")
    if input_type not in ("text", "single_choice"):
        input_type = "single_choice" if options else "text"
    return {
        "message": str(parsed.get("message") or "¿Podrías contarme un poco más sobre tu empresa?"),
        "options": [str(o) for o in options] if options else None,
        "input": input_type,
        "state": state,
        "done": bool(parsed.get("done")),
    }


def enforce_coverage(turn: dict) -> dict:
    """No permite cerrar (done) sin haber cubierto las 7 áreas."""
    if turn.get("done"):
        cubiertas = set((turn.get("state") or {}).get("areas_cubiertas") or [])
        if not set(areas.AREAS).issubset(cubiertas):
            turn["done"] = False
    return turn


def state_to_memory_buffer(state: dict) -> dict:
    """Mapea el estado de Todd a la estructura de memory_buffer que la app ya consume."""
    state = state or {}
    return {
        "company": state.get("company") or {},
        "kpis": state.get("kpis") or {},
        "vision": state.get("vision") or {},
        "governance": state.get("governance") or {},
        "ai_context": {"company_narrative": str(state.get("narrative") or "")},
        "hallazgos": state.get("hallazgos") or {},
    }


def run_todd_turn(messages: list[dict]) -> dict:
    """Llamada de red: Sonnet produce el siguiente turno. Devuelve el turno parseado y con cobertura forzada.
    Sin API key → un turno determinista mínimo (para dev/tests sin red)."""
    if not settings.ANTHROPIC_API_KEY:
        return {
            "message": "Hola, soy Todd. (Modo sin IA) ¿Cómo se llama tu empresa?",
            "options": None, "input": "text", "state": {}, "done": False,
        }
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=build_system_prompt(),
        messages=build_anthropic_messages(messages),
    )
    raw = response.content[0].text if response.content else ""
    return enforce_coverage(parse_turn(raw))
```

- [ ] **Step 5: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_agent.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/todd/ backend/tests/unit/test_todd_agent.py
git commit -m "feat(todd): lógica pura del agente (banco de áreas, prompt, parseo, mapeo a memory_buffer)"
```

---

### Task 3: Endpoints del chat (turno / retomar / cerrar)

**Files:**
- Create: `backend/app/api/v1/todd/__init__.py` (vacío)
- Create: `backend/app/api/v1/todd/router.py`
- Create: `backend/app/schemas/todd.py`
- Modify: `backend/app/main.py` (registrar el router)
- Test: `backend/tests/integration/test_todd_api.py`

**Interfaces:**
- Consumes: `run_todd_turn`, `state_to_memory_buffer` (Task 2); `ToddSession` (Task 1); `OnboardingSession`.
- Produces:
  - `POST /api/v1/onboarding/todd/turn` body `{answer: str|null}` → `ToddTurnOut`.
  - `GET /api/v1/onboarding/todd` → `ToddSessionOut` (retomar; 204 si no hay).
  - `POST /api/v1/onboarding/todd/close` → `{ok: true}` (escribe memory_buffer + marca onboarding completo).

- [ ] **Step 1: Tests de los endpoints**

`backend/tests/integration/test_todd_api.py`:
```python
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_todd"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_turn_inicia_sesion_y_responde(monkeypatch):
    # No hay sesión previa → se crea; run_todd_turn mockeado.
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=res_none)
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_turn",
        lambda messages: {"message": "Hola, soy Todd. ¿Cómo se llama tu empresa?",
                          "options": None, "input": "text",
                          "state": {"areas_cubiertas": []}, "done": False},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/turn", json={"answer": None})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["message"].startswith("Hola")
    assert body["done"] is False
    assert db.add.called  # creó la sesión


@pytest.mark.asyncio
async def test_get_todd_sin_sesion_devuelve_204(monkeypatch):
    res_none = MagicMock(); res_none.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=res_none)
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/todd")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_close_escribe_memory_buffer_y_marca_onboarding(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"company": {"name": "Keting Media"}, "areas_cubiertas": []}
    onb = MagicMock(); onb.user_id = MOCK_USER_ID
    # 1ª query: ToddSession; 2ª: OnboardingSession
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    r2 = MagicMock(); r2.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2]); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/close")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.status == "done"
    assert onb.memory_buffer["company"]["name"] == "Keting Media"
    assert onb.completed_stages == [1, 2, 3, 4, 5, 6, 7, 8]
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py -q`
Expected: FAIL (ruta no existe).

- [ ] **Step 3: Schemas**

`backend/app/schemas/todd.py`:
```python
from pydantic import BaseModel


class ToddTurnIn(BaseModel):
    answer: str | None = None


class ToddTurnOut(BaseModel):
    message: str
    options: list[str] | None = None
    input: str = "text"
    done: bool = False


class ToddMessage(BaseModel):
    role: str
    text: str
    options: list[str] | None = None


class ToddSessionOut(BaseModel):
    status: str
    messages: list[ToddMessage]
    done: bool
```

- [ ] **Step 4: Router**

`backend/app/api/v1/todd/__init__.py`: vacío.

`backend/app/api/v1/todd/router.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import anyio

from app.core.dependencies import get_current_user_id, get_db
from app.models.todd_session import ToddSession
from app.models.onboarding_session import OnboardingSession
from app.schemas.todd import ToddTurnIn, ToddTurnOut, ToddSessionOut, ToddMessage
from app.services.ai.todd.agent import run_todd_turn, state_to_memory_buffer

router = APIRouter()


async def _current(user_id: str, db: AsyncSession) -> ToddSession | None:
    return (await db.execute(
        select(ToddSession).where(ToddSession.user_id == user_id)
        .order_by(ToddSession.created_at.desc())
    )).scalar_one_or_none()


@router.get("/onboarding/todd", response_model=ToddSessionOut)
async def get_todd(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        return Response(status_code=204)
    return ToddSessionOut(
        status=sess.status,
        messages=[ToddMessage(**m) for m in (sess.messages or [])],
        done=sess.status == "done",
    )


@router.post("/onboarding/todd/turn", response_model=ToddTurnOut)
async def todd_turn(
    body: ToddTurnIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        sess = ToddSession(user_id=user_id, status="active", messages=[], state={})
        db.add(sess)
        await db.flush()

    messages = list(sess.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})

    turn = await anyio.to_thread.run_sync(lambda: run_todd_turn(messages))

    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    sess.messages = messages
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages")
    flag_modified(sess, "state")
    await db.commit()

    return ToddTurnOut(
        message=turn["message"], options=turn["options"],
        input=turn["input"], done=turn["done"],
    )


@router.post("/onboarding/todd/close")
async def todd_close(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        return {"ok": False}
    sess.status = "done"

    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    if onb is None:
        onb = OnboardingSession(user_id=user_id, completed_stages=[], memory_buffer={})
        db.add(onb)

    onb.memory_buffer = state_to_memory_buffer(sess.state or {})
    onb.completed_stages = [1, 2, 3, 4, 5, 6, 7, 8]
    onb.completed_at = datetime.now(timezone.utc)
    flag_modified(onb, "memory_buffer")
    flag_modified(onb, "completed_stages")
    await db.commit()
    # TODO (Plan 2): disparar aquí el diagnóstico combinado (Opus + web) con sess.state['hallazgos'].
    return {"ok": True}
```

> Confirmar el nombre real del helper de id de `OnboardingSession` (usa `UUIDMixin`, el `id` se genera; al crear uno nuevo aquí pasar `completed_stages=[]`, `memory_buffer={}` explícitos por el tema de defaults). `flag_modified` se importa de `sqlalchemy.orm.attributes` (ya se usa así en annual_plan router).

- [ ] **Step 5: Registrar el router**

En `backend/app/main.py`: agregar el import (junto a los otros) y el include:
```python
from app.api.v1.todd.router import router as todd_router
```
```python
app.include_router(todd_router, prefix="/api/v1", tags=["todd"])
```

- [ ] **Step 6: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py -q && ./venv/bin/pytest -q`
Expected: PASS (todo verde).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/todd/ backend/app/schemas/todd.py backend/app/main.py backend/tests/integration/test_todd_api.py
git commit -m "feat(todd): endpoints del chat (turno/retomar/cerrar) + escribe memory_buffer al cerrar"
```

---

### Task 4: Frontend — cliente + pantalla de chat de Todd

**Files:**
- Create: `frontend/src/lib/todd.ts`
- Create: `frontend/src/app/onboarding/todd/page.tsx`
- Test: `npm run lint` + `npm run build`

**Interfaces:**
- Consumes: `POST /onboarding/todd/turn`, `GET /onboarding/todd`, `POST /onboarding/todd/close`.

- [ ] **Step 1: Cliente `lib/todd.ts`**

`frontend/src/lib/todd.ts`:
```typescript
import api from "@/lib/api"

export interface ToddTurn {
  message: string
  options: string[] | null
  input: "text" | "single_choice"
  done: boolean
}

export interface ToddMessage {
  role: "todd" | "user"
  text: string
  options: string[] | null
}

export interface ToddSession {
  status: string
  messages: ToddMessage[]
  done: boolean
}

export async function getToddSession(): Promise<ToddSession | null> {
  const r = await api.get("/onboarding/todd", { validateStatus: s => s === 200 || s === 204 })
  if (r.status === 204) return null
  return r.data as ToddSession
}

export async function sendToddAnswer(answer: string | null): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/turn", { answer })
  return r.data
}

export async function closeTodd(): Promise<void> {
  await api.post("/onboarding/todd/close")
}
```

- [ ] **Step 2: Pantalla de chat**

`frontend/src/app/onboarding/todd/page.tsx`:
```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Send, Loader2 } from "lucide-react"
import {
  ToddMessage, ToddTurn, getToddSession, sendToddAnswer, closeTodd,
} from "@/lib/todd"

export default function ToddPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ToddMessage[]>([])
  const [turn, setTurn] = useState<ToddTurn | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [closing, setClosing] = useState(false)
  const started = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getToddSession()
      .then(async sess => {
        if (sess && sess.messages.length > 0) {
          setMessages(sess.messages)
          const last = sess.messages[sess.messages.length - 1]
          setTurn({ message: last.text, options: last.options, input: last.options ? "single_choice" : "text", done: sess.done })
        } else {
          const t = await sendToddAnswer(null)
          setTurn(t)
          setMessages([{ role: "todd", text: t.message, options: t.options }])
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, busy])

  const answer = async (value: string) => {
    if (!value.trim() || busy) return
    setBusy(true); setInput("")
    setMessages(prev => [...prev, { role: "user", text: value, options: null }])
    try {
      const t = await sendToddAnswer(value)
      setTurn(t)
      setMessages(prev => [...prev, { role: "todd", text: t.message, options: t.options }])
    } catch {
      setMessages(prev => [...prev, { role: "todd", text: "Tuve un problema, ¿puedes repetirlo?", options: null }])
    } finally {
      setBusy(false)
    }
  }

  const finish = async () => {
    setClosing(true)
    try { await closeTodd(); router.push("/dashboard/diagnostico") }
    catch { setClosing(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-3 text-sm font-bold tracking-widest">TODD · GOBERNIA</header>

      <main className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl mx-auto w-full space-y-4">
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]" : "bg-gray-100 text-black"}`}>
              {m.text}
            </div>
          </motion.div>
        ))}
        {busy && (
          <div className="flex justify-start"><div className="bg-gray-100 rounded-2xl px-4 py-2.5">
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" /></div></div>
        )}
        <div ref={bottomRef} />
      </main>

      <footer className="border-t border-gray-100 px-4 py-3 max-w-2xl mx-auto w-full space-y-3">
        {turn?.options && turn.options.length > 0 && !busy && (
          <div className="flex flex-wrap gap-2">
            {turn.options.map(o => (
              <button key={o} onClick={() => answer(o)}
                className="text-sm border border-gray-200 rounded-full px-3 py-1.5 hover:border-[var(--gob-navy)] transition-colors">
                {o}
              </button>
            ))}
          </div>
        )}
        {turn?.done ? (
          <button onClick={finish} disabled={closing}
            className="w-full bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-xl py-3 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50">
            {closing ? <><Loader2 className="h-4 w-4 animate-spin" /> Preparando tu diagnóstico…</> : "Finalizar y ver mi diagnóstico"}
          </button>
        ) : (
          <form onSubmit={e => { e.preventDefault(); answer(input) }} className="flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} disabled={busy}
              placeholder="Escribe tu respuesta…"
              className="flex-1 h-11 rounded-xl border-2 border-gray-100 px-4 text-sm focus:border-black focus:outline-none" />
            <button type="submit" disabled={busy || !input.trim()}
              className="h-11 w-11 rounded-xl bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center disabled:opacity-40">
              <Send className="h-4 w-4" />
            </button>
          </form>
        )}
      </footer>
    </div>
  )
}
```

> Nota lint: el setState dentro de `.then()`/handlers async no dispara `react-hooks/set-state-in-effect` (no es setState síncrono en el cuerpo del efecto). Si lint marcara algo nuevo en este archivo, mirar el patrón de `dashboard/plan/page.tsx` (queueMicrotask / eslint-disable) y aplicarlo mínimamente.

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores NUEVOS (los 8 problemas pre-existentes en otros archivos no cuentan; confirmar que `lib/todd.ts` y `onboarding/todd/page.tsx` salen limpios). Si `npm run lint` corta el `&&` por los errores pre-existentes, correr `npm run build` por separado y verificar exit 0.

- [ ] **Step 4: Smoke (referencia)**

Con backend corriendo y un usuario logueado, ir a `/onboarding/todd`: Todd saluda, responder texto y opciones, ver que la conversación avanza; al llegar a `done`, "Finalizar" lleva a `/dashboard/diagnostico`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/todd.ts frontend/src/app/onboarding/todd/page.tsx
git commit -m "feat(todd-fe): pantalla de chat de Todd + cliente"
```

---

## Self-Review (cobertura del spec, Plan 1)

- **Motor conversacional turno a turno (Sonnet, híbrido libre + cobertura 7 áreas)** → Task 2 (`build_system_prompt`, `run_todd_turn`, `enforce_coverage`) + Task 3 (endpoint de turno). ✅
- **Banco de las ~50 como guía opcional** → Task 2 (`areas.AREA_BANK`, inyectado en el prompt). ✅
- **Captura estructurada → memory_buffer** → Task 2 (`state_to_memory_buffer`) + Task 3 (close escribe memory_buffer + completed_stages + completed_at). ✅
- **Persistencia (transcript + estado, retomable)** → Task 1 (`ToddSession`) + Task 3 (GET retomar). ✅
- **UI de chat (texto + selección simple, finalizar)** → Task 4. ✅
- **No romper downstream** → close escribe la estructura que la app consume; el formulario viejo no se toca. ✅
- **Diagnóstico combinado (Opus + web)** → NO en este plan; queda el hook `# TODO (Plan 2)` en `todd_close`. (Plan 2). ✔ (fuera de alcance declarado)

Consistencia de tipos: `run_todd_turn`/`parse_turn` devuelven `{message, options, input, state, done}` — consumido igual en el router y en `ToddTurnOut`/`lib/todd.ts`. `state_to_memory_buffer(state)` produce `{company,kpis,vision,governance,ai_context,hallazgos}` — la estructura que lee `_build_company_context`/`kpi_labels_from_buffer`. `ToddSession.messages` = lista de `{role,text,options}` — igual en el modelo, el router, el schema `ToddMessage` y `lib/todd.ts`.

Pendiente a verificar al implementar: mixins reales en `app/models/base.py`; que `_extract_json_object`/`_create_with_retry` se importen bien desde `app/services/ai/agents/base.py`; el patrón exacto de `flag_modified`; que la creación de `OnboardingSession`/`ToddSession` pase los JSONB explícitos (defaults no aplican al construir).
