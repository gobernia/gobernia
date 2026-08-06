import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

// Shell compartido de las páginas legales — lenguaje bento de la landing:
// fondo PAPER, Inter en todo (se fuerza sans sobre la serif global de h1/h2),
// títulos en BNAVY y cuerpo en INK2.
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: "#F2F2F0", color: "#0E1626" }}>
      <header className="px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto h-16 flex items-center justify-between">
          <Link href="/" aria-label="Ir al inicio"><GoberniaLogo size={22} /></Link>
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-semibold transition-colors hover:text-[#152742]"
            style={{ color: "#6E7686" }}
          >
            <ArrowLeft className="h-4 w-4" /> Volver al inicio
          </Link>
        </div>
      </header>

      <main className="px-[var(--px-fluid)] py-12 sm:py-16">
        <article
          className="w-full max-w-3xl mx-auto text-[15px] leading-relaxed
            [&_h1]:font-sans [&_h1]:text-[clamp(30px,4vw,44px)] [&_h1]:font-bold [&_h1]:leading-[1.08] [&_h1]:tracking-[-0.03em] [&_h1]:text-[#152742]
            [&_h2]:font-sans [&_h2]:mt-10 [&_h2]:mb-3 [&_h2]:text-[19px] [&_h2]:font-bold [&_h2]:tracking-[-0.02em] [&_h2]:text-[#152742]
            [&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5
            [&_strong]:font-semibold [&_strong]:text-[#0E1626]
            [&_a]:font-medium [&_a]:text-[#152742] [&_a]:underline"
          style={{ color: "#39435A" }}
        >
          {children}
        </article>
      </main>

      <footer className="px-[var(--px-fluid)] pb-10">
        <div className="w-full max-w-3xl mx-auto pt-6 text-xs" style={{ borderTop: "1px solid #E2E2DC", color: "#6E7686" }}>
          © {new Date().getFullYear()} Gobernia. Todos los derechos reservados.
        </div>
      </footer>
    </div>
  )
}
