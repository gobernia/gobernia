"use client"

import { useState } from "react"
import { Meta3a } from "@/lib/roadmap"
import DocSection from "./DocSection"
import EditControls from "./EditControls"
import { MetaTrayecto } from "./MetaTrayecto"
import { SeccionProps } from "./shared"

const inputCls = "w-full rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none"

/**
 * SIGNATURE — Las metas como trayectos: hoy → meta.
 * Sin target, el trayecto va punteado y el destino es un botón para fijarlo.
 */
export default function SeccionMetas({ roadmap, editing, setEditing, saving, validado, onSave }: SeccionProps) {
  const metas = roadmap.metas_3anios ?? []
  const [draft, setDraft] = useState<Meta3a[]>(() => metas.map(m => ({ ...m })))
  const enEdicion = editing === "metas"
  const porDefinir = metas.filter(m => !m.target?.trim()).length

  const abrir = () => { setDraft(metas.map(m => ({ ...m }))); setEditing("metas") }
  const patch = (i: number, p: Partial<Meta3a>) => setDraft(d => d.map((m, j) => j === i ? { ...m, ...p } : m))
  const fijarTarget = (i: number, valor: string) =>
    onSave({ ...roadmap, metas_3anios: metas.map((m, j) => j === i ? { ...m, target: valor } : m) })

  return (
    <DocSection id="metas" orden="02 · El compromiso" titulo="Metas a 3 años"
      nota="Dónde estás hoy y a dónde te comprometes a llegar. El número de la meta lo fijas tú, no la IA."
      actions={<EditControls editing={enEdicion} onEdit={abrir} onSave={() => onSave({ ...roadmap, metas_3anios: draft })}
        onCancel={() => setEditing(null)} saving={saving} hide={validado} />}>

      {enEdicion ? (
        <div className="space-y-4">
          {draft.map((m, i) => (
            <div key={i} className="space-y-2 rounded-xl border border-[var(--gob-rule)] p-3.5">
              <textarea value={m.meta} onChange={e => patch(i, { meta: e.target.value })} rows={2} placeholder="Meta"
                aria-label="Meta" className={`${inputCls} resize-none`} />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <input value={m.kpi ?? ""} onChange={e => patch(i, { kpi: e.target.value })} placeholder="KPI" aria-label="KPI" className={inputCls} />
                <input value={m.valor_actual ?? ""} onChange={e => patch(i, { valor_actual: e.target.value })} placeholder="Valor actual" aria-label="Valor actual" className={inputCls} />
                <input value={m.target} onChange={e => patch(i, { target: e.target.value })} placeholder="Meta objetivo (target)" aria-label="Meta objetivo"
                  className="w-full rounded-lg border-2 border-[var(--gob-navy)]/30 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
              </div>
            </div>
          ))}
          {draft.length === 0 && <p className="text-xs italic text-[var(--gob-stone)]">Sin metas aún.</p>}
        </div>
      ) : metas.length > 0 ? (
        <>
          <ul className="border-b border-[var(--gob-rule)]">
            {metas.map((m, i) => (
              <MetaTrayecto key={i} meta={m} indice={i} editable={!validado} saving={saving}
                onSetTarget={v => fijarTarget(i, v)} />
            ))}
          </ul>
          {porDefinir > 0 && (
            <p className="mt-3 text-xs text-[var(--gob-muted)]">
              {porDefinir === 1
                ? "1 meta sigue sin número. Haz clic en «Define la meta» para fijarlo."
                : `${porDefinir} metas siguen sin número. Haz clic en «Define la meta» para fijarlos.`}
            </p>
          )}
        </>
      ) : <p className="text-xs italic text-[var(--gob-stone)]">Sin metas aún.</p>}
    </DocSection>
  )
}
