"use client"

import { useState } from "react"
import { TemasPorAnio } from "@/lib/roadmap"
import DocSection from "./DocSection"
import EditControls from "./EditControls"
import MapaEjecucion from "./MapaEjecucion"
import { ANIO_KEYS, SeccionProps, joinLines, splitLines } from "./shared"

const PLACEHOLDER_TEMAS = ["Ordenar la casa", "Expandir el negocio", "Consolidar el liderazgo"]

/** El mapa de ejecución (pilares × años) más los lemas de cada año y los habilitadores transversales. */
export default function SeccionMapa({ roadmap, editing, setEditing, saving, validado, onSave }: SeccionProps) {
  const temas = roadmap.temas_por_anio ?? {}
  const enablers = roadmap.key_enablers ?? []
  const [draftTemas, setDraftTemas] = useState<TemasPorAnio>(() => ({ ...temas }))
  const [draftEnablers, setDraftEnablers] = useState(() => joinLines(roadmap.key_enablers))
  const editTemas = editing === "temas"
  const editEnablers = editing === "enablers"

  const abrirTemas = () => { setDraftTemas({ ...(roadmap.temas_por_anio ?? {}) }); setEditing("temas") }
  const abrirEnablers = () => { setDraftEnablers(joinLines(roadmap.key_enablers)); setEditing("enablers") }

  const guardarTemas = () => {
    const t: TemasPorAnio = {}
    for (const yk of ANIO_KEYS) {
      const v = (draftTemas[yk] ?? "").trim()
      if (v) t[yk] = v
    }
    onSave({ ...roadmap, temas_por_anio: t })
  }

  return (
    <DocSection id="mapa" orden="04 · La ejecución" titulo="Mapa de ejecución"
      nota="Qué mueve cada pilar, año por año. Es el plan puesto en el tiempo."
      actions={<EditControls editing={editTemas} onEdit={abrirTemas} onSave={guardarTemas}
        onCancel={() => setEditing(null)} saving={saving} hide={validado} />}>

      {editTemas && (
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {ANIO_KEYS.map((yk, yi) => (
            <div key={yk} className="space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--gob-stone)]">Lema del año {yi + 1}</p>
              <input value={draftTemas[yk] ?? ""} onChange={e => setDraftTemas(d => ({ ...d, [yk]: e.target.value }))}
                placeholder={PLACEHOLDER_TEMAS[yi]} aria-label={`Lema del año ${yi + 1}`}
                className="w-full rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
            </div>
          ))}
        </div>
      )}

      <MapaEjecucion pilares={roadmap.pilares ?? []} temas={temas} anioObjetivo={roadmap.anio_objetivo} />

      {/* Habilitadores clave: lo transversal que sostiene los tres años. */}
      {(enablers.length > 0 || !validado) && (
        <div className="mt-8 rounded-2xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] p-5 sm:p-6">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-base font-bold tracking-tight text-[var(--gob-ink)]">Habilitadores clave</h3>
              <p className="mt-0.5 text-xs text-[var(--gob-muted)]">Lo transversal que sostiene los tres años.</p>
            </div>
            <EditControls editing={editEnablers} onEdit={abrirEnablers}
              onSave={() => onSave({ ...roadmap, key_enablers: splitLines(draftEnablers) })}
              onCancel={() => setEditing(null)} saving={saving} hide={validado} />
          </div>
          {editEnablers ? (
            <textarea value={draftEnablers} onChange={e => setDraftEnablers(e.target.value)} rows={4}
              placeholder="Un habilitador por línea (talento, tecnología, capital, gobernanza…)"
              aria-label="Habilitadores clave"
              className="w-full resize-none rounded-lg border-2 border-[var(--gob-rule)]/60 bg-white px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
          ) : enablers.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {enablers.map((k, i) => (
                <span key={i} className="rounded-full border border-[var(--gob-navy)]/15 bg-[var(--gob-navy)]/[0.06] px-3 py-1.5 text-xs font-medium text-[var(--gob-navy)]">{k}</span>
              ))}
            </div>
          ) : <p className="text-xs italic text-[var(--gob-stone)]">Sin habilitadores aún.</p>}
        </div>
      )}
    </DocSection>
  )
}
