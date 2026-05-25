"use client"

import { useEffect } from "react"
import { supabase } from "@/lib/supabase"
import { setAuthToken } from "@/lib/api"

/**
 * Sincroniza el token de Supabase con el cliente axios y maneja sesiones
 * inválidas (refresh token expirado / revocado) limpiando el storage local
 * sin romper la consola del usuario.
 */
export default function AuthSync() {
  useEffect(() => {
    // Cargar sesión actual al montar. Si el refresh token está roto
    // (común al volver después de mucho tiempo), Supabase tira
    // "Invalid Refresh Token: Refresh Token Not Found".
    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (error) {
          handleAuthError(error)
          return
        }
        setAuthToken(data.session?.access_token ?? null)
      })
      .catch(handleAuthError)

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        // Eventos que indican que el usuario quedó sin sesión
        if (event === "SIGNED_OUT" || event === "TOKEN_REFRESHED" && !session) {
          setAuthToken(null)
          return
        }
        setAuthToken(session?.access_token ?? null)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  return null
}

function handleAuthError(error: unknown) {
  const msg = (error as { message?: string })?.message ?? ""
  // Refresh token inválido / faltante → limpiar sesión silenciosamente.
  if (msg.toLowerCase().includes("refresh token") || msg.toLowerCase().includes("invalid")) {
    // No-await — fire and forget; signOut local borra el storage
    supabase.auth.signOut({ scope: "local" }).catch(() => {})
    setAuthToken(null)
    return
  }
  // Cualquier otro error: log silencioso para no contaminar consola pero
  // tampoco esconderlo si es algo más serio
  if (process.env.NODE_ENV === "development") {
    console.warn("[AuthSync]", msg || error)
  }
}
