# Todd — Onboarding como formulario guiado + edición — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir la pantalla de Todd de chat a un **formulario guiado paso a paso** (una pregunta por tarjeta, Todd con avatar + encuadre, controles de formulario, progreso por las 7 áreas) con **edición** ("Atrás" → corregir una respuesta; Todd decide si conservar las posteriores o repreguntar).

**Architecture:** Reutiliza el motor de Todd (tool use, estado, cobertura) y los endpoints `turn`/`close` existentes. Se añade: un campo `reanudar_desde` a la salida estructurada + `run_todd_edit` (backend), un endpoint `POST /onboarding/todd/edit`, y `areas_cubiertas` expuesto por la API. El frontend reescribe `onboarding/todd/page.tsx` de chat a wizard + panel de edición.

**Tech Stack:** FastAPI, SQLAlchemy async, anthropic (Sonnet 4.6, tool use). Next.js 16 App Router, framer-motion, lucide-react, axios (`@/lib/api`). Sin migración (reusa `todd_sessions`).

## Global Constraints

- **Backend del motor se reutiliza**: no se cambia `build_system_prompt`/`build_anthropic_messages`/`run_todd_turn` salvo lo aditivo (campo `reanudar_desde`, función `run_todd_edit`).
- **Edición con fallback seguro**: si Todd no decide claramente, se asume `"rehacer"` (consistencia > comodidad).
- **`answer_index`** = índice (en `messages`) del mensaje `role="user"` a corregir; su pregunta = el mensaje `todd` inmediatamente anterior.
- **Frontend Next.js 16**: client component con `fetch` vía `@/lib/api` (no APIs nuevas de Next). Estilo de marca (`--gob-navy`/`--gob-bone`).
- **Tras editar, el frontend re-consulta la sesión** (`GET /onboarding/todd`) para reconstruir lista + pregunta actual + progreso.

---

### Task 1: Backend — campo `reanudar_desde` + `run_todd_edit`

**Files:**
- Modify: `backend/app/services/ai/todd/agent.py` (`RESPONSE_TOOL`, `_normalize_turn`, nuevo `_edit_note` + `run_todd_edit`)
- Test: `backend/tests/unit/test_todd_edit.py` (crear)

**Interfaces:**
- Produces:
  - `_normalize_turn(...)` ahora incluye `"reanudar_desde": "continuar"|"rehacer"` (default `"continuar"`).
  - `run_todd_edit(messages: list[dict], edited_question: str, new_answer: str, state: dict|None=None) -> dict` — turno normalizado (mismo shape que `run_todd_turn` + `reanudar_desde`).

- [ ] **Step 1: Tests**

`backend/tests/unit/test_todd_edit.py`:
```python
from app.services.ai.todd.agent import _normalize_turn, RESPONSE_TOOL


def test_normalize_turn_incluye_reanudar_desde_default_continuar():
    t = _normalize_turn({"message": "x", "input": "text", "state": {}, "done": False})
    assert t["reanudar_desde"] == "continuar"


def test_normalize_turn_respeta_rehacer():
    t = _normalize_turn({"message": "x", "input": "text", "state": {}, "done": False,
                         "reanudar_desde": "rehacer"})
    assert t["reanudar_desde"] == "rehacer"


def test_normalize_turn_valor_invalido_cae_a_continuar():
    t = _normalize_turn({"message": "x", "reanudar_desde": "lo_que_sea"})
    assert t["reanudar_desde"] == "continuar"


def test_response_tool_declara_reanudar_desde():
    props = RESPONSE_TOOL["input_schema"]["properties"]
    assert "reanudar_desde" in props
    assert props["reanudar_desde"]["enum"] == ["continuar", "rehacer"]
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_edit.py -q`
Expected: FAIL (`reanudar_desde` no existe).

- [ ] **Step 3: Implementar en `backend/app/services/ai/todd/agent.py`**

(a) En `RESPONSE_TOOL["input_schema"]["properties"]`, agregar la propiedad (no la pongas en `required`):
```python
            "reanudar_desde": {"type": "string", "enum": ["continuar", "rehacer"],
                               "description": "Solo al editar: 'continuar' si la corrección no invalida "
                                              "respuestas posteriores, 'rehacer' si sí."},
```

(b) En `_normalize_turn`, agregar al dict de retorno (antes del cierre `}`):
```python
        "reanudar_desde": parsed.get("reanudar_desde") if parsed.get("reanudar_desde") in ("continuar", "rehacer") else "continuar",
```

(c) Agregar (después de `run_todd_turn`):
```python
def _edit_note(edited_question: str, new_answer: str) -> str:
    return (
        "\n\nEDICIÓN: el usuario acaba de CORREGIR una respuesta anterior. "
        f"A la pregunta «{edited_question}» ahora responde: «{new_answer}». "
        "Revisa las respuestas que dio DESPUÉS de esa pregunta y decide 'reanudar_desde':\n"
        "- 'continuar' si la corrección NO invalida ninguna respuesta posterior → incorpóralas al "
        "state y haz la SIGUIENTE pregunta que falte (no repitas lo ya respondido).\n"
        "- 'rehacer' si la corrección invalida alguna respuesta posterior → en 'message' avisa breve "
        "(p. ej. «Con ese cambio, repasemos un par de cosas desde aquí») y vuelve a preguntar lo que sigue."
    )


def run_todd_edit(messages: list[dict], edited_question: str, new_answer: str,
                  state: dict | None = None) -> dict:
    """Tras una corrección: Todd ve el transcript ya corregido + una nota de edición, y decide
    'reanudar_desde' (continuar/rehacer) además del siguiente turno. Sin API key → rehacer mínimo."""
    if not settings.ANTHROPIC_API_KEY:
        return {"message": "Listo, lo dejé corregido. Continuemos.", "options": None,
                "input": "text", "state": state or {}, "done": False, "reanudar_desde": "rehacer"}
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=build_system_prompt(state) + _edit_note(edited_question, new_answer),
        messages=build_anthropic_messages(messages),
        tools=[RESPONSE_TOOL],
        tool_choice={"type": "tool", "name": "responder_turno"},
    )
    block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    parsed = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
    return enforce_coverage(_normalize_turn(parsed))
```

- [ ] **Step 4: Correr (pasa) + tests previos de Todd**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_todd_edit.py tests/unit/test_todd_agent.py -q`
Expected: PASS (los tests del agente siguen verdes; `reanudar_desde` es aditivo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/todd/agent.py backend/tests/unit/test_todd_edit.py
git commit -m "feat(todd-form): campo reanudar_desde + run_todd_edit (análisis de impacto de la edición)"
```

---

### Task 2: Backend — endpoint `edit` + exponer `areas_cubiertas`

**Files:**
- Modify: `backend/app/schemas/todd.py` (`ToddSessionOut`, `ToddTurnOut`, nuevo `ToddEditIn`)
- Modify: `backend/app/api/v1/todd/router.py` (`get_todd`, `todd_turn`, nuevo `todd_edit`)
- Test: `backend/tests/integration/test_todd_api.py` (agregar tests)

**Interfaces:**
- Consumes: `run_todd_edit` (Task 1), `run_todd_turn`.
- Produces: `POST /onboarding/todd/edit {answer_index:int, nueva_respuesta:str}` → `ToddTurnOut`; `ToddSessionOut.areas_cubiertas`, `ToddTurnOut.areas_cubiertas`.

- [ ] **Step 1: Tests**

Agregar a `backend/tests/integration/test_todd_api.py` (reusa los helpers `_db_override`, `_user_override`, `MOCK_USER_ID` ya presentes):
```python
@pytest.mark.asyncio
async def test_edit_rehacer_trunca_posteriores(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"areas_cubiertas": ["estrategia"]}
    sess.messages = [
        {"role": "todd", "text": "¿Nombre?", "options": None},
        {"role": "user", "text": "Keting", "options": None},
        {"role": "todd", "text": "¿Industria?", "options": None},
        {"role": "user", "text": "Comercio", "options": None},
    ]
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    db = AsyncMock(); db.execute = AsyncMock(return_value=r1); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_edit",
        lambda messages, edited_question, new_answer, state=None: {
            "message": "Con ese cambio, repasemos: ¿industria?", "options": None,
            "input": "text", "state": {"areas_cubiertas": ["estrategia"]},
            "done": False, "reanudar_desde": "rehacer"},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/edit", json={"answer_index": 1, "nueva_respuesta": "Keting Media"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    # rehacer → trunca lo posterior al índice 1 y agrega el mensaje de Todd
    assert sess.messages[1]["text"] == "Keting Media"   # corregido
    assert sess.messages[-1]["role"] == "todd"
    assert all(m["text"] != "Comercio" for m in sess.messages)  # posteriores descartadas


@pytest.mark.asyncio
async def test_edit_continuar_conserva_posteriores(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"areas_cubiertas": ["estrategia", "comercial"]}
    sess.messages = [
        {"role": "todd", "text": "¿Nombre?", "options": None},
        {"role": "user", "text": "Keting", "options": None},
        {"role": "todd", "text": "¿Industria?", "options": None},
        {"role": "user", "text": "Software", "options": None},
    ]
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    db = AsyncMock(); db.execute = AsyncMock(return_value=r1); db.commit = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.todd.router.run_todd_edit",
        lambda messages, edited_question, new_answer, state=None: {
            "message": "Perfecto. ¿Tienen misión y visión?", "options": ["Sí", "No"],
            "input": "single_choice", "state": {"areas_cubiertas": ["estrategia", "comercial"]},
            "done": False, "reanudar_desde": "continuar"},
    )

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/edit", json={"answer_index": 1, "nueva_respuesta": "Keting Media"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.messages[1]["text"] == "Keting Media"        # corregido
    assert any(m["text"] == "Software" for m in sess.messages)  # posterior conservada
    assert sess.messages[-1]["text"].startswith("Perfecto")  # siguiente pregunta añadida
```

Y actualizar el assert del test de turno inicial para que tolere el nuevo campo: el test `test_turn_inicia_sesion_y_responde` no necesita cambios (solo lee `message`/`done`).

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py -q`
Expected: FAIL (ruta `/edit` no existe).

- [ ] **Step 3: Schemas**

En `backend/app/schemas/todd.py`:
```python
class ToddTurnOut(BaseModel):
    message: str
    options: list[str] | None = None
    input: str = "text"
    done: bool = False
    areas_cubiertas: list[str] = []


class ToddSessionOut(BaseModel):
    status: str
    messages: list[ToddMessage]
    done: bool
    areas_cubiertas: list[str] = []


class ToddEditIn(BaseModel):
    answer_index: int
    nueva_respuesta: str
```
(Mantener `ToddTurnIn` y `ToddMessage` como están; solo agregar `areas_cubiertas` a `ToddTurnOut`/`ToddSessionOut` y el nuevo `ToddEditIn`.)

- [ ] **Step 4: Router**

En `backend/app/api/v1/todd/router.py`:

1. Ampliar imports:
```python
from app.schemas.todd import ToddTurnIn, ToddTurnOut, ToddSessionOut, ToddMessage, ToddEditIn
from app.services.ai.todd.agent import run_todd_turn, run_todd_edit, state_to_memory_buffer
```
2. En `get_todd`, incluir `areas_cubiertas` en la respuesta:
```python
    return ToddSessionOut(
        status=sess.status,
        messages=[ToddMessage(**m) for m in (sess.messages or [])],
        done=sess.status == "done",
        areas_cubiertas=list((sess.state or {}).get("areas_cubiertas") or []),
    )
```
3. En `todd_turn`, incluir `areas_cubiertas` en el `ToddTurnOut`:
```python
    return ToddTurnOut(
        message=turn["message"], options=turn["options"],
        input=turn["input"], done=turn["done"],
        areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []),
    )
```
4. Agregar el endpoint `todd_edit` (después de `todd_turn`):
```python
@router.post("/onboarding/todd/edit", response_model=ToddTurnOut)
async def todd_edit(
    body: ToddEditIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        raise HTTPException(status_code=404, detail="No hay entrevista activa.")
    messages = list(sess.messages or [])
    i = body.answer_index
    if i < 0 or i >= len(messages) or messages[i].get("role") != "user":
        raise HTTPException(status_code=400, detail="Índice de respuesta inválido.")

    # Transcript con la respuesta corregida en su lugar (se conserva todo para que Todd juzgue impacto).
    corrected = [dict(m) for m in messages]
    corrected[i] = {"role": "user", "text": body.nueva_respuesta, "options": None}
    edited_question = messages[i - 1].get("text", "") if i > 0 else ""

    turn = await anyio.to_thread.run_sync(
        lambda: run_todd_edit(corrected, edited_question, body.nueva_respuesta, sess.state or {})
    )

    if turn.get("reanudar_desde") == "rehacer":
        # Descarta lo posterior a la respuesta corregida y agrega la (re)pregunta de Todd.
        nuevos = corrected[: i + 1] + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    else:
        # Conserva las respuestas posteriores y agrega la siguiente pregunta.
        nuevos = corrected + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]

    sess.messages = nuevos
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages")
    flag_modified(sess, "state")
    await db.commit()

    return ToddTurnOut(
        message=turn["message"], options=turn["options"],
        input=turn["input"], done=turn["done"],
        areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []),
    )
```
Agregar `HTTPException` al import de fastapi (`from fastapi import APIRouter, Depends, Response, HTTPException`).

- [ ] **Step 5: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py -q && ./venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/todd.py backend/app/api/v1/todd/router.py backend/tests/integration/test_todd_api.py
git commit -m "feat(todd-form): endpoint /edit (continuar/rehacer) + areas_cubiertas en la API"
```

---

### Task 3: Frontend — wizard de formulario guiado + edición

**Files:**
- Modify: `frontend/src/lib/todd.ts`
- Rewrite: `frontend/src/app/onboarding/todd/page.tsx`
- Test: `npm run lint` + `npm run build`

**Interfaces:**
- Consumes: `GET /onboarding/todd` (+`areas_cubiertas`), `POST /onboarding/todd/turn`, `POST /onboarding/todd/edit`, `POST /onboarding/todd/close`.

- [ ] **Step 1: Cliente `lib/todd.ts`**

Reemplazar el contenido de `frontend/src/lib/todd.ts` por:
```typescript
import api from "@/lib/api"

export const TODD_AREAS = ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]

export interface ToddTurn {
  message: string
  options: string[] | null
  input: "text" | "single_choice"
  done: boolean
  areas_cubiertas: string[]
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
  areas_cubiertas: string[]
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

export async function editToddAnswer(answerIndex: number, nuevaRespuesta: string): Promise<ToddTurn> {
  const r = await api.post<ToddTurn>("/onboarding/todd/edit",
    { answer_index: answerIndex, nueva_respuesta: nuevaRespuesta })
  return r.data
}

export async function closeTodd(): Promise<void> {
  await api.post("/onboarding/todd/close")
}

// Pares {pregunta de Todd, respuesta del usuario} con el índice (en messages) de la respuesta.
export interface QAPair { msgIndex: number; question: string; answer: string; options: string[] | null }

export function buildQAPairs(messages: ToddMessage[]): QAPair[] {
  const pairs: QAPair[] = []
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === "user") {
      const q = i > 0 ? messages[i - 1] : null
      pairs.push({
        msgIndex: i,
        question: q?.text ?? "",
        answer: messages[i].text,
        options: q?.options ?? null,
      })
    }
  }
  return pairs
}
```

- [ ] **Step 2: Reescribir la página `frontend/src/app/onboarding/todd/page.tsx`**

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, ArrowLeft, Loader2, Pencil, X, Check } from "lucide-react"
import {
  ToddMessage, ToddTurn, QAPair, TODD_AREAS,
  getToddSession, sendToddAnswer, editToddAnswer, closeTodd, buildQAPairs,
} from "@/lib/todd"

const AREA_LABEL: Record<string, string> = {
  estrategia: "Estrategia", comercial: "Comercial", operativo: "Operativo",
  rh: "RH", financiero: "Financiero", legal: "Legal", familiar: "Familiar",
}

export default function ToddFormPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ToddMessage[]>([])
  const [turn, setTurn] = useState<ToddTurn | null>(null)
  const [areas, setAreas] = useState<string[]>([])
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [closing, setClosing] = useState(false)
  const [editing, setEditing] = useState(false)         // panel de edición abierto
  const [editPair, setEditPair] = useState<QAPair | null>(null)
  const [editText, setEditText] = useState("")
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getToddSession()
      .then(async sess => {
        if (sess && sess.messages.length > 0) {
          setMessages(sess.messages); setAreas(sess.areas_cubiertas)
          const last = sess.messages[sess.messages.length - 1]
          setTurn({ message: last.text, options: last.options,
            input: last.options ? "single_choice" : "text", done: sess.done,
            areas_cubiertas: sess.areas_cubiertas })
        } else {
          const t = await sendToddAnswer(null)
          setTurn(t); setAreas(t.areas_cubiertas)
          setMessages([{ role: "todd", text: t.message, options: t.options }])
        }
      })
      .catch(() => {})
  }, [])

  const applyTurn = (t: ToddTurn, userMsg?: string) => {
    setTurn(t); setAreas(t.areas_cubiertas)
    setMessages(prev => {
      const next = [...prev]
      if (userMsg) next.push({ role: "user", text: userMsg, options: null })
      next.push({ role: "todd", text: t.message, options: t.options })
      return next
    })
  }

  const answer = async (value: string) => {
    if (!value.trim() || busy) return
    setBusy(true); setText("")
    try {
      const t = await sendToddAnswer(value)
      applyTurn(t, value)
    } catch {
      /* deja el paso actual */
    } finally { setBusy(false) }
  }

  const finish = async () => {
    setClosing(true)
    try { await closeTodd(); router.push("/dashboard/diagnostico") }
    catch { setClosing(false) }
  }

  const openEdit = (p: QAPair) => { setEditPair(p); setEditText(p.answer) }

  const submitEdit = async () => {
    if (!editPair || !editText.trim() || busy) return
    setBusy(true)
    try {
      const t = await editToddAnswer(editPair.msgIndex, editText)
      // tras editar, recargar la sesión para reconstruir lista + pregunta actual
      const sess = await getToddSession()
      if (sess) {
        setMessages(sess.messages); setAreas(sess.areas_cubiertas)
        const last = sess.messages[sess.messages.length - 1]
        setTurn({ message: last.text, options: last.options,
          input: last.options ? "single_choice" : "text", done: sess.done,
          areas_cubiertas: sess.areas_cubiertas })
      } else {
        setTurn(t); setAreas(t.areas_cubiertas)
      }
      setEditPair(null); setEditing(false)
    } catch {
      /* mantiene el panel */
    } finally { setBusy(false) }
  }

  const pairs = buildQAPairs(messages)

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      {/* Progreso por áreas */}
      <header className="border-b border-gray-100 px-5 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-4">
          <span className="text-sm font-bold tracking-widest">TODD · GOBERNIA</span>
          <div className="flex flex-wrap gap-1.5">
            {TODD_AREAS.map(a => (
              <span key={a}
                className={`text-[10px] px-2 py-0.5 rounded-full border ${
                  areas.includes(a)
                    ? "bg-[var(--gob-navy)] text-[var(--gob-bone)] border-[var(--gob-navy)]"
                    : "text-gray-400 border-gray-200"
                }`}>
                {AREA_LABEL[a]}
              </span>
            ))}
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl">
          {/* Panel de edición */}
          {editing ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">¿En qué te equivocaste?</h2>
                <button onClick={() => { setEditing(false); setEditPair(null) }}
                  className="text-gray-400 hover:text-black"><X className="h-4 w-4" /></button>
              </div>
              {!editPair ? (
                <ul className="space-y-2">
                  {pairs.map(p => (
                    <li key={p.msgIndex}>
                      <button onClick={() => openEdit(p)}
                        className="w-full text-left border border-gray-100 rounded-xl p-3 hover:border-[var(--gob-navy)] transition-colors">
                        <p className="text-xs text-gray-400">{p.question}</p>
                        <p className="text-sm text-black flex items-center justify-between gap-2">
                          {p.answer} <Pencil className="h-3.5 w-3.5 text-gray-300 shrink-0" />
                        </p>
                      </button>
                    </li>
                  ))}
                  {pairs.length === 0 && <p className="text-sm text-gray-400">Aún no hay respuestas.</p>}
                </ul>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-gray-400">{editPair.question}</p>
                  {editPair.options && editPair.options.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {editPair.options.map(o => (
                        <button key={o} onClick={() => setEditText(o)}
                          className={`text-sm border rounded-full px-3 py-1.5 ${
                            editText === o ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                            : "border-gray-200"}`}>
                          {o}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <input value={editText} onChange={e => setEditText(e.target.value)}
                      className="w-full h-11 rounded-xl border-2 border-gray-100 px-4 text-sm focus:border-black focus:outline-none" />
                  )}
                  <div className="flex gap-2">
                    <button onClick={() => setEditPair(null)}
                      className="flex-1 text-sm text-gray-500">Cancelar</button>
                    <button onClick={submitEdit} disabled={busy || !editText.trim()}
                      className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-2.5 rounded-xl disabled:opacity-50">
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Guardar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            // Paso actual del formulario
            <AnimatePresence mode="wait">
              <motion.div key={turn?.message}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }} className="space-y-6">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center text-sm font-bold shrink-0">T</div>
                  <div>
                    <p className="text-xs font-medium text-gray-400">Todd</p>
                    <h2 className="text-lg font-bold text-black leading-snug">{turn?.message}</h2>
                  </div>
                </div>

                {turn && !turn.done && (
                  turn.options && turn.options.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {turn.options.map(o => (
                        <button key={o} disabled={busy} onClick={() => answer(o)}
                          className="text-sm border border-gray-200 rounded-xl px-4 py-2.5 hover:border-[var(--gob-navy)] hover:bg-gray-50 transition-colors disabled:opacity-50">
                          {o}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <form onSubmit={e => { e.preventDefault(); answer(text) }} className="space-y-3">
                      <textarea value={text} onChange={e => setText(e.target.value)} disabled={busy}
                        rows={3} placeholder="Tu respuesta…"
                        className="w-full rounded-xl border-2 border-gray-100 px-4 py-3 text-sm focus:border-black focus:outline-none resize-none" />
                      <button type="submit" disabled={busy || !text.trim()}
                        className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-40">
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Continuar <ArrowRight className="h-4 w-4" /></>}
                      </button>
                    </form>
                  )
                )}

                {turn?.done && (
                  <button onClick={finish} disabled={closing}
                    className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-50">
                    {closing ? <><Loader2 className="h-4 w-4 animate-spin" /> Preparando tu diagnóstico…</> : "Finalizar y ver mi diagnóstico"}
                  </button>
                )}

                {pairs.length > 0 && (
                  <button onClick={() => setEditing(true)}
                    className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
                    <ArrowLeft className="h-3.5 w-3.5" /> Atrás · corregir una respuesta
                  </button>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint` (por separado) y `cd frontend && npm run build`.
Expected: el build compila (exit 0); `lib/todd.ts` y `onboarding/todd/page.tsx` sin errores NUEVOS de lint (grep el output por `todd` para confirmar limpio; los pre-existentes en otros archivos no cuentan). Si `react-hooks/set-state-in-effect` marca el efecto inicial, nota que el `setState` va dentro de `.then()` async (no síncrono) — no debería marcar; si marcara, replica el patrón de `dashboard/plan/page.tsx`.

- [ ] **Step 4: Smoke (referencia)**

Con backend+frontend corriendo y sesión iniciada: `/onboarding/todd` muestra una pregunta por tarjeta con Todd arriba y el progreso por áreas; responder avanza; "Atrás" abre la lista de respuestas; editar una → continúa o repregunta; al `done`, "Finalizar" lleva al diagnóstico.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/todd.ts frontend/src/app/onboarding/todd/page.tsx
git commit -m "feat(todd-form-fe): formulario guiado paso a paso + edición con Atrás"
```

---

## Self-Review (cobertura del spec)

- **Wizard una pregunta por tarjeta + Todd avatar/encuadre + controles de form + progreso por 7 áreas** → Task 3 (page.tsx) + `areas_cubiertas` de Task 2. ✅
- **Edición con "Atrás" → lista de respuestas → corregir** → Task 3 (panel de edición + `buildQAPairs`) + Task 2 (endpoint `/edit`). ✅
- **Todd decide continuar/rehacer; si afecta avisa y repregunta; fallback rehacer** → Task 1 (`reanudar_desde` + `run_todd_edit` + sin-API-key→rehacer) + Task 2 (router aplica truncado/conserva). ✅
- **Backend reutilizado, cambios aditivos** → sí (`reanudar_desde` opcional, `run_todd_edit` nuevo, endpoint nuevo). ✅
- **Sin migración** → reusa `todd_sessions`. ✅

Consistencia de tipos: `run_todd_edit(messages, edited_question, new_answer, state)` → turno con `reanudar_desde`; el router lo consume y aplica truncar (rehacer) / conservar (continuar). `ToddTurnOut`/`ToddSessionOut` ganan `areas_cubiertas: list[str]`; el front lo lee en `ToddTurn`/`ToddSession`. `editToddAnswer(answerIndex, nuevaRespuesta)` → `POST /edit {answer_index, nueva_respuesta}` (coincide con `ToddEditIn`). `buildQAPairs` usa `msgIndex` = índice del mensaje `user` en `messages`, que es el `answer_index` que espera el endpoint.

Puntos a verificar al implementar: que `HTTPException` quede importado en el router; que los helpers/`MOCK_USER_ID` del test de Todd ya existan (reusar, no redefinir); el nombre del componente exportado por `page.tsx` (default export, cualquier nombre sirve).
