"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, ChevronDown, Check, Clock, Gauge, Wand2, RefreshCw, Trash2, X, Download, Pencil, ArrowRight, BadgeCheck, Unlock } from "lucide-react"
import {
  AnnualPlan, Task, ExplicacionTarea, AdaptacionTarea, MONTH_NAMES,
  getAnnualPlan, getAnnualPlanStatus, updateTask, deleteTask, getTaskExplicacion,
  adaptTask, generateAnnualPlan,
} from "@/lib/annualPlan"
import { getFoda } from "@/lib/foda"
import {
  Roadmap, Meta3a, Pilar, RoadmapEstado, KpiPilar, ResultadoEsperado, Fase, TemasPorAnio,
  getRoadmap, saveRoadmap, downloadRoadmapPdf, getRoadmapEstado, validarRoadmap, reabrirRoadmap,
} from "@/lib/roadmap"

const DIF_CHIP: Record<string, string> = {
  "Fácil": "text-green-700 bg-green-50", "Media": "text-amber-700 bg-amber-50",
  "Difícil": "text-red-700 bg-red-50",
}

function TaskRow({ task, onToggle, busy, onReplaced, onRemoved }: {
  task: Task; onToggle: (t: Task) => void; busy: boolean
  onReplaced: (t: Task) => void; onRemoved: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [exp, setExp] = useState<ExplicacionTarea | null>(task.explicacion)
  const [loading, setLoading] = useState(false)
  const done = task.status === "completada"

  // Flujo "No puedo con esta tarea" → adaptar con IA
  const [adaptOpen, setAdaptOpen] = useState(false)
  const [feedback, setFeedback] = useState("")
  const [proposal, setProposal] = useState<AdaptacionTarea | null>(null)
  const [adapting, setAdapting] = useState(false)
  const [applying, setApplying] = useState(false)

  const pedirAlternativa = async () => {
    if (!feedback.trim() || adapting) return
    setAdapting(true)
    try { setProposal(await adaptTask(task.id, feedback.trim())) } catch { /* noop */ } finally { setAdapting(false) }
  }
  const reemplazar = async () => {
    if (!proposal || applying) return
    setApplying(true)
    try {
      const updated = await updateTask(task.id, { title: proposal.nueva_tarea, description: proposal.descripcion })
      onReplaced(updated)
    } catch { /* noop */ } finally { setApplying(false) }
  }
  const descartar = async () => {
    if (applying) return
    setApplying(true)
    try { await deleteTask(task.id); onRemoved(task.id) }
    catch { setApplying(false) }
  }
  const cerrarAdapt = () => { setAdaptOpen(false); setProposal(null); setFeedback("") }

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

              {!done && (
                <div className="mt-4 pt-3 border-t border-gray-100">
                  {!adaptOpen ? (
                    <button onClick={() => setAdaptOpen(true)}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
                      <Wand2 className="h-3.5 w-3.5" /> No puedo con esta tarea
                    </button>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-[11px] font-bold tracking-widest uppercase text-gray-400">Adaptar esta tarea</p>
                        <button onClick={cerrarAdapt} className="text-gray-300 hover:text-gray-500"><X className="h-3.5 w-3.5" /></button>
                      </div>

                      {!proposal ? (
                        <>
                          <textarea value={feedback} onChange={e => setFeedback(e.target.value)} rows={2}
                            placeholder="Cuéntale a Todd por qué (ej. no tengo presupuesto para un despacho)…"
                            className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                          <button onClick={pedirAlternativa} disabled={adapting || !feedback.trim()}
                            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-4 py-2 rounded-lg disabled:opacity-40 hover:bg-[var(--gob-ink)] transition-colors">
                            {adapting ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Todd está pensando…</> : <><Wand2 className="h-3.5 w-3.5" /> Pedir alternativa</>}
                          </button>
                        </>
                      ) : (
                        <div className="space-y-3">
                          <div className="rounded-xl bg-[var(--gob-navy)]/[0.04] border border-[var(--gob-navy)]/15 p-3 space-y-1.5">
                            <p className="text-[10px] font-bold tracking-widest uppercase text-[var(--gob-navy)]">Alternativa propuesta</p>
                            <p className="text-sm font-medium text-black">{proposal.nueva_tarea}</p>
                            {proposal.descripcion && <p className="text-xs text-gray-600 leading-relaxed">{proposal.descripcion}</p>}
                            {proposal.por_que && <p className="text-xs text-gray-500 italic leading-relaxed">{proposal.por_que}</p>}
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <button onClick={reemplazar} disabled={applying}
                              className="inline-flex items-center gap-1.5 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-3.5 py-2 rounded-lg disabled:opacity-50 hover:bg-[var(--gob-ink)] transition-colors">
                              {applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Reemplazar
                            </button>
                            <button onClick={descartar} disabled={applying}
                              className="inline-flex items-center gap-1.5 border border-gray-200 text-gray-600 text-xs font-medium px-3.5 py-2 rounded-lg hover:border-red-300 hover:text-red-500 transition-colors disabled:opacity-50">
                              <Trash2 className="h-3.5 w-3.5" /> Descartar tarea
                            </button>
                            <button onClick={() => { setProposal(null); setFeedback("") }} disabled={applying}
                              className="text-xs text-gray-400 hover:text-gray-600 px-2">Pedir otra</button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// --- Roadmap: edición por sección -----------------------------------------
function EditControls({ editing, onEdit, onSave, onCancel, saving, hide = false }: {
  editing: boolean; onEdit: () => void; onSave: () => void; onCancel: () => void; saving: boolean
  hide?: boolean
}) {
  if (hide) return null  // roadmap validado → solo lectura
  return editing ? (
    <div className="flex items-center gap-2 shrink-0">
      <button onClick={onSave} disabled={saving}
        className="inline-flex items-center gap-1.5 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Guardar
      </button>
      <button onClick={onCancel} disabled={saving} className="text-xs font-medium text-gray-400 hover:text-gray-600 px-2">Cancelar</button>
    </div>
  ) : (
    <button onClick={onEdit}
      className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-[var(--gob-navy)] transition-colors shrink-0">
      <Pencil className="h-3.5 w-3.5" /> Editar
    </button>
  )
}

const splitLines = (s: string): string[] => s.split("\n").map(x => x.trim()).filter(Boolean)
const joinLines = (arr: string[] | undefined | null): string => (arr ?? []).join("\n")

/** Detalle de un pilar en modo lectura: los bloques vacíos no se pintan. */
function PilarDetalle({ pilar, color }: { pilar: Pilar; color: string }) {
  const estrategias = pilar.estrategias ?? []
  const kpis = (pilar.kpis ?? []).filter(k => k.label)
  const resultados = (pilar.resultados_esperados ?? []).filter(r => r.titulo || r.descripcion)
  const vacio = !pilar.descripcion && !pilar.objetivo && estrategias.length === 0 && kpis.length === 0 && resultados.length === 0

  if (vacio) return <p className="text-xs text-gray-300 italic">Sus milestones están en el recorrido de arriba.</p>

  return (
    <div className="space-y-4">
      {pilar.descripcion && <p className="text-sm text-gray-600 leading-relaxed">{pilar.descripcion}</p>}

      {pilar.objetivo && (
        <div className="rounded-xl px-4 py-3 space-y-1" style={{ background: `${color}0d`, borderLeft: `3px solid ${color}` }}>
          <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color }}>Objetivo</p>
          <p className="text-sm text-gray-700 leading-relaxed">{pilar.objetivo}</p>
        </div>
      )}

      {estrategias.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Estrategias</p>
          <ul className="space-y-1.5">
            {estrategias.map((s, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="mt-[7px] h-1.5 w-1.5 rounded-full shrink-0" style={{ background: color }} />
                <span className="text-sm text-gray-700 leading-relaxed">{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {kpis.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">KPIs</p>
          <div className="space-y-2">
            {kpis.map((k, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-xl border border-gray-100 px-3.5 py-2.5">
                <span className="text-sm text-gray-800 font-medium leading-snug flex-1 min-w-[8rem]">{k.label}</span>
                {k.actual && (
                  <span className="text-[11px] font-medium text-gray-600 bg-gray-100 rounded-full px-2.5 py-0.5">hoy: {k.actual}</span>
                )}
                <ArrowRight className="h-3.5 w-3.5 text-gray-300 shrink-0" />
                <span className={`text-[11px] font-semibold rounded-full px-2.5 py-0.5 ${
                  k.meta ? "text-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.08]" : "text-gray-400 bg-gray-50 border border-dashed border-gray-200"}`}>
                  {k.meta ? `meta: ${k.meta}` : "meta: por definir"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {resultados.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Resultados esperados</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {resultados.map((r, i) => (
              <div key={i} className="rounded-xl p-3 space-y-1" style={{ background: `${color}0d` }}>
                {r.titulo && <p className="text-xs font-bold leading-snug" style={{ color }}>{r.titulo}</p>}
                {r.descripcion && <p className="text-[11px] text-gray-600 leading-snug">{r.descripcion}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function roadmapIsEmpty(r: Roadmap): boolean {
  return !r.vision && !r.mision && !r.propuesta_valor && !r.resumen_foda && !r.resumen_entorno &&
    (r.metas_3anios?.length ?? 0) === 0 && (r.pilares?.length ?? 0) === 0
}

type DraftEncabezado = { vision: string; mision: string; propuesta_valor: string }
type DraftPilar = {
  nombre: string; descripcion: string; anio1: string; anio2: string; anio3: string
  objetivo: string; estrategias: string
  kpis: KpiPilar[]; resultados: ResultadoEsperado[]
  fase1: string; fase2: string; fase3: string
}
type DraftTexto2 = { texto: string; conclusion: string }

const ANIO_KEYS = ["anio1", "anio2", "anio3"] as const

const KPI_SLOTS = 3
const RESULTADO_SLOTS = 3
const emptyKpi = (): KpiPilar => ({ label: "", actual: "", meta: "" })
const emptyResultado = (): ResultadoEsperado => ({ titulo: "", descripcion: "" })
/** Rellena la lista hasta `n` huecos para poder capturar filas nuevas en el formulario. */
function padSlots<T>(arr: T[] | undefined | null, n: number, make: () => T): T[] {
  const base = (arr ?? []).slice(0, n).map(x => ({ ...x }))
  while (base.length < n) base.push(make())
  return base
}

// Acentos por pilar (muteados, on-brand) para el timeline y las tarjetas.
const PILAR_COLORS = ["#1e3a5f", "#0f766e", "#b45309", "#6d28d9", "#b91c1c", "#334155"]
const pilarColor = (i: number) => PILAR_COLORS[i % PILAR_COLORS.length]

export default function PlanPage() {
  const [plan, setPlan] = useState<AnnualPlan | null>(null)
  const [active, setActive] = useState<number | null>(null)
  const [status, setStatus] = useState<string>("loading")
  const [view, setView] = useState<"roadmap" | "camino" | "timeline">("roadmap")
  const [busyTask, setBusyTask] = useState<string | null>(null)
  const [gateMsg, setGateMsg] = useState<string | null>(null)
  const [fodaReady, setFodaReady] = useState<boolean | null>(null)
  const [generating, setGenerating] = useState(false)
  const [genErr, setGenErr] = useState<string | null>(null)
  const started = useRef(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // --- Roadmap ---------------------------------------------------------
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [loadingRoadmap, setLoadingRoadmap] = useState(false)
  const [roadmapErr, setRoadmapErr] = useState<string | null>(null)
  const [downloadingRoadmap, setDownloadingRoadmap] = useState(false)
  const [savingRoadmap, setSavingRoadmap] = useState(false)
  const [estadoRoadmap, setEstadoRoadmap] = useState<RoadmapEstado | null>(null)
  const [validando, setValidando] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [draftEncabezado, setDraftEncabezado] = useState<DraftEncabezado | null>(null)
  const [draftMetas, setDraftMetas] = useState<Meta3a[] | null>(null)
  const [draftFoda, setDraftFoda] = useState<DraftTexto2 | null>(null)
  const [draftEntorno, setDraftEntorno] = useState<DraftTexto2 | null>(null)
  const [draftPilar, setDraftPilar] = useState<DraftPilar | null>(null)
  const [draftObjetivos, setDraftObjetivos] = useState<string | null>(null)
  const [draftEnablers, setDraftEnablers] = useState<string | null>(null)
  const [draftTemas, setDraftTemas] = useState<TemasPorAnio | null>(null)
  const roadmapLoaded = useRef(false)
  const aliveRef = useRef(true)

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const tick = useCallback(async () => {
    const st = await getAnnualPlanStatus().catch(() => null)
    if (!st) { setStatus("none"); stopPolling(); return }
    setActive(st.active_month_index ?? null)
    setStatus(st.status)
    if (st.status === "active" || st.status === "completed") {
      stopPolling()
      const p = await getAnnualPlan().catch(() => null)
      if (p) setPlan(p)
    } else if (st.status === "failed") {
      stopPolling()
    }
    // status "generating": seguimos en el intervalo hasta que cambie.
  }, [stopPolling])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(tick, 3000)
  }, [stopPolling, tick])

  useEffect(() => {
    if (started.current) return
    started.current = true
    tick().catch(() => setStatus("none"))
    startPolling()
    return () => stopPolling()
  }, [tick, startPolling, stopPolling])

  // En el estado vacío, averigua si la matriz FODA ya está lista (para ofrecer generar aquí).
  useEffect(() => {
    if (status === "loading" || status === "generating") return
    if ((status === "active" || status === "completed") && plan) return
    getFoda().then(f => setFodaReady(f.status === "active")).catch(() => setFodaReady(false))
  }, [status, plan])

  const generar = async () => {
    setGenerating(true); setGenErr(null)
    try {
      await generateAnnualPlan(3)
      setStatus("generating")
      startPolling()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setGenErr(detail ?? "No se pudo iniciar la generación del plan. Intenta de nuevo.")
      setGenerating(false)
    }
  }

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  // Carga el roadmap una vez, al entrar a esa vista con el plan activo.
  useEffect(() => {
    if (view !== "roadmap" || roadmapLoaded.current) return
    if (status !== "active" && status !== "completed") return
    roadmapLoaded.current = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingRoadmap(true)
    getRoadmap()
      .then(r => { if (aliveRef.current) setRoadmap(r) })
      .catch(() => { if (aliveRef.current) setRoadmapErr("No se pudo cargar tu roadmap.") })
      .finally(() => { if (aliveRef.current) setLoadingRoadmap(false) })
    getRoadmapEstado()
      .then(e => { if (aliveRef.current) setEstadoRoadmap(e) })
      .catch(() => { /* sin estado → se trata como borrador */ })
  }, [view, status])

  const clearDrafts = () => {
    setDraftEncabezado(null); setDraftMetas(null); setDraftFoda(null); setDraftEntorno(null); setDraftPilar(null)
    setDraftObjetivos(null); setDraftEnablers(null); setDraftTemas(null)
  }
  const cancelEdit = () => { setEditing(null); clearDrafts() }

  const persistRoadmap = async (next: Roadmap) => {
    setSavingRoadmap(true); setRoadmapErr(null)
    try {
      const saved = await saveRoadmap(next)
      if (aliveRef.current) { setRoadmap(saved); setEditing(null); clearDrafts() }
    } catch {
      if (aliveRef.current) setRoadmapErr("No se pudo guardar el cambio. Intenta de nuevo.")
    } finally {
      if (aliveRef.current) setSavingRoadmap(false)
    }
  }

  const startEditEncabezado = () => {
    if (!roadmap) return
    setDraftEncabezado({ vision: roadmap.vision, mision: roadmap.mision, propuesta_valor: roadmap.propuesta_valor })
    setEditing("encabezado")
  }
  const saveEncabezado = () => { if (roadmap && draftEncabezado) persistRoadmap({ ...roadmap, ...draftEncabezado }) }

  const startEditMetas = () => {
    if (!roadmap) return
    setDraftMetas((roadmap.metas_3anios ?? []).map(m => ({ ...m })))
    setEditing("metas")
  }
  const updateDraftMeta = (idx: number, patch: Partial<Meta3a>) => {
    setDraftMetas(prev => prev ? prev.map((m, i) => i === idx ? { ...m, ...patch } : m) : prev)
  }
  const saveMetas = () => { if (roadmap && draftMetas) persistRoadmap({ ...roadmap, metas_3anios: draftMetas }) }

  const startEditFoda = () => {
    if (!roadmap) return
    setDraftFoda({ texto: roadmap.resumen_foda ?? "", conclusion: roadmap.conclusion_diagnostico ?? "" })
    setEditing("foda")
  }
  const saveFoda = () => {
    if (roadmap && draftFoda) persistRoadmap({ ...roadmap, resumen_foda: draftFoda.texto, conclusion_diagnostico: draftFoda.conclusion.trim() })
  }

  const startEditEntorno = () => {
    if (!roadmap) return
    setDraftEntorno({ texto: roadmap.resumen_entorno ?? "", conclusion: roadmap.conclusion_entorno ?? "" })
    setEditing("entorno")
  }
  const saveEntorno = () => {
    if (roadmap && draftEntorno) persistRoadmap({ ...roadmap, resumen_entorno: draftEntorno.texto, conclusion_entorno: draftEntorno.conclusion.trim() })
  }

  const startEditObjetivos = () => { if (!roadmap) return; setDraftObjetivos(joinLines(roadmap.objetivos_estrategicos)); setEditing("objetivos") }
  const saveObjetivos = () => {
    if (roadmap && draftObjetivos !== null) persistRoadmap({ ...roadmap, objetivos_estrategicos: splitLines(draftObjetivos) })
  }

  const startEditEnablers = () => { if (!roadmap) return; setDraftEnablers(joinLines(roadmap.key_enablers)); setEditing("enablers") }
  const saveEnablers = () => {
    if (roadmap && draftEnablers !== null) persistRoadmap({ ...roadmap, key_enablers: splitLines(draftEnablers) })
  }

  const startEditTemas = () => {
    if (!roadmap) return
    const t = roadmap.temas_por_anio ?? {}
    setDraftTemas({ anio1: t.anio1 ?? "", anio2: t.anio2 ?? "", anio3: t.anio3 ?? "" })
    setEditing("temas")
  }
  const saveTemas = () => {
    if (!roadmap || !draftTemas) return
    const temas: TemasPorAnio = {}
    for (const yk of ANIO_KEYS) {
      const v = (draftTemas[yk] ?? "").trim()
      if (v) temas[yk] = v
    }
    persistRoadmap({ ...roadmap, temas_por_anio: temas })
  }

  const startEditPilar = (idx: number) => {
    if (!roadmap) return
    const p = roadmap.pilares[idx]
    if (!p) return
    setDraftPilar({
      nombre: p.nombre, descripcion: p.descripcion,
      anio1: joinLines(p.milestones?.anio1), anio2: joinLines(p.milestones?.anio2), anio3: joinLines(p.milestones?.anio3),
      objetivo: p.objetivo ?? "", estrategias: joinLines(p.estrategias),
      kpis: padSlots(p.kpis, KPI_SLOTS, emptyKpi),
      resultados: padSlots(p.resultados_esperados, RESULTADO_SLOTS, emptyResultado),
      fase1: p.fases?.anio1?.titulo ?? "", fase2: p.fases?.anio2?.titulo ?? "", fase3: p.fases?.anio3?.titulo ?? "",
    })
    setEditing(`pilar-${idx}`)
  }
  const updateDraftKpi = (idx: number, patch: Partial<KpiPilar>) => {
    setDraftPilar(d => d && { ...d, kpis: d.kpis.map((k, i) => i === idx ? { ...k, ...patch } : k) })
  }
  const updateDraftResultado = (idx: number, patch: Partial<ResultadoEsperado>) => {
    setDraftPilar(d => d && { ...d, resultados: d.resultados.map((r, i) => i === idx ? { ...r, ...patch } : r) })
  }
  const savePilar = (idx: number) => {
    if (!roadmap || !draftPilar) return
    const fases: Fase = {}
    const titulos = [draftPilar.fase1, draftPilar.fase2, draftPilar.fase3]
    ANIO_KEYS.forEach((yk, yi) => {
      const t = titulos[yi].trim()
      if (t) fases[yk] = { titulo: t }
    })
    const pilares: Pilar[] = roadmap.pilares.map((p, i) => i === idx ? {
      nombre: draftPilar.nombre, descripcion: draftPilar.descripcion,
      milestones: { anio1: splitLines(draftPilar.anio1), anio2: splitLines(draftPilar.anio2), anio3: splitLines(draftPilar.anio3) },
      objetivo: draftPilar.objetivo.trim(),
      estrategias: splitLines(draftPilar.estrategias),
      kpis: draftPilar.kpis
        .map(k => ({ label: k.label.trim(), actual: k.actual.trim(), meta: k.meta.trim() }))
        .filter(k => k.label),
      resultados_esperados: draftPilar.resultados
        .map(r => ({ titulo: r.titulo.trim(), descripcion: r.descripcion.trim() }))
        .filter(r => r.titulo || r.descripcion),
      fases,
    } : p)
    persistRoadmap({ ...roadmap, pilares })
  }

  const onDownloadRoadmap = async () => {
    setDownloadingRoadmap(true)
    try { await downloadRoadmapPdf() } catch { /* noop */ } finally { setDownloadingRoadmap(false) }
  }

  const validado = estadoRoadmap?.status === "validado"
  const objetivos = roadmap?.objetivos_estrategicos ?? []
  const enablers = roadmap?.key_enablers ?? []
  const temas = roadmap?.temas_por_anio ?? {}
  const hayTemas = ANIO_KEYS.some(yk => !!temas[yk])

  const onValidar = async () => {
    setValidando(true); setRoadmapErr(null)
    try {
      const e = await validarRoadmap()
      if (aliveRef.current) { setEstadoRoadmap(e); setEditing(null); clearDrafts() }
    } catch {
      if (aliveRef.current) setRoadmapErr("No se pudo validar el roadmap. Intenta de nuevo.")
    } finally {
      if (aliveRef.current) setValidando(false)
    }
  }

  const onReabrir = async () => {
    setValidando(true); setRoadmapErr(null)
    try {
      const e = await reabrirRoadmap()
      if (aliveRef.current) setEstadoRoadmap(e)
    } catch {
      if (aliveRef.current) setRoadmapErr("No se pudo reabrir el roadmap. Intenta de nuevo.")
    } finally {
      if (aliveRef.current) setValidando(false)
    }
  }

  const fechaValidacion = estadoRoadmap?.validated_at
    ? new Date(estadoRoadmap.validated_at).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })
    : null

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
  function removeTaskInPlan(p: AnnualPlan, taskId: string): AnnualPlan {
    return { ...p, months: p.months.map(m => ({ ...m, objectives: m.objectives.map(o => ({ ...o, tasks: o.tasks.filter(x => x.id !== taskId) })) })) }
  }
  const onTaskReplaced = (t: Task) => setPlan(prev => prev ? patchTaskInPlan(prev, t) : prev)
  const onTaskRemoved = (taskId: string) => setPlan(prev => prev ? removeTaskInPlan(prev, taskId) : prev)

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
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-4 text-center px-6">
        {fodaReady === null ? (
          <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
        ) : fodaReady ? (
          <>
            <div className="space-y-1.5 max-w-md">
              <p className="text-base font-medium text-black">Tu matriz FODA está lista</p>
              <p className="text-sm text-gray-500 leading-relaxed">
                Genera tu plan estratégico a 3 años: el consejo lo arma a partir de tu diagnóstico y tu FODA.
              </p>
            </div>
            <button onClick={generar} disabled={generating}
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
              {generating ? <><Loader2 className="h-4 w-4 animate-spin" /> Iniciando…</> : "Generar mi plan a 3 años →"}
            </button>
            {genErr && <p className="text-xs text-red-500 max-w-md">{genErr}</p>}
          </>
        ) : (
          <>
            <p className="text-sm text-gray-500">Aún no tienes un plan. Primero completa tu matriz FODA.</p>
            <a href="/dashboard/foda" className="text-sm font-medium text-[var(--gob-navy)] hover:underline">Ir al FODA →</a>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="min-h-dvh bg-white text-black">
      {view === "roadmap" && (
        <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-gray-100">
          <div className="max-w-3xl mx-auto px-[var(--px-fluid)] py-3.5 flex items-center justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">Tu plan · {plan.horizon_years} años</p>
              <h1 className="text-lg sm:text-xl font-bold tracking-tight truncate">
                Roadmap estratégico{roadmap?.anio_objetivo ? ` al ${roadmap.anio_objetivo}` : ""}
              </h1>
            </div>
            {roadmap && !roadmapIsEmpty(roadmap) && (
              <button onClick={onDownloadRoadmap} disabled={downloadingRoadmap}
                className="inline-flex items-center gap-2 border border-gray-200 text-sm font-medium text-gray-700 px-3.5 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50 shrink-0">
                {downloadingRoadmap ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                PDF
              </button>
            )}
          </div>
        </div>
      )}

      <main className="max-w-3xl mx-auto px-[var(--px-fluid)] py-10 space-y-8">
        {view !== "roadmap" && (
          <div className="bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-2xl p-6">
            <p className="text-[10px] font-medium tracking-widest uppercase opacity-70">Tu plan · {plan.horizon_years} años</p>
            <h1 className="text-2xl font-bold mt-1">{plan.title || "Plan estratégico"}</h1>
            <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden"><div className="h-full bg-white rounded-full" style={{ width: `${pct}%` }} /></div>
            <p className="text-xs opacity-90 mt-1.5">Mes {active ?? 1} de {total} · {pct}% completado</p>
          </div>
        )}

        <div className="flex gap-2 justify-center">
          {(["roadmap", "camino", "timeline"] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${view === v ? "bg-[var(--gob-navy)] text-[var(--gob-bone)] border-[var(--gob-navy)]" : "border-gray-200 text-gray-500 hover:border-gray-300"}`}>
              {v === "roadmap" ? "Roadmap" : v === "camino" ? "Vista Camino" : "Vista Timeline"}
            </button>
          ))}
        </div>

        {view === "roadmap" ? (
          <div className="space-y-6">
            {roadmapErr && <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{roadmapErr}</p>}

            {(loadingRoadmap || (!roadmap && !roadmapErr)) && (
              <div className="border border-gray-100 rounded-2xl p-16 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
              </div>
            )}

            {!loadingRoadmap && roadmap && roadmapIsEmpty(roadmap) && (
              <div className="border border-gray-100 rounded-2xl p-12 text-center space-y-2">
                <p className="text-sm font-medium text-black">Tu roadmap se está preparando…</p>
                <p className="text-xs text-gray-500 max-w-md mx-auto leading-relaxed">
                  Si tu plan ya está activo y este mensaje no cambia, regenera tu plan para crear el roadmap.
                </p>
              </div>
            )}

            {!loadingRoadmap && roadmap && !roadmapIsEmpty(roadmap) && (
              <>
                {/* Fase: revisión (borrador) o sellado (validado) */}
                {!validado ? (
                  <div className="rounded-2xl border-2 border-dashed border-[var(--gob-navy)]/25 bg-[var(--gob-navy)]/[0.03] p-5 space-y-2">
                    <p className="text-[10px] font-bold tracking-widest uppercase text-[var(--gob-navy)]">
                      Fase de revisión · borrador
                    </p>
                    <p className="text-sm text-gray-700 leading-relaxed">
                      Este es el <strong>borrador</strong> que preparó tu consejo. Revísalo y <strong>ajusta el
                      contenido</strong> con el botón <strong>Editar</strong> de cada bloque (visión, metas, pilares…).
                      El formato no se modifica.
                    </p>
                    <p className="text-sm text-gray-700 leading-relaxed">
                      Cuando estés conforme, pulsa <strong>Validar roadmap</strong> (abajo): quedará sellado, en solo
                      lectura, <strong>registrado para tu próxima sesión de consejo</strong> y guardado en tu Biblioteca.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-green-200 bg-green-50/60 p-5 flex items-start justify-between gap-4 flex-wrap">
                    <div className="space-y-1 min-w-0">
                      <p className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-widest uppercase text-green-700">
                        <BadgeCheck className="h-3.5 w-3.5" /> Validado{fechaValidacion ? ` · ${fechaValidacion}` : ""}
                      </p>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        Tu roadmap está sellado y en solo lectura. Quedó <strong>registrado para tu próxima sesión de
                        consejo</strong> y guardado en tu <strong>Biblioteca</strong>.
                      </p>
                    </div>
                    <button onClick={onReabrir} disabled={validando}
                      className="inline-flex items-center gap-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 px-4 py-2.5 rounded-xl hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50 shrink-0">
                      {validando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
                      Reabrir para editar
                    </button>
                  </div>
                )}

                {/* Encabezado ejecutivo */}
                <section className="rounded-2xl border border-gray-100 p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-base font-bold text-black tracking-tight">Encabezado ejecutivo</h2>
                    <EditControls editing={editing === "encabezado"} onEdit={startEditEncabezado} onSave={saveEncabezado} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                  </div>
                  {editing === "encabezado" && draftEncabezado ? (
                    <div className="space-y-3">
                      <div>
                        <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Visión</p>
                        <textarea value={draftEncabezado.vision} onChange={e => setDraftEncabezado(d => d && { ...d, vision: e.target.value })} rows={2}
                          className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      </div>
                      <div>
                        <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Misión</p>
                        <textarea value={draftEncabezado.mision} onChange={e => setDraftEncabezado(d => d && { ...d, mision: e.target.value })} rows={2}
                          className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      </div>
                      <div>
                        <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Propuesta de valor</p>
                        <textarea value={draftEncabezado.propuesta_valor} onChange={e => setDraftEncabezado(d => d && { ...d, propuesta_valor: e.target.value })} rows={2}
                          className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {roadmap.vision && (
                        <div><p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Visión</p>
                          <p className="text-sm text-gray-700 leading-relaxed">{roadmap.vision}</p></div>
                      )}
                      {roadmap.mision && (
                        <div><p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Misión</p>
                          <p className="text-sm text-gray-700 leading-relaxed">{roadmap.mision}</p></div>
                      )}
                      {roadmap.propuesta_valor && (
                        <div><p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Propuesta de valor</p>
                          <p className="text-sm text-gray-700 leading-relaxed">{roadmap.propuesta_valor}</p></div>
                      )}
                      {!roadmap.vision && !roadmap.mision && !roadmap.propuesta_valor && (
                        <p className="text-xs text-gray-300 italic">Sin contenido aún.</p>
                      )}
                    </div>
                  )}
                </section>

                {/* Metas a 3 años */}
                <section className="rounded-2xl border border-gray-100 p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-base font-bold text-black tracking-tight">Metas a 3 años</h2>
                    <EditControls editing={editing === "metas"} onEdit={startEditMetas} onSave={saveMetas} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                  </div>
                  {editing === "metas" && draftMetas ? (
                    <div className="space-y-4">
                      {draftMetas.map((m, i) => (
                        <div key={i} className="rounded-xl border border-gray-100 p-3.5 space-y-2">
                          <textarea value={m.meta} onChange={e => updateDraftMeta(i, { meta: e.target.value })} rows={2} placeholder="Meta"
                            className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            <input value={m.kpi ?? ""} onChange={e => updateDraftMeta(i, { kpi: e.target.value })} placeholder="KPI"
                              className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                            <input value={m.valor_actual ?? ""} onChange={e => updateDraftMeta(i, { valor_actual: e.target.value })} placeholder="Valor actual"
                              className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                            <input value={m.target} onChange={e => updateDraftMeta(i, { target: e.target.value })} placeholder="Meta objetivo (target)"
                              className="w-full rounded-lg border-2 border-[var(--gob-navy)]/30 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                          </div>
                        </div>
                      ))}
                      {draftMetas.length === 0 && <p className="text-xs text-gray-300 italic">Sin metas aún.</p>}
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {(roadmap.metas_3anios ?? []).map((m, i) => (
                        <div key={i} className="rounded-xl border border-gray-100 p-3.5 space-y-2">
                          <p className="text-sm text-gray-800 font-medium leading-snug">{m.meta}</p>
                          <div className="flex flex-wrap items-center gap-2">
                            {m.kpi && <span className="text-[11px] text-gray-500 bg-gray-50 rounded-full px-2 py-0.5">{m.kpi}</span>}
                            {m.valor_actual && (
                              <span className="text-[11px] font-medium text-gray-600 bg-gray-100 rounded-full px-2.5 py-0.5">hoy: {m.valor_actual}</span>
                            )}
                            {(m.valor_actual || m.target) && <ArrowRight className="h-3.5 w-3.5 text-gray-300 shrink-0" />}
                            <span className={`text-[11px] font-semibold rounded-full px-2.5 py-0.5 ${
                              m.target
                                ? "text-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.08]"
                                : "text-gray-400 bg-gray-50 border border-dashed border-gray-200"}`}>
                              {m.target ? `meta: ${m.target}` : "meta: por definir"}
                            </span>
                          </div>
                        </div>
                      ))}
                      {(roadmap.metas_3anios ?? []).length === 0 && <p className="text-xs text-gray-300 italic">Sin metas aún.</p>}
                    </div>
                  )}
                </section>

                {/* Objetivos estratégicos */}
                {(objetivos.length > 0 || !validado) && (
                  <section className="rounded-2xl border border-gray-100 p-5 space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="text-base font-bold text-black tracking-tight">Objetivos estratégicos</h2>
                      <EditControls editing={editing === "objetivos"} onEdit={startEditObjetivos} onSave={saveObjetivos} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                    </div>
                    {editing === "objetivos" ? (
                      <textarea value={draftObjetivos ?? ""} onChange={e => setDraftObjetivos(e.target.value)} rows={5}
                        placeholder="Un objetivo por línea"
                        className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                    ) : objetivos.length > 0 ? (
                      <ol className="space-y-2.5">
                        {objetivos.map((o, i) => (
                          <li key={i} className="flex items-start gap-3">
                            <span className="mt-0.5 h-5 w-5 shrink-0 rounded-full bg-[var(--gob-navy)]/[0.08] text-[var(--gob-navy)] text-[11px] font-bold flex items-center justify-center">{i + 1}</span>
                            <span className="text-sm text-gray-700 leading-relaxed">{o}</span>
                          </li>
                        ))}
                      </ol>
                    ) : <p className="text-xs text-gray-300 italic">Sin objetivos aún.</p>}
                  </section>
                )}

                {/* Key enablers (habilitadores transversales) */}
                {(enablers.length > 0 || !validado) && (
                  <section className="rounded-2xl border border-gray-100 p-5 space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="text-base font-bold text-black tracking-tight">Habilitadores clave</h2>
                        <p className="text-xs text-gray-400 mt-0.5">Lo transversal que sostiene los tres años.</p>
                      </div>
                      <EditControls editing={editing === "enablers"} onEdit={startEditEnablers} onSave={saveEnablers} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                    </div>
                    {editing === "enablers" ? (
                      <textarea value={draftEnablers ?? ""} onChange={e => setDraftEnablers(e.target.value)} rows={4}
                        placeholder="Un habilitador por línea (talento, tecnología, capital, gobernanza…)"
                        className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                    ) : enablers.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {enablers.map((k, i) => (
                          <span key={i} className="text-xs font-medium text-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.06] border border-[var(--gob-navy)]/15 rounded-full px-3 py-1.5">{k}</span>
                        ))}
                      </div>
                    ) : <p className="text-xs text-gray-300 italic">Sin habilitadores aún.</p>}
                  </section>
                )}

                {/* Resumen FODA */}
                <section className="rounded-2xl border border-gray-100 p-5 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-base font-bold text-black tracking-tight">Resumen FODA</h2>
                    <EditControls editing={editing === "foda"} onEdit={startEditFoda} onSave={saveFoda} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                  </div>
                  {editing === "foda" && draftFoda ? (
                    <div className="space-y-3">
                      <textarea value={draftFoda.texto} onChange={e => setDraftFoda(d => d && { ...d, texto: e.target.value })} rows={5}
                        className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      <div>
                        <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Conclusión del diagnóstico</p>
                        <textarea value={draftFoda.conclusion} onChange={e => setDraftFoda(d => d && { ...d, conclusion: e.target.value })} rows={3}
                          placeholder="La lectura de fondo: qué nos dice el diagnóstico."
                          className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      </div>
                    </div>
                  ) : (
                    <>
                      {roadmap.resumen_foda ? (
                        <div className="space-y-2">
                          {roadmap.resumen_foda.split("\n").filter(p => p.trim()).map((p, j) => (
                            <p key={j} className="text-sm text-gray-700 leading-relaxed">{p.trim()}</p>
                          ))}
                        </div>
                      ) : <p className="text-xs text-gray-300 italic">Sin contenido aún.</p>}
                      {roadmap.conclusion_diagnostico && (
                        <div className="rounded-xl border-l-4 border-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.04] px-4 py-3 space-y-1">
                          <p className="text-[10px] font-bold tracking-widest uppercase text-[var(--gob-navy)]">Conclusión del diagnóstico</p>
                          <p className="text-sm text-gray-700 leading-relaxed">{roadmap.conclusion_diagnostico}</p>
                        </div>
                      )}
                    </>
                  )}
                </section>

                {/* Resumen del entorno */}
                <section className="rounded-2xl border border-gray-100 p-5 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-base font-bold text-black tracking-tight">Resumen del entorno</h2>
                    <EditControls editing={editing === "entorno"} onEdit={startEditEntorno} onSave={saveEntorno} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                  </div>
                  {editing === "entorno" && draftEntorno ? (
                    <div className="space-y-3">
                      <textarea value={draftEntorno.texto} onChange={e => setDraftEntorno(d => d && { ...d, texto: e.target.value })} rows={5}
                        className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      <div>
                        <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Conclusión del entorno</p>
                        <textarea value={draftEntorno.conclusion} onChange={e => setDraftEntorno(d => d && { ...d, conclusion: e.target.value })} rows={3}
                          placeholder="Qué significa el entorno para la empresa."
                          className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                      </div>
                    </div>
                  ) : (
                    <>
                      {roadmap.resumen_entorno ? (
                        <div className="space-y-2">
                          {roadmap.resumen_entorno.split("\n").filter(p => p.trim()).map((p, j) => (
                            <p key={j} className="text-sm text-gray-700 leading-relaxed">{p.trim()}</p>
                          ))}
                        </div>
                      ) : <p className="text-xs text-gray-300 italic">Sin contenido aún.</p>}
                      {roadmap.conclusion_entorno && (
                        <div className="rounded-xl border-l-4 border-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.04] px-4 py-3 space-y-1">
                          <p className="text-[10px] font-bold tracking-widest uppercase text-[var(--gob-navy)]">Conclusión del entorno</p>
                          <p className="text-sm text-gray-700 leading-relaxed">{roadmap.conclusion_entorno}</p>
                        </div>
                      )}
                    </>
                  )}
                </section>

                {/* Recorrido a 3 años — timeline visual (signature) */}
                {((roadmap.pilares ?? []).some(p =>
                  ((p.milestones?.anio1?.length ?? 0) + (p.milestones?.anio2?.length ?? 0) + (p.milestones?.anio3?.length ?? 0)) > 0)
                  || hayTemas || (!validado && (roadmap.pilares ?? []).length > 0)) && (
                  <section className="rounded-2xl border border-gray-100 p-5 space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="text-base font-bold text-black tracking-tight">Recorrido a 3 años</h2>
                      <EditControls editing={editing === "temas"} onEdit={startEditTemas} onSave={saveTemas} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                    </div>

                    {editing === "temas" && draftTemas && (
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {ANIO_KEYS.map((yk, yi) => (
                          <div key={yk} className="space-y-1.5">
                            <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Lema del año {yi + 1}</p>
                            <input value={draftTemas[yk] ?? ""} onChange={e => setDraftTemas(d => d && { ...d, [yk]: e.target.value })}
                              placeholder={yi === 0 ? "Ordenar la casa" : yi === 1 ? "Expandir el negocio" : "Consolidar el liderazgo"}
                              className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="overflow-x-auto -mx-1 px-1">
                      <div className="min-w-[620px] space-y-2.5">
                        <div className="grid grid-cols-[132px_1fr_1fr_1fr] gap-3 items-end">
                          <div />
                          {ANIO_KEYS.map((yk, yi) => (
                            <div key={yk} className="text-center pb-1">
                              <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Año {yi + 1}</p>
                              {temas[yk] && (
                                <p className="text-[11px] font-semibold text-[var(--gob-navy)] leading-tight mt-0.5">{temas[yk]}</p>
                              )}
                            </div>
                          ))}
                        </div>
                        {(roadmap.pilares ?? []).map((p, i) => {
                          const c = pilarColor(i)
                          return (
                            <div key={i} className="grid grid-cols-[132px_1fr_1fr_1fr] gap-3 items-stretch">
                              <div className="flex items-center gap-2 min-w-0 py-1">
                                <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: c }} />
                                <span className="text-xs font-semibold text-gray-700 leading-tight">{p.nombre || `Pilar ${i + 1}`}</span>
                              </div>
                              {ANIO_KEYS.map(yk => {
                                const items = p.milestones?.[yk] ?? []
                                const fase = p.fases?.[yk]?.titulo
                                return (
                                  <div key={yk} className="rounded-lg p-2 flex flex-col gap-1.5" style={{ background: `${c}0d` }}>
                                    {fase && (
                                      <p className="text-[9px] font-bold tracking-widest uppercase leading-tight" style={{ color: c }}>{fase}</p>
                                    )}
                                    {items.length === 0 ? (
                                      <div className="flex-1 min-h-[1.75rem] flex items-center justify-center">
                                        <span className="h-0.5 w-6 rounded-full" style={{ background: `${c}33` }} />
                                      </div>
                                    ) : items.map((ms, mi) => (
                                      <div key={mi} className="text-[11px] leading-snug rounded-md px-2 py-1" style={{ background: `${c}1a`, color: c }}>{ms}</div>
                                    ))}
                                  </div>
                                )
                              })}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </section>
                )}

                {/* Pilares estratégicos (detalle + edición) */}
                <div className="space-y-4">
                  <h2 className="text-base font-bold text-black tracking-tight px-1">Pilares estratégicos</h2>
                  {(roadmap.pilares ?? []).map((p, i) => {
                    const key = `pilar-${i}`
                    const isEditing = editing === key
                    const c = pilarColor(i)
                    return (
                      <section key={i} className="rounded-2xl border border-gray-100 border-t-4 p-5 space-y-4" style={{ borderTopColor: c }}>
                        <div className="flex items-center justify-between gap-3">
                          {isEditing && draftPilar ? (
                            <input value={draftPilar.nombre} onChange={e => setDraftPilar(d => d && { ...d, nombre: e.target.value })}
                              className="flex-1 rounded-lg border-2 border-gray-100 px-3 py-1.5 text-sm font-bold focus:border-[var(--gob-navy)] focus:outline-none" />
                          ) : (
                            <h3 className="flex items-center gap-2 text-base font-bold text-black tracking-tight">
                              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: c }} />
                              {p.nombre || `Pilar ${i + 1}`}
                            </h3>
                          )}
                          <EditControls editing={isEditing} onEdit={() => startEditPilar(i)} onSave={() => savePilar(i)} onCancel={cancelEdit} saving={savingRoadmap} hide={validado} />
                        </div>

                        {isEditing && draftPilar ? (
                          <>
                            <textarea value={draftPilar.descripcion} onChange={e => setDraftPilar(d => d && { ...d, descripcion: e.target.value })} rows={2}
                              placeholder="Descripción del pilar"
                              className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />

                            <div>
                              <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Objetivo</p>
                              <textarea value={draftPilar.objetivo} onChange={e => setDraftPilar(d => d && { ...d, objetivo: e.target.value })} rows={2}
                                placeholder="El objetivo estratégico de este pilar"
                                className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                            </div>

                            <div>
                              <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400 mb-1">Estrategias</p>
                              <textarea value={draftPilar.estrategias} onChange={e => setDraftPilar(d => d && { ...d, estrategias: e.target.value })} rows={4}
                                placeholder="Una estrategia por línea"
                                className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                            </div>

                            <div className="space-y-2">
                              <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">KPIs</p>
                              {draftPilar.kpis.map((k, ki) => (
                                <div key={ki} className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                  <input value={k.label} onChange={e => updateDraftKpi(ki, { label: e.target.value })} placeholder="Indicador"
                                    className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                                  <input value={k.actual} onChange={e => updateDraftKpi(ki, { actual: e.target.value })} placeholder="Hoy"
                                    className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                                  <input value={k.meta} onChange={e => updateDraftKpi(ki, { meta: e.target.value })} placeholder="Meta"
                                    className="w-full rounded-lg border-2 border-[var(--gob-navy)]/30 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                                </div>
                              ))}
                            </div>

                            <div className="space-y-2">
                              <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Resultados esperados</p>
                              {draftPilar.resultados.map((r, ri) => (
                                <div key={ri} className="grid grid-cols-1 sm:grid-cols-[1fr_2fr] gap-2">
                                  <input value={r.titulo} onChange={e => updateDraftResultado(ri, { titulo: e.target.value })} placeholder="Título (ej. ↑ Margen bruto)"
                                    className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                                  <input value={r.descripcion} onChange={e => updateDraftResultado(ri, { descripcion: e.target.value })} placeholder="Descripción"
                                    className="w-full rounded-lg border-2 border-gray-100 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
                                </div>
                              ))}
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                              {ANIO_KEYS.map((yk, yi) => {
                                const faseKey = (["fase1", "fase2", "fase3"] as const)[yi]
                                return (
                                  <div key={yk} className="space-y-1.5">
                                    <p className="text-[10px] font-bold tracking-widest uppercase text-gray-400">Año {yi + 1}</p>
                                    <input value={draftPilar[faseKey]} onChange={e => setDraftPilar(d => d && { ...d, [faseKey]: e.target.value })}
                                      placeholder="Título de la fase"
                                      className="w-full rounded-lg border-2 border-gray-100 px-2.5 py-2 text-xs focus:border-[var(--gob-navy)] focus:outline-none" />
                                    <textarea value={draftPilar[yk]} onChange={e => setDraftPilar(d => d && { ...d, [yk]: e.target.value })} rows={4}
                                      placeholder="Un milestone por línea"
                                      className="w-full rounded-lg border-2 border-gray-100 px-2.5 py-2 text-xs focus:border-[var(--gob-navy)] focus:outline-none resize-none" />
                                  </div>
                                )
                              })}
                            </div>
                          </>
                        ) : (
                          <PilarDetalle pilar={p} color={c} />
                        )}
                      </section>
                    )
                  })}
                  {(roadmap.pilares ?? []).length === 0 && <p className="text-xs text-gray-300 italic px-1">Sin pilares aún.</p>}
                </div>

                {/* Validar el roadmap (cierra la fase de revisión) */}
                {!validado && (
                  <div className="pt-2 flex flex-col items-center gap-2">
                    <button onClick={onValidar} disabled={validando}
                      className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
                      {validando
                        ? <><Loader2 className="h-4 w-4 animate-spin" /> Validando…</>
                        : <><BadgeCheck className="h-4 w-4" /> Validar roadmap</>}
                    </button>
                    <p className="text-xs text-gray-400 text-center max-w-md leading-relaxed">
                      Al validar queda en solo lectura y se registra para tu próxima sesión de consejo.
                      Podrás reabrirlo si necesitas cambiar algo.
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        ) : view === "camino" ? (
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
                  {monthTasks.map(t => <TaskRow key={t.id} task={t} busy={busyTask === t.id} onToggle={toggleTask} onReplaced={onTaskReplaced} onRemoved={onTaskRemoved} />)}
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
