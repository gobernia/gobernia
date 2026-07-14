"use client"

import { useState } from "react"
import DocSection from "./DocSection"
import EditControls from "./EditControls"
import { SeccionProps } from "./shared"

const areaCls = "w-full resize-none rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none"
const kickerCls = "text-[10px] font-bold tracking-[0.18em] uppercase text-[var(--gob-stone)]"

function Parrafos({ texto }: { texto: string }) {
  return (
    <div className="space-y-2">
      {texto.split("\n").filter(p => p.trim()).map((p, i) => (
        <p key={i} className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{p.trim()}</p>
      ))}
    </div>
  )
}

function Conclusion({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="mt-4 space-y-1 rounded-xl border-l-4 border-[var(--gob-navy)] bg-[var(--gob-navy)]/[0.04] px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--gob-navy)]">{titulo}</p>
      <p className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{texto}</p>
    </div>
  )
}

/** El respaldo del plan: diagnóstico interno (FODA) y entorno. Va al final: es soporte, no titular. */
export default function SeccionContexto({ roadmap, editing, setEditing, saving, validado, onSave }: SeccionProps) {
  const [foda, setFoda] = useState({ texto: roadmap.resumen_foda ?? "", conclusion: roadmap.conclusion_diagnostico ?? "" })
  const [entorno, setEntorno] = useState({ texto: roadmap.resumen_entorno ?? "", conclusion: roadmap.conclusion_entorno ?? "" })
  const editFoda = editing === "foda"
  const editEntorno = editing === "entorno"

  const abrirFoda = () => {
    setFoda({ texto: roadmap.resumen_foda ?? "", conclusion: roadmap.conclusion_diagnostico ?? "" })
    setEditing("foda")
  }
  const abrirEntorno = () => {
    setEntorno({ texto: roadmap.resumen_entorno ?? "", conclusion: roadmap.conclusion_entorno ?? "" })
    setEditing("entorno")
  }

  return (
    <DocSection id="contexto" orden="05 · El respaldo" titulo="Contexto"
      nota="De dónde sale el plan: el diagnóstico interno y el entorno en el que compite la empresa.">
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Diagnóstico interno (FODA) */}
        <div className="rounded-2xl border border-[var(--gob-rule)] bg-white p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-base font-bold tracking-tight text-[var(--gob-ink)]">Diagnóstico interno · FODA</h3>
            <EditControls editing={editFoda} onEdit={abrirFoda}
              onSave={() => onSave({ ...roadmap, resumen_foda: foda.texto, conclusion_diagnostico: foda.conclusion.trim() })}
              onCancel={() => setEditing(null)} saving={saving} hide={validado} />
          </div>
          {editFoda ? (
            <div className="space-y-3">
              <textarea value={foda.texto} onChange={e => setFoda(d => ({ ...d, texto: e.target.value }))} rows={6}
                aria-label="Resumen FODA" className={areaCls} />
              <div>
                <p className={`${kickerCls} mb-1`}>Conclusión del diagnóstico</p>
                <textarea value={foda.conclusion} onChange={e => setFoda(d => ({ ...d, conclusion: e.target.value }))} rows={3}
                  placeholder="La lectura de fondo: qué nos dice el diagnóstico."
                  aria-label="Conclusión del diagnóstico" className={areaCls} />
              </div>
            </div>
          ) : (
            <>
              {roadmap.resumen_foda
                ? <Parrafos texto={roadmap.resumen_foda} />
                : <p className="text-xs italic text-[var(--gob-stone)]">Sin contenido aún.</p>}
              {roadmap.conclusion_diagnostico && (
                <Conclusion titulo="Conclusión del diagnóstico" texto={roadmap.conclusion_diagnostico} />
              )}
            </>
          )}
        </div>

        {/* Entorno */}
        <div className="rounded-2xl border border-[var(--gob-rule)] bg-white p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-base font-bold tracking-tight text-[var(--gob-ink)]">Entorno</h3>
            <EditControls editing={editEntorno} onEdit={abrirEntorno}
              onSave={() => onSave({ ...roadmap, resumen_entorno: entorno.texto, conclusion_entorno: entorno.conclusion.trim() })}
              onCancel={() => setEditing(null)} saving={saving} hide={validado} />
          </div>
          {editEntorno ? (
            <div className="space-y-3">
              <textarea value={entorno.texto} onChange={e => setEntorno(d => ({ ...d, texto: e.target.value }))} rows={6}
                aria-label="Resumen del entorno" className={areaCls} />
              <div>
                <p className={`${kickerCls} mb-1`}>Conclusión del entorno</p>
                <textarea value={entorno.conclusion} onChange={e => setEntorno(d => ({ ...d, conclusion: e.target.value }))} rows={3}
                  placeholder="Qué significa el entorno para la empresa."
                  aria-label="Conclusión del entorno" className={areaCls} />
              </div>
            </div>
          ) : (
            <>
              {roadmap.resumen_entorno
                ? <Parrafos texto={roadmap.resumen_entorno} />
                : <p className="text-xs italic text-[var(--gob-stone)]">Sin contenido aún.</p>}
              {roadmap.conclusion_entorno && (
                <Conclusion titulo="Conclusión del entorno" texto={roadmap.conclusion_entorno} />
              )}
            </>
          )}
        </div>
      </div>
    </DocSection>
  )
}
