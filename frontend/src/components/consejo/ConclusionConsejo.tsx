"use client"

/**
 * La voz del Consejo.
 *
 * No son cuatro opiniones: es UNA conclusión. Por eso lidera la pantalla con peso tipográfico
 * propio, seguida del avance contra el Roadmap, los riesgos con su semáforo y —el entregable—
 * los acuerdos, que el dueño puede asignar aquí mismo.
 */
import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { getRoadmap } from "@/lib/roadmap"
import AcuerdoRow from "./AcuerdoRow"
import { ALERT_COLOR, ALERT_LABEL, ALERT_ORDER, Acuerdo, Conclusion, toRiesgo } from "./shared"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

/** Un texto de varios párrafos se lee como varios párrafos. */
function Parrafos({ texto, className }: { texto: string; className: string }) {
  return (
    <>
      {texto.split("\n").map(l => l.trim()).filter(Boolean).map((linea, i) => (
        <p key={i} className={className}>{linea}</p>
      ))}
    </>
  )
}

export default function ConclusionConsejo({
  conclusion,
  onAcuerdoActualizado,
}: {
  conclusion: Conclusion
  onAcuerdoActualizado: (id: string, patch: Partial<Acuerdo>) => void
}) {
  // Los pilares del Roadmap dan el color de cada chip: el acuerdo y el plan hablan igual.
  const [pilares, setPilares] = useState<string[]>([])
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true
    getRoadmap()
      .then(r => {
        if (!aliveRef.current) return
         
        setPilares((r.pilares ?? []).map(p => p.nombre ?? ""))
      })
      .catch(() => {})
    return () => { aliveRef.current = false }
  }, [])

  const riesgos = (conclusion.riesgos ?? [])
    .map(toRiesgo)
    .filter(r => r.texto)
    .sort((a, b) => ALERT_ORDER[a.nivel] - ALERT_ORDER[b.nivel])

  const acuerdos = conclusion.acuerdos ?? []
  const sinDueno = acuerdos.filter(a => !(a.responsable_nombre ?? "").trim()).length

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
      className="space-y-10"
    >
      {/* ── La conclusión: la pieza principal de la pantalla ── */}
      <div className="border-t-2 border-[var(--gob-navy)] pt-6">
        <p className="text-[10px] font-medium tracking-[0.18em] uppercase text-[var(--gob-navy)]">
          La conclusión del Consejo
        </p>
        <div className="mt-4 space-y-4 max-w-[64ch]">
          <Parrafos
            texto={conclusion.conclusion || "El Consejo no emitió conclusión en esta sesión."}
            className="text-xl sm:text-2xl font-medium leading-[1.45] tracking-[-0.01em] text-[var(--gob-ink)]"
          />
        </div>
      </div>

      {/* ── Avance del Roadmap ── */}
      {conclusion.avance_roadmap && (
        <div className="rounded-2xl bg-[var(--gob-paper)] border border-[var(--gob-rule)] p-6 sm:p-7">
          <p className="text-[10px] font-medium tracking-[0.18em] uppercase text-[var(--gob-muted)]">
            Avance del Roadmap
          </p>
          <div className="mt-3 space-y-3 max-w-[70ch]">
            <Parrafos
              texto={conclusion.avance_roadmap}
              className="text-sm leading-relaxed text-[var(--gob-charcoal)]"
            />
          </div>
        </div>
      )}

      {/* ── Riesgos ── */}
      {riesgos.length > 0 && (
        <div className="space-y-3">
          <p className="text-[10px] font-medium tracking-[0.18em] uppercase text-[var(--gob-muted)]">
            Riesgos que el Consejo pone sobre la mesa
          </p>
          <ul className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {riesgos.map((r, i) => (
              <li
                key={i}
                className="border-l-2 rounded-r-lg bg-white pl-4 pr-4 py-3"
                style={{ borderLeftColor: ALERT_COLOR[r.nivel] }}
              >
                <span className="sr-only">{ALERT_LABEL[r.nivel]}: </span>
                <p
                  className="text-sm font-medium leading-relaxed"
                  style={{ color: ALERT_COLOR[r.nivel] }}
                >
                  {r.texto}
                </p>
                {r.fuente && (
                  <p className="mt-1 text-[10px] italic text-[var(--gob-stone)]">
                    Fuente: {r.fuente}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Los acuerdos: el entregable de la sesión ── */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h3 className="text-lg font-bold tracking-tight text-[var(--gob-ink)]">
              Acuerdos del Consejo
            </h3>
            <p className="mt-1 text-xs text-[var(--gob-muted)] max-w-[60ch] leading-relaxed">
              Lo que la empresa se compromete a hacer, y a qué pilar del Roadmap sirve. Ponle
              nombre y fecha a cada acuerdo: sin dueño, no se ejecuta.
            </p>
          </div>
          {sinDueno > 0 && (
            <span
              className="text-[11px] font-medium px-2.5 py-1 rounded-md"
              style={{ color: "#b45309", backgroundColor: "#b4530914" }}
            >
              {sinDueno === 1
                ? "1 acuerdo sin responsable"
                : `${sinDueno} acuerdos sin responsable`}
            </span>
          )}
        </div>

        {acuerdos.length > 0 ? (
          <ul className="rounded-2xl border border-[var(--gob-rule)] px-6 py-5">
            {acuerdos.map(a => (
              <AcuerdoRow
                key={a.id}
                acuerdo={a}
                pilaresDelRoadmap={pilares}
                onActualizado={onAcuerdoActualizado}
              />
            ))}
          </ul>
        ) : (
          <p className="rounded-2xl border border-dashed border-[var(--gob-rule)] px-6 py-8 text-center text-xs italic text-[var(--gob-stone)]">
            El Consejo no dejó acuerdos en esta sesión.
          </p>
        )}
      </div>
    </motion.section>
  )
}
