"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useRouter, useParams } from "next/navigation"
import { motion } from "framer-motion"
import { ArrowLeft, Loader2, Send, RotateCcw, ListChecks } from "lucide-react"
import Link from "next/link"
import api from "@/lib/api"
import { supabase } from "@/lib/supabase"
import { GoberniaIcon } from "@/components/ui/GoberniaLogo"
import AgentsCollaboration from "@/components/plan/AgentsCollaboration"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Data ──────────────────────────────────────────────────
const AGENTS = [
  { id: "CFO",     role: "Finanzas" },
  { id: "CSO",     role: "Estrategia" },
  { id: "CRO",     role: "Riesgos" },
  { id: "Auditor", role: "Gobierno" },
]

// ── Types ─────────────────────────────────────────────────
interface Analysis {
  summary: string
  findings: string[]
  alerts: string[]
  recommendations: string[]
}

interface ChatMsg {
  message_id: string
  role: "user" | "assistant"
  agent: string | null
  content: string
  created_at: string
}

interface SessionDetail {
  board_session_id: string
  period_year: number
  period_month: number
  period_label: string
  status: string
  agent_analyses: Record<string, Analysis> | null
  messages: ChatMsg[]
}

type Tab = "analisis" | "chat"

// ── Page ──────────────────────────────────────────────────
export default function SessionPage() {
  const router   = useRouter()
  const params   = useParams()
  const id       = params.id as string

  const [session,       setSession]       = useState<SessionDetail | null>(null)
  const [loadError,     setLoadError]     = useState<string | null>(null)
  const [loading,       setLoading]       = useState(true)
  const [planStats,     setPlanStats]     = useState<{ total: number; completed: number } | null>(null)
  const [tab,           setTab]           = useState<Tab>("analisis")
  const [analysing,     setAnalysing]     = useState(false)
  const [analyseError,  setAnalyseError]  = useState<string | null>(null)
  const [activeAgent,   setActiveAgent]   = useState("CFO")
  const [messages,      setMessages]      = useState<ChatMsg[]>([])
  const [input,         setInput]         = useState("")
  const [sending,       setSending]       = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchSession = useCallback(() => {
    return api.get(`/board-sessions/${id}`).then(r => {
      setSession(r.data)
      setMessages(r.data.messages ?? [])
    })
  }, [id])

  useEffect(() => {
    fetchSession()
      .catch((e: unknown) => {
        const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setLoadError(msg ?? "No se pudo cargar la sesión.")
      })
      .finally(() => setLoading(false))
  }, [fetchSession, router])

  // Chequear si ya existe un plan de acción para esta sesión
  useEffect(() => {
    api.get(`/board-sessions/${id}/plan`)
      .then(r => {
        const tasks = (r.data?.tasks ?? []) as { status: string }[]
        setPlanStats({
          total: tasks.length,
          completed: tasks.filter(t => t.status === "completada").length,
        })
      })
      .catch(() => setPlanStats(null))  // 404 = no plan yet
  }, [id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const runAnalysis = async () => {
    setAnalysing(true)
    setAnalyseError(null)
    try {
      const r = await api.post(`/board-sessions/${id}/analyse`, {
        agents: ["CFO", "CSO", "CRO", "Auditor"],
      }, { timeout: 600000 })  // 10 min — análisis con Challenger puede tomar 2-5 min
      setSession(prev =>
        prev ? { ...prev, agent_analyses: r.data.analyses, status: "active" } : prev
      )
    } catch (e: unknown) {
      // El backend a veces completa el análisis aunque la conexión HTTP se corte.
      // Antes de mostrar error, verificar si los análisis ya están en DB.
      const status = (e as { response?: { status?: number } })?.response?.status
      const backendMsg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail

      // Solo intentar recovery si NO fue un 4xx explícito del backend
      if (!status || status >= 500) {
        try {
          // Esperar 3s para dar margen a que termine si está cerca
          await new Promise(r => setTimeout(r, 3000))
          const check = await api.get(`/board-sessions/${id}`)
          const analyses = check.data?.agent_analyses
          if (analyses && Object.keys(analyses).length > 0) {
            setSession(prev =>
              prev ? { ...prev, agent_analyses: analyses, messages: check.data.messages ?? prev.messages, status: check.data.status ?? prev.status } : prev
            )
            return
          }
        } catch { /* fall through to error */ }
      }
      setAnalyseError(backendMsg ?? "Error al ejecutar el análisis. Intenta de nuevo.")
    } finally {
      setAnalysing(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || sending) return
    const content = input.trim()
    setInput("")
    setSending(true)

    const tempUserId = `temp-${Date.now()}`
    const tempAssistantId = `temp-asst-${Date.now()}`
    const nowIso = new Date().toISOString()

    setMessages(prev => [
      ...prev,
      { message_id: tempUserId,      role: "user",      agent: null,        content,        created_at: nowIso },
      { message_id: tempAssistantId, role: "assistant", agent: activeAgent, content: "",    created_at: nowIso },
    ])

    try {
      const { data: sessionData } = await supabase.auth.getSession()
      const token = sessionData.session?.access_token
      const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
      const res = await fetch(`${baseUrl}/board-sessions/${id}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": token ? `Bearer ${token}` : "",
        },
        body: JSON.stringify({ content, agent: activeAgent }),
      })

      if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`)

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        if (!chunk) continue
        setMessages(prev => prev.map(m =>
          m.message_id === tempAssistantId
            ? { ...m, content: m.content + chunk }
            : m
        ))
      }
    } catch {
      setMessages(prev => prev.filter(m =>
        m.message_id !== tempUserId && m.message_id !== tempAssistantId
      ))
    } finally {
      setSending(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  // Filter messages for active agent conversation
  const threadMessages = messages.filter(
    m => m.role === "user" || m.agent === activeAgent
  )

  const hasAnalysis =
    session?.agent_analyses && Object.keys(session.agent_analyses).length > 0

  // ── Loading ────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-dvh bg-white flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-gray-300" />
      </div>
    )
  }

  if (loadError || !session) {
    return (
      <div className="min-h-dvh bg-white flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-gray-500">{loadError ?? "Sesión no encontrada."}</p>
        <button
          onClick={() => router.push("/dashboard")}
          className="text-xs text-black underline underline-offset-2"
        >
          Volver al dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased flex flex-col">

      {/* ── Navbar ───────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] h-14 flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[var(--gob-navy)] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Volver
          </button>

          <div className="w-px h-4 bg-gray-200" />

          <div className="flex items-center gap-2">
            <GoberniaIcon size={18} />
            <span className="text-sm font-medium text-[var(--gob-ink)] tracking-tight">
              {session.period_label}
            </span>
          </div>

          <span className={`text-[10px] font-medium px-2.5 py-1 rounded-full ${
            hasAnalysis
              ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]"
              : "bg-gray-100 text-gray-500"
          }`}>
            {hasAnalysis ? "Activa" : "Borrador"}
          </span>
        </div>
      </header>

      {/* ── Tab bar ──────────────────────────────────────── */}
      <div className="fixed top-14 inset-x-0 z-40 bg-white border-b border-gray-100">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] flex">
          {(["analisis", "chat"] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-3.5 text-xs font-medium border-b-2 transition-colors ${
                tab === t
                  ? "border-[var(--gob-navy)] text-[var(--gob-navy)]"
                  : "border-transparent text-gray-400 hover:text-gray-700"
              }`}
            >
              {t === "analisis" ? "Análisis" : "Chat"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main ─────────────────────────────────────────── */}
      <main className="flex-1 pt-28">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] pb-10">

          {/* ── Análisis ─────────────────────────────────── */}
          {tab === "analisis" && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: EASE }}
              className="space-y-8 py-10"
            >
              {analysing ? (
                /* Live collaboration animation */
                <div className="border border-gray-100 rounded-2xl p-12 flex flex-col items-center text-center">
                  <AgentsCollaboration />
                </div>
              ) : !hasAnalysis ? (
                /* Empty state — no analysis yet */
                <div className="border border-gray-100 rounded-2xl p-16 flex flex-col items-center text-center space-y-7">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {AGENTS.map(a => (
                      <div key={a.id} className="flex flex-col items-center gap-2">
                        <div className="w-12 h-12 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
                          <span className="text-sm font-bold text-gray-300">{a.id[0]}</span>
                        </div>
                        <span className="text-[10px] font-medium text-gray-400">{a.id}</span>
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <p className="text-base font-medium text-black">
                      Tu consejo está listo para analizar
                    </p>
                    <p className="text-sm text-gray-400 max-w-sm leading-relaxed">
                      Los cinco consejeros con IA revisarán tu perfil, y el Retador
                      aplicará un pre-mortem a cada análisis antes de mostrártelo.
                    </p>
                  </div>

                  {analyseError && (
                    <p className="text-xs text-red-500">{analyseError}</p>
                  )}

                  <button
                    onClick={runAnalysis}
                    className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
                  >
                    Iniciar análisis
                  </button>
                </div>
              ) : (
                /* Analysis results */
                <div className="space-y-7">
                  <div className="flex items-end justify-between">
                    <div>
                      <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-1">
                        Diagnóstico del periodo
                      </p>
                      <h2 className="text-2xl font-bold text-black tracking-tight">
                        {session.period_label}
                      </h2>
                    </div>
                    <button
                      onClick={runAnalysis}
                      disabled={analysing}
                      className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-[var(--gob-navy)] transition-colors disabled:opacity-50"
                    >
                      <RotateCcw className={`h-3.5 w-3.5 ${analysing ? "animate-spin" : ""}`} />
                      Actualizar análisis
                    </button>
                  </div>

                  <Link
                    href={`/dashboard/sesion/${id}/plan`}
                    className="group flex items-center justify-between bg-[var(--gob-navy)] hover:bg-[var(--gob-ink)] text-[var(--gob-bone)] px-6 py-4 rounded-2xl transition-colors"
                  >
                    <div className="flex items-center gap-3.5">
                      <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                        <ListChecks className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">
                          {planStats ? "Ver plan de acción" : "Generar plan de acción"}
                        </p>
                        <p className="text-[11px] text-gray-400 mt-0.5">
                          {planStats
                            ? `${planStats.completed} de ${planStats.total} tareas completadas`
                            : "Convierte los hallazgos en tareas ejecutables tipo Kanban"}
                        </p>
                      </div>
                    </div>
                    {planStats && planStats.total > 0 && (
                      <div className="hidden sm:flex items-center gap-3 mr-3">
                        <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-white rounded-full transition-all duration-500"
                            style={{ width: `${Math.round((planStats.completed / planStats.total) * 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                    <span className="text-xs text-gray-300 group-hover:text-[var(--gob-bone)] transition-colors">→</span>
                  </Link>

                  <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-4 gap-5">
                    {AGENTS.map((a, i) => {
                      const analysis = session.agent_analyses?.[a.id]
                      if (!analysis) return null
                      return (
                        <motion.div
                          key={a.id}
                          initial={{ opacity: 0, y: 16 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.4, ease: EASE, delay: i * 0.07 }}
                          className="border border-gray-100 hover:border-gray-300 rounded-2xl p-7 space-y-5 transition-colors flex flex-col"
                        >
                          <div>
                            <p className="text-base font-bold text-black">{a.id}</p>
                            <p className="text-xs text-gray-400 mt-0.5">{a.role}</p>
                          </div>

                          <p className="text-sm text-gray-600 leading-relaxed">
                            {analysis.summary}
                          </p>

                          {analysis.findings?.length > 0 && (
                            <div className="space-y-2">
                              <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                                Hallazgos
                              </p>
                              <ul className="space-y-1.5">
                                {analysis.findings.map((f, j) => (
                                  <li key={j} className="flex gap-2 text-xs text-gray-600 leading-relaxed">
                                    <span className="text-gray-300 flex-shrink-0 mt-0.5">·</span>
                                    {f}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {analysis.alerts?.length > 0 && (
                            <div className="space-y-2">
                              <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                                Alertas
                              </p>
                              <ul className="space-y-1.5">
                                {analysis.alerts.map((al, j) => (
                                  <li key={j} className="flex gap-2 text-xs text-gray-700 font-medium leading-relaxed">
                                    <span className="text-gray-400 flex-shrink-0">!</span>
                                    {al}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {analysis.recommendations?.length > 0 && (
                            <div className="space-y-2">
                              <p className="text-[10px] font-medium tracking-widest text-gray-400 uppercase">
                                Recomendaciones
                              </p>
                              <ul className="space-y-1.5">
                                {analysis.recommendations.map((r, j) => (
                                  <li key={j} className="flex gap-2 text-xs text-gray-600 leading-relaxed">
                                    <span className="text-gray-300 flex-shrink-0">→</span>
                                    {r}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="pt-1 mt-auto">
                            <button
                              onClick={() => { setActiveAgent(a.id); setTab("chat") }}
                              className="w-full text-xs font-medium text-gray-500 hover:text-[var(--gob-navy)] border border-gray-200 hover:border-gray-400 px-3 py-2.5 rounded-xl transition-colors"
                            >
                              Chatear con {a.id} →
                            </button>
                          </div>
                        </motion.div>
                      )
                    })}
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* ── Chat ─────────────────────────────────────── */}
          {tab === "chat" && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: EASE }}
              className="flex flex-col py-6"
              style={{ height: "calc(100dvh - 8rem)" }}
            >
              {/* Agent selector */}
              <div className="flex flex-wrap gap-2 mb-6">
                {AGENTS.map(a => (
                  <button
                    key={a.id}
                    onClick={() => setActiveAgent(a.id)}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium border-2 transition-all duration-150 ${
                      activeAgent === a.id
                        ? "border-[var(--gob-navy)] bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                        : "border-gray-200 text-gray-500 hover:border-gray-400 hover:text-[var(--gob-navy)]"
                    }`}
                  >
                    {a.id}
                    <span className={`hidden sm:inline ${
                      activeAgent === a.id ? "text-gray-400" : "text-gray-400"
                    }`}>
                      · {a.role}
                    </span>
                  </button>
                ))}
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto space-y-4 pb-4 min-h-0">
                {threadMessages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                    <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center">
                      <span className="text-xl font-bold text-gray-200">
                        {activeAgent[0]}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-black">
                        Habla con {activeAgent}
                      </p>
                      <p className="text-xs text-gray-400 max-w-xs leading-relaxed">
                        Tu consejero tiene contexto completo de tu empresa. Pregunta lo que necesites.
                      </p>
                    </div>
                  </div>
                ) : (
                  threadMessages.map(msg => (
                    <div
                      key={msg.message_id}
                      className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {msg.role === "assistant" && (
                        <div className="w-7 h-7 rounded-lg bg-[var(--gob-navy)] flex items-center justify-center flex-shrink-0 mt-1">
                          <span className="text-[var(--gob-bone)] text-[10px] font-bold">
                            {msg.agent?.[0]}
                          </span>
                        </div>
                      )}
                      <div
                        className={`max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                          msg.role === "user"
                            ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                            : "bg-gray-50 border border-gray-100 text-gray-800"
                        }`}
                      >
                        {msg.role === "assistant" && !msg.content ? (
                          <div className="flex items-center gap-1.5 py-1">
                            {[0, 1, 2].map(i => (
                              <motion.div
                                key={i}
                                className="w-1.5 h-1.5 rounded-full bg-gray-400"
                                animate={{ opacity: [0.3, 1, 0.3] }}
                                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                              />
                            ))}
                          </div>
                        ) : (
                          msg.content.split("\n").filter(Boolean).map((line, i) => (
                            <p key={i} className={i > 0 ? "mt-2" : ""}>{line}</p>
                          ))
                        )}
                      </div>
                    </div>
                  ))
                )}



                <div ref={bottomRef} />
              </div>

              {/* Input bar */}
              <div className="border-t border-gray-100 pt-4 space-y-2">
                <div className="flex gap-3 items-end">
                  <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder={`Pregunta a ${activeAgent}…`}
                    rows={2}
                    className="flex-1 resize-none rounded-xl border-2 border-gray-200 px-4 py-3 text-sm text-black placeholder:text-gray-400 focus:border-[var(--gob-navy)] focus:outline-none transition-colors"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim() || sending}
                    className="h-11 w-11 rounded-xl bg-[var(--gob-navy)] flex items-center justify-center hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-30 flex-shrink-0"
                  >
                    <Send className="h-4 w-4 text-[var(--gob-bone)]" />
                  </button>
                </div>
                <p className="text-[10px] text-gray-400">
                  Enter para enviar · Shift+Enter nueva línea
                </p>
              </div>
            </motion.div>
          )}

        </div>
      </main>
    </div>
  )
}
