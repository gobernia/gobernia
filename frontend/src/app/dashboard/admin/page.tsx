"use client"

// SUPER ADMIN — quién se registró, en qué etapa va cada cliente y cuánta actividad hay.
// Solo lectura. El servidor rechaza a cualquiera que no esté en SUPERADMIN_EMAILS.

import { useEffect, useMemo, useState, type CSSProperties } from "react"
import { Loader2, Search, ShieldAlert, CreditCard } from "lucide-react"
import { PageShell, PageHeader } from "@/components/ui/PageShell"
import { getAdminResumen, type AdminResumen, type AdminUsuario } from "@/lib/admin"

const INK   = "#0E1626"
const INK2  = "#39435A"
const MUTED = "#6E7686"
const CARD  = "#FFFFFF"
const SAND  = "#E8E3D8"
const BNAVY = "#152742"
const ACCENT = "#C2410C"
const LINE  = "#E2E2DC"
const SANS: CSSProperties = { fontFamily: "var(--font-sans)" }

const PERIODICIDAD: Record<string, string> = { mensual: "Mensual", trimestral: "Trimestral", semestral: "Semestral" }

function fecha(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" })
}

function hace(iso: string | null): string {
  if (!iso) return "Nunca"
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (dias <= 0) return "Hoy"
  if (dias === 1) return "Ayer"
  if (dias < 30) return `Hace ${dias} días`
  return fecha(iso)
}

function Metrica({ label, valor, sub }: { label: string; valor: number | string; sub?: string }) {
  return (
    <div className="rounded-[26px] p-5" style={{ background: CARD, border: `1px solid ${LINE}` }}>
      <p className="text-[10px] font-extrabold uppercase tracking-[0.16em]" style={{ ...SANS, color: MUTED }}>{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums" style={{ ...SANS, color: INK }}>{valor}</p>
      {sub && <p className="mt-1 text-xs" style={{ color: MUTED }}>{sub}</p>}
    </div>
  )
}

export default function AdminPage() {
  const [data, setData] = useState<AdminResumen | null>(null)
  const [estado, setEstado] = useState<"cargando" | "listo" | "prohibido" | "error">("cargando")
  const [q, setQ] = useState("")
  const [etapa, setEtapa] = useState("")

  useEffect(() => {
    getAdminResumen()
      .then(d => { setData(d); setEstado("listo") })
      .catch((e: unknown) => {
        const st = (e as { response?: { status?: number } })?.response?.status
        setEstado(st === 403 ? "prohibido" : "error")
      })
  }, [])

  const etiquetaEtapa = useMemo(
    () => Object.fromEntries((data?.etapas ?? []).map(e => [e.etapa, e.label])) as Record<string, string>,
    [data],
  )

  const usuarios = useMemo(() => {
    const t = q.trim().toLowerCase()
    return (data?.usuarios ?? []).filter((u: AdminUsuario) =>
      (!etapa || u.etapa === etapa) &&
      (!t || u.email.toLowerCase().includes(t) || (u.empresa ?? "").toLowerCase().includes(t)))
  }, [data, q, etapa])

  const max = Math.max(1, ...(data?.embudo ?? []).map(e => e.usuarios))

  return (
    <div className="min-h-dvh font-sans antialiased" style={{ background: "#F2F2F0", color: INK }}>
      <PageHeader eyebrow="Super admin" title="Panel de Gobernia" />

      <main>
        <PageShell className="py-10 space-y-10">
          {estado === "cargando" && (
            <div className="flex items-center justify-center py-24"><Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} /></div>
          )}
          {estado === "prohibido" && (
            <div className="rounded-[26px] p-10 text-center space-y-2" style={{ background: CARD, border: `1px solid ${LINE}` }}>
              <ShieldAlert className="mx-auto h-6 w-6" style={{ color: ACCENT }} />
              <p className="font-bold" style={{ ...SANS, color: INK }}>Esta página es solo para el super admin.</p>
            </div>
          )}
          {estado === "error" && (
            <p className="text-sm" style={{ color: MUTED }}>No se pudo cargar el panel. Intenta de nuevo.</p>
          )}

          {data && (
            <>
              {/* Métricas */}
              <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Metrica label="Usuarios registrados" valor={data.usuarios_total}
                  sub={`${data.nuevos_7d} esta semana · ${data.nuevos_30d} en 30 días`} />
                <Metrica label="Activos" valor={data.activos_30d}
                  sub={`entraron en 30 días · ${data.activos_7d} esta semana`} />
                <Metrica label="Con plan activo" valor={data.con_plan} sub="plan estratégico generado" />
                <Metrica label="Sesiones de Consejo" valor={data.sesiones_total} sub="convocadas por los clientes" />
              </section>

              {/* Embudo + cobros */}
              <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 rounded-[26px] p-6 space-y-4" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                  <div>
                    <h2 className="text-lg font-bold" style={{ ...SANS, color: INK }}>Recorrido de los clientes</h2>
                    <p className="text-xs mt-0.5" style={{ color: MUTED }}>Cuántos llegaron al menos a cada etapa</p>
                  </div>
                  <ul className="space-y-2.5">
                    {data.embudo.map(e => (
                      <li key={e.etapa}>
                        <button type="button" onClick={() => setEtapa(etapa === e.etapa ? "" : e.etapa)}
                          className="w-full text-left group" aria-pressed={etapa === e.etapa}>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="font-medium" style={{ color: etapa === e.etapa ? ACCENT : INK2 }}>{e.label}</span>
                            <span className="font-bold tabular-nums" style={{ color: INK }}>{e.usuarios}</span>
                          </div>
                          <div className="h-2.5 rounded-full" style={{ background: SAND }}>
                            <div className="h-2.5 rounded-full transition-all"
                              style={{ width: `${(e.usuarios / max) * 100}%`, background: etapa === e.etapa ? ACCENT : BNAVY }} />
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-[26px] p-6 flex flex-col gap-3" style={{ background: BNAVY, color: CARD }}>
                  <CreditCard className="h-5 w-5" style={{ color: "rgba(255,255,255,.7)" }} />
                  <h2 className="text-lg font-bold" style={SANS}>Suscripciones y pagos</h2>
                  <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,.72)" }}>
                    Todavía no hay cobros: todos los usuarios usan la plataforma sin pago. Cuando se
                    conecte la pasarela (Stripe, Mercado Pago…) aquí verás suscritos, ventas y pagos.
                  </p>
                </div>
              </section>

              {/* Usuarios */}
              <section className="space-y-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold" style={{ ...SANS, color: INK }}>Usuarios</h2>
                    <p className="text-xs mt-0.5" style={{ color: MUTED }}>
                      {usuarios.length} de {data.usuarios.length}
                      {etapa && <> · etapa: <strong>{etiquetaEtapa[etapa]}</strong>{" "}
                        <button type="button" className="underline" onClick={() => setEtapa("")}>quitar filtro</button></>}
                    </p>
                  </div>
                  <label className="flex items-center gap-2 rounded-[14px] px-3 py-2 w-full sm:w-72"
                    style={{ background: CARD, border: `1px solid ${LINE}` }}>
                    <Search className="h-4 w-4 shrink-0" style={{ color: MUTED }} />
                    <input value={q} onChange={e => setQ(e.target.value)} placeholder="Buscar correo o empresa"
                      className="w-full bg-transparent text-sm outline-none" style={{ color: INK }} />
                  </label>
                </div>

                <div className="overflow-x-auto rounded-[26px]" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                  <table className="w-full min-w-[980px] text-sm">
                    <thead>
                      <tr style={{ background: SAND }}>
                        {["Usuario", "Etapa", "Registro", "Último acceso", "Tareas", "Sesiones", "Documentos", "Periodicidad"].map(h => (
                          <th key={h} className="px-4 py-2.5 text-left text-[10px] font-extrabold uppercase tracking-[0.12em]"
                            style={{ ...SANS, color: MUTED }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {usuarios.map(u => (
                        <tr key={u.id} style={{ borderTop: `1px solid ${LINE}` }}>
                          <td className="px-4 py-3">
                            <p className="font-semibold" style={{ color: INK }}>{u.empresa ?? "Sin empresa aún"}</p>
                            <p className="text-xs" style={{ color: MUTED }}>{u.email}</p>
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
                              style={{ background: `${BNAVY}10`, color: BNAVY }}>{etiquetaEtapa[u.etapa] ?? u.etapa}</span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap" style={{ color: INK2 }}>{fecha(u.registrado)}</td>
                          <td className="px-4 py-3 whitespace-nowrap" style={{ color: INK2 }}>{hace(u.ultimo_acceso)}</td>
                          <td className="px-4 py-3 tabular-nums whitespace-nowrap" style={{ color: INK2 }}>
                            {u.tareas_total ? `${u.tareas_completadas} / ${u.tareas_total}` : "—"}
                          </td>
                          <td className="px-4 py-3 tabular-nums" style={{ color: INK2 }}>
                            {u.sesiones || "—"}
                            {u.ultima_sesion && <span className="block text-[11px]" style={{ color: MUTED }}>{hace(u.ultima_sesion)}</span>}
                          </td>
                          <td className="px-4 py-3 tabular-nums" style={{ color: INK2 }}>{u.documentos || "—"}</td>
                          <td className="px-4 py-3" style={{ color: INK2 }}>{u.periodicidad ? PERIODICIDAD[u.periodicidad] ?? u.periodicidad : "—"}</td>
                        </tr>
                      ))}
                      {usuarios.length === 0 && (
                        <tr><td colSpan={8} className="px-4 py-10 text-center text-sm" style={{ color: MUTED }}>Sin resultados.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </PageShell>
      </main>
    </div>
  )
}
