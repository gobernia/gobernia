# Fase 3B — El Secretario activo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El Secretario activo sin infra nueva: análisis de cierre de mes que detecta el documento de sustento faltante, una alerta "El Secretario revisó tu mes", y avisos push arriba-derecha en el dashboard.

**Architecture:** Dos cambios de backend sobre piezas existentes (señal `tasks_missing_doc` en el review; helper `review_alert` apilado en el endpoint `/alertas`) + un componente de frontend `Notices` montado en el layout del dashboard que consume las alertas que ya existen. Sin migración, sin tabla nueva.

**Tech Stack:** FastAPI, SQLAlchemy async, anthropic SDK; Next.js 16, framer-motion, lucide-react.

**Verificación:** Backend pytest (`cd backend && ./venv/bin/pytest`). Frontend `npm run lint` + `npm run build`. Lógica pura testeada sin red/DB.

---

### Task 1: Señal de documento faltante en el análisis de cierre

**Files:**
- Modify: `backend/app/services/ai/month_review.py` (`compute_signals`, `deterministic_review`, `REVIEW_SYSTEM_PROMPT`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (`_run_close`)
- Test: `backend/tests/unit/test_missing_doc_signal.py` (crear)

- [ ] **Step 1: Tests de la señal + el review determinista**

`backend/tests/unit/test_missing_doc_signal.py`:

```python
from datetime import date
from types import SimpleNamespace
from app.services.ai.month_review import compute_signals, deterministic_review


def _task(id, required_doc=None, status="pendiente"):
    return SimpleNamespace(id=id, status=status, due_date=None, required_doc=required_doc, title=f"T{id}")


def test_tasks_missing_doc_detecta_faltante():
    tasks = [
        _task("a", required_doc="estado de resultados"),   # sin evidencia → falta
        _task("b", required_doc="contrato"),               # con evidencia → ok
        _task("c", required_doc=None),                     # no pide doc → no aplica
    ]
    sig = compute_signals(tasks, {}, {}, date(2026, 3, 1), evidence_counts={"b": 1})
    titles = [m["title"] for m in sig["tasks_missing_doc"]]
    assert titles == ["Ta"]  # solo la 'a'
    assert sig["tasks_missing_doc"][0]["required_doc"] == "estado de resultados"


def test_tasks_missing_doc_vacio_sin_evidence_counts():
    tasks = [_task("a", required_doc="x")]
    sig = compute_signals(tasks, {}, {}, date(2026, 3, 1))  # sin evidence_counts
    # sin el mapa, no se puede afirmar presencia → se asume faltante? NO: retrocompat = vacío.
    assert sig["tasks_missing_doc"] == []


def test_deterministic_review_menciona_faltantes():
    signals = {"completion_pct": 90, "tasks_missing_doc": [{"title": "T1", "required_doc": "estado de resultados"}]}
    rev = deterministic_review(signals, [])
    assert "sustento" in rev["summary"].lower() or "documento" in rev["summary"].lower()
```

> Nota: el comportamiento sin `evidence_counts` es **lista vacía** (retrocompat: los llamados viejos no pasan el mapa y no deben empezar a marcar todo como faltante). El llamado real en `_run_close` SÍ pasa el mapa.

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_missing_doc_signal.py -q`

- [ ] **Step 3: `compute_signals` gana `evidence_counts` + `tasks_missing_doc`**

En `compute_signals` (firma `def compute_signals(tasks, kpi_values, memory_buffer, today)`), cambiar a:
```python
def compute_signals(tasks, kpi_values: dict, memory_buffer: dict, today: date,
                    evidence_counts: dict | None = None) -> dict:
```
Y antes del `return`, calcular:
```python
    ev = evidence_counts or {}
    tasks_missing_doc = [
        {"title": getattr(t, "title", ""), "required_doc": t.required_doc}
        for t in tasks
        if getattr(t, "required_doc", None) and ev.get(str(t.id), 0) == 0
    ]
```
Agregar `"tasks_missing_doc": tasks_missing_doc` al dict de `return`.

- [ ] **Step 4: `deterministic_review` menciona los faltantes**

En `deterministic_review`, después de calcular `grade`, construir el summary considerando faltantes:
```python
    missing = signals.get("tasks_missing_doc") or []
    summary = "Revisión automática basada en el cumplimiento de tareas del mes."
    if missing:
        n = len(missing)
        summary += f" {n} tarea{'s' if n != 1 else ''} sin su documento de sustento — súbelos para validarlas."
```
Y usar ese `summary` en el dict de retorno (reemplazar el string fijo actual).

- [ ] **Step 5: El prompt del review factoriza los faltantes**

En `REVIEW_SYSTEM_PROMPT`, agregar una regla (las señales —incluida `tasks_missing_doc`— ya se inyectan como JSON en el user_prompt):
```
5. Si 'tasks_missing_doc' del JSON de señales trae tareas, esas NO pueden considerarse logradas
   sin su documento de sustento: dilo en el summary, pésalo en el grade, y propón subir el
   documento (o arrastra la tarea con carry_over_task).
```
(Renumerar si choca con reglas existentes; insertarlo como una regla más.)

- [ ] **Step 6: `_run_close` carga los conteos de evidencia y los pasa**

En `backend/app/api/v1/annual_plan/router.py`, dentro de `_run_close`, en el primer bloque `AsyncSessionLocal` (donde ya se cargan `tasks`), después de obtener `tasks` agregar la consulta de conteos (mismo patrón que `get_plan`) y pasarla a `compute_signals`:
```python
        from sqlalchemy import func
        evidence_counts = {}
        if tasks:
            task_ids = [t.id for t in tasks]
            cres = await db.execute(
                select(Evidence.action_task_id, func.count())
                .where(Evidence.action_task_id.in_(task_ids))
                .group_by(Evidence.action_task_id)
            )
            evidence_counts = {str(tid): cnt for tid, cnt in cres.all()}
        signals = compute_signals(tasks, kpis, memory_buffer, today, evidence_counts=evidence_counts)
```
(Reemplaza el `signals = compute_signals(tasks, kpis, memory_buffer, today)` actual. `Evidence` y `func`/`select` ya se importan en el router — confirmar; `select` sí, `func` se usa en get_plan.)

- [ ] **Step 7: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_missing_doc_signal.py -q && ./venv/bin/pytest -q`
Expected: verde. Los tests existentes del review siguen pasando (la señal nueva es aditiva; los llamados viejos a `compute_signals` sin `evidence_counts` dan lista vacía).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/app/api/v1/annual_plan/router.py backend/tests/unit/test_missing_doc_signal.py
git commit -m "feat(fase3b): el cierre de mes detecta el documento de sustento faltante"
```

---

### Task 2: Alerta "El Secretario revisó tu mes"

**Files:**
- Modify: `backend/app/services/governance/alerts.py` (nuevo helper `review_alert`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (endpoint `/alertas`)
- Test: `backend/tests/unit/test_review_alert.py` (crear)

- [ ] **Step 1: Tests de `review_alert`**

`backend/tests/unit/test_review_alert.py`:

```python
from types import SimpleNamespace
from app.services.governance.alerts import review_alert


def _month(idx, status, review=None):
    return SimpleNamespace(month_index=idx, status=status, review=review)


def test_alerta_cuando_hay_revision_con_propuestas_pendientes():
    months = [
        _month(1, "done", {"proposals": [{"applied": True}, {"applied": False}, {"applied": False}]}),
        _month(2, "active", None),
    ]
    a = review_alert(months)
    assert a is not None
    assert a["level"] == "info" and a["category"] == "revision"
    assert "2 propuesta" in a["message"]


def test_sin_alerta_si_todas_aplicadas():
    months = [_month(1, "done", {"proposals": [{"applied": True}]})]
    assert review_alert(months) is None


def test_sin_alerta_si_no_hay_mes_done():
    months = [_month(1, "active", None)]
    assert review_alert(months) is None
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_review_alert.py -q`

- [ ] **Step 3: Implementar `review_alert`**

Agregar a `backend/app/services/governance/alerts.py`:
```python
def review_alert(months) -> dict | None:
    """Alerta info cuando el mes 'done' más reciente tiene propuestas del Secretario sin aplicar."""
    done = [m for m in months if getattr(m, "status", None) == "done" and getattr(m, "review", None)]
    if not done:
        return None
    latest = max(done, key=lambda m: getattr(m, "month_index", 0))
    pending = [p for p in ((latest.review or {}).get("proposals") or []) if not p.get("applied")]
    if not pending:
        return None
    n = len(pending)
    return {
        "level": "info", "category": "revision",
        "message": f"El Secretario revisó tu mes: {n} propuesta{'s' if n != 1 else ''} para tu plan.",
    }
```

- [ ] **Step 4: El endpoint `/alertas` apila la alerta de revisión**

En `router.py`, el endpoint que devuelve las alertas (llama `compute_alerts(...)` y devuelve la lista). Leerlo: ya carga el plan con sus `months`. Después de obtener la lista de `compute_alerts`, anteponer la alerta de revisión si existe:
```python
        from app.services.governance.alerts import review_alert
        ra = review_alert(plan.months)
        alerts = ([ra] if ra else []) + alerts
```
(Usar el nombre real de la variable de la lista de alertas y del plan en ese endpoint. La alerta de revisión va primero por ser un resumen del mes.)

- [ ] **Step 5: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_review_alert.py -q && ./venv/bin/pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/governance/alerts.py backend/app/api/v1/annual_plan/router.py backend/tests/unit/test_review_alert.py
git commit -m "feat(fase3b): alerta 'El Secretario revisó tu mes' en /alertas"
```

---

### Task 3: Avisos push arriba (frontend)

**Files:**
- Create: `frontend/src/components/dashboard/Notices.tsx`
- Modify: `frontend/src/app/dashboard/layout.tsx`

- [ ] **Step 1: Crear `Notices.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X } from "lucide-react"
import { getAlertas, type AlertItem } from "@/lib/alerts"

const BORDER: Record<string, string> = {
  critical: "border-red-400 bg-red-50",
  warning: "border-amber-400 bg-amber-50",
  info: "border-gray-300 bg-gray-50",
}
const KEY = "gobernia_notices_dismissed"

function getDismissed(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try { return new Set(JSON.parse(sessionStorage.getItem(KEY) || "[]")) } catch { return new Set() }
}
function addDismissed(msg: string) {
  if (typeof window === "undefined") return
  const s = getDismissed(); s.add(msg)
  sessionStorage.setItem(KEY, JSON.stringify([...s]))
}

export default function Notices() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])

  useEffect(() => {
    getAlertas()
      .then(a => {
        const dismissed = getDismissed()
        setAlerts(a.filter(x => !dismissed.has(x.message)))
      })
      .catch(() => {})
  }, [])

  const dismissOne = (msg: string) => {
    addDismissed(msg)
    setAlerts(prev => prev.filter(a => a.message !== msg))
  }

  if (alerts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 w-80 max-w-[calc(100vw-2rem)] space-y-2">
      <AnimatePresence>
        {alerts.map(a => (
          <motion.div
            key={a.message}
            initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 30 }}
            transition={{ duration: 0.25 }}
            className={`relative rounded-xl border-l-4 shadow-sm px-4 py-3 pr-8 text-sm text-gray-700 ${BORDER[a.level] ?? BORDER.info}`}
          >
            {a.message}
            <button onClick={() => dismissOne(a.message)} aria-label="Cerrar"
              className="absolute top-2 right-2 text-gray-400 hover:text-gray-700">
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
```

(`AlertItem` y `getAlertas` ya existen en `@/lib/alerts` con `{ level, category, message }`. Si no hay plan, `getAlertas` rechaza → `.catch` silencioso → no muestra nada.)

- [ ] **Step 2: Montar `<Notices />` en el layout del dashboard**

En `frontend/src/app/dashboard/layout.tsx`, importar y montar junto al `<Sidebar />` (Notices es `fixed`, no afecta el layout):
```tsx
import Sidebar from "@/components/ui/Sidebar"
import Notices from "@/components/dashboard/Notices"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <Sidebar />
      <Notices />
      <div className="md:ml-60">{children}</div>
    </div>
  )
}
```
(Confirmar la forma actual del layout y solo agregar el import + `<Notices />`.)

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores nuevos.

- [ ] **Step 4: Smoke (referencia)**

Con un plan con alertas (tareas vencidas/por vencer o un mes cerrado con propuestas), al entrar a cualquier página del dashboard aparecen los avisos arriba-derecha; cerrar uno no reaparece en la sesión; sin plan → no aparece nada.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/Notices.tsx frontend/src/app/dashboard/layout.tsx
git commit -m "feat(fase3b-fe): avisos push arriba-derecha derivados de las alertas"
```

---

## Self-Review (cobertura del spec)

- **Componente 1 (señal de documento faltante en el cierre)** → Task 1 (`tasks_missing_doc` + `_run_close` pasa conteos + review LLM/determinista la factoriza). ✅
- **Componente 2 (alerta "Secretario revisó tu mes")** → Task 2 (`review_alert` + endpoint `/alertas`). ✅
- **Componente 3 (avisos push arriba)** → Task 3 (`Notices.tsx` + layout). ✅
- **Componente 4 (enchufes correo/S3)** → documentación en el spec; NO se construye código (correcto). ✅

Consistencia: `tasks_missing_doc` (lista de `{title, required_doc}`) se produce en `compute_signals`, se consume en `deterministic_review` y en el prompt (vía el JSON de señales). `review_alert` devuelve `{level:"info", category, message}` — coincide con `AlertItem {level, category, message}` del frontend. `Notices` reusa `getAlertas()` y los colores por nivel de `AlertsPanel`. Dismiss por mensaje en `sessionStorage` (sobrevive navegación dentro de la sesión).

Puntos a confirmar en implementación: nombres reales de la variable de lista y del plan en el endpoint `/alertas`; que `func` esté importado en el router (lo usa `get_plan`); la forma actual de `dashboard/layout.tsx`.
