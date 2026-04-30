import { ReactNode } from "react"

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-white flex flex-col items-center justify-center px-4 font-sans antialiased">
      <div className="mb-10 flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-black flex items-center justify-center">
          <span className="text-white text-xs font-black tracking-tight">G</span>
        </div>
        <span className="text-base font-semibold text-black tracking-tight">Gobernia</span>
      </div>
      {children}
    </div>
  )
}
