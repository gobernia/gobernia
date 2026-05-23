"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

// Paleta light — flippeada del original oscuro
const C = {
  bg:      "#FFFFFF",      // antes #0A0A0A
  text:    "#0B0E14",      // ink — antes #FFFFFF
  muted:   "#6C6A66",      // antes #888888
  subtle:  "#8E8B84",      // antes #555555
  rule:    "#D9D4CB",      // antes #1A1A1A
  navy:    "#142849",      // acento marca
  bone:    "#F4F1EC",
} as const

// ── Hook de scroll reveal (adaptado del original) ───────────────────────────
function useScrollReveal<T extends HTMLElement>(opts?: {
  y?: number; duration?: number; delay?: number; stagger?: number;
  start?: string; childSelector?: string;
}) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { y = 40, duration = 0.8, delay = 0, stagger = 0.1, start = "top 80%", childSelector } = opts || {}
    const targets = childSelector ? el.querySelectorAll(childSelector) : el
    gsap.set(targets, { opacity: 0, y })
    const anim = gsap.to(targets, {
      opacity: 1, y: 0, duration, delay,
      stagger: childSelector ? stagger : 0,
      ease: "power3.out",
      scrollTrigger: { trigger: el, start, toggleActions: "play none none none" },
    })
    return () => {
      anim.kill()
      ScrollTrigger.getAll().forEach(t => { if (t.trigger === el) t.kill() })
    }
  }, [opts])
  return ref
}

function useTextReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const lines = el.querySelectorAll(".reveal-line")
    if (lines.length === 0) {
      gsap.set(el, { opacity: 0, y: 40 })
      const anim = gsap.to(el, {
        opacity: 1, y: 0, duration: 0.8, ease: "power3.out",
        scrollTrigger: { trigger: el, start: "top 80%", toggleActions: "play none none none" },
      })
      return () => { anim.kill() }
    }
    gsap.set(lines, { opacity: 0, y: 40, clipPath: "polygon(0 0, 100% 0, 100% 0, 0 0)" })
    const anim = gsap.to(lines, {
      opacity: 1, y: 0, clipPath: "polygon(0 0, 100% 0, 100% 100%, 0 100%)",
      duration: 0.8, stagger: 0.15, ease: "power3.out",
      scrollTrigger: { trigger: el, start: "top 80%", toggleActions: "play none none none" },
    })
    return () => { anim.kill() }
  }, [])
  return ref
}

// ── Wave lines de fondo (sin partículas que siguen el cursor) ───────────────
function WaveLines() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const offsetRef = useRef(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener("resize", resize)

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      offsetRef.current += 0.003

      const waveCount = 6
      for (let w = 0; w < waveCount; w++) {
        ctx.beginPath()
        // Líneas en navy con muy baja opacidad — visibles sobre blanco pero sutiles
        ctx.strokeStyle = `rgba(20, 40, 73, ${0.06 + w * 0.015})`
        ctx.lineWidth = 1

        const baseY = canvas.height * (0.3 + w * 0.08)
        const amplitude = 30 + w * 10
        const frequency = 0.003 + w * 0.0005
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
      window.removeEventListener("resize", resize)
      document.removeEventListener("visibilitychange", onVis)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", zIndex: 0, pointerEvents: "none" }}
    />
  )
}

// ── Navbar ───────────────────────────────────────────────────────────────────
function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const navRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 50)
    window.addEventListener("scroll", h, { passive: true })
    return () => window.removeEventListener("scroll", h)
  }, [])

  useEffect(() => {
    gsap.fromTo(navRef.current, { y: -20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, delay: 0.2, ease: "power3.out" })
  }, [])

  const onClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith("#") && href.length > 1) {
      e.preventDefault()
      const el = document.querySelector(href)
      if (el) el.scrollIntoView({ behavior: "smooth" })
    }
  }

  const links = [
    { label: "Producto",      href: "#equipo" },
    { label: "Cómo funciona", href: "#proceso" },
    { label: "FAQ",           href: "#faq" },
  ]

  return (
    <nav
      ref={navRef}
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        backgroundColor: scrolled ? "rgba(255,255,255,0.9)" : "transparent",
        backdropFilter:  scrolled ? "blur(10px)" : "none",
        borderBottom:    scrolled ? `1px solid ${C.rule}` : "1px solid transparent",
      }}
    >
      <div className="flex items-center justify-between mx-auto" style={{ height: 80, padding: "0 80px", maxWidth: 1400 }}>
        <GoberniaLogo size={18} />

        <div className="flex items-center" style={{ gap: 40 }}>
          {links.map(l => (
            <a
              key={l.label}
              href={l.href}
              onClick={e => onClick(e, l.href)}
              className="no-underline transition-colors duration-300"
              style={{ fontSize: 14, color: C.muted }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = C.text }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = C.muted }}
            >
              {l.label}
            </a>
          ))}
          <Link
            href="/sign-in"
            className="no-underline transition-colors duration-300"
            style={{ fontSize: 14, color: C.muted }}
          >
            Iniciar sesión
          </Link>
        </div>

        <Link
          href="/sign-up"
          className="no-underline transition-all duration-300"
          style={{ fontSize: 14, color: C.bone, backgroundColor: C.navy, padding: "10px 24px" }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.text }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.navy }}
        >
          Empezar
        </Link>
      </div>
    </nav>
  )
}

// ── Hero ────────────────────────────────────────────────────────────────────
function Hero() {
  const labelRef = useRef<HTMLParagraphElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const subRef = useRef<HTMLParagraphElement>(null)
  const ctaRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const tl = gsap.timeline({ delay: 0.3 })
    tl.to(labelRef.current, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" })
    const lines = headingRef.current?.querySelectorAll(".reveal-line")
    if (lines && lines.length > 0) {
      gsap.set(lines, { opacity: 0, y: 50, clipPath: "polygon(0 0, 100% 0, 100% 0, 0 0)" })
      tl.to(lines, { opacity: 1, y: 0, clipPath: "polygon(0 0, 100% 0, 100% 100%, 0 100%)", duration: 0.8, stagger: 0.15, ease: "power3.out" }, "-=0.3")
    }
    tl.to(subRef.current,    { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3")
    tl.to(ctaRef.current,    { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, "-=0.3")
    tl.to(scrollRef.current, { opacity: 1, duration: 0.6, ease: "power3.out" }, "-=0.2")
    return () => { tl.kill() }
  }, [])

  return (
    <section
      className="relative"
      style={{ minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", padding: "160px 80px 80px", zIndex: 10 }}
    >
      <div style={{ maxWidth: 1400, margin: "0 auto", width: "100%" }}>
        <p
          ref={labelRef}
          className="opacity-0"
          style={{ fontSize: 12, color: C.muted, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 24, transform: "translateY(20px)" }}
        >
          Gobierno corporativo · Inteligencia de agentes
        </p>

        <h1
          ref={headingRef}
          style={{ fontSize: "clamp(40px, 5.5vw, 72px)", fontWeight: 300, color: C.text, lineHeight: 1.1, letterSpacing: "-0.03em", maxWidth: 900, margin: 0 }}
        >
          <span className="reveal-line block">Tu junta de consejo,</span>
          <span className="reveal-line block" style={{ color: C.navy }}>con inteligencia de agentes.</span>
        </h1>

        <p
          ref={subRef}
          className="opacity-0"
          style={{ fontSize: 16, color: C.muted, lineHeight: 1.6, maxWidth: 540, marginTop: 32, transform: "translateY(30px)" }}
        >
          Cuatro agentes de IA — CFO, CSO, CRO y Auditor — analizan tu empresa cada mes, detectan riesgos y proponen estrategias. Sin consultores. Sin esperas.
        </p>

        <div
          ref={ctaRef}
          className="opacity-0"
          style={{ display: "flex", gap: 16, marginTop: 40, flexWrap: "wrap", transform: "translateY(30px)" }}
        >
          <Link
            href="/sign-up"
            className="no-underline transition-all duration-300"
            style={{ fontSize: 14, fontWeight: 500, color: C.bone, backgroundColor: C.navy, padding: "14px 32px" }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.text }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.navy }}
          >
            Comenzar gratis
          </Link>
          <Link
            href="/sign-in"
            className="no-underline transition-all duration-300"
            style={{ fontSize: 14, fontWeight: 400, color: C.text, backgroundColor: "transparent", padding: "14px 32px", border: `1px solid ${C.subtle}` }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = C.navy }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = C.subtle }}
          >
            Ya tengo cuenta
          </Link>
        </div>

        <p style={{ fontSize: 12, color: C.subtle, marginTop: 16 }}>
          Sin tarjeta de crédito · Configuración en menos de 15 minutos
        </p>
      </div>

      <span
        ref={scrollRef}
        className="opacity-0"
        style={{ position: "absolute", right: 80, bottom: 80, fontSize: 12, color: C.subtle, animation: "ld2-pulse 2s infinite" }}
      >
        scroll down
      </span>

      <div style={{ position: "absolute", bottom: 60, left: 80, right: 80, height: 1, backgroundColor: C.rule }} />

      <style>{`
        @keyframes ld2-pulse {
          0%, 100% { opacity: 0.5; }
          50%      { opacity: 1; }
        }
      `}</style>
    </section>
  )
}

// ── Stats ───────────────────────────────────────────────────────────────────
function Stats() {
  const ref = useScrollReveal<HTMLDivElement>({ childSelector: ".stat-item", stagger: 0.1, y: 30 })
  const stats = [
    { n: "4",    l: "Agentes especializados" },
    { n: "8",    l: "Etapas de diagnóstico" },
    { n: "100%", l: "Cifrado y confidencial" },
    { n: "15'",  l: "Para tu primer análisis" },
  ]
  return (
    <section style={{ borderTop: `1px solid ${C.rule}`, padding: "60px 80px", position: "relative", zIndex: 10 }}>
      <div ref={ref} style={{ maxWidth: 1400, margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 32 }}>
        {stats.map(s => (
          <div key={s.l} className="stat-item">
            <div style={{ fontSize: 64, fontWeight: 200, color: C.navy, lineHeight: 1, letterSpacing: "-0.03em" }}>{s.n}</div>
            <div style={{ fontSize: 12, color: C.muted, textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 8 }}>{s.l}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Equipo ──────────────────────────────────────────────────────────────────
function Equipo() {
  const headerRef = useScrollReveal<HTMLDivElement>()
  const gridRef = useScrollReveal<HTMLDivElement>({ childSelector: ".agent-card", stagger: 0.15, y: 40 })
  const agents = [
    { role: "CFO",     name: "Finanzas",   d: "Rentabilidad, flujo de caja y estructura de capital. Detecta fugas y oportunidades antes de que el mes cierre." },
    { role: "CSO",     name: "Estrategia", d: "Posicionamiento, mercado y crecimiento. Propone iniciativas alineadas a tu visión de largo plazo." },
    { role: "CRO",     name: "Riesgos",    d: "Riesgos operativos, legales y de mercado. Planes de mitigación antes de que escalen." },
    { role: "Auditor", name: "Gobierno",   d: "Cumplimiento y control interno. Mide tu Governance Score y cierra brechas críticas." },
  ]
  return (
    <section id="equipo" style={{ borderTop: `1px solid ${C.rule}`, padding: "120px 80px", position: "relative", zIndex: 10 }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div ref={headerRef} style={{ marginBottom: 80 }}>
          <h2 style={{ fontSize: "clamp(32px, 3.5vw, 48px)", fontWeight: 300, color: C.text, lineHeight: 1.15, letterSpacing: "-0.02em", margin: 0 }}>
            El equipo
          </h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 16, lineHeight: 1.6 }}>
            Cuatro expertos de IA en tu mesa directiva.
          </p>
        </div>

        <div ref={gridRef} style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 32 }}>
          {agents.map(a => (
            <div key={a.role} className="agent-card">
              <span style={{ fontSize: 12, color: C.subtle, textTransform: "uppercase", letterSpacing: "0.05em" }}>{a.role}</span>
              <h3 style={{ fontSize: 24, fontWeight: 400, color: C.text, marginTop: 12, marginBottom: 0, letterSpacing: "-0.01em" }}>{a.name}</h3>
              <div style={{ width: "100%", height: 1, backgroundColor: C.rule, margin: "20px 0" }} />
              <p style={{ fontSize: 14, color: C.muted, lineHeight: 1.6, margin: 0 }}>{a.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Proceso ─────────────────────────────────────────────────────────────────
function Proceso() {
  const headerRef = useScrollReveal<HTMLDivElement>()
  const listRef = useScrollReveal<HTMLDivElement>({ childSelector: ".step-item", stagger: 0.2, y: 40 })
  const steps = [
    { n: "01", t: "Configura tu empresa", d: "8 pasos conversacionales. Industria, equipo, prioridades, KPIs y expectativas. Menos de 15 minutos." },
    { n: "02", t: "Tu consejo se activa", d: "Los cuatro agentes leen tu perfil y generan el primer diagnóstico completo: MEFI, MEFE y SWOT." },
    { n: "03", t: "Sesiones cada mes",    d: "Análisis actualizado cada periodo. Chatea con cualquier agente sobre cualquier decisión en tiempo real." },
  ]
  return (
    <section id="proceso" style={{ borderTop: `1px solid ${C.rule}`, padding: "120px 80px", position: "relative", zIndex: 10 }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div ref={headerRef} style={{ marginBottom: 80 }}>
          <h2 style={{ fontSize: "clamp(32px, 3.5vw, 48px)", fontWeight: 300, color: C.text, lineHeight: 1.15, letterSpacing: "-0.02em", margin: 0 }}>
            El proceso
          </h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 16, lineHeight: 1.6 }}>
            De cero a tu primer diagnóstico en tres pasos.
          </p>
        </div>

        <div ref={listRef}>
          {steps.map((s, i) => (
            <div
              key={s.n}
              className="step-item"
              style={{
                display: "grid", gridTemplateColumns: "120px 1fr", gap: 40,
                padding: "60px 0",
                borderTop: i === 0 ? `1px solid ${C.rule}` : "none",
                borderBottom: `1px solid ${C.rule}`,
                alignItems: "start",
              }}
            >
              <span style={{ fontSize: "clamp(48px, 5vw, 72px)", fontWeight: 200, color: C.rule, lineHeight: 1 }}>{s.n}</span>
              <div>
                <h3 style={{ fontSize: 24, fontWeight: 400, color: C.text, margin: 0, letterSpacing: "-0.01em" }}>{s.t}</h3>
                <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.6, maxWidth: 480, marginTop: 16, marginBottom: 0 }}>{s.d}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Para quién ──────────────────────────────────────────────────────────────
function ParaQuien() {
  const headerRef = useScrollReveal<HTMLDivElement>()
  const gridRef = useScrollReveal<HTMLDivElement>({ childSelector: ".target-card", stagger: 0.15, y: 40 })
  const targets = [
    { t: "Empresas familiares",    d: "Módulos de protocolo, análisis de concentración y planificación de sucesión activados automáticamente." },
    { t: "PyMEs en crecimiento",   d: "Benchmarks por industria y tamaño. Identifica en qué punto del camino estás y qué necesitas para el siguiente." },
    { t: "Directivos sin consejo", d: "Si aún no tienes consejo de administración, Gobernia es el punto de partida para estructurar tu gobierno." },
  ]
  return (
    <section style={{ borderTop: `1px solid ${C.rule}`, padding: "120px 80px", position: "relative", zIndex: 10 }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div ref={headerRef} style={{ marginBottom: 80 }}>
          <h2 style={{ fontSize: "clamp(32px, 3.5vw, 48px)", fontWeight: 300, color: C.text, lineHeight: 1.15, letterSpacing: "-0.02em", margin: 0 }}>
            Para quién
          </h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 16, lineHeight: 1.6 }}>
            Diseñado para empresas reales.
          </p>
        </div>

        <div ref={gridRef} style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 32 }}>
          {targets.map(t => (
            <div key={t.t} className="target-card">
              <h3 style={{ fontSize: 24, fontWeight: 400, color: C.text, margin: 0, letterSpacing: "-0.01em" }}>{t.t}</h3>
              <div style={{ width: "100%", height: 1, backgroundColor: C.rule, margin: "20px 0" }} />
              <p style={{ fontSize: 14, color: C.muted, lineHeight: 1.6, margin: 0 }}>{t.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── FAQ ─────────────────────────────────────────────────────────────────────
function FAQSection() {
  const [open, setOpen] = useState<number | null>(null)
  const headerRef = useScrollReveal<HTMLDivElement>()
  const listRef = useScrollReveal<HTMLDivElement>({ childSelector: ".faq-item", stagger: 0.1, y: 20 })
  const faqs = [
    { q: "¿Gobernia reemplaza a mi consejo de administración?", a: "No. Gobernia complementa y potencia tu consejo existente, o lo sustituye provisionalmente mientras lo conformas. Nuestros agentes actúan como asesores virtuales, no como miembros legales de tu junta." },
    { q: "¿Qué tan segura está mi información?",                a: "Toda tu información está cifrada end-to-end. No compartimos datos con terceros y cumplimos con GDPR y las regulaciones locales de protección de datos." },
    { q: "¿Necesito experiencia en gobierno corporativo?",      a: "No. La plataforma está diseñada para guiarte paso a paso. Los agentes explican cada concepto en lenguaje claro y te ayudan a tomar decisiones informadas." },
    { q: "¿Funciona para empresas familiares?",                 a: "Sí. Contamos con módulos específicos para empresas familiares: protocolos, análisis de concentración de riesgo y planificación de sucesión." },
    { q: "¿Con qué frecuencia se actualiza el análisis?",       a: "Los agentes generan un diagnóstico completo cada mes. Además, puedes consultar a cualquier agente en tiempo real cuando lo necesites." },
    { q: "¿Cuánto tiempo toma ver los primeros resultados?",    a: "Menos de 15 minutos después de completar la configuración inicial. Tu primer diagnóstico estará listo inmediatamente." },
  ]
  return (
    <section id="faq" style={{ borderTop: `1px solid ${C.rule}`, padding: "120px 80px", position: "relative", zIndex: 10 }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div ref={headerRef} style={{ marginBottom: 60 }}>
          <h2 style={{ fontSize: "clamp(32px, 3.5vw, 48px)", fontWeight: 300, color: C.text, lineHeight: 1.15, letterSpacing: "-0.02em", margin: 0 }}>
            FAQ
          </h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 16, lineHeight: 1.6 }}>
            Preguntas frecuentes.
          </p>
        </div>

        <div ref={listRef}>
          {faqs.map((f, i) => {
            const isOpen = open === i
            return (
              <div key={i} className="faq-item" style={{ borderBottom: `1px solid ${C.rule}` }}>
                <button
                  onClick={() => setOpen(isOpen ? null : i)}
                  style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "24px 0", background: "none", border: "none", cursor: "pointer", textAlign: "left" }}
                >
                  <span style={{ fontSize: 16, color: C.text, fontWeight: 400, flex: 1, paddingRight: 24 }}>{f.q}</span>
                  <span style={{ fontSize: 20, color: C.muted, flexShrink: 0, width: 24, textAlign: "center" }}>{isOpen ? "−" : "+"}</span>
                </button>
                <div style={{ maxHeight: isOpen ? 200 : 0, overflow: "hidden", opacity: isOpen ? 1 : 0, transition: "max-height 0.3s ease, opacity 0.3s ease" }}>
                  <p style={{ fontSize: 14, color: C.muted, lineHeight: 1.6, maxWidth: 600, paddingBottom: 24, margin: 0 }}>{f.a}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

// ── CTA ─────────────────────────────────────────────────────────────────────
function CTASection() {
  const headingRef = useTextReveal<HTMLHeadingElement>()
  return (
    <section style={{ borderTop: `1px solid ${C.rule}`, padding: "160px 80px", position: "relative", zIndex: 10 }}>
      <div style={{ maxWidth: 700, margin: "0 auto", textAlign: "center" }}>
        <h2
          ref={headingRef}
          style={{ fontSize: "clamp(32px, 3.5vw, 48px)", fontWeight: 300, color: C.text, lineHeight: 1.2, letterSpacing: "-0.02em", margin: 0 }}
        >
          <span className="reveal-line block">Tu empresa merece un consejo</span>
          <span className="reveal-line block" style={{ color: C.navy }}>que nunca duerme.</span>
        </h2>
        <p style={{ fontSize: 16, color: C.muted, marginTop: 24, lineHeight: 1.6 }}>
          Sin consultores. Sin contratos. Primer diagnóstico en menos de 15 minutos.
        </p>
        <Link
          href="/sign-up"
          className="no-underline transition-all duration-300 inline-block"
          style={{ fontSize: 14, fontWeight: 500, color: C.bone, backgroundColor: C.navy, padding: "16px 40px", marginTop: 40 }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.text }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.navy }}
        >
          Comenzar gratis
        </Link>
      </div>
    </section>
  )
}

// ── Footer ──────────────────────────────────────────────────────────────────
function FooterSection() {
  return (
    <footer style={{ backgroundColor: C.bg, borderTop: `1px solid ${C.rule}` }}>
      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "80px 80px 40px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 32 }}>
          <div>
            <div style={{ marginBottom: 16 }}><GoberniaLogo size={18} /></div>
            <p style={{ fontSize: 14, color: C.subtle }}>GOBERNIA © 2026</p>
          </div>
          {[
            { h: "Producto", links: ["El equipo", "El proceso", "Para quién", "FAQ"] },
            { h: "Cuenta",   links: ["Iniciar sesión", "Registro"] },
            { h: "Legal",    links: ["Privacidad", "Términos"] },
          ].map(col => (
            <div key={col.h}>
              <h4 style={{ fontSize: 14, fontWeight: 500, color: C.text, marginBottom: 20 }}>{col.h}</h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {col.links.map(l => (
                  <a
                    key={l}
                    href="#"
                    className="no-underline transition-colors duration-300"
                    style={{ fontSize: 14, color: C.muted }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = C.text }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = C.muted }}
                  >
                    {l}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div style={{ borderTop: `1px solid ${C.rule}`, marginTop: 60, paddingTop: 24 }}>
          <p style={{ fontSize: 12, color: C.subtle }}>Tu información está cifrada y protegida.</p>
        </div>
      </div>
    </footer>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────
export default function LandingTwo() {
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger)
    const t = setTimeout(() => ScrollTrigger.refresh(), 100)
    return () => clearTimeout(t)
  }, [])

  return (
    <div style={{ backgroundColor: C.bg, minHeight: "100vh", color: C.text, fontFamily: "var(--font-sans)" }}>
      <WaveLines />
      <Nav />
      <main>
        <Hero />
        <Stats />
        <Equipo />
        <Proceso />
        <ParaQuien />
        <FAQSection />
        <CTASection />
      </main>
      <FooterSection />
    </div>
  )
}
