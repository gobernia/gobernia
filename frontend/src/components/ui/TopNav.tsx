"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const LINKS = [
  { href: "/dashboard", label: "Inicio", exact: true },
  { href: "/dashboard/sesion-del-mes", label: "Sesión del mes", exact: false },
  { href: "/dashboard/plan", label: "Plan", exact: false },
  { href: "/dashboard/compromisos", label: "Compromisos", exact: false },
]

export default function TopNav() {
  const pathname = usePathname()
  return (
    <nav className="sticky top-0 z-40 bg-[var(--gob-navy)] text-[var(--gob-bone)]">
      <div className="max-w-6xl mx-auto px-4 flex items-center gap-1 overflow-x-auto">
        <Link href="/dashboard" className="font-bold tracking-widest text-sm py-3 pr-4 shrink-0">
          GOBERNIA
        </Link>
        {LINKS.map(l => {
          const active = l.exact ? pathname === l.href : pathname.startsWith(l.href)
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`text-sm py-3 px-3 shrink-0 border-b-2 transition-colors ${
                active
                  ? "border-[var(--gob-bone)] font-medium"
                  : "border-transparent opacity-70 hover:opacity-100"
              }`}
            >
              {l.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
