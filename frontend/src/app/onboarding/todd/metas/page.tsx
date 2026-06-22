"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, ChevronUp, ChevronDown } from "lucide-react"
import { getMetas, saveMetas } from "@/lib/todd"

export default function MetasPage() {
  const router = useRouter()
  const [metas, setMetas] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getMetas().then(m => { setMetas(m); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const move = (i: number, dir: -1 | 1) => {
    setMetas(prev => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  const confirmar = async () => {
    setSaving(true)
    try { await saveMetas(metas); router.push("/dashboard/foda") }
    catch { setSaving(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-4">
        <span className="text-sm font-bold tracking-widest">TODD · GOBERNIA</span>
      </header>
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl space-y-6">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center text-sm font-bold shrink-0">T</div>
            <div>
              <p className="text-xs font-medium text-gray-400">Todd</p>
              <h2 className="text-lg font-bold leading-snug">Ordena tus retos por prioridad — el 1 es el más importante a resolver.</h2>
            </div>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Preparando tus metas…
            </div>
          ) : (
            <>
              <ul className="space-y-2">
                {metas.map((m, i) => (
                  <li key={m} className="flex items-center gap-3 border border-gray-100 rounded-xl px-3 py-2.5">
                    <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                    <span className="flex-1 text-sm">{m}</span>
                    <div className="flex flex-col">
                      <button onClick={() => move(i, -1)} disabled={i === 0} className="text-gray-300 hover:text-black disabled:opacity-30"><ChevronUp className="h-4 w-4" /></button>
                      <button onClick={() => move(i, 1)} disabled={i === metas.length - 1} className="text-gray-300 hover:text-black disabled:opacity-30"><ChevronDown className="h-4 w-4" /></button>
                    </div>
                  </li>
                ))}
              </ul>
              <button onClick={confirmar} disabled={saving}
                className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-50">
                {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Guardando…</> : "Confirmar prioridades"}
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
