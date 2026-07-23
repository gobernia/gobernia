"use client"

import { useEffect, useRef, useState, FormEvent } from "react"
import { Loader2, Send, Check, X, RefreshCw } from "lucide-react"
import {
  ToddMensaje, ToddAccionCambio,
  getMensajesTodd, enviarMensajeTodd,
} from "@/lib/toddSecretario"
import { updateTask } from "@/lib/annualPlan"

/**
 * Todd, el secretario del Consejo — chat permanente en el Centro de operaciones.
 *
 * Burbujas (tú a la derecha, Todd a la izquierda con avatar "T"), input abajo,
 * "Todd está escribiendo…", scroll al último mensaje. Cuando Todd propone cambiar
 * una tarea, aparece una tarjeta con Reemplazar / Descartar; al reemplazar, refresca
 * el tablero.
 */

const BIENVENIDA =
  "Soy Todd, tu secretario. Puedo decirte qué está atrasado, ayudarte a preparar la reunión, o proponerte cambiar una tarea que no puedas cumplir."

// ── Avatar "T" de Todd ──
function ToddAvatar() {
  return (
    <span className="h-7 w-7 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">
      T
    </span>
  )
}

// ── Una burbuja de mensaje ──
function Burbuja({ mensaje }: { mensaje: ToddMensaje }) {
  const esUsuario = mensaje.role === "user"
  if (esUsuario) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-[var(--gob-navy)] text-[var(--gob-bone)] px-3.5 py-2.5 text-sm leading-snug whitespace-pre-wrap">
          {mensaje.content}
        </div>
      </div>
    )
  }
  return (
    <div className="flex items-start gap-2">
      <ToddAvatar />
      <div className="max-w-[85%] rounded-2xl rounded-tl-md bg-[var(--gob-paper)] border border-[var(--gob-rule)] text-[var(--gob-ink)] px-3.5 py-2.5 text-sm leading-snug whitespace-pre-wrap">
        {mensaje.content}
      </div>
    </div>
  )
}

// ── Tarjeta de propuesta de cambio de tarea ──
function PropuestaCambio({ accion, onReemplazado, onDescartar }: {
  accion: ToddAccionCambio
  onReemplazado: () => void
  onDescartar: () => void
}) {
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState(false)

  const reemplazar = async () => {
    setGuardando(true)
    setError(false)
    try {
      await updateTask(accion.task_id, {
        title: accion.propuesta.title,
        description: accion.propuesta.description ?? null,
      })
      onReemplazado()
    } catch {
      setGuardando(false)
      setError(true)
    }
  }

  return (
    <div className="ml-9 rounded-xl border border-[var(--gob-rule)] bg-white p-3.5 space-y-3">
      <div className="flex items-center gap-1.5">
        <RefreshCw className="h-3.5 w-3.5" style={{ color: "#b45309" }} />
        <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "#b45309" }}>
          Todd propone cambiar esta tarea
        </span>
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-[var(--gob-ink)] leading-snug">{accion.propuesta.title}</p>
        {accion.propuesta.description && (
          <p className="text-xs text-[var(--gob-muted)] leading-snug">{accion.propuesta.description}</p>
        )}
      </div>
      {error && <p className="text-xs text-red-500">No se pudo reemplazar. Intenta de nuevo.</p>}
      <div className="flex items-center gap-2">
        <button type="button" onClick={reemplazar} disabled={guardando}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-60">
          {guardando ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          Reemplazar
        </button>
        <button type="button" onClick={onDescartar} disabled={guardando}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--gob-rule)] text-[var(--gob-muted)] px-3 py-1.5 text-xs font-medium hover:border-[var(--gob-stone)] hover:text-[var(--gob-ink)] transition-colors disabled:opacity-60">
          <X className="h-3.5 w-3.5" />
          Descartar
        </button>
      </div>
    </div>
  )
}

export default function ToddSecretario({ onTareaCambiada, fill = false }: {
  onTareaCambiada?: () => void
  /** Si es true, Todd llena el alto de su contenedor (para el cajón lateral). */
  fill?: boolean
}) {
  const [mensajes, setMensajes] = useState<ToddMensaje[]>([])
  const [cargandoHistorial, setCargandoHistorial] = useState(true)
  const [texto, setTexto] = useState("")
  const [escribiendo, setEscribiendo] = useState(false)
  const [propuesta, setPropuesta] = useState<ToddAccionCambio | null>(null)

  const aliveRef = useRef(true)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  useEffect(() => {
    getMensajesTodd()
      .then(m => {
        if (!aliveRef.current) return
        setMensajes(m)
      })
      .catch(() => {})
      .finally(() => {
        if (aliveRef.current) setCargandoHistorial(false)
      })
  }, [])

  // Scroll al último mensaje al cambiar el hilo o el estado "escribiendo".
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [mensajes, escribiendo, propuesta])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    const content = texto.trim()
    if (!content || escribiendo) return

    const ahora = new Date().toISOString()
    setMensajes(prev => [...prev, { role: "user", content, created_at: ahora }])
    setTexto("")
    setEscribiendo(true)
    setPropuesta(null)

    try {
      const r = await enviarMensajeTodd(content)
      if (!aliveRef.current) return
      setMensajes(prev => [...prev, { role: "assistant", content: r.reply, created_at: new Date().toISOString() }])
      if (r.accion && r.accion.tipo === "proponer_cambio") setPropuesta(r.accion)
    } catch {
      if (!aliveRef.current) return
      setMensajes(prev => [...prev, {
        role: "assistant",
        content: "No pude responder en este momento. Intenta de nuevo en un momento.",
        created_at: new Date().toISOString(),
      }])
    } finally {
      if (aliveRef.current) setEscribiendo(false)
    }
  }

  const hayHistorial = mensajes.length > 0

  return (
    <div className={`flex flex-col bg-white overflow-hidden ${
      fill
        ? "h-full"
        : "rounded-2xl border border-[var(--gob-rule)] h-[560px] max-h-[75vh]"}`}>
      {/* Encabezado */}
      <header className="flex items-center gap-2.5 px-4 py-3 border-b border-[var(--gob-rule)] bg-[var(--gob-paper)]">
        <ToddAvatar />
        <div className="min-w-0">
          <p className="text-sm font-bold text-[var(--gob-ink)] leading-none">Pregúntale a Todd</p>
          <p className="text-[11px] text-[var(--gob-muted)] mt-1 leading-none">Secretario del Consejo</p>
        </div>
      </header>

      {/* Hilo */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {cargandoHistorial ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--gob-stone)]" />
          </div>
        ) : (
          <>
            {!hayHistorial && (
              <Burbuja mensaje={{ role: "assistant", content: BIENVENIDA, created_at: "" }} />
            )}
            {mensajes.map((m, i) => (
              <Burbuja key={`${m.created_at}-${i}`} mensaje={m} />
            ))}
            {propuesta && (
              <PropuestaCambio
                accion={propuesta}
                onDescartar={() => setPropuesta(null)}
                onReemplazado={() => {
                  setPropuesta(null)
                  setMensajes(prev => [...prev, {
                    role: "assistant",
                    content: "Listo, reemplacé la tarea en tu tablero.",
                    created_at: new Date().toISOString(),
                  }])
                  onTareaCambiada?.()
                }}
              />
            )}
            {escribiendo && (
              <div className="flex items-center gap-2 pl-9 text-xs text-[var(--gob-muted)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Todd está escribiendo…
              </div>
            )}
          </>
        )}
      </div>

      {/* Input */}
      <form onSubmit={enviar} className="border-t border-[var(--gob-rule)] p-3 flex items-end gap-2">
        <textarea
          value={texto}
          onChange={e => setTexto(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void enviar(e)
            }
          }}
          rows={1}
          placeholder="Escríbele a Todd…"
          className="flex-1 resize-none max-h-28 rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] px-3 py-2.5 text-sm text-[var(--gob-ink)] placeholder:text-[var(--gob-stone)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)]"
        />
        <button type="submit" disabled={!texto.trim() || escribiendo}
          aria-label="Enviar mensaje a Todd"
          className="shrink-0 inline-flex items-center justify-center h-10 w-10 rounded-xl bg-[var(--gob-navy)] text-[var(--gob-bone)] hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-40">
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}
