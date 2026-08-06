"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  Home, Users, FileSearch, Library,
  Settings, LogOut, Menu, X, ImagePlus, Loader2,
} from "lucide-react"
import { Map, CalendarCheck } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { useOnboardingStore } from "@/lib/store"
import GoberniaLogo from "@/components/ui/GoberniaLogo"
import { getLogo, uploadLogo, LOGO_ACCEPT } from "@/lib/logo"

// Menú lateral bento: riel oscuro pegado al borde. Arriba, el LOGO DE LA EMPRESA
// (clic para cambiarlo). Abajo, el logo de Gobernia sobre "Mi perfil". La pestaña
// activa usa el "hueco" (.sb-active) que se recorta hacia el contenido (papel).
const LINKS = [
  { href: "/dashboard", label: "Inicio", exact: true, icon: Home },
  { href: "/dashboard/diagnostico", label: "Diagnóstico", exact: false, icon: FileSearch },
  { href: "/dashboard/roadmap-beta", label: "Roadmap", exact: false, icon: Map },
  { href: "/dashboard/plan-anual", label: "Plan anual", exact: false, icon: CalendarCheck },
  { href: "/dashboard/consejo", label: "Tareas", exact: false, icon: Users },
  { href: "/dashboard/biblioteca", label: "Biblioteca", exact: false, icon: Library },
]

const INK = "#0E1626"
const PAPER = "#F2F2F0"
const ACCENT = "#FF5C1A"

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { reset } = useOnboardingStore()
  const [open, setOpen] = useState(false)

  // Logo de la empresa (arriba, editable).
  const [logo, setLogo] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getLogo().then(r => setLogo(r.logo)).catch(() => {})
  }, [])

  const onLogoFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ""
    if (!f) return
    setUploading(true)
    try {
      const r = await uploadLogo(f)
      setLogo(r.logo)
    } catch { /* noop */ } finally {
      setUploading(false)
    }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    reset()
    router.push("/")
  }

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  const ITEM = "flex items-center gap-3 px-4 py-2.5 text-[15px] font-medium transition-colors"

  function itemProps(active: boolean, notch: boolean): { className: string; style?: React.CSSProperties } {
    if (active && notch) return { className: `${ITEM} sb-active` }
    if (active) return { className: `${ITEM} rounded-2xl`, style: { background: PAPER, color: ACCENT } }
    return { className: `${ITEM} rounded-2xl text-white/55 hover:text-white hover:bg-white/[0.08]` }
  }

  const card = (notch: boolean) => (
    <div className="flex h-full flex-col py-5" style={{ background: INK }}>
      {/* Arriba: logo de la empresa — clic para cambiarlo */}
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        title="Cambiar el logo de tu empresa"
        className="group mx-3 mb-5 flex items-center gap-3 rounded-2xl p-2 text-left transition-colors hover:bg-white/[0.06]"
      >
        <span className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-white">
          {uploading
            ? <Loader2 className="h-4 w-4 animate-spin text-[#0E1626]" />
            : logo
              // eslint-disable-next-line @next/next/no-img-element -- data URL (base64), next/image no aplica
              ? <img src={logo} alt="Logo de tu empresa" className="h-full w-full object-contain" />
              : <ImagePlus className="h-[18px] w-[18px] text-[#0E1626]" />}
        </span>
        <span className="text-xs font-medium text-white/45 group-hover:text-white/70">
          {logo ? "Cambiar logo" : "Subir logo"}
        </span>
      </button>
      <input ref={fileRef} type="file" accept={LOGO_ACCEPT} className="hidden" onChange={onLogoFile} />

      {/* pr-0: la activa alcanza el borde para que el hueco conecte con el contenido */}
      <nav className="flex-1 space-y-1.5 pl-3 pr-0">
        {LINKS.map(l => {
          const Icon = l.icon
          const active = isActive(l.href, l.exact)
          return (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)} {...itemProps(active, notch)}>
              <Icon className="h-[19px] w-[19px] shrink-0" />
              {l.label}
            </Link>
          )
        })}
      </nav>

      {/* Abajo: logo de Gobernia, luego Mi perfil y Salir */}
      <div className="mt-2 space-y-1.5 border-t border-white/10 pl-3 pr-3 pt-4">
        <div className="px-1 pb-1 opacity-70">
          <GoberniaLogo variant="inverse" size={15} />
        </div>
        <Link
          href="/dashboard/datos"
          onClick={() => setOpen(false)}
          {...itemProps(isActive("/dashboard/datos", false), notch)}
        >
          <Settings className="h-[19px] w-[19px] shrink-0" /> Mi perfil
        </Link>
        <button onClick={signOut} className={`w-full ${itemProps(false, notch).className}`}>
          <LogOut className="h-[19px] w-[19px] shrink-0" /> Salir
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Móvil: botón hamburguesa */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-3 left-3 z-50 rounded-xl p-2 text-white"
        style={{ background: INK }}
        aria-label="Abrir menú"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Móvil: overlay (sin hueco) */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="relative h-dvh w-60">
            <button
              autoFocus
              onClick={() => setOpen(false)}
              className="absolute top-6 right-5 z-10 text-white/70 hover:text-white"
              aria-label="Cerrar menú"
            >
              <X className="h-5 w-5" />
            </button>
            {card(false)}
          </aside>
        </div>
      )}

      {/* Escritorio: riel pegado, angosto, con el hueco activo */}
      <aside className="hidden md:block fixed left-0 top-0 z-40 h-dvh w-56 overflow-visible">
        {card(true)}
      </aside>
    </>
  )
}
