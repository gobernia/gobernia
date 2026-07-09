"use client"

import { useState, useEffect, type ReactNode, type ComponentType } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowLeft, Loader2, Building2, BarChart3, ClipboardList,
  Compass, Target, Eye, ShieldCheck,
} from "lucide-react"
import api from "@/lib/api"
import GoberniaLogo from "@/components/ui/GoberniaLogo"
import { getFoda, type FodaOut } from "@/lib/foda"
import { normalizeHallazgos } from "@/lib/diagnostico"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

interface Kpi { label?: string; current_value?: number | null; unit?: string; benchmark?: number | null }
interface MemoryBuffer {
  company?: {
    name?: string; industry?: string; employees?: string | number; annual_revenue?: string | number
    years_operating?: string | number; is_family_business?: boolean; website?: string
    has_board?: boolean | string; competitors?: string | string[]
  }
  kpis?: Record<string, Kpi[]>
  vision?: { statement?: string; main_goals?: string[]; exito_consejo?: string }
  governance?: { score?: number; level?: string }
  hallazgos?: Record<string, unknown>
}

const TIPO_DOT: Record<string, string> = {
  fortaleza: "bg-green-500", debilidad: "bg-red-500", parcial: "bg-amber-500",
}
const AREA_LABEL: Record<string, string> = {
  estrategia: "Estrategia", comercial: "Comercial", operativo: "Operativo",
  rh: "RH", financiero: "Financiero", legal: "Legal", familiar: "Familiar",
}

function splitFactores(fx: Record<string, unknown> | undefined) {
  const oportunidades: string[] = [], amenazas: string[] = []
  for (const items of Object.values(fx ?? {})) {
    const list = Array.isArray(items) ? items : [items]
    for (const it of list) {
      if (it && typeof it === "object") {
        const o = it as Record<string, unknown>
        const tipo = String(o.tipo ?? "").toLowerCase()
        const texto = String(o.texto ?? o.nota ?? "").trim()
        if (!texto) continue
        if (tipo.includes("amenaz")) amenazas.push(texto)
        else oportunidades.push(texto)
      } else if (it) { oportunidades.push(String(it)) }
    }
  }
  return { oportunidades, amenazas }
}

function Section({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode }) {
  return (
    <section className="border border-gray-100 rounded-2xl p-6 space-y-4">
      <div className="flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-lg bg-[var(--gob-navy)]/[0.06] text-[var(--gob-navy)] flex items-center justify-center">
          <Icon className="h-4 w-4" />
        </span>
        <h2 className="text-base font-bold text-black tracking-tight">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="text-xs text-gray-400 shrink-0">{label}</span>
      <span className="text-sm text-black text-right">{value}</span>
    </div>
  )
}

const empty = <span className="text-gray-300 italic">Sin registrar</span>

export default function DatosPage() {
  const [buffer, setBuffer] = useState<MemoryBuffer | null>(null)
  const [foda, setFoda] = useState<FodaOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const ms = await api.get("/onboarding/my-session", { validateStatus: s => s === 200 || s === 204 })
        const sid = ms.status === 200 ? ms.data?.session_id : null
        if (!sid) { if (alive) { setError("Aún no has hecho tu onboarding con Todd."); setLoading(false) } return }
        const r = await api.get(`/onboarding/session/${sid}`)
        if (alive) setBuffer(r.data.memory_buffer || {})
        try { const f = await getFoda(); if (alive) setFoda(f) } catch { /* opcional */ }
      } catch { if (alive) setError("No se pudieron cargar tus datos.") }
      finally { if (alive) setLoading(false) }
    })()
    return () => { alive = false }
  }, [])

  const c = buffer?.company ?? {}
  const competitors = Array.isArray(c.competitors) ? c.competitors.join(", ") : (c.competitors || "")
  const kpiRows: { label: string; value: string }[] = []
  for (const [cat, arr] of Object.entries(buffer?.kpis ?? {})) {
    for (const k of (arr || [])) {
      const val = k.current_value != null ? `${k.current_value}${k.unit ?? ""}` : "—"
      kpiRows.push({ label: k.label || cat, value: val })
    }
  }
  const hallazgos = normalizeHallazgos(buffer?.hallazgos)
  const hallazgosAreas = Object.entries(hallazgos)
  const { oportunidades, amenazas } = splitFactores(foda?.factores_externos)
  const metas = foda?.metas ?? []

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      <header className="fixed top-0 inset-x-0 md:left-60 z-30 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-[1200px] mx-auto px-[var(--px-fluid)] h-14 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors">
            <ArrowLeft className="h-4 w-4" /> Volver al dashboard
          </Link>
          <GoberniaLogo size={16} />
        </div>
      </header>

      <main className="pt-14">
        <div className="w-full max-w-3xl mx-auto px-[var(--px-fluid)] py-12 space-y-8">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }} className="space-y-2">
            <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Configuración</p>
            <h1 className="text-3xl font-bold text-black tracking-tight">Mis datos</h1>
            <p className="text-sm text-gray-500 max-w-xl">
              Todo lo que Todd capturó de tu empresa — lo que usan tus consejeros con IA. ¿Cambió algo?
              Actualízalo platicando de nuevo con Todd.
            </p>
            <div className="pt-2">
              <Link href="/onboarding/todd"
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
                Actualizar con Todd
              </Link>
            </div>
          </motion.div>

          {loading && (
            <div className="flex items-center justify-center py-20"><Loader2 className="h-6 w-6 text-gray-300 animate-spin" /></div>
          )}

          {!loading && error && (
            <div className="border border-gray-200 rounded-2xl p-8 text-center space-y-3">
              <p className="text-sm text-gray-500">{error}</p>
              <Link href="/onboarding/todd"
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors">
                Empezar con Todd
              </Link>
            </div>
          )}

          {!loading && !error && buffer && (
            <div className="space-y-4">
              {/* Empresa */}
              <Section icon={Building2} title="Empresa">
                <div className="divide-y divide-gray-50">
                  <Field label="Nombre" value={c.name || empty} />
                  <Field label="Industria / sector" value={c.industry || empty} />
                  <Field label="Tamaño del equipo" value={c.employees != null && c.employees !== "" ? `${c.employees}` : empty} />
                  <Field label="Facturación anual" value={c.annual_revenue != null && c.annual_revenue !== "" ? `${c.annual_revenue}` : empty} />
                  <Field label="Años operando" value={c.years_operating != null && c.years_operating !== "" ? `${c.years_operating}` : empty} />
                  <Field label="Empresa familiar" value={c.is_family_business === true ? "Sí" : c.is_family_business === false ? "No" : empty} />
                  <Field label="Sitio web" value={c.website || empty} />
                  <Field label="Competidores" value={competitors || empty} />
                </div>
              </Section>

              {/* KPIs */}
              <Section icon={BarChart3} title="KPIs reportados">
                {kpiRows.length > 0 ? (
                  <div className="divide-y divide-gray-50">
                    {kpiRows.map((k, i) => <Field key={i} label={k.label} value={<span className="font-semibold">{k.value}</span>} />)}
                  </div>
                ) : <p className="text-sm text-gray-400">No registraste indicadores con valor. Puedes agregarlos con Todd.</p>}
              </Section>

              {/* Fortalezas y debilidades */}
              {hallazgosAreas.length > 0 && (
                <Section icon={ClipboardList} title="Fortalezas y debilidades">
                  <div className="space-y-3">
                    {hallazgosAreas.map(([area, items]) => (
                      <div key={area}>
                        <p className="text-xs font-medium tracking-wide text-gray-400 uppercase mb-1.5">{AREA_LABEL[area] ?? area}</p>
                        <ul className="space-y-1.5">
                          {items.map((h, j) => (
                            <li key={j} className="flex items-start gap-2 text-sm">
                              <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${TIPO_DOT[h.tipo] ?? "bg-gray-300"}`} />
                              <span className="text-gray-700 leading-snug">{h.texto}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {/* Factores externos */}
              {(oportunidades.length > 0 || amenazas.length > 0) && (
                <Section icon={Compass} title="Factores externos (entorno)">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs font-medium tracking-wide text-green-700 uppercase mb-1.5">Oportunidades</p>
                      <ul className="space-y-1.5">
                        {oportunidades.map((t, i) => <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-green-500">+</span>{t}</li>)}
                        {oportunidades.length === 0 && <li className="text-sm text-gray-300 italic">—</li>}
                      </ul>
                    </div>
                    <div>
                      <p className="text-xs font-medium tracking-wide text-red-600 uppercase mb-1.5">Amenazas</p>
                      <ul className="space-y-1.5">
                        {amenazas.map((t, i) => <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-red-500">−</span>{t}</li>)}
                        {amenazas.length === 0 && <li className="text-sm text-gray-300 italic">—</li>}
                      </ul>
                    </div>
                  </div>
                </Section>
              )}

              {/* Metas priorizadas */}
              {metas.length > 0 && (
                <Section icon={Target} title="Metas priorizadas">
                  <ol className="space-y-2">
                    {metas.map((m, i) => (
                      <li key={i} className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                        <span className="text-sm text-gray-700">{m}</span>
                      </li>
                    ))}
                  </ol>
                </Section>
              )}

              {/* Visión */}
              <Section icon={Eye} title="Visión a 3 años">
                <div className="space-y-4">
                  {buffer.vision?.exito_consejo && (
                    <div className="rounded-xl bg-[var(--gob-navy)]/[0.04] border border-[var(--gob-navy)]/15 p-4">
                      <p className="text-[10px] font-bold tracking-widest uppercase text-[var(--gob-navy)] mb-1">Qué haría que valga la pena</p>
                      <p className="text-sm text-gray-700 leading-relaxed">{buffer.vision.exito_consejo}</p>
                    </div>
                  )}
                  {buffer.vision?.statement
                    ? <p className="text-sm text-gray-700 leading-relaxed">{buffer.vision.statement}</p>
                    : !buffer.vision?.exito_consejo && <p className="text-sm text-gray-400">Sin registrar.</p>}
                </div>
              </Section>

              {/* Gobierno */}
              {buffer.governance?.score != null && (
                <Section icon={ShieldCheck} title="Gobierno corporativo">
                  <Field label="Governance Score" value={<span className="font-semibold">{buffer.governance.score}/100{buffer.governance.level ? ` · ${buffer.governance.level}` : ""}</span>} />
                </Section>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
