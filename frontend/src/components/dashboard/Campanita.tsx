"use client"

// Campanita de avisos — esquina superior derecha, junto al botón de ayuda (WelcomeTour).
// Junta en un solo lugar, con el número de los que no se han visto:
//   · las alertas del plan (antes eran tarjetas fijas arriba a la derecha), y
//   · las revisiones de documentos: cuando el Auditor termina de leer lo que se subió,
//     Todd lo explica en su chat; el aviso lleva ahí.
// Lo "ya visto" se recuerda en este navegador (localStorage); abrir la lista lo marca todo.

import { useCallback, useEffect, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Bell, ShieldCheck, CircleDashed, AlertTriangle, FileWarning, Info, ChevronRight,
} from "lucide-react"
import { getAlertas, type AlertItem } from "@/lib/alerts"
import { getMensajesTodd, type ToddMensaje } from "@/lib/toddSecretario"
import { abrirTodd, detalleDeRevision } from "@/lib/toddEventos"

const VISTOS_KEY = "gobernia_avisos_vistos"
const MAX_REVISIONES = 10
const REFRESCO_MS = 60_000

const NIVEL: Record<string, { color: string; Icon: typeof Bell }> = {
  critical: { color: "#b91c1c", Icon: AlertTriangle },
  warning:  { color: "#b45309", Icon: AlertTriangle },
  info:     { color: "#6C6A66", Icon: Info },
}
const REVISION: Record<string, { color: string; Icon: typeof Bell }> = {
  validada:     { color: "#0f766e", Icon: ShieldCheck },
  parcial:      { color: "#1d4ed8", Icon: CircleDashed },
  insuficiente: { color: "#b45309", Icon: AlertTriangle },
  sin_revisar:  { color: "#6C6A66", Icon: FileWarning },
}

interface Aviso {
  clave: string
  titulo: string
  detalle?: string
  fecha?: string
  color: string
  Icon: typeof Bell
  /** Si existe, el aviso lleva a algún lado (p. ej. el chat de Todd). */
  accion?: () => void
}

function leerVistos(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(VISTOS_KEY) || "[]")) } catch { return new Set() }
}
function guardarVistos(claves: Set<string>) {
  // Solo se guardan las claves vigentes, para que la lista no crezca sin fin.
  try { localStorage.setItem(VISTOS_KEY, JSON.stringify([...claves])) } catch { /* noop */ }
}

function haceCuanto(iso?: string): string {
  if (!iso) return ""
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (Number.isNaN(min)) return ""
  if (min < 1) return "ahora"
  if (min < 60) return `hace ${min} min`
  const h = Math.round(min / 60)
  if (h < 24) return `hace ${h} h`
  const d = Math.round(h / 24)
  return d === 1 ? "ayer" : `hace ${d} días`
}

function avisosDeAlertas(alertas: AlertItem[]): Aviso[] {
  return alertas.map(a => ({
    clave: `alerta:${a.message}`,
    titulo: a.message,
    ...(NIVEL[a.level] ?? NIVEL.info),
  }))
}

function avisosDeRevisiones(mensajes: ToddMensaje[]): Aviso[] {
  return mensajes
    .filter(m => m.role === "assistant" && m.revision)
    .slice(-MAX_REVISIONES)
    .reverse()
    .map((m, i) => {
      const r = m.revision!
      return {
        clave: `revision:${m.message_id ?? `${r.task_id}:${m.created_at}:${i}`}`,
        titulo: `Todd revisó «${r.archivo}»`,
        detalle: detalleDeRevision(r.estado, r.tarea),
        fecha: m.created_at,
        ...(REVISION[r.estado] ?? REVISION.sin_revisar),
        accion: abrirTodd,
      }
    })
}

export default function Campanita() {
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const [vistos, setVistos] = useState<Set<string>>(() =>
    typeof window === "undefined" ? new Set() : leerVistos())
  // Los que eran nuevos al abrir la lista (se marcan con un punto mientras está abierta).
  const [nuevos, setNuevos] = useState<Set<string>>(new Set())
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const botonRef = useRef<HTMLButtonElement>(null)

  const cargar = useCallback(async () => {
    const [alertas, mensajes] = await Promise.all([
      getAlertas().catch(() => [] as AlertItem[]),
      getMensajesTodd().catch(() => [] as ToddMensaje[]),
    ])
    // Primero lo más reciente: revisiones de documentos (con fecha) y luego las alertas del plan.
    setAvisos([...avisosDeRevisiones(mensajes), ...avisosDeAlertas(alertas)])
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial de los avisos desde el servidor
    void cargar()
    // Todd dejó un mensaje (el tablero lo avisa al terminar una revisión), al volver a la
    // pestaña y cada minuto: así llegan también las revisiones que terminan en otra página.
    const alVolver = () => { if (document.visibilityState === "visible") void cargar() }
    const id = window.setInterval(() => { if (document.visibilityState === "visible") void cargar() }, REFRESCO_MS)
    window.addEventListener("todd:nuevo-mensaje", cargar)
    document.addEventListener("visibilitychange", alVolver)
    return () => {
      window.clearInterval(id)
      window.removeEventListener("todd:nuevo-mensaje", cargar)
      document.removeEventListener("visibilitychange", alVolver)
    }
  }, [cargar])

  // Cerrar al tocar fuera o con Escape.
  useEffect(() => {
    if (!open) return
    const fuera = (e: MouseEvent) => {
      const t = e.target as Node
      if (!panelRef.current?.contains(t) && !botonRef.current?.contains(t)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false) }
    document.addEventListener("mousedown", fuera)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", fuera)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

  const sinVer = avisos.filter(a => !vistos.has(a.clave)).length

  const alternar = () => {
    if (!open) {
      // Abrir la lista cuenta como verlos: el número se va.
      setNuevos(new Set(avisos.filter(a => !vistos.has(a.clave)).map(a => a.clave)))
      const todos = new Set(avisos.map(a => a.clave))
      guardarVistos(todos)
      setVistos(todos)
    }
    setOpen(o => !o)
  }

  return (
    <>
      <button
        ref={botonRef}
        type="button"
        onClick={alternar}
        aria-label={sinVer ? `Avisos: ${sinVer} sin ver` : "Avisos"}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="fixed top-3 right-[3.5rem] z-40 w-9 h-9 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] shadow-lg flex items-center justify-center hover:bg-[var(--gob-ink)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--gob-navy)]"
      >
        <Bell className="h-[18px] w-[18px]" />
        {sinVer > 0 && (
          <span aria-hidden
            className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-[#C2410C] text-white text-[10px] font-bold leading-[18px] text-center tabular-nums ring-2 ring-[#F2F2F0]">
            {sinVer > 9 ? "9+" : sinVer}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-label="Avisos"
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="fixed top-14 right-3 z-50 w-[340px] max-w-[calc(100vw-1.5rem)] max-h-[70vh] overflow-y-auto rounded-2xl bg-white shadow-xl border border-[var(--gob-rule)]"
          >
            <p className="px-4 pt-3.5 pb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--gob-muted)]">
              Avisos
            </p>
            {avisos.length === 0 ? (
              <p className="px-4 pb-4 text-sm text-[var(--gob-muted)]">
                No tienes avisos. Aquí te diré cuando Todd revise un documento o el plan necesite tu atención.
              </p>
            ) : (
              <ul className="list-none m-0 p-0 pb-2">
                {avisos.map(a => {
                  const contenido = (
                    <>
                      <a.Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: a.color }} />
                      <span className="min-w-0 flex-1 space-y-0.5">
                        <span className="block text-[13px] leading-snug text-[var(--gob-ink)]">{a.titulo}</span>
                        {a.detalle && <span className="block text-xs leading-snug text-[var(--gob-muted)]">{a.detalle}</span>}
                        {a.fecha && <span className="block text-[11px] text-[var(--gob-stone)]">{haceCuanto(a.fecha)}</span>}
                      </span>
                      {nuevos.has(a.clave) && (
                        <span aria-label="Nuevo" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#C2410C]" />
                      )}
                      {a.accion && <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-[var(--gob-stone)]" />}
                    </>
                  )
                  const fila = "flex w-full items-start gap-2.5 px-4 py-2.5 text-left"
                  return (
                    <li key={a.clave} className="border-t border-[var(--gob-rule)]/60 first:border-t-0">
                      {a.accion ? (
                        <button type="button" onClick={() => { setOpen(false); a.accion?.() }}
                          className={`${fila} hover:bg-[var(--gob-paper)] transition-colors focus-visible:outline-none focus-visible:bg-[var(--gob-paper)]`}>
                          {contenido}
                        </button>
                      ) : (
                        <div className={fila}>{contenido}</div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
