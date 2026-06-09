"use client"

import { useEffect, useState } from "react"
import { MinutaOut, MinutaTema, getMinuta, sesionarConsejo, cerrarDecision } from "@/lib/minuta"

export default function MinutaView() {
  const [data, setData] = useState<MinutaOut | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    getMinuta().then(d => { if (active) setData(d) }).catch(() => { if (active) setData(null) })
    return () => { active = false }
  }, [])

  const onSesionar = async () => {
    setBusy(true)
    try { setData(await sesionarConsejo()) } catch { /* noop */ } finally { setBusy(false) }
  }

  const onDecidir = async (temaId: number, decision: "A" | "B" | "aplazar") => {
    setBusy(true)
    try { setData(await cerrarDecision(temaId, decision)) } catch { /* noop */ } finally { setBusy(false) }
  }

  if (data === null) return <p className="text-sm text-gray-400">Cargando minuta…</p>

  if (!data.generada) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-6 text-center">
        <p className="text-sm text-gray-500 mb-4">Aún no has sesionado al consejo este mes.</p>
        <button
          type="button"
          onClick={onSesionar}
          disabled={busy}
          className="px-4 py-2 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium disabled:opacity-50"
        >
          {busy ? "El consejo está sesionando…" : "Sesionar el Consejo"}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {data.carta && (
        <p className="text-sm text-gray-600 italic border-l-2 border-[var(--gob-navy)] pl-3">{data.carta}</p>
      )}
      {data.temas.map(t => <TemaCard key={t.id} tema={t} busy={busy} onDecidir={onDecidir} />)}
      <button
        type="button"
        onClick={onSesionar}
        disabled={busy}
        className="text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50"
      >
        {busy ? "Sesionando…" : "Volver a sesionar"}
      </button>
    </div>
  )
}

function TemaCard({ tema, busy, onDecidir }: {
  tema: MinutaTema
  busy: boolean
  onDecidir: (id: number, d: "A" | "B" | "aplazar") => void
}) {
  const tomada = tema.decision.decision_tomada
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4">
      <h4 className="text-sm font-bold text-black">{tema.titulo}</h4>
      <p className="text-xs text-gray-500 mt-1">{tema.sintesis}</p>
      <p className="text-sm text-black font-medium mt-3">{tema.decision.pregunta}</p>

      {tomada ? (
        <div className="mt-2 text-xs">
          <p className="text-gray-700">
            Decisión: <span className="font-medium">
              {tomada === "A" ? tema.decision.opcion_a : tomada === "B" ? tema.decision.opcion_b : "Aplazado"}
            </span>
          </p>
          {tema.compromiso && (
            <p className="text-gray-500 mt-1">
              Compromiso: {tema.compromiso.descripcion} · vence {tema.compromiso.fecha}
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mt-3">
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "A")}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-50">
            A · {tema.decision.opcion_a}
          </button>
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "B")}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-50">
            B · {tema.decision.opcion_b}
          </button>
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "aplazar")}
            className="px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:underline disabled:opacity-50">
            Aplazar
          </button>
        </div>
      )}
    </div>
  )
}
