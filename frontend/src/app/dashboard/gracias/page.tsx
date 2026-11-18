"use client"

// AGRADECIMIENTO después de pagar. Stripe trae al cliente aquí con ?session_id=…; la página
// confirma con el servidor (que pregunta a Stripe) que esa compra es de este cliente y ya se
// pagó. Solo entonces, y una sola vez por compra, registra la conversión: evento "purchase"
// de Google Analytics. Aquí van también los pixeles que se agreguen después (Meta, etc.).

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, CheckCircle2, Clock, Loader2 } from "lucide-react"
import { PageHeader, PageShell } from "@/components/ui/PageShell"
import { CADA, confirmarPago, pesos, type ConfirmacionPago } from "@/lib/pagos"

type Vista = "cargando" | "pagado" | "confirmando" | "error"

const INTENTOS = 4 // si Stripe aún no marca el pago, se vuelve a preguntar unos segundos

function registrarCompra(c: ConfirmacionPago) {
  const clave = `gobernia_compra_${c.transaccion}`
  try {
    if (localStorage.getItem(clave)) return // recargó la página: no se cuenta dos veces
    localStorage.setItem(clave, "1")
  } catch { /* sin almacenamiento: GA4 igual descarta compras repetidas por transaction_id */ }
  const w = window as unknown as { gtag?: (...args: unknown[]) => void }
  w.gtag?.("event", "purchase", {
    transaction_id: c.transaccion,
    value: c.monto,
    currency: c.moneda,
    items: [{ item_id: `plan-${c.intervalo_meses}m`, item_name: c.plan ?? "Suscripción", price: c.monto, quantity: 1 }],
  })
}

const PRIMARIO = "inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--gob-navy)] px-5 py-2.5 text-sm font-medium text-[var(--gob-bone)] transition-colors hover:bg-[var(--gob-ink)]"
const SECUNDARIO = "inline-flex items-center justify-center gap-2 rounded-xl border border-gray-200 px-5 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)]"

export default function GraciasPage() {
  const [vista, setVista] = useState<Vista>("cargando")
  const [compra, setCompra] = useState<ConfirmacionPago | null>(null)

  const revisar = useCallback(async () => {
    const sesion = new URLSearchParams(window.location.search).get("session_id")
    if (!sesion) { setVista("error"); return }
    setVista("cargando")
    for (let i = 0; i < INTENTOS; i++) {
      try {
        const c = await confirmarPago(sesion)
        if (c.pagado) {
          setCompra(c)
          setVista("pagado")
          registrarCompra(c)
          return
        }
      } catch {
        setVista("error")
        return
      }
      await new Promise(r => setTimeout(r, 2500))
    }
    setVista("confirmando")
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- consulta al servidor al llegar
    revisar()
  }, [revisar])

  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">
      <PageHeader eyebrow="Suscripción" title="Gracias" />
      <main>
        <PageShell className="py-14">
          <div className="mx-auto max-w-lg text-center">
            {vista === "cargando" && (
              <div className="space-y-4 py-10">
                <Loader2 className="mx-auto h-7 w-7 animate-spin text-gray-300" />
                <p className="text-sm text-gray-500">Confirmando tu pago con Stripe…</p>
              </div>
            )}

            {vista === "pagado" && compra && (
              <div className="space-y-6">
                <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
                  <CheckCircle2 className="h-9 w-9 text-green-600" />
                </span>
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold tracking-tight text-black">¡Gracias! Tu suscripción está activa</h2>
                  <p className="text-sm leading-relaxed text-gray-500">
                    Pagaste <strong className="text-black">{pesos(compra.monto, compra.moneda)}</strong>
                    {compra.plan ? <> por el plan <strong className="text-black">{compra.plan}</strong></> : null}.
                    {" "}Se renueva automáticamente {CADA[compra.intervalo_meses] ?? ""}.
                  </p>
                  <p className="text-sm leading-relaxed text-gray-500">
                    En Mi perfil puedes ver tus facturas, cambiar tu tarjeta o cancelar cuando quieras.
                  </p>
                </div>
                <div className="flex flex-col justify-center gap-3 sm:flex-row">
                  <Link href="/dashboard" className={PRIMARIO}>Ir al inicio <ArrowRight className="h-4 w-4" /></Link>
                  <Link href="/dashboard/datos#suscripcion" className={SECUNDARIO}>Ver mi suscripción</Link>
                </div>
              </div>
            )}

            {vista === "confirmando" && (
              <div className="space-y-6">
                <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-50">
                  <Clock className="h-8 w-8 text-amber-600" />
                </span>
                <div className="space-y-2">
                  <h2 className="text-xl font-bold tracking-tight text-black">Estamos confirmando tu pago</h2>
                  <p className="text-sm leading-relaxed text-gray-500">
                    Puede tardar unos minutos. No necesitas volver a pagar: en cuanto Stripe lo confirme, tu
                    suscripción aparecerá como activa en Mi perfil.
                  </p>
                </div>
                <div className="flex flex-col justify-center gap-3 sm:flex-row">
                  <button type="button" onClick={revisar} className={PRIMARIO}>Revisar de nuevo</button>
                  <Link href="/dashboard/datos#suscripcion" className={SECUNDARIO}>Ir a Mi perfil</Link>
                </div>
              </div>
            )}

            {vista === "error" && (
              <div className="space-y-6 py-6">
                <div className="space-y-2">
                  <h2 className="text-xl font-bold tracking-tight text-black">No encontramos ese pago</h2>
                  <p className="text-sm leading-relaxed text-gray-500">
                    Revisa el estado de tu suscripción en Mi perfil. Si ya pagaste y no aparece, escríbenos.
                  </p>
                </div>
                <Link href="/dashboard/datos#suscripcion" className={PRIMARIO}>Ir a Mi perfil</Link>
              </div>
            )}
          </div>
        </PageShell>
      </main>
    </div>
  )
}
