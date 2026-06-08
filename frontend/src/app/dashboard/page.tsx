"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, LogOut, Play, ChevronRight,
  CheckCircle2, Circle, ArrowUpRight, X, Loader2, ChevronDown,
  Settings, Sparkles,
} from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Data ──────────────────────────────────────────────────
const AGENTS = [
  { tag: "Consejero en", name: "Finanzas",     desc: "Rentabilidad, flujo de caja y estructura de capital." },
  { tag: "Consejero en", name: "Estrategia",   desc: "Posicionamiento, mercado y crecimiento a largo plazo." },
  { tag: "Consejero en", name: "Riesgos",      desc: "Riesgos operativos, legales y planes de mitigación." },
  { tag: "Consejero en", name: "Auditoría",    desc: "Cumplimiento, control interno y Governance Score." },
  { tag: "Consejero",    name: "Independiente", desc: "El Retador: cuestiona cada decisión con un pre-mortem antes de actuar." },
]

const ETAPAS = [
  { n: 1, label: "Empresa" },
  { n: 2, label: "Equipo" },
  { n: 3, label: "Prioridades" },
  { n: 4, label: "Diagnóstico" },
  { n: 5, label: "KPIs" },
  { n: 6, label: "Gobierno" },
  { n: 7, label: "Documentos" },
  { n: 8, label: "Visión" },
]

const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

// ── Types ─────────────────────────────────────────────────
interface AreaQuestion {
  question_id: string
  text: string
  response: string
}

interface AreaCompletion {
  label: string
  is_external: boolean
  total: number
  answered: number
  skipped: number
  pct: number
  questions: AreaQuestion[]
}

interface CompanySummary {
  company_name: string
  industry: string
  governance_score?: number
  activated_modules: string[]
  diagnostic_area_completion?: Record<string, AreaCompletion>
}

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
  period_label: string
  status: string
  governance_score_snapshot: number | null
  message_count: number
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────
function greeting() {
  const h = new Date().getHours()
  if (h < 12) return "Buenos días"
  if (h < 19) return "Buenas tardes"
  return "Buenas noches"
}

function todayLabel() {
  return new Date().toLocaleDateString("es-MX", {
    weekday: "long", day: "numeric", month: "long",
  })
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: "Borrador", active: "Activa", completed: "Completada",
  }
  return map[s] ?? s
}

// ── Page ──────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter()
  const { sessionId, completedStages, hydrate, reset } = useOnboardingStore()

  const [userEmail,   setUserEmail]   = useState<string | null>(null)
  const [summary,     setSummary]     = useState<CompanySummary | null>(null)
  const [sessions,    setSessions]    = useState<BoardSession[]>([])
  const [sessLoading, setSessLoading] = useState(true)

  const [expandedArea, setExpandedArea] = useState<string | null>(null)
  const [showSetupModal, setShowSetupModal] = useState(false)

  // Nova sesión modal state
  const [showModal,    setShowModal]   = useState(false)
  const [modalYear,    setModalYear]   = useState(new Date().getFullYear())
  const [modalMonth,   setModalMonth]  = useState(new Date().getMonth() + 1)
  const [creating,     setCreating]    = useState(false)
  const [createError,  setCreateError] = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null)
    })

    // Si no hay sessionId en local (usuario en navegador nuevo / cleared storage),
    // pregunta al backend si ya hay una sesión y la hidrata.
    if (!sessionId) {
      api.get("/onboarding/my-session")
        .then(r => {
          if (r.data?.session_id) {
            hydrate(r.data.session_id, r.data.completed_stages ?? [])
          }
        })
        .catch(() => {})
    } else {
      api.get(`/onboarding/${sessionId}/summary`)
        .then(r => setSummary(r.data))
        .catch(() => {})
      // Re-sincroniza completed_stages del backend por si difieren
      api.get(`/onboarding/session/${sessionId}`)
        .then(r => {
          const backendStages = r.data?.completed_stages ?? []
          if (Array.isArray(backendStages)) {
            hydrate(sessionId, backendStages)
          }
        })
        .catch(() => {})
    }

    api.get("/board-sessions")
      .then(r => setSessions(r.data))
      .catch(() => {})
      .finally(() => setSessLoading(false))
  }, [sessionId, hydrate])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    reset()
    router.push("/")
  }

  const openModal = () => {
    setModalYear(new Date().getFullYear())
    setModalMonth(new Date().getMonth() + 1)
    setCreateError(null)
    setShowModal(true)
  }

  const createSession = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const r = await api.post("/board-sessions", {
        period_year: modalYear,
        period_month: modalMonth,
      })
      setShowModal(false)
      router.push(`/dashboard/sesion/${r.data.board_session_id}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        // Ya existe — buscar la sesión existente y navegar a ella
        const existing = sessions.find(
          s => s.period_year === modalYear && s.period_month === modalMonth
        )
        if (existing) {
          setShowModal(false)
          router.push(`/dashboard/sesion/${existing.board_session_id}`)
          return
        }
      }
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(msg ?? "No se pudo crear la sesión. Intenta de nuevo.")
    } finally {
      setCreating(false)
    }
  }

  const onboardingComplete = completedStages.length >= 8
  const onboardingStarted  = completedStages.length > 0 || !!sessionId
  const nextEtapa          = ETAPAS.find(e => !completedStages.includes(e.n))
  const companyName        = summary?.company_name ?? null
  const governanceScore    = summary?.governance_score ?? null

  const tryCreateSession = () => {
    if (onboardingComplete) openModal()
    else setShowSetupModal(true)
  }

  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">

      {/* ── Navbar ───────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] h-14 flex items-center justify-between">
          <GoberniaLogo size={16} />

          <div className="flex items-center gap-5">
            {onboardingStarted && (
              <Link
                href="/dashboard/datos"
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
              >
                <Settings className="h-3.5 w-3.5" />
                Mis datos
              </Link>
            )}
            {userEmail && (
              <span className="text-xs text-gray-400 hidden sm:block">{userEmail}</span>
            )}
            <button
              onClick={handleSignOut}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* ── Setup-required modal ─────────────────────────── */}
      <AnimatePresence>
        {showSetupModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowSetupModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5"
            >
              <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-black" />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-black">Configura tu empresa primero</h2>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Para que el consejo de IA te entregue análisis útiles, necesitamos conocer
                  tu empresa: industria, equipo, prioridades, KPIs y gobierno. Toma unos minutos
                  y solo se hace una vez. Después podrás iniciar sesiones cuando quieras.
                </p>
              </div>
              {!onboardingComplete && completedStages.length > 0 && (
                <div className="bg-gray-50 rounded-xl p-3">
                  <p className="text-xs text-gray-500">
                    Vas en {completedStages.length} de 8 etapas
                    {nextEtapa && ` · siguiente: ${nextEtapa.label}`}
                  </p>
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => setShowSetupModal(false)}
                  className="flex-1 text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
                >
                  Más tarde
                </button>
                <Link
                  href={nextEtapa ? `/onboarding/etapa-${nextEtapa.n}` : "/onboarding/etapa-1"}
                  className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
                >
                  {completedStages.length > 0 ? "Continuar configuración" : "Empezar"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Nueva sesión modal ───────────────────────────── */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-6"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-black">Nueva sesión de consejo</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Selecciona el periodo a analizar</p>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Month selector */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Mes</p>
                <div className="grid grid-cols-4 gap-1.5">
                  {MONTH_NAMES.slice(1).map((m, i) => (
                    <button
                      key={i + 1}
                      onClick={() => setModalMonth(i + 1)}
                      className={`py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalMonth === i + 1
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {m.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Year selector */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Año</p>
                <div className="flex gap-2">
                  {years.map(y => (
                    <button
                      key={y}
                      onClick={() => setModalYear(y)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalYear === y
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"
                      }`}
                    >
                      {y}
                    </button>
                  ))}
                </div>
              </div>

              {createError && (
                <p className="text-xs text-red-500">{createError}</p>
              )}

              <button
                onClick={createSession}
                disabled={creating}
                className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50"
              >
                {creating
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Creando…</>
                  : <>Crear sesión de {MONTH_NAMES[modalMonth]} {modalYear} <ArrowRight className="h-4 w-4" /></>
                }
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main className="pt-14">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] py-12 space-y-14">

          {/* ── Greeting ─────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
            className="space-y-1"
          >
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
              {todayLabel()}
            </p>
            <h1 className="text-3xl font-bold text-black tracking-tight">
              {greeting()}{companyName ? `, ${companyName}` : ""}.
            </h1>
            {!onboardingComplete && (
              <p className="italic font-light text-sm text-gray-500 mt-1">
                {completedStages.length === 0
                  ? "Bienvenido a Gobernia. Configura tu empresa cuando estés listo."
                  : "Completa la configuración para activar tu consejo de IA."}
              </p>
            )}
          </motion.div>

          {/* ── Onboarding banner ────────────────────────── */}
          {!onboardingComplete && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
              className="border border-gray-200 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center gap-5"
            >
              <div className="flex-1 space-y-3">
                <p className="text-sm font-medium text-black">
                  {completedStages.length === 0
                    ? "Configura tu empresa para activar el consejo"
                    : `Configuración en progreso — ${completedStages.length} de 8 etapas`}
                </p>
                <div className="flex gap-1">
                  {ETAPAS.map(e => (
                    <div
                      key={e.n}
                      title={e.label}
                      className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                        completedStages.includes(e.n) ? "bg-[var(--gob-navy)]" : "bg-gray-100"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-gray-400">
                  {completedStages.length === 0
                    ? "Toma unos minutos. Se hace una vez y puedes editarla después."
                    : nextEtapa && `Siguiente: Etapa ${nextEtapa.n} — ${nextEtapa.label}`}
                </p>
              </div>
              <Link
                href={nextEtapa ? `/onboarding/etapa-${nextEtapa.n}` : "/onboarding/etapa-1"}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors whitespace-nowrap"
              >
                {completedStages.length === 0 ? "Empezar configuración" : "Continuar"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>
          )}

          {/* ── Score + checklist ────────────────────────── */}
          {onboardingComplete && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
              className="grid grid-cols-1 sm:grid-cols-3 gap-5"
            >
              {/* Score */}
              <div className="border border-gray-100 hover:border-gray-300 rounded-2xl p-7 space-y-3 transition-colors">
                <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">
                  Governance Score
                </p>
                {governanceScore !== null ? (
                  <p className="text-6xl font-bold text-black tracking-tight leading-none">
                    {governanceScore}
                  </p>
                ) : (
                  <p className="text-5xl font-bold text-gray-200 tracking-tight leading-none">—</p>
                )}
                <p className="text-xs text-gray-400">sobre 100 puntos</p>
              </div>

              {/* Etapas checklist */}
              <div className="sm:col-span-2 border border-gray-100 rounded-2xl p-7">
                <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-5">
                  Onboarding completado
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-3 gap-x-4">
                  {ETAPAS.map(e => (
                    <div key={e.n} className="flex items-center gap-2">
                      {completedStages.includes(e.n)
                        ? <CheckCircle2 className="h-3.5 w-3.5 text-black flex-shrink-0" />
                        : <Circle className="h-3.5 w-3.5 text-gray-200 flex-shrink-0" />
                      }
                      <span className="text-xs text-gray-600">{e.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* ── Diagnostic area completion ───────────────── */}
          {completedStages.includes(4) && summary?.diagnostic_area_completion && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: EASE, delay: 0.15 }}
              className="space-y-4"
            >
              <div>
                <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">Etapa 4</p>
                <h2 className="text-2xl font-bold text-black tracking-tight">Diagnóstico por área</h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {Object.entries(summary.diagnostic_area_completion).map(([key, area]) => {
                  const isExpanded = expandedArea === key
                  const RESPONSE_LABELS: Record<string, string> = {
                    yes: "Sí", partial: "Parcialmente", no: "No",
                    unknown: "No lo sé", skipped: "Omitida",
                  }
                  return (
                    <div key={key} className="border border-gray-100 rounded-2xl overflow-hidden">
                      <button
                        onClick={() => setExpandedArea(isExpanded ? null : key)}
                        className="w-full flex items-center gap-4 p-4 hover:bg-gray-50 transition-colors text-left"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-black truncate">{area.label}</span>
                            <span className="text-xs font-bold text-gray-500 ml-2 flex-shrink-0">{area.pct}%</span>
                          </div>
                          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: `${area.pct}%`,
                                backgroundColor: area.pct >= 80 ? "#16a34a" : area.pct >= 50 ? "#ca8a04" : "#dc2626",
                              }}
                            />
                          </div>
                          <p className="text-xs text-gray-400 mt-1.5">
                            {area.answered} respondidas · {area.skipped} omitidas
                          </p>
                        </div>
                        <ChevronDown
                          className={`h-4 w-4 text-gray-300 flex-shrink-0 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                        />
                      </button>

                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                            className="overflow-hidden"
                          >
                            <div className="px-4 pb-4 space-y-2 border-t border-gray-100 pt-3">
                              {area.questions.map(q => (
                                <div key={q.question_id} className="flex items-start gap-2.5">
                                  <span className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                    q.response === "yes"     ? "bg-green-500" :
                                    q.response === "partial" ? "bg-yellow-500" :
                                    q.response === "no"      ? "bg-red-500" :
                                    q.response === "unknown" ? "bg-blue-400" :
                                                               "bg-gray-300"
                                  }`} />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-xs text-gray-700 leading-snug">{q.text}</p>
                                    <p className="text-[11px] text-gray-400 mt-0.5">
                                      {RESPONSE_LABELS[q.response] ?? q.response}
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* ── Agents ───────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.2 }}
            className="space-y-6"
          >
            <div>
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">Tu consejo</p>
              <h2 className="text-2xl font-bold text-black tracking-tight">Cinco consejeros con IA</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {AGENTS.map((a, i) => (
                <motion.div
                  key={a.name}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: EASE, delay: 0.28 + i * 0.07 }}
                  className="group border border-gray-100 hover:border-gray-300 rounded-2xl p-6 space-y-4 transition-all duration-300 hover:shadow-sm flex flex-col"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs text-gray-400">{a.tag}</p>
                      <p className="text-base font-bold text-black mt-0.5">{a.name}</p>
                    </div>
                    <ArrowUpRight className={`h-4 w-4 mt-0.5 transition-colors ${
                      onboardingComplete
                        ? "text-gray-200 group-hover:text-gray-400"
                        : "text-gray-100"
                    }`} />
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed flex-1">{a.desc}</p>
                  <button
                    onClick={tryCreateSession}
                    className="w-full flex items-center justify-between text-xs font-medium py-2.5 px-3 rounded-xl border border-gray-200 text-gray-700 hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-all duration-150"
                  >
                    Iniciar sesión
                    <Play className="h-3 w-3" />
                  </button>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* ── Plan estratégico ─────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.3 }}
            className="space-y-6"
          >
            <div>
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">Estrategia</p>
              <h2 className="text-2xl font-bold text-black tracking-tight">Plan anual</h2>
            </div>

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
          </motion.div>

          {/* ── Board sessions ───────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.35 }}
            className="space-y-6"
          >
            <div className="flex items-end justify-between">
              <div>
                <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">Historial</p>
                <h2 className="text-2xl font-bold text-black tracking-tight">Sesiones de consejo</h2>
              </div>
              <button
                onClick={tryCreateSession}
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
              >
                Nueva sesión <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Sessions list or empty state */}
            {sessLoading ? (
              <div className="border border-gray-100 rounded-2xl p-12 flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
              </div>
            ) : sessions.length > 0 ? (
              <div className="space-y-3">
                {sessions.map((s, i) => (
                  <motion.div
                    key={s.board_session_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: EASE, delay: i * 0.05 }}
                  >
                    <Link
                      href={`/dashboard/sesion/${s.board_session_id}`}
                      className="group flex items-center justify-between px-6 py-4 border border-gray-100 hover:border-gray-300 rounded-2xl transition-all duration-200 hover:shadow-sm"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl border-2 border-gray-100 flex items-center justify-center group-hover:border-gray-300 transition-colors">
                          <span className="text-xs font-bold text-gray-400">
                            {MONTH_NAMES[s.period_month]?.slice(0, 3)}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-black">{s.period_label}</p>
                          <p className="text-xs text-gray-400 mt-0.5">
                            {statusLabel(s.status)}
                            {s.message_count > 0 && ` · ${s.message_count} mensajes`}
                            {s.governance_score_snapshot !== null && ` · Score ${s.governance_score_snapshot}`}
                          </p>
                        </div>
                      </div>
                      <ArrowUpRight className="h-4 w-4 text-gray-300 group-hover:text-gray-500 transition-colors" />
                    </Link>
                  </motion.div>
                ))}
              </div>
            ) : (
              /* Empty state */
              <div className="border border-gray-100 rounded-2xl p-14 flex flex-col items-center justify-center text-center space-y-4">
                <div className="w-12 h-12 rounded-full border-2 border-gray-100 flex items-center justify-center">
                  <Play className="h-5 w-5 text-gray-200" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-black">
                    {onboardingComplete ? "Aún no hay sesiones" : "Completa el onboarding primero"}
                  </p>
                  <p className="text-xs text-gray-400 max-w-xs leading-relaxed">
                    {onboardingComplete
                      ? "Inicia tu primera sesión de consejo para generar el diagnóstico completo de tu empresa."
                      : "Una vez que configures tu empresa, tus consejeros con IA generarán el primer análisis de gobierno."}
                  </p>
                </div>
                {onboardingComplete && (
                  <button
                    onClick={openModal}
                    className="inline-flex items-center gap-2 border border-gray-200 text-xs font-medium text-gray-700 px-4 py-2.5 rounded-xl hover:border-gray-400 hover:text-[var(--gob-navy)] transition-all duration-150 mt-1"
                  >
                    Iniciar primera sesión <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </motion.div>

        </div>
      </main>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-6 px-6 mt-4">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-[var(--gob-navy)] flex items-center justify-center">
              <span className="text-[var(--gob-bone)] text-[8px] font-black">G</span>
            </div>
            <span>Gobernia © {new Date().getFullYear()}</span>
          </div>
          <span>Tu información está cifrada y protegida.</span>
        </div>
      </footer>

    </div>
  )
}
