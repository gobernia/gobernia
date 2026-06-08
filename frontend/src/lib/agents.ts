// Mapa de claves internas de consejero (CFO, CSO…) a su nombre visible.
// Las claves se conservan en backend/DB/chat; esto es solo para mostrar.

export const AGENT_SHORT: Record<string, string> = {
  CFO: "Finanzas",
  CSO: "Estrategia",
  CRO: "Riesgos",
  Auditor: "Auditoría",
  Retador: "Independiente",
}

export const AGENT_LABEL: Record<string, string> = {
  CFO: "Consejero en Finanzas",
  CSO: "Consejero en Estrategia",
  CRO: "Consejero en Riesgos",
  Auditor: "Consejero en Auditoría",
  Retador: "Consejero Independiente",
}

/** Nombre corto (función): "Finanzas". Útil para chips/badges. */
export const agentShort = (key?: string | null): string =>
  key ? AGENT_SHORT[key] ?? key : ""

/** Nombre completo: "Consejero en Finanzas". Útil para prosa. */
export const agentLabel = (key?: string | null): string =>
  key ? AGENT_LABEL[key] ?? key : ""
