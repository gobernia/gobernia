"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Loader2 } from "lucide-react"
import {
  getPerspectiva, answerPerspectiva, ROLE_LABEL,
  type PerspectivaTurn, type Role,
} from "@/lib/perspectivas"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

export default function PerspectivaPublicaPage() {
  const params = useParams<{ token: string }>()
  const token = params.token

  const [role, setRole] = useState<Role | null>(null)
  const [companyName, setCompanyName] = useState("")
  const [turn, setTurn] = useState<PerspectivaTurn | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getPerspectiva(token)
      .then(async data => {
        setRole(data.role)
        setCompanyName(data.company_name)
        if (data.messages.length > 0) {
          const last = data.messages[data.messages.length - 1]
          setTurn({ message: last.text, options: last.options,
            input: last.options ? "single_choice" : "text", done: data.done })
        } else if (data.done) {
          setTurn({ message: "", options: null, input: "text", done: true })
        } else {
          const t = await answerPerspectiva(token, null)
          setTurn(t)
        }
      })
      .catch(() => setNotFound(true))
  }, [token])

  const answer = async (value: string) => {
    if (!value.trim() || busy) return
    setBusy(true); setText("")
    try {
      const t = await answerPerspectiva(token, value)
      setTurn(t)
    } catch {
      /* deja el paso actual */
    } finally { setBusy(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-4">
          <span className="flex items-center gap-2">
            <GoberniaLogo size={15} />
            <span className="text-gray-200">·</span>
            <span className="text-xs font-semibold tracking-widest text-gray-500 uppercase">Perspectiva</span>
          </span>
          {role && (
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-gray-200 text-gray-500">
              {ROLE_LABEL[role]}
            </span>
          )}
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl">
          {notFound ? (
            <p className="text-center text-sm text-gray-500">
              Este link no es válido o ya expiró.
            </p>
          ) : !turn ? (
            <p className="text-center text-sm text-gray-400">Cargando…</p>
          ) : turn.done ? (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }} className="text-center space-y-2">
              <h2 className="text-lg font-bold text-black">¡Gracias!</h2>
              <p className="text-sm text-gray-500">
                Tu perspectiva ayudará a mejorar la empresa.
              </p>
            </motion.div>
          ) : (
            <div className="space-y-6">
              <p className="text-sm text-gray-500">
                Te invitaron a compartir tu perspectiva sobre <strong className="text-black">{companyName}</strong>.
                Toma 2–3 minutos y es confidencial.
              </p>

              <AnimatePresence mode="wait">
                <motion.div key={turn.message}
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.25 }} className="space-y-6">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center text-sm font-bold shrink-0">T</div>
                    <div>
                      <p className="text-xs font-medium text-gray-400">Todd</p>
                      <h2 className="text-lg font-bold text-black leading-snug">{turn.message}</h2>
                    </div>
                  </div>

                  {turn.options && turn.options.length > 0 ? (
                    busy ? (
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Loader2 className="h-4 w-4 animate-spin" /> Procesando…
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {turn.options.map(o => (
                          <button key={o} disabled={busy} onClick={() => answer(o)}
                            className="text-sm border border-gray-200 rounded-xl px-4 py-2.5 hover:border-[var(--gob-navy)] hover:bg-gray-50 transition-colors disabled:opacity-50">
                            {o}
                          </button>
                        ))}
                      </div>
                    )
                  ) : (
                    <form onSubmit={e => { e.preventDefault(); answer(text) }} className="space-y-3">
                      <textarea value={text} onChange={e => setText(e.target.value)} disabled={busy}
                        rows={3} placeholder="Tu respuesta…"
                        className="w-full rounded-xl border-2 border-gray-100 px-4 py-3 text-sm focus:border-black focus:outline-none resize-none" />
                      <button type="submit" disabled={busy || !text.trim()}
                        className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-40">
                        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Continuar <ArrowRight className="h-4 w-4" /></>}
                      </button>
                    </form>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
