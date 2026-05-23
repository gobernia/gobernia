"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import GoberniaLogo, { GoberniaIcon } from "@/components/ui/GoberniaLogo"
import HeroWaveLines from "@/components/ui/HeroWaveLines"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Fade-up on scroll ─────────────────────────────────────
function FadeUp({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 36 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.75, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

// ── Hero stagger ──────────────────────────────────────────
const heroContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.13, delayChildren: 0.05 } },
}
const heroItem = {
  hidden: { opacity: 0, y: 40 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.8, ease: EASE } },
}

// ── Data ──────────────────────────────────────────────────
const AGENTS = [
  { id: "CFO",     role: "Finanzas",   desc: "Rentabilidad, flujo de caja y estructura de capital. Detecta fugas y oportunidades antes de que el mes cierre." },
  { id: "CSO",     role: "Estrategia", desc: "Posicionamiento, mercado y crecimiento. Propone iniciativas alineadas a tu visión de largo plazo." },
  { id: "CRO",     role: "Riesgos",    desc: "Riesgos operativos, legales y de mercado. Planes de mitigación antes de que escalen." },
  { id: "Auditor", role: "Gobierno",   desc: "Cumplimiento y control interno. Mide tu Governance Score y cierra brechas críticas." },
]

const STEPS = [
  { n: "01", title: "Configura tu empresa",  desc: "8 pasos conversacionales. Industria, equipo, prioridades, KPIs y expectativas. Menos de 15 minutos." },
  { n: "02", title: "Tu consejo se activa",  desc: "Los cuatro agentes leen tu perfil y generan el primer diagnóstico completo: MEFI, MEFE y SWOT." },
  { n: "03", title: "Sesiones cada mes",     desc: "Análisis actualizado cada periodo. Chatea con cualquier agente sobre cualquier decisión en tiempo real." },
]

const FOR_WHO = [
  { title: "Empresas familiares",    desc: "Módulos de protocolo, análisis de concentración y planificación de sucesión activados automáticamente." },
  { title: "PyMEs en crecimiento",   desc: "Benchmarks por industria y tamaño. Identifica en qué punto del camino estás y qué necesitas para el siguiente." },
  { title: "Directivos sin consejo", desc: "Si aún no tienes consejo de administración, Gobernia es el punto de partida para estructurar tu gobierno." },
]

const FAQS = [
  { q: "¿Gobernia reemplaza a mi consejo de administración?",  a: "No. Es un copiloto que complementa o prepara el camino hacia un consejo humano. Te da el rigor analítico que normalmente solo tienen las grandes corporaciones, mientras decides cuándo incorporar consejeros externos." },
  { q: "¿Qué tan segura está mi información?",                 a: "Toda la información está cifrada en tránsito y en reposo. Infraestructura en AWS vía Supabase. Tus datos nunca se usan para entrenar modelos ni se comparten con terceros." },
  { q: "¿Necesito experiencia en gobierno corporativo?",       a: "Para nada. Gobernia está diseñado para directivos y dueños que quieren profesionalizar su toma de decisiones sin ser expertos. El onboarding es conversacional y guiado." },
  { q: "¿Funciona para empresas familiares?",                  a: "Especialmente para ellas. Activa módulos de protocolo familiar, análisis de concentración de decisiones y planificación de sucesión cuando detecta que la empresa es familiar." },
  { q: "¿Con qué frecuencia se actualiza el análisis?",        a: "Tú controlas la frecuencia: mensual, bimestral, trimestral o semestral. Además puedes chatear con los agentes en cualquier momento entre sesiones." },
  { q: "¿Cuánto tiempo toma ver los primeros resultados?",     a: "El primer diagnóstico completo está disponible al terminar el onboarding. Entre 10 y 20 minutos desde que entras por primera vez." },
]

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: "1px solid var(--gob-rule)" }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "24px 0",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span
          style={{
            fontSize: 16,
            color: "var(--gob-ink)",
            fontWeight: 400,
            flex: 1,
            paddingRight: 24,
          }}
        >
          {q}
        </span>
        <span
          style={{
            fontSize: 20,
            color: "var(--gob-muted)",
            flexShrink: 0,
            width: 24,
            textAlign: "center",
          }}
        >
          {open ? "−" : "+"}
        </span>
      </button>
      <div
        style={{
          maxHeight: open ? 400 : 0,
          overflow: "hidden",
          opacity: open ? 1 : 0,
          transition: "max-height 0.32s ease, opacity 0.32s ease",
        }}
      >
        <p
          style={{
            fontSize: 14,
            color: "var(--gob-muted)",
            lineHeight: 1.6,
            maxWidth: 600,
            paddingBottom: 24,
            margin: 0,
          }}
        >
          {a}
        </p>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────
// Hook: oculta el header al hacer scroll hacia abajo (después de un umbral),
// lo muestra de nuevo al hacer scroll hacia arriba. En el top de la página
// siempre está visible.
function useAutoHideHeader(threshold = 80) {
  const [hidden, setHidden] = useState(false)
  const lastScroll = useRef(0)
  const ticking = useRef(false)

  useEffect(() => {
    const onScroll = () => {
      if (ticking.current) return
      ticking.current = true
      requestAnimationFrame(() => {
        const current = window.scrollY
        if (current <= threshold) {
          setHidden(false)
        } else if (current > lastScroll.current + 5) {
          // scroll down (con tolerancia de 5px para evitar jitter)
          setHidden(true)
        } else if (current < lastScroll.current - 5) {
          // scroll up
          setHidden(false)
        }
        lastScroll.current = current
        ticking.current = false
      })
    }
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [threshold])

  return hidden
}

export default function LandingPage() {
  const hidden = useAutoHideHeader()
  return (
    <div className="min-h-dvh bg-white text-[var(--gob-ink)] font-sans antialiased">

      {/* ── Navbar ───────────────────────────────────────── */}
      <header
        className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md transition-transform duration-300 ease-out"
        style={{ transform: hidden ? "translateY(-100%)" : "translateY(0)" }}
      >
        <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20 h-14 flex items-center justify-between">
          <GoberniaLogo size={18} />

          <nav className="hidden md:flex items-center gap-8 text-sm text-[var(--gob-muted)]">
            <a href="#producto"      className="hover:text-[var(--gob-navy)] transition-colors">Producto</a>
            <a href="#como-funciona" className="hover:text-[var(--gob-navy)] transition-colors">Cómo funciona</a>
            <a href="#faq"           className="hover:text-[var(--gob-navy)] transition-colors">FAQ</a>
          </nav>

          <div className="flex items-center gap-4">
            <Link href="/sign-in" className="text-sm text-[var(--gob-muted)] hover:text-[var(--gob-navy)] transition-colors hidden sm:block">
              Iniciar sesión
            </Link>
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-1.5 text-sm font-medium bg-[var(--gob-navy)] text-[var(--gob-bone)] px-4 py-2 rounded-lg hover:bg-[var(--gob-ink)] transition-colors"
            >
              Empezar <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="relative overflow-hidden min-h-dvh flex flex-col">
        <HeroWaveLines />

        <div className="relative z-10 flex-1 flex flex-col px-6 sm:px-12 lg:px-20 max-w-[1400px] mx-auto w-full pt-32 sm:pt-36 lg:pt-40 pb-8">
          {/* Headline 3 líneas — alterna palabras "dimmer" (apagadas) y "lighter" (resaltadas)
              al estilo de interractlabs.com. Tamaño 5.5rem = 88px, weight 300, letter-spacing -3px. */}
          <motion.h1
            variants={heroContainer}
            initial="hidden"
            animate="show"
            className="text-[var(--gob-ink)]"
            style={{
              fontFamily: "var(--font-sans)",
              fontWeight: 300,
              fontSize: "clamp(40px, 6.5vw, 88px)",
              lineHeight: 0.95,
              letterSpacing: "-0.03em",
              cursor: "default",
            }}
          >
            <motion.span variants={heroItem} className="block">
              <span style={{ opacity: 0.4 }}>Sesión de </span>
              <span>consejo</span>
            </motion.span>
            <motion.span variants={heroItem} className="block">
              <span>cada mes,</span>
              <span style={{ opacity: 0.4 }}> con cuatro</span>
            </motion.span>
            <motion.span variants={heroItem} className="block">
              <span>agentes</span>
              <span style={{ opacity: 0.4 }}> de </span>
              <span>IA.</span>
            </motion.span>
          </motion.h1>

          {/* Gap de 50px entre el texto y el "scroll down" + divider */}
          <div style={{ height: 50 }} />

          {/* "scroll down" a la derecha, justo antes del divider */}
          <motion.div
            variants={heroItem}
            initial="hidden"
            animate="show"
            className="flex justify-end pb-4"
          >
            <span
              className="text-xs text-[var(--gob-stone)] tracking-wider lowercase"
              style={{ animation: "hero-pulse 2.4s ease-in-out infinite" }}
            >
              scroll down
            </span>
          </motion.div>

          {/* Línea divisoria horizontal — sube con el texto */}
          <div className="h-px bg-[var(--gob-rule)]" />

          {/* Espacio flexible — empuja los CTAs al fondo del hero */}
          <div className="flex-1" />

          {/* CTAs discretos al pie, abajo a la izquierda */}
          <motion.div
            variants={heroItem}
            initial="hidden"
            animate="show"
            className="flex items-center gap-8"
          >
            <Link
              href="/sign-up"
              className="inline-flex items-center text-sm text-[var(--gob-ink)] hover:text-[var(--gob-navy)] transition-colors"
              style={{ borderBottom: "1px solid var(--gob-ink)", paddingBottom: 2 }}
            >
              Comenzar gratis
            </Link>
            <Link
              href="/sign-in"
              className="inline-flex items-center text-sm text-[var(--gob-muted)] hover:text-[var(--gob-navy)] transition-colors"
            >
              Ya tengo cuenta
            </Link>
          </motion.div>
        </div>

        <style>{`
          @keyframes hero-pulse {
            0%, 100% { opacity: 0.5; }
            50%      { opacity: 1; }
          }
        `}</style>
      </section>

      {/* ── Stats ────────────────────────────────────────── */}
      <section className="py-16 px-6 sm:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto grid grid-cols-2 md:grid-cols-4 gap-10">
          {[
            { n: "4",    label: "Agentes especializados" },
            { n: "8",    label: "Etapas de diagnóstico" },
            { n: "100%", label: "Cifrado y confidencial" },
            { n: "15′",  label: "Para tu primer análisis" },
          ].map((s, i) => (
            <FadeUp key={s.label} delay={i * 0.08}>
              <p className="text-4xl font-extrabold text-[var(--gob-navy)] tracking-tight" style={{ letterSpacing: "-0.03em" }}>{s.n}</p>
              <p className="italic font-light text-xs text-[var(--gob-stone)] mt-2 leading-snug">{s.label}</p>
            </FadeUp>
          ))}
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Agents ───────────────────────────────────────── */}
      <section id="producto" className="py-24 px-6 sm:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-[var(--gob-stone)] uppercase mb-4">El equipo</p>
            <h2 className="text-4xl md:text-5xl font-bold text-[var(--gob-ink)] leading-tight tracking-tight" style={{ letterSpacing: "-0.025em" }}>
              Cuatro expertos de IA<br />
              <span className="font-light italic text-[var(--gob-navy)]">en tu mesa directiva.</span>
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {AGENTS.map((a, i) => (
              <FadeUp key={a.id} delay={i * 0.09}>
                <div className="h-full">
                  <span
                    className="text-xs uppercase"
                    style={{ color: "var(--gob-stone)", letterSpacing: "0.05em" }}
                  >
                    {a.id}
                  </span>
                  <h3
                    className="text-2xl font-normal text-[var(--gob-ink)]"
                    style={{ marginTop: 12, marginBottom: 0, letterSpacing: "-0.01em" }}
                  >
                    {a.role}
                  </h3>
                  <div
                    className="w-full"
                    style={{ height: 1, backgroundColor: "var(--gob-rule)", margin: "20px 0" }}
                  />
                  <p className="text-sm leading-relaxed text-[var(--gob-muted)]" style={{ margin: 0 }}>
                    {a.desc}
                  </p>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Cómo funciona ────────────────────────────────── */}
      <section id="como-funciona" className="py-24 px-6 sm:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-[var(--gob-stone)] uppercase mb-4">El proceso</p>
            <h2 className="text-4xl md:text-5xl font-bold text-[var(--gob-ink)] tracking-tight leading-tight" style={{ letterSpacing: "-0.025em" }}>
              De cero a tu primer diagnóstico<br />
              <span className="font-light italic text-[var(--gob-navy)]">en tres pasos.</span>
            </h2>
          </FadeUp>

          <div>
            {STEPS.map((s, i) => (
              <FadeUp key={s.n} delay={i * 0.1}>
                <div
                  className="grid items-start"
                  style={{
                    gridTemplateColumns: "120px 1fr",
                    gap: 40,
                    padding: "60px 0",
                    borderTop: i === 0 ? "1px solid var(--gob-rule)" : "none",
                    borderBottom: "1px solid var(--gob-rule)",
                  }}
                >
                  <span
                    className="font-extralight leading-none"
                    style={{
                      fontSize: "clamp(48px, 5vw, 72px)",
                      color: "var(--gob-rule)",
                    }}
                  >
                    {s.n}
                  </span>
                  <div>
                    <h3
                      className="text-2xl font-normal text-[var(--gob-ink)]"
                      style={{ margin: 0, letterSpacing: "-0.01em" }}
                    >
                      {s.title}
                    </h3>
                    <p
                      className="text-base leading-relaxed text-[var(--gob-muted)]"
                      style={{ maxWidth: 480, marginTop: 16, marginBottom: 0 }}
                    >
                      {s.desc}
                    </p>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Para quién ───────────────────────────────────── */}
      <section className="py-24 px-6 sm:px-12 lg:px-20 bg-[var(--gob-bone)]">
        <div className="max-w-[1400px] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-[var(--gob-stone)] uppercase mb-4">Para quién</p>
            <h2 className="text-4xl md:text-5xl font-bold text-[var(--gob-ink)] tracking-tight leading-tight" style={{ letterSpacing: "-0.025em" }}>
              Diseñado para<br />
              <span className="font-light italic text-[var(--gob-navy)]">empresas reales.</span>
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {FOR_WHO.map((c, i) => (
              <FadeUp key={c.title} delay={i * 0.1}>
                <div className="bg-white border border-[var(--gob-rule)]/60 rounded-2xl p-7 space-y-3 h-full">
                  <h3 className="font-bold text-[var(--gob-navy)] text-sm">{c.title}</h3>
                  <p className="italic font-light text-sm text-[var(--gob-muted)] leading-relaxed">{c.desc}</p>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────── */}
      <section id="faq" className="py-24 px-6 sm:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto">
          <FadeUp>
            <div style={{ marginBottom: 60 }}>
              <h2
                className="text-4xl md:text-5xl font-bold text-[var(--gob-ink)] tracking-tight leading-tight"
                style={{ letterSpacing: "-0.025em" }}
              >
                FAQ<br />
                <span className="font-light italic text-[var(--gob-navy)]">preguntas frecuentes.</span>
              </h2>
            </div>
          </FadeUp>

          <FadeUp delay={0.1}>
            <div>
              {FAQS.map(f => <FAQItem key={f.q} q={f.q} a={f.a} />)}
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto px-6 sm:px-12 lg:px-20"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="py-28 px-6 sm:px-12 lg:px-20">
        <FadeUp className="max-w-[1400px] mx-auto space-y-8">
          <p className="text-xs font-semibold tracking-widest text-[var(--gob-stone)] uppercase">Empieza hoy</p>
          <h2 className="text-5xl md:text-6xl font-bold text-[var(--gob-ink)] leading-[1.0] tracking-tight" style={{ letterSpacing: "-0.035em" }}>
            Tu empresa merece un consejo<br />
            <span className="font-light italic text-[var(--gob-navy)]">que nunca duerme.</span>
          </h2>
          <p className="italic font-light text-xl text-[var(--gob-muted)] max-w-xl leading-relaxed">
            Sin consultores. Sin contratos. Primer diagnóstico en menos de 15 minutos.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] font-semibold px-8 py-4 rounded-xl hover:bg-[var(--gob-ink)] transition-all duration-200 text-base"
          >
            Comenzar gratis <ArrowRight className="h-4 w-4" />
          </Link>
        </FadeUp>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-[var(--gob-rule)]/60 py-8 px-6 sm:px-12 lg:px-20">
        <div className="max-w-[1400px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[var(--gob-stone)]">
          <div className="flex items-center gap-2.5">
            <GoberniaIcon size={18} />
            <span>GOBERNIA © {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/sign-in"  className="hover:text-[var(--gob-navy)] transition-colors">Iniciar sesión</Link>
            <Link href="/sign-up"  className="hover:text-[var(--gob-navy)] transition-colors">Registro</Link>
            <span>Tu información está cifrada y protegida.</span>
          </div>
        </div>
      </footer>

    </div>
  )
}
