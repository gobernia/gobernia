"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, Plus, X, ArrowRight } from "lucide-react"
import { getMetas, saveMetas } from "@/lib/todd"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

export default function MetasPage() {
  const router = useRouter()
  const [metas, setMetas] = useState<string[]>([])
  const [ranked, setRanked] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getMetas().then(m => { setMetas(m); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const pool = metas.filter(m => !ranked.includes(m))
  const add = (m: string) => setRanked(prev => [...prev, m])
  const remove = (m: string) => setRanked(prev => prev.filter(x => x !== m))
  const allDone = metas.length > 0 && ranked.length === metas.length

  const confirmar = async () => {
    setSaving(true)
    try { await saveMetas(ranked); router.push("/dashboard/foda") }
    catch { setSaving(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-4">
        <span className="flex items-center gap-2">
          <GoberniaLogo size={15} />
          <span className="text-gray-200">·</span>
          <span className="text-xs font-semibold tracking-widest text-gray-500 uppercase">Todd</span>
        </span>
      </header>

      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="w-full max-w-3xl space-y-7">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center text-sm font-bold shrink-0">T</div>
            <div>
              <p className="text-xs font-medium text-gray-400">Todd</p>
              <h2 className="text-lg font-bold leading-snug">Ordena tus retos por prioridad.</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Toca primero el reto <strong>más importante</strong> a resolver: será tu prioridad #1. Sigue tocando en orden.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Preparando tus metas…
            </div>
          ) : (
            <>
              <div className="grid gap-5 sm:grid-cols-2">
                {/* Izquierda: retos por ordenar */}
                <div className="space-y-2.5">
                  <p className="text-[11px] font-medium tracking-widest text-gray-400 uppercase">
                    Tus retos · toca en orden
                  </p>
                  <div className="space-y-2">
                    <AnimatePresence initial={false}>
                      {pool.map(m => (
                        <motion.button key={m} layout
                          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
                          transition={{ duration: 0.18 }}
                          onClick={() => add(m)}
                          className="w-full flex items-center gap-3 border border-gray-200 rounded-xl px-3 py-3 text-left hover:border-[var(--gob-navy)] hover:bg-gray-50 transition-colors">
                          <span className="w-6 h-6 rounded-full border-2 border-gray-200 flex items-center justify-center shrink-0">
                            <Plus className="h-3.5 w-3.5 text-gray-400" />
                          </span>
                          <span className="flex-1 text-sm">{m}</span>
                        </motion.button>
                      ))}
                    </AnimatePresence>
                    {pool.length === 0 && (
                      <p className="text-sm text-gray-400 italic px-1 py-3">¡Listo! Ordenaste todos tus retos.</p>
                    )}
                  </div>
                </div>

                {/* Derecha: tu orden de prioridad */}
                <div className="space-y-2.5">
                  <p className="text-[11px] font-medium tracking-widest text-gray-400 uppercase">
                    Tu orden · {ranked.length}/{metas.length}
                  </p>
                  <div className="space-y-2">
                    {ranked.length === 0 && (
                      <div className="border border-dashed border-gray-200 rounded-xl px-3 py-8 text-center text-sm text-gray-400">
                        Toca un reto de la izquierda<br />para colocarlo como tu #1.
                      </div>
                    )}
                    <AnimatePresence initial={false}>
                      {ranked.map((m, i) => (
                        <motion.div key={m} layout
                          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
                          transition={{ duration: 0.18 }}
                          className="flex items-center gap-3 border border-gray-100 rounded-xl px-3 py-2.5">
                          <span className="w-7 h-7 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                          <span className="flex-1 text-sm">{m}</span>
                          <button onClick={() => remove(m)} aria-label="Quitar"
                            className="text-gray-300 hover:text-red-500 transition-colors">
                            <X className="h-4 w-4" />
                          </button>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              </div>

              <button onClick={confirmar} disabled={saving || !allDone}
                className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-50 transition-colors hover:bg-[var(--gob-ink)]">
                {saving ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Guardando…</>
                ) : !allDone ? (
                  `Te faltan ${pool.length} reto${pool.length !== 1 ? "s" : ""} por ordenar`
                ) : (
                  <>Confirmar prioridades <ArrowRight className="h-4 w-4" /></>
                )}
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
