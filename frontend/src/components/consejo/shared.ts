/**
 * Piezas compartidas de la sesión de consejo.
 *
 * El Consejo habla con UNA voz: la conclusión manda y los acuerdos son el entregable.
 * Las cuatro voces individuales quedan como auditoría de la deliberación.
 */
import { PILAR_COLORS, pilarColor } from "@/components/roadmap/shared"

// ── Los cuatro consejeros ─────────────────────────────────
export const AGENTS = [
  { id: "CFO",     role: "Finanzas" },
  { id: "CSO",     role: "Estrategia" },
  { id: "CRO",     role: "Riesgos" },
  { id: "Auditor", role: "Auditoría" },
] as const

// ── Semáforo ──────────────────────────────────────────────
// Tailwind v4 no detecta clases dinámicas: colores literales en `style`.
export type AlertLevel = "rojo" | "ambar" | "verde"

export const ALERT_COLOR: Record<AlertLevel, string> = {
  rojo:  "#b91c1c",
  ambar: "#b45309",
  verde: "#0f766e",
}
export const ALERT_ORDER: Record<AlertLevel, number> = { rojo: 0, ambar: 1, verde: 2 }
// El semáforo también se lee sin color (lectores de pantalla).
export const ALERT_LABEL: Record<AlertLevel, string> = {
  rojo: "Alerta crítica", ambar: "Alerta media", verde: "En orden",
}

// ── Análisis de cada consejero ────────────────────────────
export interface Finding {
  texto: string
  fuente?: string
}

export interface Alert {
  nivel: AlertLevel
  texto: string
  fuente?: string
}

export interface Analysis {
  summary: string
  // La API normaliza a objetos, pero toleramos strings de sesiones antiguas.
  findings: (Finding | string)[]
  alerts: (Alert | string)[]
  recommendations: string[]
  preguntas?: string[]
  // El consejero no pudo leer los documentos y se analizó sin ellos.
  _documentos_omitidos?: boolean
}

/** Normaliza un hallazgo: acepta string suelto sin reventar. */
export function toFinding(f: Finding | string | null | undefined): Finding {
  if (typeof f === "string") return { texto: f, fuente: "" }
  return { texto: f?.texto ?? "", fuente: f?.fuente ?? "" }
}

/** Normaliza una alerta: acepta string suelto y nivel desconocido. */
export function toAlert(a: Alert | string | null | undefined): Alert {
  if (typeof a === "string") return { nivel: "ambar", texto: a, fuente: "" }
  const nivel = a?.nivel
  return {
    nivel: nivel && nivel in ALERT_COLOR ? nivel : "ambar",
    texto: a?.texto ?? "",
    fuente: a?.fuente ?? "",
  }
}

// ── La conclusión del Consejo ─────────────────────────────
export type Prioridad = "alta" | "media" | "baja"

/** Un acuerdo es un Compromiso real, ya persistido: se puede editar con PATCH /pm/compromisos/{id}. */
export interface Acuerdo {
  id: string
  texto: string
  /** La IA propone un ROL ("Dirección General"); el dueño le pone nombre y correo. */
  responsable_sugerido: string
  responsable_nombre?: string | null
  responsable_email?: string | null
  fecha_compromiso: string
  prioridad: Prioridad
  /** Pilar del Roadmap al que sirve. Vacío = transversal. */
  pilar: string
  racional: string
  status: string
}

export interface Riesgo {
  nivel: AlertLevel
  texto: string
  fuente?: string
}

export interface Conclusion {
  conclusion: string
  avance_roadmap: string
  riesgos: (Riesgo | string)[]
  acuerdos: Acuerdo[]
}

/** Normaliza un riesgo de la conclusión (mismo semáforo que las alertas). */
export function toRiesgo(r: Riesgo | string | null | undefined): Riesgo {
  return toAlert(r as Alert | string | null | undefined)
}

export const PRIORIDADES: Prioridad[] = ["alta", "media", "baja"]

export const PRIORIDAD_COLOR: Record<Prioridad, string> = {
  alta:  "#b91c1c",
  media: "#b45309",
  baja:  "#6C6A66",
}

export const PRIORIDAD_LABEL: Record<Prioridad, string> = {
  alta: "Prioridad alta", media: "Prioridad media", baja: "Prioridad baja",
}

export function toPrioridad(p: string | null | undefined): Prioridad {
  return p === "alta" || p === "media" || p === "baja" ? p : "media"
}

const norm = (s: string) => s.trim().toLowerCase()

/**
 * Color del chip del pilar. Si el pilar existe en el Roadmap, usa SU color (mismo índice que
 * el documento, para que la vista del consejo y la del plan hablen el mismo idioma). Si no lo
 * encuentra, cae a un índice estable derivado del nombre: nunca cambia entre renders.
 */
export function colorDePilar(pilar: string, pilaresDelRoadmap: string[]): string {
  const i = pilaresDelRoadmap.findIndex(p => norm(p) === norm(pilar))
  if (i >= 0) return pilarColor(i)
  let h = 0
  for (const ch of pilar) h = (h * 31 + ch.charCodeAt(0)) % 997
  return PILAR_COLORS[h % PILAR_COLORS.length]
}

/** Fecha corta y legible; si viene basura, no rompe la fila. */
export function formatFecha(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })
}

/** `<input type="date">` sólo acepta YYYY-MM-DD. */
export function fechaInput(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toISOString().slice(0, 10)
}
