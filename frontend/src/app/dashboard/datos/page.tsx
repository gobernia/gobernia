"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowLeft, Pencil, Building2, Users, Target,
  ClipboardList, BarChart3, ShieldCheck, FileText, Compass, Loader2,
} from "lucide-react"
import { useOnboardingStore } from "@/lib/store"
import api from "@/lib/api"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

interface MemoryBuffer {
  company?: {
    name?: string
    industry?: string
    location_city?: string
    location_state?: string
    location_country?: string
    employees?: string
    years_operating?: string
    annual_revenue?: string
    branches?: string
    has_board?: string
    is_family_business?: boolean
    family_generation?: string
  }
  team?: Array<{ name?: string; role?: string; is_decision_maker?: boolean }>
  priorities?: Array<{ challenge?: string; rank?: number; description?: string }>
  diagnostic_responses?: Array<{ question_id: string; response: string; area: string }>
  kpis?: Record<string, Array<{ label: string; current_value: number | null; unit?: string }>>
  governance?: { score?: number; level?: string }
  documents?: Array<{ filename: string; document_type: string; status: string }>
  vision?: { statement?: string; main_goals?: string[] }
  agent_configs?: Record<string, { tone?: string; alert_sensitivity?: string }>
}

const SECTIONS = [
  { etapa: 1, icon: Building2,    title: "Empresa",     desc: "Datos básicos, industria, tamaño" },
  { etapa: 2, icon: Users,        title: "Equipo",      desc: "Miembros directivos y roles" },
  { etapa: 3, icon: Target,       title: "Prioridades", desc: "Los 3-5 retos principales" },
  { etapa: 4, icon: ClipboardList,title: "Diagnóstico", desc: "Respuestas del diagnóstico interno" },
  { etapa: 5, icon: BarChart3,    title: "KPIs",        desc: "Indicadores clave y benchmarks" },
  { etapa: 6, icon: ShieldCheck,  title: "Gobierno",    desc: "Checklist de gobierno corporativo" },
  { etapa: 7, icon: FileText,     title: "Documentos",  desc: "Archivos cargados" },
  { etapa: 8, icon: Compass,      title: "Visión",      desc: "Visión, metas y configuración de consejeros" },
]

export default function DatosPage() {
  const { sessionId, completedStages } = useOnboardingStore()
  const [buffer, setBuffer] = useState<MemoryBuffer | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) {
      setLoading(false)
      setError("Aún no has empezado la configuración.")
      return
    }
    api.get(`/onboarding/session/${sessionId}`)
      .then(r => setBuffer(r.data.memory_buffer || {}))
      .catch(() => setError("No se pudieron cargar tus datos."))
      .finally(() => setLoading(false))
  }, [sessionId])

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      <header className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-[1200px] mx-auto px-[var(--px-fluid)] h-14 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
            <ArrowLeft className="h-4 w-4" />
            Volver al dashboard
          </Link>
          <GoberniaLogo size={16} />
        </div>
      </header>

      <main className="pt-14">
        <div className="w-full max-w-[1200px] mx-auto px-[var(--px-fluid)] py-12 space-y-10">

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="space-y-2"
          >
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Configuración</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">Mis datos</h1>
            <p className="text-sm text-gray-500 max-w-xl">
              Información que usan tus consejeros con IA para sus análisis. Edita cualquier sección
              cuando tu empresa cambie — los nuevos datos se aplicarán a las próximas sesiones.
            </p>
          </motion.div>

          {loading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 text-gray-300 animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="border border-gray-200 rounded-2xl p-8 text-center space-y-3">
              <p className="text-sm text-gray-500">{error}</p>
              <Link
                href="/onboarding/etapa-1"
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
              >
                Empezar configuración
              </Link>
            </div>
          )}

          {!loading && !error && buffer && (
            <div className="grid grid-cols-1 gap-3">
              {SECTIONS.map((s, i) => {
                const Icon = s.icon
                const isCompleted = completedStages.includes(s.etapa)
                const preview = buildPreview(s.etapa, buffer)
                return (
                  <motion.div
                    key={s.etapa}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE, delay: i * 0.04 }}
                    className="border border-gray-100 hover:border-gray-300 rounded-2xl p-5 flex items-start gap-4 transition-colors"
                  >
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      isCompleted ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]" : "bg-gray-50 text-gray-300"
                    }`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-gray-400">Etapa {s.etapa}</span>
                        <span className="text-xs text-gray-300">·</span>
                        <span className="text-xs text-gray-400">{s.desc}</span>
                      </div>
                      <p className="text-sm font-medium text-black">{s.title}</p>
                      {isCompleted && preview && (
                        <p className="text-xs text-gray-500 leading-relaxed pt-1">{preview}</p>
                      )}
                      {!isCompleted && (
                        <p className="text-xs text-gray-400 italic pt-1">Sin completar</p>
                      )}
                    </div>
                    <Link
                      href={`/onboarding/etapa-${s.etapa}?from=datos`}
                      className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-[var(--gob-navy)] border border-gray-200 hover:border-[var(--gob-navy)] rounded-lg px-3 py-2 transition-colors flex-shrink-0"
                    >
                      <Pencil className="h-3 w-3" />
                      {isCompleted ? "Editar" : "Completar"}
                    </Link>
                  </motion.div>
                )
              })}
            </div>
          )}

        </div>
      </main>
    </div>
  )
}

function buildPreview(etapa: number, buf: MemoryBuffer): string | null {
  switch (etapa) {
    case 1: {
      const c = buf.company
      if (!c?.name) return null
      const parts: string[] = [c.name]
      if (c.industry) parts.push(c.industry)
      if (c.employees) parts.push(`${c.employees} empleados`)
      if (c.is_family_business) parts.push("empresa familiar")
      return parts.join(" · ")
    }
    case 2: {
      const t = buf.team || []
      if (t.length === 0) return null
      const decisionMakers = t.filter(m => m.is_decision_maker).length
      return `${t.length} miembro${t.length !== 1 ? "s" : ""} · ${decisionMakers} con poder de decisión`
    }
    case 3: {
      const p = buf.priorities || []
      if (p.length === 0) return null
      return p
        .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
        .slice(0, 3)
        .map((x, i) => `${i + 1}. ${x.challenge ?? "—"}`)
        .join(" · ")
    }
    case 4: {
      const d = buf.diagnostic_responses || []
      if (d.length === 0) return null
      const skipped = d.filter(r => r.response === "skipped").length
      return `${d.length} preguntas respondidas${skipped > 0 ? ` · ${skipped} omitidas` : ""}`
    }
    case 5: {
      const k = buf.kpis
      if (!k) return null
      const total = Object.values(k).reduce((acc, arr) => acc + arr.length, 0)
      const reported = Object.values(k).reduce(
        (acc, arr) => acc + arr.filter(x => x.current_value !== null).length, 0,
      )
      return `${reported} de ${total} KPIs reportados`
    }
    case 6: {
      const g = buf.governance
      if (!g?.score) return null
      return `Governance Score: ${g.score}/100${g.level ? ` (${g.level})` : ""}`
    }
    case 7: {
      const docs = buf.documents || []
      if (docs.length === 0) return null
      return `${docs.length} documento${docs.length !== 1 ? "s" : ""} cargado${docs.length !== 1 ? "s" : ""}`
    }
    case 8: {
      const v = buf.vision
      if (!v?.statement) return null
      return v.statement.length > 90 ? v.statement.slice(0, 90) + "…" : v.statement
    }
  }
  return null
}
