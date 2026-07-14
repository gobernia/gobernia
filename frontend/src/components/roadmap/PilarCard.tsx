"use client"

import { useState } from "react"
import { Pilar, KpiPilar, ResultadoEsperado, Fase } from "@/lib/roadmap"
import EditControls from "./EditControls"
import { KpiTrayecto } from "./MetaTrayecto"
import {
  ANIO_KEYS, KPI_SLOTS, RESULTADO_SLOTS, emptyKpi, emptyResultado,
  joinLines, padSlots, splitLines,
} from "./shared"

type DraftPilar = {
  nombre: string; descripcion: string; anio1: string; anio2: string; anio3: string
  objetivo: string; estrategias: string
  kpis: KpiPilar[]; resultados: ResultadoEsperado[]
  fase1: string; fase2: string; fase3: string
}

const draftDe = (p: Pilar): DraftPilar => ({
  nombre: p.nombre, descripcion: p.descripcion,
  anio1: joinLines(p.milestones?.anio1), anio2: joinLines(p.milestones?.anio2), anio3: joinLines(p.milestones?.anio3),
  objetivo: p.objetivo ?? "", estrategias: joinLines(p.estrategias),
  kpis: padSlots(p.kpis, KPI_SLOTS, emptyKpi),
  resultados: padSlots(p.resultados_esperados, RESULTADO_SLOTS, emptyResultado),
  fase1: p.fases?.anio1?.titulo ?? "", fase2: p.fases?.anio2?.titulo ?? "", fase3: p.fases?.anio3?.titulo ?? "",
})

const pilarDe = (d: DraftPilar): Pilar => {
  const fases: Fase = {}
  const titulos = [d.fase1, d.fase2, d.fase3]
  ANIO_KEYS.forEach((yk, yi) => {
    const t = titulos[yi].trim()
    if (t) fases[yk] = { titulo: t }
  })
  return {
    nombre: d.nombre, descripcion: d.descripcion,
    milestones: { anio1: splitLines(d.anio1), anio2: splitLines(d.anio2), anio3: splitLines(d.anio3) },
    objetivo: d.objetivo.trim(),
    estrategias: splitLines(d.estrategias),
    kpis: d.kpis.map(k => ({ label: k.label.trim(), actual: k.actual.trim(), meta: k.meta.trim() })).filter(k => k.label),
    resultados_esperados: d.resultados
      .map(r => ({ titulo: r.titulo.trim(), descripcion: r.descripcion.trim() }))
      .filter(r => r.titulo || r.descripcion),
    fases,
  }
}

const inputCls = "w-full rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none"
const areaCls = `${inputCls} resize-none`
const kickerCls = "text-[10px] font-bold tracking-[0.18em] uppercase text-[var(--gob-stone)]"

/** Un pilar del plan: acento de color, objetivo, estrategias, KPIs (hoy → meta) y resultados. */
export default function PilarCard({ pilar, indice, color, editing, saving, validado, onEdit, onCancel, onSave }: {
  pilar: Pilar
  indice: number
  color: string
  editing: boolean
  saving: boolean
  validado: boolean
  onEdit: () => void
  onCancel: () => void
  onSave: (p: Pilar) => void
}) {
  const [draft, setDraft] = useState<DraftPilar>(() => draftDe(pilar))

  const abrir = () => { setDraft(draftDe(pilar)); onEdit() }
  const guardar = () => onSave(pilarDe(draft))
  const setKpi = (i: number, patch: Partial<KpiPilar>) =>
    setDraft(d => ({ ...d, kpis: d.kpis.map((k, j) => j === i ? { ...k, ...patch } : k) }))
  const setResultado = (i: number, patch: Partial<ResultadoEsperado>) =>
    setDraft(d => ({ ...d, resultados: d.resultados.map((r, j) => j === i ? { ...r, ...patch } : r) }))

  const estrategias = pilar.estrategias ?? []
  const kpis = (pilar.kpis ?? []).filter(k => k.label)
  const resultados = (pilar.resultados_esperados ?? []).filter(r => r.titulo || r.descripcion)
  const sinContenido = !pilar.descripcion && !pilar.objetivo && estrategias.length === 0 &&
    kpis.length === 0 && resultados.length === 0

  return (
    <article className="flex flex-col rounded-2xl border border-[var(--gob-rule)] bg-white p-5">
      <span className="mb-4 block h-1 w-12 rounded-full" style={{ background: color }} />

      <div className="mb-4 flex items-start justify-between gap-3">
        {editing ? (
          <input value={draft.nombre} onChange={e => setDraft(d => ({ ...d, nombre: e.target.value }))}
            aria-label="Nombre del pilar"
            className="flex-1 rounded-lg border-2 border-[var(--gob-rule)]/60 px-3 py-1.5 text-base font-bold focus:border-[var(--gob-navy)] focus:outline-none" />
        ) : (
          <div className="min-w-0">
            <p className={kickerCls} style={{ color }}>Pilar {indice + 1}</p>
            <h3 className="text-lg font-bold leading-tight tracking-tight text-[var(--gob-ink)]">
              {pilar.nombre || `Pilar ${indice + 1}`}
            </h3>
          </div>
        )}
        <EditControls editing={editing} onEdit={abrir} onSave={guardar} onCancel={onCancel} saving={saving} hide={validado} />
      </div>

      {editing ? (
        <div className="space-y-4">
          <textarea value={draft.descripcion} onChange={e => setDraft(d => ({ ...d, descripcion: e.target.value }))} rows={2}
            placeholder="Descripción del pilar" aria-label="Descripción" className={areaCls} />

          <div>
            <p className={`${kickerCls} mb-1`}>Objetivo</p>
            <textarea value={draft.objetivo} onChange={e => setDraft(d => ({ ...d, objetivo: e.target.value }))} rows={2}
              placeholder="El objetivo estratégico de este pilar" aria-label="Objetivo" className={areaCls} />
          </div>

          <div>
            <p className={`${kickerCls} mb-1`}>Estrategias</p>
            <textarea value={draft.estrategias} onChange={e => setDraft(d => ({ ...d, estrategias: e.target.value }))} rows={4}
              placeholder="Una estrategia por línea" aria-label="Estrategias" className={areaCls} />
          </div>

          <div className="space-y-2">
            <p className={kickerCls}>KPIs</p>
            {draft.kpis.map((k, ki) => (
              <div key={ki} className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <input value={k.label} onChange={e => setKpi(ki, { label: e.target.value })} placeholder="Indicador" aria-label="Indicador" className={inputCls} />
                <input value={k.actual} onChange={e => setKpi(ki, { actual: e.target.value })} placeholder="Hoy" aria-label="Valor de hoy" className={inputCls} />
                <input value={k.meta} onChange={e => setKpi(ki, { meta: e.target.value })} placeholder="Meta" aria-label="Meta"
                  className="w-full rounded-lg border-2 border-[var(--gob-navy)]/30 px-3 py-2 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <p className={kickerCls}>Resultados esperados</p>
            {draft.resultados.map((r, ri) => (
              <div key={ri} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr]">
                <input value={r.titulo} onChange={e => setResultado(ri, { titulo: e.target.value })}
                  placeholder="Título (ej. ↑ Margen bruto)" aria-label="Título del resultado" className={inputCls} />
                <input value={r.descripcion} onChange={e => setResultado(ri, { descripcion: e.target.value })}
                  placeholder="Descripción" aria-label="Descripción del resultado" className={inputCls} />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {ANIO_KEYS.map((yk, yi) => {
              const faseKey = (["fase1", "fase2", "fase3"] as const)[yi]
              return (
                <div key={yk} className="space-y-1.5">
                  <p className={kickerCls}>Año {yi + 1}</p>
                  <input value={draft[faseKey]} onChange={e => setDraft(d => ({ ...d, [faseKey]: e.target.value }))}
                    placeholder="Título de la fase" aria-label={`Fase del año ${yi + 1}`}
                    className="w-full rounded-lg border-2 border-[var(--gob-rule)]/60 px-2.5 py-2 text-xs focus:border-[var(--gob-navy)] focus:outline-none" />
                  <textarea value={draft[yk]} onChange={e => setDraft(d => ({ ...d, [yk]: e.target.value }))} rows={4}
                    placeholder="Un milestone por línea" aria-label={`Milestones del año ${yi + 1}`}
                    className="w-full resize-none rounded-lg border-2 border-[var(--gob-rule)]/60 px-2.5 py-2 text-xs focus:border-[var(--gob-navy)] focus:outline-none" />
                </div>
              )
            })}
          </div>
        </div>
      ) : sinContenido ? (
        <p className="text-xs italic text-[var(--gob-stone)]">Sus hitos están en el mapa de ejecución.</p>
      ) : (
        <div className="space-y-5">
          {pilar.descripcion && <p className="text-sm leading-relaxed text-[var(--gob-muted)]">{pilar.descripcion}</p>}

          {pilar.objetivo && (
            <div className="space-y-1 rounded-xl px-4 py-3" style={{ background: `${color}0d`, borderLeft: `3px solid ${color}` }}>
              <p className={kickerCls} style={{ color }}>Objetivo</p>
              <p className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{pilar.objetivo}</p>
            </div>
          )}

          {estrategias.length > 0 && (
            <div className="space-y-2">
              <p className={kickerCls}>Estrategias</p>
              <ul className="space-y-1.5">
                {estrategias.map((s, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
                    <span className="text-sm leading-relaxed text-[var(--gob-charcoal)]">{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {kpis.length > 0 && (
            <div className="space-y-1">
              <p className={kickerCls}>KPIs · hoy → meta</p>
              <ul>
                {kpis.map((k, i) => <KpiTrayecto key={i} kpi={k} color={color} />)}
              </ul>
            </div>
          )}

          {resultados.length > 0 && (
            <div className="space-y-2">
              <p className={kickerCls}>Resultados esperados</p>
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                {resultados.map((r, i) => (
                  <div key={i} className="space-y-1 rounded-xl p-3" style={{ background: `${color}0d` }}>
                    {r.titulo && <p className="text-xs font-bold leading-snug" style={{ color }}>{r.titulo}</p>}
                    {r.descripcion && <p className="text-[11px] leading-snug text-[var(--gob-muted)]">{r.descripcion}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
