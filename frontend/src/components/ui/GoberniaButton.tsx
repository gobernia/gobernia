"use client"

import { forwardRef, ButtonHTMLAttributes } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface GoberniaButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost"
  loading?: boolean
  size?: "sm" | "md" | "lg"
  href?: string
}

const GoberniaButton = forwardRef<HTMLButtonElement, GoberniaButtonProps>(
  ({ className, variant = "primary", loading, size = "md", children, disabled, href, ...props }, ref) => {
    const base =
      "relative inline-flex items-center justify-center gap-2 font-semibold rounded-xl " +
      "transition-all duration-200 ease-out select-none outline-none " +
      "focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 " +
      "active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none"

    const sizes = {
      sm: "h-9 px-4 text-xs",
      md: "h-11 px-6 text-sm",
      lg: "h-12 px-7 text-sm",
    }

    const variants = {
      primary:
        "bg-black text-white hover:bg-gray-900",
      secondary:
        "bg-white text-black border-2 border-gray-200 " +
        "hover:border-gray-400 hover:bg-gray-50",
      ghost:
        "bg-transparent text-gray-500 " +
        "hover:bg-gray-100 hover:text-black",
    }

    const classes = cn(base, sizes[size], variants[variant], className)
    const content = (
      <>
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </>
    )

    if (href) {
      return (
        <Link href={href} className={classes}>
          {content}
        </Link>
      )
    }

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={classes}
        {...props}
      >
        {content}
      </button>
    )
  }
)

GoberniaButton.displayName = "GoberniaButton"
export default GoberniaButton
