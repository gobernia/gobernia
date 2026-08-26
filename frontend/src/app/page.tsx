"use client"

// Landing V2 — hero editorial estilo "kettal" + sistema bento del Inicio:
//   · Logo GOBERNIA normal en la barra del menú.
//   · Headline gigante FIJO (Inter, como el Inicio): no se mueve con el
//     scroll — el video, en el flujo del documento, sube y lo va tapando.
//   · Pie del hero: ubicación + hora en vivo | tagline con subrayado naranja.
//   · Tipografía y variantes del dashboard (Inter en todo, eyebrows 10.5px,
//     títulos bold tracking apretado) y paleta bento (PAPER/INK/SAND/BNAVY).
//   · Botones en azul BNAVY — el naranja ACCENT solo en detalles (squiggle,
//     tags, subrayados).

import { useState, useEffect, useRef, useContext, createContext, type CSSProperties, type ReactNode } from "react"
import Link from "next/link"
import Image from "next/image"
import { motion, useScroll, useTransform, useMotionValue, type MotionValue } from "framer-motion"
import { ArrowRight, Lock, ShieldCheck, KeyRound, EyeOff, Play, Pause, Rewind, FastForward, Volume2, VolumeX } from "lucide-react"
import GoberniaLogo from "@/components/ui/GoberniaLogo"

// ── Easing ────────────────────────────────────────────────
type CubicBezier = [number, number, number, number]
const EASE: CubicBezier = [0.22, 1, 0.36, 1]

// ── Paleta bento — mismos tokens del Inicio ───────────────
const PAPER = "#F2F2F0"
const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"
// El CSS global pone h1/h2 en serif (Newsreader). En el bento NO queremos serif:
// forzamos sans en cada título, igual que en el Inicio.
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

// ── Geometría del hero ────────────────────────────────────
const HERO_ALTO = "74svh"  // alto del área del hero; el video asoma debajo

// ── Video que se ensancha con el scroll + controles propios ──
// Arranca con los márgenes de la página y esquinas bento (26px); al hacer
// scroll los márgenes se cierran hasta quedar a sangre completa. Se muestra
// COMPLETO (16:9, sin recorte) y trae controles táctiles: pausa, ±10s,
// audio y barra de progreso con seek — funcionan en desktop y móvil.
function VideoExpand() {
  const { scrollY } = useScroll()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [m, setM] = useState({ pad: 48, dist: 400 })
  const [playing, setPlaying] = useState(true)
  const [muted, setMuted] = useState(true)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const calc = () => setM({
      // Mismo cálculo que --px-fluid: clamp(1.25rem, 4vw, 5rem)
      pad: Math.min(Math.max(20, window.innerWidth * 0.04), 80),
      dist: window.innerHeight * 0.5,
    })
    calc()
    window.addEventListener("resize", calc)
    return () => window.removeEventListener("resize", calc)
  }, [])

  const inset = useTransform(scrollY, [0, m.dist], [m.pad, 0])
  const radius = useTransform(scrollY, [0, m.dist], [26, 0])

  const togglePlay = () => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) void v.play()
    else v.pause()
  }
  const skip = (s: number) => {
    const v = videoRef.current
    if (!v || !v.duration) return
    v.currentTime = Math.min(Math.max(0, v.currentTime + s), v.duration)
  }
  const toggleMute = () => {
    const v = videoRef.current
    if (!v) return
    v.muted = !v.muted
    setMuted(v.muted)
  }
  const seek = (e: React.PointerEvent<HTMLDivElement>) => {
    const v = videoRef.current
    if (!v || !v.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(Math.max(0, (e.clientX - rect.left) / rect.width), 1)
    v.currentTime = ratio * v.duration
    setProgress(ratio)
  }

  const btn =
    "flex h-11 w-11 items-center justify-center rounded-full text-white transition-colors " +
    "bg-[rgba(14,22,38,0.5)] hover:bg-[rgba(14,22,38,0.75)] backdrop-blur-sm"

  return (
    <section className="relative">
      <motion.div className="relative overflow-hidden" style={{ marginInline: inset, borderRadius: radius }}>
        <video
          ref={videoRef}
          src="/video/Fertodd.mp4"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={e => {
            const v = e.currentTarget
            if (v.duration) setProgress(v.currentTime / v.duration)
          }}
          className="block w-full h-auto"
        />

        {/* Controles: siempre visibles (táctiles), sobre un degradado para legibilidad */}
        <div className="absolute inset-x-0 bottom-0 px-4 pb-3 pt-12 sm:px-6 sm:pb-5 bg-gradient-to-t from-[rgba(14,22,38,0.55)] to-transparent">
          {/* Barra de progreso con seek */}
          <div
            role="slider"
            aria-label="Posición del video"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            onPointerDown={seek}
            className="group mb-3 cursor-pointer py-1.5"
          >
            <div className="h-1 w-full rounded-full bg-white/30 transition-all group-hover:h-1.5">
              <div className="h-full rounded-full bg-white" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
          <div className="flex items-center justify-center gap-2.5 sm:gap-3">
            <button type="button" onClick={() => skip(-10)} aria-label="Retroceder 10 segundos" className={btn}>
              <Rewind className="h-4.5 w-4.5" />
            </button>
            <button type="button" onClick={togglePlay} aria-label={playing ? "Pausar" : "Reproducir"} className={btn}>
              {playing ? <Pause className="h-4.5 w-4.5" /> : <Play className="h-4.5 w-4.5" />}
            </button>
            <button type="button" onClick={() => skip(10)} aria-label="Adelantar 10 segundos" className={btn}>
              <FastForward className="h-4.5 w-4.5" />
            </button>
            <button type="button" onClick={toggleMute} aria-label={muted ? "Activar sonido" : "Silenciar"} className={btn}>
              {muted ? <VolumeX className="h-4.5 w-4.5" /> : <Volume2 className="h-4.5 w-4.5" />}
            </button>
          </div>
        </div>
      </motion.div>
    </section>
  )
}

// ── Reloj en vivo ("Ciudad de México 16:12") ──────────────
function useHora() {
  const [hora, setHora] = useState("")
  useEffect(() => {
    const tick = () =>
      setHora(new Date().toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false }))
    tick()
    const id = setInterval(tick, 15_000)
    return () => clearInterval(id)
  }, [])
  return hora
}

// ── Eyebrow bento (igual que el Inicio) ───────────────────
function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={`text-[10.5px] font-extrabold uppercase tracking-[0.17em] ${className}`}
      style={{ ...SANS, color: MUTED }}
    >
      {children}
    </p>
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

// ── Fade-up on scroll ─────────────────────────────────────
function FadeUp({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode
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

// ── Scroll-driven reveal (palabras que se oscurecen) ──────
const ScrollProgressContext = createContext<MotionValue<number> | null>(null)

type ScrollOffset = [string, string]

function ScrollReveal({
  children,
  offset,
  className = "",
}: {
  children: ReactNode
  offset?: ScrollOffset
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
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

function Heavy({
  children,
  range = [0, 0.6],
}: {
  children: ReactNode
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
const SECURITY = [
  { icon: Lock, title: "Cifrado en tránsito", desc: "Toda la comunicación viaja sobre HTTPS/TLS." },
  { icon: ShieldCheck, title: "Cifrado en reposo", desc: "Tu información se almacena cifrada en la base de datos." },
  { icon: KeyRound, title: "Acceso autenticado", desc: "Solo tú entras a tu cuenta, con inicio de sesión seguro." },
  { icon: EyeOff, title: "Privado y confidencial", desc: "Tu información es solo para tu Consejo y sus análisis." },
]

const CONSEJEROS = [
  { tag: "Consejero en", name: "Finanzas",     desc: "Tus números bajo la lupa: rentabilidad, flujo de caja y estructura de capital, antes de que el mes cierre." },
  { tag: "Consejero en", name: "Estrategia",   desc: "Define dónde ganar: posicionamiento, mercado y crecimiento alineados a tu visión de largo plazo." },
  { tag: "Consejero en", name: "Riesgos",      desc: "Anticipa lo que viene: riesgos operativos, legales y de mercado, con planes de mitigación antes de que escalen." },
  { tag: "Consejero en", name: "Auditoría",    desc: "Orden, control y cumplimiento: mide tu Governance Score y cierra brechas críticas." },
  { tag: "Consejero",    name: "Independiente", desc: "El Retador: cuestiona cada decisión con un pre-mortem que expone supuestos débiles y riesgos ocultos antes de actuar." },
]

const STEPS = [
  { n: "01", title: "Configura tu empresa",  desc: "8 pasos conversacionales. Industria, equipo, prioridades, KPIs y expectativas. Menos de 30 minutos para conocerte bien." },
  { n: "02", title: "Tu Consejo se activa",  desc: "Los cinco consejeros con IA leen tu perfil, generan el primer diagnóstico completo y proponen un plan de acción." },
  { n: "03", title: "Sesiones cada mes",     desc: "Análisis actualizado cada periodo. Chatea con cualquier consejero sobre cualquier decisión en tiempo real." },
]

const FOR_WHO = [
  { title: "Empresas familiares",    desc: "Módulos de protocolo, análisis de concentración y planificación de sucesión activados automáticamente." },
  { title: "PyMEs en crecimiento",   desc: "Benchmarks por industria y tamaño. Identifica en qué punto del camino estás y qué necesitas para el siguiente." },
  { title: "Directivos sin consejo", desc: "Si aún no tienes Consejo de Administración, Gobernia es el punto de partida para estructurar tu gobierno." },
]

const FAQS = [
  { q: "¿Gobernia reemplaza a mi Consejo de Administración?",  a: "No. Es un copiloto que complementa o prepara el camino hacia un Consejo humano. Te da el rigor analítico que normalmente solo tienen las grandes corporaciones, mientras decides cuándo incorporar consejeros externos." },
  { q: "¿Qué tan segura está mi información?",                 a: "Toda la información está cifrada en tránsito y en reposo. Infraestructura en AWS vía Supabase. Tus datos nunca se usan para entrenar modelos ni se comparten con terceros." },
  { q: "¿Necesito experiencia en Consejos de Administración?",       a: "Para nada. Gobernia está diseñado para directivos y dueños que quieren profesionalizar su toma de decisiones sin ser expertos. El onboarding es conversacional y guiado." },
  { q: "¿Funciona para empresas familiares?",                  a: "Especialmente para ellas. Activa módulos de protocolo familiar, análisis de concentración de decisiones y planificación de sucesión cuando detecta que la empresa es familiar." },
  { q: "¿Con qué frecuencia se actualiza el análisis?",        a: "Tú controlas la frecuencia: mensual, bimestral, trimestral o semestral. Además puedes chatear con tus consejeros con IA en cualquier momento entre sesiones." },
  { q: "¿Cuánto tiempo toma ver los primeros resultados?",     a: "El primer diagnóstico completo está disponible al terminar el onboarding. Menos de 30 minutos desde que entras por primera vez." },
]

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: `1px solid ${LINE}` }}>
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
        <span style={{ ...SANS, fontSize: 16, color: INK, fontWeight: 600, letterSpacing: "-0.015em", flex: 1, paddingRight: 24 }}>
          {q}
        </span>
        <span style={{ fontSize: 20, color: ACCENT, flexShrink: 0, width: 24, textAlign: "center" }}>
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
        <p style={{ fontSize: "0.95rem", color: INK2, lineHeight: 1.6, maxWidth: "40em", paddingBottom: 24, margin: 0 }}>
          {a}
        </p>
      </div>
    </div>
  )
}

// ── Barra que se esconde al bajar y reaparece al subir ────
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
          setHidden(true)   // bajando (tolerancia de 5px para evitar jitter)
        } else if (current < lastScroll.current - 5) {
          setHidden(false)  // subiendo
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

// ── Page ──────────────────────────────────────────────────
export default function LandingV2() {
  const hora = useHora()
  const headerHidden = useAutoHideHeader()

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: PAPER, color: INK }}>

      {/* ── Barra de menú: se esconde al bajar, reaparece al subir ── */}
      <header
        className="fixed top-0 inset-x-0 z-50 px-[var(--px-fluid)] transition-transform duration-500"
        style={{
          transform: headerHidden ? "translateY(-100%)" : "translateY(0)",
          transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        <div className="w-full max-w-[var(--container-fluid)] mx-auto h-16 flex items-center justify-between">
          <GoberniaLogo size={26} />

          <div className="flex items-center gap-3">
            {/* Píldora de navegación (como la referencia) */}
            <nav
              className="hidden md:flex items-center rounded-full px-2 py-1.5 text-sm font-medium"
              style={{ ...SANS, background: SAND, color: INK2 }}
            >
              <a href="#producto"      className="px-3.5 py-1.5 rounded-full transition-colors hover:text-[#152742]">Producto</a>
              <a href="#como-funciona" className="px-3.5 py-1.5 rounded-full transition-colors hover:text-[#152742]">Cómo funciona</a>
              <a href="#faq"           className="px-3.5 py-1.5 rounded-full transition-colors hover:text-[#152742]">FAQ</a>
              <Link href="/sign-in"    className="px-3.5 py-1.5 rounded-full transition-colors hover:text-[#152742]">Iniciar sesión</Link>
            </nav>

            <Link
              href="/sign-up"
              className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
              style={{ ...SANS, background: BNAVY }}
            >
              Empezar <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero FIJO: no se mueve con el scroll; el video sube y lo tapa ──
             El headline vive PEGADO al borde superior del video.
             OJO: el padding va POR FUERA del contenedor centrado (igual que en
             las secciones) para que el headline alinee con el resto de la página. */}
      {/* En móvil el headline queda CENTRADO entre la barra del menú (pt-16
          compensa su altura) y el pie de Ciudad de México; en desktop se
          ancla abajo junto al video. */}
      <div className="fixed inset-x-0 top-0 z-0 flex flex-col px-[var(--px-fluid)] pt-16 lg:pt-0" style={{ height: HERO_ALTO }}>
        {/* Texto descriptivo arriba a la DERECHA (entre el menú y la mitad),
            posicionado en absoluto sobre el hero */}
        <div className="absolute inset-x-0 hidden lg:block px-[var(--px-fluid)]" style={{ top: "26%" }}>
          <div className="w-full max-w-[var(--container-fluid)] mx-auto flex justify-end">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: EASE, delay: 0.4 }}
              className="max-w-md"
            >
              <p className="text-[15.5px] leading-relaxed" style={{ color: INK2 }}>
                Cinco consejeros con IA sesionan sobre tu empresa cada mes. Las mejores
                prácticas corporativas, por una fracción del costo — sin contratar
                consultores.
              </p>
              <Link
                href="/sign-up"
                className="mt-6 inline-flex items-center gap-2.5 text-[15px] font-semibold transition-colors hover:text-[#152742]"
                style={{ ...SANS, color: INK }}
              >
                <ArrowRight className="h-4 w-4" style={{ color: ACCENT }} /> Comenzar gratis
              </Link>
            </motion.div>
          </div>
        </div>

        {/* Headline grande a la IZQUIERDA: my-auto lo centra en móvil entre el
            menú y el pie; en desktop vuelve a anclarse abajo. */}
        <div className="w-full max-w-[var(--container-fluid)] mx-auto my-auto lg:my-0 lg:mt-auto">
          <motion.h1
            variants={heroContainer}
            initial="hidden"
            animate="show"
            style={{
              ...SANS,
              color: INK,
              fontWeight: 300,
              fontSize: "clamp(38px, 4.8vw, 118px)",
              lineHeight: 0.98,
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

          {/* En móvil (sin columna derecha) la descripción va bajo el headline */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.4 }}
            className="lg:hidden max-w-md mt-6"
          >
            <p className="text-[15.5px] leading-relaxed" style={{ color: INK2 }}>
              Cinco consejeros con IA sesionan sobre tu empresa cada mes. Las mejores
              prácticas corporativas, por una fracción del costo — sin contratar
              consultores.
            </p>
            <Link
              href="/sign-up"
              className="mt-5 inline-flex items-center gap-2.5 text-[15px] font-semibold transition-colors hover:text-[#152742]"
              style={{ ...SANS, color: INK }}
            >
              <ArrowRight className="h-4 w-4" style={{ color: ACCENT }} /> Comenzar gratis
            </Link>
          </motion.div>
        </div>

        {/* Pie del hero, entre el headline y el borde del video */}
        <div className="w-full max-w-[var(--container-fluid)] mx-auto flex flex-wrap items-end justify-between gap-x-8 gap-y-2 pt-6 pb-3.5">
          <span className="text-[10.5px] font-extrabold uppercase tracking-[0.17em]" style={{ ...SANS, color: INK2 }}>
            Ciudad de México{hora ? ` · ${hora}` : ""}
          </span>
          <span
            className="text-sm font-semibold"
            style={{ ...SANS, color: INK, borderBottom: `2px solid ${ACCENT}`, paddingBottom: 3, letterSpacing: "-0.01em" }}
          >
            Tu Consejo, sesión tras sesión
          </span>
        </div>
      </div>

      {/* ── Espaciador del hero: el video asoma al fondo ── */}
      <div style={{ height: HERO_ALTO }} aria-hidden />

      {/* ── Todo lo que sigue viaja POR ENCIMA del hero fijo ── */}
      <div className="relative z-10" style={{ background: PAPER }}>

        {/* Video — arranca angosto y se ensancha con el scroll mientras sube
            tapando el hero */}
        <VideoExpand />

        {/* ── Agents: justo después del video ──────────────── */}
        <section id="producto" className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]">
          <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
            <FadeUp>
              <Eyebrow className="mb-4">Cinco consejeros</Eyebrow>
              <ScrollReveal>
                <h2
                  style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.02, letterSpacing: "-0.03em", maxWidth: "13em" }}
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
                <FadeUp key={a.name} delay={i * 0.09}>
                  <div className="h-full">
                    <span className="text-[11px] font-extrabold uppercase tracking-[0.09em]" style={{ ...SANS, color: ACCENT }}>
                      {a.tag}
                    </span>
                    <h3
                      className="text-[23px] font-bold leading-tight tracking-[-.025em]"
                      style={{ ...SANS, color: INK, marginTop: 12, marginBottom: 0 }}
                    >
                      {a.name}
                    </h3>
                    <div className="w-full" style={{ height: 1, backgroundColor: LINE, margin: "20px 0" }} />
                    <p className="text-[14.5px] leading-relaxed" style={{ color: INK2, margin: 0 }}>
                      {a.desc}
                    </p>
                  </div>
                </FadeUp>
              ))}
            </div>
          </div>
        </section>

        {/* ── Empieza + números: un solo tile bento navy (como los tiles
               oscuros del Inicio), en lugar de CTAs sueltos + stats genéricos ── */}
        <section className="pb-16 sm:pb-24 3xl:pb-32 px-[var(--px-fluid)]">
          <FadeUp className="w-full max-w-[var(--container-fluid)] mx-auto">
            <div
              className="rounded-[26px] p-[30px] sm:p-12 lg:p-14 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center overflow-hidden"
              style={{ background: BNAVY, color: "#fff" }}
            >
              {/* Izquierda: el pitch + CTAs */}
              <div>
                <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em]" style={{ ...SANS, color: "rgba(255,255,255,.55)" }}>
                  Listo desde el primer día
                </p>
                <h3
                  className="mt-4 font-bold leading-[1.08] tracking-[-.03em]"
                  style={{ ...SANS, fontSize: "clamp(26px, 2.6vw, 44px)" }}
                >
                  Configuras hoy,<br />sesionas este mes.
                </h3>
                <p className="mt-4 text-[15.5px] leading-relaxed" style={{ color: "rgba(255,255,255,.72)", maxWidth: "30em" }}>
                  Sin consultores ni implementaciones largas: entras, Todd conoce tu
                  empresa y tu Consejo queda listo para trabajar.
                </p>
                <div className="mt-8 flex items-center gap-6">
                  <Link
                    href="/sign-up"
                    className="inline-flex items-center gap-2.5 rounded-full px-5 py-3 text-[13px] font-bold tracking-wide transition-all hover:brightness-95"
                    style={{ ...SANS, background: "#fff", color: BNAVY }}
                  >
                    Comenzar gratis <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/sign-in"
                    className="inline-flex items-center text-sm font-semibold transition-colors hover:text-white"
                    style={{ ...SANS, color: "rgba(255,255,255,.65)" }}
                  >
                    Ya tengo cuenta
                  </Link>
                </div>
              </div>

              {/* Derecha: los números, en rejilla 2×2 con filetes finos */}
              <div className="grid grid-cols-2">
                {[
                  { n: "5",    label: "consejeros con IA en cada sesión" },
                  { n: "8",    label: "etapas de diagnóstico de tu empresa" },
                  { n: "100%", label: "cifrado y confidencial" },
                  { n: "30′",  label: "para tu primer diagnóstico" },
                ].map((s, i) => (
                  <div
                    key={s.label}
                    className="p-6 sm:p-7"
                    style={{
                      borderTop:  i >= 2      ? "1px solid rgba(255,255,255,.14)" : "none",
                      borderLeft: i % 2 === 1 ? "1px solid rgba(255,255,255,.14)" : "none",
                    }}
                  >
                    <span aria-hidden className="block h-1.5 w-1.5 mb-3.5" style={{ background: ACCENT }} />
                    <p className="font-bold tracking-[-.05em] leading-[.88]" style={{ ...SANS, fontSize: "clamp(34px, 3vw, 52px)" }}>
                      {s.n}
                    </p>
                    <p className="mt-2 text-[13px] font-semibold leading-snug" style={{ ...SANS, color: "rgba(255,255,255,.6)", maxWidth: "16ch" }}>
                      {s.label}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </FadeUp>
        </section>

        {/* ── Divider ──────────────────────────────────────── */}
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px" style={{ background: LINE }} /></div>

        {/* ── Cómo funciona ────────────────────────────────── */}
        <section id="como-funciona" className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]">
          <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
            <FadeUp>
              <Eyebrow className="mb-4">El proceso</Eyebrow>
              <ScrollReveal>
                <h2
                  style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.02, letterSpacing: "-0.03em", maxWidth: "13em" }}
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
                      borderTop: i === 0 ? `1px solid ${LINE}` : "none",
                      borderBottom: `1px solid ${LINE}`,
                    }}
                  >
                    <span className="font-bold leading-[.85] tracking-[-.04em]" style={{ ...SANS, fontSize: "clamp(42px, 5.5vw, 128px)", color: INK, opacity: 0.15 }}>
                      {s.n}
                    </span>
                    <div>
                      <h3 className="text-[23px] font-bold leading-tight tracking-[-.025em]" style={{ ...SANS, color: INK, margin: 0 }}>
                        {s.title}
                      </h3>
                      <p className="text-[15.5px] leading-relaxed" style={{ color: INK2, maxWidth: "32em", marginTop: 16, marginBottom: 0 }}>
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
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px" style={{ background: LINE }} /></div>

        {/* ── Todd, tu Secretario: te acompaña desde el inicio ── */}
        <section className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)] overflow-x-clip">
          <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">

            {/* Título tamaño hero + intro */}
            <FadeUp>
              <Eyebrow className="mb-4">Tu Secretario de consejo</Eyebrow>
              <ScrollReveal>
                <h2
                  style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.0, letterSpacing: "-0.03em", maxWidth: "13em" }}
                >
                  <span style={{ opacity: 0.4 }}>Desde el inicio, </span>
                  <Heavy range={[0.1, 0.45]}>Todd</Heavy>
                  <br />
                  <span style={{ opacity: 0.4 }}>te </span>
                  <Heavy range={[0.4, 0.8]}>acompaña.</Heavy>
                </h2>
              </ScrollReveal>
              <p className="text-[17px] leading-relaxed mt-8" style={{ color: INK2, maxWidth: "38em" }}>
                Al entrar a Gobernia te recibe <span className="font-semibold" style={{ color: INK }}>Todd</span>,
                el Secretario del Consejo. Él te va guiando en todo el proceso: conoce tu empresa
                haciéndote preguntas como en una conversación, y con tus respuestas construye el
                diagnóstico y deja todo listo para tu primera sesión.
              </p>
            </FadeUp>

            {/* iPad grande, centrado (la imagen ya trae el dispositivo) */}
            <div className="relative mx-auto w-full max-w-[700px]">
              {/* Círculo azul translúcido de fondo */}
              <motion.div
                aria-hidden
                initial={{ opacity: 0, scale: 0.6 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 1.1, ease: EASE }}
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full blur-2xl"
                style={{
                  width: "112%",
                  aspectRatio: "1 / 1",
                  background: "radial-gradient(circle, rgba(21,39,66,0.16) 0%, rgba(21,39,66,0.08) 55%, rgba(21,39,66,0) 75%)",
                }}
              />
              {/* Entrada: sube, escala y se asienta */}
              <motion.div
                initial={{ opacity: 0, y: 70, scale: 0.94, rotate: -1.5 }}
                whileInView={{ opacity: 1, y: 0, scale: 1, rotate: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ duration: 0.95, ease: EASE, delay: 0.12 }}
                className="relative"
              >
                <Image
                  src="/images/todd-ipad5.png"
                  alt="Todd, el Secretario del Consejo de Gobernia, dando la bienvenida y haciendo la primera pregunta del onboarding en un iPad"
                  width={1347}
                  height={1750}
                  className="w-full h-auto drop-shadow-[0_34px_60px_rgba(14,22,38,0.30)]"
                />
              </motion.div>
            </div>

            {/* Bullets en fila bajo el iPad */}
            <FadeUp>
              <ul className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-4xl mx-auto">
                {[
                  "Preguntas una a la vez — sin formularios largos.",
                  "Tu progreso se guarda solo: puedes pausar y volver cuando quieras.",
                  "En 5–10 minutos, tu Consejo ya te conoce.",
                ].map(item => (
                  <li key={item} className="flex items-start gap-3 text-[15px] leading-relaxed" style={{ color: INK2 }}>
                    <span className="mt-[9px] h-1.5 w-1.5 shrink-0" style={{ background: ACCENT }} />
                    {item}
                  </li>
                ))}
              </ul>
            </FadeUp>

          </div>
        </section>

        {/* ── Divider ──────────────────────────────────────── */}
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px" style={{ background: LINE }} /></div>

        {/* ── Para quién ───────────────────────────────────── */}
        <section className="py-16 sm:py-24 3xl:py-32 px-[var(--px-fluid)]" style={{ background: SAND }}>
          <div className="w-full max-w-[var(--container-fluid)] mx-auto space-y-14">
            <FadeUp>
              <Eyebrow className="mb-4">Para quién</Eyebrow>
              <ScrollReveal>
                <h2
                  style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.02, letterSpacing: "-0.03em", maxWidth: "13em" }}
                >
                  <span style={{ opacity: 0.4 }}>Diseñado para </span>
                  <Heavy range={[0.2, 0.7]}>empresas reales.</Heavy>
                </h2>
              </ScrollReveal>
            </FadeUp>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {FOR_WHO.map((c, i) => (
                <FadeUp key={c.title} delay={i * 0.1}>
                  <div className="rounded-[26px] p-[30px] space-y-3 h-full" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                    <h3 className="text-[19px] font-bold leading-tight tracking-[-.02em]" style={{ ...SANS, color: INK }}>{c.title}</h3>
                    <p className="text-[14.5px] leading-relaxed" style={{ color: INK2 }}>{c.desc}</p>
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
                    style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.02, letterSpacing: "-0.03em", maxWidth: "13em" }}
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
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px" style={{ background: LINE }} /></div>

        {/* ── CTA ──────────────────────────────────────────── */}
        <section className="py-20 sm:py-28 3xl:py-36 px-[var(--px-fluid)]">
          <FadeUp className="w-full max-w-[var(--container-fluid)] mx-auto space-y-8">
            <Eyebrow>Empieza hoy</Eyebrow>
            <ScrollReveal>
              <h2
                style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.0, letterSpacing: "-0.03em", maxWidth: "13em" }}
              >
                <span style={{ opacity: 0.4 }}>Tu empresa merece un </span>
                <Heavy range={[0.15, 0.5]}>consejo</Heavy>
                <br />
                <span style={{ opacity: 0.4 }}>que </span>
                <Heavy range={[0.45, 0.85]}>nunca duerme.</Heavy>
              </h2>
            </ScrollReveal>
            <p className="text-[17px] leading-relaxed max-w-xl" style={{ color: INK2 }}>
              Cinco consejeros listos para sesionar sobre tu empresa. Sin consultores, cancela cuando quieras — primer diagnóstico en menos de 30 minutos.
            </p>
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-2.5 rounded-full px-7 py-3.5 text-[14px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
              style={{ ...SANS, background: BNAVY }}
            >
              Comenzar gratis <ArrowRight className="h-4 w-4" />
            </Link>
          </FadeUp>
        </section>

        {/* ── Divider ──────────────────────────────────────── */}
        <div className="w-full max-w-[var(--container-fluid)] mx-auto px-[var(--px-fluid)]"><div className="h-px" style={{ background: LINE }} /></div>

        {/* ── Seguridad y confidencialidad ─────────────────── */}
        <section className="py-20 sm:py-28 3xl:py-36 px-[var(--px-fluid)]">
          <FadeUp className="w-full max-w-[var(--container-fluid)] mx-auto space-y-12">
            <div className="space-y-5 max-w-2xl">
              <Eyebrow>Seguridad y confidencialidad</Eyebrow>
              <ScrollReveal>
                <h2
                  style={{ ...SANS, color: BNAVY, fontWeight: 300, fontSize: "clamp(27px, 3.8vw, 92px)", lineHeight: 1.02, letterSpacing: "-0.03em", maxWidth: "13em" }}
                >
                  <span style={{ opacity: 0.4 }}>Tus datos financieros y estratégicos, </span>
                  <Heavy range={[0.15, 0.55]}>protegidos.</Heavy>
                </h2>
              </ScrollReveal>
              <p className="text-[17px] leading-relaxed" style={{ color: INK2 }}>
                La información que compartes con tu Consejo es sensible. La ciframos y la mantenemos privada.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {SECURITY.map(s => {
                const Icon = s.icon
                return (
                  <div key={s.title} className="rounded-[26px] p-6 space-y-3" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(21,39,66,0.06)", color: BNAVY }}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="text-sm font-bold" style={{ ...SANS, color: INK }}>{s.title}</p>
                    <p className="text-sm leading-relaxed" style={{ color: INK2 }}>{s.desc}</p>
                  </div>
                )
              })}
            </div>
          </FadeUp>
        </section>

        {/* ── Footer ───────────────────────────────────────── */}
        <footer className="px-[var(--px-fluid)] pt-16 pb-8" style={{ background: SAND }}>
          <div className="w-full max-w-[var(--container-fluid)] mx-auto">

            <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pb-14">
              {/* Marca */}
              <div className="md:col-span-5 space-y-5">
                <GoberniaLogo size={30} />
                <p className="text-[14.5px] leading-relaxed" style={{ color: INK2, maxWidth: "26em" }}>
                  La evolución del Consejo de Administración. Cinco consejeros con IA
                  sesionan sobre tu empresa cada mes.
                </p>
                <Link
                  href="/sign-up"
                  className="inline-flex items-center gap-2.5 rounded-full px-5 py-3 text-[13px] font-bold tracking-wide text-white transition-colors hover:brightness-90"
                  style={{ ...SANS, background: BNAVY }}
                >
                  Comenzar gratis <ArrowRight className="h-4 w-4" />
                </Link>
              </div>

              {/* Producto */}
              <div className="md:col-span-2">
                <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em] mb-4" style={{ ...SANS, color: MUTED }}>
                  Producto
                </p>
                <ul className="space-y-2.5 text-sm" style={{ color: INK2 }}>
                  <li><a href="#producto"      className="transition-colors hover:text-[#152742]">Consejeros</a></li>
                  <li><a href="#como-funciona" className="transition-colors hover:text-[#152742]">Cómo funciona</a></li>
                  <li><a href="#faq"           className="transition-colors hover:text-[#152742]">FAQ</a></li>
                </ul>
              </div>

              {/* Cuenta */}
              <div className="md:col-span-2">
                <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em] mb-4" style={{ ...SANS, color: MUTED }}>
                  Cuenta
                </p>
                <ul className="space-y-2.5 text-sm" style={{ color: INK2 }}>
                  <li><Link href="/sign-in" className="transition-colors hover:text-[#152742]">Iniciar sesión</Link></li>
                  <li><Link href="/sign-up" className="transition-colors hover:text-[#152742]">Crear cuenta</Link></li>
                </ul>
              </div>

              {/* Legal */}
              <div className="md:col-span-3">
                <p className="text-[10.5px] font-extrabold uppercase tracking-[0.17em] mb-4" style={{ ...SANS, color: MUTED }}>
                  Legal
                </p>
                <ul className="space-y-2.5 text-sm" style={{ color: INK2 }}>
                  <li><Link href="/legal/privacidad" className="transition-colors hover:text-[#152742]">Aviso de privacidad</Link></li>
                  <li><Link href="/legal/terminos"   className="transition-colors hover:text-[#152742]">Términos y condiciones</Link></li>
                  <li><Link href="/legal/cookies"    className="transition-colors hover:text-[#152742]">Política de cookies</Link></li>
                </ul>
              </div>
            </div>

            {/* Línea final */}
            <div
              className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-6 text-xs"
              style={{ borderTop: "1px solid rgba(14,22,38,0.12)", color: MUTED }}
            >
              <span>© {new Date().getFullYear()} Gobernia. Todos los derechos reservados.</span>
              <span className="inline-flex items-center gap-2">
                <span aria-hidden className="h-1.5 w-1.5" style={{ background: ACCENT }} />
                Tu información está cifrada y protegida.
              </span>
            </div>

          </div>
        </footer>

      </div>
    </div>
  )
}
