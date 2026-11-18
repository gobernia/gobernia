"use client"

// Pago DENTRO de gobernia.ai: la página de pago de Stripe (Checkout incrustado) en una
// ventana sobre Mi perfil. La tarjeta la captura Stripe en su propio marco; Gobernia nunca
// la ve. Al pagar, Stripe lleva al cliente a /dashboard/gracias (return_url de la sesión).

import { useEffect, useMemo } from "react"
import { Lock, X } from "lucide-react"
import { loadStripe } from "@stripe/stripe-js"
import { EmbeddedCheckout, EmbeddedCheckoutProvider } from "@stripe/react-stripe-js"

export default function PagoIncrustado({ clavePublica, clientSecret, onCerrar }: {
  clavePublica: string; clientSecret: string; onCerrar: () => void
}) {
  // Stripe.js se descarga solo cuando el cliente abre el pago.
  const stripe = useMemo(() => loadStripe(clavePublica), [clavePublica])

  useEffect(() => {
    const anterior = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar() }
    window.addEventListener("keydown", tecla)
    return () => {
      document.body.style.overflow = anterior
      window.removeEventListener("keydown", tecla)
    }
  }, [onCerrar])

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center" role="dialog" aria-modal="true"
      aria-label="Pago de la suscripción">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onCerrar} />
      <div className="relative flex max-h-[100dvh] w-full max-w-[560px] flex-col overflow-hidden bg-white shadow-xl sm:max-h-[92dvh] sm:rounded-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-5 py-3.5">
          <p className="flex items-center gap-2 text-sm font-semibold text-black">
            <Lock className="h-4 w-4 text-gray-400" /> Pago seguro con Stripe
          </p>
          <button type="button" onClick={onCerrar} aria-label="Cerrar el pago"
            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-black">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <EmbeddedCheckoutProvider stripe={stripe} options={{ clientSecret }}>
            <EmbeddedCheckout />
          </EmbeddedCheckoutProvider>
        </div>
      </div>
    </div>
  )
}
