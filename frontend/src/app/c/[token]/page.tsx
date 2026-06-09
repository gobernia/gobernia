"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { CompromisoPublic, getCompromisoPublico, reportarAvance } from "@/lib/pm"

export default function CompromisoPublicoPage() {
  const params = useParams<{ token: string }>()
  const token = params.token
  const [data, setData] = useState<CompromisoPublic | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [pct, setPct] = useState(0)
  const [nota, setNota] = useState("")
  const [evidencia, setEvidencia] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    getCompromisoPublico(token)
      .then(d => { if (active) setData(d) })
      .catch(() => { if (active) setNotFound(true) })
    return () => { active = false }
  }, [token])

  const enviar = async (completar: boolean) => {
    setBusy(true)
    try {
      const d = await reportarAvance(token, {
        pct: completar ? 100 : pct,
        nota: nota || undefined,
        evidencia_url: evidencia || undefined,
      })
      setData(d)
      if (completar) setPct(100)
    } catch { /* noop */ } finally { setBusy(false) }
  }

  if (notFound) {
    return <main className="min-h-screen flex items-center justify-center p-6 text-gray-500">Compromiso no encontrado.</main>
  }
  if (!data) {
    return <main className="min-h-screen flex items-center justify-center p-6 text-gray-400">Cargando…</main>
  }

  const completado = data.status === "completado"

  return (
    <main className="min-h-screen bg-[var(--gob-bone)] p-6 flex justify-center">
      <div className="w-full max-w-lg space-y-4">
        <div className="rounded-2xl border border-gray-100 bg-white p-5">
          <p className="text-xs uppercase tracking-wide text-gray-400 mb-1">Compromiso del consejo</p>
          <h1 className="text-lg font-bold text-black">{data.descripcion}</h1>
          {data.fecha_compromiso && (
            <p className="text-xs text-gray-500 mt-1">Vence: {data.fecha_compromiso}</p>
          )}
          <p className="text-xs text-gray-500 mt-1">Estado: {data.status}</p>
        </div>

        {data.avances.length > 0 && (
          <div className="rounded-2xl border border-gray-100 bg-white p-5">
            <p className="text-sm font-bold text-black mb-2">Avances reportados</p>
            {data.avances.map((a, i) => (
              <p key={i} className="text-xs text-gray-500">{a.fecha} · {a.pct}% {a.nota ? `· ${a.nota}` : ""}</p>
            ))}
          </div>
        )}

        {!completado && (
          <div className="rounded-2xl border border-gray-100 bg-white p-5 space-y-3">
            <p className="text-sm font-bold text-black">Reportar avance</p>
            <label className="block text-xs text-gray-500">
              % de avance
              <input type="number" min={0} max={100} value={pct}
                onChange={e => setPct(Number(e.target.value))}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            </label>
            <label className="block text-xs text-gray-500">
              Nota
              <textarea value={nota} onChange={e => setNota(e.target.value)}
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" rows={2} />
            </label>
            <label className="block text-xs text-gray-500">
              Link de evidencia (opcional)
              <input type="url" value={evidencia} onChange={e => setEvidencia(e.target.value)}
                placeholder="https://…"
                className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            </label>
            <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={() => enviar(false)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-sm disabled:opacity-50">
                {busy ? "Enviando…" : "Reportar avance"}
              </button>
              <button type="button" disabled={busy} onClick={() => enviar(true)}
                className="px-4 py-2 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium disabled:opacity-50">
                Marcar completado
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
