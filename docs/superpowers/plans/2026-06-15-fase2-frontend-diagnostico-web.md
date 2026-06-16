# Fase 2 (Frontend) — Diagnóstico estratégico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el frontend del Diagnóstico estratégico: ítem en el sidebar, página dedicada con estados (vacío/generando/listo/error) + vista tipo revista + descarga PDF, campos web/competidores en la Etapa 1, y ocultar el viejo "Diagnóstico por área".

**Architecture:** Una página `/dashboard/diagnostico` que hace polling del estado (igual que la página del plan) y muestra los 4 estados. Un cliente API tipado (`lib/diagnostico.ts`) consume los endpoints del backend (ya implementados). El form de Etapa 1 gana dos inputs opcionales (web + competidores). Se quita la sección "Diagnóstico por área" del Inicio.

**Tech Stack:** Next.js 16 App Router (client components; ver `frontend/AGENTS.md`), TypeScript, framer-motion, lucide-react, axios vía `@/lib/api` (baseURL incluye `/api/v1`), Tailwind v4 (`--gob-navy`/`--gob-bone`/`--gob-ink`).

**Verificación:** Sin suite de UI. Gate: `npm run lint` + `npm run build` + smoke manual (descrito por tarea). Comandos desde `frontend/`. Errores de lint preexistentes en `datos/page.tsx`, `sesion/[id]/plan/page.tsx`, `onboarding/` están fuera de alcance.

**Dependencia:** El backend de la Fase 2 (endpoints `/api/v1/diagnostico/{generate,status,pdf}` y GET) ya existe en esta misma rama.

---

### Task 1: Cliente API + ítem en el sidebar

**Files:**
- Create: `frontend/src/lib/diagnostico.ts`
- Modify: `frontend/src/components/ui/Sidebar.tsx`

- [ ] **Step 1: Crear `frontend/src/lib/diagnostico.ts`**

```ts
import api from "@/lib/api"

export type DiagnosticoStatus = "generating" | "active" | "failed"

export interface DiagnosticoSection {
  key: string
  title: string
  body: string
}

export interface DiagnosticoSource {
  title: string
  url: string
}

export interface Diagnostico {
  status: DiagnosticoStatus
  fail_reason: string | null
  sections: DiagnosticoSection[]
  sources: DiagnosticoSource[]
}

export interface DiagnosticoStatusOut {
  status: DiagnosticoStatus
  fail_reason: string | null
}

export async function getDiagnosticoStatus(): Promise<DiagnosticoStatusOut> {
  const r = await api.get<DiagnosticoStatusOut>("/diagnostico/status")
  return r.data
}

export async function getDiagnostico(): Promise<Diagnostico> {
  const r = await api.get<Diagnostico>("/diagnostico")
  return r.data
}

export async function generateDiagnostico(): Promise<DiagnosticoStatusOut> {
  const r = await api.post<DiagnosticoStatusOut>("/diagnostico/generate")
  return r.data
}

export async function downloadDiagnosticoPdf(): Promise<void> {
  const r = await api.get("/diagnostico/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "diagnostico.pdf"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Agregar el ítem "Diagnóstico" al sidebar**

En `frontend/src/components/ui/Sidebar.tsx`:
- En el import de lucide, agregar `FileSearch`:
  ```tsx
  import {
    Home, CalendarDays, ClipboardList, CheckSquare, Users,
    FileSearch,
    Settings, LogOut, Menu, X,
  } from "lucide-react"
  ```
- En el array `LINKS`, agregar el ítem después de "Plan" (queda: Inicio · Sesión del mes · Plan · Diagnóstico · Compromisos · Tu consejo):
  ```tsx
    { href: "/dashboard/plan", label: "Plan", exact: false, icon: ClipboardList },
    { href: "/dashboard/diagnostico", label: "Diagnóstico", exact: false, icon: FileSearch },
    { href: "/dashboard/compromisos", label: "Compromisos", exact: false, icon: CheckSquare },
  ```

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan. (El ítem apunta a `/dashboard/diagnostico`, que se crea en Task 2; hasta entonces da 404 al navegar — se resuelve en la siguiente tarea.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/diagnostico.ts frontend/src/components/ui/Sidebar.tsx
git commit -m "feat(fase2-fe): cliente API del diagnóstico + ítem en el sidebar"
```

---

### Task 2: Página del diagnóstico (estados + vista revista + PDF)

**Files:**
- Create: `frontend/src/app/dashboard/diagnostico/page.tsx`

Mirror del patrón de estados/polling de `frontend/src/app/dashboard/plan/page.tsx` (View type, `pollRef` con `setInterval` cada 2.5s, `init` que ramifica por status).

- [ ] **Step 1: Crear la página**

```tsx
"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Sparkles, AlertCircle, Download, FileSearch } from "lucide-react"
import {
  getDiagnostico, getDiagnosticoStatus, generateDiagnostico, downloadDiagnosticoPdf,
  type Diagnostico,
} from "@/lib/diagnostico"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

export default function DiagnosticoPage() {
  const [view, setView] = useState<View>("loading")
  const [diag, setDiag] = useState<Diagnostico | null>(null)
  const [failReason, setFailReason] = useState<"datos" | "general" | null>(null)
  const [failDetail, setFailDetail] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const loadDiag = useCallback(async () => {
    const d = await getDiagnostico()
    setDiag(d)
    setView("active")
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const s = await getDiagnosticoStatus()
        if (s.status === "active") { stopPolling(); await loadDiag() }
        else if (s.status === "failed") { stopPolling(); setFailReason("general"); setView("failed") }
      } catch { /* reintenta en el próximo tick */ }
    }, 2500)
  }, [stopPolling, loadDiag])

  const init = useCallback(async () => {
    try {
      const s = await getDiagnosticoStatus()
      if (s.status === "generating") { setView("generating"); startPolling() }
      else if (s.status === "failed") { setView("failed") }
      else await loadDiag()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) setView("none")
      else setView("error")
    }
  }, [startPolling, loadDiag])

  useEffect(() => { init(); return () => stopPolling() }, [init, stopPolling])

  const onGenerate = async () => {
    setView("generating")
    setFailReason(null); setFailDetail(null)
    try {
      await generateDiagnostico()
      startPolling()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 400) { setFailReason("datos"); setFailDetail(detail ?? null) }
      else setFailReason("general")
      setView("failed")
    }
  }

  const onDownload = async () => {
    setDownloading(true)
    try { await downloadDiagnosticoPdf() } catch { /* noop */ } finally { setDownloading(false) }
  }

  // ── loading ──
  if (view === "loading") {
    return <div className="min-h-dvh bg-white flex items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
    </div>
  }

  // ── generating ──
  if (view === "generating") {
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--gob-navy)]" />
        <div className="space-y-1">
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Investigando</p>
          <h1 className="text-2xl font-bold text-black">Tu consejo está investigando tu empresa en la web</h1>
          <p className="text-sm text-gray-500 max-w-md">
            Analiza tu presencia digital, competidores reales, tendencias de mercado y contexto de tu región.
            Esto puede tardar unos minutos.
          </p>
        </div>
      </div>
    )
  }

  // ── none / failed / error ──
  if (view === "none" || view === "failed" || view === "error") {
    const isFail = view === "failed" || view === "error"
    const isDatos = isFail && failReason === "datos"
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
          {isFail ? <AlertCircle className="h-5 w-5 text-red-400" /> : <FileSearch className="h-5 w-5 text-gray-300" />}
        </div>
        <div className="space-y-2 max-w-md">
          <p className="text-base font-medium text-black">
            {isDatos ? "Completa los datos de tu empresa"
              : isFail ? "No se pudo generar el diagnóstico"
              : "Genera tu diagnóstico estratégico"}
          </p>
          <p className="text-sm text-gray-500 leading-relaxed">
            {isDatos ? (failDetail ?? "Para investigar tu empresa necesito tu página web y tus competidores. Complétalos en tu onboarding.")
              : isFail ? "Algo falló al investigar. Puedes reintentarlo."
              : "Investigaré tu empresa en la web —presencia digital, competidores reales, mercado y contexto— y armaré un diagnóstico con fuentes. Tarda unos minutos."}
          </p>
        </div>
        {isDatos ? (
          <Link href="/onboarding/etapa-1"
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
            Completar mis datos
          </Link>
        ) : (
          <button onClick={onGenerate}
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
            <Sparkles className="h-4 w-4" /> {isFail ? "Reintentar" : "Generar diagnóstico"}
          </button>
        )}
      </div>
    )
  }

  // ── active: vista tipo revista ──
  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      <main>
        <div className="w-full max-w-3xl mx-auto px-[var(--px-fluid)] py-12 space-y-8">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }} className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Diagnóstico estratégico</p>
              <h1 className="text-3xl font-bold text-black tracking-tight">La realidad de tu empresa</h1>
            </div>
            <button onClick={onDownload} disabled={downloading}
              className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-4 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50">
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
          </motion.div>

          {(diag?.sections ?? []).map((s, i) => {
            const highlight = s.key === "competencia"
            return (
              <motion.section key={s.key} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: EASE, delay: 0.05 + i * 0.05 }}
                className={`space-y-3 ${highlight ? "border-l-2 border-[var(--gob-navy)] pl-5" : ""}`}>
                <h2 className="text-xl font-bold text-black tracking-tight">{s.title}</h2>
                <div className="space-y-3">
                  {(s.body || "").split("\n").filter(p => p.trim()).map((p, j) => (
                    <p key={j} className="text-[15px] text-gray-700 leading-relaxed">{p.trim()}</p>
                  ))}
                  {!s.body && <p className="text-sm text-gray-300 italic">Sin contenido.</p>}
                </div>
              </motion.section>
            )
          })}

          {(diag?.sources ?? []).length > 0 && (
            <section className="space-y-2 pt-4 border-t border-gray-100">
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Fuentes</p>
              <ul className="space-y-1">
                {diag!.sources.map((src, i) => (
                  <li key={i} className="text-xs text-gray-500">
                    <a href={src.url} target="_blank" rel="noopener noreferrer"
                      className="hover:text-[var(--gob-navy)] underline decoration-gray-200">
                      {src.title}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="pt-4">
            <button onClick={onGenerate}
              className="text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
              Regenerar diagnóstico
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 2: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan. `/dashboard/diagnostico` aparece como ruta.

- [ ] **Step 3: Smoke (referencia humana)**

Sin navegador en el subagente; basta con que build pase. Para el verificador: con un usuario con web+competidores, "Generar diagnóstico" → pantalla de investigación → al terminar, vista revista con secciones + fuentes + PDF. Usuario sin esos datos → estado "Completa los datos" con link al onboarding.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/diagnostico/page.tsx
git commit -m "feat(fase2-fe): página del diagnóstico (estados + vista revista + PDF)"
```

---

### Task 3: Campos web + competidores en la Etapa 1 del onboarding

**Files:**
- Modify: `frontend/src/app/onboarding/etapa-1/page.tsx`

**Contexto:** Es un wizard de ~764 líneas con un objeto de estado `form` (`useState({...})` ~línea 146), navegación por `subStep`, e `handleSubmit` (~línea 213) que arma `payload` y lo envía a `POST /onboarding/${sid}/etapa-1`. Los campos nuevos son **opcionales** (no bloquean el wizard); solo se agregan al estado, a un substep visible, y al payload.

- [ ] **Step 1: Leer el archivo** para ubicar: el objeto inicial de `form` (useState), el `payload` dentro de `handleSubmit`, y un substep adecuado donde insertar los inputs (p. ej. el mismo bloque donde se captura el nombre/ubicación de la empresa, o un substep propio si el patrón lo permite fácilmente). NO reestructurar la navegación.

- [ ] **Step 2: Agregar al estado inicial `form`**

En el objeto de `useState({...})`, agregar:
```tsx
    website: "",
    competitors: [] as string[],
```
Y en el `setForm(f => ({...}))` de hidratación (donde se rellena desde `c` = company del backend, ~línea 177), agregar:
```tsx
        website:     c.website ?? "",
        competitors: c.competitors ?? [],
```

- [ ] **Step 3: Agregar al `payload` de `handleSubmit`**

Dentro del objeto `payload` (~línea 223), agregar:
```tsx
        website:     form.website.trim() || null,
        competitors: form.competitors,
```

- [ ] **Step 4: Renderizar los inputs en un substep visible**

Insertar este bloque dentro de la JSX de un substep existente (siguiendo el estilo de los inputs del form — p. ej. justo después de los inputs de ubicación). Es autocontenido (input de web + chips de competidores con agregar/quitar). Usa un estado local para el texto del competidor en curso:

Cerca de los otros `useState` del componente, agregar:
```tsx
  const [competidorInput, setCompetidorInput] = useState("")
```

JSX a insertar (un bloque, opcional para el usuario):
```tsx
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Página web de tu empresa
                </label>
                <input
                  type="url"
                  placeholder="https://tuempresa.com"
                  value={form.website}
                  onChange={e => setForm(f => ({ ...f, website: e.target.value }))}
                  className="w-full h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
                />
                <p className="text-xs text-gray-400">La usa tu consejo para investigar tu presencia digital real.</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Competidores que crees tener
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Nombre de un competidor"
                    value={competidorInput}
                    onChange={e => setCompetidorInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === "Enter") {
                        e.preventDefault()
                        const v = competidorInput.trim()
                        if (v && form.competitors.length < 10 && !form.competitors.includes(v)) {
                          setForm(f => ({ ...f, competitors: [...f.competitors, v] }))
                        }
                        setCompetidorInput("")
                      }
                    }}
                    className="flex-1 h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const v = competidorInput.trim()
                      if (v && form.competitors.length < 10 && !form.competitors.includes(v)) {
                        setForm(f => ({ ...f, competitors: [...f.competitors, v] }))
                      }
                      setCompetidorInput("")
                    }}
                    className="px-4 rounded-xl border-2 border-gray-100 text-sm font-medium text-gray-600 hover:border-gray-300"
                  >
                    Agregar
                  </button>
                </div>
                {form.competitors.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {form.competitors.map(c => (
                      <span key={c} className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-700 rounded-full pl-3 pr-1.5 py-1">
                        {c}
                        <button
                          type="button"
                          onClick={() => setForm(f => ({ ...f, competitors: f.competitors.filter(x => x !== c) }))}
                          className="text-gray-400 hover:text-gray-700"
                          aria-label={`Quitar ${c}`}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-400">Tu consejo los contrasta con la competencia real que encuentre.</p>
              </div>
            </div>
```

> Nota: si el bloque donde se hidrata `c` usa un tipo TypeScript explícito para `company` (sin `website`/`competitors`), agregar esos campos opcionales al tipo o usar `(c as { website?: string; competitors?: string[] })`. Que `npm run lint && npm run build` pase sin errores de tipos.

- [ ] **Step 5: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores nuevos.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/onboarding/etapa-1/page.tsx
git commit -m "feat(fase2-fe): campos web+competidores (opcionales) en la Etapa 1"
```

---

### Task 4: Ocultar "Diagnóstico por área" del Inicio

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Quitar la sección**

En `frontend/src/app/dashboard/page.tsx`, eliminar el bloque JSX de "Diagnóstico por área" — el `<motion.div>` condicionado por `completedStages.includes(4) && summary?.diagnostic_area_completion` que renderiza el encabezado "Etapa 4" / "Diagnóstico por área" y el grid de `diagnostic_area_completion`. Eliminar también el estado `expandedArea`/`setExpandedArea` si queda sin uso tras quitar la sección, y cualquier import que quede sin usar (lo indicará `npm run lint`).

- [ ] **Step 2: lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: pasan sin errores nuevos (sin variables/imports sin usar introducidos).

- [ ] **Step 3: Smoke (referencia)**

El Inicio ya no muestra "Diagnóstico por área". El resto del Inicio (saludo, score, checklist, plan, sesiones) permanece.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx
git commit -m "feat(fase2-fe): ocultar 'Diagnóstico por área' del Inicio"
```

---

## Self-Review (cobertura del spec — Componente 7)

- **Cliente API + tipos** → Task 1 (`lib/diagnostico.ts`). ✅
- **Ítem "Diagnóstico" en el sidebar** → Task 1. ✅
- **Página con estados (none/generating/failed/active) + polling** → Task 2 (mirror de plan/page.tsx). ✅
- **Vista tipo revista (6 secciones, "competencia" destacada, fuentes)** → Task 2. ✅
- **Descarga PDF** → Task 1 (`downloadDiagnosticoPdf`, blob+auth) + Task 2 (botón). ✅
- **Compuerta de datos en UI (400 → "Completa tus datos" + link onboarding)** → Task 2 (`onGenerate` maneja 400). ✅
- **Campos web+competidores en Etapa 1 (opcionales)** → Task 3. ✅
- **Ocultar "Diagnóstico por área"** → Task 4. ✅

Consistencia de tipos: `Diagnostico`/`DiagnosticoSection`/`DiagnosticoSource` de `lib/diagnostico.ts` coinciden con la forma que devuelve el backend (`DiagnosticoOut`: status, fail_reason, sections[{key,title,body}], sources[{title,url}]). El polling usa los mismos status (`generating/active/failed`) que el backend. Las rutas del cliente (`/diagnostico`, `/diagnostico/status`, `/diagnostico/generate`, `/diagnostico/pdf`) corresponden a los endpoints registrados con prefix `/api/v1` (el axios `@/lib/api` ya incluye `/api/v1`).

Orden: Task 1 → 2 (la página usa el cliente). Task 3 y 4 son independientes.
