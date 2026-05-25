import { cn } from "@/lib/utils"

type Variant = "default" | "inverse" | "ink" | "line"

interface Props {
  variant?: Variant
  size?: number  // tamaño base en px (font-size del wordmark)
  className?: string
}

/**
 * Logo oficial GOBERNIA — wordmark GOBERN + cápsula IA.
 * Construido según el Manual de Identidad v1.0.
 *
 * Variantes:
 *  - default → navy + cápsula charcoal (sobre fondos claros)
 *  - inverse → bone + cápsula bone-outline (sobre fondos oscuros)
 *  - ink     → todo ink (monocromo)
 *  - line    → contornos sin relleno
 */
export default function GoberniaLogo({
  variant = "default",
  size = 24,
  className = "",
}: Props) {
  const styles: Record<Variant, { word: string; chip: string }> = {
    default: {
      word: "text-[var(--gob-navy)]",
      chip: "bg-[var(--gob-charcoal)] text-[var(--gob-bone)]",
    },
    inverse: {
      word: "text-[var(--gob-bone)]",
      chip: "bg-[var(--gob-ink)] text-[var(--gob-bone)] ring-1 ring-[var(--gob-bone)]/15",
    },
    ink: {
      word: "text-[var(--gob-ink)]",
      chip: "bg-[var(--gob-ink)] text-[var(--gob-bone)]",
    },
    line: {
      word: "text-transparent",
      chip: "bg-transparent text-transparent ring-1 ring-[var(--gob-charcoal)]",
    },
  }

  const s = styles[variant]

  return (
    <span
      className={cn(
        "inline-flex items-baseline leading-none tracking-tight select-none",
        className
      )}
      style={{
        fontSize: `${size}px`,
        fontFamily: "var(--font-sans)",
        gap: "0.12em",
        letterSpacing: "-0.01em",
      }}
      aria-label="GOBERNIA"
    >
      <span
        className={cn("font-medium", s.word)}
        style={
          variant === "line"
            ? { WebkitTextStroke: "1px #142849", letterSpacing: "-0.015em" }
            : { letterSpacing: "-0.015em" }
        }
      >
        GOBERN
      </span>
      <span
        className={cn("inline-block font-normal", s.chip)}
        style={{
          borderRadius: "0.18em",
          padding: "0.22em 0.26em 0.06em",
          letterSpacing: "0.01em",
          lineHeight: 1,
          ...(variant === "line" ? { WebkitTextStroke: "1px #26282E" } : {}),
        }}
      >
        IA
      </span>
    </span>
  )
}

/**
 * Variante icónica — solo la cápsula con la "G" del wordmark,
 * para favicons o tamaños muy reducidos.
 */
export function GoberniaIcon({
  size = 24,
  className = "",
  variant = "default",
}: { size?: number; className?: string; variant?: "default" | "inverse" }) {
  const bg = variant === "inverse" ? "var(--gob-bone)" : "var(--gob-ink)"
  const fg = variant === "inverse" ? "var(--gob-ink)" : "var(--gob-bone)"
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center font-bold leading-none tracking-tight",
        className
      )}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.6,
        borderRadius: size * 0.22,
        background: bg,
        color: fg,
        letterSpacing: "-0.03em",
        fontFamily: "var(--font-sans)",
      }}
      aria-label="GOBERNIA"
    >
      G
    </span>
  )
}
