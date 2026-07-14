"use client"

/**
 * Un acuerdo del Consejo: el entregable de la sesión.
 *
 * No es una recomendación más: tiene dueño, fecha y un pilar del Roadmap al que sirve. Mientras
 * nadie lo tome, la fila lo grita ("Sin responsable asignado"). El dueño asigna inline y se
 * guarda con PATCH /pm/compromisos/{id}.
 */
import { useState } from "react"
import { ChevronDown, Loader2 } from "lucide-react"
import { patchCompromiso } from "@/lib/pm"
import {
  Acuerdo,
  PRIORIDADES,
  PRIORIDAD_COLOR,
  PRIORIDAD_LABEL,
  colorDePilar,
  fechaInput,
  formatFecha,
  toPrioridad,
} from "./shared"

export default function AcuerdoRow({
  acuerdo,
  pilaresDelRoadmap,
  onActualizado,
}: {
  acuerdo: Acuerdo
  pilaresDelRoadmap: string[]
  onActualizado: (id: string, patch: Partial<Acuerdo>) => void
}) {
  const [editando, setEditando] = useState(false)
  const [abierto,  setAbierto]  = useState(false)   // el racional
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [nombre,    setNombre]    = useState(acuerdo.responsable_nombre ?? "")
  const [email,     setEmail]     = useState(acuerdo.responsable_email ?? "")
  const [fecha,     setFecha]     = useState(fechaInput(acuerdo.fecha_compromiso))
  const [prioridad, setPrioridad] = useState(toPrioridad(acuerdo.prioridad))

  const pilar     = (acuerdo.pilar ?? "").trim()
  const color     = pilar ? colorDePilar(pilar, pilaresDelRoadmap) : "#8E8B84"
  const prio      = toPrioridad(acuerdo.prioridad)
  const asignado  = Boolean((acuerdo.responsable_nombre ?? "").trim())

  const abrir = () => {
    setNombre(acuerdo.responsable_nombre ?? "")
    setEmail(acuerdo.responsable_email ?? "")
    setFecha(fechaInput(acuerdo.fecha_compromiso))
    setPrioridad(toPrioridad(acuerdo.prioridad))
    setError(null)
    setEditando(true)
  }

  const guardar = async () => {
    setGuardando(true)
    setError(null)
    try {
      await patchCompromiso(acuerdo.id, {
        responsable_nombre: nombre.trim(),
        responsable_email: email.trim(),
        ...(fecha ? { fecha_compromiso: fecha } : {}),
        prioridad,
      })
      onActualizado(acuerdo.id, {
        responsable_nombre: nombre.trim(),
        responsable_email: email.trim(),
        ...(fecha ? { fecha_compromiso: fecha } : {}),
        prioridad,
      })
      setEditando(false)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "No se pudo guardar el acuerdo. Intenta de nuevo.")
    } finally {
      setGuardando(false)
    }
  }

  return (
    <li className="border-b border-[var(--gob-rule)] last:border-b-0 py-5 first:pt-0">
      {/* Cabecera: el acuerdo, con su pilar y su prioridad */}
      <div className="flex items-start gap-3">
        <span
          className="mt-2 h-1.5 w-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
          aria-hidden
        />
        <div className="min-w-0 flex-1 space-y-2.5">
          <p className="text-sm sm:text-[15px] font-medium leading-relaxed text-[var(--gob-ink)] max-w-[80ch]">
            {acuerdo.texto}
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className="text-[10px] font-medium tracking-wide px-2 py-1 rounded-md"
              style={{ color, backgroundColor: `${color}14` }}
            >
              {pilar || "Transversal"}
            </span>
            <span
              className="text-[10px] font-medium tracking-wide px-2 py-1 rounded-md border"
              style={{ color: PRIORIDAD_COLOR[prio], borderColor: `${PRIORIDAD_COLOR[prio]}44` }}
            >
              {PRIORIDAD_LABEL[prio]}
            </span>
            {formatFecha(acuerdo.fecha_compromiso) && (
              <span className="text-[10px] text-[var(--gob-muted)]">
                Compromiso: {formatFecha(acuerdo.fecha_compromiso)}
              </span>
            )}
          </div>

          {/* Responsable — el llamado a la acción */}
          {!editando && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              {asignado ? (
                <p className="text-xs text-[var(--gob-charcoal)]">
                  <span className="font-medium">{acuerdo.responsable_nombre}</span>
                  {acuerdo.responsable_email && (
                    <span className="text-[var(--gob-muted)]"> · {acuerdo.responsable_email}</span>
                  )}
                </p>
              ) : (
                <p className="text-xs font-medium" style={{ color: "#b45309" }}>
                  Sin responsable asignado
                  {acuerdo.responsable_sugerido && (
                    <span className="font-normal text-[var(--gob-muted)]">
                      {" "}— el Consejo sugiere: {acuerdo.responsable_sugerido}
                    </span>
                  )}
                </p>
              )}
              <button
                type="button"
                onClick={abrir}
                className="text-xs font-medium text-[var(--gob-navy)] underline underline-offset-2 hover:text-[var(--gob-ink)] transition-colors"
              >
                {asignado ? "Cambiar responsable o fecha" : "Asignar responsable"}
              </button>
            </div>
          )}

          {/* Asignación inline */}
          {editando && (
            <div className="rounded-xl border border-[var(--gob-rule)] bg-[var(--gob-paper)] p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="block text-[10px] font-medium tracking-widest uppercase text-[var(--gob-muted)]">
                    Responsable
                  </span>
                  <input
                    value={nombre}
                    onChange={e => setNombre(e.target.value)}
                    placeholder={acuerdo.responsable_sugerido || "Nombre y apellido"}
                    className="w-full rounded-lg border border-[var(--gob-rule)] bg-white px-3 py-2 text-xs text-[var(--gob-ink)] placeholder:text-[var(--gob-stone)] focus:border-[var(--gob-navy)] focus:outline-none transition-colors"
                  />
                </label>
                <label className="space-y-1">
                  <span className="block text-[10px] font-medium tracking-widest uppercase text-[var(--gob-muted)]">
                    Correo
                  </span>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="correo@empresa.com"
                    className="w-full rounded-lg border border-[var(--gob-rule)] bg-white px-3 py-2 text-xs text-[var(--gob-ink)] placeholder:text-[var(--gob-stone)] focus:border-[var(--gob-navy)] focus:outline-none transition-colors"
                  />
                </label>
                <label className="space-y-1">
                  <span className="block text-[10px] font-medium tracking-widest uppercase text-[var(--gob-muted)]">
                    Fecha de compromiso
                  </span>
                  <input
                    type="date"
                    value={fecha}
                    onChange={e => setFecha(e.target.value)}
                    className="w-full rounded-lg border border-[var(--gob-rule)] bg-white px-3 py-2 text-xs text-[var(--gob-ink)] focus:border-[var(--gob-navy)] focus:outline-none transition-colors"
                  />
                </label>
                <div className="space-y-1">
                  <span className="block text-[10px] font-medium tracking-widest uppercase text-[var(--gob-muted)]">
                    Prioridad
                  </span>
                  <div className="flex gap-1.5">
                    {PRIORIDADES.map(p => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setPrioridad(p)}
                        className="flex-1 rounded-lg border px-2 py-2 text-[11px] font-medium capitalize transition-colors"
                        style={
                          prioridad === p
                            ? { borderColor: PRIORIDAD_COLOR[p], color: "#FBF8F3", backgroundColor: PRIORIDAD_COLOR[p] }
                            : { borderColor: "#D9D4CB", color: "#6C6A66", backgroundColor: "#fff" }
                        }
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {error && <p className="text-xs" style={{ color: "#b91c1c" }}>{error}</p>}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={guardar}
                  disabled={guardando}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--gob-navy)] px-4 py-2 text-xs font-medium text-[var(--gob-bone)] hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-50"
                >
                  {guardando && <Loader2 className="h-3 w-3 animate-spin" />}
                  Guardar acuerdo
                </button>
                <button
                  type="button"
                  onClick={() => setEditando(false)}
                  disabled={guardando}
                  className="rounded-lg px-3 py-2 text-xs font-medium text-[var(--gob-muted)] hover:text-[var(--gob-ink)] transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {/* El racional: disponible, pero no compite con el acuerdo */}
          {acuerdo.racional && (
            <div>
              <button
                type="button"
                onClick={() => setAbierto(o => !o)}
                aria-expanded={abierto}
                className="inline-flex items-center gap-1 text-[11px] text-[var(--gob-stone)] hover:text-[var(--gob-charcoal)] transition-colors"
              >
                Por qué lo acordó el Consejo
                <ChevronDown className={`h-3 w-3 transition-transform ${abierto ? "rotate-180" : ""}`} />
              </button>
              {abierto && (
                <p className="mt-2 border-l-2 border-[var(--gob-rule)] pl-3 text-xs leading-relaxed text-[var(--gob-muted)] max-w-[72ch]">
                  {acuerdo.racional}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  )
}
