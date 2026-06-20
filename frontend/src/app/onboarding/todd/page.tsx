"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Send, Loader2 } from "lucide-react"
import {
  ToddMessage, ToddTurn, getToddSession, sendToddAnswer, closeTodd,
} from "@/lib/todd"

export default function ToddPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ToddMessage[]>([])
  const [turn, setTurn] = useState<ToddTurn | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [closing, setClosing] = useState(false)
  const started = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true
    getToddSession()
      .then(async sess => {
        if (sess && sess.messages.length > 0) {
          setMessages(sess.messages)
          const last = sess.messages[sess.messages.length - 1]
          setTurn({ message: last.text, options: last.options, input: last.options ? "single_choice" : "text", done: sess.done })
        } else {
          const t = await sendToddAnswer(null)
          setTurn(t)
          setMessages([{ role: "todd", text: t.message, options: t.options }])
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, busy])

  const answer = async (value: string) => {
    if (!value.trim() || busy) return
    setBusy(true); setInput("")
    setMessages(prev => [...prev, { role: "user", text: value, options: null }])
    try {
      const t = await sendToddAnswer(value)
      setTurn(t)
      setMessages(prev => [...prev, { role: "todd", text: t.message, options: t.options }])
    } catch {
      setMessages(prev => [...prev, { role: "todd", text: "Tuve un problema, ¿puedes repetirlo?", options: null }])
    } finally {
      setBusy(false)
    }
  }

  const finish = async () => {
    setClosing(true)
    try { await closeTodd(); router.push("/dashboard/diagnostico") }
    catch { setClosing(false) }
  }

  return (
    <div className="min-h-dvh bg-white text-black flex flex-col">
      <header className="border-b border-gray-100 px-5 py-3 text-sm font-bold tracking-widest">TODD · GOBERNIA</header>

      <main className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl mx-auto w-full space-y-4">
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]" : "bg-gray-100 text-black"}`}>
              {m.text}
            </div>
          </motion.div>
        ))}
        {busy && (
          <div className="flex justify-start"><div className="bg-gray-100 rounded-2xl px-4 py-2.5">
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" /></div></div>
        )}
        <div ref={bottomRef} />
      </main>

      <footer className="border-t border-gray-100 px-4 py-3 max-w-2xl mx-auto w-full space-y-3">
        {turn?.options && turn.options.length > 0 && !busy && (
          <div className="flex flex-wrap gap-2">
            {turn.options.map(o => (
              <button key={o} onClick={() => answer(o)}
                className="text-sm border border-gray-200 rounded-full px-3 py-1.5 hover:border-[var(--gob-navy)] transition-colors">
                {o}
              </button>
            ))}
          </div>
        )}
        {turn?.done ? (
          <button onClick={finish} disabled={closing}
            className="w-full bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-xl py-3 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50">
            {closing ? <><Loader2 className="h-4 w-4 animate-spin" /> Preparando tu diagnóstico…</> : "Finalizar y ver mi diagnóstico"}
          </button>
        ) : (
          <form onSubmit={e => { e.preventDefault(); answer(input) }} className="flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} disabled={busy}
              placeholder="Escribe tu respuesta…"
              className="flex-1 h-11 rounded-xl border-2 border-gray-100 px-4 text-sm focus:border-black focus:outline-none" />
            <button type="submit" disabled={busy || !input.trim()}
              className="h-11 w-11 rounded-xl bg-[var(--gob-navy)] text-[var(--gob-bone)] flex items-center justify-center disabled:opacity-40">
              <Send className="h-4 w-4" />
            </button>
          </form>
        )}
      </footer>
    </div>
  )
}
