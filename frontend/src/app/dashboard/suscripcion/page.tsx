"use client"

// SUSCRIPCIÓN del cliente: elige un plan, aplica un cupón y paga en Mercado Pago (la
// tarjeta nunca pasa por Gobernia). Al regresar de Mercado Pago, el servidor actualiza
// el estado. Por ahora el pago es opcional: nadie pierde acceso por no suscribirse.

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, Clock, Gift, Loader2, Lock, Ticket } from "lucide-react"
import { PageShell, PageHeader } from "@/components/ui/PageShell"
import { mensajeError } from "@/lib/admin"
import {
  CADA, canjearCupon, cancelarSuscripcion, getPagos, pesos, revisarCupon, suscribirme,
  type CuponRevisado, type EstadoPagos, type MiSuscripcion,
} from "@/lib/pagos"
import { B, Boton, fecha, INPUT, INPUT_STYLE, SANS } from "@/components/admin/ui"

function MiPlan({ s, onCancelar }: { s: MiSuscripcion; onCancelar: () => Promise<void> }) {
  const [confirmar, setConfirmar] = useState(false)
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState("")

  async function cancelar() {
    setTrabajando(true)
    setError("")
    try {
      await onCancelar()
    } catch (e) {
      setError(mensajeError(e, "No se pudo cancelar. Intenta de nuevo."))
    } finally {
      setTrabajando(false)
      setConfirmar(false)
    }
  }

  if (s.estado === "cancelada") return null

  if (s.estado === "cortesia") {
    return (
      <div className="rounded-[26px] p-6 flex items-start gap-3" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
        <Gift className="h-5 w-5 mt-0.5 shrink-0" style={{ color: B.BNAVY }} />
        <div>
          <p className="font-bold" style={{ ...SANS, color: B.INK }}>Tienes acceso de cortesía</p>
          <p className="text-sm mt-1" style={{ color: B.INK2 }}>Vigente hasta el {fecha(s.vence)}.</p>
        </div>
      </div>
    )
  }

  if (s.estado === "pendiente") {
    return (
      <div className="rounded-[26px] p-6 space-y-3" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
        <div className="flex items-start gap-3">
          <Clock className="h-5 w-5 mt-0.5 shrink-0" style={{ color: "#B45309" }} />
          <div>
            <p className="font-bold" style={{ ...SANS, color: B.INK }}>Tu pago está pendiente</p>
            <p className="text-sm mt-1" style={{ color: B.INK2 }}>
              {s.plan} · {pesos(s.monto, s.moneda)} {CADA[s.intervalo_meses]}. Si ya pagaste, en unos minutos
              aparecerá como activa.
            </p>
          </div>
        </div>
        {s.liga_pago && (
          <a href={s.liga_pago} className="inline-flex rounded-[14px] px-4 py-2 text-sm font-bold text-white"
            style={{ ...SANS, background: B.BNAVY }}>Continuar con el pago</a>
        )}
      </div>
    )
  }

  const pausada = s.estado === "pausada"
  return (
    <div className="rounded-[26px] p-6 space-y-4" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
      <div className="flex items-start gap-3">
        <CheckCircle2 className="h-5 w-5 mt-0.5 shrink-0" style={{ color: pausada ? "#B45309" : "#15803D" }} />
        <div>
          <p className="font-bold" style={{ ...SANS, color: B.INK }}>
            {pausada ? "Tu suscripción está pausada" : "Tu suscripción está activa"}
          </p>
          <p className="text-sm mt-1" style={{ color: B.INK2 }}>
            {s.plan} · {pesos(s.monto, s.moneda)} {CADA[s.intervalo_meses]}
            {s.cobros_con_descuento != null && s.monto < s.monto_regular &&
              ` con descuento (${s.cobros_con_descuento === 1 ? "1 cobro más" : `${s.cobros_con_descuento} cobros más`}; después ${pesos(s.monto_regular, s.moneda)})`}
          </p>
          {pausada
            ? <p className="text-sm mt-1" style={{ color: B.INK2 }}>Revisa tu tarjeta en tu cuenta de Mercado Pago.</p>
            : s.proximo_cobro && <p className="text-sm mt-1" style={{ color: B.MUTED }}>Próximo cobro: {fecha(s.proximo_cobro)}</p>}
        </div>
      </div>
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      {confirmar ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm" style={{ color: B.INK2 }}>¿Cancelar? No se harán más cobros.</span>
          <Boton onClick={cancelar} disabled={trabajando}>{trabajando ? "Cancelando…" : "Sí, cancelar"}</Boton>
          <Boton variante="secundario" onClick={() => setConfirmar(false)}>No</Boton>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirmar(true)} className="text-xs font-semibold underline" style={{ color: B.MUTED }}>
          Cancelar suscripción
        </button>
      )}
    </div>
  )
}

export default function SuscripcionPage() {
  const [data, setData] = useState<EstadoPagos | null>(null)
  const [error, setError] = useState(false)
  const [planId, setPlanId] = useState<string | null>(null)
  const [codigo, setCodigo] = useState("")
  const [cupon, setCupon] = useState<CuponRevisado | null>(null)
  const [aviso, setAviso] = useState("")
  const [trabajando, setTrabajando] = useState<"" | "cupon" | "pagar" | "canjear">("")

  const cargar = useCallback(() => getPagos()
    .then(d => {
      setData(d)
      setPlanId(id => id ?? d.planes[0]?.id ?? null)
      setError(false)
    })
    .catch(() => setError(true)), [])

  useEffect(() => { cargar() }, [cargar])

  function elegirPlan(id: string) {
    setPlanId(id)
    // El precio con cupón depende del plan.
    if (cupon && cupon.tipo !== "meses_gratis") revisarCupon(cupon.codigo, id).then(setCupon).catch(() => {})
  }

  async function aplicar() {
    setTrabajando("cupon")
    setAviso("")
    try {
      setCupon(await revisarCupon(codigo.trim(), planId ?? undefined))
    } catch (e) {
      setCupon(null)
      setAviso(mensajeError(e, "No se pudo revisar el cupón."))
    } finally {
      setTrabajando("")
    }
  }

  async function pagar() {
    if (!planId) return
    setTrabajando("pagar")
    setAviso("")
    try {
      window.location.href = await suscribirme(planId, cupon && cupon.tipo !== "meses_gratis" ? cupon.codigo : undefined)
    } catch (e) {
      setAviso(mensajeError(e, "No se pudo abrir el pago. Intenta de nuevo."))
      setTrabajando("")
    }
  }

  async function canjear() {
    if (!cupon) return
    setTrabajando("canjear")
    setAviso("")
    try {
      await canjearCupon(cupon.codigo)
      setCupon(null)
      setCodigo("")
      await cargar()
    } catch (e) {
      setAviso(mensajeError(e, "No se pudo canjear el cupón."))
    } finally {
      setTrabajando("")
    }
  }

  const s = data?.suscripcion
  const dePago = s && (s.estado === "activa" || s.estado === "pausada")
  const plan = data?.planes.find(p => p.id === planId)

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: B.PAPER, color: B.INK }}>
      <PageHeader eyebrow="Mi cuenta" title="Suscripción" />
      <main>
        <PageShell className="py-10 space-y-6 max-w-[880px]">
          {!data && !error && (
            <div className="flex items-center justify-center py-24"><Loader2 className="h-6 w-6 animate-spin" style={{ color: B.MUTED }} /></div>
          )}
          {error && <p className="text-sm" style={{ color: B.MUTED }}>No se pudo cargar tu suscripción. Intenta de nuevo.</p>}

          {data && s && <MiPlan s={s} onCancelar={async () => { await cancelarSuscripcion(); await cargar() }} />}

          {data && !dePago && (
            <>
              {data.planes.length === 0 ? (
                <div className="rounded-[26px] p-6" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
                  <p className="font-bold" style={{ ...SANS, color: B.INK }}>Por ahora Gobernia no tiene costo</p>
                  <p className="text-sm mt-1" style={{ color: B.INK2 }}>Sigue usando la plataforma con normalidad.</p>
                </div>
              ) : (
                <section className="space-y-3">
                  <h2 className="text-lg font-bold" style={{ ...SANS, color: B.INK }}>Elige tu plan</h2>
                  <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Planes">
                    {data.planes.map(p => {
                      const sel = p.id === planId
                      return (
                        <button key={p.id} type="button" role="radio" aria-checked={sel} onClick={() => elegirPlan(p.id)}
                          className="rounded-[22px] p-5 text-left transition"
                          style={{ background: B.CARD, border: `2px solid ${sel ? B.BNAVY : B.LINE}` }}>
                          <p className="font-bold" style={{ ...SANS, color: B.INK }}>{p.nombre}</p>
                          <p className="mt-1 text-2xl font-bold tabular-nums" style={{ ...SANS, color: B.INK }}>
                            {pesos(p.precio, p.moneda)} <span className="text-sm font-medium" style={{ color: B.MUTED }}>{CADA[p.intervalo_meses]}</span>
                          </p>
                          {p.descripcion && <p className="text-sm mt-2" style={{ color: B.INK2 }}>{p.descripcion}</p>}
                        </button>
                      )
                    })}
                  </div>
                </section>
              )}

              <section className="rounded-[26px] p-6 space-y-3" style={{ background: B.CARD, border: `1px solid ${B.LINE}` }}>
                <p className="flex items-center gap-2 text-sm font-bold" style={{ ...SANS, color: B.INK }}>
                  <Ticket className="h-4 w-4" /> ¿Tienes un cupón?
                </p>
                <div className="flex flex-wrap gap-2">
                  <input className={`${INPUT} max-w-xs`} style={INPUT_STYLE} value={codigo} maxLength={30}
                    placeholder="Escribe tu código" aria-label="Código de cupón"
                    onChange={e => { setCodigo(e.target.value.replace(/\s/g, "").toUpperCase()); setCupon(null) }}
                    onKeyDown={e => { if (e.key === "Enter" && codigo.trim()) aplicar() }} />
                  <Boton variante="secundario" onClick={aplicar} disabled={!codigo.trim() || trabajando === "cupon"}>
                    {trabajando === "cupon" ? "Revisando…" : "Aplicar"}
                  </Boton>
                </div>
                {cupon && (
                  <div className="flex flex-wrap items-center gap-3 text-sm" style={{ color: B.INK2 }}>
                    <span><strong style={{ color: B.INK }}>{cupon.codigo}</strong>: {cupon.resumen}.</span>
                    {cupon.tipo === "meses_gratis" ? (
                      <Boton onClick={canjear} disabled={trabajando === "canjear"}>
                        {trabajando === "canjear" ? "Canjeando…" : "Canjear"}
                      </Boton>
                    ) : cupon.precio_final != null && cupon.precio != null && plan && (
                      <span>
                        <s>{pesos(cupon.precio, plan.moneda)}</s>{" "}
                        <strong style={{ color: B.INK }}>{pesos(cupon.precio_final, plan.moneda)}</strong> {CADA[plan.intervalo_meses]}
                      </span>
                    )}
                  </div>
                )}
              </section>

              {aviso && <p className="text-sm font-medium" style={{ color: B.ACCENT }}>{aviso}</p>}

              {plan && (
                <div className="space-y-2">
                  <Boton onClick={pagar} disabled={!data.cobros_activos || trabajando === "pagar"} className="!px-6 !py-3">
                    {trabajando === "pagar" ? "Abriendo Mercado Pago…" : "Suscribirme con Mercado Pago"}
                  </Boton>
                  <p className="flex items-center gap-1.5 text-xs" style={{ color: B.MUTED }}>
                    <Lock className="h-3.5 w-3.5" />
                    {data.cobros_activos
                      ? "Pagas en Mercado Pago con tarjeta; Gobernia no guarda los datos de tu tarjeta. Puedes cancelar cuando quieras."
                      : "Los pagos se activarán pronto."}
                  </p>
                </div>
              )}
            </>
          )}
        </PageShell>
      </main>
    </div>
  )
}
