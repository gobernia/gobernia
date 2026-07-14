"use client"

import { ReactNode } from "react"

/**
 * Sección del expediente: regla superior, número de orden, título y acciones.
 * El `id` es el ancla del índice (scroll-spy).
 */
export default function DocSection({ id, orden, titulo, nota, actions, children }: {
  id?: string
  orden?: string
  titulo: string
  nota?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-28 border-t border-[var(--gob-rule)] pt-6">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
        <div className="min-w-0">
          {orden && (
            <p className="text-[10px] font-bold tracking-[0.18em] uppercase text-[var(--gob-stone)] mb-1">{orden}</p>
          )}
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--gob-ink)]">{titulo}</h2>
          {nota && <p className="text-sm text-[var(--gob-muted)] mt-1 max-w-2xl leading-relaxed">{nota}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}
