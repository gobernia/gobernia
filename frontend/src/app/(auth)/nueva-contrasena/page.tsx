"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import type { AuthError } from "@supabase/supabase-js"
import { supabase } from "@/lib/supabase"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// Mismo mínimo que al registrarse.
const MINIMO = 8

function mensajeDeError(error: AuthError) {
  if (error.code === "same_password") return "La contraseña nueva debe ser distinta de la anterior."
  if (error.code === "weak_password") return "Esa contraseña es muy débil. Combina letras y números."
  if (error.code === "session_not_found" || error.code === "reauthentication_needed" || error.status === 401)
    return "El enlace ya venció. Pide uno nuevo."
  return "No pudimos guardar la contraseña. Inténtalo de nuevo."
}

export default function NuevaContrasenaPage() {
  const router = useRouter()
  const [password,     setPassword]     = useState("")
  const [confirmacion, setConfirmacion] = useState("")
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState<string | null>(null)

  const coinciden = password === confirmacion
  const canSubmit = password.length >= MINIMO && coinciden

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.updateUser({ password })
    if (error) {
      setError(mensajeDeError(error))
      setLoading(false)
      return
    }
    router.push("/dashboard")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE }}
      className="w-full max-w-sm"
    >
      <div className="space-y-1 mb-8 text-center">
        <h1 className="text-2xl font-bold text-black tracking-tight">Elige tu nueva contraseña</h1>
        <p className="text-sm text-gray-400 italic font-light">Al guardarla entrarás a tu cuenta</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Contraseña nueva
          </label>
          <input
            type="password"
            autoFocus
            autoComplete="new-password"
            placeholder={`Mínimo ${MINIMO} caracteres`}
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Repite la contraseña
          </label>
          <input
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            value={confirmacion}
            onChange={e => setConfirmacion(e.target.value)}
            className="w-full h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
          />
          {confirmacion.length > 0 && !coinciden && (
            <p className="text-xs text-gray-400">Las contraseñas no coinciden.</p>
          )}
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-xs text-red-500 text-center"
          >
            {error}{" "}
            {error.startsWith("El enlace") && (
              <Link href="/recuperar" className="underline">Pedir otro</Link>
            )}
          </motion.p>
        )}

        <button
          type="submit"
          disabled={!canSubmit || loading}
          className="w-full h-12 rounded-xl bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium flex items-center justify-center gap-2 hover:bg-[var(--gob-ink)] transition-colors disabled:opacity-40 mt-2"
        >
          {loading ? "Guardando…" : <> Guardar y entrar <ArrowRight className="h-4 w-4" /> </>}
        </button>
      </form>
    </motion.div>
  )
}
