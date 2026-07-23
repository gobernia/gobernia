"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Loader2, ChevronDown, Check, ArrowRight, Gavel, CornerDownRight, UserPlus, X,
  Upload, Paperclip, Download, Trash2, ShieldCheck, AlertTriangle, Clock, Info,
} from "lucide-react"
import {
  BoardMes, BoardTask, TaskStatus, Validacion, ValidacionEstado,
  getBoard, setTaskEstado, setTaskOwner, abrirSesionMes,
} from "@/lib/board"
import {
  Evidence, getEvidence, uploadEvidence, deleteEvidence, downloadEvidenceUrl,
} from "@/lib/evidence"

/**
 * El tablero tipo Monday del plan mensual, en la paleta sobria de Gobernia.
 *
 * Estructura de Monday con colores de Gobernia: rejilla real (líneas verticales y
 * horizontales), columnas con sombreado alterno para que cada una "se note", la celda
 * de Estado rellena del color del estado (editable, optimista) y la de Responsable
 * editable con popover (input prellenado + chips de responsables ya usados).
 */

// ── Estado: etiqueta + color sobrio (hex literal; Tailwind v4 no ve clases dinámicas) ──
const ESTADOS: TaskStatus[] = ["pendiente", "en_progreso", "completada"]

const ESTADO_LABEL: Record<TaskStatus, string> = {
  pendiente:   "Aún sin ejecutar",
  en_progreso: "En proceso",
  completada:  "Hecho",
}

const ESTADO_COLOR: Record<TaskStatus, string> = {
  pendiente:   "#8E8B84", // --gob-stone
  en_progreso: "#b45309", // ámbar
  completada:  "#0f766e", // verde
}

// ── Filete de color por grupo de mes: paleta rotatoria sobria (navy y variantes) ──
// Array literal de hex — NADA dinámico por el JIT de Tailwind.
const FILETE = ["#142849", "#3a4a63", "#26282E", "#5a6b82", "#1f3a5f", "#4a5568"]

const filete = (i: number) => FILETE[i % FILETE.length]

// ── Rejilla de columnas: mismo template en encabezado y filas ──
// Tablero ancho tipo Monday: la 1ª (Tarea) queda congelada y respira; las demás
// tienen ancho fijo y se desplazan en horizontal dentro del contenedor de la tabla.
const GRID_COLS = "md:grid-cols-[minmax(260px,1fr)_220px_200px_120px_120px_260px]"
// Ancho mínimo de la rejilla: fuerza el scroll horizontal cuando el tablero aprieta.
const GRID_MINW = "md:min-w-[1180px]"

// Sombreado alterno de columnas (efecto Monday, tonos Gobernia).
// Literales para el JIT: blanco / gris tenue (--gob-paper). Estado va aparte (color).
const BG_WHITE = "md:bg-white"
const BG_ALT = "md:bg-[#FBF8F3]"

// La columna Tarea queda fija a la izquierda (sticky) con fondo sólido y un corte
// (borde + sombra) para marcar el congelado mientras el resto se desplaza. Solo en
// desktop; en móvil el layout de bloque no necesita congelar nada.
const STICKY_TAREA = "md:sticky md:left-0 md:z-[15] md:shadow-[6px_0_10px_-8px_rgba(20,40,73,0.22)]"

// ── Fecha corta es-MX ("15 mar") ──
function venceCorto(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short" })
}

// ── Iniciales del responsable ──
function iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return "?"
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase()
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase()
}

// ── Prioridad: 3 barras discretas (alta 3 · media 2 · baja 1) ──
const PRIORIDAD_LLENAS: Record<BoardTask["priority"], number> = { alta: 3, media: 2, baja: 1 }
const PRIORIDAD_LABEL: Record<BoardTask["priority"], string> = {
  alta: "Prioridad alta", media: "Prioridad media", baja: "Prioridad baja",
}

function Prioridad({ nivel }: { nivel: BoardTask["priority"] }) {
  const llenas = PRIORIDAD_LLENAS[nivel]
  return (
    <span className="inline-flex items-end gap-0.5" role="img" aria-label={PRIORIDAD_LABEL[nivel]} title={PRIORIDAD_LABEL[nivel]}>
      {[0, 1, 2].map(i => (
        <span key={i} className="w-1 rounded-full"
          style={{ height: 7 + i * 4, backgroundColor: i < llenas ? "#142849" : "#D9D4CB" }} />
      ))}
    </span>
  )
}

// ── Celda de Responsable, editable con popover ──
function ResponsableCelda({ owner, sugerencias, onChange }: {
  owner: string | null
  sugerencias: string[]
  onChange: (owner: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [valor, setValor] = useState(owner ?? "")

  const abrir = () => { setValor(owner ?? ""); setOpen(true) }
  const cerrar = () => setOpen(false)
  const confirmar = (v: string) => {
    const nuevo = v.trim()
    setOpen(false)
    if (nuevo && nuevo !== (owner ?? "")) onChange(nuevo)
  }

  // Chips de acceso rápido: responsables ya usados, sin el actual.
  const chips = sugerencias.filter(s => s !== owner)

  return (
    <div className="relative min-w-0 w-full">
      <button type="button" onClick={abrir}
        aria-haspopup="dialog" aria-expanded={open}
        aria-label={owner ? `Responsable: ${owner}. Cambiar responsable` : "Sin asignar. Asignar responsable"}
        className="group inline-flex items-center gap-2 min-w-0 max-w-full rounded-lg -mx-1.5 px-1.5 py-1 text-left hover:bg-[var(--gob-bone)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)]">
        {owner ? (
          <>
            <span className="h-6 w-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-[10px] font-bold flex items-center justify-center shrink-0">
              {iniciales(owner)}
            </span>
            <span className="text-sm text-[var(--gob-charcoal)] truncate">{owner}</span>
          </>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs text-[var(--gob-stone)] group-hover:text-[var(--gob-muted)]">
            <UserPlus className="h-3.5 w-3.5" />
            Sin asignar
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Cierre al hacer clic fuera */}
          <button type="button" aria-hidden tabIndex={-1}
            className="fixed inset-0 z-20 cursor-default" onClick={cerrar} />
          <div role="dialog" aria-label="Editar responsable"
            className="absolute z-30 mt-1 left-0 w-64 rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] shadow-lg p-3 space-y-2.5">
            <input
              autoFocus
              value={valor}
              onChange={e => setValor(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") { e.preventDefault(); confirmar(valor) }
                else if (e.key === "Escape") { e.preventDefault(); cerrar() }
              }}
              placeholder="Nombre del responsable"
              className="w-full rounded-lg border border-[var(--gob-rule)] bg-white px-2.5 py-2 text-sm text-[var(--gob-ink)] placeholder:text-[var(--gob-stone)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)]"
            />

            {chips.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)]">Del tablero</p>
                <div className="flex flex-wrap gap-1.5">
                  {chips.map(c => (
                    <button key={c} type="button" onClick={() => confirmar(c)}
                      className="inline-flex items-center gap-1 rounded-full border border-[var(--gob-rule)] bg-white px-2 py-1 text-xs text-[var(--gob-charcoal)] hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors">
                      <span className="h-4 w-4 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-[8px] font-bold flex items-center justify-center shrink-0">
                        {iniciales(c)}
                      </span>
                      <span className="truncate max-w-[8rem]">{c}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 pt-0.5">
              <button type="button" onClick={() => confirmar(valor)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--gob-ink)] transition-colors">
                <Check className="h-3.5 w-3.5" />
                Asignar
              </button>
              <button type="button" onClick={cerrar}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--gob-rule)] text-[var(--gob-muted)] px-3 py-1.5 text-xs font-medium hover:border-[var(--gob-stone)] hover:text-[var(--gob-ink)] transition-colors">
                <X className="h-3.5 w-3.5" />
                Cancelar
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Celda de Estado tipo Monday: rellena del color del estado, editable (optimista) ──
function EstadoCelda({ status, onChange }: { status: TaskStatus; onChange: (s: TaskStatus) => void }) {
  const [open, setOpen] = useState(false)
  const color = ESTADO_COLOR[status]

  return (
    <div className="relative h-full">
      <button type="button" onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox" aria-expanded={open}
        aria-label={`Estado: ${ESTADO_LABEL[status]}. Cambiar estado`}
        className="w-full h-full min-h-[3.25rem] flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--gob-navy)]"
        style={{ color, backgroundColor: `${color}22` }}>
        <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
        <span className="flex-1 text-left truncate">{ESTADO_LABEL[status]}</span>
        <ChevronDown className="h-3.5 w-3.5 opacity-60 shrink-0" />
      </button>

      {open && (
        <>
          {/* Cierre al hacer clic fuera */}
          <button type="button" aria-hidden tabIndex={-1}
            className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <ul role="listbox" aria-label="Estados"
            className="absolute z-30 mt-1 left-3 min-w-[184px] rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] shadow-lg py-1">
            {ESTADOS.map(s => (
              <li key={s} role="option" aria-selected={s === status}>
                <button type="button"
                  onClick={() => { setOpen(false); if (s !== status) onChange(s) }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-left hover:bg-[var(--gob-bone)] transition-colors focus-visible:outline-none focus-visible:bg-[var(--gob-bone)]">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: ESTADO_COLOR[s] }} />
                  <span className="flex-1" style={{ color: ESTADO_COLOR[s] }}>{ESTADO_LABEL[s]}</span>
                  {s === status && <Check className="h-3.5 w-3.5 text-[var(--gob-muted)]" />}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

// ── Etiqueta de columna en móvil (bloque) ──
function EtiquetaMovil({ children }: { children: string }) {
  return (
    <span className="md:hidden text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)] w-20 shrink-0">
      {children}
    </span>
  )
}

// ── Lee el mensaje de error legible del backend (err.response.data.detail) ──
function detalleError(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

// ── Badge de validación del Consejo ──
// La validación la hace el Consejo al sesionar el mes; aquí solo se muestra su resultado.
const VALIDACION: Record<ValidacionEstado, {
  color: string; label: string; Icon: typeof ShieldCheck
}> = {
  validada:     { color: "#0f766e", label: "Validada por el Consejo", Icon: ShieldCheck },
  insuficiente: { color: "#b45309", label: "Falta sustento",          Icon: AlertTriangle },
  sin_revisar:  { color: "#8E8B84", label: "Sin revisar",             Icon: Clock },
}

function ValidacionBadge({ validacion, tieneEvidencia }: {
  validacion?: Validacion | null
  tieneEvidencia: boolean
}) {
  const estado: ValidacionEstado = validacion?.estado ?? "sin_revisar"
  // Sin evidencia y sin revisar: no ensuciamos la celda con un badge vacío.
  if (estado === "sin_revisar" && !tieneEvidencia) return null

  const { color, label, Icon } = VALIDACION[estado]
  const motivo = validacion?.motivo?.trim()

  return (
    <span className="inline-flex flex-col gap-0.5 min-w-0">
      <span
        title={motivo || label}
        className="inline-flex items-center gap-1 self-start rounded-full px-1.5 py-0.5 text-[10px] font-medium"
        style={{ color, backgroundColor: `${color}14`, border: `1px solid ${color}33` }}>
        <Icon className="h-3 w-3 shrink-0" />
        <span className="truncate">{label}</span>
      </span>
      {estado === "insuficiente" && motivo && (
        <span className="text-[10px] leading-snug text-[var(--gob-muted)] line-clamp-2">{motivo}</span>
      )}
    </span>
  )
}

// ── Celda de Documentos: subir evidencia, ver/descargar/borrar y estado de validación ──
function DocumentosCelda({ tarea, onRefresh }: {
  tarea: BoardTask
  onRefresh: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [lista, setLista] = useState<Evidence[] | null>(null)
  const [cargandoLista, setCargandoLista] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const count = tarea.evidencias ?? 0

  const subir = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true); setError(null)
    try {
      await uploadEvidence(tarea.id, file)
      setLista(null)   // invalida la lista para que se recargue al abrir el popover
      onRefresh()      // refresca el tablero para que suba el conteo
    } catch (err: unknown) {
      setError(detalleError(err) ?? "No se pudo subir el documento.")
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  const abrirLista = async () => {
    setOpen(true)
    if (lista === null) {
      setCargandoLista(true)
      try {
        setLista(await getEvidence(tarea.id))
      } catch {
        setError("No se pudieron cargar los documentos.")
      } finally {
        setCargandoLista(false)
      }
    }
  }

  const descargar = async (id: string) => {
    setError(null)
    try {
      const url = await downloadEvidenceUrl(id)
      window.open(url, "_blank", "noopener,noreferrer")
    } catch {
      setError("No se pudo abrir el documento.")
    }
  }

  const borrar = async (id: string) => {
    setError(null)
    setLista(l => (l ? l.filter(x => x.id !== id) : l))
    try {
      await deleteEvidence(id)
      onRefresh()
    } catch {
      setError("No se pudo borrar el documento.")
      setLista(null)
    }
  }

  return (
    <div className="relative flex flex-col gap-1.5 min-w-0 w-full">
      <ValidacionBadge validacion={tarea.validacion} tieneEvidencia={count > 0} />

      <div className="flex items-center gap-2 flex-wrap">
        <button type="button" disabled={busy} onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--gob-rule)] px-2 py-1 text-xs font-medium text-[var(--gob-muted)] hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)]">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {busy ? "Subiendo…" : "Subir"}
        </button>

        {count > 0 && (
          <button type="button" onClick={abrirLista}
            aria-haspopup="dialog" aria-expanded={open}
            aria-label={`Ver ${count} ${count === 1 ? "documento" : "documentos"}`}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--gob-navy)] hover:bg-[var(--gob-bone)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)]">
            <Paperclip className="h-3.5 w-3.5" />
            {count}
          </button>
        )}
      </div>

      {error && <p className="text-[10px] leading-snug" style={{ color: "#b45309" }}>{error}</p>}

      <input ref={inputRef} type="file" className="hidden" onChange={subir}
        accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.docx" />

      {open && (
        <>
          {/* Cierre al hacer clic fuera */}
          <button type="button" aria-hidden tabIndex={-1}
            className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <div role="dialog" aria-label="Documentos de la tarea"
            className="absolute z-30 mt-1 left-0 top-full w-72 rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] shadow-lg p-3 space-y-2">
            <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)]">Documentos</p>
            {cargandoLista ? (
              <div className="flex items-center justify-center py-3">
                <Loader2 className="h-4 w-4 animate-spin text-[var(--gob-stone)]" />
              </div>
            ) : (lista && lista.length > 0) ? (
              <ul className="space-y-1.5">
                {lista.map(ev => (
                  <li key={ev.id} className="flex items-center gap-2 rounded-lg bg-white border border-[var(--gob-rule)] px-2.5 py-1.5">
                    <Paperclip className="h-3.5 w-3.5 text-[var(--gob-stone)] shrink-0" />
                    <span className="flex-1 truncate text-xs text-[var(--gob-charcoal)]" title={ev.filename}>{ev.filename}</span>
                    <button type="button" onClick={() => descargar(ev.id)}
                      aria-label={`Descargar ${ev.filename}`}
                      className="text-[var(--gob-navy)] hover:text-[var(--gob-ink)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gob-navy)] rounded">
                      <Download className="h-3.5 w-3.5" />
                    </button>
                    <button type="button" onClick={() => borrar(ev.id)}
                      aria-label={`Borrar ${ev.filename}`}
                      className="text-[var(--gob-stone)] hover:text-[#b45309] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b45309] rounded">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--gob-muted)] py-1">Sin documentos todavía.</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── Una fila de tarea (rejilla en desktop, bloque en móvil) ──
function TareaRow({ tarea, sugerencias, onEstado, onOwner, onRefresh }: {
  tarea: BoardTask
  sugerencias: string[]
  onEstado: (s: TaskStatus) => void
  onOwner: (owner: string) => void
  onRefresh: () => void
}) {
  const celdaBase = "px-4 py-3 flex items-center gap-2"

  return (
    <div className={`grid grid-cols-1 ${GRID_COLS} md:gap-x-1 md:bg-[var(--gob-rule)] md:items-stretch border-b border-[var(--gob-rule)] last:border-b-0`}>
      {/* Tarea + objetivo — columna congelada a la izquierda */}
      <div className={`px-4 py-3 flex flex-col justify-center min-w-0 ${BG_WHITE} ${STICKY_TAREA}`}>
        <p className="text-sm font-medium text-[var(--gob-ink)] leading-snug">{tarea.title}</p>
        {tarea.viene_de && (
          <span className="inline-flex items-center gap-1 mt-1 self-start rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ color: "#b45309", backgroundColor: "#b4530914", border: "1px solid #b4530933" }}>
            <CornerDownRight className="h-3 w-3" />
            viene de {tarea.viene_de}
          </span>
        )}
        {tarea.objetivo && (
          <p className="text-xs text-[var(--gob-muted)] leading-snug mt-0.5 truncate">{tarea.objetivo}</p>
        )}
      </div>

      {/* Responsable (editable) */}
      <div className={`${celdaBase} ${BG_ALT}`}>
        <EtiquetaMovil>Responsable</EtiquetaMovil>
        <ResponsableCelda owner={tarea.owner} sugerencias={sugerencias} onChange={onOwner} />
      </div>

      {/* Estado (celda rellena tipo Monday) */}
      <div className="flex flex-col">
        <span className="md:hidden px-4 pt-3 text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)]">Estado</span>
        <EstadoCelda status={tarea.status} onChange={onEstado} />
      </div>

      {/* Vence */}
      <div className={`${celdaBase} ${BG_WHITE}`}>
        <EtiquetaMovil>Vence</EtiquetaMovil>
        <span className="text-sm text-[var(--gob-charcoal)]">
          {venceCorto(tarea.due_date) || <span className="text-[var(--gob-stone)]">—</span>}
        </span>
      </div>

      {/* Prioridad */}
      <div className={`px-4 py-3 flex items-center gap-2 ${BG_ALT}`}>
        <EtiquetaMovil>Prioridad</EtiquetaMovil>
        <Prioridad nivel={tarea.priority} />
      </div>

      {/* Documentos (última columna: sin filete derecho) */}
      <div className={`px-4 py-3 flex items-start gap-2 ${BG_WHITE}`}>
        <EtiquetaMovil>Documentos</EtiquetaMovil>
        <DocumentosCelda tarea={tarea} onRefresh={onRefresh} />
      </div>
    </div>
  )
}

// ── Botón "Sesionar {mes}" ──
function SesionarBtn({ label, cargando, onClick }: {
  label: string; cargando: boolean; onClick: () => void
}) {
  return (
    <button type="button" onClick={onClick} disabled={cargando}
      aria-label={`Sesionar ${label}: convocar al Consejo a evaluar este mes`}
      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--gob-rule)] px-2.5 py-1.5 text-xs font-medium text-[var(--gob-muted)] hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)] transition-colors disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-[var(--gob-navy)]">
      {cargando
        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
        : <Gavel className="h-3.5 w-3.5" />}
      Sesionar
    </button>
  )
}

// ── Encabezado de columnas (rejilla, solo desktop) ──
function EncabezadoColumnas() {
  const cols = ["Tarea", "Responsable", "Estado", "Vence", "Prioridad", "Documentos"]
  return (
    <div className={`hidden md:grid ${GRID_COLS} md:gap-x-1 bg-[var(--gob-rule)] border-b border-[var(--gob-rule)]`}>
      {cols.map((label, i) => (
        <span key={label}
          className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--gob-muted)] bg-[var(--gob-bone)] ${
            i === 0 ? STICKY_TAREA : ""}`}>
          {label}
        </span>
      ))}
    </div>
  )
}

// ── Grupo de un mes ──
function MesGrupo({ mes, index, sugerencias, onEstado, onOwner, onRefresh, onSesionar, sesionando }: {
  mes: BoardMes
  index: number
  sugerencias: string[]
  onEstado: (taskId: string, s: TaskStatus) => void
  onOwner: (taskId: string, owner: string) => void
  onRefresh: () => void
  onSesionar: () => void
  sesionando: boolean
}) {
  const arrastradas = mes.es_mes_actual ? (mes.arrastradas ?? []) : []

  return (
    <section className="rounded-2xl border border-[var(--gob-rule)] overflow-hidden bg-white"
      style={{ borderLeftWidth: 4, borderLeftColor: filete(index) }}>
      {/* Encabezado del mes */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-[var(--gob-rule)]">
        <h3 className="text-sm font-bold text-[var(--gob-ink)] tracking-tight">{mes.label}</h3>
        {mes.es_mes_actual && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)]">
            Mes actual
          </span>
        )}
        <span className="ml-auto text-xs text-[var(--gob-muted)]">
          {mes.tareas.length} {mes.tareas.length === 1 ? "tarea" : "tareas"}
        </span>
        <SesionarBtn label={mes.label} cargando={sesionando} onClick={onSesionar} />
      </header>

      {/* La rejilla vive en su propio contenedor con scroll horizontal (la columna Tarea
          queda congelada); el body de la página nunca se desplaza a los lados. */}
      <div className="md:overflow-x-auto">
        <div className={GRID_MINW}>
          {/* Subgrupo: tareas arrastradas de meses anteriores (solo mes actual) */}
          {arrastradas.length > 0 && (
            <div className="border-b border-[var(--gob-rule)]" style={{ backgroundColor: "#b4530908" }}>
              <div className="px-4 py-2">
                <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "#b45309" }}>
                  Vienen de antes
                </span>
              </div>
              <div>
                {arrastradas.map(t => (
                  <TareaRow key={t.id} tarea={t} sugerencias={sugerencias}
                    onEstado={s => onEstado(t.id, s)} onOwner={o => onOwner(t.id, o)}
                    onRefresh={onRefresh} />
                ))}
              </div>
            </div>
          )}

          {/* Encabezado de columnas */}
          <EncabezadoColumnas />

          {/* Filas */}
          <div>
            {mes.tareas.map(t => (
              <TareaRow key={t.id} tarea={t} sugerencias={sugerencias}
                onEstado={s => onEstado(t.id, s)} onOwner={o => onOwner(t.id, o)}
                onRefresh={onRefresh} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ── El tablero ──
export default function TableroPlan({ reloadSignal = 0 }: { reloadSignal?: number }) {
  const router = useRouter()
  const [meses, setMeses] = useState<BoardMes[]>([])
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  // Mes que se está sesionando (por month_index), para el estado de carga del botón.
  const [sesionandoMes, setSesionandoMes] = useState<number | null>(null)
  // Recarga interna: sube al subir/borrar documentos para refrescar conteos.
  const [tick, setTick] = useState(0)
  const aliveRef = useRef(true)

  const refrescarTablero = () => setTick(t => t + 1)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  useEffect(() => {
    getBoard()
      .then(m => {
        if (!aliveRef.current) return
        // Meses con tareas propias o con tareas arrastradas (mes actual).
        setMeses(m.filter(x => x.tareas.length > 0 || (x.arrastradas?.length ?? 0) > 0))
        setStatus("ready")
      })
      .catch(() => { if (aliveRef.current) setStatus("error") })
  }, [reloadSignal, tick])

  // Responsables ya usados en el tablero (tareas + arrastradas), únicos y no vacíos.
  const sugerencias = useMemo(() => {
    const set = new Set<string>()
    for (const mes of meses) {
      for (const t of mes.tareas) if (t.owner?.trim()) set.add(t.owner.trim())
      for (const t of mes.arrastradas ?? []) if (t.owner?.trim()) set.add(t.owner.trim())
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b, "es"))
  }, [meses])

  // Sesionar un mes: crea/abre la sesión del Consejo y navega a la pantalla de sesión.
  const sesionarMes = async (mes: BoardMes) => {
    if (sesionandoMes !== null) return
    setSesionandoMes(mes.month_index)
    try {
      const id = await abrirSesionMes(mes.period_year, mes.period_month)
      router.push(`/dashboard/sesion/${id}`)
    } catch {
      if (aliveRef.current) setSesionandoMes(null)
    }
  }

  // Aplica un parche a una tarea por id en tareas Y arrastradas de todos los meses.
  const parcharTarea = (taskId: string, patch: Partial<BoardTask>) => {
    setMeses(prev => prev.map(mes => ({
      ...mes,
      tareas: mes.tareas.map(t => t.id === taskId ? { ...t, ...patch } : t),
      arrastradas: mes.arrastradas?.map(t => t.id === taskId ? { ...t, ...patch } : t),
    })))
  }

  // Localiza el valor actual de un campo para poder revertir.
  const valorActual = <K extends keyof BoardTask>(taskId: string, key: K): BoardTask[K] | undefined => {
    for (const mes of meses) {
      const t = mes.tareas.find(x => x.id === taskId) ?? mes.arrastradas?.find(x => x.id === taskId)
      if (t) return t[key]
    }
    return undefined
  }

  // Cambio optimista de estado: aplica ya, revierte si el PATCH falla.
  const cambiarEstado = (taskId: string, next: TaskStatus) => {
    const previo = valorActual(taskId, "status")
    parcharTarea(taskId, { status: next })
    setTaskEstado(taskId, next).catch(() => {
      if (aliveRef.current && previo) parcharTarea(taskId, { status: previo })
    })
  }

  // Cambio optimista de responsable: aplica ya, revierte si el PATCH falla.
  const cambiarOwner = (taskId: string, owner: string) => {
    const previo = valorActual(taskId, "owner") ?? null
    parcharTarea(taskId, { owner })
    setTaskOwner(taskId, owner).catch(() => {
      if (aliveRef.current) parcharTarea(taskId, { owner: previo })
    })
  }

  if (status === "loading") {
    return (
      <div className="border border-[var(--gob-rule)] rounded-2xl p-16 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--gob-stone)]" />
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="border border-[var(--gob-rule)] rounded-2xl p-10 text-center space-y-1">
        <p className="text-sm font-medium text-[var(--gob-ink)]">No se pudo cargar el tablero</p>
        <p className="text-xs text-[var(--gob-muted)]">Vuelve a intentarlo en un momento.</p>
      </div>
    )
  }

  if (meses.length === 0) {
    return (
      <div className="border border-[var(--gob-rule)] rounded-2xl p-12 flex flex-col items-center justify-center text-center gap-3">
        <p className="text-sm font-medium text-[var(--gob-ink)]">Tu tablero está vacío</p>
        <p className="text-xs text-[var(--gob-muted)] max-w-sm leading-relaxed">
          Cuando generes tu plan estratégico, las tareas de cada mes aparecerán aquí para que las operes.
        </p>
        <Link href="/dashboard/plan"
          className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-medium px-4 py-2.5 rounded-xl hover:bg-[var(--gob-ink)] transition-colors mt-1">
          Generar mi plan <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Ayuda: qué es la columna Documentos y quién valida. */}
      <p className="flex items-start gap-2 text-xs text-[var(--gob-muted)] leading-snug">
        <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-[var(--gob-stone)]" />
        <span>
          Cada responsable sube en <strong className="font-medium text-[var(--gob-charcoal)]">Documentos</strong> la
          evidencia de su tarea. La validación la hace el Consejo al sesionar el mes.
        </span>
      </p>

      {meses.map((mes, i) => (
        <MesGrupo key={mes.month_index} mes={mes} index={i} sugerencias={sugerencias}
          onEstado={cambiarEstado} onOwner={cambiarOwner} onRefresh={refrescarTablero}
          onSesionar={() => sesionarMes(mes)} sesionando={sesionandoMes === mes.month_index} />
      ))}
    </div>
  )
}
