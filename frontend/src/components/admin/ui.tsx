// Piezas comunes del panel de super admin (bento: tarjetas blancas sobre papel).
import type { ButtonHTMLAttributes, ReactNode } from "react"
import { B, SANS } from "@/components/blog/tokens"

export { B, SANS }

export function fecha(iso: string | null): string {
  if (!iso) return "—"
  // Una fecha sola (AAAA-MM-DD) se lee como local, no como UTC del día anterior.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T12:00:00`) : new Date(iso)
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })
}

export function Metrica({ label, valor, sub }: { label: string; valor: number | string; sub?: string }) {
  return (
    <div className="rounded-[26px] p-5" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
      <p className="text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ ...SANS, color: B.MUTED }}>{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums" style={{ ...SANS, color: B.INK }}>{valor}</p>
      {sub && <p className="mt-1 text-xs" style={{ color: B.MUTED }}>{sub}</p>}
    </div>
  )
}

export function Tarjeta({ titulo, sub, acciones, children, className = "" }: {
  titulo: string; sub?: ReactNode; acciones?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`rounded-[26px] p-6 space-y-4 ${className}`} style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold" style={{ ...SANS, color: B.INK }}>{titulo}</h2>
          {sub && <p className="text-xs mt-0.5" style={{ color: B.MUTED }}>{sub}</p>}
        </div>
        {acciones}
      </div>
      {children}
    </section>
  )
}

export function Campo({ label, ayuda, children }: { label: string; ayuda?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-bold uppercase tracking-[0.1em]" style={{ ...SANS, color: B.MUTED }}>{label}</span>
      {children}
      {ayuda && <span className="block text-[11px]" style={{ color: B.MUTED }}>{ayuda}</span>}
    </label>
  )
}

export const INPUT = "w-full rounded-[14px] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#152742]/20"
export const INPUT_STYLE = { background: B.CARD, border: `1px solid ${B.LINE}`, color: B.INK }

export function Boton({ children, variante = "primario", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variante?: "primario" | "secundario" }) {
  const estilo = variante === "primario"
    ? { ...SANS, background: B.BNAVY, color: "#fff" }
    : { ...SANS, background: B.CARD, color: B.INK, border: `1px solid ${B.LINE}` }
  return (
    <button type="button" {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-[14px] px-4 py-2 text-sm font-bold transition hover:brightness-95 disabled:opacity-50 ${className}`}
      style={estilo}>
      {children}
    </button>
  )
}

export function Etiqueta({ children, tono = "navy" }: { children: ReactNode; tono?: "navy" | "verde" | "ambar" | "gris" | "rojo" }) {
  const colores = {
    navy: [`${B.BNAVY}12`, B.BNAVY],
    verde: ["#15803D18", "#15803D"],
    ambar: ["#B4530918", "#B45309"],
    gris: ["#6E768614", B.MUTED],
    rojo: ["#B91C1C14", "#B91C1C"],
  }[tono]
  return (
    <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
      style={{ background: colores[0], color: colores[1] }}>{children}</span>
  )
}

/** Tabla con el encabezado arena del panel. */
export function Tabla({ columnas, children, vacio, minW = 720 }: {
  columnas: string[]; children: ReactNode; vacio?: boolean; minW?: number
}) {
  return (
    <div className="overflow-x-auto rounded-[18px]" style={{ border: `1px solid ${B.LINE}` }}>
      <table className="w-full text-sm" style={{ minWidth: minW }}>
        <thead>
          <tr style={{ background: B.SAND }}>
            {columnas.map(h => (
              <th key={h} className="px-4 py-2.5 text-left text-[10px] font-extrabold uppercase tracking-[0.12em]"
                style={{ ...SANS, color: B.MUTED }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {children}
          {vacio && (
            <tr><td colSpan={columnas.length} className="px-4 py-8 text-center text-sm" style={{ color: B.MUTED }}>Nada todavía.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
