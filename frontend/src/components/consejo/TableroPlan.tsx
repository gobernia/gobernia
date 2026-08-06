"use client"

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Loader2, ChevronDown, Check, ArrowRight, Gavel, CornerDownRight, UserPlus, X,
  Upload, Paperclip, Download, Trash2, ShieldCheck, AlertTriangle, Clock, Info, Link2,
} from "lucide-react"
import {
  BoardMes, BoardTask, TaskStatus, Validacion, ValidacionEstado,
  getBoard, setTaskEstado, setTaskOwner, abrirSesionMes,
} from "@/lib/board"
import {
  Evidence, getEvidence, uploadEvidence, deleteEvidence, downloadEvidenceUrl,
} from "@/lib/evidence"
import { getColaboradorLink } from "@/lib/colaborador"

/**
 * El tablero tipo Monday del plan mensual, en el sistema de diseño Bento.
 *
 * Estructura de Monday con colores Bento: rejilla real (líneas verticales y
 * horizontales), columnas con sombreado alterno para que cada una "se note", la celda
 * de Estado rellena del color del estado (editable, optimista) y la de Responsable
 * editable con popover (input prellenado + chips de responsables ya usados).
 */

// ── Bento design system color tokens ──
const INK = "#0E1626"      // primary text
const MUTED = "#6E7686"    // tertiary text
const CARD = "#FFFFFF"     // cards/containers
const SAND = "#E8E3D8"     // accent backgrounds
const BNAVY = "#152742"    // navy accent
const LINE = "#E2E2DC"     // borders

// ── Estado: etiqueta + color sobrio (hex literal; Tailwind v4 no ve clases dinámicas) ──
const ESTADOS: TaskStatus[] = ["pendiente", "en_progreso", "completada"]

const ESTADO_LABEL: Record<TaskStatus, string> = {
  pendiente:   "Aún sin ejecutar",
  en_progreso: "En proceso",
  completada:  "Hecho",
}

const ESTADO_COLOR: Record<TaskStatus, string> = {
  pendiente:   MUTED,     // bento MUTED
  en_progreso: "#b45309", // ámbar
  completada:  "#0f766e", // verde
}

// ── Filete de color por grupo de mes: paleta rotatoria Bento (navy y variantes) ──
// Array literal de hex — NADA dinámico por el JIT de Tailwind.
const FILETE = [BNAVY, "#1f3a52", "#203950", "#2d4563", "#1a334d", "#26384a"]

const filete = (i: number) => FILETE[i % FILETE.length]

// ── Rejilla de columnas: mismo template en encabezado y filas ──
// Tablero ancho tipo Monday: la 1ª (Tarea) queda congelada y respira; las demás
// tienen ancho fijo y se desplazan en horizontal dentro del contenedor de la tabla.
const GRID_COLS = "md:grid-cols-[minmax(260px,1fr)_220px_200px_120px_120px_260px]"
// Ancho mínimo de la rejilla: fuerza el scroll horizontal cuando el tablero aprieta.
const GRID_MINW = "md:min-w-[1180px]"

// La columna Tarea queda fija a la izquierda (sticky) con fondo sólido y un corte
// (borde + sombra) para marcar el congelado mientras el resto se desplaza. Solo en
// desktop; en móvil el layout de bloque no necesita congelar nada.
const STICKY_TAREA = `md:sticky md:left-0 md:z-[15] md:shadow-[6px_0_10px_-8px_rgba(21,39,66,0.22)]`

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
          style={{ height: 7 + i * 4, backgroundColor: i < llenas ? BNAVY : LINE }} />
      ))}
    </span>
  )
}

// ── Menú flotante: escapa de cualquier contenedor con overflow ──
// Se posiciona con `position: fixed` a partir del getBoundingClientRect() del botón
// disparador, así NINGÚN overflow lo recorta (el bug de la última fila). Voltea hacia
// arriba si no hay espacio abajo, se clampea al borde derecho, y se cierra con clic
// fuera, Escape, scroll (con capture, para atrapar el scroll horizontal del mes) y resize.
function MenuFlotante({ anchorRef, open, onClose, ancho, altoEstimado = 240, children }: {
  anchorRef: React.RefObject<HTMLButtonElement | null>
  open: boolean
  onClose: () => void
  ancho: number
  altoEstimado?: number
  children: React.ReactNode
}) {
  const [coords, setCoords] = useState<{ left: number; top: number | null; bottom: number | null }>(
    { left: 0, top: null, bottom: null },
  )

  useLayoutEffect(() => {
    if (!open) return
    const btn = anchorRef.current
    if (!btn) return
    const rect = btn.getBoundingClientRect()
    // Voltea hacia arriba solo si no cabe abajo Y sí cabe arriba.
    const flipUp = rect.bottom + altoEstimado > window.innerHeight && rect.top > altoEstimado
    // Alinea a la izquierda del botón y clampea para no salirse por la derecha.
    let left = rect.left
    const maxLeft = window.innerWidth - ancho - 8
    if (left > maxLeft) left = maxLeft
    if (left < 8) left = 8
    setCoords(
      flipUp
        ? { left, top: null, bottom: window.innerHeight - rect.top + 4 }
        : { left, top: rect.bottom + 4, bottom: null },
    )
  }, [open, anchorRef, ancho, altoEstimado])

  useEffect(() => {
    if (!open) return
    const cerrar = () => onClose()
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    // capture: true atrapa el scroll de contenedores internos (el mes con overflow-x).
    window.addEventListener("scroll", cerrar, true)
    window.addEventListener("resize", cerrar)
    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("scroll", cerrar, true)
      window.removeEventListener("resize", cerrar)
      window.removeEventListener("keydown", onKey)
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <>
      {/* Backdrop de cierre (debajo del menú) */}
      <button type="button" aria-hidden tabIndex={-1}
        className="fixed inset-0 z-[60] cursor-default" onClick={onClose} />
      {/* Menú (encima del backdrop) */}
      <div
        style={{
          position: "fixed",
          left: coords.left,
          top: coords.top ?? undefined,
          bottom: coords.bottom ?? undefined,
          width: ancho,
          zIndex: 61,
        }}>
        {children}
      </div>
    </>,
    document.body,
  )
}

// ── Celda de Responsable, editable con popover ──
function ResponsableCelda({ owner, ownerEmail, sugerencias, onChange }: {
  owner: string | null
  ownerEmail: string | null
  sugerencias: string[]
  onChange: (owner: string, email: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [valor, setValor] = useState(owner ?? "")
  const [correo, setCorreo] = useState(ownerEmail ?? "")
  const [copiado, setCopiado] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)

  const copiarEnlace = async () => {
    const email = correo.trim()
    if (!email) return
    try {
      const { token } = await getColaboradorLink(email, valor.trim() || owner)
      const url = `${window.location.origin}/t/${token}`
      await navigator.clipboard.writeText(url)
      setCopiado(true)
      window.setTimeout(() => setCopiado(false), 2000)
    } catch {
      /* noop */
    }
  }

  const abrir = () => { setValor(owner ?? ""); setCorreo(ownerEmail ?? ""); setOpen(true) }
  const cerrar = () => setOpen(false)
  // Asigna si cambió el nombre O el correo. Con el correo prellenado a "" cuando no había.
  const confirmar = (v: string, email: string | null) => {
    const nuevo = v.trim()
    const nuevoEmail = email?.trim() || null
    setOpen(false)
    if (nuevo && (nuevo !== (owner ?? "") || nuevoEmail !== (ownerEmail ?? null))) {
      onChange(nuevo, nuevoEmail)
    }
  }

  // Chips de acceso rápido: responsables ya usados, sin el actual.
  const chips = sugerencias.filter(s => s !== owner)

  return (
    <div className="relative min-w-0 w-full">
      <button ref={btnRef} type="button" onClick={abrir}
        aria-haspopup="dialog" aria-expanded={open}
        aria-label={owner ? `Responsable: ${owner}. Cambiar responsable` : "Sin asignar. Asignar responsable"}
        className="group inline-flex items-center gap-2 min-w-0 max-w-full rounded-lg -mx-1.5 px-1.5 py-1 text-left transition-colors focus-visible:outline-none focus-visible:ring-2"
        style={{ outlineColor: BNAVY }}>
        {owner ? (
          <>
            <span className="h-6 w-6 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0"
              style={{ backgroundColor: BNAVY, color: CARD }}>
              {iniciales(owner)}
            </span>
            <span className="text-xs truncate" style={{ color: INK }}>{owner}</span>
          </>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: MUTED }}>
            <UserPlus className="h-3.5 w-3.5" />
            Sin asignar
          </span>
        )}
      </button>

      <MenuFlotante anchorRef={btnRef} open={open} onClose={cerrar} ancho={256} altoEstimado={200}>
        <div role="dialog" aria-label="Editar responsable"
          className="w-full rounded-xl shadow-lg p-3 space-y-2.5"
          style={{ border: `1px solid ${LINE}`, backgroundColor: SAND }}>
          <input
              autoFocus
              value={valor}
              onChange={e => setValor(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter") { e.preventDefault(); confirmar(valor, correo) }
                else if (e.key === "Escape") { e.preventDefault(); cerrar() }
              }}
              placeholder="Nombre del responsable"
              className="w-full rounded-lg px-2.5 py-2 text-sm placeholder:text-[color:inherit] focus-visible:outline-none focus-visible:ring-2"
              style={{ border: `1px solid ${LINE}`, backgroundColor: CARD, color: INK, outlineColor: BNAVY }}
            />

            <div className="space-y-1">
              <input
                type="email"
                value={correo}
                onChange={e => setCorreo(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter") { e.preventDefault(); confirmar(valor, correo) }
                  else if (e.key === "Escape") { e.preventDefault(); cerrar() }
                }}
                placeholder="Correo (opcional, para enviarle sus tareas)"
                className="w-full rounded-lg px-2.5 py-2 text-sm placeholder:text-[color:inherit] focus-visible:outline-none focus-visible:ring-2"
                style={{ border: `1px solid ${LINE}`, backgroundColor: CARD, color: INK, outlineColor: BNAVY }}
              />
              <p className="text-[10px] leading-snug" style={{ color: MUTED }}>
                Con su correo podrás enviarle un enlace a sus tareas.
              </p>
              {correo.trim() && (
                <button type="button" onClick={copiarEnlace}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors"
                  style={{ border: `1px solid ${LINE}`, backgroundColor: CARD, color: BNAVY }}>
                  {copiado ? <Check className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
                  {copiado ? "¡Copiado!" : "Copiar enlace de sus tareas"}
                </button>
              )}
            </div>

            {chips.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: MUTED }}>Del tablero</p>
                <div className="flex flex-wrap gap-1.5">
                  {chips.map(c => (
                    <button key={c} type="button" onClick={() => confirmar(c, ownerEmail)}
                      className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs transition-colors"
                      style={{ border: `1px solid ${LINE}`, backgroundColor: CARD, color: INK }}>
                      <span className="h-4 w-4 rounded-full text-[8px] font-bold flex items-center justify-center shrink-0"
                        style={{ backgroundColor: BNAVY, color: CARD }}>
                        {iniciales(c)}
                      </span>
                      <span className="truncate max-w-[8rem]">{c}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 pt-0.5">
              <button type="button" onClick={() => confirmar(valor, correo)}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={{ backgroundColor: BNAVY, color: CARD }}>
                <Check className="h-3.5 w-3.5" />
                Asignar
              </button>
              <button type="button" onClick={cerrar}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={{ border: `1px solid ${LINE}`, color: MUTED }}>
                <X className="h-3.5 w-3.5" />
                Cancelar
              </button>
            </div>
        </div>
      </MenuFlotante>
    </div>
  )
}

// ── Celda de Estado tipo Monday: rellena del color del estado, editable (optimista) ──
function EstadoCelda({ status, onChange }: { status: TaskStatus; onChange: (s: TaskStatus) => void }) {
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)
  const color = ESTADO_COLOR[status]

  return (
    <div className="relative h-full">
      <button ref={btnRef} type="button" onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox" aria-expanded={open}
        aria-label={`Estado: ${ESTADO_LABEL[status]}. Cambiar estado`}
        className="w-full h-full min-h-[2.75rem] flex items-center gap-2 px-4 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset"
        style={{ color, backgroundColor: `${color}22`, outlineColor: BNAVY }}>
        <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
        <span className="flex-1 text-left truncate">{ESTADO_LABEL[status]}</span>
        <ChevronDown className="h-3.5 w-3.5 opacity-60 shrink-0" />
      </button>

      <MenuFlotante anchorRef={btnRef} open={open} onClose={() => setOpen(false)} ancho={200} altoEstimado={140}>
        <ul role="listbox" aria-label="Estados"
          className="w-full rounded-xl shadow-lg py-1"
          style={{ border: `1px solid ${LINE}`, backgroundColor: SAND }}>
          {ESTADOS.map(s => (
            <li key={s} role="option" aria-selected={s === status}>
              <button type="button"
                onClick={() => { setOpen(false); if (s !== status) onChange(s) }}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-left transition-colors"
                style={{ backgroundColor: "transparent" }}>
                <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: ESTADO_COLOR[s] }} />
                <span className="flex-1" style={{ color: ESTADO_COLOR[s] }}>{ESTADO_LABEL[s]}</span>
                {s === status && <Check className="h-3.5 w-3.5" style={{ color: MUTED }} />}
              </button>
            </li>
          ))}
        </ul>
      </MenuFlotante>
    </div>
  )
}

// ── Etiqueta de columna en móvil (bloque) ──
function EtiquetaMovil({ children }: { children: string }) {
  return (
    <span className="md:hidden text-[10px] font-medium uppercase tracking-wider w-20 shrink-0" style={{ color: MUTED }}>
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
  sin_revisar:  { color: MUTED,    label: "Sin revisar",             Icon: Clock },
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
        <span className="text-[10px] leading-snug line-clamp-2" style={{ color: MUTED }}>{motivo}</span>
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
  const verBtnRef = useRef<HTMLButtonElement>(null)

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
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium transition-colors disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2"
          style={{ border: `1px solid ${LINE}`, color: MUTED, outlineColor: BNAVY }}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {busy ? "Subiendo…" : "Subir"}
        </button>

        {count > 0 && (
          <button ref={verBtnRef} type="button" onClick={abrirLista}
            aria-haspopup="dialog" aria-expanded={open}
            aria-label={`Ver ${count} ${count === 1 ? "documento" : "documentos"}`}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2"
            style={{ color: BNAVY, outlineColor: BNAVY }}>
            <Paperclip className="h-3.5 w-3.5" />
            {count}
          </button>
        )}
      </div>

      {error && <p className="text-[10px] leading-snug" style={{ color: "#b45309" }}>{error}</p>}

      <input ref={inputRef} type="file" className="hidden" onChange={subir}
        accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.docx" />

      <MenuFlotante anchorRef={verBtnRef} open={open} onClose={() => setOpen(false)} ancho={288} altoEstimado={260}>
        <div role="dialog" aria-label="Documentos de la tarea"
          className="w-full rounded-xl shadow-lg p-3 space-y-2"
          style={{ border: `1px solid ${LINE}`, backgroundColor: SAND }}>
          <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: MUTED }}>Documentos</p>
          {cargandoLista ? (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: MUTED }} />
            </div>
          ) : (lista && lista.length > 0) ? (
            <ul className="space-y-1.5">
              {lista.map(ev => (
                <li key={ev.id} className="flex items-center gap-2 rounded-lg px-2.5 py-1.5"
                  style={{ border: `1px solid ${LINE}`, backgroundColor: CARD }}>
                  <Paperclip className="h-3.5 w-3.5 shrink-0" style={{ color: MUTED }} />
                  <span className="flex-1 truncate text-xs" style={{ color: INK }} title={ev.filename}>{ev.filename}</span>
                  <button type="button" onClick={() => descargar(ev.id)}
                    aria-label={`Descargar ${ev.filename}`}
                    className="transition-colors focus-visible:outline-none focus-visible:ring-2 rounded"
                    style={{ color: BNAVY, outlineColor: BNAVY }}>
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button type="button" onClick={() => borrar(ev.id)}
                    aria-label={`Borrar ${ev.filename}`}
                    className="transition-colors focus-visible:outline-none focus-visible:ring-2 rounded"
                    style={{ color: MUTED, outlineColor: "#b45309" }}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs py-1" style={{ color: MUTED }}>Sin documentos todavía.</p>
          )}
        </div>
      </MenuFlotante>
    </div>
  )
}

// ── Una fila de tarea (rejilla en desktop, bloque en móvil) ──
function TareaRow({ tarea, sugerencias, onEstado, onOwner, onRefresh }: {
  tarea: BoardTask
  sugerencias: string[]
  onEstado: (s: TaskStatus) => void
  onOwner: (owner: string, email: string | null) => void
  onRefresh: () => void
}) {
  const celdaBase = "px-4 py-2.5 flex items-center gap-2"

  return (
    <div className={`grid grid-cols-1 ${GRID_COLS} md:gap-x-1 md:items-stretch last:border-b-0`}
      style={{ borderBottom: `1px solid ${LINE}`, backgroundColor: CARD }}>
      {/* Tarea + objetivo — columna congelada a la izquierda */}
      <div className={`px-4 py-2.5 flex flex-col justify-center min-w-0 ${STICKY_TAREA}`}
        style={{ backgroundColor: CARD }}>
        <p className="text-[13px] font-medium leading-snug" style={{ color: INK }}>{tarea.title}</p>
        {tarea.viene_de && (
          <span className="inline-flex items-center gap-1 mt-1 self-start rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ color: "#b45309", backgroundColor: "#b4530914", border: "1px solid #b4530933" }}>
            <CornerDownRight className="h-3 w-3" />
            viene de {tarea.viene_de}
          </span>
        )}
        {tarea.objetivo && (
          <p className="text-[11px] leading-snug mt-0.5 truncate" style={{ color: MUTED }}>{tarea.objetivo}</p>
        )}
      </div>

      {/* Responsable (editable) */}
      <div className={`${celdaBase}`} style={{ backgroundColor: SAND }}>
        <EtiquetaMovil>Responsable</EtiquetaMovil>
        <ResponsableCelda owner={tarea.owner} ownerEmail={tarea.owner_email} sugerencias={sugerencias} onChange={onOwner} />
      </div>

      {/* Estado (celda rellena tipo Monday) */}
      <div className="flex flex-col">
        <span className="md:hidden px-4 pt-2.5 text-[10px] font-medium uppercase tracking-wider" style={{ color: MUTED }}>Estado</span>
        <EstadoCelda status={tarea.status} onChange={onEstado} />
      </div>

      {/* Vence */}
      <div className={`${celdaBase}`} style={{ backgroundColor: CARD }}>
        <EtiquetaMovil>Vence</EtiquetaMovil>
        <span className="text-xs" style={{ color: INK }}>
          {venceCorto(tarea.due_date) || <span style={{ color: MUTED }}>—</span>}
        </span>
      </div>

      {/* Prioridad */}
      <div className={`px-4 py-2.5 flex items-center gap-2`} style={{ backgroundColor: SAND }}>
        <EtiquetaMovil>Prioridad</EtiquetaMovil>
        <Prioridad nivel={tarea.priority} />
      </div>

      {/* Documentos (última columna: sin filete derecho) */}
      <div className={`px-4 py-2.5 flex items-start gap-2`} style={{ backgroundColor: CARD }}>
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
      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
      style={{ border: `1px solid ${LINE}`, color: MUTED, outlineColor: BNAVY }}>
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
    <div className={`hidden md:grid ${GRID_COLS} md:gap-x-1`}
      style={{ borderBottom: `1px solid ${LINE}`, backgroundColor: CARD }}>
      {cols.map((label, i) => (
        <span key={label}
          className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider ${
            i === 0 ? STICKY_TAREA : ""}`}
          style={{ backgroundColor: SAND, color: MUTED }}>
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
  onOwner: (taskId: string, owner: string, email: string | null) => void
  onRefresh: () => void
  onSesionar: () => void
  sesionando: boolean
}) {
  const arrastradas = mes.es_mes_actual ? (mes.arrastradas ?? []) : []

  return (
    <section className="rounded-2xl overflow-hidden"
      style={{ border: `1px solid ${LINE}`, borderLeftWidth: 4, borderLeftColor: filete(index), backgroundColor: CARD }}>
      {/* Encabezado del mes */}
      <header className="flex items-center gap-3 px-4 py-3"
        style={{ borderBottom: `1px solid ${LINE}` }}>
        <h3 className="text-sm font-bold tracking-tight" style={{ color: INK }}>{mes.label}</h3>
        {mes.es_mes_actual && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full"
            style={{ backgroundColor: BNAVY, color: CARD }}>
            Mes actual
          </span>
        )}
        <span className="ml-auto text-xs" style={{ color: MUTED }}>
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
            <div style={{ borderBottom: `1px solid ${LINE}`, backgroundColor: "#b4530908" }}>
              <div className="px-4 py-2">
                <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "#b45309" }}>
                  Vienen de antes
                </span>
              </div>
              <div>
                {arrastradas.map(t => (
                  <TareaRow key={t.id} tarea={t} sugerencias={sugerencias}
                    onEstado={s => onEstado(t.id, s)} onOwner={(o, email) => onOwner(t.id, o, email)}
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
                onEstado={s => onEstado(t.id, s)} onOwner={(o, email) => onOwner(t.id, o, email)}
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
  // Error al intentar sesionar (antes se tragaba en silencio y el botón "no hacía nada").
  const [sesionError, setSesionError] = useState<string | null>(null)
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
    setSesionError(null)
    setSesionandoMes(mes.month_index)
    try {
      const id = await abrirSesionMes(mes.period_year, mes.period_month)
      router.push(`/dashboard/sesion/${id}`)
    } catch (err: unknown) {
      // El error ya no se traga: el cliente ve por qué no pudo sesionar.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = typeof detail === "string" ? detail
        : "No se pudo abrir la sesión del Consejo. Intenta de nuevo."
      if (aliveRef.current) { setSesionError(msg); setSesionandoMes(null) }
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

  // Cambio optimista de responsable (y su correo): aplica ya, revierte si el PATCH falla.
  const cambiarOwner = (taskId: string, owner: string, email: string | null) => {
    const previoOwner = valorActual(taskId, "owner") ?? null
    const previoEmail = valorActual(taskId, "owner_email") ?? null
    parcharTarea(taskId, { owner, owner_email: email })
    setTaskOwner(taskId, owner, email).catch(() => {
      if (aliveRef.current) parcharTarea(taskId, { owner: previoOwner, owner_email: previoEmail })
    })
  }

  if (status === "loading") {
    return (
      <div className="rounded-2xl p-16 flex items-center justify-center"
        style={{ border: `1px solid ${LINE}` }}>
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} />
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="rounded-2xl p-10 text-center space-y-1"
        style={{ border: `1px solid ${LINE}` }}>
        <p className="text-sm font-medium" style={{ color: INK }}>No se pudo cargar el tablero</p>
        <p className="text-xs" style={{ color: MUTED }}>Vuelve a intentarlo en un momento.</p>
      </div>
    )
  }

  if (meses.length === 0) {
    return (
      <div className="rounded-2xl p-12 flex flex-col items-center justify-center text-center gap-3"
        style={{ border: `1px solid ${LINE}` }}>
        <p className="text-sm font-medium" style={{ color: INK }}>Tu tablero está vacío</p>
        <p className="text-xs max-w-sm leading-relaxed" style={{ color: MUTED }}>
          Cuando generes tu plan estratégico, las tareas de cada mes aparecerán aquí para que las operes.
        </p>
        <Link href="/dashboard/plan"
          className="inline-flex items-center gap-2 text-xs font-medium px-4 py-2.5 rounded-xl transition-colors mt-1"
          style={{ backgroundColor: BNAVY, color: CARD }}>
          Generar mi plan <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Ayuda: qué es la columna Documentos y quién valida. */}
      <p className="flex items-start gap-2 text-xs leading-snug" style={{ color: MUTED }}>
        <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" style={{ color: MUTED }} />
        <span>
          Cada responsable sube en <strong className="font-medium" style={{ color: INK }}>Documentos</strong> la
          evidencia de su tarea. La validación la hace el Consejo al sesionar el mes.
        </span>
      </p>

      {sesionError && (
        <div role="alert" className="flex items-start gap-2 rounded-xl px-3.5 py-2.5 text-xs leading-snug"
          style={{ backgroundColor: "#b4530910", border: "1px solid #b4530933", color: "#b45309" }}>
          <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{sesionError}</span>
        </div>
      )}

      {meses.map((mes, i) => (
        <MesGrupo key={mes.month_index} mes={mes} index={i} sugerencias={sugerencias}
          onEstado={cambiarEstado} onOwner={cambiarOwner} onRefresh={refrescarTablero}
          onSesionar={() => sesionarMes(mes)} sesionando={sesionandoMes === mes.month_index} />
      ))}
    </div>
  )
}
