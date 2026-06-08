# Bloque B3 — Acuerdos + Evidencias · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir subir evidencia a un acuerdo (tarea) y gobernar el cierre por evidencia: no se puede marcar "Validado" (status `completada`) sin ≥1 evidencia.

**Architecture:** Nueva entidad `Evidence` ligada a `ActionTask` (reusa el storage existente). Router dedicado de evidencia (upload/list/delete). Un gate en `update_task` bloquea pasar a `completada` sin evidencia. Frontend: sección "Evidencia" en el `TaskDrawer` + guard del botón Validado.

**Tech Stack:** FastAPI (UploadFile/multipart), SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada con AsyncMock), Next.js 16 + TS, axios (FormData).

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b3-acuerdos-evidencias-design.md`

**Patrones existentes a seguir:**
- Subida: `app/api/v1/onboarding/etapa7.py` (`UploadFile`, `_validate_file`, `generate_storage_key`, `upload_to_storage`). Constantes en `app/schemas/etapa7.py`: `ALLOWED_EXTENSIONS`, `MAX_FILE_SIZE_BYTES`.
- Storage: `app/services/documents/storage.py` — `generate_storage_key(ns_id, doc_id, filename)`, `async upload_to_storage(content, key)` (degrada sin S3).
- Tarea/gate: `app/api/v1/action_plans/router.py` — `update_task` (PATCH `/tasks/{id}`), `_get_user_task_or_404`, `_task_to_out`. Modelo `ActionTask` en `app/models/action_plan.py`.
- `TimestampMixin.created_at` usa `server_default` (es `None` en construcción Python; se puebla en `db.refresh`). `UUIDMixin.id` usa `default=uuid.uuid4` (sí se setea en construcción).

---

### Task 1: Modelo `Evidence` + relación + script de tabla

**Files:**
- Create: `backend/app/models/evidence.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/action_plan.py` (relación `ActionTask.evidences`)
- Create: `backend/scripts/create_evidences.py`
- Test: `backend/tests/unit/test_evidence_model.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_evidence_model.py`:

```python
from app.models import Base
from app.models.evidence import Evidence
from app.models.action_plan import ActionTask


def test_evidences_table_registered():
    table = Base.metadata.tables.get("evidences")
    assert table is not None
    cols = set(table.columns.keys())
    assert {"id", "action_task_id", "filename", "s3_key",
            "content_type", "size_bytes", "created_at"} <= cols


def test_action_task_has_evidences_relationship():
    assert hasattr(ActionTask, "evidences")


def test_evidence_instantiable():
    e = Evidence(action_task_id=None, filename="a.pdf", s3_key="k",
                 content_type="application/pdf", size_bytes=10)
    assert e.filename == "a.pdf"
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_evidence_model.py -v`

- [ ] **Step 3: Create the model** `backend/app/models/evidence.py`:

```python
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Evidence(Base, UUIDMixin, TimestampMixin):
    """Evidencia que respalda un acuerdo (ActionTask). Archivo en storage."""
    __tablename__ = "evidences"

    action_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename:     Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key:       Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes:   Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 4: Add the relationship to `ActionTask`.** In `backend/app/models/action_plan.py`, add `relationship` to the imports if missing (`from sqlalchemy.orm import Mapped, mapped_column, relationship`) and add this attribute inside the `ActionTask` class (after `order_index`):

```python
    evidences: Mapped[list["Evidence"]] = relationship(
        "Evidence", cascade="all, delete-orphan", order_by="Evidence.created_at",
    )
```

- [ ] **Step 5: Register the model.** In `backend/app/models/__init__.py`, add `from app.models.evidence import Evidence` and add `"Evidence"` to `__all__`.

- [ ] **Step 6: Create the table-creation script** `backend/scripts/create_evidences.py`:

```python
"""Crea la tabla evidences SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_evidences
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: tabla evidences creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 7: Run the test, verify it PASSES** (3 passed):
`cd backend && venv/bin/python -m pytest tests/unit/test_evidence_model.py -v`

- [ ] **Step 8: Commit:**
```bash
git add backend/app/models/evidence.py backend/app/models/__init__.py backend/app/models/action_plan.py backend/scripts/create_evidences.py backend/tests/unit/test_evidence_model.py
git commit -m "feat(b3): modelo Evidence + relación ActionTask.evidences + script"
```

---

### Task 2: Esquema + router de evidencia (upload/list/delete)

**Files:**
- Create: `backend/app/schemas/evidence.py`
- Create: `backend/app/api/v1/evidence/__init__.py` (vacío)
- Create: `backend/app/api/v1/evidence/router.py`
- Modify: `backend/app/main.py` (registrar el router)
- Test: `backend/tests/integration/test_evidence_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_evidence_api.py`:

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_evidence"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(status="pendiente"):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.status = status
    return t


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_upload_evidence_creates_and_advances_status(monkeypatch):
    task = _task(status="pendiente")

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: setattr(o, "created_at", NOW))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/tasks/{task.id}/evidence",
                files={"file": ("acta.pdf", b"%PDF-1.4 data", "application/pdf")},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["filename"] == "acta.pdf"
    assert db.add.called
    assert task.status == "en_progreso"  # pendiente -> en_progreso al subir evidencia


@pytest.mark.asyncio
async def test_upload_evidence_rejects_bad_extension(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    db = AsyncMock()
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/tasks/{task.id}/evidence",
                files={"file": ("malo.exe", b"x", "application/octet-stream")},
            )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_evidence(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)

    ev = MagicMock()
    ev.id = uuid.uuid4(); ev.action_task_id = task.id; ev.filename = "x.pdf"
    ev.content_type = "application/pdf"; ev.size_bytes = 5; ev.created_at = NOW

    result = MagicMock()
    result.scalars.return_value.all.return_value = [ev]
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/tasks/{task.id}/evidence")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["filename"] == "x.pdf"
```

- [ ] **Step 2: Run it, verify it FAILS** (router/schema don't exist):
`cd backend && venv/bin/python -m pytest tests/integration/test_evidence_api.py -v`

- [ ] **Step 3: Create the schema** `backend/app/schemas/evidence.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class EvidenceOut(BaseModel):
    id: str
    action_task_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
```

- [ ] **Step 4: Create the package init** `backend/app/api/v1/evidence/__init__.py` (empty file).

- [ ] **Step 5: Create the router** `backend/app/api/v1/evidence/router.py`:

```python
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceOut
from app.schemas.etapa7 import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES
from app.services.documents.storage import generate_storage_key, upload_to_storage
from app.api.v1.action_plans.router import _get_user_task_or_404

router = APIRouter()


def _validate_file(filename: str, content: bytes) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido '{ext}'. Permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo supera el tamaño máximo de 10 MB.",
        )


def _evidence_out(e: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=str(e.id), action_task_id=str(e.action_task_id), filename=e.filename,
        content_type=e.content_type, size_bytes=e.size_bytes, created_at=e.created_at,
    )


@router.post("/tasks/{task_id}/evidence", response_model=EvidenceOut)
async def upload_evidence(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task_or_404(task_id, user_id, db)
    content = await file.read()
    _validate_file(file.filename or "", content)

    ev_id = uuid.uuid4()
    filename = file.filename or f"evidence_{ev_id}"
    s3_key = generate_storage_key(task_id, ev_id, filename)
    await upload_to_storage(content, s3_key)

    ev = Evidence(
        id=ev_id, action_task_id=task_id, filename=filename, s3_key=s3_key,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    db.add(ev)
    if task.status == "pendiente":
        task.status = "en_progreso"
    await db.flush()
    await db.commit()
    await db.refresh(ev)
    return _evidence_out(ev)


@router.get("/tasks/{task_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    task_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_task_or_404(task_id, user_id, db)
    res = await db.execute(
        select(Evidence).where(Evidence.action_task_id == task_id).order_by(Evidence.created_at)
    )
    return [_evidence_out(e) for e in res.scalars().all()]


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    await _get_user_task_or_404(ev.action_task_id, user_id, db)  # autoriza vía la tarea
    await db.delete(ev)
    await db.commit()
```

- [ ] **Step 6: Register the router in `backend/app/main.py`.** Add the import near the other router imports and include it with the others (after the annual_plan line):

```python
from app.api.v1.evidence.router import router as evidence_router
```
```python
app.include_router(evidence_router, prefix="/api/v1", tags=["evidence"])
```

- [ ] **Step 7: Run the test, verify it PASSES** (3 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_evidence_api.py -v`

- [ ] **Step 8: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 9: Commit:**
```bash
git add backend/app/schemas/evidence.py backend/app/api/v1/evidence/ backend/app/main.py backend/tests/integration/test_evidence_api.py
git commit -m "feat(b3): router de evidencia (upload/list/delete) + registro"
```

---

### Task 3: Gate de cierre en `update_task`

**Files:**
- Modify: `backend/app/api/v1/action_plans/router.py` (`update_task` + imports)
- Test: `backend/tests/integration/test_evidence_gate.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_evidence_gate.py`:

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.action_plan import ActionTask
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_gate"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(status="en_progreso"):
    return ActionTask(
        id=uuid.uuid4(), plan_id=uuid.uuid4(), title="Acuerdo",
        status=status, priority="media", order_index=0,
    )


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_validar_sin_evidencia_409(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    result = MagicMock(); result.scalar.return_value = 0  # 0 evidencias
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "completada"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_validar_con_evidencia_200(monkeypatch):
    task = _task()

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    result = MagicMock(); result.scalar.return_value = 1  # 1 evidencia
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock(); db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: (setattr(o, "created_at", NOW), setattr(o, "updated_at", NOW)))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "completada"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["status"] == "completada"
    assert task.status == "completada"


@pytest.mark.asyncio
async def test_cambio_no_validar_no_bloquea(monkeypatch):
    task = _task(status="pendiente")

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)

    db = AsyncMock(); db.execute = AsyncMock()  # no debe consultar evidencias
    db.flush = AsyncMock(); db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda o: (setattr(o, "created_at", NOW), setattr(o, "updated_at", NOW)))

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}", json={"status": "en_progreso"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    db.execute.assert_not_called()
```

- [ ] **Step 2: Run it, verify it FAILS** (no gate yet → 409 test gets 200):
`cd backend && venv/bin/python -m pytest tests/integration/test_evidence_gate.py -v`

- [ ] **Step 3: Add imports** to `backend/app/api/v1/action_plans/router.py`. Ensure `func` is imported from sqlalchemy (change `from sqlalchemy import select` to `from sqlalchemy import func, select`) and add `from app.models.evidence import Evidence`.

- [ ] **Step 4: Add the gate in `update_task`.** Replace the body of `update_task` so the gate runs before applying the payload:

```python
    task = await _get_user_task_or_404(task_id, user_id, db)

    payload = body.model_dump(exclude_unset=True)
    if payload.get("status") == "completada":
        count = await db.execute(
            select(func.count()).select_from(Evidence).where(Evidence.action_task_id == task.id)
        )
        if (count.scalar() or 0) == 0:
            raise HTTPException(
                status_code=409,
                detail="Se requiere al menos una evidencia para validar este acuerdo.",
            )

    for key, value in payload.items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()

    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_to_out(task)
```

- [ ] **Step 5: Run the test, verify it PASSES** (3 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_evidence_gate.py -v`

- [ ] **Step 6: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 7: Commit:**
```bash
git add backend/app/api/v1/action_plans/router.py backend/tests/integration/test_evidence_gate.py
git commit -m "feat(b3): gate de cierre — Validado exige >=1 evidencia (409)"
```

---

### Task 4: Frontend — evidencia en el TaskDrawer

**Files:**
- Create: `frontend/src/lib/evidence.ts`
- Create: `frontend/src/components/plan/EvidenceSection.tsx`
- Modify: `frontend/src/components/plan/TaskDrawer.tsx`

- [ ] **Step 1: Create the API lib** `frontend/src/lib/evidence.ts`:

```typescript
import api from "@/lib/api"

export interface Evidence {
  id: string
  action_task_id: string
  filename: string
  content_type: string
  size_bytes: number
  created_at: string
}

export async function getEvidence(taskId: string): Promise<Evidence[]> {
  const r = await api.get<Evidence[]>(`/tasks/${taskId}/evidence`)
  return r.data
}

export async function uploadEvidence(taskId: string, file: File): Promise<Evidence> {
  const form = new FormData()
  form.append("file", file)
  const r = await api.post<Evidence>(`/tasks/${taskId}/evidence`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return r.data
}

export async function deleteEvidence(evidenceId: string): Promise<void> {
  await api.delete(`/evidence/${evidenceId}`)
}
```

- [ ] **Step 2: Create the EvidenceSection component** `frontend/src/components/plan/EvidenceSection.tsx`:

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { Paperclip, Upload, X } from "lucide-react"
import { Evidence, getEvidence, uploadEvidence, deleteEvidence } from "@/lib/evidence"

export default function EvidenceSection({
  taskId, onCountChange,
}: { taskId: string; onCountChange?: (n: number) => void }) {
  const [items, setItems] = useState<Evidence[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const apply = (list: Evidence[]) => { setItems(list); onCountChange?.(list.length) }

  useEffect(() => {
    getEvidence(taskId).then(apply).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId])

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true); setError(null)
    try {
      const ev = await uploadEvidence(taskId, file)
      apply([...items, ev])
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo subir la evidencia.")
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  const onRemove = async (id: string) => {
    apply(items.filter(i => i.id !== id))
    await deleteEvidence(id).catch(() => getEvidence(taskId).then(apply))
  }

  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Evidencia</label>
      <div className="space-y-1.5">
        {items.map(e => (
          <div key={e.id} className="flex items-center gap-2 text-sm text-black bg-gray-50 rounded-lg px-3 py-2">
            <Paperclip className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            <span className="flex-1 truncate">{e.filename}</span>
            <button type="button" onClick={() => onRemove(e.id)} className="text-gray-300 hover:text-red-500">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-gray-400">Sin evidencia. Súbela para poder validar el acuerdo.</p>
        )}
      </div>
      <input ref={inputRef} type="file" className="hidden" onChange={onPick}
        accept=".pdf,.docx,.xlsx,.xls,.png,.jpg,.jpeg" />
      <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50">
        <Upload className="h-3.5 w-3.5" /> {busy ? "Subiendo…" : "Subir evidencia"}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
```

- [ ] **Step 3: Wire into TaskDrawer.** Read `frontend/src/components/plan/TaskDrawer.tsx`. It maps status options as buttons like `onClick={() => save({ status: s.id })}` (the option with `id === "completada"` is the "Validado" one). Make these changes:

  1. Add imports at the top:
  ```typescript
  import { useState } from "react"
  import EvidenceSection from "@/components/plan/EvidenceSection"
  ```
  (If `useState` is already imported, don't duplicate it.)

  2. Inside the component, add state near the other `useState` hooks:
  ```typescript
  const [evidenceCount, setEvidenceCount] = useState(0)
  const [statusError, setStatusError] = useState<string | null>(null)
  ```

  3. Add a guarded status handler (place it near the other handlers, before the `return`):
  ```typescript
  const onStatusClick = (s: string) => {
    if (s === "completada" && evidenceCount === 0) {
      setStatusError("Sube una evidencia para validar este acuerdo.")
      return
    }
    setStatusError(null)
    save({ status: s })
  }
  ```

  4. Change the status buttons' `onClick={() => save({ status: s.id })}` to `onClick={() => onStatusClick(s.id)}`.

  5. Render `statusError` right below the status buttons block (the `<div className="flex gap-1.5">` that holds them): add after it
  ```tsx
  {statusError && <p className="text-xs text-red-500">{statusError}</p>}
  ```

  6. Mount the evidence section inside the drawer body (the `<div className="p-6 space-y-6">` block), e.g. after the tags field:
  ```tsx
  <EvidenceSection taskId={task.id} onCountChange={setEvidenceCount} />
  ```

  7. **Relabel (acuerdos).** Find the status-options array in `TaskDrawer.tsx` (the one mapped to the status buttons, each item with `id` + `label`). Change the visible `label` (NOT the `id`) so the acuerdos vocabulary shows: `en_progreso` → "En proceso", `completada` → "Validado". Leave `pendiente`'s label as "Pendiente". Do not change any `id` value (the ids are the DB status values).

  Read the file to place these precisely. Keep the existing optimistic `save`/`onUpdate` flow intact — the guard only prevents the local `save({status:"completada"})` call when there's no evidence; if a 409 still arrives from the server it surfaces via the existing error handling (leave that as-is).

- [ ] **Step 4: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/evidence.ts src/components/plan/EvidenceSection.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 5: Commit:**
```bash
git add frontend/src/lib/evidence.ts frontend/src/components/plan/EvidenceSection.tsx frontend/src/components/plan/TaskDrawer.tsx
git commit -m "feat(b3): sección Evidencia en el TaskDrawer + guard de Validado"
```

---

## Done criteria

- Tabla `evidences` creada (script corrido en prod cuando se autorice); subir evidencia crea registro y pasa `pendiente`→`en_progreso`.
- `PATCH /tasks/{id}` con `status=completada` y 0 evidencias → 409.
- El dueño sube/ve/borra evidencia desde el drawer; el botón Validado se guarda sin evidencia.
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **created_at es server_default** → en los tests con db mockeada, `db.refresh` se mockea con un `side_effect` que setea `created_at` (y `updated_at` donde aplique). Ya está en los tests del plan.
- **El gate solo dispara con `status="completada"`** — usa `payload.get("status")` (el `exclude_unset=True` evita falsos positivos en cambios de otros campos).
- **Import cruzado:** `evidence/router.py` importa `_get_user_task_or_404` de `action_plans.router`. No hay ciclo (action_plans no importa evidence).
- **Despliegue (manual, autorizado):** tras desplegar, correr en Railway `python -m scripts.create_evidences`.
