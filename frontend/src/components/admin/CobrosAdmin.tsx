"use client"

// Super admin → Cobros: conexión con Stripe, ingresos, planes (precios editables),
// suscripciones y pagos. Por ahora nadie pierde acceso por no pagar.

import { useState } from "react"
import Link from "next/link"
import { CheckCircle2, CircleAlert, Copy, Pencil, Plus } from "lucide-react"
import {
  crearPlan, editarPlan, mensajeError,
  type AdminCobros, type EstadoSuscripcion, type Intervalo, type Plan, type PlanIn,
} from "@/lib/admin"
import { CADA, INTERVALO, pesos } from "@/lib/pagos"
import { B, Boton, Campo, Etiqueta, fecha, INPUT, INPUT_STYLE, Metrica, SANS, Tabla, Tarjeta } from "./ui"

export const ESTADO_SUSCRIPCION: Record<EstadoSuscripcion, [string, "verde" | "ambar" | "gris" | "navy" | "rojo"]> = {
  activa: ["Activa", "verde"],
  pendiente: ["Pendiente de pago", "ambar"],
  pausada: ["Pausada", "ambar"],
  cancelada: ["Cancelada", "gris"],
  cortesia: ["Cortesía", "navy"],
}

const ESTADO_PAGO: Record<string, [string, "verde" | "ambar" | "gris" | "rojo"]> = {
  pagado: ["Pagado", "verde"],
  fallido: ["Cobro fallido", "rojo"],
}

const VACIO: PlanIn = { nombre: "", descripcion: null, precio: 0, intervalo_meses: 1, activo: true }

function FormPlan({ inicial, onGuardar, onCancelar }: {
  inicial: PlanIn; onGuardar: (p: PlanIn) => Promise<void>; onCancelar: () => void
}) {
  const [p, setP] = useState<PlanIn>(inicial)
  const [precio, setPrecio] = useState(inicial.precio ? String(inicial.precio) : "")
  const [error, setError] = useState("")
  const [guardando, setGuardando] = useState(false)

  async function guardar() {
    const n = Number(precio.replace(/[$,\s]/g, ""))
    if (!p.nombre.trim()) return setError("Ponle nombre al plan.")
    if (!(n > 0)) return setError("Escribe un precio mayor a cero.")
    setGuardando(true)
    setError("")
    try {
      await onGuardar({ nombre: p.nombre.trim(), descripcion: p.descripcion?.trim() || null, precio: n,
        intervalo_meses: p.intervalo_meses, activo: p.activo })
    } catch (e) {
      setError(mensajeError(e))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="rounded-[18px] p-4 space-y-3" style={{ background: B.PAPER, border: `1px solid ${B.LINE}` }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <Campo label="Nombre">
          <input className={INPUT} style={INPUT_STYLE} value={p.nombre} maxLength={80} placeholder="Ej. Consejo mensual"
            onChange={e => setP({ ...p, nombre: e.target.value })} />
        </Campo>
        <Campo label="Precio por cobro (MXN)" ayuda="Es lo que Stripe le cobra al cliente.">
          <input className={INPUT} style={INPUT_STYLE} value={precio} inputMode="decimal" placeholder="Ej. 2500"
            onChange={e => setPrecio(e.target.value)} />
        </Campo>
        <Campo label="Se cobra">
          <select className={INPUT} style={INPUT_STYLE} value={p.intervalo_meses}
            onChange={e => setP({ ...p, intervalo_meses: Number(e.target.value) as Intervalo })}>
            {[1, 3, 6, 12].map(m => <option key={m} value={m}>{CADA[m]} ({INTERVALO[m]})</option>)}
          </select>
        </Campo>
      </div>
      <Campo label="Descripción (la ve el cliente)">
        <input className={INPUT} style={INPUT_STYLE} value={p.descripcion ?? ""} maxLength={500}
          placeholder="Ej. Sesiones del Consejo cada mes, Todd y los cinco consejeros"
          onChange={e => setP({ ...p, descripcion: e.target.value })} />
      </Campo>
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      <div className="flex gap-2">
        <Boton onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar plan"}</Boton>
        <Boton variante="secundario" onClick={onCancelar}>Cancelar</Boton>
      </div>
    </div>
  )
}

function Planes({ planes, recargar }: { planes: Plan[]; recargar: () => Promise<void> }) {
  const [editando, setEditando] = useState<string | null>(null)
  const [error, setError] = useState("")

  async function alternar(p: Plan) {
    setError("")
    try {
      await editarPlan(p.id, { activo: !p.activo })
      await recargar()
    } catch (e) {
      setError(mensajeError(e))
    }
  }

  return (
    <Tarjeta titulo="Planes y precios"
      sub="Los clientes eligen entre los planes activos. Un precio nuevo aplica a suscripciones nuevas; las vigentes conservan el suyo."
      acciones={editando !== "nuevo" && (
        <Boton onClick={() => setEditando("nuevo")}><Plus className="h-4 w-4" /> Nuevo plan</Boton>
      )}>
      {editando === "nuevo" && (
        <FormPlan inicial={VACIO} onCancelar={() => setEditando(null)}
          onGuardar={async p => { await crearPlan(p); setEditando(null); await recargar() }} />
      )}
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      {planes.length === 0 && editando !== "nuevo" && (
        <p className="text-sm" style={{ color: B.MUTED }}>Aún no hay planes. Crea el primero con su precio.</p>
      )}
      <ul className="grid gap-3 md:grid-cols-2">
        {planes.map(p => editando === p.id ? (
          <li key={p.id} className="md:col-span-2">
            <FormPlan inicial={p} onCancelar={() => setEditando(null)}
              onGuardar={async body => { await editarPlan(p.id, body); setEditando(null); await recargar() }} />
          </li>
        ) : (
          <li key={p.id} className="rounded-[18px] p-4 flex items-start justify-between gap-3"
            style={{ border: `1px solid ${B.LINE}`, opacity: p.activo ? 1 : 0.6 }}>
            <div className="min-w-0">
              <p className="font-bold" style={{ ...SANS, color: B.INK }}>{p.nombre}</p>
              <p className="text-xl font-bold tabular-nums mt-1" style={{ ...SANS, color: B.INK }}>
                {pesos(p.precio, p.moneda)} <span className="text-xs font-medium" style={{ color: B.MUTED }}>{CADA[p.intervalo_meses]}</span>
              </p>
              {p.descripcion && <p className="text-xs mt-1" style={{ color: B.MUTED }}>{p.descripcion}</p>}
            </div>
            <div className="flex flex-col items-end gap-2 shrink-0">
              <button type="button" onClick={() => alternar(p)} aria-pressed={p.activo}>
                <Etiqueta tono={p.activo ? "verde" : "gris"}>{p.activo ? "Activo" : "Oculto"}</Etiqueta>
              </button>
              <button type="button" onClick={() => setEditando(p.id)}
                className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: B.INK2 }}>
                <Pencil className="h-3.5 w-3.5" /> Editar
              </button>
            </div>
          </li>
        ))}
      </ul>
    </Tarjeta>
  )
}

function Copiable({ texto }: { texto: string }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = () => navigator.clipboard?.writeText(texto).then(() => {
    setCopiado(true)
    setTimeout(() => setCopiado(false), 1500)
  })
  return (
    <span className="mt-1.5 flex items-center gap-2 rounded-[12px] px-3 py-2 font-mono text-xs break-all"
      style={{ background: "rgba(255,255,255,.1)" }}>
      {texto}
      <button type="button" onClick={copiar} className="shrink-0" aria-label="Copiar">
        {copiado ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </button>
    </span>
  )
}

function Conexion({ data }: { data: AdminCobros }) {
  if (data.configurado) {
    return (
      <div className="rounded-[26px] p-5 flex flex-wrap items-center gap-3" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
        <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: "#15803D" }} />
        <p className="text-sm flex-1 min-w-[220px]" style={{ color: B.INK2 }}>
          <strong style={{ color: B.INK }}>Stripe conectado</strong>
          {data.modo === "prueba" ? " en modo de prueba: los cobros no son reales." : " en modo real."}
          {!data.webhook_firmado && " Falta el secreto de firma del webhook (whsec_…) para validar los avisos."}
        </p>
        <Link href="/dashboard/suscripcion" className="text-xs font-bold underline" style={{ color: B.BNAVY }}>
          Ver la página de suscripción del cliente
        </Link>
      </div>
    )
  }
  return (
    <div className="rounded-[26px] p-6 space-y-3" style={{ background: B.BNAVY, color: "#fff" }}>
      <div className="flex items-center gap-2">
        <CircleAlert className="h-5 w-5" style={{ color: "rgba(255,255,255,.75)" }} />
        <h2 className="text-lg font-bold" style={SANS}>Falta conectar Stripe</h2>
      </div>
      <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,.75)" }}>
        Ya puedes dar de alta planes y cupones. Para cobrar, el equipo técnico necesita:
      </p>
      <ol className="list-decimal pl-5 text-sm space-y-1.5" style={{ color: "rgba(255,255,255,.85)" }}>
        <li>Una cuenta de Stripe a nombre de la empresa que recibe los pagos (razón social, RFC y cuenta bancaria).</li>
        <li>La <em>clave secreta</em> (Stripe → Desarrolladores → Claves de API). Primero la de prueba, que empieza con sk_test_.</li>
        <li>Un webhook (Desarrolladores → Webhooks) apuntando a:
          <Copiable texto={data.url_webhook} />
          <span className="mt-1.5 block" style={{ color: "rgba(255,255,255,.75)" }}>con estos eventos:</span>
          <span className="mt-1 block font-mono text-xs leading-relaxed" style={{ color: "rgba(255,255,255,.85)" }}>
            {data.eventos_webhook.join(" · ")}
          </span>
          <span className="mt-1.5 block" style={{ color: "rgba(255,255,255,.75)" }}>
            y su secreto de firma, que empieza con whsec_.
          </span>
        </li>
        <li>Activar el portal del cliente (Configuración → Facturación → Portal del cliente) para que cada
          cliente pueda cambiar su tarjeta y ver sus facturas.</li>
      </ol>
    </div>
  )
}

export default function CobrosAdmin({ data, recargar }: { data: AdminCobros; recargar: () => Promise<void> }) {
  const m = data.metricas
  return (
    <div className="space-y-6">
      <Conexion data={data} />

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metrica label="Suscriptores activos" valor={m.suscriptores_activos} sub="pagando con Stripe" />
        <Metrica label="Ingreso mensual" valor={pesos(m.ingreso_mensual)} sub="recurrente, llevado a pesos por mes" />
        <Metrica label="Cobrado en 30 días" valor={pesos(m.cobrado_30d)} sub={`${pesos(m.cobrado_total)} desde el inicio`} />
        <Metrica label="Cortesías vigentes" valor={m.cortesias_vigentes} sub="meses gratis por cupón" />
      </section>

      <Planes planes={data.planes} recargar={recargar} />

      <Tarjeta titulo="Suscripciones" sub="Cada cliente que se suscribió o canjeó meses gratis">
        <Tabla columnas={["Cliente", "Plan", "Estado", "Cobro", "Próximo cobro / vence"]} vacio={data.suscripciones.length === 0}>
          {data.suscripciones.map(s => {
            const [label, tono] = ESTADO_SUSCRIPCION[s.estado] ?? [s.estado, "gris"]
            return (
              <tr key={s.id} style={{ borderTop: `1px solid ${B.LINE}` }}>
                <td className="px-4 py-3">
                  <p className="font-semibold" style={{ color: B.INK }}>{s.empresa ?? "Sin empresa aún"}</p>
                  <p className="text-xs" style={{ color: B.MUTED }}>{s.email}</p>
                </td>
                <td className="px-4 py-3" style={{ color: B.INK2 }}>{s.plan ?? (s.estado === "cortesia" ? "Meses gratis" : "—")}</td>
                <td className="px-4 py-3"><Etiqueta tono={tono}>{label}</Etiqueta></td>
                <td className="px-4 py-3 tabular-nums whitespace-nowrap" style={{ color: B.INK2 }}>
                  {s.estado === "cortesia" ? "—" : `${pesos(s.monto, s.moneda)} ${CADA[s.intervalo_meses] ?? ""}`}
                  {s.cobros_con_descuento != null && (
                    <span className="block text-[11px]" style={{ color: B.MUTED }}>
                      con descuento {s.cobros_con_descuento} {s.cobros_con_descuento === 1 ? "cobro" : "cobros"} más
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 whitespace-nowrap" style={{ color: B.INK2 }}>
                  {s.estado === "cortesia" || (!s.proximo_cobro && s.vence)
                    ? <>{s.estado !== "cortesia" && "Termina "}{fecha(s.vence)}</>
                    : fecha(s.proximo_cobro)}
                </td>
              </tr>
            )
          })}
        </Tabla>
      </Tarjeta>

      <Tarjeta titulo="Pagos" sub="Las últimas 100 facturas de Stripe">
        <Tabla columnas={["Fecha", "Cliente", "Monto", "Estado"]} vacio={data.pagos.length === 0} minW={560}>
          {data.pagos.map(p => {
            const [label, tono] = ESTADO_PAGO[p.estado] ?? [p.estado, "gris"]
            return (
              <tr key={p.id} style={{ borderTop: `1px solid ${B.LINE}` }}>
                <td className="px-4 py-3 whitespace-nowrap" style={{ color: B.INK2 }}>{fecha(p.fecha)}</td>
                <td className="px-4 py-3">
                  <p className="font-semibold" style={{ color: B.INK }}>{p.empresa ?? p.email ?? "—"}</p>
                  {p.empresa && <p className="text-xs" style={{ color: B.MUTED }}>{p.email}</p>}
                </td>
                <td className="px-4 py-3 tabular-nums" style={{ color: B.INK }}>{pesos(p.monto, p.moneda)}</td>
                <td className="px-4 py-3"><Etiqueta tono={tono}>{label}</Etiqueta></td>
              </tr>
            )
          })}
        </Tabla>
      </Tarjeta>
    </div>
  )
}
