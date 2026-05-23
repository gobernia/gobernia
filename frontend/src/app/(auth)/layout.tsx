import { ReactNode } from "react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-[var(--gob-paper)] flex flex-col items-center justify-center px-4 font-sans antialiased">
      <div className="mb-10">
        <GoberniaLogo size={22} />
      </div>
      {children}
    </div>
  )
}
