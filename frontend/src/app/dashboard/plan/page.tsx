"use client"

import { useEffect, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, ChevronDown, Check, Clock, Gauge } from "lucide-react"
import {
  AnnualPlan, Task, ExplicacionTarea, MONTH_NAMES,
  getAnnualPlan, getAnnualPlanStatus, updateTask, getTaskExplicacion,
} from "@/lib/annualPlan"

const DIF_CHIP: Record<string, string> = {
  "Fácil": "text-green-700 bg-green-50", "Media": "text-amber-700 bg-amber-50",
  "Difícil": "text-red-700 bg-red-50",
}

function TaskRow({ task, onToggle, busy }: { task: Task; onToggle: (t: Task) => void; busy: boolean }) {
  const [open, setOpen] = useState(false)
  const [exp, setExp] = useState<ExplicacionTarea | null>(task.explicacion)
  const [loading, setLoading] = useState(false)
  const done = task.status === "completada"

  const toggleOpen = async () => {
    const next = !open
    setOpen(next)
    if (next && !exp && !loading) {
      setLoading(true)
      try { setExp(await getTaskExplicacion(task.id)) } catch { /* deja vacío */ } finally { setLoading(false) }
    }
  }

  return (
    <div className={`rounded-xl border overflow-hidden ${done ? "border-green-100 bg-green-50/40" : open ? "border-[var(--gob-navy)]/30" : "border-gray-100"}`}>
      <div className="flex items-center gap-3 p-3.5">
        <button onClick={() => onToggle(task)} disabled={busy}
          className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 transition-colors ${done ? "bg-green-500 text-white" : "border-2 border-gray-300"}`}>
          {done && <Check className="h-3.5 w-3.5" />}
        </button>
        <button onClick={toggleOpen} className="flex-1 flex items-center gap-2 text-left">
          <span className={`flex-1 text-sm font-medium ${done ? "line-through text-green-700/70" : "text-gray-800"}`}>{task.title}</span>
          {task.required_doc && !done && (
            <span className="text-[10px] text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">Necesita doc</span>
          )}
          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }} className="overflow-hidden">
            <div className="px-4 pb-4 pl-[52px]">
              {loading ? (
                <div className="flex items-center gap-2 text-xs text-gray-400 py-2"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Preparando la explicación…</div>
              ) : exp ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <span className="text-[11px] font-medium px-2.5 py-1 rounded-full text-amber-700 bg-amber-50 inline-flex items-center gap-1"><Clock className="h-3 w-3" /> {exp.tiempo}</span>
                    <span className={`text-[11px] font-medium px-2.5 py-1 rounded-full inline-flex items-center gap-1 ${DIF_CHIP[exp.dificultad] ?? "text-gray-600 bg-gray-50"}`}><Gauge className="h-3 w-3" /> {exp.dificultad}</span>
                  </div>
                  {exp.que_es && (<div><p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Qué es</p><p className="text-sm text-gray-600 leading-relaxed">{exp.que_es}</p></div>)}
                  {exp.como.length > 0 && (<div><p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Cómo hacerlo</p><ol className="list-decimal pl-5 space-y-1">{exp.como.map((s, i) => <li key={i} className="text-sm text-gray-600 leading-snug">{s}</li>)}</ol></div>)}
                </div>
              ) : <p className="text-xs text-gray-300 italic py-2">Sin explicación.</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function PlanPage() {
  const [plan, setPlan] = useState<AnnualPlan | null>(null)
  const [active, setActive] = useState<number | null>(null)
  const [status, setStatus] = useState<string>("loading")
  const [view, setView] = useState<"camino" | "timeline">("camino")
  const [busyTask, setBusyTask] = useState<string | null>(null)
  const [gateMsg, setGateMsg] = useState<string | null>(null)
  const started = useRef(false)

  const load = async () => {
    const st = await getAnnualPlanStatus().catch(() => null)
    if (!st || st.status === "failed") { setStatus(st?.status ?? "none"); return }
    setActive(st.active_month_index ?? null)
    setStatus(st.status)
    if (st.status === "active" || st.status === "completed") {
      const p = await getAnnualPlan().catch(() => null)
      if (p) setPlan(p)
    }
  }

  useEffect(() => {
    if (started.current) return
    started.current = true
    load().catch(() => setStatus("none"))
  }, [])

  const total = (plan?.horizon_years ?? 3) * 12
  const months = (plan?.months ?? []).slice().sort((a, b) => a.month_index - b.month_index)
  const activeMonth = months.find(m => m.month_index === active) ?? months.find(m => m.status === "active") ?? null
  const monthTasks: Task[] = (activeMonth?.objectives ?? []).flatMap(o => o.tasks)
  const doneCount = monthTasks.filter(t => t.status === "completada").length
  const monthsDone = months.filter(m => m.status === "done").length
  const pct = total ? Math.round((monthsDone / total) * 100) : 0

  function patchTaskInPlan(p: AnnualPlan, t: Task): AnnualPlan {
    return { ...p, months: p.months.map(m => ({ ...m, objectives: m.objectives.map(o => ({ ...o, tasks: o.tasks.map(x => x.id === t.id ? { ...x, ...t } : x) })) })) }
  }

  const toggleTask = async (t: Task) => {
    setBusyTask(t.id); setGateMsg(null)
    const next = t.status === "completada" ? "pendiente" : "completada"
    try {
      const updated = await updateTask(t.id, { status: next })
      setPlan(prev => prev ? patchTaskInPlan(prev, updated) : prev)
    } catch (e: unknown) {
      const code = (e as { response?: { status?: number } })?.response?.status
      if (code === 409) setGateMsg("Esa tarea necesita su documento de sustento para marcarse como hecha. Súbelo en la tarea.")
    } finally { setBusyTask(null) }
  }

  if (status === "loading") {
    return <div className="min-h-dvh flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-gray-300" /></div>
  }
  if (status === "generating") {
    return <div className="min-h-dvh flex flex-col items-center justify-center gap-3 text-center px-6">
      <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
      <p className="text-sm text-gray-500">Tu consejo está armando tu plan a 3 años…</p></div>
  }
  if (status === "none" || !plan) {
    return <div className="min-h-dvh flex flex-col items-center justify-center gap-4 text-center px-6">
      <p className="text-sm text-gray-500">Aún no tienes un plan. Genéralo desde tu FODA.</p>
      <a href="/dashboard/foda" className="text-sm font-medium text-[var(--gob-navy)] hover:underline">Ir al FODA →</a></div>
  }

  return (
    <div className="min-h-dvh bg-white text-black">
      <main className="max-w-3xl mx-auto px-[var(--px-fluid)] py-10 space-y-8">
        <div className="bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-2xl p-6">
          <p className="text-[10px] font-medium tracking-widest uppercase opacity-70">Tu plan · {plan.horizon_years} años</p>
          <h1 className="text-2xl font-bold mt-1">{plan.title || "Plan estratégico"}</h1>
          <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden"><div className="h-full bg-white rounded-full" style={{ width: `${pct}%` }} /></div>
          <p className="text-xs opacity-90 mt-1.5">Mes {active ?? 1} de {total} · {pct}% completado</p>
        </div>

        <div className="flex gap-2 justify-center">
          {(["camino", "timeline"] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${view === v ? "bg-[var(--gob-navy)] text-[var(--gob-bone)] border-[var(--gob-navy)]" : "border-gray-200 text-gray-500 hover:border-gray-300"}`}>
              {v === "camino" ? "Vista Camino" : "Vista Timeline"}
            </button>
          ))}
        </div>

        {view === "camino" ? (
          <>
            <div className="flex items-center gap-1 overflow-x-auto pb-2">
              {months.map(m => {
                const isDone = m.status === "done" || (active != null && m.month_index < active)
                const isCur = m.month_index === active
                return (
                  <div key={m.id} className="flex items-center shrink-0">
                    <div className={`rounded-full flex items-center justify-center font-bold transition-all ${
                      isCur ? "w-12 h-12 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs ring-4 ring-[var(--gob-navy)]/15"
                      : isDone ? "w-8 h-8 bg-blue-100 text-[var(--gob-navy)] text-xs"
                      : "w-8 h-8 bg-gray-100 text-gray-400 text-[11px]"}`}>
                      {isDone && !isCur ? "✓" : m.month_index}
                    </div>
                    {m.month_index < total && <div className={`w-4 h-1 ${isDone ? "bg-blue-200" : "bg-gray-100"}`} />}
                  </div>
                )
              })}
            </div>

            {activeMonth && (
              <div className="border-2 border-[var(--gob-navy)]/20 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] font-medium tracking-widest uppercase text-gray-400">Este mes · {MONTH_NAMES[activeMonth.period_month]} {activeMonth.period_year}</p>
                    <h2 className="text-lg font-bold">{activeMonth.focus || "Objetivo del mes"}</h2>
                  </div>
                  <span className="text-xs bg-gray-100 text-gray-600 px-3 py-1 rounded-full font-medium shrink-0">{doneCount} de {monthTasks.length} hechas</span>
                </div>
                {gateMsg && <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{gateMsg}</p>}
                <div className="space-y-2">
                  {monthTasks.map(t => <TaskRow key={t.id} task={t} busy={busyTask === t.id} onToggle={toggleTask} />)}
                  {monthTasks.length === 0 && <p className="text-sm text-gray-400">Sin tareas este mes.</p>}
                </div>
              </div>
            )}
            <p className="text-center text-xs text-gray-400">Toca una tarea para ver qué es y cómo hacerla · toca el círculo para marcarla.</p>
          </>
        ) : (
          <div className="space-y-5">
            {Array.from({ length: plan.horizon_years }, (_, y) => y + 1).map(y => (
              <div key={y}>
                <p className="text-sm font-bold text-[var(--gob-navy)] mb-2">Año {y}</p>
                <div className="grid grid-cols-12 gap-1.5">
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(mn => {
                    const abs = (y - 1) * 12 + mn
                    const m = months.find(x => x.month_index === abs)
                    const isCur = abs === active
                    const isDone = m?.status === "done" || (active != null && abs < active)
                    return (
                      <div key={mn}
                        className={`h-11 rounded-lg flex items-center justify-center text-[11px] font-semibold ${
                          isCur ? "bg-[var(--gob-navy)] text-[var(--gob-bone)] ring-2 ring-[var(--gob-navy)]/25"
                          : isDone ? "bg-blue-100 text-[var(--gob-navy)]"
                          : "bg-gray-50 text-gray-400"}`}>
                        {isDone && !isCur ? "✓" : "M" + abs}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
            <p className="text-center text-xs text-gray-400">Panorama completo — para planear, no para el día a día.</p>
          </div>
        )}
      </main>
    </div>
  )
}
