"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { ClipboardList, ArrowRight, Gavel, Target, ListChecks, Gauge } from "lucide-react"
import { getPlanAnual, type PlanAnual, type PilarAnual } from "@/lib/planAnual"

/**
 * La orden del día, armada DESDE el Plan anual — la cadena que pide el cliente:
 * cada punto = una prioridad aprobada, con su indicador, su meta, sus tareas y
 * qué decide el Consejo. Es lo que el Consejo revisará al sesionar el mes.
 *
 * Paso 1: se compone en vivo de las prioridades aprobadas (sin tocar la base de
 * datos). El análisis por punto, los documentos por punto y el acta de 5 apartados
 * son fases siguientes.
 */

// Colores por hex — Tailwind v4 no ve clases dinámicas.
const NAVY = "#142849"
const TEAL = "#0f766e"

// Acentos por prioridad, on-brand (mismos que el roadmap).
const PILAR_COLORS = ["#1e3a5f", "#0f766e", "#b45309", "#6d28d9", "#b91c1c", "#334155"]
const colorDe = (i: number) => PILAR_COLORS[i % PILAR_COLORS.length]

export default function OrdenDelDiaCadena() {
  const [plan, setPlan] = useState<PlanAnual | null>(null)
  const [loaded, setLoaded] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getPlanAnual()
      .then(p => { if (aliveRef.current) setPlan(p) })
      .catch(() => { if (aliveRef.current) setPlan(null) })
      .finally(() => { if (aliveRef.current) setLoaded(true) })
    return () => { aliveRef.current = false }
  }, [])

  if (!loaded) return null

  const aprobados = plan?.pilares_aprobados ?? []
  const listo = !!plan?.aprobado && aprobados.length > 0

  return (
    <section className="space-y-5">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-widest text-gray-400">Antes de sesionar</p>
        <h2 className="text-2xl font-bold tracking-tight text-black">Orden del día</h2>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-gray-500">
          Lo que el Consejo revisará este mes. Cada punto sale de tu Plan anual y va conectado:
          la <span className="font-medium text-gray-700">prioridad</span>, su{" "}
          <span className="font-medium text-gray-700">indicador</span>, su{" "}
          <span className="font-medium text-gray-700">meta</span>, las{" "}
          <span className="font-medium text-gray-700">tareas</span> y{" "}
          <span className="font-medium text-gray-700">qué decide el Consejo</span>.
        </p>
      </div>

      {!listo ? (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-gray-100 p-6">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl" style={{ background: "#f4f7fb", color: NAVY }}>
            <ClipboardList className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <p className="text-sm font-medium text-black">Aún no hay orden del día</p>
            <p className="max-w-md text-sm leading-relaxed text-gray-500">
              La orden del día se arma con las prioridades de tu Plan anual. Aprueba entre 3 y 5
              prioridades y aquí aparecerá lo que el Consejo revisará cada mes.
            </p>
          </div>
          <Link
            href="/dashboard/plan-anual"
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-4 py-2.5 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]"
          >
            Aprobar mi Plan anual <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <ol className="space-y-4">
          {aprobados.map((p, i) => (
            <PuntoOrden key={p.indice} pilar={p} orden={i + 1} color={colorDe(i)} />
          ))}
        </ol>
      )}
    </section>
  )
}

function PuntoOrden({ pilar, orden, color }: { pilar: PilarAnual; orden: number; color: string }) {
  const kpis = (pilar.kpis ?? []).filter(k => k.label)
  const tareas = (pilar.estrategias ?? []).filter(Boolean)
  const meta = pilar.objetivo?.trim() || ""

  return (
    <li className="overflow-hidden rounded-2xl border border-gray-100">
      {/* Cabecera del punto: número + prioridad */}
      <div className="flex items-center gap-3 border-l-4 p-4" style={{ borderColor: color, background: "#fafafa" }}>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: color }}>
          {orden}
        </span>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-400">Punto {orden} · Prioridad</p>
          <p className="text-sm font-bold leading-tight text-black">{pilar.nombre || `Prioridad ${orden}`}</p>
        </div>
      </div>

      {/* La cadena: indicador · meta · tareas */}
      <div className="grid gap-px bg-gray-100 md:grid-cols-3">
        {/* Indicador */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <Gauge className="h-3.5 w-3.5" /> Indicador
          </p>
          {kpis.length > 0 ? (
            <ul className="space-y-1.5">
              {kpis.map((k, j) => (
                <li key={j} className="text-xs leading-snug text-gray-700">
                  {k.label}
                  <span className="mt-0.5 block text-gray-500">
                    {k.actual || "—"}
                    <span className="mx-1 text-gray-300">→</span>
                    <span className="font-semibold" style={{ color: TEAL }}>{k.meta || "por definir"}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-gray-400">Sin indicador definido.</p>
          )}
        </div>

        {/* Meta */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <Target className="h-3.5 w-3.5" /> Meta
          </p>
          {meta ? (
            <p className="text-xs leading-relaxed text-gray-700">{meta}</p>
          ) : (
            <p className="text-xs italic text-gray-400">La meta la fija el dueño.</p>
          )}
        </div>

        {/* Tareas */}
        <div className="bg-white p-4">
          <p className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">
            <ListChecks className="h-3.5 w-3.5" /> Tareas
          </p>
          {tareas.length > 0 ? (
            <ol className="space-y-1">
              {tareas.map((t, j) => (
                <li key={j} className="flex gap-1.5 text-xs leading-relaxed text-gray-600">
                  <span className="shrink-0 font-bold tabular-nums" style={{ color }}>{j + 1}.</span>
                  <span>{t}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs italic text-gray-400">Sin tareas aún.</p>
          )}
        </div>
      </div>

      {/* Qué decide el Consejo */}
      <div className="flex items-start gap-2.5 border-t border-gray-100 p-4" style={{ background: "#f7f8fa" }}>
        <Gavel className="mt-0.5 h-4 w-4 shrink-0" style={{ color: NAVY }} />
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400">Qué decide el Consejo</p>
          <p className="mt-0.5 text-xs leading-relaxed text-gray-600">
            Revisar el avance del periodo con la evidencia cargada y decidir si la prioridad continúa,
            se ajusta la meta o se corrige el rumbo.
          </p>
        </div>
      </div>
    </li>
  )
}
