"use client"

import { useState } from "react"
import { Check, Loader2, X } from "lucide-react"
import { Meta3a, KpiPilar } from "@/lib/roadmap"

/**
 * El trayecto: punto de hoy → línea → destino.
 * Sin destino la línea va punteada: el plan admite lo que todavía no está decidido.
 */
function Trayecto({ actual, definido, color = "var(--gob-navy)", destino, captionDestino }: {
  actual?: string | null
  definido: boolean
  color?: string
  /** Nodo del destino (punto lleno o botón "define la meta"). */
  destino: React.ReactNode
  captionDestino: React.ReactNode
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
        <span
          className={`h-0 min-w-6 flex-1 border-t ${definido ? "border-solid" : "border-dashed"}`}
          style={{ borderColor: definido ? color : "var(--gob-rule)" }}
          aria-hidden
        />
        {destino}
      </div>
      <div className="mt-2 flex items-start justify-between gap-4">
        <span className="text-[11px] leading-tight text-[var(--gob-muted)]">
          <span className="block text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--gob-stone)]">hoy</span>
          {actual?.trim() || "sin dato"}
        </span>
        {captionDestino}
      </div>
    </div>
  )
}

/** Punto de destino lleno (meta fijada). */
function PuntoMeta({ color }: { color: string }) {
  return <span className="h-3.5 w-3.5 shrink-0 rounded-full ring-2 ring-white" style={{ background: color }} aria-hidden />
}

/** Círculo abierto: la meta está por definir. */
function PuntoAbierto({ color }: { color: string }) {
  return (
    <span className="h-3.5 w-3.5 shrink-0 rounded-full border-2 border-dashed bg-white"
      style={{ borderColor: color }} aria-hidden />
  )
}

/**
 * Una meta a 3 años. Si no hay `target`, el destino es un botón: el dueño fija el número
 * (la IA no lo inventa). Con el roadmap validado no se puede editar.
 */
export function MetaTrayecto({ meta, indice, editable, saving, onSetTarget }: {
  meta: Meta3a
  indice: number
  editable: boolean
  saving: boolean
  onSetTarget: (valor: string) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [valor, setValor] = useState("")
  const definido = !!meta.target?.trim()

  const confirmar = () => {
    const v = valor.trim()
    if (!v) return
    onSetTarget(v)
    setAbierto(false)
    setValor("")
  }

  const destino = definido ? (
    <PuntoMeta color="var(--gob-navy)" />
  ) : editable && !abierto ? (
    <button onClick={() => setAbierto(true)}
      className="group flex shrink-0 items-center gap-2 rounded-full border border-dashed border-[var(--gob-navy)]/45 bg-white pl-1 pr-3 py-1 text-[11px] font-semibold text-[var(--gob-navy)] transition-colors hover:bg-[var(--gob-navy)]/[0.06] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
      <PuntoAbierto color="var(--gob-navy)" />
      Define la meta
    </button>
  ) : (
    <PuntoAbierto color={editable ? "var(--gob-navy)" : "var(--gob-stone)"} />
  )

  const captionDestino = definido ? (
    <span className="text-right text-[11px] font-semibold leading-tight text-[var(--gob-navy)]">
      <span className="block text-[9px] font-bold uppercase tracking-[0.14em] text-[var(--gob-navy)]/60">meta</span>
      {meta.target}
    </span>
  ) : !editable ? (
    <span className="text-right text-[11px] leading-tight text-[var(--gob-stone)]">
      <span className="block text-[9px] font-bold uppercase tracking-[0.14em]">meta</span>
      por definir
    </span>
  ) : null

  return (
    <li className="grid items-center gap-x-8 gap-y-4 border-t border-[var(--gob-rule)] py-5 sm:grid-cols-[minmax(0,1fr)_minmax(15rem,22rem)]">
      <div className="min-w-0">
        <div className="flex items-start gap-3">
          <span className="mt-[3px] text-[11px] font-bold tabular-nums text-[var(--gob-stone)]">
            {String(indice + 1).padStart(2, "0")}
          </span>
          <div className="min-w-0 space-y-1">
            <p className="text-[15px] font-medium leading-snug text-[var(--gob-ink)]">{meta.meta}</p>
            {meta.kpi && (
              <p className="text-xs text-[var(--gob-muted)]">
                <span className="font-semibold text-[var(--gob-stone)]">KPI</span> · {meta.kpi}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="min-w-0">
        <Trayecto actual={meta.valor_actual} definido={definido} destino={destino} captionDestino={captionDestino} />
        {abierto && (
          <div className="mt-3 flex items-center gap-2">
            <input autoFocus value={valor} onChange={e => setValor(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") confirmar(); if (e.key === "Escape") setAbierto(false) }}
              placeholder="¿A cuánto quieres llegar?" aria-label="Meta objetivo"
              className="min-w-0 flex-1 rounded-lg border-2 border-[var(--gob-navy)]/30 px-3 py-1.5 text-sm focus:border-[var(--gob-navy)] focus:outline-none" />
            <button onClick={confirmar} disabled={saving || !valor.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--gob-navy)] px-3 py-2 text-xs font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Fijar
            </button>
            <button onClick={() => { setAbierto(false); setValor("") }} aria-label="Cancelar"
              className="rounded p-1 text-[var(--gob-stone)] hover:text-[var(--gob-ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gob-navy)]">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </li>
  )
}

/** El mismo lenguaje visual, compacto, para los KPIs de un pilar. */
export function KpiTrayecto({ kpi, color }: { kpi: KpiPilar; color: string }) {
  const definido = !!kpi.meta?.trim()
  return (
    <li className="grid items-center gap-x-6 gap-y-2 border-t border-[var(--gob-rule)] py-3 sm:grid-cols-[minmax(0,1fr)_minmax(11rem,15rem)]">
      <p className="text-[13px] font-medium leading-snug text-[var(--gob-ink)]">{kpi.label}</p>
      <Trayecto
        actual={kpi.actual}
        definido={definido}
        color={color}
        destino={definido ? <PuntoMeta color={color} /> : <PuntoAbierto color="var(--gob-stone)" />}
        captionDestino={
          <span className="text-right text-[11px] leading-tight" style={{ color: definido ? color : "var(--gob-stone)" }}>
            <span className="block text-[9px] font-bold uppercase tracking-[0.14em] opacity-70">meta</span>
            <span className={definido ? "font-semibold" : ""}>{definido ? kpi.meta : "por definir"}</span>
          </span>
        }
      />
    </li>
  )
}
