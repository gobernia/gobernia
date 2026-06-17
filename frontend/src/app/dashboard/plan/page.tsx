"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Sparkles, AlertCircle } from "lucide-react"
import AgentsCollaboration from "@/components/plan/AgentsCollaboration"
import ThemesPanel from "@/components/plan/ThemesPanel"
import DiagnosticoPanel from "@/components/plan/DiagnosticoPanel"
import MonthTimeline from "@/components/plan/MonthTimeline"
import MonthDetail from "@/components/plan/MonthDetail"
import TaskDrawer from "@/components/plan/TaskDrawer"
import CoberturaBoard from "@/components/plan/CoberturaBoard"
import CloseMonthModal from "@/components/plan/CloseMonthModal"
import MilestoneRoadmap from "@/components/plan/MilestoneRoadmap"
import {
  getAnnualPlan, getAnnualPlanStatus, generateAnnualPlan,
  updateTask, deleteTask,
  closeMonth, applyProposal,
  type AnnualPlan, type Task,
} from "@/lib/annualPlan"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

type View = "loading" | "none" | "generating" | "failed" | "active" | "error"

export default function AnnualPlanPage() {
  const [view, setView] = useState<View>("loading")
  const [plan, setPlan] = useState<AnnualPlan | null>(null)
  const [selectedMonth, setSelectedMonth] = useState(1)
  const [openTask, setOpenTask] = useState<Task | null>(null)
  const [closingMonthId, setClosingMonthId] = useState<string | null>(null)
  const [horizonYears, setHorizonYears] = useState(3)
  const [failReason, setFailReason] = useState<"datos" | "general" | null>(null)
  const [failDetail, setFailDetail] = useState<string | null>(null)
  const [closeRunning, setCloseRunning] = useState(false)
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

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { init(); return stopPolling }, [init, stopPolling])

  const onGenerate = async (isRegenerate = false) => {
    if (isRegenerate && !window.confirm("Se borrará el plan mensual anterior y se generará uno nuevo desde cero. ¿Continuar?")) {
      return
    }
    setView("generating")
    try {
      await generateAnnualPlan(horizonYears)
      setFailReason(null)
      startPolling()
    } catch (err: unknown) {
      const resp = (err as { response?: { status?: number; data?: { detail?: unknown } } })?.response
      const detail = typeof resp?.data?.detail === "string" ? resp.data.detail : null
      setFailReason(resp?.status === 400 ? "datos" : "general")
      setFailDetail(detail)
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
    try { await updateTask(taskId, patch) } catch { loadPlan().catch(() => setView("error")) }
  }

  const onDeleteTask = async (taskId: string) => {
    setOpenTask(null)
    setPlan(p => p && ({
      ...p,
      months: p.months.map(m => ({
        ...m, objectives: m.objectives.map(o => ({ ...o, tasks: o.tasks.filter(t => t.id !== taskId) })),
      })),
    }))
    try { await deleteTask(taskId) } catch { loadPlan().catch(() => setView("error")) }
  }

  const onCloseMonth = (monthlyPlanId: string) => setClosingMonthId(monthlyPlanId)

  const onSubmitClose = async (kpis: Record<string, number>) => {
    const m = plan?.months.find(mm => mm.id === closingMonthId)
    if (!m) return
    setCloseRunning(true)
    try {
      const res = await closeMonth(m.month_index, kpis)
      await loadPlan()
      setSelectedMonth(res.active_month_index)
    } catch {
      loadPlan().catch(() => setView("error"))
    } finally {
      setCloseRunning(false)
      setClosingMonthId(null)
    }
  }

  const onApplyProposal = async (monthIndex: number, proposalId: string) => {
    try {
      await applyProposal(monthIndex, proposalId)
      await loadPlan()
    } catch {
      loadPlan().catch(() => setView("error"))
    }
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
          <h1 className="text-2xl font-bold text-black">Tu consejo está diseñando tu plan estratégico</h1>
        </div>
        <AgentsCollaboration caption="Tus consejeros con IA analizan tu empresa, el Retador aplica pre-mortem, y con eso se arma tu plan estratégico anual. Esto puede tardar un par de minutos." />
      </div>
    )
  }

  if (view === "none" || view === "failed" || view === "error") {
    const isFail = view === "failed" || view === "error"
    const isDatos = isFail && failReason === "datos"
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-6 px-6 text-center">
        <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
          {isFail ? <AlertCircle className="h-5 w-5 text-red-400" /> : <Sparkles className="h-5 w-5 text-gray-300" />}
        </div>
        <div className="space-y-2 max-w-md">
          <p className="text-base font-medium text-black">
            {isDatos
              ? "Completa los datos de tu empresa"
              : isFail ? "No se pudo generar tu plan" : "Genera tu plan estratégico de 12 meses"}
          </p>
          <p className="text-sm text-gray-500 leading-relaxed">
            {isDatos
              ? (failDetail ?? "Para que tu consejo diseñe el plan necesita conocer tu empresa. Completa tus datos y vuelve a intentarlo.")
              : isFail
                ? "Algo falló al construir el plan. Puedes reintentarlo."
                : "A partir de tu onboarding, el consejo diseñará un plan anual con objetivos, tareas, responsables y KPIs."}
          </p>
        </div>
        {isDatos ? (
          <Link
            href="/dashboard/datos"
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
          >
            Completar mis datos
          </Link>
        ) : (
          <>
            {!isDatos && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Horizonte:</span>
                {[1, 2, 3].map(y => (
                  <button key={y} type="button" onClick={() => setHorizonYears(y)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border-2 transition-colors ${
                      horizonYears === y
                        ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                        : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                    {y} año{y > 1 ? "s" : ""}{y === 3 ? " ·rec" : ""}
                  </button>
                ))}
              </div>
            )}
            <button
              onClick={() => onGenerate(isFail)}
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
            >
              <Sparkles className="h-4 w-4" /> {isFail ? "Reintentar" : "Generar plan"}
            </button>
          </>
        )}
        {isFail && !isDatos && (
          <p className="text-xs text-gray-400 max-w-xs">
            Al regenerar se borrará el plan mensual anterior.
          </p>
        )}
      </div>
    )
  }

  // view === "active"
  const month = plan?.months.find(m => m.month_index === selectedMonth) ?? plan?.months[0]
  const kpiOptions = month ? Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs))) : []

  return (
    <div className="min-h-dvh bg-white text-black antialiased">
      <main>
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] py-10 space-y-8">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }} className="space-y-1">
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Plan estratégico</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">{plan?.title ?? "Plan estratégico"}</h1>
          </motion.div>

          {plan && (
            <MonthTimeline months={plan.months} selectedIndex={selectedMonth} onSelect={setSelectedMonth} />
          )}

          {plan?.milestones && <MilestoneRoadmap milestones={plan.milestones} />}

          {month && (
            <MonthDetail
              month={month}
              onTaskClick={setOpenTask}
              onUpdateTask={onUpdateTask}
              onCloseMonth={onCloseMonth}
              onApplyProposal={onApplyProposal}
            />
          )}

          <DiagnosticoPanel summary={plan?.diagnostico_summary ?? null} />

          <details className="mt-10">
            <summary className="text-xs font-medium text-gray-400 cursor-pointer hover:text-[var(--gob-navy)] select-none">
              Ver cobertura anual y temas del consejo
            </summary>
            <div className="mt-4 space-y-5">
              <CoberturaBoard />
              <ThemesPanel />
            </div>
          </details>
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

      {closingMonthId && (() => {
        const m = plan?.months.find(mm => mm.id === closingMonthId)
        return m ? (
          <CloseMonthModal
            month={m}
            running={closeRunning}
            onClose={() => setClosingMonthId(null)}
            onSubmit={onSubmitClose}
          />
        ) : null
      })()}
    </div>
  )
}
