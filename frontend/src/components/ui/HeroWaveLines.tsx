"use client"

import { useEffect, useRef } from "react"

/**
 * Líneas de onda animadas de fondo. Diseñado para vivir DENTRO de una sección
 * (no fixed al viewport). El parent debe tener position: relative y overflow: hidden.
 * Las líneas se dibujan en navy con alpha bajo — sutiles sobre fondos claros.
 */
export default function HeroWaveLines({
  className = "",
  color = "20, 40, 73",  // navy en RGB para usar con alpha dinámico
}: { className?: string; color?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const offsetRef = useRef(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const parent = canvas.parentElement
    const resize = () => {
      const w = parent?.offsetWidth ?? window.innerWidth
      const h = parent?.offsetHeight ?? window.innerHeight
      canvas.width = w
      canvas.height = h
    }
    resize()
    const ro = new ResizeObserver(resize)
    if (parent) ro.observe(parent)
    window.addEventListener("resize", resize)

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      offsetRef.current += 0.003

      const waveCount = 7
      for (let w = 0; w < waveCount; w++) {
        ctx.beginPath()
        ctx.strokeStyle = `rgba(${color}, ${0.10 + w * 0.025})`
        ctx.lineWidth = 1

        // Concentradas en la parte SUPERIOR del hero (esquina top-left)
        const baseY = canvas.height * (0.05 + w * 0.05)
        const amplitude = 40 + w * 14
        const frequency = 0.002 + w * 0.0006
        const phase = offsetRef.current + w * 0.5

        for (let x = 0; x <= canvas.width; x += 2) {
          const y = baseY
            + Math.sin(x * frequency + phase) * amplitude
            + Math.sin(x * frequency * 0.5 + phase * 1.3) * (amplitude * 0.5)
          if (x === 0) ctx.moveTo(x, y)
          else          ctx.lineTo(x, y)
        }
        ctx.stroke()
      }
      rafRef.current = requestAnimationFrame(animate)
    }
    animate()

    const onVis = () => {
      if (document.hidden) cancelAnimationFrame(rafRef.current)
      else animate()
    }
    document.addEventListener("visibilitychange", onVis)

    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
      window.removeEventListener("resize", resize)
      document.removeEventListener("visibilitychange", onVis)
    }
  }, [color])

  // Gradient mask: sólidas en la esquina SUPERIOR-DERECHA, fade out hacia el resto.
  // Las líneas ocupan el top-right (como una serigrafía) y se evaporan
  // antes de chocar con el cuerpo del texto (que está a la izquierda).
  const fadeMask =
    "linear-gradient(to bottom left, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 20%, rgba(0,0,0,0) 70%)"

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className}
      style={{
        position: "absolute", inset: 0, width: "100%", height: "100%",
        pointerEvents: "none", zIndex: 0,
        maskImage: fadeMask,
        WebkitMaskImage: fadeMask,
      }}
    />
  )
}
