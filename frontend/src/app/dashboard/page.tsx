"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, Play, ChevronRight,
  CheckCircle2, Circle, ArrowUpRight, X, Loader2,
  Sparkles, FileSearch, LayoutGrid, MessagesSquare, ClipboardList, Library, Users,
} from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"
import SecretarioWelcome from "@/components/dashboard/SecretarioWelcome"
import { PageShell } from "@/components/ui/PageShell"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"
import { getLogo } from "@/lib/logo"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Data ──────────────────────────────────────────────────
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

// El flujo del producto, en el mismo orden que la barra lateral.
// Es el acceso principal desde Inicio: una rejilla, no una lista suelta.
const FLUJO = [
  {
    href: "/dashboard/diagnostico", icon: FileSearch, step: "01", label: "Diagnóstico",
    desc: "El estado real de tu gobierno corporativo, con evidencia.",
  },
  {
    href: "/dashboard/foda", icon: LayoutGrid, step: "02", label: "FODA",
    desc: "Fortalezas, oportunidades, debilidades y amenazas del negocio.",
  },
  {
    href: "/dashboard/perspectivas", icon: MessagesSquare, step: "03", label: "Perspectivas",
    desc: "Lo que ven tu equipo, tus socios y tus clientes desde fuera.",
  },
  {
    href: "/dashboard/plan", icon: ClipboardList, step: "04", label: "Plan anual",
    desc: "Objetivos, tareas y KPIs mes a mes, generados por tu consejo.",
  },
  {
    href: "/dashboard/biblioteca", icon: Library, step: "05", label: "Biblioteca",
    desc: "Los documentos que sostienen cada decisión del consejo.",
  },
  {
    href: "/dashboard/consejo", icon: Users, step: "06", label: "Tu consejo",
    desc: "Cinco consejeros con IA: finanzas, estrategia, riesgos, auditoría y el Retador.",
  },
]

// Sesiones de consejo ocultas por ahora (no se borra el código). Cambiar a true para reactivar.
const SHOW_SESSIONS = false

// ── Types ─────────────────────────────────────────────────
interface CompanySummary {
  company_name: string
  industry: string
  governance_score?: number
  activated_modules: string[]
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
  const { completedStages, hydrate, reset } = useOnboardingStore()

  const [userEmail,   setUserEmail]   = useState<string | null>(null)
  const [userName,    setUserName]    = useState<string>("")
  const [summary,     setSummary]     = useState<CompanySummary | null>(null)
  const [sessions,    setSessions]    = useState<BoardSession[]>([])
  const [sessLoading, setSessLoading] = useState(true)

  const [showSetupModal, setShowSetupModal] = useState(false)

  // Nova sesión modal state
  const [showModal,    setShowModal]   = useState(false)
  const [modalYear,    setModalYear]   = useState(new Date().getFullYear())
  const [modalMonth,   setModalMonth]  = useState(new Date().getMonth() + 1)
  const [creating,     setCreating]    = useState(false)
  const [createError,  setCreateError] = useState<string | null>(null)
  const [companyLogo,  setCompanyLogo] = useState<string | null>(null)

  useEffect(() => {
    getLogo()
      .then(r => setCompanyLogo(r.logo))
      .catch(() => {})

    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null)
      const meta = data.user?.user_metadata ?? {}
      const name = (meta.full_name ?? meta.name ?? "") as string
      // solo el primer nombre, para un saludo más cálido
      setUserName(name.trim().split(/\s+/)[0] ?? "")
    })

    // Siempre resolvemos la sesión del usuario ACTUAL vía /my-session (va con su token).
    // Si el backend no tiene sesión (usuario nuevo → 204), reseteamos el store para no
    // arrastrar el onboarding de un usuario anterior guardado en localStorage.
    api.get("/onboarding/my-session")
      .then(r => {
        const sid = r.data?.session_id
        if (sid) {
          hydrate(sid, r.data.completed_stages ?? [])
          api.get(`/onboarding/${sid}/summary`)
            .then(rr => setSummary(rr.data))
            .catch(() => {})
        } else {
          reset()
        }
      })
      .catch(() => {})

    api.get("/board-sessions")
      .then(r => setSessions(r.data))
      .catch(() => {})
      .finally(() => setSessLoading(false))
  }, [hydrate, reset])

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

      <SecretarioWelcome
        onboardingComplete={onboardingComplete}
        nextStageHref={"/onboarding/todd"}
        userKey={userEmail ?? ""}
        userName={userName}
      />

      {/* ── Navbar ───────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 md:left-60 z-30 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <PageShell className="h-14 flex items-center justify-between">
          <GoberniaLogo size={16} />

          <div className="flex items-center gap-5">
            {userEmail && (
              <span className="text-xs text-gray-400 hidden sm:block">{userEmail}</span>
            )}
          </div>
        </PageShell>
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
                  href={"/onboarding/todd"}
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
        <PageShell className="py-12 space-y-14">

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
            <div className="flex items-center gap-3">
              {companyLogo && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={companyLogo}
                  alt={companyName ?? "Logo de tu empresa"}
                  className="h-9 w-9 rounded-lg object-contain bg-white border border-gray-100 shrink-0"
                />
              )}
              <h1 className="text-3xl font-bold text-black tracking-tight">
                {greeting()}{companyName ? `, ${companyName}` : ""}.
              </h1>
            </div>
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
                href={"/onboarding/todd"}
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

          {/* ── El flujo ─────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.3 }}
            className="space-y-6"
          >
            <div>
              <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">
                Tu flujo
              </p>
              <h2 className="text-2xl font-bold text-black tracking-tight">
                Del diagnóstico al plan
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {FLUJO.map((f, i) => {
                const Icon = f.icon
                return (
                  <motion.div
                    key={f.href}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE, delay: 0.35 + i * 0.05 }}
                  >
                    <Link
                      href={f.href}
                      className="group h-full flex flex-col border border-gray-100 rounded-2xl p-6 hover:border-gray-300 hover:shadow-sm transition-all duration-200"
                    >
                      <div className="flex items-start justify-between">
                        <span className="h-9 w-9 rounded-xl border border-gray-100 flex items-center justify-center text-[var(--gob-navy)] group-hover:border-gray-300 transition-colors">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="text-[10px] font-medium tracking-widest text-gray-300 tabular-nums">
                          {f.step}
                        </span>
                      </div>
                      <p className="text-sm font-bold text-black mt-4">{f.label}</p>
                      <p className="text-xs text-gray-500 leading-relaxed mt-1.5 flex-1">
                        {f.desc}
                      </p>
                      <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 group-hover:text-[var(--gob-navy)] transition-colors">
                        Abrir
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </span>
                    </Link>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>

          {/* ── Board sessions ── OCULTO por ahora (no se borra; las "Sesiones de consejo" se deshabilitan temporalmente). El modal "Nueva sesión" queda en el código pero ya no es alcanzable. ── */}
          {SHOW_SESSIONS && (
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
              <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-3">
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
          )}

        </PageShell>
      </main>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-6 mt-4">
        <PageShell className="flex items-center justify-between gap-4 flex-wrap text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-[var(--gob-navy)] flex items-center justify-center">
              <span className="text-[var(--gob-bone)] text-[8px] font-black">G</span>
            </div>
            <span>Gobernia © {new Date().getFullYear()}</span>
          </div>
          <span>Tu información está cifrada y protegida.</span>
        </PageShell>
      </footer>

    </div>
  )
}
