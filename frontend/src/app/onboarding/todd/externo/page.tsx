"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, ArrowLeft, Loader2, Pencil, X, Check } from "lucide-react"
import {
  ToddMessage, ToddTurn, QAPair, PESTEL_CATS,
  getExternoSession, sendExternoAnswer, editExternoAnswer, buildQAPairs,
} from "@/lib/todd"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

const AREA_LABEL: Record<string, string> = {
  politicos: "Políticos", economicos: "Económicos", sociales: "Sociales",
  tecnologicos: "Tecnológicos", ambiental: "Ambiental", legal: "Legal",
}

export default function ExternoPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ToddMessage[]>([])
  const [turn, setTurn] = useState<ToddTurn | null>(null)
  const [areas, setAreas] = useState<string[]>([])
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [closing, setClosing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editPair, setEditPair] = useState<QAPair | null>(null)
  const [editText, setEditText] = useState("")
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getExternoSession()
      .then(async sess => {
        if (sess && sess.messages.length > 0) {
          setMessages(sess.messages); setAreas(sess.areas_cubiertas)
          const last = sess.messages[sess.messages.length - 1]
          setTurn({ message: last.text, options: last.options,
            input: last.options ? "single_choice" : "text", done: sess.done,
            areas_cubiertas: sess.areas_cubiertas })
        } else {
          const t = await sendExternoAnswer(null)
          setTurn(t); setAreas(t.areas_cubiertas)
          setMessages([{ role: "todd", text: t.message, options: t.options }])
        }
      })
      .catch(() => {})
  }, [])

  const applyTurn = (t: ToddTurn, userMsg?: string) => {
    setTurn(t); setAreas(t.areas_cubiertas)
    setMessages(prev => {
      const next = [...prev]
      if (userMsg) next.push({ role: "user", text: userMsg, options: null })
      next.push({ role: "todd", text: t.message, options: t.options })
      return next
    })
  }

  const answer = async (value: string) => {
    if (!value.trim() || busy) return
    setBusy(true); setText("")
    try {
      const t = await sendExternoAnswer(value)
      applyTurn(t, value)
    } catch {
      /* deja el paso actual */
    } finally { setBusy(false) }
  }

  const finish = async () => {
    setClosing(true)
    router.push("/onboarding/todd/metas")
  }

  const openEdit = (p: QAPair) => { setEditPair(p); setEditText(p.answer) }

  const submitEdit = async () => {
    if (!editPair || !editText.trim() || busy) return
    setBusy(true)
    try {
      const t = await editExternoAnswer(editPair.msgIndex, editText)
      const sess = await getExternoSession()
      if (sess) {
        setMessages(sess.messages); setAreas(sess.areas_cubiertas)
        const last = sess.messages[sess.messages.length - 1]
        setTurn({ message: last.text, options: last.options,
          input: last.options ? "single_choice" : "text", done: sess.done,
          areas_cubiertas: sess.areas_cubiertas })
      } else {
        setTurn(t); setAreas(t.areas_cubiertas)
      }
      setEditPair(null); setEditing(false)
    } catch {
      /* mantiene el panel */
    } finally { setBusy(false) }
  }

  const pairs = buildQAPairs(messages)

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-4">
          <span className="flex items-center gap-2">
            <GoberniaLogo size={15} />
            <span className="text-gray-200">·</span>
            <span className="text-xs font-semibold tracking-widest text-gray-500 uppercase">Todd</span>
          </span>
          <div className="flex flex-wrap gap-1.5">
            {PESTEL_CATS.map(a => (
              <span key={a}
                className={`text-[10px] px-2 py-0.5 rounded-full border ${
                  areas.includes(a)
                    ? "bg-[var(--gob-navy)] text-[var(--gob-bone)] border-[var(--gob-navy)]"
                    : "text-gray-400 border-gray-200"
                }`}>
                {AREA_LABEL[a]}
              </span>
            ))}
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-xl">
          {editing ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">¿En qué te equivocaste?</h2>
                <button onClick={() => { setEditing(false); setEditPair(null) }}
                  className="text-gray-400 hover:text-black"><X className="h-4 w-4" /></button>
              </div>
              {!editPair ? (
                <ul className="space-y-2">
                  {pairs.map(p => (
                    <li key={p.msgIndex}>
                      <button onClick={() => openEdit(p)}
                        className="w-full text-left border border-gray-100 rounded-xl p-3 hover:border-[var(--gob-navy)] transition-colors">
                        <p className="text-xs text-gray-400">{p.question}</p>
                        <p className="text-sm text-black flex items-center justify-between gap-2">
                          {p.answer} <Pencil className="h-3.5 w-3.5 text-gray-300 shrink-0" />
                        </p>
                      </button>
                    </li>
                  ))}
                  {pairs.length === 0 && <p className="text-sm text-gray-400">Aún no hay respuestas.</p>}
                </ul>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-gray-400">{editPair.question}</p>
                  {editPair.options && editPair.options.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {editPair.options.map(o => (
                        <button key={o} onClick={() => setEditText(o)}
                          className={`text-sm border rounded-full px-3 py-1.5 ${
                            editText === o ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                            : "border-gray-200"}`}>
                          {o}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <input value={editText} onChange={e => setEditText(e.target.value)}
                      className="w-full h-11 rounded-xl border-2 border-gray-100 px-4 text-sm focus:border-black focus:outline-none" />
                  )}
                  <div className="flex gap-2">
                    <button onClick={() => setEditPair(null)}
                      className="flex-1 text-sm text-gray-500">Cancelar</button>
                    <button onClick={submitEdit} disabled={busy || !editText.trim()}
                      className="flex-[2] inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-2.5 rounded-xl disabled:opacity-50">
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Guardar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div key={turn?.message}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }} className="space-y-6">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center text-sm font-bold shrink-0">T</div>
                  <div>
                    <p className="text-xs font-medium text-gray-400">Todd</p>
                    <h2 className="text-lg font-bold text-black leading-snug">{turn?.message}</h2>
                  </div>
                </div>

                {turn && !turn.done && (
                  turn.options && turn.options.length > 0 ? (
                    busy ? (
                      <div className="flex items-center gap-2 text-sm text-gray-400">
                        <Loader2 className="h-4 w-4 animate-spin" /> Procesando tu respuesta…
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
                  )
                )}

                {turn?.done && (
                  <button onClick={finish} disabled={closing}
                    className="w-full inline-flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium py-3 rounded-xl disabled:opacity-50">
                    {closing ? <><Loader2 className="h-4 w-4 animate-spin" /> Un momento…</> : <>Continuar a priorizar mis metas <ArrowRight className="h-4 w-4" /></>}
                  </button>
                )}

                {pairs.length > 0 && (
                  <button onClick={() => setEditing(true)}
                    className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-[var(--gob-navy)] transition-colors">
                    <ArrowLeft className="h-3.5 w-3.5" /> Atrás · corregir una respuesta
                  </button>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </main>
    </div>
  )
}
