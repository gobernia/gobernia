"use client"

import { useEffect } from "react"
import { supabase } from "@/lib/supabase"
import { setAuthToken } from "@/lib/api"

export default function AuthSync() {
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setAuthToken(data.session?.access_token ?? null)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthToken(session?.access_token ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  return null
}
