# Capa de evidencias con S3 + Secretario lector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que las evidencias se descarguen/previsualicen en la UI y que el Secretario lea los PDFs/imágenes del mes al cerrar la sesión, validándolos contra la meta de cada tarea.

**Architecture:** Dos helpers nuevos en el storage (descarga de bytes + URL prefirmada, ambos no-op sin credenciales AWS); un endpoint protegido de descarga + link "Ver" en la UI; y `run_month_review` ampliado a multimodal (bloques `document`/`image`) alimentado desde `_run_close` con las evidencias legibles del mes (tope 8, solo PDF/imagen). Todo degrada al comportamiento actual cuando S3 no está configurado.

**Tech Stack:** FastAPI, SQLAlchemy async, boto3 (ya instalado), Anthropic SDK (bloques `document`/`image` base64, modelo `settings.AI_MODEL` = Sonnet 4.6). Next.js 16 App Router. Sin migración.

## Global Constraints

- **Sin migración de esquema** — no hay columnas nuevas; nada de Alembic ni scripts de DB.
- **Degradación sin S3 obligatoria** — sin `settings.AWS_ACCESS_KEY_ID`, todo helper devuelve `None` y el cierre se comporta como hoy (solo presencia). Los tests corren sin credenciales.
- **Solo PDF/PNG/JPG/JPEG se leen**; los demás formatos (Excel/Word) se anotan como nota de texto, no se descargan ni adjuntan.
- **Tope `_MAX_REVIEW_DOCS = 8`** documentos por cierre.
- **boto3 con lazy import** dentro de las funciones del storage (igual que `upload_to_storage`).
- **Frontend Next.js 16:** antes de tocar frontend, leer `node_modules/next/dist/docs/` si se usa cualquier API de Next; aquí el cambio es un componente cliente con `fetch` vía `@/lib/api`, sin APIs de Next nuevas.

---

### Task 1: Helpers de storage — descarga de bytes + URL prefirmada

**Files:**
- Modify: `backend/app/services/documents/storage.py`
- Test: `backend/tests/unit/test_storage_helpers.py` (crear)

**Interfaces:**
- Produces:
  - `download_from_storage(key: str) -> bytes | None` — bytes del objeto S3, o `None` sin credenciales / si falla.
  - `presigned_get_url(key: str, expires: int = 300) -> str | None` — URL GET prefirmada, o `None` sin credenciales / si falla.

- [ ] **Step 1: Escribir los tests**

`backend/tests/unit/test_storage_helpers.py`:

```python
import io
import app.services.documents.storage as storage


def test_download_sin_credenciales_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "")
    assert storage.download_from_storage("documents/x/y/z.pdf") is None


def test_presigned_sin_credenciales_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "")
    assert storage.presigned_get_url("documents/x/y/z.pdf") is None


def test_download_con_credenciales_lee_bytes(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _FakeS3:
        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(b"PDFBYTES")}

    monkeypatch.setattr(storage, "_s3_client", lambda: _FakeS3())
    assert storage.download_from_storage("documents/a/b/c.pdf") == b"PDFBYTES"


def test_presigned_con_credenciales_devuelve_url(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _FakeS3:
        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://signed/{Params['Key']}?e={ExpiresIn}"

    monkeypatch.setattr(storage, "_s3_client", lambda: _FakeS3())
    url = storage.presigned_get_url("documents/a/b/c.pdf", expires=120)
    assert url.startswith("https://signed/documents/a/b/c.pdf")


def test_download_traga_excepcion_y_devuelve_none(monkeypatch):
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "AKIA_fake")

    class _BoomS3:
        def get_object(self, Bucket, Key):
            raise RuntimeError("network down")

    monkeypatch.setattr(storage, "_s3_client", lambda: _BoomS3())
    assert storage.download_from_storage("documents/a/b/c.pdf") is None
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_storage_helpers.py -q`
Expected: FAIL (`_s3_client`, `download_from_storage`, `presigned_get_url` no existen).

- [ ] **Step 3: Implementar los helpers**

En `backend/app/services/documents/storage.py`, agregar al final (debajo de `upload_to_storage`):

```python
def _s3_client():
    import boto3  # lazy — no instalar en dev si no se usa S3
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def download_from_storage(key: str) -> bytes | None:
    """Descarga el objeto de S3. Sin credenciales o ante cualquier fallo → None (no rompe el cierre)."""
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    try:
        obj = _s3_client().get_object(Bucket=settings.S3_BUCKET_DOCUMENTS, Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def presigned_get_url(key: str, expires: int = 300) -> str | None:
    """URL GET prefirmada y temporal. Sin credenciales o ante fallo → None."""
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_DOCUMENTS, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return None
```

> Nota: `upload_to_storage` se deja como está (ya funciona). `_s3_client` centraliza el cliente para que los tests lo puedan monkeypatchear.

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_storage_helpers.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/documents/storage.py backend/tests/unit/test_storage_helpers.py
git commit -m "feat(evidencias-s3): helpers download_from_storage + presigned_get_url"
```

---

### Task 2: Endpoint de descarga + link "Ver" en la UI

**Files:**
- Modify: `backend/app/api/v1/evidence/router.py`
- Modify: `frontend/src/lib/evidence.ts`
- Modify: `frontend/src/components/plan/EvidenceSection.tsx`
- Test: `backend/tests/integration/test_evidence_download.py` (crear)

**Interfaces:**
- Consumes: `presigned_get_url(key)` de Task 1.
- Produces: `GET /evidence/{evidence_id}/download` → `{"url": str}` (200) o 404; `downloadEvidenceUrl(id): Promise<string>` en el cliente.

- [ ] **Step 1: Escribir el test del endpoint**

`backend/tests/integration/test_evidence_download.py`:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_dl"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _evidence():
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.action_task_id = uuid.uuid4()
    ev.s3_key = "documents/a/b/c.pdf"
    return ev


@pytest.mark.asyncio
async def test_download_devuelve_url_prefirmada(monkeypatch):
    ev = _evidence()

    async def fake_owned(tid, uid, db):
        return MagicMock()
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.evidence.router.presigned_get_url", lambda key: "https://signed/x")

    result = MagicMock()
    result.scalar_one_or_none.return_value = ev
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{ev.id}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["url"] == "https://signed/x"


@pytest.mark.asyncio
async def test_download_404_sin_s3(monkeypatch):
    ev = _evidence()

    async def fake_owned(tid, uid, db):
        return MagicMock()
    monkeypatch.setattr("app.api.v1.evidence.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.evidence.router.presigned_get_url", lambda key: None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = ev
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{ev.id}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_download_404_evidencia_inexistente(monkeypatch):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=result)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/evidence/{uuid.uuid4()}/download")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_evidence_download.py -q`
Expected: FAIL (404 en todos / ruta inexistente).

- [ ] **Step 3: Implementar el endpoint**

En `backend/app/api/v1/evidence/router.py`:

1. Ampliar el import del storage:
```python
from app.services.documents.storage import generate_storage_key, upload_to_storage, presigned_get_url
```
2. Agregar el endpoint (después de `list_evidence`, antes de `delete_evidence`):
```python
@router.get("/evidence/{evidence_id}/download")
async def download_evidence(
    evidence_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    await _get_user_task_or_404(ev.action_task_id, user_id, db)
    url = presigned_get_url(ev.s3_key)
    if not url:
        raise HTTPException(status_code=404, detail="Almacenamiento no configurado")
    return {"url": url}
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_evidence_download.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Cliente frontend**

En `frontend/src/lib/evidence.ts`, agregar al final:
```typescript
export async function downloadEvidenceUrl(evidenceId: string): Promise<string> {
  const r = await api.get<{ url: string }>(`/evidence/${evidenceId}/download`)
  return r.data.url
}
```

- [ ] **Step 6: Link "Ver" en `EvidenceSection`**

En `frontend/src/components/plan/EvidenceSection.tsx`:

1. Ampliar el import:
```tsx
import { Evidence, getEvidence, uploadEvidence, deleteEvidence, downloadEvidenceUrl } from "@/lib/evidence"
```
2. Agregar el handler dentro del componente (junto a `onRemove`):
```tsx
  const onView = async (id: string) => {
    try {
      const url = await downloadEvidenceUrl(id)
      window.open(url, "_blank", "noopener,noreferrer")
    } catch {
      setError("No se pudo abrir la evidencia (¿almacenamiento sin configurar?).")
    }
  }
```
3. En la fila de cada evidencia, agregar un botón "Ver" antes del botón de borrar (la `<X>`):
```tsx
          <div key={e.id} className="flex items-center gap-2 text-sm text-black bg-gray-50 rounded-lg px-3 py-2">
            <Paperclip className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            <span className="flex-1 truncate">{e.filename}</span>
            <button type="button" onClick={() => onView(e.id)} className="text-xs text-[var(--gob-navy)] hover:underline">
              Ver
            </button>
            <button type="button" onClick={() => onRemove(e.id)} className="text-gray-300 hover:text-red-500">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
```

- [ ] **Step 7: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores nuevos (los errores pre-existentes de `react-hooks/set-state-in-effect` en otras páginas no cuentan).

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/evidence/router.py backend/tests/integration/test_evidence_download.py frontend/src/lib/evidence.ts frontend/src/components/plan/EvidenceSection.tsx
git commit -m "feat(evidencias-s3): descarga/preview de evidencias (endpoint + link Ver)"
```

---

### Task 3: `run_month_review` multimodal

**Files:**
- Modify: `backend/app/services/ai/month_review.py`
- Test: `backend/tests/unit/test_review_multimodal.py` (crear)

**Interfaces:**
- Produces:
  - `_build_review_content(user_prompt: str, documents: list[dict] | None) -> str | list[dict]` — string si no hay documentos; lista de bloques (texto+document/image) si los hay. Cada `document` es `{"kind": "pdf"|"image", "media_type": str, "data": <base64 str>, "label": str}`.
  - `run_month_review(..., documents: list[dict] | None = None, documents_note: str = "")` — parámetros nuevos.

- [ ] **Step 1: Escribir el test del builder de contenido**

`backend/tests/unit/test_review_multimodal.py`:

```python
from app.services.ai.month_review import _build_review_content


def test_content_sin_documentos_es_string():
    out = _build_review_content("PROMPT", None)
    assert out == "PROMPT"
    assert _build_review_content("PROMPT", []) == "PROMPT"


def test_content_con_pdf_e_imagen_arma_bloques():
    docs = [
        {"kind": "pdf", "media_type": "application/pdf", "data": "QkFTRTY0", "label": "Doc A"},
        {"kind": "image", "media_type": "image/png", "data": "SU1H", "label": "Doc B"},
    ]
    out = _build_review_content("PROMPT", docs)
    assert isinstance(out, list)
    # texto(label A), document, texto(label B), image, texto(prompt) = 5 bloques
    assert len(out) == 5
    assert out[0] == {"type": "text", "text": "Doc A"}
    assert out[1] == {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "QkFTRTY0"}}
    assert out[2] == {"type": "text", "text": "Doc B"}
    assert out[3] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "SU1H"}}
    assert out[4] == {"type": "text", "text": "PROMPT"}
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_review_multimodal.py -q`
Expected: FAIL (`_build_review_content` no existe).

- [ ] **Step 3: Implementar `_build_review_content` + ampliar `run_month_review`**

En `backend/app/services/ai/month_review.py`:

1. Agregar el builder (antes de `run_month_review`):
```python
def _build_review_content(user_prompt: str, documents: list[dict] | None):
    """Sin documentos → string (comportamiento de hoy). Con documentos → lista de bloques multimodales."""
    if not documents:
        return user_prompt
    blocks: list[dict] = []
    for d in documents:
        blocks.append({"type": "text", "text": d["label"]})
        if d["kind"] == "pdf":
            blocks.append({"type": "document",
                           "source": {"type": "base64", "media_type": d["media_type"], "data": d["data"]}})
        else:  # image
            blocks.append({"type": "image",
                           "source": {"type": "base64", "media_type": d["media_type"], "data": d["data"]}})
    blocks.append({"type": "text", "text": user_prompt})
    return blocks
```

2. Cambiar la firma de `run_month_review`:
```python
def run_month_review(signals: dict, month_focus, objectives: list[dict],
                     memory_buffer: dict, period_label: str,
                     incomplete_task_ids: list[str],
                     documents: list[dict] | None = None,
                     documents_note: str = "") -> dict:
```

3. Dentro de `run_month_review`, después de construir `user_prompt` y antes de crear el cliente, inyectar la nota de documentos si existe. Reemplazar el bloque de `user_prompt` para que la nota quede ANTES de la línea "Emite el veredicto":
```python
    nota_docs = f"NOTA SOBRE DOCUMENTOS: {documents_note}\n" if documents_note else ""
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label} | Foco: {month_focus or 'N/D'}\n"
        f"OBJETIVOS DEL MES:\n{obj_lines}\n\n"
        f"SEÑALES DEL MES:\n{json.dumps(signals, ensure_ascii=False, indent=2)}\n"
        f"IDs de tareas incompletas (para carry_over_task): {incomplete}\n"
        f"{nota_docs}\n"
        "Emite el veredicto del consejo. Responde ÚNICAMENTE con JSON válido:\n"
        f"{REVIEW_SCHEMA}"
    )
```

4. Cambiar la llamada al cliente para usar el contenido multimodal:
```python
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_review_content(user_prompt, documents)}],
    )
```

5. Agregar al `REVIEW_SYSTEM_PROMPT` una regla 6 (después de la regla 5 actual):
```
6. Si se adjuntan DOCUMENTOS (PDF/imágenes), son las evidencias subidas este mes. Cada uno trae
   antes un texto que dice de qué tarea es y qué pedía. Léelos y valida si CADA documento respalda
   la meta de su tarea: si no la respalda, no des la tarea por lograda — propón arrastrarla
   (carry_over_task) o ajustarla, y dilo en el summary. NO inventes contenido de documentos que no
   se adjuntaron. Si hay una NOTA SOBRE DOCUMENTOS, menciónala (p. ej. pídele al usuario subir en
   PDF los formatos que no se pudieron leer).
```

- [ ] **Step 4: Correr (pasa) + suite del review**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_review_multimodal.py tests/unit/test_month_review.py tests/unit/test_missing_doc_signal.py -q`
Expected: PASS (los tests viejos de `run_month_review` siguen verdes: sin `documents` el contenido es el string de hoy y la nota va vacía).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/tests/unit/test_review_multimodal.py
git commit -m "feat(evidencias-s3): run_month_review multimodal (lee PDFs/imágenes adjuntos)"
```

---

### Task 4: Selección de documentos + cableado en `_run_close`

**Files:**
- Modify: `backend/app/services/ai/month_review.py` (helper puro `select_review_documents`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (`_run_close`)
- Test: `backend/tests/unit/test_select_review_documents.py` (crear)

**Interfaces:**
- Consumes: `select_review_documents` (este task), `download_from_storage` (Task 1), `run_month_review(..., documents=, documents_note=)` (Task 3).
- Produces: `select_review_documents(evidences, tasks_by_id, max_docs=_MAX_REVIEW_DOCS) -> tuple[list[dict], str]` — `(seleccionados, nota)`. Cada seleccionado: `{"s3_key": str, "kind": "pdf"|"image", "media_type": str, "label": str}`. Constante módulo `_MAX_REVIEW_DOCS = 8`.

- [ ] **Step 1: Escribir el test del helper de selección**

`backend/tests/unit/test_select_review_documents.py`:

```python
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.services.ai.month_review import select_review_documents, _MAX_REVIEW_DOCS

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _ev(filename, task_id, key="k", minutes=0):
    return SimpleNamespace(filename=filename, action_task_id=task_id, s3_key=key,
                           created_at=NOW + timedelta(minutes=minutes))


def _task(title, required_doc=None):
    return SimpleNamespace(title=title, required_doc=required_doc)


def test_filtra_legibles_y_anota_no_legibles():
    t1 = "task-1"
    evs = [
        _ev("estado.pdf", t1, key="k1"),
        _ev("foto.png", t1, key="k2"),
        _ev("hoja.xlsx", t1, key="k3"),
        _ev("doc.docx", t1, key="k4"),
    ]
    tasks_by_id = {t1: _task("Margen 11%", required_doc="estado de resultados")}
    selected, note = select_review_documents(evs, tasks_by_id)
    keys = {s["s3_key"] for s in selected}
    assert keys == {"k1", "k2"}  # solo pdf + png
    kinds = {s["s3_key"]: s["kind"] for s in selected}
    assert kinds["k1"] == "pdf" and kinds["k2"] == "image"
    assert "hoja.xlsx" in note and "doc.docx" in note
    # el label del pdf menciona la tarea y el required_doc
    pdf = next(s for s in selected if s["s3_key"] == "k1")
    assert "Margen 11%" in pdf["label"] and "estado de resultados" in pdf["label"]


def test_media_type_por_extension():
    t = "t"
    evs = [_ev("a.jpg", t, key="kj"), _ev("b.jpeg", t, key="kje"), _ev("c.png", t, key="kp")]
    selected, _ = select_review_documents(evs, {})
    mt = {s["s3_key"]: s["media_type"] for s in selected}
    assert mt["kj"] == "image/jpeg" and mt["kje"] == "image/jpeg" and mt["kp"] == "image/png"


def test_topa_a_max_docs_y_anota_truncado():
    t = "t"
    evs = [_ev(f"d{i}.pdf", t, key=f"k{i}", minutes=i) for i in range(_MAX_REVIEW_DOCS + 3)]
    selected, note = select_review_documents(evs, {})
    assert len(selected) == _MAX_REVIEW_DOCS
    assert str(_MAX_REVIEW_DOCS) in note  # menciona que solo leyó los N más recientes
    # los más recientes (mayor 'minutes') quedan seleccionados
    assert selected[0]["s3_key"] == f"k{_MAX_REVIEW_DOCS + 2}"


def test_sin_evidencias_devuelve_vacio():
    selected, note = select_review_documents([], {})
    assert selected == [] and note == ""
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_select_review_documents.py -q`
Expected: FAIL (`select_review_documents` / `_MAX_REVIEW_DOCS` no existen).

- [ ] **Step 3: Implementar `select_review_documents`**

En `backend/app/services/ai/month_review.py`, agregar arriba (después de los imports, junto a las constantes) y la función (cerca de `_build_review_content`):

```python
from pathlib import Path

_MAX_REVIEW_DOCS = 8
```

```python
def select_review_documents(evidences, tasks_by_id: dict, max_docs: int = _MAX_REVIEW_DOCS):
    """De las evidencias del mes, selecciona las legibles (PDF/imagen), las más recientes hasta
    max_docs, con un label por documento. Devuelve (seleccionados, nota_texto). No descarga nada."""
    evs = sorted(evidences, key=lambda e: e.created_at, reverse=True)
    readable: list[dict] = []
    unreadable: list[str] = []
    for e in evs:
        ext = Path(e.filename or "").suffix.lower()
        if ext == ".pdf":
            kind, media_type = "pdf", "application/pdf"
        elif ext in (".png", ".jpg", ".jpeg"):
            kind, media_type = "image", ("image/png" if ext == ".png" else "image/jpeg")
        else:
            unreadable.append(e.filename or "archivo")
            continue
        task = tasks_by_id.get(str(e.action_task_id))
        label = f"Documento «{e.filename}»"
        if task is not None:
            label += f" de la tarea «{getattr(task, 'title', '')}»"
            if getattr(task, "required_doc", None):
                label += f" que pedía: {task.required_doc}"
        readable.append({"s3_key": e.s3_key, "kind": kind, "media_type": media_type, "label": label})

    selected = readable[:max_docs]
    truncated = len(readable) - len(selected)
    notes: list[str] = []
    if unreadable:
        notes.append(
            "Documentos en un formato que no pude leer (pídele al usuario subirlos en PDF): "
            + ", ".join(unreadable[:10]) + "."
        )
    if truncated > 0:
        notes.append(f"Había más documentos; solo leí los {max_docs} más recientes.")
    return selected, " ".join(notes)
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_select_review_documents.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Cablear en `_run_close`**

En `backend/app/api/v1/annual_plan/router.py`:

1. Asegurar imports (arriba del archivo): `import base64` y ampliar los imports de `month_review` y `storage`:
```python
import base64
from app.services.ai.month_review import compute_signals, run_month_review, select_review_documents
from app.services.documents.storage import download_from_storage
```
(Si `compute_signals`/`run_month_review` ya se importan de `month_review`, solo agregar `select_review_documents`. Verificar el import existente y no duplicar.)

2. Dentro de `_run_close`, en el bloque `async with AsyncSessionLocal() as db:` donde ya se cargan `tasks` y `evidence_counts`, agregar la carga de evidencias y la selección **dentro** del `if tasks:` (reusa `task_ids`). Inicializar antes del `with` para que existan siempre:
```python
    selected_docs: list[dict] = []
    docs_note = ""
```
y dentro del `if tasks:` (después de calcular `evidence_counts`):
```python
            eres = await db.execute(
                select(Evidence).where(Evidence.action_task_id.in_(task_ids)).order_by(Evidence.created_at)
            )
            evidences = list(eres.scalars().all())
            tasks_by_id = {str(t.id): t for t in tasks}
            selected_docs, docs_note = select_review_documents(evidences, tasks_by_id)
```

3. **Después** de cerrar el bloque `async with` (antes de la llamada `review = await anyio.to_thread...`), descargar de S3 y armar los documentos multimodales (fuera del contexto de DB para no retener la conexión durante las descargas):
```python
    review_documents: list[dict] = []
    for d in selected_docs:
        raw = download_from_storage(d["s3_key"])
        if raw is None:
            continue
        review_documents.append({
            "kind": d["kind"], "media_type": d["media_type"],
            "data": base64.b64encode(raw).decode("ascii"), "label": d["label"],
        })
```

4. Pasar `documents` y `documents_note` a `run_month_review`:
```python
    review = await anyio.to_thread.run_sync(
        lambda: run_month_review(
            signals=signals, month_focus=focus, objectives=objectives,
            memory_buffer=memory_buffer, period_label=period_label,
            incomplete_task_ids=incomplete_ids,
            documents=review_documents, documents_note=docs_note,
        )
    )
```

- [ ] **Step 6: Correr la suite completa**

Run: `cd backend && ./venv/bin/pytest -q`
Expected: PASS (todo verde; el cierre sin S3 → `download_from_storage` devuelve `None` → `review_documents` vacío → comportamiento de hoy; los tests de cierre de mes existentes siguen pasando).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/app/api/v1/annual_plan/router.py backend/tests/unit/test_select_review_documents.py
git commit -m "feat(evidencias-s3): el cierre de mes lee las evidencias del mes (S3 + multimodal)"
```

---

## Self-Review (cobertura del spec)

- **Componente A (config S3)** → no es código; los pasos quedan en el spec. ✅ (sin task)
- **Componente B (descarga/preview)** → Task 1 (`presigned_get_url`) + Task 2 (endpoint `GET /evidence/{id}/download` + cliente `downloadEvidenceUrl` + link "Ver"). ✅
- **Componente C (cierre multimodal)** → Task 1 (`download_from_storage`) + Task 3 (`run_month_review` multimodal + reglas del prompt) + Task 4 (`select_review_documents` + cableado en `_run_close`). ✅
- **Solo PDF/imagen; Excel/Word como nota** → `select_review_documents` filtra por extensión y arma la nota; regla 6 del prompt la menciona. ✅
- **Tope 8** → `_MAX_REVIEW_DOCS = 8` + test de truncado. ✅
- **Degradación sin S3** → helpers devuelven `None`; `review_documents` vacío; nota vacía; tests corren sin credenciales. ✅
- **Sin migración** → ninguna columna nueva; confirmado. ✅

Consistencia de tipos: el dict de `select_review_documents` (`{s3_key, kind, media_type, label}`) se enriquece en `_run_close` con `data` (base64) → coincide con lo que `_build_review_content` espera (`{kind, media_type, data, label}`). `presigned_get_url`/`download_from_storage` (Task 1) se consumen en Task 2 y Task 4 con las firmas declaradas. `run_month_review` gana `documents`/`documents_note` en Task 3 y se llaman así en Task 4.

Puntos a verificar en implementación: el import existente de `month_review` en el router (no duplicar `compute_signals`/`run_month_review`); que `Evidence`, `select`, `func` ya estén importados en el router (lo están, se usan en `get_plan`/`_run_close`); la forma exacta del bloque `document`/`image` del SDK de Anthropic (skill `claude-api`) — el plan usa `{"type":"document","source":{"type":"base64","media_type":...,"data":...}}` y `{"type":"image",...}`, que es la forma de la Messages API.
