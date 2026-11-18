"use client"

// SUSCRIPCIÓN del cliente, dentro de Mi perfil: elige un plan, aplica un cupón y paga en la
// página de Stripe (la tarjeta nunca pasa por Gobernia). Stripe regresa a Mi perfil con
// ?pago=listo (pagó) o ?pago=volver (canceló o salió del portal). Tarjeta y facturas, en el
// portal de Stripe. El pago es opcional: nadie pierde acceso por no suscribirse.
//
// Quién la ve: los clientes, solo cuando Stripe cobra en modo real (o si ya tienen una
// suscripción o cortesía); el super admin, siempre, para revisarla antes de lanzar.

import { useCallback, useEffect, useRef, useState } from "react"
import dynamic from "next/dynamic"
import { CheckCircle2, Clock, CreditCard, Eye, Gift, Lock, Ticket } from "lucide-react"
import { esAdmin, mensajeError } from "@/lib/admin"
import {
  CADA, abrirPortal, canjearCupon, cancelarSuscripcion, getPagos, pesos, revisarCupon, suscribirme,
  type CuponRevisado, type EstadoPagos, type MiSuscripcion,
} from "@/lib/pagos"
import { B, Boton, fecha, INPUT, INPUT_STYLE, SANS } from "@/components/admin/ui"

// La ventana de pago (Stripe.js) solo se descarga cuando el cliente decide pagar.
const PagoIncrustado = dynamic(() => import("./PagoIncrustado"), { ssr: false })

function MiPlan({ s, regreso, onCancelar }: { s: MiSuscripcion; regreso: boolean; onCancelar: () => Promise<void> }) {
  const [confirmar, setConfirmar] = useState(false)
  const [trabajando, setTrabajando] = useState(false)
  const [abriendo, setAbriendo] = useState(false)
  const [error, setError] = useState("")

  async function administrar() {
    setAbriendo(true)
    setError("")
    try {
      window.location.href = await abrirPortal()
    } catch (e) {
      setError(mensajeError(e, "No se pudo abrir el portal de pagos. Intenta de nuevo."))
      setAbriendo(false)
    }
  }

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
      <div className="flex items-start gap-3">
        <Gift className="h-5 w-5 mt-0.5 shrink-0" style={{ color: B.BNAVY }} />
        <div>
          <p className="text-sm font-bold text-black">Tienes acceso de cortesía</p>
          <p className="text-sm text-gray-500 mt-0.5">Vigente hasta el {fecha(s.vence)}.</p>
        </div>
      </div>
    )
  }

  if (s.estado === "pendiente") {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-3">
          <Clock className="h-5 w-5 mt-0.5 shrink-0" style={{ color: "#B45309" }} />
          <div>
            <p className="text-sm font-bold text-black">
              {regreso ? "Estamos confirmando tu pago" : "Tu pago está pendiente"}
            </p>
            <p className="text-sm text-gray-500 mt-0.5">
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
  // Cancelada por el cliente: ya no se renueva, pero conserva el acceso hasta `vence`.
  const termina = !s.proximo_cobro && s.vence ? s.vence : null
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <CheckCircle2 className="h-5 w-5 mt-0.5 shrink-0" style={{ color: pausada ? "#B45309" : "#15803D" }} />
        <div>
          <p className="text-sm font-bold text-black">
            {pausada ? "No pudimos cobrar tu tarjeta" : termina ? "Tu suscripción ya no se renovará" : "Tu suscripción está activa"}
          </p>
          <p className="text-sm text-gray-500 mt-0.5">
            {s.plan} · {pesos(s.monto, s.moneda)} {CADA[s.intervalo_meses]}
            {s.cobros_con_descuento != null && s.monto < s.monto_regular &&
              ` con descuento (${s.cobros_con_descuento === 1 ? "1 cobro más" : `${s.cobros_con_descuento} cobros más`}; después ${pesos(s.monto_regular, s.moneda)})`}
          </p>
          {pausada
            ? <p className="text-sm text-gray-500 mt-0.5">Actualiza tu tarjeta en “Administrar mi pago” y Stripe volverá a intentar el cobro.</p>
            : termina
              ? <p className="text-sm text-gray-500 mt-0.5">Conservas el acceso hasta el {fecha(termina)}. No se harán más cobros.</p>
              : s.proximo_cobro && <p className="text-xs text-gray-400 mt-1">Próximo cobro: {fecha(s.proximo_cobro)}</p>}
        </div>
      </div>
      {error && <p className="text-xs font-medium" style={{ color: B.ACCENT }}>{error}</p>}
      <div className="flex flex-wrap items-center gap-4">
        {s.puede_administrar && (
          <Boton variante="secundario" onClick={administrar} disabled={abriendo}>
            <CreditCard className="h-4 w-4" /> {abriendo ? "Abriendo…" : "Administrar mi pago"}
          </Boton>
        )}
        {!termina && !confirmar && (
          <button type="button" onClick={() => setConfirmar(true)} className="text-xs font-semibold text-gray-400 underline hover:text-gray-600">
            Cancelar suscripción
          </button>
        )}
      </div>
      {!termina && confirmar && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-600">
            ¿Cancelar? Ya no se renovará{s.proximo_cobro ? ` y conservas el acceso hasta el ${fecha(s.proximo_cobro)}` : ""}.
          </span>
          <Boton onClick={cancelar} disabled={trabajando}>{trabajando ? "Cancelando…" : "Sí, cancelar"}</Boton>
          <Boton variante="secundario" onClick={() => setConfirmar(false)}>No</Boton>
        </div>
      )}
    </div>
  )
}

export default function SuscripcionCuenta({ className = "" }: { className?: string }) {
  // Stripe regresa a Mi perfil con ?pago=listo (pagó) o ?pago=volver.
  const [regreso] = useState(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).get("pago") === "listo")
  const [admin, setAdmin] = useState(false)
  const [data, setData] = useState<EstadoPagos | null>(null)
  const [error, setError] = useState(false)
  const [planId, setPlanId] = useState<string | null>(null)
  const [codigo, setCodigo] = useState("")
  const [cupon, setCupon] = useState<CuponRevisado | null>(null)
  const [aviso, setAviso] = useState("")
  const [trabajando, setTrabajando] = useState<"" | "cupon" | "pagar" | "canjear">("")
  const [pago, setPago] = useState<{ clavePublica: string; clientSecret: string } | null>(null)
  const ref = useRef<HTMLElement>(null)
  const yaBajo = useRef(false)

  const cargar = useCallback(() => getPagos()
    .then(d => {
      setData(d)
      setPlanId(id => id ?? d.planes[0]?.id ?? null)
      setError(false)
    })
    .catch(() => setError(true)), [])

  useEffect(() => {
    cargar()
    esAdmin().then(setAdmin)
  }, [cargar])

  const s = data?.suscripcion
  const tieneSuscripcion = !!s && s.estado !== "cancelada"
  const paraClientes = !!data?.cobros_activos && data.modo === "produccion"
  const visible = admin || (!!data && (paraClientes || tieneSuscripcion))

  // Al volver de Stripe (o con la liga #suscripcion), baja hasta esta sección una sola vez.
  useEffect(() => {
    if (!visible || !data || yaBajo.current) return
    const params = new URLSearchParams(window.location.search)
    if (!params.has("pago") && window.location.hash !== "#suscripcion") return
    yaBajo.current = true
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    if (params.has("pago")) window.history.replaceState(null, "", `${window.location.pathname}#suscripcion`)
  }, [visible, data])

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
      const r = await suscribirme(planId, cupon && cupon.tipo !== "meses_gratis" ? cupon.codigo : undefined)
      if (r.modo === "incrustado") {
        setPago({ clavePublica: r.clave_publica, clientSecret: r.client_secret })
        setTrabajando("")
      } else {
        window.location.href = r.liga_pago
      }
    } catch (e) {
      setAviso(mensajeError(e, "No se pudo abrir el pago. Intenta de nuevo."))
      setTrabajando("")
    }
  }

  // Cerró la ventana sin pagar: se descarta ese intento (si sí pagó, el servidor lo detecta
  // y no la cancela). Al pagar no se llega aquí: Stripe lleva directo a /dashboard/gracias.
  const cerrarPago = useCallback(() => {
    setPago(null)
    cancelarSuscripcion().catch(() => {}).finally(() => { cargar() })
  }, [cargar])

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

  if (!visible) return null

  const dePago = s && (s.estado === "activa" || s.estado === "pausada")
  const plan = data?.planes.find(p => p.id === planId)

  return (
    <section ref={ref} id="suscripcion" className={`scroll-mt-24 border border-gray-100 rounded-2xl p-6 space-y-5 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-[var(--gob-navy)]/[0.06] text-[var(--gob-navy)] flex items-center justify-center shrink-0">
            <CreditCard className="h-4 w-4" />
          </span>
          <h2 className="text-base font-bold text-black tracking-tight">Suscripción</h2>
        </div>
        {admin && !paraClientes && !tieneSuscripcion && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
            <Eye className="h-3.5 w-3.5" /> Solo tú la ves: tus clientes la verán cuando Stripe cobre en modo real
          </span>
        )}
      </div>

      {!data && !error && <p className="text-sm text-gray-400">Cargando…</p>}
      {error && <p className="text-sm text-gray-400">No se pudo cargar tu suscripción. Intenta de nuevo.</p>}

      {data && s && <MiPlan s={s} regreso={regreso} onCancelar={async () => { await cancelarSuscripcion(); await cargar() }} />}

      {data && !dePago && (
        <div className="space-y-5 max-w-3xl">
          {data.planes.length === 0 ? (
            <div>
              <p className="text-sm font-bold text-black">Por ahora Gobernia no tiene costo</p>
              <p className="text-sm text-gray-500 mt-0.5">Sigue usando la plataforma con normalidad.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              <p className="text-xs font-medium tracking-wide text-gray-400 uppercase">Elige tu plan</p>
              <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Planes">
                {data.planes.map(p => {
                  const sel = p.id === planId
                  return (
                    <button key={p.id} type="button" role="radio" aria-checked={sel} onClick={() => elegirPlan(p.id)}
                      className="rounded-xl p-4 text-left transition"
                      style={{ background: B.CARD, border: `2px solid ${sel ? B.BNAVY : B.LINE}` }}>
                      <p className="text-sm font-bold text-black">{p.nombre}</p>
                      <p className="mt-1 text-2xl font-bold tabular-nums text-black">
                        {pesos(p.precio, p.moneda)} <span className="text-sm font-medium text-gray-400">{CADA[p.intervalo_meses]}</span>
                      </p>
                      {p.descripcion && <p className="text-sm text-gray-500 mt-1.5">{p.descripcion}</p>}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          <div className="space-y-2.5">
            <p className="flex items-center gap-2 text-sm font-semibold text-black">
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
              <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
                <span><strong className="text-black">{cupon.codigo}</strong>: {cupon.resumen}.</span>
                {cupon.tipo === "meses_gratis" ? (
                  <Boton onClick={canjear} disabled={trabajando === "canjear"}>
                    {trabajando === "canjear" ? "Canjeando…" : "Canjear"}
                  </Boton>
                ) : cupon.precio_final != null && cupon.precio != null && plan && (
                  <span>
                    <s>{pesos(cupon.precio, plan.moneda)}</s>{" "}
                    <strong className="text-black">{pesos(cupon.precio_final, plan.moneda)}</strong> {CADA[plan.intervalo_meses]}
                  </span>
                )}
              </div>
            )}
          </div>

          {aviso && <p className="text-sm font-medium" style={{ color: B.ACCENT }}>{aviso}</p>}

          {plan && (
            <div className="space-y-2">
              <Boton onClick={pagar} disabled={!data.cobros_activos || trabajando === "pagar"} className="!px-6 !py-3">
                {trabajando === "pagar" ? "Abriendo el pago…" : "Suscribirme"}
              </Boton>
              <p className="flex items-center gap-1.5 text-xs text-gray-400">
                <Lock className="h-3.5 w-3.5 shrink-0" />
                {data.cobros_activos
                  ? "El pago lo procesa Stripe de forma segura; Gobernia no guarda los datos de tu tarjeta. Puedes cancelar cuando quieras."
                  : "Los pagos se activarán pronto."}
              </p>
            </div>
          )}
        </div>
      )}

      {pago && <PagoIncrustado clavePublica={pago.clavePublica} clientSecret={pago.clientSecret} onCerrar={cerrarPago} />}
    </section>
  )
}
