"use client"

import { useState, useEffect, type ReactNode, type ComponentType } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowLeft, Loader2, Building2, BarChart3, ClipboardList,
  Compass, Target, Eye, ShieldCheck, Palette,
} from "lucide-react"
import api from "@/lib/api"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import LogoUpload from "@/components/company/LogoUpload"
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

/** Tarjeta del tablero. `span` la ensancha cuando su contenido lo pide (bandas de ancho completo). */
function Section({ icon: Icon, title, span = "", children }: {
  icon: ComponentType<{ className?: string }>; title: string; span?: string; children: ReactNode
}) {
  return (
    <section className={`border border-gray-100 rounded-2xl p-6 space-y-4 ${span}`}>
      <div className="flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-lg bg-[var(--gob-navy)]/[0.06] text-[var(--gob-navy)] flex items-center justify-center shrink-0">
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
  const listo = !loading && !error && !!buffer

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      <PageHeader
        eyebrow="Configuración"
        title="Mis datos"
        actions={
          <>
            <Link href="/dashboard"
              className="inline-flex items-center gap-2 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              <ArrowLeft className="h-4 w-4" /> <span className="hidden sm:inline">Volver al dashboard</span>
            </Link>
            <Link href="/onboarding/todd"
              className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              Actualizar con Todd
            </Link>
          </>
        }
      />

      <main>
        <PageShell className="py-8 space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: EASE }}>
            <Prose>
              <p className="text-sm text-gray-500 leading-relaxed">
                Todo lo que Todd capturó de tu empresa — lo que usan tus consejeros con IA. ¿Cambió algo?
                Actualízalo platicando de nuevo con Todd.
              </p>
            </Prose>
          </motion.div>

          {loading && (
            <div className="flex items-center justify-center py-20"><Loader2 className="h-6 w-6 text-gray-300 animate-spin" /></div>
          )}

          {!loading && error && (
            <div className="border border-gray-200 rounded-2xl p-8 text-center space-y-3">
              <p className="text-sm text-gray-500">{error}</p>
              <Link href="/onboarding/todd"
                className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-5 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                Empezar con Todd
              </Link>
            </div>
          )}

          {/* Tablero: rejilla de tarjetas. Las bandas anchas van al final para no dejar huecos. */}
          <div className="grid gap-4 items-start lg:grid-cols-2 xl:grid-cols-3">

            {/* Tu marca — el logo del cliente (siempre disponible) */}
            <Section icon={Palette} title="Tu marca">
              <p className="text-sm text-gray-500 leading-relaxed">
                Sube el logo de tu empresa: aparecerá en tus reportes en PDF y dentro de la plataforma.
              </p>
              <LogoUpload companyName={c.name ?? null} />
            </Section>

            {listo && (
              <>
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

                {/* Metas priorizadas */}
                {metas.length > 0 && (
                  <Section icon={Target} title="Metas priorizadas">
                    <ol className="space-y-2.5">
                      {metas.map((m, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                          <span className="text-sm text-gray-700 leading-snug">{m}</span>
                        </li>
                      ))}
                    </ol>
                  </Section>
                )}

                {/* Gobierno */}
                {buffer.governance?.score != null && (
                  <Section icon={ShieldCheck} title="Gobierno corporativo">
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-bold tracking-tight text-[var(--gob-navy)]">{buffer.governance.score}</span>
                      <span className="text-sm text-gray-400">/ 100</span>
                    </div>
                    {buffer.governance.level && (
                      <p className="text-xs font-medium uppercase tracking-[0.14em] text-gray-400">{buffer.governance.level}</p>
                    )}
                  </Section>
                )}

                {/* Fortalezas y debilidades — banda ancha: una columna por área */}
                {hallazgosAreas.length > 0 && (
                  <Section icon={ClipboardList} title="Fortalezas y debilidades"
                    span="lg:col-span-2 xl:col-span-3">
                    <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
                      {hallazgosAreas.map(([area, items]) => (
                        <div key={area}>
                          <p className="text-xs font-medium tracking-wide text-gray-400 uppercase mb-2">{AREA_LABEL[area] ?? area}</p>
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

                {/* Factores externos — banda ancha: oportunidades vs amenazas */}
                {(oportunidades.length > 0 || amenazas.length > 0) && (
                  <Section icon={Compass} title="Factores externos (entorno)"
                    span="lg:col-span-2 xl:col-span-3">
                    <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
                      <div>
                        <p className="text-xs font-medium tracking-wide text-green-700 uppercase mb-2">Oportunidades</p>
                        <ul className="space-y-1.5">
                          {oportunidades.map((t, i) => <li key={i} className="text-sm text-gray-700 leading-snug flex gap-2"><span className="text-green-500 shrink-0">+</span>{t}</li>)}
                          {oportunidades.length === 0 && <li className="text-sm text-gray-300 italic">—</li>}
                        </ul>
                      </div>
                      <div>
                        <p className="text-xs font-medium tracking-wide text-red-600 uppercase mb-2">Amenazas</p>
                        <ul className="space-y-1.5">
                          {amenazas.map((t, i) => <li key={i} className="text-sm text-gray-700 leading-snug flex gap-2"><span className="text-red-500 shrink-0">−</span>{t}</li>)}
                          {amenazas.length === 0 && <li className="text-sm text-gray-300 italic">—</li>}
                        </ul>
                      </div>
                    </div>
                  </Section>
                )}
              </>
            )}
          </div>
        </PageShell>
      </main>
    </div>
  )
}
