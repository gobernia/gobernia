"use client"

import { useState, useEffect, useRef, useContext, createContext } from "react"
import Link from "next/link"
import { motion, useScroll, useTransform, useMotionValue, type MotionValue } from "framer-motion"
import { ArrowRight } from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

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

// ── Scroll-driven reveal ──────────────────────────────────
// Las palabras "Heavy" (negro intenso) inician en gris (opacity 0.4) igual que
// los conectores. Conforme el usuario scrollea, cada palabra se va oscureciendo
// de izquierda a derecha en función de cuánto ha avanzado el scroll dentro de
// la sección que las contiene.

const ScrollProgressContext = createContext<MotionValue<number> | null>(null)

// Disponible en Framer Motion como una de las cadenas válidas del tipo Edge
type ScrollOffset = [string, string]

/**
 * Envuelve un título: registra la progresión del scroll mientras la sección
 * cruza el viewport y la expone vía context a los <Heavy>.
 *  - default offset = secciones que entran desde abajo
 *  - hero: pasar offset={["start start", "end start"]}
 */
function ScrollReveal({
  children,
  offset,
  className = "",
}: {
  children: React.ReactNode
  offset?: ScrollOffset
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  // Si no se pasa offset → comportamiento por defecto para secciones (rise into viewport)
  const { scrollYProgress } = useScroll({
    target: ref,
    // @ts-expect-error framer accepts string-array offsets at runtime
    offset: offset ?? ["start end", "start 0.3"],
  })
  return (
    <ScrollProgressContext.Provider value={scrollYProgress}>
      <div ref={ref} className={className}>{children}</div>
    </ScrollProgressContext.Provider>
  )
}

/**
 * Palabra resaltada. Su opacidad se interpola entre 0.4 (gris muted) y 1 (ink full)
 * a lo largo del rango [start, end] del progreso de scroll del padre.
 *   range=[0, 0.4]   → empieza a oscurecer desde el primer instante de scroll,
 *                      completa a 40% del progreso (palabras más a la izquierda)
 *   range=[0.5, 0.9] → empieza más tarde, completa cerca del final (palabras a la derecha)
 */
function Heavy({
  children,
  range = [0, 0.6],
}: {
  children: React.ReactNode
  range?: [number, number]
}) {
  const ctx = useContext(ScrollProgressContext)
  const fallback = useMotionValue(1)
  const source = ctx ?? fallback
  const opacity = useTransform(source, range, [0.4, 1])
  return (
    <motion.span style={{ opacity, fontWeight: 500 }}>
      {children}
    </motion.span>
  )
}

// ── Data ──────────────────────────────────────────────────
const CONSEJEROS = [
  { id: "CFO",     role: "Finanzas",   desc: "Tus números bajo la lupa: rentabilidad, flujo de caja y estructura de capital, antes de que el mes cierre." },
  { id: "CSO",     role: "Estrategia", desc: "Define dónde ganar: posicionamiento, mercado y crecimiento alineados a tu visión de largo plazo." },
  { id: "CRO",     role: "Riesgos",    desc: "Anticipa lo que viene: riesgos operativos, legales y de mercado, con planes de mitigación antes de que escalen." },
  { id: "Auditor", role: "Auditoría",  desc: "Orden, control y cumplimiento: mide tu Governance Score y cierra brechas críticas." },
  { id: "Retador", role: "Retador",    desc: "Cuestiona cada decisión: aplica un pre-mortem que expone supuestos débiles y riesgos ocultos antes de actuar." },
]

const STEPS = [
  { n: "01", title: "Configura tu empresa",  desc: "8 pasos conversacionales. Industria, equipo, prioridades, KPIs y expectativas. Menos de 30 minutos para conocerte bien." },
  { n: "02", title: "Tu consejo se activa",  desc: "Los cinco consejeros con IA leen tu perfil, generan el primer diagnóstico completo y proponen un plan de acción." },
  { n: "03", title: "Sesiones cada mes",     desc: "Análisis actualizado cada periodo. Chatea con cualquier consejero sobre cualquier decisión en tiempo real." },
]

const FOR_WHO = [
  { title: "Empresas familiares",    desc: "Módulos de protocolo, análisis de concentración y planificación de sucesión activados automáticamente." },
  { title: "PyMEs en crecimiento",   desc: "Benchmarks por industria y tamaño. Identifica en qué punto del camino estás y qué necesitas para el siguiente." },
  { title: "Directivos sin consejo", desc: "Si aún no tienes consejo de administración, Gobernia es el punto de partida para estructurar tu gobierno." },
]

const FAQS = [
  { q: "¿Gobernia reemplaza a mi consejo de administración?",  a: "No. Es un copiloto que complementa o prepara el camino hacia un consejo humano. Te da el rigor analítico que normalmente solo tienen las grandes corporaciones, mientras decides cuándo incorporar consejeros externos." },
  { q: "¿Qué tan segura está mi información?",                 a: "Toda la información está cifrada en tránsito y en reposo. Infraestructura en AWS vía Supabase. Tus datos nunca se usan para entrenar modelos ni se comparten con terceros." },
  { q: "¿Necesito experiencia en Consejos de Administración?",       a: "Para nada. Gobernia está diseñado para directivos y dueños que quieren profesionalizar su toma de decisiones sin ser expertos. El onboarding es conversacional y guiado." },
  { q: "¿Funciona para empresas familiares?",                  a: "Especialmente para ellas. Activa módulos de protocolo familiar, análisis de concentración de decisiones y planificación de sucesión cuando detecta que la empresa es familiar." },
  { q: "¿Con qué frecuencia se actualiza el análisis?",        a: "Tú controlas la frecuencia: mensual, bimestral, trimestral o semestral. Además puedes chatear con tus consejeros con IA en cualquier momento entre sesiones." },
  { q: "¿Cuánto tiempo toma ver los primeros resultados?",     a: "El primer diagnóstico completo está disponible al terminar el onboarding. Menos de 30 minutos desde que entras por primera vez." },
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
            fontSize: "0.95rem",
            color: "var(--gob-muted)",
            lineHeight: 1.6,
            maxWidth: "40em",
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
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] h-14 flex items-center justify-between">
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
        <div className="relative z-10 flex-1 flex flex-col w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)] pt-32 sm:pt-36 lg:pt-40 pb-8">
          {/* Headline 3 líneas — el hero se muestra en estado final desde el inicio
              (los Heavy heredan opacity 1 al no estar dentro de un ScrollReveal) */}
          <motion.h1
            variants={heroContainer}
            initial="hidden"
            animate="show"
            className="font-sans text-[var(--gob-ink)]"
            style={{
              fontWeight: 300,
              fontSize: "clamp(40px, 7vw, 168px)",
              lineHeight: 0.95,
              letterSpacing: "-0.03em",
              cursor: "default",
            }}
          >
            <motion.span variants={heroItem} className="block">
              <span style={{ opacity: 0.4 }}>La </span>
              <Heavy>evolución</Heavy>
            </motion.span>
            <motion.span variants={heroItem} className="block">
              <span style={{ opacity: 0.4 }}>del </span>
              <Heavy>Consejo de</Heavy>
            </motion.span>
            <motion.span variants={heroItem} className="block">
              <Heavy>Administración.</Heavy>
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

          {/* Descripción pegada a la línea, alineada a la derecha */}
          <motion.div
            variants={heroItem}
            initial="hidden"
            animate="show"
            className="flex justify-end pt-5"
          >
            <p
              className="text-sm text-[var(--gob-muted)] leading-relaxed sm:text-right"
              style={{ maxWidth: "32em" }}
            >
              Cinco consejeros con IA sesionan sobre tu empresa cada mes. Las mejores
              prácticas corporativas, por una fracción del costo — sin contratar
              consultores.
            </p>
          </motion.div>

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
      <section className="py-12 sm:py-16 3xl:py-24 px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto grid grid-cols-2 md:grid-cols-4 gap-10">
          {[
            { n: "5",    label: "Consejeros con IA" },
            { n: "8",    label: "Etapas de diagnóstico" },
            { n: "100%", label: "Cifrado y confidencial" },
            { n: "30′",  label: "Para tu primer diagnóstico" },
          ].map((s, i) => (
            <FadeUp key={s.label} delay={i * 0.08}>
              <p className="text-4xl font-bold text-[var(--gob-navy)] tracking-tight" style={{ letterSpacing: "-0.03em" }}>{s.n}</p>
              <p className="italic font-light text-xs text-[var(--gob-stone)] mt-2 leading-snug">{s.label}</p>
            </FadeUp>
          ))}
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Agents ───────────────────────────────────────── */}
      <section id="producto" className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-medium tracking-widest text-[var(--gob-stone)] uppercase mb-4">Cinco consejeros</p>
            <ScrollReveal>
              <h2
                className="font-light text-[var(--gob-ink)]"
                style={{
                  fontSize: "clamp(28px, 4.2vw, 104px)",
                  lineHeight: 1.0,
                  letterSpacing: "-0.03em",
                }}
              >
                <span style={{ opacity: 0.4 }}>Cinco </span>
                <Heavy range={[0.1, 0.45]}>consejeros con IA</Heavy>
                <span style={{ opacity: 0.4 }}> en tu </span>
                <Heavy range={[0.4, 0.8]}>Sesión de Consejo.</Heavy>
              </h2>
            </ScrollReveal>
          </FadeUp>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-8">
            {CONSEJEROS.map((a, i) => (
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
      <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Cómo funciona ────────────────────────────────── */}
      <section id="como-funciona" className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-medium tracking-widest text-[var(--gob-stone)] uppercase mb-4">El proceso</p>
            <ScrollReveal>
              <h2
                className="font-light text-[var(--gob-ink)]"
                style={{
                  fontSize: "clamp(28px, 4.2vw, 104px)",
                  lineHeight: 1.0,
                  letterSpacing: "-0.03em",
                }}
              >
                <span style={{ opacity: 0.4 }}>De cero a tu </span>
                <Heavy range={[0.1, 0.45]}>primer diagnóstico</Heavy>
                <span style={{ opacity: 0.4 }}> en </span>
                <Heavy range={[0.4, 0.8]}>tres pasos.</Heavy>
              </h2>
            </ScrollReveal>
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
                    className="font-light leading-none"
                    style={{
                      fontSize: "clamp(42px, 5.5vw, 128px)",
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
                      style={{ maxWidth: "32em", marginTop: 16, marginBottom: 0 }}
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
      <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── Para quién ───────────────────────────────────── */}
      <section className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)] bg-[var(--gob-bone)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-medium tracking-widest text-[var(--gob-stone)] uppercase mb-4">Para quién</p>
            <ScrollReveal>
              <h2
                className="font-light text-[var(--gob-ink)]"
                style={{
                  fontSize: "clamp(28px, 4.2vw, 104px)",
                  lineHeight: 1.0,
                  letterSpacing: "-0.03em",
                }}
              >
                <span style={{ opacity: 0.4 }}>Diseñado para </span>
                <Heavy range={[0.2, 0.7]}>empresas reales.</Heavy>
              </h2>
            </ScrollReveal>
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
      <section id="faq" className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto">
          <FadeUp>
            <div style={{ marginBottom: 60 }}>
              <ScrollReveal>
                <h2
                  className="font-light text-[var(--gob-ink)]"
                  style={{
                    fontSize: "clamp(28px, 4.2vw, 104px)",
                    lineHeight: 1.0,
                    letterSpacing: "-0.03em",
                  }}
                >
                  <Heavy range={[0.15, 0.55]}>FAQ</Heavy>
                  <span style={{ opacity: 0.4 }}> — preguntas frecuentes.</span>
                </h2>
              </ScrollReveal>
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
      <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px bg-[var(--gob-rule)]/60" /></div>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="py-20 sm:py-28 3xl:py-36 px-[var(--px-fluid)]">
        <FadeUp className="w-full max-w-[var(--container-fluid)] mx-auto space-y-8">
          <p className="text-xs font-medium tracking-widest text-[var(--gob-stone)] uppercase">Empieza hoy</p>
          <ScrollReveal>
            <h2
              className="font-light text-[var(--gob-ink)]"
              style={{
                fontSize: "clamp(34px, 5.5vw, 128px)",
                lineHeight: 0.98,
                letterSpacing: "-0.03em",
              }}
            >
              <span style={{ opacity: 0.4 }}>Tu empresa merece un </span>
              <Heavy range={[0.15, 0.5]}>consejo</Heavy>
              <br />
              <span style={{ opacity: 0.4 }}>que </span>
              <Heavy range={[0.45, 0.85]}>nunca duerme.</Heavy>
            </h2>
          </ScrollReveal>
          <p className="italic font-light text-xl text-[var(--gob-muted)] max-w-xl leading-relaxed">
            Cinco consejeros listos para sesionar sobre tu empresa. Sin consultores, cancela cuando quieras — primer diagnóstico en menos de 30 minutos.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] font-medium px-8 py-4 rounded-xl hover:bg-[var(--gob-ink)] transition-all duration-200 text-base"
          >
            Comenzar gratis <ArrowRight className="h-4 w-4" />
          </Link>
        </FadeUp>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-[var(--gob-rule)]/60 py-8 sm:py-10 3xl:py-14 px-[var(--px-fluid)]">
        <div className="w-full max-w-[var(--container-fluid)] mx-auto flex flex-col sm:flex-row items-center justify-between gap-6 text-xs text-[var(--gob-stone)]">
          <div className="flex items-center gap-3">
            <GoberniaLogo size={16} />
            <span>© {new Date().getFullYear()}</span>
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
