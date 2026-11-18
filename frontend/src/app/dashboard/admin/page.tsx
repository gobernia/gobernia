"use client"

// SUPER ADMIN — quién se registró, en qué etapa va cada cliente, cuánta actividad hay,
// y los cobros: planes con precio, cupones, suscripciones y pagos de Stripe.
// El servidor rechaza a cualquiera que no esté en SUPERADMIN_EMAILS.

import { useCallback, useEffect, useMemo, useState } from "react"
import { Loader2, Search, ShieldAlert, CreditCard, Download, ChevronLeft, ChevronRight } from "lucide-react"
import { PageShell, PageHeader } from "@/components/ui/PageShell"
import { getAdminCobros, getAdminResumen, type AdminCobros, type AdminResumen, type AdminUsuario } from "@/lib/admin"
import { pesos } from "@/lib/pagos"
import { B, Etiqueta, fecha, Metrica, SANS } from "@/components/admin/ui"
import CobrosAdmin from "@/components/admin/CobrosAdmin"
import CuponesAdmin from "@/components/admin/CuponesAdmin"

const { INK, INK2, MUTED, CARD, SAND, BNAVY, ACCENT, LINE } = B

const PERIODICIDAD: Record<string, string> = { mensual: "Mensual", trimestral: "Trimestral", semestral: "Semestral" }

const POR_PAGINA = 15

/** Números de página a mostrar: primera, última y las vecinas de la actual; null = "…". */
function paginasVisibles(actual: number, total: number): (number | null)[] {
  const n = new Set([1, total, actual - 1, actual, actual + 1].filter(p => p >= 1 && p <= total))
  const orden = [...n].sort((a, b) => a - b)
  return orden.flatMap((p, i) => (i > 0 && p - orden[i - 1] > 1 ? [null, p] : [p]))
}

const PAGO: Record<AdminUsuario["pago"], [string, "verde" | "ambar" | "navy" | "gris"]> = {
  activa: ["Suscrito", "verde"],
  pausada: ["Pausada", "ambar"],
  cortesia: ["Cortesía", "navy"],
  gratis: ["Gratis", "gris"],
}

type Pestana = "usuarios" | "cobros" | "cupones"
const PESTANAS: [Pestana, string][] = [["usuarios", "Usuarios"], ["cobros", "Cobros y planes"], ["cupones", "Cupones"]]

function hace(iso: string | null): string {
  if (!iso) return "Nunca"
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (dias <= 0) return "Hoy"
  if (dias === 1) return "Ayer"
  if (dias < 30) return `Hace ${dias} días`
  return fecha(iso)
}

/** CSV con BOM (Excel abre bien los acentos) de los usuarios visibles. */
function descargarCsv(usuarios: AdminUsuario[], etiquetaEtapa: Record<string, string>) {
  const cols: [string, (u: AdminUsuario) => string | number][] = [
    ["Correo", u => u.email],
    ["Empresa", u => u.empresa ?? ""],
    ["Industria", u => u.industria ?? ""],
    ["Etapa", u => etiquetaEtapa[u.etapa] ?? u.etapa],
    ["Pago", u => PAGO[u.pago]?.[0] ?? u.pago],
    ["Fecha de registro", u => u.registrado?.slice(0, 10) ?? ""],
    ["Último acceso", u => u.ultimo_acceso?.slice(0, 10) ?? ""],
    ["Periodicidad", u => (u.periodicidad && PERIODICIDAD[u.periodicidad]) ?? ""],
    ["Tareas completadas", u => u.tareas_completadas],
    ["Tareas totales", u => u.tareas_total],
    ["Sesiones", u => u.sesiones],
    ["Última sesión", u => u.ultima_sesion?.slice(0, 10) ?? ""],
    ["Documentos", u => u.documentos],
  ]
  const celda = (v: string | number) => {
    const t = String(v)
    return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t
  }
  const lineas = [cols.map(([h]) => celda(h)).join(","),
    ...usuarios.map(u => cols.map(([, f]) => celda(f(u))).join(","))]
  const blob = new Blob(["\uFEFF" + lineas.join("\r\n")], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `usuarios-gobernia-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function AdminPage() {
  const [data, setData] = useState<AdminResumen | null>(null)
  const [estado, setEstado] = useState<"cargando" | "listo" | "prohibido" | "error">("cargando")
  const [q, setQ] = useState("")
  const [etapa, setEtapa] = useState("")
  const [pagina, setPagina] = useState(1)
  const [pestana, setPestana] = useState<Pestana>("usuarios")

  // Cambiar la búsqueda o el filtro regresa a la primera página.
  const buscar = (v: string) => { setQ(v); setPagina(1) }
  const filtrarEtapa = (v: string) => { setEtapa(v); setPagina(1) }
  // Cobros se carga aparte: si falla, la pestaña de usuarios sigue funcionando.
  const [cobros, setCobros] = useState<AdminCobros | null>(null)
  const [errorCobros, setErrorCobros] = useState(false)

  const recargarCobros = useCallback(async () => {
    try {
      setCobros(await getAdminCobros())
      setErrorCobros(false)
    } catch {
      setErrorCobros(true)
    }
  }, [])

  useEffect(() => {
    getAdminResumen()
      .then(d => { setData(d); setEstado("listo"); recargarCobros() })
      .catch((e: unknown) => {
        const st = (e as { response?: { status?: number } })?.response?.status
        setEstado(st === 403 ? "prohibido" : "error")
      })
  }, [recargarCobros])

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

  const totalPaginas = Math.max(1, Math.ceil(usuarios.length / POR_PAGINA))
  const actual = Math.min(pagina, totalPaginas)
  const desde = (actual - 1) * POR_PAGINA
  const visibles = usuarios.slice(desde, desde + POR_PAGINA)

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
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Secciones del panel">
              {PESTANAS.map(([k, label]) => (
                <button key={k} type="button" role="tab" aria-selected={pestana === k} onClick={() => setPestana(k)}
                  className="rounded-full px-4 py-2 text-sm font-bold transition"
                  style={{ ...SANS, background: pestana === k ? BNAVY : CARD, color: pestana === k ? CARD : INK2,
                    border: `1px solid ${pestana === k ? BNAVY : LINE}` }}>
                  {label}
                </button>
              ))}
            </div>
          )}

          {data && pestana !== "usuarios" && !cobros && (
            errorCobros
              ? <p className="text-sm" style={{ color: MUTED }}>No se pudieron cargar los cobros. Intenta de nuevo.</p>
              : <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" style={{ color: MUTED }} /></div>
          )}
          {data && pestana === "cobros" && cobros && <CobrosAdmin data={cobros} recargar={recargarCobros} />}
          {data && pestana === "cupones" && cobros && <CuponesAdmin cupones={cobros.cupones} recargar={recargarCobros} />}

          {data && pestana === "usuarios" && (
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
                        <button type="button" onClick={() => filtrarEtapa(etapa === e.etapa ? "" : e.etapa)}
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
                  {cobros?.configurado ? (
                    <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,.72)" }}>
                      <strong className="text-white">{cobros.metricas.suscriptores_activos}</strong> suscritos ·{" "}
                      <strong className="text-white">{pesos(cobros.metricas.ingreso_mensual)}</strong> al mes ·{" "}
                      {pesos(cobros.metricas.cobrado_30d)} cobrados en 30 días
                      {cobros.modo === "prueba" && " (modo de prueba)"}.
                    </p>
                  ) : (
                    <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,.72)" }}>
                      Todos usan la plataforma sin pago por ahora. Los planes y cupones ya se pueden
                      crear; falta conectar Stripe para cobrar.
                    </p>
                  )}
                  <button type="button" onClick={() => setPestana("cobros")}
                    className="mt-auto self-start text-xs font-bold underline">Ver cobros, planes y cupones</button>
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
                        <button type="button" className="underline" onClick={() => filtrarEtapa("")}>quitar filtro</button></>}
                    </p>
                  </div>
                  <div className="flex w-full sm:w-auto flex-wrap items-center gap-2">
                    <label className="flex items-center gap-2 rounded-[14px] px-3 py-2 flex-1 sm:w-72 sm:flex-none"
                      style={{ background: CARD, border: `1px solid ${LINE}` }}>
                      <Search className="h-4 w-4 shrink-0" style={{ color: MUTED }} />
                      <input value={q} onChange={e => buscar(e.target.value)} placeholder="Buscar correo o empresa"
                        className="w-full bg-transparent text-sm outline-none" style={{ color: INK }} />
                    </label>
                    <button type="button" onClick={() => descargarCsv(usuarios, etiquetaEtapa)}
                      disabled={usuarios.length === 0}
                      className="inline-flex items-center gap-2 rounded-[14px] px-4 py-2 text-sm font-bold text-white transition-colors hover:brightness-90 disabled:opacity-50"
                      style={{ ...SANS, background: BNAVY }}>
                      <Download className="h-4 w-4" /> Descargar CSV
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-[26px]" style={{ background: CARD, border: `1px solid ${LINE}` }}>
                  <table className="w-full min-w-[1060px] text-sm">
                    <thead>
                      <tr style={{ background: SAND }}>
                        {["Usuario", "Etapa", "Pago", "Registro", "Último acceso", "Tareas", "Sesiones", "Documentos", "Periodicidad"].map(h => (
                          <th key={h} className="px-4 py-2.5 text-left text-[10px] font-extrabold uppercase tracking-[0.12em]"
                            style={{ ...SANS, color: MUTED }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibles.map(u => (
                        <tr key={u.id} style={{ borderTop: `1px solid ${LINE}` }}>
                          <td className="px-4 py-3">
                            <p className="font-semibold" style={{ color: INK }}>{u.empresa ?? "Sin empresa aún"}</p>
                            <p className="text-xs" style={{ color: MUTED }}>{u.email}</p>
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
                              style={{ background: `${BNAVY}10`, color: BNAVY }}>{etiquetaEtapa[u.etapa] ?? u.etapa}</span>
                          </td>
                          <td className="px-4 py-3">
                            <Etiqueta tono={PAGO[u.pago]?.[1] ?? "gris"}>{PAGO[u.pago]?.[0] ?? u.pago}</Etiqueta>
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
                        <tr><td colSpan={9} className="px-4 py-10 text-center text-sm" style={{ color: MUTED }}>Sin resultados.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {totalPaginas > 1 && (
                  <nav aria-label="Páginas de usuarios" className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs tabular-nums" style={{ color: MUTED }}>
                      {desde + 1}–{desde + visibles.length} de {usuarios.length}
                    </p>
                    <div className="flex items-center gap-1.5">
                      <button type="button" onClick={() => setPagina(actual - 1)} disabled={actual === 1}
                        aria-label="Página anterior"
                        className="grid h-9 w-9 place-items-center rounded-[12px] transition-colors hover:brightness-95 disabled:opacity-40"
                        style={{ background: CARD, border: `1px solid ${LINE}`, color: INK }}>
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      {paginasVisibles(actual, totalPaginas).map((p, i) => p === null ? (
                        <span key={`hueco-${i}`} className="px-1 text-sm" style={{ color: MUTED }}>…</span>
                      ) : (
                        <button key={p} type="button" onClick={() => setPagina(p)}
                          aria-current={p === actual ? "page" : undefined}
                          className="h-9 min-w-9 rounded-[12px] px-2.5 text-sm font-bold tabular-nums transition-colors hover:brightness-95"
                          style={p === actual
                            ? { ...SANS, background: BNAVY, color: CARD, border: `1px solid ${BNAVY}` }
                            : { ...SANS, background: CARD, color: INK, border: `1px solid ${LINE}` }}>
                          {p}
                        </button>
                      ))}
                      <button type="button" onClick={() => setPagina(actual + 1)} disabled={actual === totalPaginas}
                        aria-label="Página siguiente"
                        className="grid h-9 w-9 place-items-center rounded-[12px] transition-colors hover:brightness-95 disabled:opacity-40"
                        style={{ background: CARD, border: `1px solid ${LINE}`, color: INK }}>
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </nav>
                )}
              </section>
            </>
          )}
        </PageShell>
      </main>
    </div>
  )
}
