import type { CSSProperties } from "react"

// Paleta bento de Gobernia (la misma de la landing y el dashboard).
export const B = {
  PAPER: "#F2F2F0",
  INK: "#0E1626",
  INK2: "#39435A",
  MUTED: "#6E7686",
  CARD: "#FFFFFF",
  SAND: "#E8E3D8",
  BNAVY: "#152742",
  ACCENT: "#C2410C",
  LINE: "#E2E2DC",
} as const

// El CSS global pone h1/h2 en serif; el bento usa sans en los títulos.
export const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }
