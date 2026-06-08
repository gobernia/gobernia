// Formato de números es-MX: separadores de miles, moneda y unidades de KPI.

const MONEY_UNITS = new Set(["mxn", "$", "pesos", "peso"])

/** Número con separadores de miles (es-MX), hasta 2 decimales. "" si no hay valor. */
export function formatNumber(n: number | string | null | undefined): string {
  if (n === null || n === undefined || n === "") return ""
  const num = typeof n === "string" ? parseFloat(n) : n
  if (Number.isNaN(num)) return String(n)
  return num.toLocaleString("es-MX", { maximumFractionDigits: 2 })
}

/** Valor de un KPI formateado según su unidad: $…MXN, 15%, 45 días, 1.5x, 120. */
export function formatKpiValue(
  value: number | string | null | undefined,
  unit?: string | null,
): string {
  if (value === null || value === undefined || value === "") return "—"
  const num = typeof value === "string" ? parseFloat(value) : value
  if (Number.isNaN(num)) return String(value)
  const u = (unit ?? "").trim()
  const ul = u.toLowerCase()
  if (MONEY_UNITS.has(ul)) return `$${formatNumber(num)} MXN`
  if (ul === "usd") return `$${formatNumber(num)} USD`
  if (u === "%") return `${formatNumber(num)}%`
  if (!u) return formatNumber(num)
  return `${formatNumber(num)} ${u}` // x, días, #, etc.
}

/** ¿La unidad representa dinero? (para anteponer "$" en inputs) */
export function isMoneyUnit(unit?: string | null): boolean {
  const ul = (unit ?? "").trim().toLowerCase()
  return MONEY_UNITS.has(ul) || ul === "usd"
}

/**
 * Formatea lo que el usuario teclea en un input numérico: agrega separadores de
 * miles conforme escribe, conserva (un) punto decimal y hasta 2 decimales.
 * Devuelve el texto a mostrar. Para el valor crudo usar parseNumberInput().
 */
export function formatNumberInput(raw: string): string {
  const cleaned = raw.replace(/[^\d.]/g, "")
  if (cleaned === "") return ""
  const firstDot = cleaned.indexOf(".")
  if (firstDot === -1) {
    return Number(cleaned).toLocaleString("es-MX")
  }
  const intPart = cleaned.slice(0, firstDot)
  const decPart = cleaned.slice(firstDot + 1).replace(/\./g, "").slice(0, 2)
  const intFmt = intPart === "" ? "0" : Number(intPart).toLocaleString("es-MX")
  return `${intFmt}.${decPart}`
}

/** Convierte el texto formateado de un input al valor crudo (solo dígitos y punto). */
export function parseNumberInput(formatted: string): string {
  const cleaned = formatted.replace(/[^\d.]/g, "")
  const firstDot = cleaned.indexOf(".")
  if (firstDot === -1) return cleaned
  return cleaned.slice(0, firstDot + 1) + cleaned.slice(firstDot + 1).replace(/\./g, "")
}
