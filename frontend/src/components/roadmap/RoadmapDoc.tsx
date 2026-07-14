"use client"

import { useState } from "react"
import { BadgeCheck, Loader2, Unlock } from "lucide-react"
import { Roadmap, Pilar } from "@/lib/roadmap"
import DocSection from "./DocSection"
import IndiceDoc from "./IndiceDoc"
import PilarCard from "./PilarCard"
import SeccionApertura from "./SeccionApertura"
import SeccionContexto from "./SeccionContexto"
import SeccionMapa from "./SeccionMapa"
import SeccionMetas from "./SeccionMetas"
import { DOC_SECCIONES, SeccionProps, pilarColor } from "./shared"

/** El expediente del consejo: índice a la izquierda, documento a la derecha. */
export default function RoadmapDoc({ roadmap, validado, validando, fechaValidacion, saving, onSave, onValidar, onReabrir }: {
  roadmap: Roadmap
  validado: boolean
  validando: boolean
  fechaValidacion: string | null
  saving: boolean
  /** Persiste el roadmap. Devuelve true si se guardó. */
  onSave: (next: Roadmap) => Promise<boolean>
  onValidar: () => void
  onReabrir: () => void
}) {
  const [editing, setEditing] = useState<string | null>(null)

  const commit = async (next: Roadmap) => {
    const ok = await onSave(next)
    if (ok) setEditing(null)
  }

  const comunes: Omit<SeccionProps, "roadmap"> = { editing, setEditing, saving, validado, onSave: commit }
  const pilares = roadmap.pilares ?? []

  const savePilar = (idx: number, p: Pilar) =>
    commit({ ...roadmap, pilares: pilares.map((x, i) => i === idx ? p : x) })

  return (
    <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-12 xl:gap-16">
      <div className="mb-8 lg:mb-0">
        <IndiceDoc ids={DOC_SECCIONES.map(s => s.id)} />
      </div>

      <div className="min-w-0 space-y-14">
        {/* Fase: revisión (borrador) o sellado (validado) */}
        {!validado ? (
          <div className="space-y-2 rounded-2xl border-2 border-dashed border-[var(--gob-navy)]/25 bg-[var(--gob-navy)]/[0.03] p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--gob-navy)]">Fase de revisión · borrador</p>
            <p className="max-w-3xl text-sm leading-relaxed text-[var(--gob-charcoal)]">
              Este es el <strong>borrador</strong> que preparó tu consejo. Revísalo y <strong>ajusta el contenido</strong> con
              el botón <strong>Editar</strong> de cada bloque. Las metas sin número las fijas tú: el consejo no las inventa.
            </p>
            <p className="max-w-3xl text-sm leading-relaxed text-[var(--gob-charcoal)]">
              Cuando estés conforme, pulsa <strong>Validar roadmap</strong>: queda sellado, en solo lectura,{" "}
              <strong>registrado para tu próxima sesión de consejo</strong> y guardado en tu Biblioteca.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-green-200 bg-green-50/60 p-5">
            <div className="min-w-0 space-y-1">
              <p className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-green-700">
                <BadgeCheck className="h-3.5 w-3.5" /> Validado{fechaValidacion ? ` · ${fechaValidacion}` : ""}
              </p>
              <p className="max-w-3xl text-sm leading-relaxed text-[var(--gob-charcoal)]">
                Tu roadmap está sellado y en solo lectura. Quedó <strong>registrado para tu próxima sesión de
                consejo</strong> y guardado en tu <strong>Biblioteca</strong>.
              </p>
            </div>
            <button onClick={onReabrir} disabled={validando}
              className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-[var(--gob-rule)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--gob-charcoal)] transition-colors hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {validando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
              Reabrir para editar
            </button>
          </div>
        )}

        <SeccionApertura roadmap={roadmap} {...comunes} />
        <SeccionMetas roadmap={roadmap} {...comunes} />

        <DocSection id="pilares" orden="03 · Las apuestas" titulo="Pilares estratégicos"
          nota="Los frentes en los que la empresa concentra su esfuerzo durante los tres años.">
          {pilares.length > 0 ? (
            <div className="grid gap-5 lg:grid-cols-2">
              {pilares.map((p, i) => (
                <PilarCard key={i} pilar={p} indice={i} color={pilarColor(i)}
                  editing={editing === `pilar-${i}`} saving={saving} validado={validado}
                  onEdit={() => setEditing(`pilar-${i}`)} onCancel={() => setEditing(null)}
                  onSave={p2 => savePilar(i, p2)} />
              ))}
            </div>
          ) : <p className="text-xs italic text-[var(--gob-stone)]">Sin pilares aún.</p>}
        </DocSection>

        <SeccionMapa roadmap={roadmap} {...comunes} />
        <SeccionContexto roadmap={roadmap} {...comunes} />

        {/* Cierre: validar el roadmap */}
        {!validado && (
          <div className="flex flex-col items-center gap-2 border-t border-[var(--gob-rule)] pt-10">
            <button onClick={onValidar} disabled={validando}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--gob-navy)] px-6 py-3 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {validando
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Validando…</>
                : <><BadgeCheck className="h-4 w-4" /> Validar roadmap</>}
            </button>
            <p className="max-w-md text-center text-xs leading-relaxed text-[var(--gob-muted)]">
              Al validar queda en solo lectura y se registra para tu próxima sesión de consejo.
              Podrás reabrirlo si necesitas cambiar algo.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
