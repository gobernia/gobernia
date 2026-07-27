"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Loader2, ArrowRight, Map as MapIcon, CalendarCheck } from "lucide-react"
import { PageShell, PageHeader, Prose } from "@/components/ui/PageShell"
import { getRoadmap, type Roadmap } from "@/lib/roadmap"
import { roadmapIsEmpty } from "@/components/roadmap/shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Colores por hex — Tailwind v4 no detecta clases dinámicas.
const NAVY = "#142849"
const STEEL = "#9fb2ce"

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
  const anioActual = new Date().getFullYear()

  return (
    <div className="min-h-dvh bg-white text-black">
      <PageHeader
        eyebrow="Dirección a 3 años"
        title="Roadmap"
        actions={
          hasRoadmap ? (
            <Link
              href="/dashboard/plan-anual"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-4 py-2.5 text-xs font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
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
            <div className="flex items-center justify-center rounded-2xl border border-gray-100 p-16">
              <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
            </div>
          )}

          {/* Vacío */}
          {loaded && !hasRoadmap && (
            <div className="flex flex-col items-center gap-4 rounded-2xl border border-gray-100 p-12 text-center sm:p-16">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border-2 border-gray-100">
                <MapIcon className="h-5 w-5 text-gray-300" />
              </div>
              <div className="max-w-md space-y-1.5">
                <p className="text-base font-medium text-black">Todavía no hay una dirección a 3 años</p>
                <p className="text-sm leading-relaxed text-gray-500">
                  Cuando generes tu Roadmap, aquí verás la estrategia a tres años: la visión, las prioridades
                  y hacia dónde apunta cada año.
                </p>
              </div>
              <Link
                href="/dashboard/plan"
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-5 py-2.5 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
              >
                Generar mi plan <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}

          {/* Contenido */}
          {loaded && hasRoadmap && (
            <RoadmapBeta roadmap={roadmap!} anioActual={anioActual} />
          )}

        </PageShell>
      </main>
    </div>
  )
}

function RoadmapBeta({ roadmap, anioActual }: { roadmap: Roadmap; anioActual: number }) {
  const objetivos = roadmap.objetivos_estrategicos ?? []
  const enablers = roadmap.key_enablers ?? []
  const pilares = (roadmap.pilares ?? []).slice(0, 6)
  const n = pilares.length || 1
  const gridCols = { gridTemplateColumns: `repeat(${n}, minmax(190px,1fr))` }

  const temas = roadmap.temas_por_anio ?? {}
  // El año objetivo del roadmap ancla los tres años; si no hay, el año 1 es el actual.
  const anio1 = roadmap.anio_objetivo && roadmap.anio_objetivo > 2000
    ? roadmap.anio_objetivo - 2
    : anioActual
  const anios = [
    { n: anio1,     lema: temas.anio1, activo: true },
    { n: anio1 + 1, lema: temas.anio2, activo: false },
    { n: anio1 + 2, lema: temas.anio3, activo: false },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE }}
      className="space-y-8"
    >
      {/* Banner: qué es cada año */}
      <div className="rounded-2xl border border-[var(--gob-rule)] bg-[var(--gob-bone)]/40 p-5">
        <p className="text-sm leading-relaxed text-[var(--gob-charcoal)]">
          Esta es tu <span className="font-semibold text-black">dirección a tres años</span>. El{" "}
          <span className="font-semibold" style={{ color: NAVY }}>Año 1 es tu Plan anual</span> — lo que
          de verdad se ejecuta y el Consejo monitorea cada mes. Los{" "}
          <span className="font-semibold" style={{ color: "#b45309" }}>Años 2 y 3 son una propuesta orientativa</span>:
          marcan el rumbo, pero se aterrizan año con año.
        </p>
        <Link
          href="/dashboard/plan-anual"
          className="mt-4 inline-flex items-center gap-2 text-sm font-medium transition-colors hover:underline"
          style={{ color: NAVY }}
        >
          <CalendarCheck className="h-4 w-4" /> Ir a mi Plan anual <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {/* Recorrido de los tres años */}
      <div className="grid gap-3 md:grid-cols-3">
        {anios.map((a, i) => (
          <div
            key={i}
            className="rounded-2xl border p-5"
            style={
              a.activo
                ? { background: NAVY, borderColor: NAVY, color: "#fff" }
                : { background: "#fff", borderColor: "var(--gob-rule)" }
            }
          >
            <div className="flex items-center justify-between">
              <span
                className="text-[10px] font-bold uppercase tracking-[0.16em]"
                style={{ color: a.activo ? "rgba(255,255,255,0.6)" : "var(--gob-muted)" }}
              >
                Año {i + 1} · {a.n}
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                style={
                  a.activo
                    ? { background: "rgba(255,255,255,0.15)", color: "#fff" }
                    : { background: "#fef3e2", color: "#b45309" }
                }
              >
                {a.activo ? "Plan anual" : "Orientativo"}
              </span>
            </div>
            <p
              className="mt-3 text-sm font-semibold leading-snug"
              style={{ color: a.activo ? "#fff" : NAVY }}
            >
              {a.lema || (a.activo ? "El año en curso" : "Por definir")}
            </p>
            {a.activo && (
              <Link
                href="/dashboard/plan-anual"
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-white/80 transition-colors hover:text-white"
              >
                Elegir prioridades <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
          </div>
        ))}
      </div>

      {/* Misión · Visión */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl p-6 text-white" style={{ background: NAVY }}>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-white/60">Misión</p>
          <p className="text-sm leading-relaxed text-white/90">{roadmap.mision || "—"}</p>
        </div>
        <div className="rounded-2xl p-6 text-white" style={{ background: NAVY }}>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-white/60">Visión</p>
          <p className="text-sm leading-relaxed text-white/90">{roadmap.vision || "—"}</p>
        </div>
      </div>

      {/* KPI Visión */}
      {objetivos.length > 0 && (
        <div className="rounded-xl px-6 py-3.5 text-sm text-white" style={{ background: NAVY }}>
          <span className="font-bold">KPI Visión: </span>
          <span className="text-white/85">{objetivos.join(" · ")}</span>
        </div>
      )}

      {/* Prioridades estratégicas */}
      <div className="space-y-4">
        <div
          className="rounded-xl py-2.5 text-center text-sm font-bold uppercase tracking-wide"
          style={{ background: STEEL, color: NAVY }}
        >
          Prioridades estratégicas
        </div>

        <div className="overflow-x-auto">
          <div className="grid min-w-[860px] gap-3" style={gridCols}>
            {pilares.map((p, i) => {
              const kpis = (p.kpis ?? []).filter(k => k.label).slice(0, 3)
              const desc = p.objetivo || p.descripcion
              return (
                <article key={i} className="rounded-2xl p-4 text-center text-white" style={{ background: NAVY }}>
                  <h3 className="text-sm font-bold leading-tight">{p.nombre || `Prioridad ${i + 1}`}</h3>
                  {desc && (
                    <p className="mt-2 text-xs italic leading-relaxed text-white/75 line-clamp-3">{desc}</p>
                  )}
                  {kpis.length > 0 && (
                    <div className="mt-3 border-t border-white/15 pt-3">
                      <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-white/50">Indicadores</p>
                      <ul className="space-y-1">
                        {kpis.map((k, j) => (
                          <li key={j} className="text-xs leading-snug text-white/85">{k.label}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </div>
      </div>

      {/* Key enablers */}
      {enablers.length > 0 && (
        <div className="rounded-xl px-6 py-3.5 text-sm text-white" style={{ background: NAVY }}>
          <span className="font-bold">Key enablers: </span>
          <span className="text-white/85">{enablers.join(" · ")}</span>
        </div>
      )}

      {/* Cierre: solo lectura */}
      <Prose>
        <p className="text-xs leading-relaxed text-gray-400">
          Esta vista es solo de lectura. Para trabajar el año en curso, elige y aprueba tus prioridades en{" "}
          <Link href="/dashboard/plan-anual" className="font-medium underline" style={{ color: NAVY }}>Plan anual</Link>.
        </p>
      </Prose>
    </motion.div>
  )
}
