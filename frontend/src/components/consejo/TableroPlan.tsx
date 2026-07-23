"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Loader2, ChevronDown, Check, ArrowRight, Gavel, CornerDownRight } from "lucide-react"
import { BoardMes, BoardTask, TaskStatus, getBoard, setTaskEstado, abrirSesionMes } from "@/lib/board"

/**
 * El tablero tipo Monday del plan mensual, en la paleta sobria de Gobernia.
 *
 * Cada mes es un grupo con su filete de color a la izquierda. La columna Estado es
 * una pastilla editable (optimista, con reversión si el PATCH falla). Sin candado.
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

// ── Responsable ──
function Responsable({ owner }: { owner: string | null }) {
  if (!owner) return <span className="text-xs text-[var(--gob-stone)]">Sin asignar</span>
  return (
    <span className="inline-flex items-center gap-2 min-w-0">
      <span className="h-6 w-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-[10px] font-bold flex items-center justify-center shrink-0">
        {iniciales(owner)}
      </span>
      <span className="text-sm text-[var(--gob-charcoal)] truncate">{owner}</span>
    </span>
  )
}

// ── Pastilla de estado editable ──
function EstadoPill({ status, onChange }: { status: TaskStatus; onChange: (s: TaskStatus) => void }) {
  const [open, setOpen] = useState(false)
  const color = ESTADO_COLOR[status]

  return (
    <span className="relative inline-block">
      <button type="button" onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox" aria-expanded={open}
        aria-label={`Estado: ${ESTADO_LABEL[status]}. Cambiar estado`}
        className="inline-flex items-center gap-1.5 rounded-full pl-2.5 pr-2 py-1 text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-[var(--gob-navy)]"
        style={{ color, borderColor: `${color}33`, backgroundColor: `${color}14` }}>
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
        {ESTADO_LABEL[status]}
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <>
          {/* Cierre al hacer clic fuera */}
          <button type="button" aria-hidden tabIndex={-1}
            className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <ul role="listbox" aria-label="Estados"
            className="absolute z-30 mt-1 left-0 min-w-[176px] rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] shadow-lg py-1">
            {ESTADOS.map(s => (
              <li key={s} role="option" aria-selected={s === status}>
                <button type="button"
                  onClick={() => { setOpen(false); if (s !== status) onChange(s) }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-left hover:bg-[var(--gob-bone)] transition-colors focus-visible:outline-none focus-visible:bg-[var(--gob-bone)]">
                  <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: ESTADO_COLOR[s] }} />
                  <span className="flex-1" style={{ color: ESTADO_COLOR[s] }}>{ESTADO_LABEL[s]}</span>
                  {s === status && <Check className="h-3.5 w-3.5 text-[var(--gob-muted)]" />}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </span>
  )
}

// ── Una fila de tarea (grid en desktop, bloque en móvil) ──
function TareaRow({ tarea, onEstado }: { tarea: BoardTask; onEstado: (s: TaskStatus) => void }) {
  return (
    <div className="px-4 py-3 md:grid md:grid-cols-[minmax(0,1fr)_180px_180px_92px_88px] md:items-center md:gap-4">
      {/* Tarea + objetivo */}
      <div className="min-w-0">
        <p className="text-sm font-medium text-[var(--gob-ink)] leading-snug">{tarea.title}</p>
        {tarea.viene_de && (
          <span className="inline-flex items-center gap-1 mt-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ color: "#b45309", backgroundColor: "#b4530914", border: "1px solid #b4530933" }}>
            <CornerDownRight className="h-3 w-3" />
            viene de {tarea.viene_de}
          </span>
        )}
        {tarea.objetivo && (
          <p className="text-xs text-[var(--gob-muted)] leading-snug mt-0.5 truncate">{tarea.objetivo}</p>
        )}
      </div>

      {/* Responsable */}
      <div className="mt-2 md:mt-0 flex items-center gap-2">
        <span className="md:hidden text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)] w-20 shrink-0">Responsable</span>
        <Responsable owner={tarea.owner} />
      </div>

      {/* Estado */}
      <div className="mt-2 md:mt-0 flex items-center gap-2">
        <span className="md:hidden text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)] w-20 shrink-0">Estado</span>
        <EstadoPill status={tarea.status} onChange={onEstado} />
      </div>

      {/* Vence */}
      <div className="mt-2 md:mt-0 flex items-center gap-2">
        <span className="md:hidden text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)] w-20 shrink-0">Vence</span>
        <span className="text-sm text-[var(--gob-charcoal)]">{venceCorto(tarea.due_date) || <span className="text-[var(--gob-stone)]">—</span>}</span>
      </div>

      {/* Prioridad */}
      <div className="mt-2 md:mt-0 flex items-center gap-2">
        <span className="md:hidden text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)] w-20 shrink-0">Prioridad</span>
        <Prioridad nivel={tarea.priority} />
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

// ── Grupo de un mes ──
function MesGrupo({ mes, index, onEstado, onSesionar, sesionando }: {
  mes: BoardMes
  index: number
  onEstado: (taskId: string, s: TaskStatus) => void
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

      {/* Subgrupo: tareas arrastradas de meses anteriores (solo mes actual) */}
      {arrastradas.length > 0 && (
        <div className="border-b border-[var(--gob-rule)]" style={{ backgroundColor: "#b4530908" }}>
          <div className="px-4 py-2">
            <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: "#b45309" }}>
              Vienen de antes
            </span>
          </div>
          <div className="divide-y divide-[var(--gob-rule)]">
            {arrastradas.map(t => (
              <TareaRow key={t.id} tarea={t} onEstado={s => onEstado(t.id, s)} />
            ))}
          </div>
        </div>
      )}

      {/* Encabezado de columnas (solo desktop) */}
      <div className="hidden md:grid md:grid-cols-[minmax(0,1fr)_180px_180px_92px_88px] md:gap-4 px-4 py-2 border-b border-[var(--gob-rule)] bg-[var(--gob-paper)]">
        {["Tarea", "Responsable", "Estado", "Vence", "Prioridad"].map(c => (
          <span key={c} className="text-[10px] font-medium uppercase tracking-wider text-[var(--gob-stone)]">{c}</span>
        ))}
      </div>

      {/* Filas */}
      <div className="divide-y divide-[var(--gob-rule)]">
        {mes.tareas.map(t => (
          <TareaRow key={t.id} tarea={t} onEstado={s => onEstado(t.id, s)} />
        ))}
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
  const aliveRef = useRef(true)

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
  }, [reloadSignal])

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

  // Cambio optimista de estado: aplica ya, revierte si el PATCH falla.
  const cambiarEstado = (taskId: string, next: TaskStatus) => {
    let previo: TaskStatus | null = null
    setMeses(prev => prev.map(mes => ({
      ...mes,
      tareas: mes.tareas.map(t => {
        if (t.id !== taskId) return t
        previo = t.status
        return { ...t, status: next }
      }),
    })))
    setTaskEstado(taskId, next).catch(() => {
      if (!aliveRef.current || previo === null) return
      setMeses(prev => prev.map(mes => ({
        ...mes,
        tareas: mes.tareas.map(t => t.id === taskId ? { ...t, status: previo as TaskStatus } : t),
      })))
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
      {meses.map((mes, i) => (
        <MesGrupo key={mes.month_index} mes={mes} index={i} onEstado={cambiarEstado}
          onSesionar={() => sesionarMes(mes)} sesionando={sesionandoMes === mes.month_index} />
      ))}
    </div>
  )
}
