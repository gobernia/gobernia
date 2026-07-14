"use client"

import { useState } from "react"
import DocSection from "./DocSection"
import EditControls from "./EditControls"
import { SeccionProps, joinLines, splitLines } from "./shared"

const areaCls = "w-full resize-none rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none"
const kickerCls = "text-[10px] font-bold tracking-[0.18em] uppercase text-[var(--gob-stone)]"

/**
 * La tesis del documento: visión (a toda voz), misión y propuesta de valor,
 * más los objetivos estratégicos que se desprenden de ella.
 */
export default function SeccionApertura({ roadmap, editing, setEditing, saving, validado, onSave }: SeccionProps) {
  const [enc, setEnc] = useState({ vision: roadmap.vision, mision: roadmap.mision, propuesta_valor: roadmap.propuesta_valor })
  const [objs, setObjs] = useState(joinLines(roadmap.objetivos_estrategicos))
  const objetivos = roadmap.objetivos_estrategicos ?? []
  const editEnc = editing === "encabezado"
  const editObj = editing === "objetivos"

  const abrirEnc = () => {
    setEnc({ vision: roadmap.vision, mision: roadmap.mision, propuesta_valor: roadmap.propuesta_valor })
    setEditing("encabezado")
  }
  const abrirObj = () => { setObjs(joinLines(roadmap.objetivos_estrategicos)); setEditing("objetivos") }

  return (
    <DocSection id="vision" orden="01 · La tesis" titulo="Visión y propuesta"
      actions={<EditControls editing={editEnc} onEdit={abrirEnc} onSave={() => onSave({ ...roadmap, ...enc })}
        onCancel={() => setEditing(null)} saving={saving} hide={validado} />}>

      {editEnc ? (
        <div className="space-y-3 max-w-3xl">
          <div>
            <p className={`${kickerCls} mb-1`}>Visión</p>
            <textarea value={enc.vision} onChange={e => setEnc(d => ({ ...d, vision: e.target.value }))} rows={2} aria-label="Visión" className={areaCls} />
          </div>
          <div>
            <p className={`${kickerCls} mb-1`}>Misión</p>
            <textarea value={enc.mision} onChange={e => setEnc(d => ({ ...d, mision: e.target.value }))} rows={2} aria-label="Misión" className={areaCls} />
          </div>
          <div>
            <p className={`${kickerCls} mb-1`}>Propuesta de valor</p>
            <textarea value={enc.propuesta_valor} onChange={e => setEnc(d => ({ ...d, propuesta_valor: e.target.value }))} rows={2} aria-label="Propuesta de valor" className={areaCls} />
          </div>
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:gap-12">
          <div>
            {roadmap.vision ? (
              <>
                <p className={`${kickerCls} mb-2`}>Visión</p>
                <p className="text-2xl sm:text-[1.75rem] font-semibold leading-[1.25] tracking-tight text-balance text-[var(--gob-ink)]">
                  {roadmap.vision}
                </p>
              </>
            ) : (
              <p className="text-xs italic text-[var(--gob-stone)]">Sin visión aún.</p>
            )}
          </div>

          <div className="space-y-5 lg:border-l lg:border-[var(--gob-rule)] lg:pl-8">
            {roadmap.mision && (
              <div>
                <p className={`${kickerCls} mb-1`}>Misión</p>
                <p className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{roadmap.mision}</p>
              </div>
            )}
            {roadmap.propuesta_valor && (
              <div>
                <p className={`${kickerCls} mb-1`}>Propuesta de valor</p>
                <p className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{roadmap.propuesta_valor}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Objetivos estratégicos */}
      {(objetivos.length > 0 || !validado) && (
        <div className="mt-10 rounded-2xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-base font-bold tracking-tight text-[var(--gob-ink)]">Objetivos estratégicos</h3>
            <EditControls editing={editObj} onEdit={abrirObj}
              onSave={() => onSave({ ...roadmap, objetivos_estrategicos: splitLines(objs) })}
              onCancel={() => setEditing(null)} saving={saving} hide={validado} />
          </div>
          {editObj ? (
            <textarea value={objs} onChange={e => setObjs(e.target.value)} rows={5} placeholder="Un objetivo por línea"
              aria-label="Objetivos estratégicos" className={`${areaCls} bg-white`} />
          ) : objetivos.length > 0 ? (
            <ol className="grid gap-x-8 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
              {objetivos.map((o, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--gob-navy)]/[0.08] text-[11px] font-bold text-[var(--gob-navy)]">
                    {i + 1}
                  </span>
                  <span className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{o}</span>
                </li>
              ))}
            </ol>
          ) : <p className="text-xs italic text-[var(--gob-stone)]">Sin objetivos aún.</p>}
        </div>
      )}
    </DocSection>
  )
}
