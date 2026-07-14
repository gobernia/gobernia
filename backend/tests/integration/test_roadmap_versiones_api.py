"""Versionado del Roadmap: validar archiva un snapshot inmutable; reabrir NO lo borra.
La Biblioteca lista todas las versiones y su PDF sale de SU snapshot, no del roadmap actual.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user_id, get_db
from app.main import app
from app.models.roadmap_version import RoadmapVersion

USER = "user-123"


def _user():
    return USER


def _db_override(db):
    async def _dep():
        yield db
    return _dep


def _plan(roadmap: dict, status: str = "borrador"):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.roadmap = roadmap
    p.roadmap_status = status
    p.roadmap_validated_at = None
    return p


def _res(scalar_one_or_none=None, scalars_all=None, scalars_first=None, scalar=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar_one_or_none
    r.scalar.return_value = scalar
    r.scalars.return_value.all.return_value = scalars_all or []
    r.scalars.return_value.first.return_value = scalars_first
    return r


def _version(version: int, roadmap: dict, vid=None, validated_at=None):
    v = MagicMock()
    v.id = vid or uuid.uuid4()
    v.version = version
    v.roadmap = roadmap
    v.validated_at = validated_at or datetime(2026, 7, 14, tzinfo=timezone.utc)
    return v


async def _call(db, method: str, path: str):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await getattr(c, method)(path)
    finally:
        app.dependency_overrides.clear()


async def _validar(plan, max_version: int | None):
    """Corre POST /roadmap/validar y devuelve la RoadmapVersion que se archivó."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _res(scalar_one_or_none=plan),   # plan actual
        _res(scalars_all=[]),            # BoardTheme del roadmap
        _res(scalar=max_version),        # max(version) archivada
    ])
    r = await _call(db, "post", "/api/v1/annual-plan/roadmap/validar")
    assert r.status_code == 200, r.text
    archivadas = [a.args[0] for a in db.add.call_args_list if isinstance(a.args[0], RoadmapVersion)]
    assert len(archivadas) == 1
    return r.json(), archivadas[0]


@pytest.mark.asyncio
async def test_validar_archiva_la_v1():
    plan = _plan({"vision": "V1", "pilares": [{"nombre": "Comercial"}]})
    estado, v1 = await _validar(plan, max_version=None)

    assert estado["status"] == "validado"
    assert estado["version_actual"] == 1
    assert v1.version == 1
    assert v1.user_id == USER
    assert v1.plan_id == plan.id
    assert v1.roadmap == {"vision": "V1", "pilares": [{"nombre": "Comercial"}]}
    assert v1.validated_at is not None
    assert plan.roadmap_status == "validado"


@pytest.mark.asyncio
async def test_reabrir_editar_y_revalidar_crea_la_v2_sin_tocar_la_v1():
    plan = _plan({"vision": "V1", "pilares": [{"nombre": "Comercial"}]})
    _estado1, v1 = await _validar(plan, max_version=None)
    original = {"vision": "V1", "pilares": [{"nombre": "Comercial"}]}

    # Reabrir + editar el roadmap (incluso mutando el dict en sitio).
    plan.roadmap_status = "borrador"
    plan.roadmap["vision"] = "V2"
    plan.roadmap["pilares"][0]["nombre"] = "Operaciones"

    estado2, v2 = await _validar(plan, max_version=1)

    assert estado2["version_actual"] == 2
    assert v2.version == 2
    assert v2.roadmap == {"vision": "V2", "pilares": [{"nombre": "Operaciones"}]}
    # La v1 es un snapshot inmutable: sigue igual que el día que se validó.
    assert v1.roadmap == original


@pytest.mark.asyncio
async def test_listar_versiones_mas_reciente_primero():
    v2 = _version(2, {"vision": "V2"})
    v1 = _version(1, {"vision": "V1"})
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_res(scalars_all=[v2, v1]))  # el ORDER BY lo hace el query
    r = await _call(db, "get", "/api/v1/annual-plan/roadmap/versiones")

    assert r.status_code == 200
    body = r.json()
    assert [i["version"] for i in body] == [2, 1]
    assert body[0]["id"] == str(v2.id)
    assert body[0]["validated_at"] is not None


@pytest.mark.asyncio
async def test_pdf_de_una_version_usa_su_snapshot(monkeypatch):
    from app.services.pdf import roadmap_pdf as pdf_mod

    capturado = {}

    def _fake_build(roadmap, company_name=None, logo=None):
        capturado["roadmap"] = roadmap
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(pdf_mod, "build_roadmap_pdf", _fake_build)

    v1 = _version(1, {"vision": "V1 (archivada)"})
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _res(scalar_one_or_none=v1),      # la versión
        _res(scalars_first=None),         # onboarding (sin company_name)
        _res(scalar_one_or_none=None),    # logo
    ])
    r = await _call(db, "get", f"/api/v1/annual-plan/roadmap/versiones/{v1.id}/pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "roadmap-v1.pdf" in r.headers["content-disposition"]
    # El PDF se construyó con el snapshot archivado, no con el roadmap actual del plan.
    assert capturado["roadmap"] == {"vision": "V1 (archivada)"}


@pytest.mark.asyncio
async def test_biblioteca_lista_todas_las_versiones():
    v2 = _version(2, {"vision": "V2"})
    v1 = _version(1, {"vision": "V1"})
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_res(scalars_all=[v2, v1]))
    r = await _call(db, "get", "/api/v1/biblioteca")

    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["version"] == 2
    assert items[0]["titulo"] == "Roadmap Estratégico — v2"
    assert items[0]["pdf_path"] == f"/annual-plan/roadmap/versiones/{v2.id}/pdf"
    assert items[1]["version"] == 1
    assert items[1]["pdf_path"] == f"/annual-plan/roadmap/versiones/{v1.id}/pdf"
    assert all(i["tipo"] == "roadmap" for i in items)


@pytest.mark.asyncio
async def test_biblioteca_retrocompat_plan_validado_sin_versiones():
    """Datos previos al versionado: validado pero sin snapshot → se muestra el roadmap actual."""
    plan = _plan({"vision": "V"}, status="validado")
    plan.roadmap_validated_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _res(scalars_all=[]),             # no hay versiones archivadas
        _res(scalar_one_or_none=plan),    # el plan
    ])
    r = await _call(db, "get", "/api/v1/biblioteca")

    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["tipo"] == "roadmap"
    assert items[0]["pdf_path"] == "/annual-plan/roadmap/pdf"


@pytest.mark.asyncio
async def test_biblioteca_vacia_si_no_hay_nada_validado():
    plan = _plan({"vision": "V"}, status="borrador")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _res(scalars_all=[]),
        _res(scalar_one_or_none=plan),
    ])
    r = await _call(db, "get", "/api/v1/biblioteca")

    assert r.status_code == 200
    assert r.json()["items"] == []
