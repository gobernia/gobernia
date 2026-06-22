"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import {
  ArrowRight, ArrowUpRight, Play, X, Loader2, Sparkles,
} from "lucide-react"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

const AGENTS = [
  { tag: "Consejero en", name: "Finanzas",      desc: "Rentabilidad, flujo de caja y estructura de capital." },
  { tag: "Consejero en", name: "Estrategia",    desc: "Posicionamiento, mercado y crecimiento a largo plazo." },
  { tag: "Consejero en", name: "Riesgos",       desc: "Riesgos operativos, legales y planes de mitigación." },
  { tag: "Consejero en", name: "Auditoría",     desc: "Cumplimiento, control interno y Governance Score." },
  { tag: "Consejero",    name: "Independiente", desc: "El Retador: cuestiona cada decisión con un pre-mortem antes de actuar." },
]

const ETAPAS = [
  { n: 1, label: "Empresa" }, { n: 2, label: "Equipo" }, { n: 3, label: "Prioridades" },
  { n: 4, label: "Diagnóstico" }, { n: 5, label: "KPIs" }, { n: 6, label: "Gobierno" },
  { n: 7, label: "Documentos" }, { n: 8, label: "Visión" },
]

const MONTH_NAMES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

interface BoardSession {
  board_session_id: string
  period_year: number
  period_month: number
}

export default function ConsejoPage() {
  const router = useRouter()
  const { completedStages, hydrate, reset } = useOnboardingStore()

  const [sessions, setSessions] = useState<BoardSession[]>([])
  const [showSetupModal, setShowSetupModal] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [modalYear, setModalYear] = useState(new Date().getFullYear())
  const [modalMonth, setModalMonth] = useState(new Date().getMonth() + 1)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    api.get("/onboarding/my-session")
      .then(r => {
        const sid = r.data?.session_id
        if (sid) hydrate(sid, r.data.completed_stages ?? [])
        else reset()
      })
      .catch(() => {})
    api.get("/board-sessions").then(r => setSessions(r.data)).catch(() => {})
  }, [hydrate, reset])

  const onboardingComplete = completedStages.length >= 8
  const nextEtapa = ETAPAS.find(e => !completedStages.includes(e.n))
  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]

  const openModal = () => {
    setModalYear(new Date().getFullYear())
    setModalMonth(new Date().getMonth() + 1)
    setCreateError(null)
    setShowModal(true)
  }

  const tryCreateSession = () => {
    if (onboardingComplete) openModal()
    else setShowSetupModal(true)
  }

  const createSession = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const r = await api.post("/board-sessions", { period_year: modalYear, period_month: modalMonth })
      setShowModal(false)
      router.push(`/dashboard/sesion/${r.data.board_session_id}`)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        const existing = sessions.find(s => s.period_year === modalYear && s.period_month === modalMonth)
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

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      {/* Setup-required modal */}
      <AnimatePresence>
        {showSetupModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowSetupModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-5">
              <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-black" />
              </div>
              <div className="space-y-2">
                <h2 className="text-lg font-bold text-black">Configura tu empresa primero</h2>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Para que el consejo de IA te entregue análisis útiles, necesitamos conocer tu empresa: industria, equipo, prioridades, KPIs y gobierno. Toma unos minutos y solo se hace una vez. Después podrás iniciar sesiones cuando quieras.
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
                <button onClick={() => setShowSetupModal(false)}
                  className="flex-1 text-sm font-medium text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
                  Más tarde
                </button>
                <Link href="/onboarding/todd"
                  className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
                  {completedStages.length > 0 ? "Continuar configuración" : "Empezar"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Nueva sesión modal */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }} className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
              onClick={() => setShowModal(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }} transition={{ duration: 0.25, ease: EASE }}
              className="fixed z-50 inset-x-4 top-1/2 -translate-y-1/2 max-w-sm mx-auto bg-white rounded-2xl shadow-xl p-8 space-y-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-black">Nueva sesión de consejo</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Selecciona el periodo a analizar</p>
                </div>
                <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Mes</p>
                <div className="grid grid-cols-4 gap-1.5">
                  {MONTH_NAMES.slice(1).map((m, i) => (
                    <button key={i + 1} onClick={() => setModalMonth(i + 1)}
                      className={`py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalMonth === i + 1
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                      {m.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium text-gray-600">Año</p>
                <div className="flex gap-2">
                  {years.map(y => (
                    <button key={y} onClick={() => setModalYear(y)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border-2 transition-all duration-100 ${
                        modalYear === y
                          ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                          : "border-gray-100 text-gray-500 hover:border-gray-300"}`}>
                      {y}
                    </button>
                  ))}
                </div>
              </div>
              {createError && <p className="text-xs text-red-500">{createError}</p>}
              <button onClick={createSession} disabled={creating}
                className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50">
                {creating
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Creando…</>
                  : <>Crear sesión de {MONTH_NAMES[modalMonth]} {modalYear} <ArrowRight className="h-4 w-4" /></>}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main>
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] py-12 space-y-8">
          <div className="space-y-1">
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Tu consejo</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">Cinco consejeros con IA</h1>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {AGENTS.map((a, i) => (
              <motion.div key={a.name} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE, delay: 0.05 + i * 0.07 }}
                className="group border border-gray-100 hover:border-gray-300 rounded-2xl p-6 space-y-4 transition-all duration-300 hover:shadow-sm flex flex-col">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-gray-400">{a.tag}</p>
                    <p className="text-base font-bold text-black mt-0.5">{a.name}</p>
                  </div>
                  <ArrowUpRight className={`h-4 w-4 mt-0.5 transition-colors ${
                    onboardingComplete ? "text-gray-200 group-hover:text-gray-400" : "text-gray-100"}`} />
                </div>
                <p className="text-xs text-gray-500 leading-relaxed flex-1">{a.desc}</p>
                <button onClick={tryCreateSession}
                  className="w-full flex items-center justify-between text-xs font-medium py-2.5 px-3 rounded-xl border border-gray-200 text-gray-700 hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-all duration-150">
                  Iniciar sesión
                  <Play className="h-3 w-3" />
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
