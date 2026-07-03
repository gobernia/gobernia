# Perspectivas (múltiples voces) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir invitar por link (sin cuenta) a empleados, directivos, socios, clientes y proveedores a una mini-entrevista con Todd adaptada a su rol, consolidar sus voces (coincidencias / contradicciones / puntos ciegos) respetando el anonimato por rol, e inyectar esa síntesis al FODA y al plan.

**Architecture:** Tabla nueva `perspectiva_invites` (como `ToddSession` pero accesible por token público). Motor de entrevista que reutiliza el tool-use estructurado de Todd con un prompt por rol. Endpoints públicos por token (sin login) + endpoints del dueño (con login). Agente de consolidación Opus (espejo de `foda.py`) disparado por Celery, que escribe `DiagnosticoEstrategico.content["perspectivas"]`. Frontend: página del dueño `/dashboard/perspectivas` + página pública `/p/{token}` que reutiliza el wizard de Todd.

**Tech Stack:** FastAPI, SQLAlchemy async (Base/UUIDMixin/TimestampMixin), Celery, Pydantic v2, anthropic SDK (tool use forzado), Next.js 16 App Router, TypeScript, Tailwind v4, framer-motion, axios (`@/lib/api`, baseURL incluye `/api/v1`).

## Global Constraints

- Esquema de prod con scripts `create_all`, **NO Alembic**. Tablas nuevas se crean con `backend/scripts/create_*.py` y se corren en prod **solo con autorización humana**.
- Deploy: push a **AMBOS remotos** (`origin`=gobernia/gobernia web/Vercel, `cbeuvrin`=cbeuvrin/gobernia worker/Railway).
- Modelos: chat/turnos = `settings.AI_MODEL` (Sonnet); síntesis/diagnóstico = `settings.DIAGNOSTICO_AI_MODEL` (Opus).
- Salida estructurada del LLM SIEMPRE por tool use forzado (`tools=[TOOL]` + `tool_choice={"type":"tool","name":...}`), leyendo `block.input`.
- Sin API key → los servicios de IA devuelven un fallback determinista (dev/tests sin red).
- Anonimato: roles `empleado` y `cliente` son agregados/anónimos (nunca nombre ni respuesta individual en salida visible); `directivo`, `socio`, `proveedor` son atribuidos (con nombre).
- Referencia de baseURL frontend: las funciones de `@/lib/api` ya incluyen `/api/v1`, así que las rutas se pasan sin ese prefijo (p. ej. `/perspectivas`, `/perspectiva/{token}`).
- Correr la suite backend completa con `venv/bin/python -m pytest -q` desde `backend/`. Lint frontend con `npx eslint <archivo>` desde `frontend/`.

---

### Task 1: Modelo `perspectiva_invites` + script de creación

**Files:**
- Create: `backend/app/models/perspectiva_invite.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/scripts/create_perspectiva_invites.py`
- Test: `backend/tests/unit/test_perspectiva_model.py`

**Interfaces:**
- Produces: modelo `PerspectivaInvite` (tabla `perspectiva_invites`) con columnas `id, owner_user_id, role, invitee_name, token, status, messages, state, created_at, updated_at`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_perspectiva_model.py
from app.models.perspectiva_invite import PerspectivaInvite


def test_perspectiva_invite_tablename_y_columnas():
    assert PerspectivaInvite.__tablename__ == "perspectiva_invites"
    cols = PerspectivaInvite.__table__.columns
    for c in ("owner_user_id", "role", "invitee_name", "token", "status", "messages", "state"):
        assert c in cols, f"falta columna {c}"
    assert cols["token"].unique is True
    assert cols["status"].default.arg == "pending"


def test_perspectiva_invite_esta_registrado_en_metadata():
    from app.models import Base
    assert "perspectiva_invites" in Base.metadata.tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectiva_model.py -v`
Expected: FAIL con `ModuleNotFoundError: app.models.perspectiva_invite`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/models/perspectiva_invite.py
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PerspectivaInvite(Base, UUIDMixin, TimestampMixin):
    """Invitación a una perspectiva externa. Accesible por token público (el invitado no tiene cuenta)."""
    __tablename__ = "perspectiva_invites"

    owner_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # empleado|directivo|socio|cliente|proveedor
    invitee_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|active|done
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

Añade a `backend/app/models/__init__.py` (después de la línea de `ToddSession`):

```python
from app.models.perspectiva_invite import PerspectivaInvite  # noqa: F401
```

y agrega `"PerspectivaInvite"` a la lista `__all__`.

Crea el script (idéntico patrón a `create_todd_sessions.py`):

```python
# backend/scripts/create_perspectiva_invites.py
"""Crea la tabla perspectiva_invites SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_perspectiva_invites
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: tabla perspectiva_invites creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectiva_model.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/perspectiva_invite.py backend/app/models/__init__.py backend/scripts/create_perspectiva_invites.py backend/tests/unit/test_perspectiva_model.py
git commit -m "feat(perspectivas): modelo perspectiva_invites + script de creación"
```

---

### Task 2: Bancos de rol + motor de entrevista por rol

**Files:**
- Create: `backend/app/services/ai/perspectivas/__init__.py` (vacío)
- Create: `backend/app/services/ai/perspectivas/roles.py`
- Create: `backend/app/services/ai/perspectivas/agent.py`
- Test: `backend/tests/unit/test_perspectivas_agent.py`

**Interfaces:**
- Consumes: de `app.services.ai.todd.agent` → `RESPONSE_TOOL`, `build_anthropic_messages`, `_normalize_turn`. De `app.services.ai.agents.base` → `_create_with_retry`.
- Produces:
  - `roles.ROLES: list[str]` = `["empleado", "directivo", "socio", "cliente", "proveedor"]`
  - `roles.ROLE_LABEL: dict[str,str]`, `roles.ANONYMOUS_ROLES: set[str]` = `{"empleado","cliente"}`, `roles.ROLE_BANK: dict[str,list[str]]`
  - `agent.build_perspectiva_prompt(role: str, empresa_ctx: str) -> str`
  - `agent.run_perspectiva_turn(messages: list[dict], state: dict | None, role: str, empresa_ctx: str) -> dict` (devuelve turno normalizado `{message, options, input, state, done, ...}`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_perspectivas_agent.py
from app.services.ai.perspectivas import roles
from app.services.ai.perspectivas.agent import build_perspectiva_prompt, run_perspectiva_turn


def test_roles_definidos():
    assert roles.ROLES == ["empleado", "directivo", "socio", "cliente", "proveedor"]
    assert roles.ANONYMOUS_ROLES == {"empleado", "cliente"}


def test_prompt_por_rol_menciona_el_rol_y_la_empresa():
    p = build_perspectiva_prompt("cliente", "Keting Media · software")
    assert "Keting Media" in p
    # el prompt de cliente NO debe pedir datos internos que un cliente no conoce (rh/finanzas)
    low = p.lower()
    assert "cliente" in low
    assert "rotación de personal" not in low and "margen neto" not in low


def test_prompt_empleado_enfoca_operacion_y_cultura():
    p = build_perspectiva_prompt("empleado", "Empresa X").lower()
    assert "empleado" in p or "equipo" in p


def test_run_perspectiva_turn_sin_api_key_devuelve_turno_minimo(monkeypatch):
    monkeypatch.setattr("app.services.ai.perspectivas.agent.settings.ANTHROPIC_API_KEY", "")
    t = run_perspectiva_turn([], None, "cliente", "Empresa X")
    assert set(t.keys()) >= {"message", "options", "input", "state", "done"}
    assert t["done"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_agent.py -v`
Expected: FAIL con `ModuleNotFoundError: app.services.ai.perspectivas`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/ai/perspectivas/__init__.py
```

```python
# backend/app/services/ai/perspectivas/roles.py
"""Roles de perspectivas + guía de temas por rol (opcional; el agente adapta)."""

ROLES = ["empleado", "directivo", "socio", "cliente", "proveedor"]

ROLE_LABEL = {
    "empleado": "Empleado clave",
    "directivo": "Directivo",
    "socio": "Socio",
    "cliente": "Cliente",
    "proveedor": "Proveedor / aliado",
}

# Roles cuyas respuestas se muestran SIEMPRE agregadas/anónimas (nunca nombre).
ANONYMOUS_ROLES = {"empleado", "cliente"}

# Guía de temas por rol (el agente pregunta SOLO lo que ese rol conoce bien).
ROLE_BANK = {
    "empleado": [
        "Claridad de sus funciones y responsabilidades",
        "Qué tan claros y ágiles son los procesos del día a día",
        "Cuellos de botella o trabas que ve en la operación",
        "Cómo percibe la comunicación y el clima laboral",
        "Qué cambiaría para trabajar mejor",
    ],
    "directivo": [
        "Claridad de la estrategia y las prioridades de la empresa",
        "Fortalezas y debilidades que ve en el negocio",
        "Salud financiera y de crecimiento (a alto nivel)",
        "Riesgos principales que percibe",
        "Qué debería cambiar la dirección",
    ],
    "socio": [
        "Visión de largo plazo y alineación entre socios",
        "Fortalezas y riesgos del negocio",
        "Uso de utilidades e inversiones",
        "Gobierno y toma de decisiones",
    ],
    "cliente": [
        "Qué tan clara y valiosa percibe la propuesta de valor",
        "Por qué compra (o dejaría de comprar)",
        "Calidad del producto/servicio y del trato",
        "Qué mejoraría de su experiencia",
        "Cómo lo compara con otras opciones del mercado",
    ],
    "proveedor": [
        "Confiabilidad de la relación comercial (pagos, comunicación)",
        "Qué tan fácil es trabajar con la empresa",
        "Oportunidades de mejora en la colaboración",
    ],
}
```

```python
# backend/app/services/ai/perspectivas/agent.py
"""Motor de entrevista de perspectivas: prompt por rol + turno estructurado (tool use).
Reutiliza el tool-use de Todd; NO exige cobertura de 7 áreas (es específico por rol)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.todd.agent import RESPONSE_TOOL, build_anthropic_messages, _normalize_turn
from app.services.ai.perspectivas import roles as roles_mod


def build_perspectiva_prompt(role: str, empresa_ctx: str) -> str:
    label = roles_mod.ROLE_LABEL.get(role, role)
    banco = "\n".join(f"    · {t}" for t in roles_mod.ROLE_BANK.get(role, []))
    return (
        f"Eres Todd, el secretario del consejo de Gobernia. Estás entrevistando a un {label} de la "
        f"empresa «{empresa_ctx or 'la empresa'}» para conocer SU perspectiva. Habla en español, "
        "cálido y breve. Haces UNA pregunta a la vez.\n\n"
        "IMPORTANTE: pregunta SOLO lo que este rol conoce de primera mano. NO le pidas datos internos "
        "que no le corresponden (finanzas internas, nómina, RH) si el rol es cliente o proveedor.\n\n"
        "TEMAS SUGERIDOS PARA ESTE ROL (guía; adapta según responda):\n" + banco + "\n\n"
        "REGLAS:\n"
        "1. Preguntas CONCRETAS y específicas, una a la vez. Nada de «cuéntame de la empresa».\n"
        "2. Ofrece 'single_choice' con 'options' cuando la respuesta sea acotada; si es abierta usa 'text'.\n"
        "3. Un «no sé / no aplica» es válido: regístralo y avanza; nunca te atores.\n"
        "4. Acumula en 'state' lo que aprendas (percepciones, fortalezas, quejas, sugerencias).\n"
        "5. La entrevista es CORTA (5–8 preguntas). Pon 'done': true con un cierre cálido de agradecimiento "
        "cuando tengas suficiente."
    )


def run_perspectiva_turn(messages: list[dict], state: dict | None,
                         role: str, empresa_ctx: str) -> dict:
    """Siguiente turno de la entrevista de perspectiva (Sonnet, tool use forzado).
    Sin API key → turno determinista mínimo (dev/tests sin red)."""
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Hola, soy Todd. (Modo sin IA) ¿Qué es lo que más valoras de la empresa?",
                "options": None, "input": "text", "state": state or {}, "done": False}
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=build_perspectiva_prompt(role, empresa_ctx),
        messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL], tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return _normalize_turn(parsed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_agent.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/perspectivas/ backend/tests/unit/test_perspectivas_agent.py
git commit -m "feat(perspectivas): bancos por rol + motor de entrevista adaptado"
```

---

### Task 3: Endpoints del dueño (crear/listar/revocar invitaciones)

**Files:**
- Create: `backend/app/schemas/perspectivas.py`
- Create: `backend/app/api/v1/perspectivas/__init__.py` (vacío)
- Create: `backend/app/api/v1/perspectivas/router.py`
- Modify: `backend/app/main.py` (registrar router)
- Test: `backend/tests/integration/test_perspectivas_api.py`

**Interfaces:**
- Consumes: `PerspectivaInvite` (Task 1), `roles.ROLES` (Task 2), `get_current_user_id`, `get_db`.
- Produces: router del dueño montado en `/api/v1`; helper `_empresa_ctx_for(owner_user_id, db) -> str`; endpoints `POST /perspectivas/invite`, `GET /perspectivas`, `DELETE /perspectivas/{id}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_perspectivas_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user_override():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_invite_crea_token_y_url():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/perspectivas/invite", json={"role": "cliente"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cliente"
    assert len(body["token"]) >= 16
    assert body["token"] in body["url"]


@pytest.mark.asyncio
async def test_invite_rechaza_rol_invalido():
    db = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/perspectivas/invite", json={"role": "extraterrestre"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_perspectivas_api.py -v`
Expected: FAIL (404 en la ruta / router no montado).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/schemas/perspectivas.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["empleado", "directivo", "socio", "cliente", "proveedor"]


class InviteIn(BaseModel):
    role: Role
    name: str | None = None


class InviteOut(BaseModel):
    id: str
    role: str
    invitee_name: str | None = None
    token: str
    url: str
    status: str
    created_at: datetime


class InviteListItem(BaseModel):
    id: str
    role: str
    invitee_name: str | None = None
    token: str
    status: str
    created_at: datetime
```

```python
# backend/app/api/v1/perspectivas/router.py
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.perspectiva_invite import PerspectivaInvite
from app.models.onboarding_session import OnboardingSession
from app.schemas.perspectivas import InviteIn, InviteOut, InviteListItem

router = APIRouter()


async def _empresa_ctx_for(owner_user_id: str, db: AsyncSession) -> str:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == owner_user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    c = (((onb.memory_buffer if onb else {}) or {}).get("company") or {})
    partes = [str(c[k]) for k in ("name", "industry") if c.get(k)]
    return " · ".join(partes)


def _invite_url(token: str) -> str:
    return f"/p/{token}"


@router.post("/perspectivas/invite", response_model=InviteOut)
async def crear_invite(
    body: InviteIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(16)
    inv = PerspectivaInvite(
        owner_user_id=user_id, role=body.role,
        invitee_name=(body.name or None), token=token,
        status="pending", messages=[], state={},
    )
    db.add(inv)
    await db.flush()
    await db.commit()
    return InviteOut(
        id=str(inv.id), role=inv.role, invitee_name=inv.invitee_name, token=token,
        url=_invite_url(token), status=inv.status, created_at=inv.created_at,
    )


@router.get("/perspectivas", response_model=list[InviteListItem])
async def listar_invites(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PerspectivaInvite).where(PerspectivaInvite.owner_user_id == user_id)
        .order_by(PerspectivaInvite.created_at.desc())
    )).scalars().all()
    return [InviteListItem(id=str(r.id), role=r.role, invitee_name=r.invitee_name,
                           token=r.token, status=r.status, created_at=r.created_at) for r in rows]


@router.delete("/perspectivas/{invite_id}")
async def revocar_invite(
    invite_id: str,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    inv = (await db.execute(
        select(PerspectivaInvite).where(
            PerspectivaInvite.id == invite_id, PerspectivaInvite.owner_user_id == user_id)
    )).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    await db.delete(inv)
    await db.commit()
    return {"deleted": True}
```

En `backend/app/main.py`: junto a los otros imports de routers añade
`from app.api.v1.perspectivas.router import router as perspectivas_router`
y junto a los `include_router` añade
`app.include_router(perspectivas_router, prefix="/api/v1", tags=["perspectivas"])`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_perspectivas_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/perspectivas.py backend/app/api/v1/perspectivas/ backend/app/main.py backend/tests/integration/test_perspectivas_api.py
git commit -m "feat(perspectivas): endpoints del dueño (crear/listar/revocar)"
```

---

### Task 4: Endpoints públicos de la entrevista (por token, sin login)

**Files:**
- Create: `backend/app/api/v1/perspectivas/public.py`
- Modify: `backend/app/main.py` (registrar router público)
- Test: `backend/tests/integration/test_perspectivas_public_api.py`

**Interfaces:**
- Consumes: `PerspectivaInvite`, `run_perspectiva_turn` (Task 2), `_empresa_ctx_for` (Task 3), `get_db`. NO usa `get_current_user_id` (es público por token).
- Produces: router público montado en `/api/v1`; endpoints `GET /perspectiva/{token}`, `POST /perspectiva/{token}/turn`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_perspectivas_public_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_db


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_get_token_invalido_da_404():
    db = AsyncMock()
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/perspectiva/token-inexistente")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_token_valido_devuelve_rol_y_empresa(monkeypatch):
    inv = MagicMock()
    inv.role = "cliente"; inv.messages = []; inv.status = "pending"
    res_inv = MagicMock(); res_inv.scalar_one_or_none.return_value = inv
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "Keting Media"}}
    res_onb = MagicMock(); res_onb.scalars.return_value.first.return_value = onb
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[res_inv, res_onb])
    app.dependency_overrides[get_db] = _db_override(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/perspectiva/tok-abc")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cliente"
    assert "Keting Media" in body["company_name"]
    assert body["done"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_perspectivas_public_api.py -v`
Expected: FAIL (404 por ruta inexistente en ambos, o error de import).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/api/v1/perspectivas/public.py
import anyio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_db
from app.models.perspectiva_invite import PerspectivaInvite
from app.services.ai.perspectivas.agent import run_perspectiva_turn
from app.api.v1.perspectivas.router import _empresa_ctx_for

router = APIRouter()


class PublicAnswerIn(BaseModel):
    answer: str | None = None


async def _get_invite_or_404(token: str, db: AsyncSession) -> PerspectivaInvite:
    inv = (await db.execute(
        select(PerspectivaInvite).where(PerspectivaInvite.token == token)
    )).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada o expirada.")
    return inv


@router.get("/perspectiva/{token}")
async def get_perspectiva(token: str, db: AsyncSession = Depends(get_db)):
    inv = await _get_invite_or_404(token, db)
    company_name = await _empresa_ctx_for(inv.owner_user_id, db)
    return {
        "role": inv.role,
        "company_name": company_name,
        "messages": inv.messages or [],
        "done": inv.status == "done",
    }


@router.post("/perspectiva/{token}/turn")
async def turn_perspectiva(token: str, body: PublicAnswerIn, db: AsyncSession = Depends(get_db)):
    inv = await _get_invite_or_404(token, db)
    if inv.status == "done":
        raise HTTPException(status_code=409, detail="Esta entrevista ya terminó. ¡Gracias!")
    company_ctx = await _empresa_ctx_for(inv.owner_user_id, db)
    messages = list(inv.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})
    turn = await anyio.to_thread.run_sync(
        lambda: run_perspectiva_turn(messages, inv.state or {}, inv.role, company_ctx))
    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    inv.messages = messages
    inv.state = turn["state"] or inv.state
    inv.status = "done" if turn["done"] else "active"
    flag_modified(inv, "messages")
    flag_modified(inv, "state")
    await db.commit()
    return {"message": turn["message"], "options": turn["options"],
            "input": turn["input"], "done": turn["done"]}
```

En `backend/app/main.py`: añade
`from app.api.v1.perspectivas.public import router as perspectivas_public_router`
y
`app.include_router(perspectivas_public_router, prefix="/api/v1", tags=["perspectivas-public"])`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_perspectivas_public_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/perspectivas/public.py backend/app/main.py backend/tests/integration/test_perspectivas_public_api.py
git commit -m "feat(perspectivas): entrevista pública por token (sin login)"
```

---

### Task 5: Agente de consolidación + Celery + endpoints de síntesis

**Files:**
- Create: `backend/app/services/ai/perspectivas/consolidar.py`
- Create: `backend/app/tasks/perspectivas_tasks.py`
- Modify: `backend/app/tasks/worker.py` (agregar al `include`)
- Modify: `backend/app/api/v1/perspectivas/router.py` (endpoints `consolidar` + `sintesis`)
- Test: `backend/tests/unit/test_perspectivas_consolidar.py`

**Interfaces:**
- Consumes: `PerspectivaInvite`, `DiagnosticoEstrategico`, `roles.ANONYMOUS_ROLES`, `_create_with_retry`.
- Produces: `consolidar.consolidar_perspectivas(owner_memory_buffer: dict, invites: list[dict]) -> dict` (retorna `{coincidencias, contradicciones, puntos_ciegos, por_rol, conteo}`); `consolidar._fallback(invites) -> dict`; task Celery `generate_perspectivas_task(user_id)`; endpoints `POST /perspectivas/consolidar` y `GET /perspectivas/sintesis`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_perspectivas_consolidar.py
from app.services.ai.perspectivas.consolidar import _fallback, consolidar_perspectivas


def test_fallback_agrega_por_rol_y_conteo():
    invites = [
        {"role": "empleado", "name": "Juan", "state": {"percepciones": ["faltan procesos"]},
         "messages": [{"role": "user", "text": "Faltan procesos claros"}]},
        {"role": "cliente", "name": None, "state": {},
         "messages": [{"role": "user", "text": "Buen servicio pero lento"}]},
    ]
    out = _fallback(invites)
    assert out["conteo"]["empleado"] == 1 and out["conteo"]["cliente"] == 1
    assert "empleado" in out["por_rol"] and "cliente" in out["por_rol"]
    # roles anónimos NO exponen el nombre
    assert "Juan" not in str(out)


def test_consolidar_sin_api_key_usa_fallback(monkeypatch):
    monkeypatch.setattr("app.services.ai.perspectivas.consolidar.settings.ANTHROPIC_API_KEY", "")
    out = consolidar_perspectivas({}, [{"role": "cliente", "name": None, "state": {},
                                        "messages": [{"role": "user", "text": "ok"}]}])
    assert set(out.keys()) >= {"coincidencias", "contradicciones", "puntos_ciegos", "por_rol", "conteo"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_consolidar.py -v`
Expected: FAIL con `ModuleNotFoundError: ...consolidar`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/ai/perspectivas/consolidar.py
"""Consolida las perspectivas de los invitados en coincidencias / contradicciones / puntos ciegos.
Opus tool-use, sin web. Respeta el anonimato por rol (empleado/cliente nunca por nombre)."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry
from app.services.ai.perspectivas import roles as roles_mod

CONSOLIDAR_TOOL = {
    "name": "consolidar_perspectivas",
    "description": "Sintetiza las perspectivas de varios invitados sobre una empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coincidencias": {"type": "array", "items": {"type": "string"},
                              "description": "Puntos donde las voces (incl. el dueño) coinciden."},
            "contradicciones": {"type": "array", "items": {"type": "string"},
                                "description": "Dónde chocan las percepciones (p. ej. el dueño cree X pero los clientes perciben Y)."},
            "puntos_ciegos": {"type": "array", "items": {"type": "string"},
                              "description": "Cosas que el dueño no mencionó y que otros sí ven."},
            "por_rol": {"type": "object",
                        "description": "Resumen agregado por rol. Para empleado/cliente NUNCA uses nombres."},
        },
        "required": ["coincidencias", "contradicciones", "puntos_ciegos", "por_rol"],
    },
}

_SYSTEM = (
    "Eres Todd, secretario del consejo de Gobernia. Recibes lo que el DUEÑO reportó y las "
    "perspectivas de varias personas (por rol). Sintetiza en español: coincidencias, contradicciones "
    "(lo más valioso: dónde el dueño y los demás perciben distinto) y puntos ciegos del dueño. "
    "REGLA DE ANONIMATO: para roles 'empleado' y 'cliente' habla SIEMPRE en agregado ('los empleados…', "
    "'2 de 3 clientes…') y NUNCA uses nombres; para 'directivo', 'socio' y 'proveedor' puedes atribuir."
)


def _conteo(invites: list[dict]) -> dict:
    out: dict[str, int] = {}
    for inv in invites:
        out[inv.get("role", "?")] = out.get(inv.get("role", "?"), 0) + 1
    return out


def _fallback(invites: list[dict]) -> dict:
    por_rol: dict[str, list[str]] = {}
    for inv in invites:
        role = inv.get("role", "?")
        textos = [m.get("text", "") for m in (inv.get("messages") or []) if m.get("role") == "user"]
        por_rol.setdefault(role, []).extend([t for t in textos if t.strip()])
    return {
        "coincidencias": [], "contradicciones": [], "puntos_ciegos": [],
        "por_rol": {r: " · ".join(v)[:800] for r, v in por_rol.items()},
        "conteo": _conteo(invites),
    }


def _invites_prompt(invites: list[dict]) -> str:
    partes = []
    for inv in invites:
        role = inv.get("role", "?")
        anon = role in roles_mod.ANONYMOUS_ROLES
        etiqueta = roles_mod.ROLE_LABEL.get(role, role)
        quien = etiqueta if anon or not inv.get("name") else f"{etiqueta} ({inv['name']})"
        textos = [m.get("text", "") for m in (inv.get("messages") or []) if m.get("role") == "user"]
        partes.append(f"[{quien}] " + " | ".join(t for t in textos if t.strip()))
    return "\n".join(partes)


def consolidar_perspectivas(owner_memory_buffer: dict, invites: list[dict]) -> dict:
    if not invites:
        return {"coincidencias": [], "contradicciones": [], "puntos_ciegos": [],
                "por_rol": {}, "conteo": {}}
    if not settings.ANTHROPIC_API_KEY:
        return _fallback(invites)
    hallazgos = (owner_memory_buffer or {}).get("hallazgos") or {}
    user = (
        "LO QUE REPORTÓ EL DUEÑO (hallazgos internos):\n"
        + json.dumps(hallazgos, ensure_ascii=False)[:2000] + "\n\n"
        "PERSPECTIVAS DE LOS INVITADOS (por rol):\n" + _invites_prompt(invites) + "\n\n"
        "Sintetiza en el JSON indicado, respetando el anonimato por rol."
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=2048,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[CONSOLIDAR_TOOL], tool_choice={"type": "tool", "name": "consolidar_perspectivas"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        data = dict(block.input) if block and isinstance(block.input, dict) else {}
        return {
            "coincidencias": [str(x) for x in (data.get("coincidencias") or [])],
            "contradicciones": [str(x) for x in (data.get("contradicciones") or [])],
            "puntos_ciegos": [str(x) for x in (data.get("puntos_ciegos") or [])],
            "por_rol": data.get("por_rol") or {},
            "conteo": _conteo(invites),
        }
    except Exception:
        return _fallback(invites)
```

```python
# backend/app/tasks/perspectivas_tasks.py
"""Task de Celery de consolidación de perspectivas (espejo de foda_tasks). Sin web."""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.tasks.worker import celery_app
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.models.perspectiva_invite import PerspectivaInvite
from app.services.ai.perspectivas.consolidar import consolidar_perspectivas


@celery_app.task(name="generate_perspectivas", bind=True, max_retries=1)
def generate_perspectivas_task(self, user_id: str) -> dict:
    try:
        return asyncio.run(_run(user_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


async def _run(user_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
            .order_by(DiagnosticoEstrategico.created_at.desc())
        )).scalars().first()
        if diag is None:
            return {"status": "skipped"}
        onb = (await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc())
        )).scalars().first()
        mb = (onb.memory_buffer if onb else {}) or {}
        rows = (await db.execute(
            select(PerspectivaInvite).where(
                PerspectivaInvite.owner_user_id == user_id, PerspectivaInvite.status == "done")
        )).scalars().all()
        invites = [{"role": r.role, "name": r.invitee_name, "state": r.state or {},
                    "messages": r.messages or []} for r in rows]
        content = dict(diag.content or {})
        try:
            sintesis = await asyncio.to_thread(consolidar_perspectivas, mb, invites)
            sintesis["status"] = "active"
            content["perspectivas"] = sintesis
        except Exception:
            content["perspectivas"] = {"status": "failed"}
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"status": "active", "user_id": user_id}
```

En `backend/app/tasks/worker.py`, agrega `"app.tasks.perspectivas_tasks"` a la lista `include`.

En `backend/app/api/v1/perspectivas/router.py` añade al final:

```python
from app.models.diagnostico_estrategico import DiagnosticoEstrategico  # (añade este import arriba con los demás)
from sqlalchemy.orm.attributes import flag_modified  # (añade arriba)


@router.post("/perspectivas/consolidar")
async def consolidar(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="Genera tu diagnóstico antes de consolidar.")
    content = dict(diag.content or {})
    content["perspectivas"] = {**(content.get("perspectivas") or {}), "status": "generating"}
    diag.content = content
    flag_modified(diag, "content")
    await db.commit()
    try:
        from app.tasks.perspectivas_tasks import generate_perspectivas_task
        generate_perspectivas_task.delay(user_id)
    except Exception:
        content["perspectivas"]["status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"ok": True}


@router.get("/perspectivas/sintesis")
async def get_sintesis(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    p = ((diag.content if diag else {}) or {}).get("perspectivas") or {}
    return {"status": p.get("status") or "none",
            "coincidencias": p.get("coincidencias") or [],
            "contradicciones": p.get("contradicciones") or [],
            "puntos_ciegos": p.get("puntos_ciegos") or [],
            "por_rol": p.get("por_rol") or {},
            "conteo": p.get("conteo") or {}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_consolidar.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/perspectivas/consolidar.py backend/app/tasks/perspectivas_tasks.py backend/app/tasks/worker.py backend/app/api/v1/perspectivas/router.py backend/tests/unit/test_perspectivas_consolidar.py
git commit -m "feat(perspectivas): consolidación (síntesis) + Celery + endpoints"
```

---

### Task 6: Inyectar la síntesis de perspectivas al FODA y al plan

**Files:**
- Modify: `backend/app/services/ai/foda.py` (`generate_foda` recibe/usa `perspectivas`)
- Modify: `backend/app/services/ai/foda_into_plan.py` (`augment_buffer_with_foda` agrega perspectivas al narrative)
- Modify: `backend/app/tasks/foda_tasks.py` (pasa `content.get("perspectivas")` a `generate_foda`)
- Test: `backend/tests/unit/test_perspectivas_en_foda.py`

**Interfaces:**
- Consumes: `content["perspectivas"]` (Task 5).
- Produces: `generate_foda(memory_buffer, diagnostico_content, factores_externos, metas_orden, perspectivas=None)` (nuevo parámetro opcional al final, retrocompatible).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_perspectivas_en_foda.py
from app.services.ai.foda_into_plan import augment_buffer_with_foda


def test_augment_incluye_perspectivas_en_narrative():
    mb = {"ai_context": {"company_narrative": "Base."}}
    foda = {"fortalezas": ["x"], "debilidades": [], "oportunidades": [], "amenazas": [], "sintesis": "s"}
    persp = {"contradicciones": ["El dueño cree X, los clientes perciben Y"],
             "puntos_ciegos": ["Falta seguimiento a clientes"]}
    out = augment_buffer_with_foda(mb, foda, ["Crecer"], perspectivas=persp)
    narr = out["ai_context"]["company_narrative"]
    assert "clientes perciben Y" in narr
    assert "Falta seguimiento a clientes" in narr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_en_foda.py -v`
Expected: FAIL (`augment_buffer_with_foda` no acepta `perspectivas` / no lo inyecta).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/services/ai/foda_into_plan.py`, cambia la firma de `augment_buffer_with_foda` para aceptar `perspectivas: dict | None = None` (parámetro final) y, dentro (donde arma el texto que concatena al `company_narrative`), añade antes de escribir el narrative:

```python
    persp = perspectivas or {}
    persp_lineas = []
    for etiqueta, clave in (("Contradicciones", "contradicciones"),
                            ("Puntos ciegos", "puntos_ciegos"),
                            ("Coincidencias", "coincidencias")):
        items = [str(x) for x in (persp.get(clave) or []) if str(x).strip()]
        if items:
            persp_lineas.append(f"{etiqueta}: " + "; ".join(items))
    bloque_persp = ("\n\nPERSPECTIVAS DE OTRAS VOCES (empleados, clientes, directivos):\n"
                    + "\n".join(persp_lineas)) if persp_lineas else ""
```

y concaténa `bloque_persp` al final del narrative que ya construye la función (junto al bloque del FODA).

En `backend/app/services/ai/foda.py`, cambia la firma de `generate_foda` a:

```python
def generate_foda(memory_buffer: dict, diagnostico_content: dict,
                  factores_externos: dict, metas_orden: list, perspectivas: dict | None = None):
```

y en el `user` prompt que construye, añade (si hay perspectivas):

```python
    persp = perspectivas or {}
    if any(persp.get(k) for k in ("contradicciones", "puntos_ciegos", "coincidencias")):
        user += ("\n\nPERSPECTIVAS DE OTRAS VOCES:\n" + json.dumps(
            {k: persp.get(k) for k in ("coincidencias", "contradicciones", "puntos_ciegos")},
            ensure_ascii=False)[:1500])
```

(asegúrate de que `import json` esté presente en `foda.py`; si no, añádelo).

En `backend/app/tasks/foda_tasks.py`, en la llamada a `generate_foda`, pasa las perspectivas:

```python
            foda = await asyncio.to_thread(
                generate_foda, memory_buffer, content,
                content.get("factores_externos") or {}, content.get("metas_orden") or [],
                content.get("perspectivas") or {})
```

Donde el generador del plan llame a `augment_buffer_with_foda` (buscar con `grep -rn "augment_buffer_with_foda" backend/app`), pásale también `content.get("perspectivas")` como argumento `perspectivas=`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_perspectivas_en_foda.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run full backend suite + commit**

Run: `cd backend && venv/bin/python -m pytest -q` → Expected: all passed.

```bash
git add backend/app/services/ai/foda.py backend/app/services/ai/foda_into_plan.py backend/app/tasks/foda_tasks.py backend/tests/unit/test_perspectivas_en_foda.py
git commit -m "feat(perspectivas): la síntesis alimenta el FODA y el plan"
```

---

### Task 7: Frontend — librería de API de perspectivas

**Files:**
- Create: `frontend/src/lib/perspectivas.ts`

**Interfaces:**
- Consumes: `@/lib/api` (baseURL con `/api/v1`).
- Produces: tipos `Invite`, `PublicPerspectiva`, `PerspectivaTurn`, `Sintesis`, `ROLE_LABEL`; funciones `createInvite`, `listInvites`, `revokeInvite`, `consolidarPerspectivas`, `getSintesis`, `getPerspectiva`, `answerPerspectiva`.

- [ ] **Step 1: Write the implementation**

```typescript
// frontend/src/lib/perspectivas.ts
import api from "@/lib/api"

export type Role = "empleado" | "directivo" | "socio" | "cliente" | "proveedor"

export const ROLE_LABEL: Record<Role, string> = {
  empleado: "Empleado clave", directivo: "Directivo", socio: "Socio",
  cliente: "Cliente", proveedor: "Proveedor / aliado",
}
export const ANONYMOUS_ROLES: Role[] = ["empleado", "cliente"]

export interface Invite {
  id: string; role: Role; invitee_name: string | null
  token: string; url?: string; status: "pending" | "active" | "done"; created_at: string
}

export interface PublicPerspectiva {
  role: Role; company_name: string
  messages: { role: "todd" | "user"; text: string; options: string[] | null }[]
  done: boolean
}
export interface PerspectivaTurn {
  message: string; options: string[] | null; input: "text" | "single_choice"; done: boolean
}

export interface Sintesis {
  status: "none" | "generating" | "active" | "failed"
  coincidencias: string[]; contradicciones: string[]; puntos_ciegos: string[]
  por_rol: Record<string, string>; conteo: Record<string, number>
}

export async function createInvite(role: Role, name?: string): Promise<Invite> {
  const r = await api.post<Invite>("/perspectivas/invite", { role, name: name || null })
  return r.data
}
export async function listInvites(): Promise<Invite[]> {
  const r = await api.get<Invite[]>("/perspectivas")
  return r.data
}
export async function revokeInvite(id: string): Promise<void> {
  await api.delete(`/perspectivas/${id}`)
}
export async function consolidarPerspectivas(): Promise<void> {
  await api.post("/perspectivas/consolidar")
}
export async function getSintesis(): Promise<Sintesis> {
  const r = await api.get<Sintesis>("/perspectivas/sintesis")
  return r.data
}
export async function getPerspectiva(token: string): Promise<PublicPerspectiva> {
  const r = await api.get<PublicPerspectiva>(`/perspectiva/${token}`)
  return r.data
}
export async function answerPerspectiva(token: string, answer: string | null): Promise<PerspectivaTurn> {
  const r = await api.post<PerspectivaTurn>(`/perspectiva/${token}/turn`, { answer })
  return r.data
}
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint src/lib/perspectivas.ts`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/perspectivas.ts
git commit -m "feat(perspectivas-fe): librería de API"
```

---

### Task 8: Frontend — página del dueño `/dashboard/perspectivas` + ítem en Sidebar

**Files:**
- Create: `frontend/src/app/dashboard/perspectivas/page.tsx`
- Modify: `frontend/src/components/ui/Sidebar.tsx` (agregar ítem "Perspectivas")

**Interfaces:**
- Consumes: `@/lib/perspectivas` (Task 7).

- [ ] **Step 1: Write the implementation**

Crea `frontend/src/app/dashboard/perspectivas/page.tsx`: página que
1. Al montar, `listInvites()` y `getSintesis()`.
2. Formulario para crear invitación: `<select>` de rol (usa `ROLE_LABEL`), input de nombre (solo visible/relevante si el rol NO está en `ANONYMOUS_ROLES`), botón "Crear link" → `createInvite(role, name)` → agrega a la lista y muestra el link con botón "Copiar" (usa `navigator.clipboard.writeText(location.origin + invite.url)` con fallback a `/p/{token}`).
3. Lista de invitaciones con su rol (`ROLE_LABEL`), estado (pendiente/activo/respondió), botón copiar link y botón revocar (`revokeInvite`).
4. Botón "Consolidar perspectivas" → `consolidarPerspectivas()` + polling de `getSintesis()` cada 3s mientras `status === "generating"`.
5. Vista de síntesis cuando `status === "active"`: secciones **Coincidencias**, **Contradicciones** (destacadas en rojo), **Puntos ciegos**, y **Por rol** (mapa `por_rol`), con el estilo de marca (tokens `--gob-*`, tarjetas `rounded-2xl border border-gray-100`). Header sticky como en `dashboard/foda/page.tsx`.

Sigue el patrón visual de `frontend/src/app/dashboard/foda/page.tsx` (header, tokens, tarjetas). Usa `import { motion } from "framer-motion"` para animaciones suaves e iconos de `lucide-react` (`Users`, `Copy`, `Trash2`, `Loader2`, `Link2`, `ArrowRight`).

En `frontend/src/components/ui/Sidebar.tsx`, agrega al array `LINKS` (después de "FODA", antes de "Plan") importando `Users` de lucide (o `MessagesSquare`):

```tsx
  { href: "/dashboard/perspectivas", label: "Perspectivas", exact: false, icon: Users },
```

(asegúrate de importar el icono elegido en el bloque de imports de lucide del Sidebar).

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint src/app/dashboard/perspectivas/page.tsx src/components/ui/Sidebar.tsx`
Expected: sin errores. (Si aparece `react-hooks/set-state-in-effect` por leer datos en el efecto de montaje, añade `// eslint-disable-next-line react-hooks/set-state-in-effect` como en `dashboard/diagnostico/page.tsx`.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/perspectivas/page.tsx frontend/src/components/ui/Sidebar.tsx
git commit -m "feat(perspectivas-fe): página del dueño (invitar + consolidar + síntesis)"
```

---

### Task 9: Frontend — página pública del invitado `/p/[token]`

**Files:**
- Create: `frontend/src/app/p/[token]/page.tsx`

**Interfaces:**
- Consumes: `@/lib/perspectivas` (Task 7: `getPerspectiva`, `answerPerspectiva`, `ROLE_LABEL`).

- [ ] **Step 1: Write the implementation**

Crea `frontend/src/app/p/[token]/page.tsx` — página pública (fuera del layout del dashboard, sin login) que reutiliza el estilo del wizard de Todd (`frontend/src/app/onboarding/todd/page.tsx`), sin el store ni las áreas:
1. Obtiene el `token` de los params (Next 16: `params` es una Promise; usa `use(params)` o `useParams()` del cliente — revisa el patrón vigente en `node_modules/next/dist/docs/` antes de escribir).
2. Al montar: `getPerspectiva(token)`. Si 404 → estado "Este link no es válido o ya expiró.". Si `done` → pantalla de agradecimiento.
3. Header con `GoberniaLogo` (`import GoberniaLogo from "@/components/ui/GoberniaLogo"`) + etiqueta "Perspectiva".
4. Encuadre: "Te invitaron a compartir tu perspectiva sobre {company_name}. Toma 2–3 minutos y es confidencial."
5. Turno actual (tarjeta con avatar "T" + pregunta) + `options` como botones (single_choice) o `textarea` (text). Al responder → `answerPerspectiva(token, value)` → aplica el turno. Muestra "Procesando…" mientras.
6. Al `done` → pantalla "¡Gracias! Tu perspectiva ayudará a mejorar la empresa." (sin CTA de login).

Reutiliza literalmente la estructura de tarjeta/controles de `onboarding/todd/page.tsx` (avatar T, botones de opción, textarea + botón Continuar), adaptada a los tipos `PublicPerspectiva`/`PerspectivaTurn`.

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint src/app/p/[token]/page.tsx`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/p/
git commit -m "feat(perspectivas-fe): página pública del invitado /p/[token]"
```

---

## Despliegue (después de completar y con autorización del usuario)

1. `cd backend && venv/bin/python -m pytest -q` → todo verde.
2. Correr en prod (con autorización humana): `venv/bin/python -m scripts.create_perspectiva_invites`.
3. Push a **ambos remotos**: `git push origin main && git push cbeuvrin main`.
4. Verificar redeploy de Vercel (web) y Railway (worker: la tarea `generate_perspectivas` debe estar en el `include`).

## Self-Review (hecho por el autor del plan)

- **Cobertura del spec:** modelo/tabla (T1) ✓, entrevista por rol (T2) ✓, invitar/listar/revocar (T3) ✓, entrevista pública por token (T4) ✓, consolidación + anonimato + Celery + endpoints (T5) ✓, inyección a FODA/plan (T6) ✓, vista del dueño (T8) ✓, página pública (T9) ✓, librería FE (T7) ✓. Anonimato por rol implementado en `_invites_prompt`/`_SYSTEM` y `ANONYMOUS_ROLES`. Despliegue con script `create_all` + dual-remote documentado.
- **Consistencia de tipos:** `run_perspectiva_turn(messages, state, role, empresa_ctx)` usado igual en T4. `consolidar_perspectivas(owner_memory_buffer, invites)` con `invites` = list de `{role, name, state, messages}` producido igual en T5 (task) y consumido en el fallback/prompt. `generate_foda(..., perspectivas=None)` firma nueva usada en T6 (foda_tasks). `augment_buffer_with_foda(..., perspectivas=None)`. Endpoints FE (`/perspectivas`, `/perspectiva/{token}`) sin doble `/api/v1`. `Sintesis`/`Invite` FE calzan con las respuestas de T3/T5.
- **Sin placeholders** en tareas con código completo (T1–T7). T8 y T9 son UI descriptiva que sigue patrones existentes citados por archivo (foda/todd pages) — se apoyan en componentes y estilos ya presentes; el implementador tiene los tipos exactos (T7) y las páginas de referencia.
