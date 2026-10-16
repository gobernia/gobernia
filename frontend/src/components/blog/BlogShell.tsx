import Link from "next/link"
import type { ReactNode } from "react"
import { ArrowRight } from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"
import { B, SANS } from "./tokens"

// Marco del blog: mismo lenguaje bento de la landing (papel, navy, acento terracota).
export default function BlogShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: B.PAPER, color: B.INK }}>
      <header className="px-[var(--px-fluid)] sticky top-0 z-30 backdrop-blur-md" style={{ background: "rgba(242,242,240,.88)", borderBottom: `1px solid ${B.LINE}` }}>
        <div className="w-full max-w-[var(--container-fluid)] mx-auto h-16 flex items-center justify-between gap-4">
          <Link href="/" aria-label="Gobernia, ir al inicio"><GoberniaLogo size={24} /></Link>
          <nav className="flex items-center gap-1 text-sm font-medium" style={{ ...SANS, color: B.INK2 }}>
            <Link href="/" className="hidden sm:inline px-3 py-1.5 rounded-full transition-colors hover:text-[#152742]">Inicio</Link>
            <Link href="/blog" className="px-3 py-1.5 rounded-full transition-colors hover:text-[#152742]">Blog</Link>
            <Link href="/sign-in" className="hidden sm:inline px-3 py-1.5 rounded-full transition-colors hover:text-[#152742]">Iniciar sesión</Link>
            <Link href="/sign-up"
              className="ml-1 inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
              style={{ ...SANS, background: B.BNAVY }}>
              Empezar <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      <main>{children}</main>

      <footer className="px-[var(--px-fluid)] pt-14 pb-8 mt-20" style={{ background: B.SAND }}>
        <div className="w-full max-w-[var(--container-fluid)] mx-auto flex flex-col md:flex-row gap-8 md:items-end md:justify-between">
          <div className="space-y-4 max-w-md">
            <GoberniaLogo size={26} />
            <p className="text-[14px] leading-relaxed" style={{ color: B.INK2 }}>
              Gobernia es tu Consejo de Administración con Inteligencia Artificial: cinco consejeros
              analizan tu empresa, preparan cada sesión y dan seguimiento a cada acuerdo.
            </p>
          </div>
          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm" style={{ color: B.INK2 }}>
            <Link href="/" className="hover:text-[#152742]">Inicio</Link>
            <Link href="/blog" className="hover:text-[#152742]">Blog</Link>
            <Link href="/sign-up" className="hover:text-[#152742]">Crear cuenta</Link>
            <Link href="/legal/privacidad" className="hover:text-[#152742]">Privacidad</Link>
            <Link href="/legal/terminos" className="hover:text-[#152742]">Términos</Link>
          </nav>
        </div>
        <p className="w-full max-w-[var(--container-fluid)] mx-auto mt-10 text-xs" style={{ color: B.MUTED }}>
          © {new Date().getFullYear()} Gobernia. Todos los derechos reservados.
        </p>
      </footer>
    </div>
  )
}
