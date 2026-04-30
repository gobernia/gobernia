"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, Minus, ArrowRight, ArrowUpRight } from "lucide-react"

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
    <div className="border-b border-gray-100">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start justify-between gap-6 py-5 text-left group"
      >
        <span className="text-sm font-medium text-gray-900 group-hover:text-black transition-colors leading-snug">
          {q}
        </span>
        <span className="mt-0.5 flex-shrink-0 text-gray-400 group-hover:text-gray-600 transition-colors">
          {open ? <Minus className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: EASE }}
            className="overflow-hidden"
          >
            <p className="font-display italic text-sm text-gray-500 leading-relaxed pb-5">{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-white text-black font-sans antialiased">

      {/* ── Navbar ───────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-black flex items-center justify-center">
              <span className="text-white text-[11px] font-black tracking-tight">G</span>
            </div>
            <span className="text-sm font-semibold text-black tracking-tight">Gobernia</span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-500">
            <a href="#producto"      className="hover:text-black transition-colors">Producto</a>
            <a href="#como-funciona" className="hover:text-black transition-colors">Cómo funciona</a>
            <a href="#faq"           className="hover:text-black transition-colors">FAQ</a>
          </nav>

          <div className="flex items-center gap-4">
            <Link href="/sign-in" className="text-sm text-gray-500 hover:text-black transition-colors hidden sm:block">
              Iniciar sesión
            </Link>
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-1.5 text-sm font-medium bg-black text-white px-4 py-2 rounded-lg hover:bg-gray-900 transition-colors"
            >
              Empezar <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="pt-36 pb-28 px-6 max-w-5xl mx-auto">
        <motion.div
          variants={heroContainer}
          initial="hidden"
          animate="show"
          className="space-y-8"
        >
          <motion.p variants={heroItem} className="text-xs font-semibold tracking-widest text-gray-400 uppercase">
            Gobierno corporativo · Inteligencia artificial
          </motion.p>

          <motion.h1
            variants={heroItem}
            className="text-5xl sm:text-6xl md:text-7xl font-bold leading-[1.04] tracking-tight text-black max-w-4xl"
          >
            Tu consejo directivo,<br />
            <span className="text-gray-300">siempre disponible.</span>
          </motion.h1>

          <motion.p variants={heroItem} className="font-display italic text-xl text-gray-500 max-w-xl leading-relaxed">
            Cuatro agentes de IA — CFO, CSO, CRO y Auditor — analizan tu empresa cada mes,
            detectan riesgos y proponen estrategias. Sin consultores. Sin esperas.
          </motion.p>

          <motion.div variants={heroItem} className="flex flex-wrap items-center gap-3">
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-2 bg-black text-white font-medium px-6 py-3 rounded-xl hover:bg-gray-900 transition-all duration-200 text-sm"
            >
              Comenzar gratis <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/sign-in"
              className="inline-flex items-center gap-2 text-sm text-gray-500 border border-gray-200 px-6 py-3 rounded-xl hover:border-gray-400 hover:text-black transition-all duration-200"
            >
              Ya tengo cuenta
            </Link>
          </motion.div>

          <motion.p variants={heroItem} className="text-xs text-gray-400">
            Sin tarjeta de crédito · Configuración en menos de 15 minutos
          </motion.p>
        </motion.div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-gray-100" /></div>

      {/* ── Stats ────────────────────────────────────────── */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-10">
          {[
            { n: "4",    label: "Agentes especializados" },
            { n: "8",    label: "Etapas de diagnóstico" },
            { n: "100%", label: "Cifrado y confidencial" },
            { n: "15′",  label: "Para tu primer análisis" },
          ].map((s, i) => (
            <FadeUp key={s.label} delay={i * 0.08}>
              <p className="text-4xl font-bold text-black tracking-tight">{s.n}</p>
              <p className="font-display italic text-xs text-gray-400 mt-2 leading-snug">{s.label}</p>
            </FadeUp>
          ))}
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-gray-100" /></div>

      {/* ── Agents ───────────────────────────────────────── */}
      <section id="producto" className="py-24 px-6">
        <div className="max-w-5xl mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-4">El equipo</p>
            <h2 className="text-4xl md:text-5xl font-bold text-black leading-tight tracking-tight max-w-2xl">
              Cuatro expertos de IA en tu mesa directiva.
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {AGENTS.map((a, i) => (
              <FadeUp key={a.id} delay={i * 0.09}>
                <div className="group h-full border border-gray-100 hover:border-gray-300 rounded-2xl p-7 space-y-4 transition-all duration-300 hover:shadow-sm">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-lg font-bold text-black">{a.id}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{a.role}</p>
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-gray-300 group-hover:text-gray-500 transition-colors mt-1" />
                  </div>
                  <p className="font-display italic text-sm text-gray-500 leading-relaxed">{a.desc}</p>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-gray-100" /></div>

      {/* ── Cómo funciona ────────────────────────────────── */}
      <section id="como-funciona" className="py-24 px-6">
        <div className="max-w-5xl mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-4">El proceso</p>
            <h2 className="text-4xl md:text-5xl font-bold text-black tracking-tight max-w-xl leading-tight">
              De cero a tu primer diagnóstico en tres pasos.
            </h2>
          </FadeUp>

          <div className="space-y-0 divide-y divide-gray-100">
            {STEPS.map((s, i) => (
              <FadeUp key={s.n} delay={i * 0.1}>
                <div className="py-8 flex gap-8 items-start">
                  <span className="text-sm font-mono text-gray-300 flex-shrink-0 pt-0.5 w-8">{s.n}</span>
                  <div className="space-y-1.5">
                    <h3 className="text-base font-semibold text-black">{s.title}</h3>
                    <p className="font-display italic text-sm text-gray-500 leading-relaxed max-w-lg">{s.desc}</p>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-gray-100" /></div>

      {/* ── Para quién ───────────────────────────────────── */}
      <section className="py-24 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto space-y-14">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-4">Para quién</p>
            <h2 className="text-4xl md:text-5xl font-bold text-black tracking-tight leading-tight max-w-2xl">
              Diseñado para empresas reales.
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {FOR_WHO.map((c, i) => (
              <FadeUp key={c.title} delay={i * 0.1}>
                <div className="bg-white border border-gray-100 rounded-2xl p-7 space-y-3 h-full">
                  <h3 className="font-semibold text-black text-sm">{c.title}</h3>
                  <p className="font-display italic text-sm text-gray-500 leading-relaxed">{c.desc}</p>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────── */}
      <section id="faq" className="py-24 px-6">
        <div className="max-w-3xl mx-auto space-y-12">
          <FadeUp>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-4">FAQ</p>
            <h2 className="text-4xl md:text-5xl font-bold text-black tracking-tight leading-tight">
              Preguntas frecuentes.
            </h2>
          </FadeUp>

          <FadeUp delay={0.1}>
            <div>
              {FAQS.map(f => <FAQItem key={f.q} q={f.q} a={f.a} />)}
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── Divider ──────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6"><div className="h-px bg-gray-100" /></div>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="py-28 px-6">
        <FadeUp className="max-w-4xl mx-auto space-y-8">
          <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase">Empieza hoy</p>
          <h2 className="text-5xl md:text-6xl font-bold text-black leading-tight tracking-tight">
            Tu empresa merece un consejo<br />
            <span className="text-gray-300">que nunca duerme.</span>
          </h2>
          <p className="font-display italic text-xl text-gray-500 max-w-xl leading-relaxed">
            Sin consultores. Sin contratos. Primer diagnóstico en menos de 15 minutos.
          </p>
          <Link
            href="/sign-up"
            className="inline-flex items-center gap-2 bg-black text-white font-semibold px-8 py-4 rounded-xl hover:bg-gray-900 transition-all duration-200 text-base"
          >
            Comenzar gratis <ArrowRight className="h-4 w-4" />
          </Link>
        </FadeUp>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-black flex items-center justify-center">
              <span className="text-white text-[9px] font-black">G</span>
            </div>
            <span>Gobernia © {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/sign-in"  className="hover:text-black transition-colors">Iniciar sesión</Link>
            <Link href="/sign-up"  className="hover:text-black transition-colors">Registro</Link>
            <span>Tu información está cifrada y protegida.</span>
          </div>
        </div>
      </footer>

    </div>
  )
}
