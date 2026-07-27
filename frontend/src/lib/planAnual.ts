// frontend/src/lib/planAnual.ts
//
// El "Plan anual" es el mecanismo: de las prioridades del Roadmap (3 años), el
// Consejo elige y APRUEBA entre 3 y 5 para trabajar el año en curso. Solo a esas
// se les da seguimiento cada mes en el Board IA.
//
// El backend implementa el contrato; aquí solo lo consumimos.
import api from "@/lib/api"

/** Indicador de un pilar: valor de hoy → meta. `meta` puede venir vacía ("por definir"). */
export interface KpiPilarAnual { label: string; actual: string; meta: string }

/**
 * Una prioridad candidata (o aprobada) para el Plan anual. Es un pilar del Roadmap
 * con un `indice` estable que identifica al pilar para aprobarlo/quitarlo.
 */
export interface PilarAnual {
  indice: number
  nombre: string
  descripcion: string
  objetivo: string
  kpis: KpiPilarAnual[]
  estrategias: string[]
}

export interface PlanAnual {
  anio: number
  aprobado: boolean
  aprobado_at: string | null
  /** Todas las prioridades del Roadmap entre las que se elige. */
  pilares_disponibles: PilarAnual[]
  /** Las 3–5 prioridades que quedaron aprobadas para el año. */
  pilares_aprobados: PilarAnual[]
}

const EMPTY: PlanAnual = {
  anio: new Date().getFullYear(),
  aprobado: false,
  aprobado_at: null,
  pilares_disponibles: [],
  pilares_aprobados: [],
}

function normalize(data: Partial<PlanAnual> | undefined): PlanAnual {
  return {
    ...EMPTY,
    ...(data || {}),
    pilares_disponibles: data?.pilares_disponibles ?? [],
    pilares_aprobados: data?.pilares_aprobados ?? [],
  }
}

export async function getPlanAnual(): Promise<PlanAnual> {
  const r = await api.get<Partial<PlanAnual>>("/annual-plan/plan-anual")
  return normalize(r.data)
}

/**
 * Aprueba el Plan anual con las prioridades elegidas (por `indice`). Deben ser 3–5;
 * si no, el backend responde 400 con `detail`, que el llamador debe mostrar.
 */
export async function aprobarPlanAnual(indices: number[]): Promise<PlanAnual> {
  const r = await api.post<Partial<PlanAnual>>("/annual-plan/plan-anual/aprobar", { indices })
  return normalize(r.data)
}

/** Reabre el plan para volver a elegir prioridades (vuelve a modo selección). */
export async function reabrirPlanAnual(): Promise<PlanAnual> {
  const r = await api.post<Partial<PlanAnual>>("/annual-plan/plan-anual/reabrir")
  return normalize(r.data)
}
