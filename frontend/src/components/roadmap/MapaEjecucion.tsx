"use client"

import { useCallback, useMemo, useState, useSyncExternalStore } from "react"
import { Pilar, TemasPorAnio } from "@/lib/roadmap"
import { ANIO_KEYS, aniosDelPlan, pilarColor } from "./shared"

const LABEL_W = 180 // px de la columna de pilares; la línea de "hoy" se posiciona a partir de aquí.

const noop = () => () => {}

/** Posición de hoy dentro del span de 3 años (0–1), o null si hoy cae fuera del plan. */
function posicionDeHoy(anioObjetivo?: number): number | null {
  const [a1, , a3] = aniosDelPlan(anioObjetivo)
  const ini = new Date(a1, 0, 1).getTime()
  const fin = new Date(a3 + 1, 0, 1).getTime()
  const now = Date.now()
  if (now < ini || now > fin) return null
  return (now - ini) / (fin - ini)
}

/** La línea de "hoy" solo existe en el cliente: en el servidor no hay "hoy" (evita desajuste de hidratación). */
function useHoy(anioObjetivo?: number): number | null {
  const pct = useMemo(() => posicionDeHoy(anioObjetivo), [anioObjetivo])
  const getSnapshot = useCallback(() => pct, [pct])
  return useSyncExternalStore(noop, getSnapshot, () => null)
}

/**
 * SIGNATURE — Mapa de ejecución: pilares (filas) × años (columnas).
 * Clic en un pilar para aislar su fila; la línea punteada marca dónde estamos hoy.
 */
export default function MapaEjecucion({ pilares, temas, anioObjetivo }: {
  pilares: Pilar[]
  temas: TemasPorAnio
  anioObjetivo?: number
}) {
  const [foco, setFoco] = useState<number | null>(null)
  const pctHoy = useHoy(anioObjetivo)
  const anios = aniosDelPlan(anioObjetivo)

  return (
    <div>
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="relative min-w-[880px] pt-7">
          {/* Línea de "hoy" */}
          {pctHoy !== null && (
            <div className="pointer-events-none absolute top-7 bottom-0 z-10"
              style={{ left: `calc(${LABEL_W}px + (100% - ${LABEL_W}px) * ${pctHoy})` }}>
              <span className="absolute left-0 top-0 -translate-x-1/2 -translate-y-[calc(100%+4px)] rounded-full bg-[var(--gob-navy)] px-2 py-[3px] text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--gob-bone)]">
                hoy
              </span>
              <span className="block h-full w-px border-l border-dashed border-[var(--gob-navy)]/45" />
            </div>
          )}

          {/* Cabecera de años */}
          <div className="grid" style={{ gridTemplateColumns: `${LABEL_W}px repeat(3, minmax(220px, 1fr))` }}>
            <div />
            {ANIO_KEYS.map((yk, yi) => (
              <div key={yk} className="border-l border-[var(--gob-rule)] px-4 pb-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--gob-stone)]">
                  Año {yi + 1} · {anios[yi]}
                </p>
                {temas[yk] && (
                  <p className="mt-0.5 text-sm font-semibold leading-tight text-[var(--gob-navy)]">{temas[yk]}</p>
                )}
              </div>
            ))}
          </div>

          {/* Filas de pilares */}
          {pilares.map((p, i) => {
            const c = pilarColor(i)
            const atenuado = foco !== null && foco !== i
            const activo = foco === i
            return (
              <div key={i}
                className={`grid border-t border-[var(--gob-rule)] transition-opacity duration-200 motion-reduce:transition-none ${
                  atenuado ? "opacity-25" : "opacity-100"}`}
                style={{ gridTemplateColumns: `${LABEL_W}px repeat(3, minmax(220px, 1fr))` }}>
                <div className="py-4 pr-4">
                  <button onClick={() => setFoco(activo ? null : i)} aria-pressed={activo}
                    className="group flex w-full items-start gap-2.5 rounded-md p-1 text-left transition-colors hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
                    <span className="mt-[5px] h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c }} />
                    <span className="min-w-0">
                      <span className={`block text-[13px] leading-tight ${activo ? "font-bold text-[var(--gob-ink)]" : "font-semibold text-[var(--gob-charcoal)]"}`}>
                        {p.nombre || `Pilar ${i + 1}`}
                      </span>
                      <span className="mt-0.5 block text-[10px] text-[var(--gob-stone)] opacity-0 transition-opacity group-hover:opacity-100 motion-reduce:transition-none">
                        {activo ? "ver todos" : "aislar"}
                      </span>
                    </span>
                  </button>
                </div>

                {ANIO_KEYS.map(yk => {
                  const items = p.milestones?.[yk] ?? []
                  const fase = p.fases?.[yk]?.titulo
                  return (
                    <div key={yk} className="flex flex-col gap-1.5 border-l border-[var(--gob-rule)] px-4 py-4"
                      style={{ background: activo ? `${c}08` : undefined }}>
                      {fase && (
                        <p className="text-[9px] font-bold uppercase leading-tight tracking-[0.14em]" style={{ color: c }}>{fase}</p>
                      )}
                      {items.length === 0 ? (
                        <span className="mt-1 block h-px w-8 rounded-full" style={{ background: `${c}40` }} />
                      ) : items.map((ms, mi) => (
                        <div key={mi} tabIndex={0}
                          className="rounded-md px-2.5 py-1.5 text-[11px] leading-snug transition-transform duration-150 hover:-translate-y-px hover:shadow-[0_2px_10px_rgba(11,14,20,0.10)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)] motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                          style={{ background: `${c}14`, color: c }}>
                          {ms}
                        </div>
                      ))}
                    </div>
                  )
                })}
              </div>
            )
          })}
          {pilares.length === 0 && (
            <p className="border-t border-[var(--gob-rule)] py-6 text-xs italic text-[var(--gob-stone)]">Sin pilares aún.</p>
          )}
        </div>
      </div>
      <p className="mt-3 text-xs text-[var(--gob-stone)]">
        Haz clic en un pilar para aislar su fila. La línea punteada marca dónde estás hoy.
      </p>
    </div>
  )
}
