"use client"

// Super admin → Cupones: % de descuento, monto fijo o meses gratis, con vigencia y
// límite de usos. Un cupón no se borra: se desactiva (conserva su historial de usos).

import { useMemo, useState } from "react"
import { Plus } from "lucide-react"
import { crearCupon, editarCupon, mensajeError, type Cupon, type CuponIn, type TipoCupon } from "@/lib/admin"
import { pesos } from "@/lib/pagos"
import { B, Boton, Campo, Etiqueta, fecha, INPUT, INPUT_STYLE, SANS, Tabla, Tarjeta } from "./ui"

const TIPOS: { tipo: TipoCupon; label: string; valor: string; ejemplo: string }[] = [
  { tipo: "porcentaje", label: "% de descuento", valor: "Porcentaje", ejemplo: "20" },
  { tipo: "monto", label: "Monto fijo", valor: "Pesos de descuento", ejemplo: "500" },
  { tipo: "meses_gratis", label: "Meses gratis", valor: "Meses", ejemplo: "3" },
]

type Duracion = "primero" | "varios" | "siempre"

function hoy(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

/** Lo mismo que el servidor muestra, para ver el cupón antes de crearlo. */
function resumen(tipo: TipoCupon, valor: number, numCobros: number | null): string {
  if (!(valor > 0)) return "—"
  if (tipo === "meses_gratis") return `${valor} ${valor === 1 ? "mes" : "meses"} gratis, sin tarjeta`
  const base = tipo === "porcentaje" ? `${valor}% de descuento` : `${pesos(valor)} MXN de descuento`
  if (numCobros == null) return `${base} en cada cobro`
  return numCobros === 1 ? `${base} en el primer cobro` : `${base} en los primeros ${numCobros} cobros`
}

function NuevoCupon({ onCreado, onCancelar }: { onCreado: () => Promise<void>; onCancelar: () => void }) {
  const [tipo, setTipo] = useState<TipoCupon>("porcentaje")
  const [codigo, setCodigo] = useState("")
  const [valor, setValor] = useState("")
  const [duracion, setDuracion] = useState<Duracion>("primero")
  const [cobros, setCobros] = useState("3")
  const [vence, setVence] = useState("")
  const [maxUsos, setMaxUsos] = useState("")
  const [nota, setNota] = useState("")
  const [error, setError] = useState("")
  const [guardando, setGuardando] = useState(false)

  const n = Number(valor.replace(/[$,%\s]/g, ""))
  const numCobros = tipo === "meses_gratis" || duracion === "siempre" ? null : duracion === "primero" ? 1 : Number(cobros)
  const def = TIPOS.find(t => t.tipo === tipo)!

  async function guardar() {
    const cod = codigo.trim().toUpperCase()
    if (!/^[A-Z0-9_-]{3,30}$/.test(cod)) return setError("El código lleva de 3 a 30 letras, números, guiones o guiones bajos, sin espacios.")
    if (!(n > 0)) return setError("Escribe cuánto da el cupón.")
    if (tipo === "porcentaje" && n >= 100) return setError("El descuento debe ser menor a 100%. Para dar acceso gratis usa Meses gratis.")
    if (tipo === "meses_gratis" && !Number.isInteger(n)) return setError("Los meses gratis deben ser un número entero.")
    if (numCobros != null && !(Number.isInteger(numCobros) && numCobros >= 1)) return setError("Indica en cuántos cobros aplica.")
    const usos = maxUsos.trim() ? Number(maxUsos) : null
    if (usos != null && !(Number.isInteger(usos) && usos >= 1)) return setError("El límite de usos debe ser un número entero.")
    const body: CuponIn = {
      codigo: cod, tipo, valor: n, num_cobros: numCobros,
      vigente_hasta: vence || null, max_usos: usos, descripcion: nota.trim() || null,
    }
    setGuardando(true)
    setError("")
    try {
      await crearCupon(body)
      await onCreado()
    } catch (e) {
      setError(mensajeError(e))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="rounded-[18px] p-4 space-y-4" style={{ background: B.PAPER, border: `1px solid ${B.LINE}` }}>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Tipo de cupón">
        {TIPOS.map(t => (
          <button key={t.tipo} type="button" role="radio" aria-checked={tipo === t.tipo} onClick={() => setTipo(t.tipo)}
            className="rounded-full px-3.5 py-1.5 text-xs font-bold transition"
            style={{ ...SANS, background: tipo === t.tipo ? B.BNAVY : B.CARD, color: tipo === t.tipo ? "#fff" : B.INK2,
              border: `1px solid ${tipo === t.tipo ? B.BNAVY : B.LINE}` }}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Campo label="Código" ayuda="El cliente lo escribe al suscribirse.">
          <input className={INPUT} style={INPUT_STYLE} value={codigo} maxLength={30} placeholder="Ej. BIENVENIDA20"
            onChange={e => setCodigo(e.target.value.replace(/\s/g, "").toUpperCase())} />
        </Campo>
        <Campo label={def.valor}>
          <input className={INPUT} style={INPUT_STYLE} value={valor} inputMode="decimal" placeholder={`Ej. ${def.ejemplo}`}
            onChange={e => setValor(e.target.value)} />
        </Campo>
        <Campo label="Vence (opcional)" ayuda="Último día en que se puede usar.">
          <input type="date" className={INPUT} style={INPUT_STYLE} value={vence} min={hoy()} onChange={e => setVence(e.target.value)} />
        </Campo>
        <Campo label="Límite de usos (opcional)" ayuda="Vacío = sin límite. Cada cliente lo usa una vez.">
          <input className={INPUT} style={INPUT_STYLE} value={maxUsos} inputMode="numeric" placeholder="Ej. 50"
            onChange={e => setMaxUsos(e.target.value.replace(/\D/g, ""))} />
        </Campo>
      </div>

      {tipo !== "meses_gratis" && (
        <Campo label="¿En cuántos cobros aplica el descuento?">
          <div className="flex flex-wrap items-center gap-2">
            {([["primero", "Solo el primero"], ["varios", "Los primeros…"], ["siempre", "En todos"]] as [Duracion, string][]).map(([d, l]) => (
              <button key={d} type="button" aria-pressed={duracion === d} onClick={() => setDuracion(d)}
                className="rounded-full px-3 py-1.5 text-xs font-semibold"
                style={{ background: duracion === d ? `${B.BNAVY}12` : B.CARD, color: duracion === d ? B.BNAVY : B.INK2,
                  border: `1px solid ${duracion === d ? B.BNAVY : B.LINE}` }}>
                {l}
              </button>
            ))}
            {duracion === "varios" && (
              <input className={`${INPUT} !w-20`} style={INPUT_STYLE} value={cobros} inputMode="numeric" aria-label="Número de cobros"
                onChange={e => setCobros(e.target.value.replace(/\D/g, ""))} />
            )}
          </div>
        </Campo>
      )}

      <Campo label="Nota interna (opcional)">
        <input className={INPUT} style={INPUT_STYLE} value={nota} maxLength={300} placeholder="Ej. Para los asistentes del evento AMEF"
          onChange={e => setNota(e.target.value)} />
      </Campo>

      <p className="text-sm" style={{ color: B.INK2 }}>
        El cliente recibe: <strong style={{ color: B.INK }}>{resumen(tipo, n, numCobros)}</strong>
      </p>
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      <div className="flex gap-2">
        <Boton onClick={guardar} disabled={guardando}>{guardando ? "Creando…" : "Crear cupón"}</Boton>
        <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
      </div>
    </div>
  )
}

function estadoCupon(c: Cupon): [string, "verde" | "gris" | "ambar"] {
  if (!c.activo) return ["Inactivo", "gris"]
  if (c.vigente_hasta && c.vigente_hasta < hoy()) return ["Vencido", "ambar"]
  if (c.max_usos != null && c.usos >= c.max_usos) return ["Agotado", "ambar"]
  return ["Activo", "verde"]
}

export default function CuponesAdmin({ cupones, recargar }: { cupones: Cupon[]; recargar: () => Promise<void> }) {
  const [creando, setCreando] = useState(false)
  const [error, setError] = useState("")
  const usados = useMemo(() => cupones.reduce((n, c) => n + c.usos, 0), [cupones])

  async function alternar(c: Cupon) {
    setError("")
    try {
      await editarCupon(c.id, { activo: !c.activo })
      await recargar()
    } catch (e) {
      setError(mensajeError(e))
    }
  }

  return (
    <Tarjeta titulo="Cupones"
      sub={`${cupones.length} ${cupones.length === 1 ? "cupón" : "cupones"} · ${usados} ${usados === 1 ? "uso" : "usos"} en total. Un cupón se gasta cuando el pago queda autorizado o al canjear meses gratis.`}
      acciones={!creando && <Boton onClick={() => setCreando(true)}><Plus className="h-4 w-4" /> Nuevo cupón</Boton>}>
      {creando && <NuevoCupon onCancelar={() => setCreando(false)} onCreado={async () => { setCreando(false); await recargar() }} />}
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      <Tabla columnas={["Código", "Qué da", "Usos", "Vence", "Estado", ""]} vacio={cupones.length === 0}>
        {cupones.map(c => {
          const [label, tono] = estadoCupon(c)
          return (
            <tr key={c.id} style={{ borderTop: `1px solid ${B.LINE}` }}>
              <td className="px-4 py-3">
                <p className="font-mono font-bold" style={{ color: B.INK }}>{c.codigo}</p>
                {c.descripcion && <p className="text-xs" style={{ color: B.MUTED }}>{c.descripcion}</p>}
              </td>
              <td className="px-4 py-3" style={{ color: B.INK2 }}>{c.resumen}</td>
              <td className="px-4 py-3 tabular-nums whitespace-nowrap" style={{ color: B.INK2 }}>
                {c.usos}{c.max_usos != null && ` / ${c.max_usos}`}
              </td>
              <td className="px-4 py-3 whitespace-nowrap" style={{ color: B.INK2 }}>{c.vigente_hasta ? fecha(c.vigente_hasta) : "Sin fecha"}</td>
              <td className="px-4 py-3"><Etiqueta tono={tono}>{label}</Etiqueta></td>
              <td className="px-4 py-3 text-right">
                <button type="button" onClick={() => alternar(c)} className="text-xs font-semibold underline" style={{ color: B.INK2 }}>
                  {c.activo ? "Desactivar" : "Activar"}
                </button>
              </td>
            </tr>
          )
        })}
      </Tabla>
    </Tarjeta>
  )
}
