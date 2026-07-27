"use client"

import { Fragment, useState } from "react"
import Link from "next/link"
import { ArrowRight, ChevronRight } from "lucide-react"
import { Roadmap, Pilar } from "@/lib/roadmap"
import DocSection from "./DocSection"
import { pilarColor } from "./shared"

const kickerCls = "text-[10px] font-bold uppercase tracking-[0.18em]"

/** Texto que se recorta a pocas líneas y se despliega con "ver más" cuando es largo. */
function Recorte({ text, className }: { text: string; className?: string }) {
  const [open, setOpen] = useState(false)
  const largo = text.length > 90
  return (
    <div>
      <p className={`${className ?? ""} ${!open && largo ? "line-clamp-3" : ""}`}>{text}</p>
      {largo && (
        <button type="button" onClick={() => setOpen(o => !o)}
          className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--gob-stone)] transition-colors hover:text-[var(--gob-navy)]">
          {open ? "ver menos" : "ver más"}
        </button>
      )}
    </div>
  )
}

/** Lista de un paso (indicadores, metas o tareas): muestra los primeros y despliega el resto. */
function ListaPaso({ items, color }: { items: string[]; color: string }) {
  const [open, setOpen] = useState(false)
  if (items.length === 0) return <p className="text-sm text-[var(--gob-stone)]">—</p>
  const visibles = open ? items : items.slice(0, 3)
  const resto = items.length - 3
  return (
    <div className="space-y-1.5">
      <ul className="space-y-1.5">
        {visibles.map((t, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
            <span className={`text-sm leading-snug text-[var(--gob-charcoal)] ${open ? "" : "line-clamp-2"}`}>{t}</span>
          </li>
        ))}
      </ul>
      {resto > 0 && (
        <button type="button" onClick={() => setOpen(o => !o)}
          className="text-[10px] font-semibold uppercase tracking-wide text-[var(--gob-stone)] transition-colors hover:text-[var(--gob-navy)]">
          {open ? "ver menos" : `ver ${resto} más`}
        </button>
      )}
    </div>
  )
}

/** Caja de un paso de la cadena: nombre del nivel arriba (versalitas) + contenido debajo. */
function Paso({ nivel, color, children }: { nivel: string; color: string; children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col rounded-2xl border border-[var(--gob-rule)] bg-white p-4 md:w-60 md:shrink-0">
      <p className={`${kickerCls} mb-2`} style={{ color }}>{nivel}</p>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

/** La flecha que conecta dos pasos: hacia abajo en móvil, hacia la derecha en escritorio. */
function Conector() {
  return (
    <div className="flex items-center justify-center py-1.5 md:shrink-0 md:py-0 md:px-1">
      <ChevronRight className="h-5 w-5 rotate-90 text-[var(--gob-rule)] md:rotate-0" strokeWidth={2.5} />
    </div>
  )
}

/** La cadena de una prioridad: Prioridad → Indicador → Meta → Tareas → Plan de acción → Consejo. */
function CadenaPilar({ pilar, indice }: { pilar: Pilar; indice: number }) {
  const color = pilarColor(indice)
  const kpis = (pilar.kpis ?? []).filter(k => k.label)
  const indicadores = kpis.map(k => k.label)
  const metas = kpis.map(k => (k.meta?.trim() ? k.meta.trim() : "por definir"))
  const tareas = (pilar.estrategias ?? []).filter(Boolean)
  const objetivo = pilar.objetivo?.trim()

  const pasos: React.ReactNode[] = [
    <Paso key="prioridad" nivel="Prioridad estratégica" color={color}>
      <p className="text-sm font-bold leading-snug text-[var(--gob-ink)] line-clamp-3">
        {pilar.nombre || `Prioridad estratégica ${indice + 1}`}
      </p>
      {objetivo && <Recorte text={objetivo} className="mt-1.5 text-xs leading-snug text-[var(--gob-muted)]" />}
    </Paso>,

    <Paso key="indicador" nivel="Indicador" color={color}>
      <ListaPaso items={indicadores} color={color} />
    </Paso>,

    <Paso key="meta" nivel="Meta" color={color}>
      <ListaPaso items={metas} color={color} />
    </Paso>,

    <Paso key="tareas" nivel="Tareas" color={color}>
      <ListaPaso items={tareas} color={color} />
    </Paso>,

    <div key="plan" className="flex w-full flex-col rounded-2xl border border-[var(--gob-navy)]/25 bg-[var(--gob-navy)]/[0.04] p-4 md:w-60 md:shrink-0">
      <p className={`${kickerCls} mb-2 text-[var(--gob-navy)]`}>Plan de acción</p>
      <p className="text-xs leading-snug text-[var(--gob-charcoal)]">
        El quién, cuándo y la evidencia se asignan y se les da seguimiento en Board IA.
      </p>
      <Link href="/dashboard/consejo"
        className="mt-2.5 inline-flex items-center gap-1 text-xs font-semibold text-[var(--gob-navy)] transition-opacity hover:opacity-70">
        Ir a Board IA <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>,

    <div key="consejo" className="flex w-full flex-col rounded-2xl bg-[var(--gob-navy)] p-4 md:w-60 md:shrink-0">
      <p className={`${kickerCls} mb-2 text-[var(--gob-bone)]/70`}>Seguimiento del Consejo</p>
      <p className="text-sm font-semibold leading-snug text-[var(--gob-bone)]">El Consejo revisa el avance cada mes.</p>
    </div>,
  ]

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2.5">
        <span className="h-1 w-8 shrink-0 rounded-full" style={{ background: color }} />
        <p className={kickerCls} style={{ color }}>Prioridad estratégica {indice + 1}</p>
      </div>
      <div className="flex flex-col md:flex-row md:flex-nowrap md:items-stretch md:overflow-x-auto md:pb-2">
        {pasos.map((p, i) => (
          <Fragment key={i}>
            {i > 0 && <Conector />}
            {p}
          </Fragment>
        ))}
      </div>
    </div>
  )
}

/** Solo lectura: cada prioridad estratégica dibujada como la cadena completa que la lleva a la ejecución. */
export default function SeccionCadena({ roadmap }: { roadmap: Roadmap }) {
  const pilares = roadmap.pilares ?? []
  return (
    <DocSection id="cadena" orden="03 · La cadena" titulo="La cadena estratégica"
      nota="Cada prioridad, paso a paso: qué se quiere lograr, cómo se mide, la meta y las tareas — hasta quién la ejecuta. Así se conecta el plan con el seguimiento mensual del Consejo.">
      {pilares.length > 0 ? (
        <div className="space-y-8">
          {pilares.map((p, i) => <CadenaPilar key={i} pilar={p} indice={i} />)}
        </div>
      ) : (
        <p className="text-xs italic text-[var(--gob-stone)]">Sin prioridades estratégicas aún.</p>
      )}
    </DocSection>
  )
}
