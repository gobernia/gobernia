"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  Home, ClipboardList, Users,
  FileSearch, LayoutGrid,
  Settings, LogOut, Menu, X,
} from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"

const LINKS = [
  { href: "/dashboard", label: "Inicio", exact: true, icon: Home },
  { href: "/dashboard/plan", label: "Plan", exact: false, icon: ClipboardList },
  { href: "/dashboard/diagnostico", label: "Diagnóstico", exact: false, icon: FileSearch },
  { href: "/dashboard/foda", label: "FODA", exact: false, icon: LayoutGrid },
  // Oculto por ahora (no se borra; la página /dashboard/compromisos sigue existiendo):
  // { href: "/dashboard/compromisos", label: "Compromisos", exact: false, icon: CheckSquare },
  { href: "/dashboard/consejo", label: "Tu consejo", exact: false, icon: Users },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { reset } = useOnboardingStore()
  const [open, setOpen] = useState(false)

  const signOut = async () => {
    await supabase.auth.signOut()
    reset()
    router.push("/")
  }

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  const navBody = (
    <>
      <Link
        href="/dashboard"
        onClick={() => setOpen(false)}
        className="font-bold tracking-widest text-sm px-4 py-4 block"
      >
        GOBERNIA
      </Link>
      <nav className="flex-1 px-2 space-y-1">
        {LINKS.map(l => {
          const Icon = l.icon
          const active = isActive(l.href, l.exact)
          return (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors border-l-2 ${
                active
                  ? "bg-white/10 font-medium border-[var(--gob-bone)]"
                  : "opacity-70 hover:opacity-100 hover:bg-white/5 border-transparent"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {l.label}
            </Link>
          )
        })}
      </nav>
      <div className="border-t border-white/10 px-2 py-3 space-y-1">
        <Link
          href="/dashboard/datos"
          onClick={() => setOpen(false)}
          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
            isActive("/dashboard/datos", false)
              ? "bg-white/10 font-medium"
              : "opacity-70 hover:opacity-100 hover:bg-white/5"
          }`}
        >
          <Settings className="h-4 w-4 shrink-0" /> Datos
        </Link>
        <button
          onClick={signOut}
          className="w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm opacity-70 hover:opacity-100 hover:bg-white/5"
        >
          <LogOut className="h-4 w-4 shrink-0" /> Salir
        </button>
      </div>
    </>
  )

  return (
    <>
      {/* Móvil: botón hamburguesa */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-lg p-2"
        aria-label="Abrir menú"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Móvil: overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative w-60 h-dvh bg-[var(--gob-navy)] text-[var(--gob-bone)] flex flex-col">
            <button
              autoFocus
              onClick={() => setOpen(false)}
              className="absolute top-3 right-3"
              aria-label="Cerrar menú"
            >
              <X className="h-5 w-5" />
            </button>
            {navBody}
          </aside>
        </div>
      )}

      {/* Escritorio: sidebar fijo */}
      <aside className="hidden md:flex fixed left-0 top-0 h-dvh w-60 bg-[var(--gob-navy)] text-[var(--gob-bone)] flex-col z-40">
        {navBody}
      </aside>
    </>
  )
}
