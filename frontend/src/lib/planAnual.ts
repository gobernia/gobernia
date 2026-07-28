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

// ── Orden del día (cadena): documentos solicitados por prioridad ──────────────
// Por cada prioridad aprobada, los documentos (`required_doc` de sus tareas) que
// la sustentan, deduplicados y contados. Empata con cada punto por `indice`.

/** Un documento pedido por una prioridad, con cuántas tareas lo solicitan. */
export interface DocSolicitado {
  doc: string
  n_tareas: number
}

// ── Análisis del punto (formato fijo, calculado en el backend de forma determinista) ──

/** Qué se esperaba: la meta (metas de los KPIs unidas) y cuántas tareas se planearon. */
export interface QueSeEsperaba {
  meta: string
  tareas_planeadas: number
}

/** Qué ocurrió: avance de tareas por status + los KPIs (actual→meta). */
export interface QueOcurrio {
  hechas: number
  en_proceso: number
  pendientes: number
  kpis: Array<Record<string, unknown>>
}

/** Evidencia: cuántos documentos (filas Evidence) se subieron para esta prioridad. */
export interface Evidencia {
  documentos_subidos: number
}

/** Desviación: tareas vencidas e indicadores sin dato. */
export interface Desviacion {
  tareas_vencidas: number
  kpis_sin_dato: number
}

/** El análisis fijo de un punto (formato del PDF), sin IA. */
export interface AnalisisPunto {
  que_se_esperaba: QueSeEsperaba
  que_ocurrio: QueOcurrio
  evidencia: Evidencia
  desviacion: Desviacion
  /** Lo que documenta la administración en la sesión; null por ahora (placeholder). */
  explicacion: string | null
  decision_sugerida: string
}

/** Un punto de la cadena = una prioridad aprobada + sus documentos solicitados. */
export interface PuntoCadena {
  indice: number
  nombre: string
  objetivo: string
  kpis: Array<Record<string, unknown>>
  estrategias: string[]
  documentos_solicitados: DocSolicitado[]
  n_tareas: number
  analisis: AnalisisPunto
}

export interface OrdenCadena {
  aprobado: boolean
  anio: number
  puntos: PuntoCadena[]
}

const EMPTY_CADENA: OrdenCadena = {
  aprobado: false,
  anio: new Date().getFullYear(),
  puntos: [],
}

/** Análisis por defecto: todo en 0 / "" cuando el backend aún no lo manda. */
function defaultAnalisis(): AnalisisPunto {
  return {
    que_se_esperaba: { meta: "", tareas_planeadas: 0 },
    que_ocurrio: { hechas: 0, en_proceso: 0, pendientes: 0, kpis: [] },
    evidencia: { documentos_subidos: 0 },
    desviacion: { tareas_vencidas: 0, kpis_sin_dato: 0 },
    explicacion: null,
    decision_sugerida: "",
  }
}

function normalizeAnalisis(a: Partial<AnalisisPunto> | undefined): AnalisisPunto {
  const d = defaultAnalisis()
  if (!a) return d
  return {
    que_se_esperaba: {
      meta: a.que_se_esperaba?.meta ?? d.que_se_esperaba.meta,
      tareas_planeadas: a.que_se_esperaba?.tareas_planeadas ?? d.que_se_esperaba.tareas_planeadas,
    },
    que_ocurrio: {
      hechas: a.que_ocurrio?.hechas ?? d.que_ocurrio.hechas,
      en_proceso: a.que_ocurrio?.en_proceso ?? d.que_ocurrio.en_proceso,
      pendientes: a.que_ocurrio?.pendientes ?? d.que_ocurrio.pendientes,
      kpis: a.que_ocurrio?.kpis ?? d.que_ocurrio.kpis,
    },
    evidencia: { documentos_subidos: a.evidencia?.documentos_subidos ?? d.evidencia.documentos_subidos },
    desviacion: {
      tareas_vencidas: a.desviacion?.tareas_vencidas ?? d.desviacion.tareas_vencidas,
      kpis_sin_dato: a.desviacion?.kpis_sin_dato ?? d.desviacion.kpis_sin_dato,
    },
    explicacion: a.explicacion ?? null,
    decision_sugerida: a.decision_sugerida ?? d.decision_sugerida,
  }
}

function normalizeCadena(data: Partial<OrdenCadena> | undefined): OrdenCadena {
  return {
    ...EMPTY_CADENA,
    ...(data || {}),
    puntos: (data?.puntos ?? []).map(p => ({
      indice: p.indice,
      nombre: p.nombre ?? "",
      objetivo: p.objetivo ?? "",
      kpis: p.kpis ?? [],
      estrategias: p.estrategias ?? [],
      documentos_solicitados: p.documentos_solicitados ?? [],
      n_tareas: p.n_tareas ?? 0,
      analisis: normalizeAnalisis(p.analisis),
    })),
  }
}

/**
 * Los documentos solicitados por cada prioridad aprobada. Empata por `indice`
 * con los puntos de la orden del día.
 */
export async function getOrdenCadena(): Promise<OrdenCadena> {
  const r = await api.get<Partial<OrdenCadena>>("/annual-plan/orden-del-dia-cadena")
  return normalizeCadena(r.data)
}
