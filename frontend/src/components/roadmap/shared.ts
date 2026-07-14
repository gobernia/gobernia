// Piezas compartidas del expediente del consejo (vista Roadmap).
import { Roadmap, KpiPilar, ResultadoEsperado } from "@/lib/roadmap"

/** Acentos por pilar (muteados, on-brand). Se usan como hex en `style`, nunca como clase dinámica. */
export const PILAR_COLORS = ["#1e3a5f", "#0f766e", "#b45309", "#6d28d9", "#b91c1c", "#334155"]
export const pilarColor = (i: number) => PILAR_COLORS[i % PILAR_COLORS.length]

export const ANIO_KEYS = ["anio1", "anio2", "anio3"] as const
export type AnioKey = (typeof ANIO_KEYS)[number]

export const splitLines = (s: string): string[] => s.split("\n").map(x => x.trim()).filter(Boolean)
export const joinLines = (arr: string[] | undefined | null): string => (arr ?? []).join("\n")

export function roadmapIsEmpty(r: Roadmap): boolean {
  return !r.vision && !r.mision && !r.propuesta_valor && !r.resumen_foda && !r.resumen_entorno &&
    (r.metas_3anios?.length ?? 0) === 0 && (r.pilares?.length ?? 0) === 0
}

export const KPI_SLOTS = 3
export const RESULTADO_SLOTS = 3
export const emptyKpi = (): KpiPilar => ({ label: "", actual: "", meta: "" })
export const emptyResultado = (): ResultadoEsperado => ({ titulo: "", descripcion: "" })

/** Rellena la lista hasta `n` huecos para poder capturar filas nuevas en el formulario. */
export function padSlots<T>(arr: T[] | undefined | null, n: number, make: () => T): T[] {
  const base = (arr ?? []).slice(0, n).map(x => ({ ...x }))
  while (base.length < n) base.push(make())
  return base
}

/** El año 3 es el año objetivo; si no hay, se asume que el año 1 es el año en curso. */
export function aniosDelPlan(anioObjetivo?: number): [number, number, number] {
  const a3 = anioObjetivo && anioObjetivo > 2000 ? anioObjetivo : new Date().getFullYear() + 2
  return [a3 - 2, a3 - 1, a3]
}

/** Props comunes de cada sección editable del documento. */
export interface SeccionProps {
  roadmap: Roadmap
  editing: string | null
  setEditing: (key: string | null) => void
  saving: boolean
  validado: boolean
  /** Guarda el roadmap completo; al terminar bien, el documento cierra el modo edición. */
  onSave: (next: Roadmap) => void
}

/** Secciones del índice del documento, en el orden en que se leen. */
export const DOC_SECCIONES = [
  { id: "vision", label: "Visión y propuesta" },
  { id: "metas", label: "Metas a 3 años" },
  { id: "pilares", label: "Pilares" },
  { id: "mapa", label: "Mapa de ejecución" },
  { id: "contexto", label: "Contexto" },
] as const
