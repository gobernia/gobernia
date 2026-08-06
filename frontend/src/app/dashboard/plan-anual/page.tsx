"use client"

import { useEffect, useRef, useState, type CSSProperties } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, Check, ArrowRight, CalendarCheck, BadgeCheck, RotateCcw, AlertTriangle } from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import {
  getPlanAnual, aprobarPlanAnual, reabrirPlanAnual,
  type PlanAnual, type PilarAnual,
} from "@/lib/planAnual"
import { getRoadmap, type Roadmap } from "@/lib/roadmap"
import { aniosDelPlan } from "@/components/roadmap/shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Paleta bento — mismos tokens del Inicio.
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }
const TEAL = "#0f766e"
const AMBER = "#b45309"
const NAVY = BNAVY

const MIN = 3
const MAX = 5

export default function PlanAnualPage() {
  const [plan, setPlan] = useState<PlanAnual | null>(null)
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [loaded, setLoaded] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    Promise.all([getPlanAnual(), getRoadmap()])
      .then(([p, r]) => {
        if (aliveRef.current) {
          setPlan(p)
          setRoadmap(r)
        }
      })
      .catch(() => {
        if (aliveRef.current) {
          setPlan(null)
          setRoadmap(null)
        }
      })
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    return () => { aliveRef.current = false }
  }, [])

  const disponibles = plan?.pilares_disponibles ?? []
  const sinPrioridades = loaded && !!plan && disponibles.length === 0 && !plan.aprobado
  const [anio] = roadmap ? aniosDelPlan(roadmap.anio_objetivo) : [new Date().getFullYear()]

  return (
    <div className="min-h-dvh text-black antialiased">
      <PageHeader eyebrow="El año en curso" title={`Plan anual${plan ? ` · ${anio}` : ""}`} />

      <main>
        <PageShell className="py-10 space-y-8">

          {!loaded && (
            <div className="flex items-center justify-center rounded-[26px] border p-16" style={{ background: CARD, borderColor: LINE }}>
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} />
            </div>
          )}

          {/* Sin roadmap / sin prioridades */}
          {sinPrioridades && (
            <div className="flex flex-col items-center gap-4 rounded-[26px] border p-12 text-center sm:p-16" style={{ background: CARD, borderColor: LINE }}>
              <div className="flex h-14 w-14 items-center justify-center rounded-[26px] border-2" style={{ borderColor: LINE }}>
                <CalendarCheck className="h-5 w-5" style={{ color: MUTED }} />
              </div>
              <div className="max-w-md space-y-1.5">
                <p className="text-base font-medium" style={{ color: INK, ...SANS }}>Aún no hay prioridades para elegir</p>
                <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                  El Plan anual se arma con las prioridades de tu Roadmap. Genera primero tu plan
                  estratégico y aquí podrás elegir las 3 a 5 en las que trabajarás este año.
                </p>
              </div>
              <Link
                href="/dashboard/plan"
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
                style={{ background: ACCENT }}
              >
                Generar mi plan <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}

          {loaded && plan && !sinPrioridades && (
            plan.aprobado
              ? <PlanAprobado plan={plan} onChange={setPlan} aliveRef={aliveRef} />
              : <ModoSeleccion plan={plan} onChange={setPlan} aliveRef={aliveRef} />
          )}

        </PageShell>
      </main>
    </div>
  )
}

// ── Modo selección (plan NO aprobado) ─────────────────────────────
function ModoSeleccion({
  plan, onChange, aliveRef,
}: { plan: PlanAnual; onChange: (p: PlanAnual) => void; aliveRef: React.RefObject<boolean> }) {
  const disponibles = plan.pilares_disponibles
  const [sel, setSel] = useState<Set<number>>(new Set())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggle = (indice: number) => {
    setError(null)
    setSel(prev => {
      const s = new Set(prev)
      if (s.has(indice)) s.delete(indice); else s.add(indice)
      return s
    })
  }

  const count = sel.size
  const tooMany = count > MAX
  const enRango = count >= MIN && count <= MAX

  const aprobar = async () => {
    if (!enRango || saving) return
    setSaving(true)
    setError(null)
    try {
      const indices = Array.from(sel).sort((a, b) => a - b)
      const updated = await aprobarPlanAnual(indices)
      if (aliveRef.current) onChange(updated)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (aliveRef.current) setError(detail ?? "No se pudo aprobar el plan. Intenta de nuevo.")
    } finally {
      if (aliveRef.current) setSaving(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="space-y-6"
    >
      {/* Explicación */}
      <Prose>
        <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
          Elige entre <span className="font-semibold" style={{ color: INK, ...SANS }}>3 y 5 prioridades</span> para trabajar
          este año. El Consejo dará seguimiento solo a estas, mes con mes, en el Board IA.
        </p>
      </Prose>

      {/* Tarjetas seleccionables */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {disponibles.map((p, i) => (
          <PilarSeleccionable
            key={p.indice}
            pilar={p}
            index={i}
            selected={sel.has(p.indice)}
            onToggle={() => toggle(p.indice)}
          />
        ))}
      </div>

      {/* Barra de aprobación — pegada abajo para que el contador siempre esté a la vista */}
      <div className="sticky bottom-4 z-10">
        <div className="rounded-[26px] border p-4 shadow-sm backdrop-blur-md" style={{ background: `${CARD}/95`, borderColor: LINE }}>
          {tooMany && (
            <div
              className="mb-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-xs leading-relaxed"
              style={{ background: SAND, color: AMBER }}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Elegiste demasiadas. Si todo es prioridad, nada es prioridad — deja máximo {MAX}.
              </span>
            </div>
          )}
          {error && (
            <p className="mb-3 rounded-xl px-3 py-2.5 text-xs" style={{ background: "#fee2e2", color: "#dc2626" }}>{error}</p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm">
              <span
                className="font-bold tabular-nums"
                style={{ color: tooMany ? AMBER : enRango ? TEAL : INK2 }}
              >
                {count}
              </span>
              <span style={{ color: INK2 }}> de {MIN}–{MAX} elegidas</span>
            </p>
            <button
              onClick={aprobar}
              disabled={!enRango || saving}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2"
              style={{ background: ACCENT }}
            >
              {saving
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Aprobando…</>
                : <><Check className="h-4 w-4" /> Aprobar plan anual</>}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function PilarSeleccionable({
  pilar, index, selected, onToggle,
}: { pilar: PilarAnual; index: number; selected: boolean; onToggle: () => void }) {
  const kpis = (pilar.kpis ?? []).filter(k => k.label).slice(0, 3)
  const desc = pilar.objetivo || pilar.descripcion
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      className="group flex h-full flex-col rounded-[26px] border-2 p-5 text-left transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
      style={
        selected
          ? { borderColor: NAVY, background: "#f4f7fb" }
          : { borderColor: "#e5e7eb", background: "#fff" }
      }
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">
          Prioridad {index + 1}
        </span>
        <span
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors"
          style={
            selected
              ? { background: NAVY, borderColor: NAVY, color: "#fff" }
              : { borderColor: "#d1d5db", color: "transparent" }
          }
        >
          <Check className="h-3.5 w-3.5" />
        </span>
      </div>
      <h3 className="mt-2 text-sm font-bold leading-tight text-black">
        {pilar.nombre || `Prioridad ${index + 1}`}
      </h3>
      {desc && (
        <p className="mt-1.5 text-xs leading-relaxed line-clamp-3" style={{ color: INK2 }}>{desc}</p>
      )}
      {kpis.length > 0 && (
        <div className="mt-3 border-t border-gray-100 pt-3">
          <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">Indicadores</p>
          <ul className="space-y-1">
            {kpis.map((k, j) => (
              <li key={j} className="text-xs leading-snug text-gray-600">
                {k.label}
                {k.meta && <span className="text-gray-400"> · meta {k.meta}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </button>
  )
}

// ── Plan aprobado ─────────────────────────────────────────────────
function PlanAprobado({
  plan, onChange, aliveRef,
}: { plan: PlanAnual; onChange: (p: PlanAnual) => void; aliveRef: React.RefObject<boolean> }) {
  const [reopening, setReopening] = useState(false)
  const aprobados = plan.pilares_aprobados

  const fecha = plan.aprobado_at
    ? new Date(plan.aprobado_at).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" })
    : null

  const reabrir = async () => {
    if (reopening) return
    setReopening(true)
    try {
      const updated = await reabrirPlanAnual()
      if (aliveRef.current) onChange(updated)
    } catch {
      if (aliveRef.current) setReopening(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="space-y-6"
    >
      {/* Sello + reabrir */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[26px] border p-4"
        style={{ borderColor: LINE, background: CARD }}>
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full" style={{ background: NAVY }}>
            <BadgeCheck className="h-5 w-5 text-white" />
          </span>
          <div>
            <p className="text-sm font-bold" style={{ color: NAVY, ...SANS }}>
              Plan anual aprobado{fecha ? ` · ${fecha}` : ""}
            </p>
            <p className="text-xs" style={{ color: INK2 }}>
              {aprobados.length} {aprobados.length === 1 ? "prioridad" : "prioridades"} en seguimiento este año.
            </p>
          </div>
        </div>
        <button
          onClick={reabrir}
          disabled={reopening}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-xs font-medium text-white transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2"
          style={{ background: ACCENT }}
        >
          {reopening
            ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Reabriendo…</>
            : <><RotateCcw className="h-3.5 w-3.5" /> Reabrir para cambiar</>}
        </button>
      </div>

      {/* Prioridades aprobadas */}
      <div className="grid gap-4 md:grid-cols-2">
        {aprobados.map((p, i) => (
          <article key={p.indice} className="overflow-hidden rounded-[26px] border" style={{ borderColor: LINE }}>
            <div className="p-5 text-white" style={{ background: NAVY }}>
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/50">
                Prioridad {i + 1}
              </span>
              <h3 className="mt-1 text-base font-bold leading-tight" style={SANS}>{p.nombre || `Prioridad ${i + 1}`}</h3>
              {(p.objetivo || p.descripcion) && (
                <p className="mt-2 text-xs leading-relaxed text-white/80">{p.objetivo || p.descripcion}</p>
              )}
            </div>
            <div className="space-y-4 p-5">
              {/* Razón: por qué esta prioridad importa */}
              {p.razon && (
                <div className="rounded-xl border-l-2 pl-3" style={{ borderColor: LINE }}>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: MUTED }}>Por qué importa</p>
                  <p className="mt-0.5 text-xs leading-relaxed" style={{ color: INK }}>{p.razon}</p>
                </div>
              )}
              {/* Indicadores: línea base → meta */}
              {(p.kpis ?? []).filter(k => k.label).length > 0 && (
                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: MUTED }}>
                    Indicadores <span style={{ color: MUTED }}>· línea base → meta</span>
                  </p>
                  <ul className="space-y-2">
                    {(p.kpis ?? []).filter(k => k.label).map((k, j) => (
                      <li key={j} className="flex items-baseline justify-between gap-3 text-xs">
                        <span style={{ color: INK }}>{k.label}</span>
                        <span className="shrink-0 tabular-nums" style={{ color: INK2 }}>
                          {k.actual || "—"}
                          <span className="mx-1" style={{ color: MUTED }}>→</span>
                          <span className="font-semibold" style={{ color: TEAL }}>{k.meta || "por definir"}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Tareas */}
              {(p.estrategias ?? []).length > 0 && (
                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: MUTED }}>Tareas</p>
                  <ol className="space-y-1.5">
                    {(p.estrategias ?? []).map((s, j) => (
                      <li key={j} className="flex gap-2 text-xs leading-relaxed" style={{ color: INK2 }}>
                        <span className="shrink-0 font-bold tabular-nums" style={{ color: NAVY }}>{j + 1}.</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {/* Riesgos de la prioridad */}
              {(p.riesgos ?? []).length > 0 && (
                <div>
                  <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: AMBER }}>Riesgos</p>
                  <ul className="space-y-1.5">
                    {(p.riesgos ?? []).map((r, j) => (
                      <li key={j} className="flex gap-2 text-xs leading-relaxed" style={{ color: INK2 }}>
                        <span className="mt-1 h-1 w-1 shrink-0 rounded-full" style={{ background: AMBER }} />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </motion.div>
  )
}
