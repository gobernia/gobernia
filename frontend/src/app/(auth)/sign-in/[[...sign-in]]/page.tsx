"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import { supabase } from "@/lib/supabase"
import GoogleSignInButton from "@/components/ui/GoogleSignInButton"

type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// /auth/callback manda aquí con ?error=link_invalido si el enlace del correo no sirvió
// (vencido, ya usado o abierto en otro navegador).
function AvisoEnlaceInvalido() {
  const params = useSearchParams()
  if (params.get("error") !== "link_invalido") return null
  return (
    <p className="mb-6 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-500 leading-relaxed text-center">
      El enlace ya no es válido. Si estabas recuperando tu contraseña,{" "}
      <Link href="/recuperar" className="text-black font-medium hover:underline">pide uno nuevo</Link>{" "}
      y ábrelo en el mismo navegador.
    </p>
  )
}

export default function SignInPage() {
  const router = useRouter()
  const [email,    setEmail]    = useState("")
  const [password, setPassword] = useState("")
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  const canSubmit = email.includes("@") && password.length >= 6

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError("Correo o contraseña incorrectos.")
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
        <h1 className="text-2xl font-bold text-black tracking-tight">Bienvenido de vuelta</h1>
        <p className="text-sm text-gray-400 italic font-light">Ingresa a tu espacio de gobierno corporativo</p>
      </div>

      <Suspense fallback={null}>
        <AvisoEnlaceInvalido />
      </Suspense>

      <GoogleSignInButton />

      <div className="flex items-center gap-3 my-6">
        <div className="h-px flex-1 bg-gray-100" />
        <span className="text-xs text-gray-400">o con tu correo</span>
        <div className="h-px flex-1 bg-gray-100" />
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

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Contraseña
            </label>
            <Link href="/recuperar" className="text-xs text-gray-400 hover:text-black hover:underline">
              ¿Olvidaste tu contraseña?
            </Link>
          </div>
          <input
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={e => setPassword(e.target.value)}
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
          {loading ? "Entrando…" : <> Entrar <ArrowRight className="h-4 w-4" /> </>}
        </button>
      </form>

      <p className="text-center text-sm text-gray-400 mt-8">
        ¿No tienes cuenta?{" "}
        <Link href="/sign-up" className="text-black font-medium hover:underline">
          Regístrate gratis
        </Link>
      </p>
    </motion.div>
  )
}
