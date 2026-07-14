"use client"

import { useEffect, useState } from "react"
import { DOC_SECCIONES } from "./shared"

/**
 * Índice del documento. Rail vertical en `lg:`; barra de chips en móvil.
 * Se ilumina con la sección visible (IntersectionObserver) y lleva a ella al hacer clic.
 */
export default function IndiceDoc({ ids }: { ids: string[] }) {
  const [activo, setActivo] = useState<string>(ids[0] ?? "")

  useEffect(() => {
    if (ids.length === 0) return
    const visibles = new Set<string>()
    const obs = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (e.isIntersecting) visibles.add(e.target.id)
        else visibles.delete(e.target.id)
      }
      // La sección activa es la primera visible en el orden del documento.
      const primera = ids.find(id => visibles.has(id))
      if (primera) setActivo(primera)
    }, { rootMargin: "-120px 0px -55% 0px", threshold: 0 })

    for (const id of ids) {
      const el = document.getElementById(id)
      if (el) obs.observe(el)
    }
    return () => obs.disconnect()
  }, [ids])

  const irA = (id: string) => {
    const el = document.getElementById(id)
    if (!el) return
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" })
    setActivo(id)
  }

  const secciones = DOC_SECCIONES.filter(s => ids.includes(s.id))

  return (
    <>
      {/* Móvil / tablet: chips horizontales */}
      <nav aria-label="Índice del documento"
        className="lg:hidden -mx-[var(--px-fluid)] px-[var(--px-fluid)] overflow-x-auto pb-1">
        <ul className="flex gap-2 w-max">
          {secciones.map(s => (
            <li key={s.id}>
              <button onClick={() => irA(s.id)} aria-current={activo === s.id ? "true" : undefined}
                className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] ${
                  activo === s.id
                    ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                    : "border-[var(--gob-rule)] text-[var(--gob-muted)] hover:border-[var(--gob-navy)]/40"}`}>
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Escritorio: rail vertical */}
      <nav aria-label="Índice del documento" className="hidden lg:block sticky top-28 self-start">
        <p className="text-[10px] font-bold tracking-[0.18em] uppercase text-[var(--gob-stone)] mb-3">Índice</p>
        <ul className="space-y-0.5">
          {secciones.map((s, i) => {
            const on = activo === s.id
            return (
              <li key={s.id}>
                <button onClick={() => irA(s.id)} aria-current={on ? "true" : undefined}
                  className={`group flex w-full items-start gap-2.5 rounded-md py-1.5 pl-2.5 pr-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] ${
                    on ? "bg-[var(--gob-navy)]/[0.06]" : "hover:bg-black/[0.03]"}`}>
                  <span className={`mt-[3px] h-3.5 w-px shrink-0 transition-colors ${
                    on ? "bg-[var(--gob-navy)]" : "bg-[var(--gob-rule)]"}`} />
                  <span className={`text-[11px] font-bold tabular-nums transition-colors ${
                    on ? "text-[var(--gob-navy)]" : "text-[var(--gob-stone)]"}`}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className={`text-[13px] leading-tight transition-colors ${
                    on ? "font-semibold text-[var(--gob-ink)]" : "text-[var(--gob-muted)] group-hover:text-[var(--gob-ink)]"}`}>
                    {s.label}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>
    </>
  )
}
