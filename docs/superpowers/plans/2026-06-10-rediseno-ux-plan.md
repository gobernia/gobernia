# Rediseño UX "for dummies" — Plan mes a mes + nav superior · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Barra de navegación superior (Inicio · Sesión del mes · Plan · Compromisos), página del ritual mensual, página de compromisos, y el Plan rediseñado como pantalla mes-por-mes con tabla estilo Monday (edición inline) — eliminando las 5 pestañas y el kanban.

**Architecture:** Solo frontend (Next.js 16 App Router). Un `layout.tsx` del dashboard monta `TopNav`. Dos páginas nuevas componen componentes existentes. `MonthDetail` se reescribe alrededor de un componente nuevo `TasksTable` (tareas agrupadas por objetivo, inline editing vía el handler optimista `onUpdateTask` ya existente). `plan/page.tsx` pierde el toggle de 5 vistas.

**Tech Stack:** Next.js 16 (App Router, "use client"), TypeScript, Tailwind v4 (vars `--gob-navy`/`--gob-bone`), lucide-react. Cero cambios de backend.

**Spec:** `docs/superpowers/specs/2026-06-10-rediseno-ux-plan-design.md`

**Hechos del codebase (verificados):**
- `lib/annualPlan.ts`: `Task {id, title, status, priority, owner, due_date, tags, order_index, evidence_count, …}` (`evidence_count` existe — lo usa el kanban), `Objective {id, title, kpi_refs, tasks[]}`, `MONTH_NAMES` (1-indexado), `updateTask`, `getAnnualPlanStatus`.
- `plan/page.tsx` ya tiene handlers optimistas: `onUpdateTask(taskId, patch)` (patch local + PATCH + revert via reload), `onAddTask(objectiveId)`, `onRenameObjective`, `onDeleteObjective`, `onAddObjective`, `setOpenTask` (abre `TaskDrawer`), `boardView` toggle de 5 vistas (l.~277-330), paneles `DiagnosticoPanel`/`AgendaPanel`/`AlertsPanel` (l.270-274), `ThemesPanel` (l.326).
- `MonthDetail.tsx` hoy monta `OrdenDelDiaPanel monthIndex={month.month_index}` + `ObjectiveCard`s.
- `ObjectiveCard` solo lo importa `MonthDetail`; `AcuerdosBoard` solo lo importa `plan/page.tsx` → ambos se borran al final.
- Rutas existentes: `/dashboard`, `/dashboard/plan`, `/dashboard/datos`, `/dashboard/sesion/[id]` (NO tocar). No hay `app/dashboard/layout.tsx`.
- Verificación frontend del proyecto: `npx tsc --noEmit` + `npx eslint <files>` + `npm run build` (no hay tests unitarios de front).

---

### Task 1: `TopNav` + layout del dashboard

**Files:**
- Create: `frontend/src/components/ui/TopNav.tsx`
- Create: `frontend/src/app/dashboard/layout.tsx`

- [ ] **Step 1: Create** `frontend/src/components/ui/TopNav.tsx`:
```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const LINKS = [
  { href: "/dashboard", label: "Inicio", exact: true },
  { href: "/dashboard/sesion-del-mes", label: "Sesión del mes", exact: false },
  { href: "/dashboard/plan", label: "Plan", exact: false },
  { href: "/dashboard/compromisos", label: "Compromisos", exact: false },
]

export default function TopNav() {
  const pathname = usePathname()
  return (
    <nav className="sticky top-0 z-40 bg-[var(--gob-navy)] text-[var(--gob-bone)]">
      <div className="max-w-6xl mx-auto px-4 flex items-center gap-1 overflow-x-auto">
        <Link href="/dashboard" className="font-bold tracking-widest text-sm py-3 pr-4 shrink-0">
          GOBERNIA
        </Link>
        {LINKS.map(l => {
          const active = l.exact ? pathname === l.href : pathname.startsWith(l.href)
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`text-sm py-3 px-3 shrink-0 border-b-2 transition-colors ${
                active
                  ? "border-[var(--gob-bone)] font-medium"
                  : "border-transparent opacity-70 hover:opacity-100"
              }`}
            >
              {l.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
```

- [ ] **Step 2: Create** `frontend/src/app/dashboard/layout.tsx`:
```tsx
import TopNav from "@/components/ui/TopNav"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopNav />
      {children}
    </>
  )
}
```

- [ ] **Step 3: Verify:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/components/ui/TopNav.tsx src/app/dashboard/layout.tsx && npm run build
```
Expected: limpio + `✓ Compiled successfully`. (Los links a rutas aún no creadas compilan bien — Next no valida hrefs.)

- [ ] **Step 4: Commit:**
```bash
git add frontend/src/components/ui/TopNav.tsx frontend/src/app/dashboard/layout.tsx
git commit -m "feat(ux): barra de navegación superior del dashboard (TopNav + layout)"
```

---

### Task 2: Páginas "Sesión del mes" y "Compromisos"

**Files:**
- Create: `frontend/src/app/dashboard/sesion-del-mes/page.tsx`
- Create: `frontend/src/app/dashboard/compromisos/page.tsx`

- [ ] **Step 1: Create** `frontend/src/app/dashboard/sesion-del-mes/page.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import AgendaPanel from "@/components/plan/AgendaPanel"
import MinutaView from "@/components/plan/MinutaView"
import AlertsPanel from "@/components/plan/AlertsPanel"
import { MONTH_NAMES, getAnnualPlanStatus } from "@/lib/annualPlan"

export default function SesionDelMesPage() {
  const [hasPlan, setHasPlan] = useState<boolean | null>(null)

  useEffect(() => {
    let active = true
    getAnnualPlanStatus()
      .then(() => { if (active) setHasPlan(true) })
      .catch(() => { if (active) setHasPlan(false) })
    return () => { active = false }
  }, [])

  const now = new Date()

  return (
    <main className="min-h-screen bg-[var(--gob-bone)] px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Tu sesión de</p>
          <h1 className="text-3xl font-bold text-black tracking-tight">
            {MONTH_NAMES[now.getMonth() + 1]} {now.getFullYear()}
          </h1>
        </div>

        {hasPlan === null && <p className="text-sm text-gray-400">Cargando…</p>}

        {hasPlan === false && (
          <div className="rounded-2xl border border-gray-100 bg-white p-6 text-center">
            <p className="text-sm text-gray-500 mb-3">
              Aún no tienes un plan estratégico. Genera tu plan para convocar a tu consejo.
            </p>
            <Link
              href="/dashboard/plan"
              className="inline-block px-4 py-2 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium"
            >
              Ir al Plan
            </Link>
          </div>
        )}

        {hasPlan === true && (
          <>
            <AgendaPanel />
            <MinutaView />
            <AlertsPanel />
          </>
        )}
      </div>
    </main>
  )
}
```
(NOTA: `MONTH_NAMES` es 1-indexado — verifica su export en `lib/annualPlan.ts`; `now.getMonth() + 1` es correcto.)

- [ ] **Step 2: Create** `frontend/src/app/dashboard/compromisos/page.tsx`:
```tsx
"use client"

import CompromisosBoard from "@/components/plan/CompromisosBoard"

export default function CompromisosPage() {
  return (
    <main className="min-h-screen bg-[var(--gob-bone)] px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <div>
          <h1 className="text-3xl font-bold text-black tracking-tight">Compromisos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Acuerdos del consejo con responsable y seguimiento. Copia el link para que el
            responsable reporte avance sin necesidad de cuenta.
          </p>
        </div>
        <CompromisosBoard />
      </div>
    </main>
  )
}
```

- [ ] **Step 3: Verify:**
```bash
cd frontend && npx tsc --noEmit && npx eslint "src/app/dashboard/sesion-del-mes/page.tsx" "src/app/dashboard/compromisos/page.tsx" && npm run build
```
Expected: limpio; el build lista las rutas `/dashboard/sesion-del-mes` y `/dashboard/compromisos`.

- [ ] **Step 4: Commit:**
```bash
git add frontend/src/app/dashboard/sesion-del-mes frontend/src/app/dashboard/compromisos
git commit -m "feat(ux): páginas Sesión del mes (ritual) y Compromisos"
```

---

### Task 3: Componente `TasksTable` (tabla estilo Monday)

**Files:**
- Create: `frontend/src/components/plan/TasksTable.tsx`

- [ ] **Step 1: Create** `frontend/src/components/plan/TasksTable.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import { MoreHorizontal, Paperclip, Plus, Trash2 } from "lucide-react"
import type { Objective, Task } from "@/lib/annualPlan"

const STATUS: { id: Task["status"]; label: string; cls: string }[] = [
  { id: "pendiente", label: "Pendiente", cls: "bg-gray-100 text-gray-600" },
  { id: "en_progreso", label: "En proceso", cls: "bg-amber-100 text-amber-700" },
  { id: "completada", label: "Validado", cls: "bg-green-100 text-green-700" },
]

export default function TasksTable({
  objectives, onTaskClick, onUpdateTask, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objectives: Objective[]
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 4000)
    return () => clearTimeout(t)
  }, [notice])

  const onStatusChange = (task: Task, status: Task["status"]) => {
    if (status === task.status) return
    if (status === "completada" && task.evidence_count === 0) {
      setNotice("Sube evidencia para validar esta tarea — se abrió el detalle.")
      onTaskClick(task)
      return
    }
    onUpdateTask(task.id, { status })
  }

  if (objectives.length === 0) {
    return <p className="text-sm text-gray-400 italic">Este mes aún no tiene objetivos.</p>
  }

  return (
    <div className="space-y-5">
      {notice && (
        <p className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {notice}
        </p>
      )}

      {objectives.map(o => (
        <ObjectiveGroup
          key={o.id}
          objective={o}
          onTaskClick={onTaskClick}
          onUpdateTask={onUpdateTask}
          onStatusChange={onStatusChange}
          onAddTask={onAddTask}
          onRenameObjective={onRenameObjective}
          onDeleteObjective={onDeleteObjective}
        />
      ))}
    </div>
  )
}

function ObjectiveGroup({
  objective, onTaskClick, onUpdateTask, onStatusChange, onAddTask, onRenameObjective, onDeleteObjective,
}: {
  objective: Objective
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onStatusChange: (t: Task, s: Task["status"]) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="rounded-2xl border border-gray-100 bg-white overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-gray-100">
        <input
          defaultValue={objective.title}
          onBlur={e => {
            const v = e.target.value.trim()
            if (v && v !== objective.title) onRenameObjective(objective.id, v)
          }}
          className="text-sm font-bold text-black bg-transparent outline-none flex-1 min-w-0"
        />
        <div className="relative shrink-0">
          <button type="button" onClick={() => setMenuOpen(v => !v)}
            className="text-gray-300 hover:text-gray-500 p-1">
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {menuOpen && (
            <button
              type="button"
              onClick={() => { setMenuOpen(false); onDeleteObjective(objective.id) }}
              className="absolute right-0 top-7 z-10 flex items-center gap-1.5 bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-1.5 text-xs text-red-600 whitespace-nowrap"
            >
              <Trash2 className="h-3 w-3" /> Eliminar objetivo
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-gray-400">
              <th className="text-left font-medium px-4 py-2">Tarea</th>
              <th className="text-left font-medium px-2 py-2 w-40">Responsable</th>
              <th className="text-left font-medium px-2 py-2 w-36">Vence</th>
              <th className="text-left font-medium px-2 py-2 w-32">Estado</th>
              <th className="text-left font-medium px-2 py-2 w-12">
                <Paperclip className="h-3 w-3" />
              </th>
            </tr>
          </thead>
          <tbody>
            {objective.tasks.map(t => {
              const st = STATUS.find(s => s.id === t.status) ?? STATUS[0]
              return (
                <tr key={t.id} className="border-t border-gray-50 hover:bg-gray-50/60">
                  <td className="px-4 py-2">
                    <button
                      type="button"
                      onClick={() => onTaskClick(t)}
                      className="text-left text-black hover:text-[var(--gob-navy)] hover:underline"
                    >
                      {t.title}
                    </button>
                  </td>
                  <td className="px-2 py-2">
                    <input
                      defaultValue={t.owner ?? ""}
                      placeholder="➕ asignar"
                      onBlur={e => {
                        const v = e.target.value.trim()
                        if (v !== (t.owner ?? "")) onUpdateTask(t.id, { owner: v || null })
                      }}
                      className="w-full bg-transparent outline-none text-xs text-gray-700 placeholder:text-gray-300 border border-transparent focus:border-gray-200 rounded px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <input
                      type="date"
                      defaultValue={t.due_date ?? ""}
                      onChange={e => onUpdateTask(t.id, { due_date: e.target.value || null })}
                      className="bg-transparent outline-none text-xs text-gray-700 border border-transparent focus:border-gray-200 rounded px-1.5 py-1"
                    />
                  </td>
                  <td className="px-2 py-2">
                    <select
                      value={t.status}
                      onChange={e => onStatusChange(t, e.target.value as Task["status"])}
                      className={`text-xs font-medium rounded-full px-2.5 py-1 outline-none cursor-pointer appearance-none ${st.cls}`}
                    >
                      {STATUS.map(s => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2 text-xs text-gray-400">
                    {t.evidence_count > 0 ? t.evidence_count : ""}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={() => onAddTask(objective.id)}
        className="w-full flex items-center gap-1.5 px-4 py-2 text-xs text-gray-400 hover:text-[var(--gob-navy)] border-t border-gray-50"
      >
        <Plus className="h-3.5 w-3.5" /> Agregar tarea
      </button>
    </div>
  )
}
```
(NOTA: si `Task.evidence_count` fuera opcional en el tipo, usa `(t.evidence_count ?? 0)`. El campo existe — lo usa el kanban actual.)

- [ ] **Step 2: Verify (compila aunque aún nadie lo monte):**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/components/plan/TasksTable.tsx
```
Expected: limpio.

- [ ] **Step 3: Commit:**
```bash
git add frontend/src/components/plan/TasksTable.tsx
git commit -m "feat(ux): TasksTable estilo Monday (inline edit + candado de evidencia)"
```

---

### Task 4: `MonthDetail` rediseñado (orden del día colapsable + resumen + tabla)

**Files:**
- Modify (rewrite): `frontend/src/components/plan/MonthDetail.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (solo pasar el prop nuevo `onUpdateTask` al `<MonthDetail …>`)

- [ ] **Step 1: REPLACE the content of** `frontend/src/components/plan/MonthDetail.tsx` with:
```tsx
"use client"

import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { CheckCircle2, ChevronDown, FileText, Plus } from "lucide-react"
import type { MonthlyPlan, Task, MonthReview } from "@/lib/annualPlan"
import { MONTH_NAMES } from "@/lib/annualPlan"
import MonthReviewPanel from "./MonthReviewPanel"
import TasksTable from "./TasksTable"
import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"

export default function MonthDetail({
  month, onTaskClick, onUpdateTask, onAddTask, onRenameObjective, onDeleteObjective,
  onAddObjective, onCloseMonth, onApplyProposal,
}: {
  month: MonthlyPlan
  onTaskClick: (t: Task) => void
  onUpdateTask: (taskId: string, patch: Partial<Task>) => void
  onAddTask: (objectiveId: string) => void
  onRenameObjective: (objectiveId: string, title: string) => void
  onDeleteObjective: (objectiveId: string) => void
  onAddObjective: (monthlyPlanId: string) => void
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
}) {
  const [ordenOpen, setOrdenOpen] = useState(false)

  const kpis = useMemo(
    () => Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs))).slice(0, 6),
    [month.objectives],
  )

  return (
    <motion.div
      key={month.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-5"
    >
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
            {MONTH_NAMES[month.period_month]} {month.period_year} · Mes {month.month_index}
          </p>
          {month.focus && <h2 className="text-xl font-bold text-black mt-1">{month.focus}</h2>}
        </div>
        <button
          type="button"
          onClick={() => setOrdenOpen(v => !v)}
          className="flex items-center gap-1.5 text-xs font-medium text-[var(--gob-navy)] border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          <FileText className="h-3.5 w-3.5" /> Orden del día
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${ordenOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {ordenOpen && <OrdenDelDiaPanel monthIndex={month.month_index} />}

      {kpis.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">KPIs:</span>
          {kpis.map(k => (
            <span key={k} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {k}
            </span>
          ))}
        </div>
      )}

      {month.status === "done" && month.review && (
        <MonthReviewPanel
          review={month.review as unknown as MonthReview}
          onApply={pid => onApplyProposal(month.month_index, pid)}
        />
      )}

      <TasksTable
        objectives={month.objectives}
        onTaskClick={onTaskClick}
        onUpdateTask={onUpdateTask}
        onAddTask={onAddTask}
        onRenameObjective={onRenameObjective}
        onDeleteObjective={onDeleteObjective}
      />

      {month.status === "active" && (
        <button
          onClick={() => onCloseMonth(month.id)}
          className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium rounded-xl py-3 hover:bg-[var(--gob-ink)] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4" /> Cerrar mes y revisar
        </button>
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
(El "resumen de objetivos" en chips se omite a propósito: los objetivos YA son los headers de
grupo de la tabla, justo debajo — duplicarlos en chips sería ruido. Los KPIs sí van en chips.)

- [ ] **Step 2: Pass the new prop at the call site.** In `frontend/src/app/dashboard/plan/page.tsx`, find the `<MonthDetail` JSX (l.~311) and add ONE prop alongside the existing ones:
```tsx
onUpdateTask={onUpdateTask}
```
(`onUpdateTask` ya existe en la página — es el handler optimista. No toques nada más todavía;
la limpieza grande es la Task 5.)

- [ ] **Step 3: Verify:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/components/plan/MonthDetail.tsx && npm run build
```
Expected: limpio. (`ObjectiveCard` queda sin usar — eslint puede avisar import muerto SOLO si quedara importado en MonthDetail: ya no lo importa.)

- [ ] **Step 4: Commit:**
```bash
git add frontend/src/components/plan/MonthDetail.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(ux): MonthDetail con tabla Monday + orden del día colapsable + chips KPI"
```

---

### Task 5: Limpieza del plan — sin pestañas, cobertura colapsable, borrar kanban

**Files:**
- Modify: `frontend/src/app/dashboard/plan/page.tsx`
- Delete: `frontend/src/components/plan/AcuerdosBoard.tsx`
- Delete: `frontend/src/components/plan/ObjectiveCard.tsx`

- [ ] **Step 1: Read** `frontend/src/app/dashboard/plan/page.tsx` completo (para ubicar el toggle y los branches).

- [ ] **Step 2: Remove imports** que ya no se usan en esa página:
```tsx
import AcuerdosBoard from "@/components/plan/AcuerdosBoard"      // ELIMINAR
import AgendaPanel from "@/components/plan/AgendaPanel"          // ELIMINAR (vive en sesión-del-mes)
import AlertsPanel from "@/components/plan/AlertsPanel"          // ELIMINAR (ídem)
import MinutaView from "@/components/plan/MinutaView"            // ELIMINAR (ídem)
import CompromisosBoard from "@/components/plan/CompromisosBoard" // ELIMINAR (vive en /compromisos)
```
`CoberturaBoard` y `ThemesPanel` SE QUEDAN (sección colapsable). `DiagnosticoPanel` SE QUEDA.

- [ ] **Step 3: Remove the `boardView` state** (l.~39):
```tsx
const [boardView, setBoardView] = useState<"meses" | "tablero" | "cobertura" | "minuta" | "compromisos">("meses")
```
→ se elimina la línea (y el import de tipos si quedara colgado).

- [ ] **Step 4: Replace the render block.** Dentro de la vista activa, hoy hay: `<DiagnosticoPanel …/>`, `<AgendaPanel />`, `<AlertsPanel />`, la fila del toggle (`{(["meses", "tablero", …] as const).map(…)}`) y el ternario de 5 branches (que en el branch "meses" contiene `MonthTimeline` + `MonthDetail` + `ThemesPanel`). REEMPLAZA todo ese bloque (desde `<AgendaPanel />` hasta el cierre del ternario) por:
```tsx
          <MonthTimeline months={plan.months} selectedIndex={selectedMonth} onSelect={setSelectedMonth} />

          {(() => {
            const month = plan.months.find(m => m.month_index === selectedMonth)
            return month ? (
              <MonthDetail
                month={month}
                onTaskClick={t => setOpenTask(t)}
                onUpdateTask={onUpdateTask}
                onAddTask={onAddTask}
                onRenameObjective={onRenameObjective}
                onDeleteObjective={onDeleteObjective}
                onAddObjective={onAddObjective}
                onCloseMonth={id => setClosingMonthId(id)}
                onApplyProposal={onApplyProposal}
              />
            ) : null
          })()}

          <details className="mt-10">
            <summary className="text-xs font-medium text-gray-400 cursor-pointer hover:text-[var(--gob-navy)] select-none">
              Ver cobertura anual y temas del consejo
            </summary>
            <div className="mt-4 space-y-5">
              <CoberturaBoard />
              <ThemesPanel />
            </div>
          </details>
```
**IMPORTANTE:** conserva `<DiagnosticoPanel …/>` arriba tal cual está. ADAPTA los nombres de
props/handlers a los EXACTOS que ya usa la página hoy (p.ej. si el `MonthDetail` actual recibe
`onTaskClick={setOpenTask}` o `onCloseMonth={…}` con otra forma, copia los existentes del branch
"meses" actual — la única adición nueva es `onUpdateTask={onUpdateTask}`, que la Task 4 ya dejó).
La forma de derivar `month`/`selectedMonth` ya existe en el branch actual — reúsala tal cual.

- [ ] **Step 5: Delete the dead components:**
```bash
git rm frontend/src/components/plan/AcuerdosBoard.tsx frontend/src/components/plan/ObjectiveCard.tsx
```
(Antes verifica que nadie más los importe: `grep -rn "AcuerdosBoard\|ObjectiveCard" frontend/src/ --include="*.tsx" --include="*.ts"` → solo deben aparecer los archivos mismos.)

- [ ] **Step 6: Verify (todo):**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/app/dashboard/plan/page.tsx && npm run build
```
Expected: limpio; build lista todas las rutas (incl. `/dashboard/sesion-del-mes`, `/dashboard/compromisos`).

- [ ] **Step 7: Commit:**
```bash
git add -A frontend/src
git commit -m "feat(ux): plan sin pestañas — mes por mes con tabla; cobertura colapsable; adiós kanban"
```

---

## Done criteria

- Barra superior (Inicio · Sesión del mes · Plan · Compromisos) en todo el dashboard.
- `/dashboard/sesion-del-mes`: agenda+carta, minuta, alertas (o empty-state si no hay plan).
- `/dashboard/compromisos`: tablero de compromisos.
- `/dashboard/plan`: timeline → pantalla del mes con orden del día colapsable (PDF dentro),
  chips de KPIs, tabla Monday (inline: responsable/fecha/estado; candado de evidencia abre el
  drawer), cerrar mes/agregar objetivo; cobertura+temas en `<details>`; sin pestañas ni kanban.
- `tsc` + lint + build verdes. Backend intacto.

## Notes for the implementer

- **Cero backend.** Solo archivos de `frontend/src`.
- Los handlers optimistas YA existen en `plan/page.tsx` — no reimplementar; solo cablear.
- El candado de evidencia es doble: front (no llama PATCH si `evidence_count === 0`) y backend
  (409). El front abre el drawer (`onTaskClick`) donde está `EvidenceSection`.
- `/dashboard/sesion/[id]` (sesiones viejas) NO se toca.
- `<select>` con `appearance-none` para que la pastilla se vea como pill (el dropdown nativo
  está bien — es lo más "for dummies" y accesible).
- Next.js 16: revisa `node_modules/next/dist/docs/` ante cualquier duda de App Router.
