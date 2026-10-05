import type { Metadata } from "next"

// Enlaces privados por token: nunca deben indexarse.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
