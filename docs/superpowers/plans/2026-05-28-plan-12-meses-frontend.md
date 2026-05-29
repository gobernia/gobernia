# Frontend Plan de 12 meses (Subproyecto A.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la interfaz `/dashboard/plan` que muestra y permite editar el plan estratégico de 12 meses (tira de tiempo + mes enfocado con objetivos→tareas), con pantalla de generación, diagnóstico, y un script backend de sembrado para probar local.

**Architecture:** Una página cliente `dashboard/plan/page.tsx` orquesta los estados (sin-plan / generando / falló / activo), hace polling de `/annual-plan/status` mientras genera, y maneja mutaciones optimistas. La UI se compone de componentes presentacionales enfocados bajo `components/plan/`. Los datos se acceden por funciones tipadas en `lib/annualPlan.ts` sobre el `api` axios existente.

**Tech Stack:** Next.js 16.2.4 (App Router, "use client"), TypeScript, Tailwind v4 (variables de marca `--gob-navy`/`--gob-bone`), framer-motion, lucide-react, axios. Backend: FastAPI + SQLAlchemy async (solo el script de sembrado).

**Spec:** `docs/superpowers/specs/2026-05-28-plan-12-meses-frontend-design.md`
**Rama:** `feat/plan-12-meses-frontend` (ya creada desde main).

---

## Notas de entorno (leer antes de empezar)

- **`frontend/AGENTS.md`:** esta versión de Next.js (16.x) puede diferir de tu conocimiento previo. Antes de escribir frontend, revisa `frontend/node_modules/next/dist/docs/` si dudas de una API. Sigue los patrones ya usados en `frontend/src/app/dashboard/sesion/[id]/plan/page.tsx` (página cliente, axios `@/lib/api`, framer-motion, drawer de edición).
- **Comandos:** desde `frontend/`. Gate de verificación por tarea: `npx tsc --noEmit` (typecheck) y `npm run lint`. No hay framework de tests; la verificación funcional es manual en local (Task 9).
- **`api` (`@/lib/api`):** axios con `baseURL` que ya incluye `/api/v1` y un interceptor que inyecta el token Supabase. Las rutas se pasan relativas, p.ej. `api.get("/annual-plan")`.
- **Marca:** fondo blanco, texto negro, grises; `var(--gob-navy)` (#142849) y `var(--gob-bone)` (#F4F1EC) para activo/botones. Contenedor `max-w-[var(--container-fluid)]`, padding `px-[var(--px-fluid)]`.
- **Backend ya desplegado** expone: `GET /annual-plan`, `GET /annual-plan/status`, `POST /annual-plan/generate`, `POST /annual-plan/objectives`, `PATCH /annual-plan/objectives/{id}`, `DELETE /annual-plan/objectives/{id}`, `POST /annual-plan/tasks`, y los existentes `PATCH /tasks/{id}` y `DELETE /tasks/{id}`.

---

## Estructura de archivos

**Crear:**
- `frontend/src/lib/annualPlan.ts` — tipos + funciones de API.
- `frontend/src/components/plan/AgentsCollaboration.tsx` — animación compartida (extraída).
- `frontend/src/components/plan/DiagnosticoPanel.tsx` — diagnóstico colapsable.
- `frontend/src/components/plan/MonthTimeline.tsx` — tira de 12 meses.
- `frontend/src/components/plan/TaskDrawer.tsx` — drawer de edición de tarea.
- `frontend/src/components/plan/TaskRow.tsx` — fila de tarea.
- `frontend/src/components/plan/ObjectiveCard.tsx` — objetivo + sus tareas.
- `frontend/src/components/plan/MonthDetail.tsx` — detalle del mes enfocado.
- `frontend/src/app/dashboard/plan/page.tsx` — página orquestadora.
- `backend/scripts/seed_sample_annual_plan.py` — sembrado de datos de muestra.

**Modificar:**
- `frontend/src/app/dashboard/sesion/[id]/page.tsx` — usar el `AgentsCollaboration` extraído.
- `frontend/src/app/onboarding/etapa-8/page.tsx` — redirigir a `/dashboard/plan` al completar.
- `frontend/src/app/dashboard/page.tsx` — tarjeta de entrada al plan.

---

## Task 1: Capa de datos (tipos + funciones API)

**Files:**
- Create: `frontend/src/lib/annualPlan.ts`

- [ ] **Step 1: Crear `frontend/src/lib/annualPlan.ts`**

```typescript
import api from "@/lib/api"

export type TaskStatus = "pendiente" | "en_progreso" | "completada"
export type TaskPriority = "alta" | "media" | "baja"
export type PlanStatus = "generating" | "active" | "failed" | "completed"

export interface Task {
  id: string
  plan_id: string | null
  objective_id: string | null
  kpi_ref: string | null
  title: string
  description: string | null
  source_agent: string | null
  status: TaskStatus
  priority: TaskPriority
  owner: string | null
  due_date: string | null
  tags: string[]
  order_index: number
  created_at: string
  updated_at: string
}

export interface Objective {
  id: string
  title: string
  description: string | null
  kpi_refs: string[]
  order_index: number
  tasks: Task[]
}

export interface MonthlyPlan {
  id: string
  month_index: number
  period_year: number
  period_month: number
  focus: string | null
  status: "locked" | "active" | "done"
  review: Record<string, unknown> | null
  objectives: Objective[]
}

export interface AnnualPlan {
  id: string
  title: string
  start_date: string
  status: PlanStatus
  diagnostico_summary: string | null
  genesis_session_id: string | null
  months: MonthlyPlan[]
}

export interface AnnualPlanStatus {
  status: PlanStatus
  active_month_index: number | null
}

export const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

export async function getAnnualPlan(): Promise<AnnualPlan> {
  const r = await api.get<AnnualPlan>("/annual-plan")
  return r.data
}

export async function getAnnualPlanStatus(): Promise<AnnualPlanStatus> {
  const r = await api.get<AnnualPlanStatus>("/annual-plan/status")
  return r.data
}

export async function generateAnnualPlan(): Promise<AnnualPlanStatus> {
  const r = await api.post<AnnualPlanStatus>("/annual-plan/generate")
  return r.data
}

export async function createObjective(body: {
  monthly_plan_id: string
  title: string
  description?: string | null
  kpi_refs?: string[]
}): Promise<Objective> {
  const r = await api.post<Objective>("/annual-plan/objectives", body)
  return r.data
}

export async function updateObjective(
  id: string,
  patch: Partial<Pick<Objective, "title" | "description" | "kpi_refs" | "order_index">>,
): Promise<Objective> {
  const r = await api.patch<Objective>(`/annual-plan/objectives/${id}`, patch)
  return r.data
}

export async function deleteObjective(id: string): Promise<void> {
  await api.delete(`/annual-plan/objectives/${id}`)
}

export async function createTask(body: {
  objective_id: string
  title: string
  description?: string | null
  status?: TaskStatus
  priority?: TaskPriority
  owner?: string | null
  due_date?: string | null
  kpi_ref?: string | null
  tags?: string[]
}): Promise<Task> {
  const r = await api.post<Task>("/annual-plan/tasks", body)
  return r.data
}

export async function updateTask(id: string, patch: Partial<Task>): Promise<Task> {
  const r = await api.patch<Task>(`/tasks/${id}`, patch)
  return r.data
}

export async function deleteTask(id: string): Promise<void> {
  await api.delete(`/tasks/${id}`)
}
```

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: sin errores (exit 0).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/annualPlan.ts
git commit -m "feat(plan-fe): capa de datos y tipos del plan anual"
```

---

## Task 2: Extraer AgentsCollaboration a componente compartido

**Files:**
- Create: `frontend/src/components/plan/AgentsCollaboration.tsx`
- Modify: `frontend/src/app/dashboard/sesion/[id]/page.tsx`

- [ ] **Step 1: Crear `frontend/src/components/plan/AgentsCollaboration.tsx`**

Mueve la animación (hoy embebida en la página de sesión) a un componente reutilizable. Acepta props opcionales de copy para reusarla en la generación del plan.

```tsx
"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const AGENTS = [
  { id: "CFO", role: "Finanzas" },
  { id: "CSO", role: "Estrategia" },
  { id: "CRO", role: "Riesgos" },
  { id: "Auditor", role: "Gobierno" },
]

const PIPELINE_AGENTS = ["CFO", "CSO", "CRO", "Auditor"] as const
const PHASES = ["analiza", "challenge", "revisa"] as const
type Phase = (typeof PHASES)[number]
type PipelineAgent = (typeof PIPELINE_AGENTS)[number]

const AGENT_ANGLES: Record<PipelineAgent, number> = {
  CFO: 270, CSO: 0, CRO: 90, Auditor: 180,
}

const PHASE_COPY: Record<Phase, (agent: PipelineAgent) => string> = {
  analiza:   a => `${a} está analizando tu información…`,
  challenge: a => `Challenger aplica pre-mortem al ${a}…`,
  revisa:    a => `${a} revisa su análisis con la crítica…`,
}

export default function AgentsCollaboration({
  caption = "Cada agente entrega su diagnóstico al Challenger, que imagina cómo podría fracasar en 12 meses y devuelve la crítica antes de mostrarte el resultado.",
}: {
  caption?: string
}) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setStep(s => s + 1), 1400)
    return () => clearInterval(t)
  }, [])

  const agent = PIPELINE_AGENTS[Math.floor(step / 3) % PIPELINE_AGENTS.length]
  const phase = PHASES[step % PHASES.length]

  const size = 260
  const radius = 100
  const c = size / 2

  const pos = (a: PipelineAgent) => {
    const rad = (AGENT_ANGLES[a] * Math.PI) / 180
    return { x: c + radius * Math.cos(rad), y: c + radius * Math.sin(rad) }
  }

  const active = pos(agent)
  const packetFrom = phase === "challenge" ? active : { x: c, y: c }
  const packetTo   = phase === "challenge" ? { x: c, y: c } : active

  return (
    <div className="flex flex-col items-center gap-7">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="absolute inset-0 overflow-visible">
          {PIPELINE_AGENTS.map(a => {
            const p = pos(a)
            const isActive = a === agent
            return (
              <line
                key={a}
                x1={c} y1={c} x2={p.x} y2={p.y}
                stroke={isActive ? "#000" : "#e5e7eb"}
                strokeWidth={isActive ? 1.5 : 1}
                strokeDasharray={isActive ? "0" : "3 4"}
              />
            )
          })}
          <circle cx={c} cy={c} r={radius} fill="none" stroke="#f3f4f6" strokeWidth={1} />
          <motion.circle
            key={`${agent}-${phase}-${step}`}
            r={4}
            fill="#000"
            initial={{ cx: packetFrom.x, cy: packetFrom.y, opacity: 0 }}
            animate={{
              cx: [packetFrom.x, packetTo.x],
              cy: [packetFrom.y, packetTo.y],
              opacity: [0, 1, 1, 0],
            }}
            transition={{ duration: 1.2, ease: EASE, times: [0, 0.15, 0.85, 1] }}
          />
        </svg>

        {PIPELINE_AGENTS.map(a => {
          const p = pos(a)
          const isActive = a === agent
          const meta = AGENTS.find(x => x.id === a)!
          return (
            <motion.div
              key={a}
              className="absolute flex flex-col items-center pointer-events-none"
              style={{ left: p.x - 28, top: p.y - 28, width: 56 }}
              animate={{ scale: isActive ? 1.1 : 1 }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              <div className={`w-12 h-12 rounded-2xl border-2 flex items-center justify-center transition-colors ${
                isActive
                  ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                  : "border-gray-200 bg-white text-gray-400"
              }`}>
                <span className="text-sm font-bold">{a[0]}</span>
              </div>
              <span className={`text-[9px] mt-1.5 font-medium tracking-wide ${isActive ? "text-black" : "text-gray-400"}`}>{a}</span>
              <span className="text-[8px] text-gray-300 leading-none mt-0.5">{meta.role}</span>
            </motion.div>
          )
        })}

        <motion.div
          className="absolute flex flex-col items-center pointer-events-none"
          style={{ left: c - 34, top: c - 34, width: 68 }}
          animate={{ scale: phase === "challenge" ? 1.12 : 1 }}
          transition={{ duration: 0.35, ease: EASE }}
        >
          <div className={`w-14 h-14 rounded-2xl border-2 flex items-center justify-center transition-colors ${
            phase === "challenge"
              ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
              : "border-gray-300 bg-white text-gray-500"
          }`}>
            <span className="text-[10px] font-black tracking-tight">PRE</span>
          </div>
          <span className={`text-[9px] mt-1.5 font-medium tracking-wide ${phase === "challenge" ? "text-black" : "text-gray-500"}`}>Challenger</span>
          <span className="text-[8px] text-gray-400 leading-none mt-0.5">Pre-mortem</span>
        </motion.div>
      </div>

      <div className="space-y-2 text-center max-w-md">
        <motion.p
          key={`${agent}-${phase}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="text-sm font-medium text-black"
        >
          {PHASE_COPY[phase](agent)}
        </motion.p>
        <p className="text-xs text-gray-400 leading-relaxed">{caption}</p>

        <div className="flex items-center justify-center gap-4 pt-3">
          {PIPELINE_AGENTS.map(a => (
            <div key={a} className="flex items-center gap-1.5">
              <span className={`text-[10px] font-medium tracking-wide ${a === agent ? "text-black" : "text-gray-300"}`}>{a}</span>
              <div className="flex gap-0.5">
                {PHASES.map((p, i) => {
                  const ai = PIPELINE_AGENTS.indexOf(a)
                  const cur = PIPELINE_AGENTS.indexOf(agent)
                  const done = ai < cur || (ai === cur && i < PHASES.indexOf(phase))
                  const isNow = a === agent && p === phase
                  return (
                    <div key={p} className={`h-1 w-3 rounded-full transition-colors ${
                      isNow ? "bg-[var(--gob-navy)]" : done ? "bg-gray-400" : "bg-gray-100"
                    }`} />
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Refactorizar `frontend/src/app/dashboard/sesion/[id]/page.tsx` para usar el componente extraído**

1. Borra del archivo el bloque embebido: las constantes `PIPELINE_AGENTS`, `PHASES`, `Phase`, `PipelineAgent`, `AGENT_ANGLES`, `PHASE_COPY` y la función completa `function AgentsCollaboration() { … }` (líneas ~24-27 y ~57-253; el bloque comentado "Collaboration animation").
2. Agrega el import al inicio: `import AgentsCollaboration from "@/components/plan/AgentsCollaboration"`.
3. La constante `AGENTS` (líneas 17-22) se sigue usando en el resto de la página de sesión — NO la borres si se usa fuera de la animación; si tras quitar la animación queda sin usos, bórrala. Verifica con el typecheck/lint del Step 3 (un `AGENTS` sin usar lo marca el lint).
4. Donde antes se renderizaba `<AgentsCollaboration />` no cambia nada (mismo nombre de componente, ahora importado).

- [ ] **Step 3: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: sin errores. Si `lint` marca `AGENTS` o `EASE` como no usados en la página de sesión, elimínalos de esa página (quedaron sólo para la animación que ya moviste).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/AgentsCollaboration.tsx frontend/src/app/dashboard/sesion/[id]/page.tsx
git commit -m "refactor(plan-fe): extraer AgentsCollaboration a componente compartido"
```

---

## Task 3: DiagnosticoPanel + MonthTimeline

**Files:**
- Create: `frontend/src/components/plan/DiagnosticoPanel.tsx`
- Create: `frontend/src/components/plan/MonthTimeline.tsx`

- [ ] **Step 1: Crear `frontend/src/components/plan/DiagnosticoPanel.tsx`**

El `diagnostico_summary` viene como texto con líneas tipo `**CFO:** resumen…` separadas por doble salto de línea. Lo renderizamos legible (negritas del agente + texto), colapsable.

```tsx
"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChevronDown, Sparkles } from "lucide-react"

function renderLine(line: string, i: number) {
  const m = line.match(/^\*\*(.+?):\*\*\s*(.*)$/)
  if (m) {
    return (
      <p key={i} className="text-sm text-gray-600 leading-relaxed">
        <span className="font-bold text-black">{m[1]}:</span> {m[2]}
      </p>
    )
  }
  return <p key={i} className="text-sm text-gray-600 leading-relaxed">{line}</p>
}

export default function DiagnosticoPanel({ summary }: { summary: string | null }) {
  const [open, setOpen] = useState(true)
  if (!summary) return null

  const lines = summary.split("\n").filter(l => l.trim().length > 0)

  return (
    <div className="border border-gray-100 rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Sparkles className="h-4 w-4 text-[var(--gob-navy)]" />
          <span className="text-sm font-bold text-black">Diagnóstico del consejo</span>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="h-4 w-4 text-gray-400" />
        </motion.div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-2.5 border-t border-gray-50 pt-4">
              {lines.map(renderLine)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
```

- [ ] **Step 2: Crear `frontend/src/components/plan/MonthTimeline.tsx`**

```tsx
"use client"

import type { MonthlyPlan } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"

export default function MonthTimeline({
  months, selectedIndex, onSelect,
}: {
  months: MonthlyPlan[]
  selectedIndex: number
  onSelect: (monthIndex: number) => void
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
      {months.map(m => {
        const isSelected = m.month_index === selectedIndex
        const isActive = m.status === "active"
        const isDone = m.status === "done"
        return (
          <button
            key={m.id}
            onClick={() => onSelect(m.month_index)}
            className={`snap-start flex-shrink-0 w-28 text-left rounded-xl border-2 px-3 py-2.5 transition-all ${
              isSelected
                ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                : "border-gray-100 bg-white text-gray-500 hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-medium uppercase tracking-wide opacity-70">
                Mes {m.month_index}
              </span>
              {isActive && !isSelected && (
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--gob-navy)]" />
              )}
              {isDone && !isSelected && (
                <span className="text-[9px] text-gray-300">✓</span>
              )}
            </div>
            <p className={`text-sm font-bold mt-0.5 ${isSelected ? "" : "text-black"}`}>
              {MONTH_NAMES[m.period_month]}
            </p>
            <p className={`text-[10px] mt-0.5 line-clamp-1 ${isSelected ? "opacity-80" : "text-gray-400"}`}>
              {m.focus ?? "Sin foco"}
            </p>
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/DiagnosticoPanel.tsx frontend/src/components/plan/MonthTimeline.tsx
git commit -m "feat(plan-fe): DiagnosticoPanel y MonthTimeline"
```

---

## Task 4: TaskDrawer + TaskRow

**Files:**
- Create: `frontend/src/components/plan/TaskDrawer.tsx`
- Create: `frontend/src/components/plan/TaskRow.tsx`

- [ ] **Step 1: Crear `frontend/src/components/plan/TaskRow.tsx`**

```tsx
"use client"

import type { Task, TaskPriority } from "@/lib/annualPlan"
import { User, Calendar } from "lucide-react"

const PRIORITY_DOT: Record<TaskPriority, string> = {
  alta: "bg-red-500", media: "bg-amber-500", baja: "bg-emerald-500",
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso + "T00:00:00")
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short" })
}

export default function TaskRow({ task, onClick }: { task: Task; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-50 transition-colors text-left group"
    >
      <span className={`h-2 w-2 rounded-full flex-shrink-0 ${PRIORITY_DOT[task.priority]}`} />
      <span className={`text-sm flex-1 truncate ${
        task.status === "completada" ? "line-through text-gray-400" : "text-black"
      }`}>
        {task.title}
      </span>
      {task.owner && (
        <span className="hidden sm:flex items-center gap-1 text-[11px] text-gray-400 flex-shrink-0">
          <User className="h-3 w-3" /> {task.owner}
        </span>
      )}
      {task.due_date && (
        <span className="flex items-center gap-1 text-[11px] text-gray-400 flex-shrink-0">
          <Calendar className="h-3 w-3" /> {shortDate(task.due_date)}
        </span>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Crear `frontend/src/components/plan/TaskDrawer.tsx`**

```tsx
"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { X, Trash2, User, Calendar, Tag, Target } from "lucide-react"
import type { Task, TaskStatus, TaskPriority } from "@/lib/annualPlan"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const STATUSES: { id: TaskStatus; label: string }[] = [
  { id: "pendiente", label: "Por hacer" },
  { id: "en_progreso", label: "En progreso" },
  { id: "completada", label: "Completada" },
]

const PRIORITIES: { id: TaskPriority; label: string }[] = [
  { id: "alta", label: "Alta" },
  { id: "media", label: "Media" },
  { id: "baja", label: "Baja" },
]

export default function TaskDrawer({
  task, kpiOptions, onClose, onUpdate, onDelete,
}: {
  task: Task
  kpiOptions: string[]
  onClose: () => void
  onUpdate: (patch: Partial<Task>) => void
  onDelete: () => void
}) {
  const [local, setLocal] = useState<Task>(task)
  useEffect(() => setLocal(task), [task])

  const save = (patch: Partial<Task>) => {
    setLocal(prev => ({ ...prev, ...patch }))
    onUpdate(patch)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }}
        transition={{ duration: 0.3, ease: EASE }}
        className="fixed z-50 inset-y-0 right-0 w-full sm:w-[460px] bg-white shadow-2xl overflow-y-auto"
      >
        <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-6 h-14 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-widest">Tarea</span>
          <button onClick={onClose} className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <textarea
            value={local.title}
            onChange={e => setLocal(p => ({ ...p, title: e.target.value }))}
            onBlur={() => local.title !== task.title && save({ title: local.title })}
            rows={2}
            className="w-full text-lg font-bold text-black resize-none focus:outline-none placeholder:text-gray-300"
            placeholder="Título de la tarea"
          />

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Estado</label>
            <div className="flex gap-1.5">
              {STATUSES.map(s => (
                <button
                  key={s.id}
                  onClick={() => save({ status: s.id })}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all ${
                    local.status === s.id
                      ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Prioridad</label>
            <div className="flex gap-1.5">
              {PRIORITIES.map(p => (
                <button
                  key={p.id}
                  onClick={() => save({ priority: p.id })}
                  className={`flex-1 text-xs font-medium py-2 rounded-lg border-2 transition-all ${
                    local.priority === p.id
                      ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                      : "border-gray-100 text-gray-500 hover:border-gray-300"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Descripción</label>
            <textarea
              value={local.description ?? ""}
              onChange={e => setLocal(p => ({ ...p, description: e.target.value }))}
              onBlur={() => local.description !== task.description && save({ description: local.description })}
              rows={4}
              placeholder="Detalles, contexto, criterios de éxito…"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)] resize-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <User className="h-3 w-3" /> Responsable
            </label>
            <input
              value={local.owner ?? ""}
              onChange={e => setLocal(p => ({ ...p, owner: e.target.value }))}
              onBlur={() => local.owner !== task.owner && save({ owner: local.owner || null })}
              placeholder="Director General, CFO, Consejo…"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Calendar className="h-3 w-3" /> Fecha límite
            </label>
            <input
              type="date"
              value={local.due_date ?? ""}
              onChange={e => save({ due_date: e.target.value || null })}
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Target className="h-3 w-3" /> Impacto KPI
            </label>
            <select
              value={local.kpi_ref ?? ""}
              onChange={e => save({ kpi_ref: e.target.value || null })}
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            >
              <option value="">Sin KPI</option>
              {kpiOptions.map(k => <option key={k} value={k}>{k}</option>)}
              {local.kpi_ref && !kpiOptions.includes(local.kpi_ref) && (
                <option value={local.kpi_ref}>{local.kpi_ref}</option>
              )}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-medium tracking-widest text-gray-400 uppercase flex items-center gap-1.5">
              <Tag className="h-3 w-3" /> Etiquetas
            </label>
            <input
              value={local.tags.join(", ")}
              onChange={e => setLocal(p => ({ ...p, tags: e.target.value.split(",").map(s => s.trim()).filter(Boolean) }))}
              onBlur={() => save({ tags: local.tags })}
              placeholder="compliance, liquidez, talento"
              className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
            />
          </div>

          <button
            onClick={onDelete}
            className="w-full flex items-center justify-center gap-2 text-xs font-medium text-red-500 hover:text-red-700 border border-red-100 hover:border-red-300 rounded-xl py-2.5 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" /> Borrar tarea
          </button>
        </div>
      </motion.div>
    </>
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/TaskRow.tsx frontend/src/components/plan/TaskDrawer.tsx
git commit -m "feat(plan-fe): TaskRow y TaskDrawer de edición"
```

---

## Task 5: ObjectiveCard + MonthDetail

**Files:**
- Create: `frontend/src/components/plan/ObjectiveCard.tsx`
- Create: `frontend/src/components/plan/MonthDetail.tsx`

- [ ] **Step 1: Crear `frontend/src/components/plan/ObjectiveCard.tsx`**

```tsx
"use client"

import { useState } from "react"
import { Plus, Trash2, Target } from "lucide-react"
import type { Objective, Task } from "@/lib/annualPlan"
import TaskRow from "./TaskRow"

export default function ObjectiveCard({
  objective, onTaskClick, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objective: Objective
  onTaskClick: (t: Task) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [title, setTitle] = useState(objective.title)

  return (
    <div className="border border-gray-100 rounded-2xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          onBlur={() => title.trim() && title !== objective.title && onRenameObjective(objective.id, title.trim())}
          className="flex-1 text-sm font-bold text-black bg-transparent focus:outline-none focus:bg-gray-50 rounded px-1 -mx-1"
        />
        <button
          onClick={() => onDeleteObjective(objective.id)}
          className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0"
          aria-label="Borrar objetivo"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {objective.kpi_refs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {objective.kpi_refs.map(k => (
            <span key={k} className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-md border border-gray-200 text-gray-600">
              <Target className="h-2.5 w-2.5" /> {k}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-0.5">
        {objective.tasks.map(t => (
          <TaskRow key={t.id} task={t} onClick={() => onTaskClick(t)} />
        ))}
      </div>

      <button
        onClick={() => onAddTask(objective.id)}
        className="w-full flex items-center justify-center gap-1.5 text-xs text-gray-400 hover:text-[var(--gob-navy)] border border-dashed border-gray-200 hover:border-gray-400 rounded-lg py-2 transition-colors"
      >
        <Plus className="h-3 w-3" /> Nueva tarea
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Crear `frontend/src/components/plan/MonthDetail.tsx`**

```tsx
"use client"

import { motion } from "framer-motion"
import { Plus } from "lucide-react"
import type { MonthlyPlan, Task } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import ObjectiveCard from "./ObjectiveCard"

export default function MonthDetail({
  month, onTaskClick, onAddTask, onRenameObjective, onDeleteObjective, onAddObjective,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
  onAddObjective: (monthlyPlanId: string) => void
}) {
  return (
    <motion.div
      key={month.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <div>
        <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
          {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
        </p>
        {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
      </div>

      {month.objectives.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Este mes aún no tiene objetivos.</p>
      ) : (
        <div className="space-y-3">
          {month.objectives.map(o => (
            <ObjectiveCard
              key={o.id}
              objective={o}
              onTaskClick={onTaskClick}
              onAddTask={onAddTask}
              onRenameObjective={onRenameObjective}
              onDeleteObjective={onDeleteObjective}
            />
          ))}
        </div>
      )}

      <button
        onClick={() => onAddObjective(month.id)}
        className="w-full flex items-center justify-center gap-1.5 text-xs font-medium text-gray-500 hover:text-[var(--gob-navy)] border border-dashed border-gray-200 hover:border-gray-400 rounded-xl py-2.5 transition-colors"
      >
        <Plus className="h-3.5 w-3.5" /> Agregar objetivo
      </button>
    </motion.div>
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/ObjectiveCard.tsx frontend/src/components/plan/MonthDetail.tsx
git commit -m "feat(plan-fe): ObjectiveCard y MonthDetail"
```

---

## Task 6: Página orquestadora `/dashboard/plan`

**Files:**
- Create: `frontend/src/app/dashboard/plan/page.tsx`

- [ ] **Step 1: Crear `frontend/src/app/dashboard/plan/page.tsx`**

```tsx
"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { ArrowLeft, Loader2, Sparkles, AlertCircle } from "lucide-react"
import AgentsCollaboration from "@/components/plan/AgentsCollaboration"
import DiagnosticoPanel from "@/components/plan/DiagnosticoPanel"
import MonthTimeline from "@/components/plan/MonthTimeline"
import MonthDetail from "@/components/plan/MonthDetail"
import TaskDrawer from "@/components/plan/TaskDrawer"
import {
  getAnnualPlan, getAnnualPlanStatus, generateAnnualPlan,
  createObjective, updateObjective, deleteObjective,
  createTask, updateTask, deleteTask,
  type AnnualPlan, type Task, type PlanStatus,
} from "@/lib/annualPlan"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

export default function AnnualPlanPage() {
  const router = useRouter()
  const [view, setView] = useState<View>("loading")
  const [plan, setPlan] = useState<AnnualPlan | null>(null)
  const [selectedMonth, setSelectedMonth] = useState(1)
  const [openTask, setOpenTask] = useState<Task | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const loadPlan = useCallback(async () => {
    const p = await getAnnualPlan()
    setPlan(p)
    setSelectedMonth(prev => {
      const active = p.months.find(m => m.status === "active")
      return prev !== 1 ? prev : (active?.month_index ?? 1)
    })
    setView("active")
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const s = await getAnnualPlanStatus()
        if (s.status === "active" || s.status === "completed") {
          stopPolling()
          await loadPlan()
        } else if (s.status === "failed") {
          stopPolling()
          setView("failed")
        }
      } catch { /* reintenta en el próximo tick */ }
    }, 2500)
  }, [stopPolling, loadPlan])

  const init = useCallback(async () => {
    try {
      const s = await getAnnualPlanStatus()
      if (s.status === "generating") { setView("generating"); startPolling() }
      else if (s.status === "failed") setView("failed")
      else await loadPlan()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) setView("none")
      else setView("error")
    }
  }, [startPolling, loadPlan])

  useEffect(() => { init(); return stopPolling }, [init, stopPolling])

  const onGenerate = async () => {
    setView("generating")
    try {
      await generateAnnualPlan()
      startPolling()
    } catch {
      setView("failed")
    }
  }

  // ── Mutaciones optimistas ──────────────────────────────
  const patchTaskLocal = (taskId: string, patch: Partial<Task>) => {
    setPlan(p => p && ({
      ...p,
      months: p.months.map(m => ({
        ...m,
        objectives: m.objectives.map(o => ({
          ...o, tasks: o.tasks.map(t => t.id === taskId ? { ...t, ...patch } : t),
        })),
      })),
    }))
    setOpenTask(prev => prev && prev.id === taskId ? { ...prev, ...patch } : prev)
  }

  const onUpdateTask = async (taskId: string, patch: Partial<Task>) => {
    patchTaskLocal(taskId, patch)
    try { await updateTask(taskId, patch) } catch { loadPlan() }
  }

  const onDeleteTask = async (taskId: string) => {
    setOpenTask(null)
    setPlan(p => p && ({
      ...p,
      months: p.months.map(m => ({
        ...m, objectives: m.objectives.map(o => ({ ...o, tasks: o.tasks.filter(t => t.id !== taskId) })),
      })),
    }))
    try { await deleteTask(taskId) } catch { loadPlan() }
  }

  const onAddTask = async (objectiveId: string) => {
    try {
      const t = await createTask({ objective_id: objectiveId, title: "Nueva tarea", priority: "media" })
      setPlan(p => p && ({
        ...p,
        months: p.months.map(m => ({
          ...m, objectives: m.objectives.map(o => o.id === objectiveId ? { ...o, tasks: [...o.tasks, t] } : o),
        })),
      }))
      setOpenTask(t)
    } catch { loadPlan() }
  }

  const onRenameObjective = async (objectiveId: string, title: string) => {
    setPlan(p => p && ({
      ...p, months: p.months.map(m => ({
        ...m, objectives: m.objectives.map(o => o.id === objectiveId ? { ...o, title } : o),
      })),
    }))
    try { await updateObjective(objectiveId, { title }) } catch { loadPlan() }
  }

  const onDeleteObjective = async (objectiveId: string) => {
    setPlan(p => p && ({
      ...p, months: p.months.map(m => ({ ...m, objectives: m.objectives.filter(o => o.id !== objectiveId) })),
    }))
    try { await deleteObjective(objectiveId) } catch { loadPlan() }
  }

  const onAddObjective = async (monthlyPlanId: string) => {
    try {
      const o = await createObjective({ monthly_plan_id: monthlyPlanId, title: "Nuevo objetivo", kpi_refs: [] })
      setPlan(p => p && ({
        ...p, months: p.months.map(m => m.id === monthlyPlanId ? { ...m, objectives: [...m.objectives, o] } : m),
      }))
    } catch { loadPlan() }
  }

  // ── Render por estado ──────────────────────────────────
  if (view === "loading") {
    return <div className="min-h-dvh bg-white flex items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
    </div>
  }

  if (view === "generating") {
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-10 px-6">
        <div className="text-center space-y-1">
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Construyendo tu plan</p>
          <h1 className="text-2xl font-bold text-black">Tu consejo está diseñando los 12 meses</h1>
        </div>
        <AgentsCollaboration caption="Los agentes analizan tu empresa, el Challenger aplica pre-mortem, y con eso se arma tu plan estratégico anual. Esto puede tardar un par de minutos." />
      </div>
    )
  }

  if (view === "none" || view === "failed" || view === "error") {
    const isFail = view === "failed" || view === "error"
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
          {isFail ? <AlertCircle className="h-5 w-5 text-red-400" /> : <Sparkles className="h-5 w-5 text-gray-300" />}
        </div>
        <div className="space-y-2 max-w-md">
          <p className="text-base font-medium text-black">
            {isFail ? "No se pudo generar tu plan" : "Genera tu plan estratégico de 12 meses"}
          </p>
          <p className="text-sm text-gray-500 leading-relaxed">
            {isFail
              ? "Algo falló al construir el plan. Puedes reintentarlo."
              : "A partir de tu onboarding, el consejo diseñará un plan anual con objetivos, tareas, responsables y KPIs."}
          </p>
        </div>
        <button
          onClick={onGenerate}
          className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
        >
          <Sparkles className="h-4 w-4" /> {isFail ? "Reintentar" : "Generar plan"}
        </button>
      </div>
    )
  }

  // view === "active"
  const month = plan?.months.find(m => m.month_index === selectedMonth) ?? plan?.months[0]
  const kpiOptions = month ? Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs))) : []

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      <header className="fixed top-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] h-14 flex items-center justify-between">
          <button onClick={() => router.push("/dashboard")} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
          </button>
        </div>
      </header>

      <main className="pt-14">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] py-10 space-y-8">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }} className="space-y-1">
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Plan estratégico</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">{plan?.title ?? "Plan de 12 meses"}</h1>
          </motion.div>

          <DiagnosticoPanel summary={plan?.diagnostico_summary ?? null} />

          {plan && (
            <MonthTimeline months={plan.months} selectedIndex={selectedMonth} onSelect={setSelectedMonth} />
          )}

          {month && (
            <MonthDetail
              month={month}
              onTaskClick={setOpenTask}
              onAddTask={onAddTask}
              onRenameObjective={onRenameObjective}
              onDeleteObjective={onDeleteObjective}
              onAddObjective={onAddObjective}
            />
          )}
        </div>
      </main>

      {openTask && (
        <TaskDrawer
          task={openTask}
          kpiOptions={kpiOptions}
          onClose={() => setOpenTask(null)}
          onUpdate={patch => onUpdateTask(openTask.id, patch)}
          onDelete={() => onDeleteTask(openTask.id)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(plan-fe): página /dashboard/plan con estados, polling y edición"
```

---

## Task 7: Wire-ups (redirect de onboarding + tarjeta en dashboard)

**Files:**
- Modify: `frontend/src/app/onboarding/etapa-8/page.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Redirigir al plan tras completar onboarding**

En `frontend/src/app/onboarding/etapa-8/page.tsx`, reemplazar la línea del `handleSubmit`:
```tsx
      router.push(fromDatos ? "/dashboard/datos" : "/dashboard")
```
por:
```tsx
      router.push(fromDatos ? "/dashboard/datos" : "/dashboard/plan")
```
(Cuando el usuario solo edita sus datos —`fromDatos`— sigue yendo a `/dashboard/datos`; al completar el onboarding por primera vez, va al plan recién encolado.)

- [ ] **Step 2: Agregar tarjeta de entrada al plan en el dashboard**

En `frontend/src/app/dashboard/page.tsx`, agrega un enlace/tarjeta hacia `/dashboard/plan`. Primero lee el archivo para ubicar la rejilla de tarjetas/acciones existente y replica su estilo. Inserta una tarjeta con este contenido (ajusta el wrapper al patrón vecino — si las demás usan `<Link href=...>`, usa lo mismo; importa `Link from "next/link"` si no está):

```tsx
<Link
  href="/dashboard/plan"
  className="group block border border-gray-100 rounded-2xl p-5 hover:border-gray-300 transition-colors"
>
  <div className="flex items-center justify-between">
    <span className="text-sm font-bold text-black">Plan estratégico de 12 meses</span>
    <span className="text-gray-300 group-hover:text-[var(--gob-navy)] transition-colors">→</span>
  </div>
  <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
    Objetivos, tareas y KPIs mes a mes, generados por tu consejo.
  </p>
</Link>
```

Si el dashboard no tiene una rejilla obvia de tarjetas, colócala en una sección propia bajo el encabezado, dentro del contenedor principal (`max-w-[var(--container-fluid)]`).

- [ ] **Step 3: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/onboarding/etapa-8/page.tsx frontend/src/app/dashboard/page.tsx
git commit -m "feat(plan-fe): redirect post-onboarding al plan + tarjeta en dashboard"
```

---

## Task 8: Script de sembrado (backend)

**Files:**
- Create: `backend/scripts/seed_sample_annual_plan.py`

> Inserta un plan de muestra directo en la DB (sin IA ni Celery) para iterar la UI. Se ejecuta a mano contra la DB configurada en `DATABASE_URL`.

- [ ] **Step 1: Crear `backend/scripts/seed_sample_annual_plan.py`**

```python
"""
Siembra un AnnualPlan de muestra (status 'active') para probar el frontend localmente,
SIN IA ni Celery. Inserta 12 meses; los primeros con objetivos y tareas de ejemplo.

USO (desde backend/):
    venv/bin/python -m scripts.seed_sample_annual_plan <USER_ID> [--status active|generating]

Si no se pasa USER_ID, usa el del usuario de prueba (variable SEED_USER_ID o un default).
"""
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import delete
from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.action_plan import ActionTask
from app.services.ai.annual_plan_generator import month_calendar, compute_active_month_index

DEFAULT_USER_ID = "seed-user"

SAMPLE = {
    1: {"focus": "Estabilizar liquidez", "objectives": [
        {"title": "Mejorar el flujo de caja", "kpi_refs": ["Razón corriente"], "tasks": [
            {"title": "Negociar línea de crédito revolvente", "owner": "CFO", "priority": "alta"},
            {"title": "Revisar política de cuentas por cobrar", "owner": "Director General", "priority": "media"},
        ]},
        {"title": "Ordenar el gobierno corporativo", "kpi_refs": ["Governance Score"], "tasks": [
            {"title": "Documentar el reglamento del consejo", "owner": "Auditor Interno", "priority": "media"},
        ]},
    ]},
    2: {"focus": "Impulsar ventas", "objectives": [
        {"title": "Diversificar la cartera de clientes", "kpi_refs": ["Concentración de clientes"], "tasks": [
            {"title": "Definir plan comercial por segmento", "owner": "Director Comercial", "priority": "alta"},
        ]},
    ]},
    3: {"focus": "Fortalecer talento", "objectives": [
        {"title": "Reducir rotación clave", "kpi_refs": ["Rotación de personal"], "tasks": [
            {"title": "Diseñar plan de retención de directivos", "owner": "Director de RH", "priority": "media"},
        ]},
    ]},
}


async def main(user_id: str, status: str) -> None:
    today = date.today()
    async with AsyncSessionLocal() as db:
        # Limpiar planes previos del usuario (idempotente para re-sembrar).
        existing = await db.execute(
            AnnualPlan.__table__.select().where(AnnualPlan.user_id == user_id)
        )
        for row in existing.fetchall():
            await db.execute(delete(AnnualPlan).where(AnnualPlan.id == row.id))
        await db.commit()

        plan = AnnualPlan(
            user_id=user_id,
            title="Plan estratégico de 12 meses",
            start_date=today,
            status=status,
            diagnostico_summary=(
                "**CFO:** La liquidez está ajustada; conviene asegurar una línea de crédito.\n\n"
                "**CSO:** Las ventas dependen de pocos clientes; urge diversificar.\n\n"
                "**CRO:** El principal riesgo es de concentración comercial.\n\n"
                "**Auditor:** El gobierno corporativo necesita formalizar su reglamento."
            ),
        )
        db.add(plan)
        await db.flush()

        active_idx = compute_active_month_index(today, today)  # = 1
        for i in range(1, 13):
            year, month = month_calendar(today.year, today.month, i)
            mp = MonthlyPlan(
                annual_plan_id=plan.id, month_index=i,
                period_year=year, period_month=month,
                focus=SAMPLE.get(i, {}).get("focus"),
                status="active" if i == active_idx else ("done" if i < active_idx else "locked"),
            )
            db.add(mp)
            await db.flush()

            for oi, obj_spec in enumerate(SAMPLE.get(i, {}).get("objectives", [])):
                obj = Objective(
                    monthly_plan_id=mp.id, title=obj_spec["title"],
                    kpi_refs=obj_spec.get("kpi_refs", []), order_index=oi,
                )
                db.add(obj)
                await db.flush()
                for ti, t in enumerate(obj_spec.get("tasks", [])):
                    db.add(ActionTask(
                        objective_id=obj.id, title=t["title"],
                        status="pendiente", priority=t.get("priority", "media"),
                        owner=t.get("owner"),
                        due_date=date(year, month, min(25, 28)),
                        kpi_ref=(obj_spec.get("kpi_refs") or [None])[0],
                        tags=[], order_index=ti,
                    ))
        await db.commit()
    print(f"OK: plan de muestra sembrado para user_id={user_id} (status={status})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    uid = args[0] if args else DEFAULT_USER_ID
    st = "active"
    if "--status" in sys.argv:
        st = sys.argv[sys.argv.index("--status") + 1]
    asyncio.run(main(uid, st))
```

- [ ] **Step 2: Verificar que compila (no toca la DB)**

Run (desde `backend/`): `venv/bin/python -m py_compile scripts/seed_sample_annual_plan.py`
Expected: sin salida (exit 0).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_sample_annual_plan.py
git commit -m "feat(plan-fe): script de sembrado de plan de muestra para prueba local"
```

---

## Task 9: Verificación local manual (end-to-end)

**Files:** ninguno (verificación).

> Esta tarea NO se delega a un subagente de implementación; el controlador la coordina con el usuario. El `USER_ID` debe ser el `sub` del JWT del usuario de prueba con el que entrarás (el mismo que usa el frontend al loguearte). Si no lo conoces, ver nota abajo.

- [ ] **Step 1: Build de frontend (typecheck global)**

Run (desde `frontend/`): `npm run build`
Expected: build exitoso, sin errores de tipos.

- [ ] **Step 2: Sembrar datos** (requiere autorización para tocar la DB)

Run (desde `backend/`): `venv/bin/python -m scripts.seed_sample_annual_plan <USER_ID_DE_PRUEBA>`
Expected: `OK: plan de muestra sembrado…`.

> Nota sobre USER_ID: el backend identifica al usuario por `sub` del JWT de Supabase. Para conocerlo, loguéate en el frontend local y revisa la request a `/api/v1/...` (header Authorization) o usa el usuario de prueba `prueba@gobernia.com`. El sembrado debe usar ese mismo `user_id`.

- [ ] **Step 3: Levantar backend y frontend**

Backend (desde `backend/`): `venv/bin/uvicorn app.main:app --port 8000 --reload`
Frontend (desde `frontend/`): `npm run dev`

- [ ] **Step 4: Verificar en el navegador**

Entrar a `/dashboard/plan` logueado con el usuario sembrado y confirmar:
- Se ve el diagnóstico colapsable, la tira de 12 meses (mes 1 marcado activo) y el detalle del mes con objetivos→tareas.
- Navegar entre meses cambia el detalle.
- Abrir una tarea (drawer), cambiar estado/prioridad/responsable/fecha/KPI/etiquetas → recargar la página → los cambios persisten.
- Crear objetivo, crear tarea, borrar tarea, borrar objetivo → persisten.
- Probar ancho móvil: la tira de meses hace scroll horizontal.
- (Opcional) Sembrar con `--status generating` para ver la pantalla de generación con la animación.
- Desde el dashboard, la tarjeta "Plan estratégico" lleva a `/dashboard/plan`.

---

## Cierre

- [ ] Confirmar que `npm run build` (frontend) pasa y la verificación manual del Task 9 se ve y funciona.
- [ ] El frontend del subproyecto A queda completo. Pendiente (decisión del usuario): merge+push de esta rama y de `fix/etapa8-hook-hardening`, y eventualmente Redis+worker en Railway para la generación real.

## Fuera de alcance (otros subproyectos)
- Tablero Monday con columnas de estado + confeti (C/F), recordatorios (D), Secretario/orden del día (B), UI de revisión de fin de mes (E).
