"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Mail } from "lucide-react"
import type { AuthError } from "@supabase/supabase-js"
import { supabase } from "@/lib/supabase"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

function mensajeDeError(error: AuthError) {
  if (error.code === "over_email_send_rate_limit" || error.status === 429)
    return "Ya pediste varios enlaces. Espera unos minutos e inténtalo de nuevo."
  if (error.code === "email_address_not_authorized")
    return "No pudimos enviar el enlace a este correo. Escríbenos a hola@gobernia.ai y te ayudamos a entrar."
  return "No pudimos enviar el enlace. Inténtalo de nuevo en unos minutos."
}

export default function RecuperarPage() {
  const [email,   setEmail]   = useState("")
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)

  const canSubmit = email.includes("@")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    // El enlace vuelve a /auth/callback, que lo reconoce como recuperación y lleva a /nueva-contrasena.
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/auth/callback`,
    })
    if (error) {
      setError(mensajeDeError(error))
      setLoading(false)
      return
    }
    setEnviado(true)
    setLoading(false)
  }

  if (enviado) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE }}
        className="w-full max-w-sm text-center space-y-5"
      >
        <div className="w-14 h-14 rounded-2xl border-2 border-gray-100 flex items-center justify-center mx-auto">
          <Mail className="h-6 w-6 text-gray-400" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-black tracking-tight">Revisa tu correo</h2>
          {/* Supabase no dice si el correo tiene cuenta, así que el mensaje es el mismo en ambos casos. */}
          <p className="text-sm text-gray-400 leading-relaxed">
            Si hay una cuenta con <span className="text-black font-medium">{email.trim()}</span>, te
            enviamos un enlace para elegir una contraseña nueva. Ábrelo en este mismo navegador.
          </p>
        </div>
        <Link
          href="/sign-in"
          className="inline-flex items-center gap-2 text-sm font-medium text-black hover:underline"
        >
          Volver a iniciar sesión <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE }}
      className="w-full max-w-sm"
    >
      <div className="space-y-1 mb-8 text-center">
        <h1 className="text-2xl font-bold text-black tracking-tight">Recupera tu contraseña</h1>
        <p className="text-sm text-gray-400 italic font-light">Te enviamos un enlace para elegir una nueva</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Correo electrónico
          </label>
          <input
            type="email"
            autoFocus
            autoComplete="email"
            placeholder="correo@empresa.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
          />
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-xs text-red-500 text-center"
          >
            {error}
          </motion.p>
        )}

        <button
          type="submit"
          disabled={!canSubmit || loading}
          className="w-full h-12 rounded-xl bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium flex items-center justify-center gap-2 hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-40 mt-2"
        >
          {loading ? "Enviando…" : <> Enviar enlace <ArrowRight className="h-4 w-4" /> </>}
        </button>
      </form>

      <div className="mt-6 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
        <p className="text-xs text-gray-500 leading-relaxed">
          Si te registraste con Google, no necesitas contraseña: entra con el botón de Google.
        </p>
      </div>

      <p className="text-center text-sm text-gray-400 mt-8">
        ¿La recordaste?{" "}
        <Link href="/sign-in" className="text-black font-medium hover:underline">
          Inicia sesión
        </Link>
      </p>
    </motion.div>
  )
}
