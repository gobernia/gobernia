"use client"

import { useEffect, useRef, useState, type CSSProperties } from "react"
import { Check, Loader2 } from "lucide-react"

const INK = "#0E1626"
const MUTED = "#6E7686"
const BNAVY = "#152742"
const ACCENT = "#C2410C"
const LINE = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

/** 3:07 / 12:45 */
export function reloj(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
}

/** Paso en curso según el tiempo típico. Se queda en el último hasta que el servidor diga que
 * terminó: nunca marca como listo algo que no lo está. */
export function pasoActual(segundos: number, pasos: number, minutosTipicos: number): number {
  return Math.min(pasos - 1, Math.floor((segundos / (minutosTipicos * 60)) * pasos))
}

interface Props {
  eyebrow: string
  titulo: string
  descripcion: string
  pasos: string[]
  /** Cuánto suele tardar. Sin un dato medido no se estima: solo se muestra el reloj. */
  minutosTipicos?: number
  /** Lo que lleva según el servidor (así el reloj no se reinicia al recargar). */
  segundos?: number | null
  /** P. ej. "Tu diagnóstico aparecerá aquí cuando esté listo." */
  listo: string
}

/** Pantalla de espera de los procesos largos del Consejo (diagnóstico, plan): qué está
 * haciendo, cuánto lleva, cuánto suele tardar y que se puede salir sin perder nada. */
export function EsperaConsejo({ eyebrow, titulo, descripcion, pasos, minutosTipicos, segundos, listo }: Props) {
  const [transcurrido, setTranscurrido] = useState(segundos ?? 0)
  // Primer dato del servidor + el momento en que llegó; entre consultas se cuenta aquí.
  const base = useRef<{ s: number; t: number } | null>(null)

  useEffect(() => {
    if (segundos != null && base.current == null) base.current = { s: segundos, t: Date.now() }
  }, [segundos])

  useEffect(() => {
    const montado = Date.now()
    const id = setInterval(() => {
      const b = base.current
      setTranscurrido(b ? b.s + (Date.now() - b.t) / 1000 : (Date.now() - montado) / 1000)
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const actual = minutosTipicos ? pasoActual(transcurrido, pasos.length, minutosTipicos) : -1
  const tarde = !!minutosTipicos && transcurrido > minutosTipicos * 60 * 1.3

  return (
    <div className="w-full max-w-md flex flex-col items-center gap-6 text-center">
      <Loader2 className="h-6 w-6 animate-spin" style={{ color: BNAVY }} aria-hidden />
      <div className="space-y-1">
        <p className="text-[10.5px] font-extrabold tracking-[0.17em] uppercase" style={{ color: ACCENT }}>{eyebrow}</p>
        <h1 className="text-xl font-bold text-balance" style={{ ...SANS, color: INK }}>{titulo}</h1>
        <p className="text-sm text-gray-500 text-pretty">{descripcion}</p>
      </div>

      <ol className="w-full rounded-2xl border bg-white px-5 py-4 space-y-3 text-left" style={{ borderColor: LINE }}
        aria-label={minutosTipicos ? "Avance" : "Lo que está haciendo tu Consejo"}>
        {pasos.map((paso, i) => {
          const hecho = actual >= 0 && i < actual
          const enCurso = i === actual
          return (
            <li key={paso} className="flex items-start gap-3 text-sm"
              aria-current={enCurso ? "step" : undefined}
              style={{ color: hecho || enCurso || actual < 0 ? INK : MUTED, fontWeight: enCurso ? 600 : 400 }}>
              <span className="mt-0.5 h-4 w-4 shrink-0 flex items-center justify-center" aria-hidden>
                {hecho ? <Check className="h-4 w-4" style={{ color: "#0f766e" }} />
                  : enCurso ? <Loader2 className="h-4 w-4 animate-spin" style={{ color: ACCENT }} />
                  : <span className="h-1.5 w-1.5 rounded-full" style={{ background: actual < 0 ? BNAVY : LINE }} />}
              </span>
              {paso}
            </li>
          )
        })}
      </ol>

      <div className="space-y-1.5">
        <p className="text-sm tabular-nums" style={{ color: INK }}>
          Lleva <span className="font-semibold">{reloj(transcurrido)}</span>
          <span style={{ color: MUTED }}>
            {minutosTipicos ? ` · suele tardar alrededor de ${minutosTipicos} minutos` : " · suele tardar varios minutos"}
          </span>
        </p>
        {tarde && (
          <p className="text-sm" style={{ color: MUTED }}>Está tardando más de lo normal, pero sigue trabajando.</p>
        )}
        <p className="text-sm text-gray-500 text-pretty">
          Puedes cerrar esta página o seguir usando Gobernia. {listo}
        </p>
      </div>
    </div>
  )
}
