# Bloque B5 — Orden del día en PDF · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Descargar la Orden del Día de un mes como PDF (generado en el servidor con reportlab).

**Architecture:** La computación de la orden del día se extrae a un helper compartido `_build_orden_data`. Un servicio `orden_del_dia_pdf.build_orden_pdf` arma el PDF (reportlab). Un endpoint nuevo devuelve `application/pdf` como descarga. El frontend agrega un botón que baja el blob con auth.

**Tech Stack:** FastAPI, SQLAlchemy async, reportlab (nuevo, pure-python), pytest, Next.js 16 + TS + axios (blob).

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b5-orden-del-dia-pdf-design.md`

**Patrones existentes:**
- `app/api/v1/annual_plan/router.py`: `get_orden_del_dia` (computa plan→themes→month→`scheduled_for_session`→`OrdenDelDiaOut`); helpers `_current_plan`, `_theme_ref`, `_objective_out`, `_tasks_by_objective`; ya importa `_MONTH_NAMES` (lista indexada por `period_month`), `BoardTheme`, `MonthlyPlan`, `select`, `selectinload`. El flujo de cierre ya consulta `OnboardingSession` por `user_id` y lee `onboarding.memory_buffer` (patrón a reusar para el nombre de empresa).
- `OrdenDelDiaOut` en `app/schemas/orden_del_dia.py` (campos: month_index, period_year, period_month, permanent_themes, coverage_themes, covered_keys, objectives). `ThemeRef` tiene `.key/.label/.every_n_sessions`; `ObjectiveOut` tiene `.title/.kpi_refs`.
- Frontend: `lib/ordenDelDia.ts` (axios `api`), `OrdenDelDiaPanel.tsx` (título "Orden del día" en un `<h3>` dentro de un header flex).

---

### Task 1: Dependencia reportlab + servicio PDF

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/pdf/__init__.py` (vacío)
- Create: `backend/app/services/pdf/orden_del_dia_pdf.py`
- Test: `backend/tests/unit/test_orden_pdf.py`

- [ ] **Step 1: Add the dependency.** Append to `backend/requirements.txt`:
```
reportlab==4.2.5
```
Then install it in the venv (needed to run the test):
`cd backend && venv/bin/pip install reportlab==4.2.5`

- [ ] **Step 2: Write the failing test** at `backend/tests/unit/test_orden_pdf.py`:
```python
from app.schemas.orden_del_dia import ThemeRef
from app.schemas.annual_plan import ObjectiveOut
from app.services.pdf.orden_del_dia_pdf import build_orden_pdf


def _data():
    return {
        "month_index": 1,
        "period_label": "Enero 2026",
        "permanent_themes": [ThemeRef(key="fin", label="Resultados financieros", every_n_sessions=1)],
        "coverage_themes": [ThemeRef(key="aud", label="Auditoría", every_n_sessions=3)],
        "covered_keys": ["fin"],
        "objectives": [ObjectiveOut(id="o1", title="Mejorar margen", kpi_refs=["EBITDA"])],
    }


def test_build_orden_pdf_returns_pdf_bytes():
    pdf = build_orden_pdf(_data(), "Acme S.A.")
    assert isinstance(pdf, (bytes, bytearray))
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_build_orden_pdf_without_company():
    pdf = build_orden_pdf(_data(), None)
    assert pdf[:4] == b"%PDF"
```

- [ ] **Step 3: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_orden_pdf.py -v`

- [ ] **Step 4: Create the package init** `backend/app/services/pdf/__init__.py` (empty file).

- [ ] **Step 5: Implement** `backend/app/services/pdf/orden_del_dia_pdf.py`:
```python
"""Genera el PDF de la Orden del Día (Bloque B5) con reportlab. Determinista, sin DB."""
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_GREY = colors.HexColor("#6b7280")
_MUTED = colors.HexColor("#9ca3af")


def build_orden_pdf(data: dict, company_name: str | None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    s_company = ParagraphStyle("company", parent=base["Title"], fontSize=16, spaceAfter=2, alignment=0)
    s_sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=11, textColor=_GREY, spaceAfter=14)
    s_section = ParagraphStyle("section", parent=base["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6)
    s_body = base["Normal"]
    s_muted = ParagraphStyle("muted", parent=base["Normal"], fontSize=9, textColor=_MUTED)

    covered = set(data.get("covered_keys") or [])
    story = []

    # escape() en TODO el contenido de usuario: reportlab parsea markup XML, un '&' lo rompe.
    # Separadores ASCII ('-') para evitar caracteres fuera de la fuente base.
    story.append(Paragraph(escape(company_name or "Plan estratégico de 12 meses"), s_company))
    story.append(Paragraph(
        escape(f"Orden del día - {data['period_label']} - Sesión {data['month_index']}"), s_sub))

    def _theme_lines(title, themes):
        if not themes:
            return
        story.append(Paragraph(f"<b>{title}</b>", s_body))  # title es literal nuestro, seguro
        for t in themes:
            suffix = " (cubierto)" if t.key in covered else ""
            story.append(Paragraph(escape(f"- {t.label}{suffix}"), s_body))
        story.append(Spacer(1, 6))

    perms = data.get("permanent_themes") or []
    cobs = data.get("coverage_themes") or []
    if perms or cobs:
        story.append(Paragraph("Temas del Consejo", s_section))
        _theme_lines("Permanentes", perms)
        _theme_lines("Cobertura este mes", cobs)

    objs = data.get("objectives") or []
    if objs:
        story.append(Paragraph("Objetivos del mes", s_section))
        for o in objs:
            story.append(Paragraph(escape(o.title), s_body))
            if o.kpi_refs:
                story.append(Paragraph(escape(", ".join(o.kpi_refs)), s_muted))

    story.append(Spacer(1, 18))
    story.append(Paragraph(escape(f"Generado por Gobernia - {date.today().isoformat()}"), s_muted))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 6: Run the test, verify it PASSES** (2 passed):
`cd backend && venv/bin/python -m pytest tests/unit/test_orden_pdf.py -v`

- [ ] **Step 7: Commit:**
```bash
git add backend/requirements.txt backend/app/services/pdf/__init__.py backend/app/services/pdf/orden_del_dia_pdf.py backend/tests/unit/test_orden_pdf.py
git commit -m "feat(b5): servicio build_orden_pdf (reportlab) + dependencia"
```

---

### Task 2: Refactor `_build_orden_data` + endpoint PDF

**Files:**
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports, refactor `get_orden_del_dia`, nuevo endpoint)
- Test: `backend/tests/integration/test_orden_pdf_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_orden_pdf_api.py`:
```python
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_pdf"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_orden_del_dia_pdf():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    themes = [_theme("fin", "permanente", 1, 0)]
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.period_year = 2026; month.period_month = 1
    month.covered_themes = ["fin"]; month.objectives = []
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "Acme"}}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes  # themes
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = month         # month
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb           # onboarding
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia/pdf")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")
```

- [ ] **Step 2: Run it, verify it FAILS** (endpoint doesn't exist):
`cd backend && venv/bin/python -m pytest tests/integration/test_orden_pdf_api.py -v`

- [ ] **Step 3: Add imports** to `backend/app/api/v1/annual_plan/router.py`. Change the fastapi import line `from fastapi import APIRouter, Depends, HTTPException` to add `Response`:
```python
from fastapi import APIRouter, Depends, HTTPException, Response
```
And add:
```python
from app.models.onboarding_session import OnboardingSession
from app.services.pdf.orden_del_dia_pdf import build_orden_pdf
```

- [ ] **Step 4: Refactor `get_orden_del_dia` to use a shared helper.** Replace the existing `get_orden_del_dia` function body so the computation lives in `_build_orden_data`. Add this helper directly ABOVE the `get_orden_del_dia` endpoint:
```python
async def _build_orden_data(plan, month_index: int, db: AsyncSession) -> dict | None:
    res = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(res.scalars().all())
    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = mres.scalar_one_or_none()
    if not month:
        return None
    sched = scheduled_for_session(themes, month_index)
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return {
        "month_index": month.month_index,
        "period_year": month.period_year,
        "period_month": month.period_month,
        "permanent_themes": [_theme_ref(t) for t in sched["permanente"]],
        "coverage_themes": [_theme_ref(t) for t in sched["cobertura"]],
        "covered_keys": list(month.covered_themes or []),
        "objectives": [_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    }
```
And replace the body of `get_orden_del_dia` with:
```python
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    data = await _build_orden_data(plan, month_index, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    return OrdenDelDiaOut(**data)
```
(`OrdenDelDiaOut(**data)` works because the dict keys match the schema fields exactly.)

- [ ] **Step 5: Add the PDF endpoint** right after `get_orden_del_dia`:
```python
@router.get("/annual-plan/months/{month_index}/orden-del-dia/pdf")
async def get_orden_del_dia_pdf(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    data = await _build_orden_data(plan, month_index, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    data["period_label"] = f"{_MONTH_NAMES[data['period_month']]} {data['period_year']}"

    company_name = None
    try:
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        mb = (onboarding.memory_buffer if onboarding else {}) or {}
        company_name = (mb.get("company") or {}).get("name")
    except Exception:
        company_name = None

    pdf = build_orden_pdf(data, company_name)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="orden-del-dia-mes-{month_index}.pdf"'},
    )
```

- [ ] **Step 6: Run the tests, verify they PASS:**
`cd backend && venv/bin/python -m pytest tests/integration/test_orden_pdf_api.py tests/integration/test_orden_del_dia_api.py -v`
(The existing orden JSON test must stay green — the refactor preserves its 3-execute sequence: plan → themes → month.)

- [ ] **Step 7: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 8: Commit:**
```bash
git add backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_orden_pdf_api.py
git commit -m "feat(b5): endpoint orden-del-dia/pdf + refactor _build_orden_data"
```

---

### Task 3: Frontend — botón "Descargar PDF"

**Files:**
- Modify: `frontend/src/lib/ordenDelDia.ts` (`downloadOrdenPdf`)
- Modify: `frontend/src/components/plan/OrdenDelDiaPanel.tsx` (botón)

- [ ] **Step 1: Add the download function.** In `frontend/src/lib/ordenDelDia.ts`, add:
```typescript
export async function downloadOrdenPdf(monthIndex: number): Promise<void> {
  const r = await api.get(`/annual-plan/months/${monthIndex}/orden-del-dia/pdf`, { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `orden-del-dia-mes-${monthIndex}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Add the button to the panel.** Read `frontend/src/components/plan/OrdenDelDiaPanel.tsx`. The title is an `<h3>Orden del día</h3>` inside a header. Changes:
  1. Update the import to include `downloadOrdenPdf`:
  ```typescript
  import { OrdenDelDia, getOrdenDelDia, markCoverage, downloadOrdenPdf } from "@/lib/ordenDelDia"
  ```
  2. Add a `downloading` state near the other `useState` hooks:
  ```typescript
  const [downloading, setDownloading] = useState(false)
  ```
  3. Add a handler (above the `return`):
  ```typescript
  const onDownload = async () => {
    setDownloading(true)
    try { await downloadOrdenPdf(monthIndex) } catch { /* noop */ } finally { setDownloading(false) }
  }
  ```
  4. Wrap the existing `<h3>Orden del día</h3>` so the title and a button sit on one row. Replace the `<h3 ...>Orden del día</h3>` with:
  ```tsx
  <div className="flex items-center justify-between">
    <h3 className="text-sm font-bold text-black uppercase tracking-wide">Orden del día</h3>
    <button
      type="button"
      onClick={onDownload}
      disabled={downloading}
      className="text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50"
    >
      {downloading ? "Generando…" : "Descargar PDF"}
    </button>
  </div>
  ```
  Read the file to place this precisely (keep the existing className on the surrounding container; only the `<h3>` line is wrapped).

- [ ] **Step 3: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/ordenDelDia.ts src/components/plan/OrdenDelDiaPanel.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 4: Commit:**
```bash
git add frontend/src/lib/ordenDelDia.ts frontend/src/components/plan/OrdenDelDiaPanel.tsx
git commit -m "feat(b5): botón Descargar PDF en el panel de Orden del día"
```

---

## Done criteria

- `reportlab` en `requirements.txt`; `GET .../orden-del-dia/pdf` devuelve un PDF (`%PDF`, application/pdf, attachment).
- El dueño descarga el PDF de la orden del día desde el panel.
- El endpoint JSON existente sigue funcionando (refactor sin regresión).
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **reportlab debe instalarse en el venv** (`venv/bin/pip install reportlab==4.2.5`) para que los tests corran, y quedar en `requirements.txt` para que Railway lo instale en el deploy.
- **ASCII-safe + escape:** el PDF usa `- ` y el sufijo `(cubierto)` (no ✓/•/em-dash, para evitar problemas de fuente en Helvetica), y separadores con guion ASCII. Los acentos del español (é/í/ó) sí los soporta la fuente base. TODO el contenido de usuario (nombre de empresa, labels, títulos de objetivos, KPIs) pasa por `xml.sax.saxutils.escape` porque reportlab parsea markup XML y un `&` crudo rompería el `doc.build`. Las etiquetas `<b>…</b>` de los subtítulos son literales nuestros (no se escapan).
- **Sin migración** (B5 no toca DB).
- **El refactor** preserva la secuencia de queries del endpoint JSON (plan → themes → month), así que el test existente `test_orden_del_dia_api.py` sigue verde sin cambios.
