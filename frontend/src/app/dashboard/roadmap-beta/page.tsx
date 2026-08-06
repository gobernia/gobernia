"use client"

import { useEffect, useRef, useState, type CSSProperties } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, ArrowRight, Map as MapIcon, CalendarCheck } from "lucide-react"
import { PageShell, PageHeader } from "@/components/ui/PageShell"
import { getRoadmap, type Roadmap, type Pilar } from "@/lib/roadmap"
import { aniosDelPlan, pilarColor, roadmapIsEmpty } from "@/components/roadmap/shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Paleta bento — mismos tokens del Inicio.
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#FF5C1A"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

type AnioKey = "anio1" | "anio2" | "anio3"

export default function RoadmapBetaPage() {
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [loaded, setLoaded] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getRoadmap()
      .then(r => { if (aliveRef.current) setRoadmap(r) })
      .catch(() => { if (aliveRef.current) setRoadmap(null) })
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    return () => { aliveRef.current = false }
  }, [])

  const hasRoadmap = !!roadmap && !roadmapIsEmpty(roadmap)

  return (
    <div className="min-h-dvh text-black antialiased" style={{ background: PAPER }}>
      <PageHeader
        eyebrow="Cómo te ves a 3 años"
        title="Roadmap"
        actions={
          hasRoadmap ? (
            <Link
              href="/dashboard/plan-anual"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-xs font-medium text-white transition-colors"
              style={{ background: ACCENT }}
            >
              <CalendarCheck className="h-3.5 w-3.5" /> Ir a mi Plan anual
            </Link>
          ) : undefined
        }
      />

      <main>
        <PageShell className="py-10 space-y-8">

          {/* Cargando */}
          {!loaded && (
            <div className="flex items-center justify-center rounded-[26px] p-16" style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} />
            </div>
          )}

          {/* Vacío */}
          {loaded && !hasRoadmap && (
            <div className="flex flex-col items-center gap-4 rounded-[26px] p-12 text-center sm:p-16" style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <div className="flex h-14 w-14 items-center justify-center rounded-[26px] border-2" style={{ borderColor: LINE, color: MUTED }}>
                <MapIcon className="h-5 w-5" />
              </div>
              <div className="max-w-md space-y-1.5">
                <p className="text-base font-medium" style={{ ...SANS, color: INK }}>Todavía no hay una dirección a 3 años</p>
                <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
                  Cuando generes tu plan, aquí verás — muy sencillo, año por año — a dónde apunta la
                  empresa en los próximos tres años. El detalle y las tareas viven en tu Plan anual.
                </p>
              </div>
              <Link
                href="/dashboard/plan"
                className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors"
                style={{ background: ACCENT }}
              >
                Generar mi plan <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}

          {/* La línea de tiempo, año por año */}
          {loaded && hasRoadmap && <RoadmapTresAnios roadmap={roadmap!} />}

        </PageShell>
      </main>
    </div>
  )
}

// El roadmap: sencillo, año por año. Qué debe conseguir la empresa cada año durante
// los próximos tres. El detalle por prioridad y las tareas NO van aquí — van en el Plan.
function RoadmapTresAnios({ roadmap }: { roadmap: Roadmap }) {
  const [a1, a2, a3] = aniosDelPlan(roadmap.anio_objetivo)
  const temas = roadmap.temas_por_anio ?? {}
  const pilares = roadmap.pilares ?? []

  const anios: { n: number; key: AnioKey; lema?: string; activo: boolean }[] = [
    { n: a1, key: "anio1", lema: temas.anio1, activo: true },
    { n: a2, key: "anio2", lema: temas.anio2, activo: false },
    { n: a3, key: "anio3", lema: temas.anio3, activo: false },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="space-y-6"
    >
      {/* La pregunta que responde el roadmap + la regla de que solo el año 1 se ejecuta */}
      <div className="max-w-3xl space-y-2">
        <p className="text-lg font-semibold leading-snug tracking-tight" style={{ ...SANS, color: INK }}>
          ¿Qué debe conseguir la empresa en los próximos tres años para fortalecerse, crecer y
          asegurar su continuidad?
        </p>
        <p className="text-sm leading-relaxed" style={{ color: INK2 }}>
          Solo el <span className="font-semibold" style={{ color: INK }}>año en curso se ejecuta</span> — su detalle
          y sus tareas están en tu{" "}
          <Link href="/dashboard/plan-anual" className="font-medium underline" style={{ color: BNAVY }}>Plan anual</Link>.
          Los <span style={{ color: ACCENT }}>años 2 y 3 son orientativos</span> y se ajustan al cerrar cada año.
        </p>
      </div>

      {/* Tres columnas: un año cada una */}
      <div className="grid gap-5 lg:grid-cols-3">
        {anios.map((y, i) => (
          <ColumnaAnio key={y.n} anio={y} orden={i + 1} pilares={pilares} />
        ))}
      </div>
    </motion.div>
  )
}

function ColumnaAnio({
  anio, orden, pilares,
}: {
  anio: { n: number; key: AnioKey; lema?: string; activo: boolean }
  orden: number
  pilares: Pilar[]
}) {
  // Qué avanza cada pilar ESE año: su fase (el titular del año) y sus milestones.
  const filas = pilares
    .map((p, pi) => ({
      nombre: p.nombre,
      color: pilarColor(pi),
      fase: p.fases?.[anio.key]?.titulo?.trim() || "",
      hitos: (p.milestones?.[anio.key] ?? []).map(s => s.trim()).filter(Boolean),
    }))
    .filter(f => f.nombre && (f.fase || f.hitos.length > 0))

  const activo = anio.activo

  return (
    <section
      className="flex flex-col overflow-hidden rounded-[26px] border"
      style={activo ? { borderColor: BNAVY } : { borderColor: LINE }}
    >
      {/* Cabecera del año */}
      <div className="p-5" style={activo ? { background: BNAVY, color: "#fff" } : { background: SAND }}>
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em]" style={{ ...SANS, color: activo ? "rgba(255,255,255,0.55)" : MUTED }}>
              Año {orden}
            </p>
            <p className="text-xl font-bold tabular-nums" style={{ ...SANS, color: activo ? "#fff" : INK }}>{anio.n}</p>
          </div>
          <span
            className="rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em]"
            style={activo ? { background: "rgba(255,255,255,0.16)", color: "#fff" } : { background: CARD, color: ACCENT, border: `1px solid ${LINE}` }}
          >
            {activo ? "En ejecución" : "Orientativo"}
          </span>
        </div>
        {anio.lema && (
          <p className="mt-2 text-sm font-medium leading-snug" style={{ ...SANS, color: activo ? "rgba(255,255,255,0.92)" : INK }}>
            «{anio.lema}»
          </p>
        )}
      </div>

      {/* Qué se trabaja ese año, prioridad por prioridad */}
      <div className="flex-1 space-y-4 p-5" style={{ background: CARD }}>
        {filas.length > 0 ? (
          filas.map((f, j) => (
            <div key={j} className="border-l-2 pl-3" style={{ borderColor: f.color }}>
              <p className="text-sm font-bold leading-tight" style={{ ...SANS, color: INK }}>{f.nombre}</p>
              {f.fase && <p className="mt-0.5 text-xs font-medium" style={{ color: INK2 }}>{f.fase}</p>}
              {f.hitos.length > 0 && (
                <ul className="mt-1.5 space-y-1">
                  {f.hitos.map((h, k) => (
                    <li key={k} className="flex gap-1.5 text-xs leading-relaxed" style={{ color: INK2 }}>
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full" style={{ background: f.color }} />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        ) : (
          <p className="text-xs italic" style={{ color: MUTED }}>Sin actividades definidas para este año todavía.</p>
        )}
      </div>

      {/* El año en curso conecta con el Plan anual */}
      {activo && (
        <div className="border-t p-4" style={{ borderColor: LINE }}>
          <Link
            href="/dashboard/plan-anual"
            className="inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-xs font-medium text-white transition-colors"
            style={{ background: ACCENT }}
          >
            <CalendarCheck className="h-3.5 w-3.5" /> Trabajar este año en mi Plan anual
          </Link>
        </div>
      )}
    </section>
  )
}
