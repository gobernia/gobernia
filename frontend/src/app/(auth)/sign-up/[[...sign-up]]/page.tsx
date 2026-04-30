"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Mail } from "lucide-react"
import { supabase } from "@/lib/supabase"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

export default function SignUpPage() {
  const router   = useRouter()
  const [email,    setEmail]    = useState("")
  const [password, setPassword] = useState("")
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [done,     setDone]     = useState(false)

  const canSubmit = email.includes("@") && password.length >= 8

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }
    const { data } = await supabase.auth.getSession()
    if (data.session) {
      router.push("/onboarding/etapa-1")
    } else {
      setDone(true)
      setLoading(false)
    }
  }

  if (done) {
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
          <p className="text-sm text-gray-400 leading-relaxed">
            Enviamos un enlace de confirmación a <span className="text-black font-medium">{email}</span>.
            Una vez que lo confirmes, podrás iniciar sesión.
          </p>
        </div>
        <Link
          href="/sign-in"
          className="inline-flex items-center gap-2 text-sm font-semibold text-black hover:underline"
        >
          Ir a iniciar sesión <ArrowRight className="h-3.5 w-3.5" />
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
        <h1 className="text-2xl font-bold text-black tracking-tight">Crea tu cuenta</h1>
        <p className="text-sm text-gray-400 font-display italic">Empieza a gobernar tu empresa con inteligencia</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
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

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Contraseña
          </label>
          <input
            type="password"
            autoComplete="new-password"
            placeholder="Mínimo 8 caracteres"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full h-12 rounded-xl border-2 border-gray-100 px-4 text-sm text-black placeholder:text-gray-300 focus:border-black focus:outline-none transition-colors"
          />
          {password.length > 0 && password.length < 8 && (
            <p className="text-xs text-gray-400">{8 - password.length} caracteres más</p>
          )}
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
          className="w-full h-12 rounded-xl bg-black text-white text-sm font-semibold flex items-center justify-center gap-2 hover:bg-gray-900 transition-colors disabled:opacity-40 mt-2"
        >
          {loading ? "Creando cuenta…" : <> Crear cuenta <ArrowRight className="h-4 w-4" /> </>}
        </button>
      </form>

      <p className="text-center text-sm text-gray-400 mt-8">
        ¿Ya tienes cuenta?{" "}
        <Link href="/sign-in" className="text-black font-semibold hover:underline">
          Inicia sesión
        </Link>
      </p>
    </motion.div>
  )
}
