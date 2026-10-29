// Panel de super admin: usuarios, cobros, planes y cupones. Acceso restringido en el servidor.
import api from "@/lib/api"

export interface AdminUsuario {
  id: string
  email: string
  registrado: string
  ultimo_acceso: string | null
  empresa: string | null
  industria: string | null
  etapa: string
  plan_estado: string | null
  periodicidad: string | null
  sesiones: number
  ultima_sesion: string | null
  tareas_total: number
  tareas_completadas: number
  documentos: number
  pago: "activa" | "pausada" | "cortesia" | "gratis"
}

export interface AdminResumen {
  usuarios_total: number
  nuevos_7d: number
  nuevos_30d: number
  activos_7d: number
  activos_30d: number
  sesiones_total: number
  con_plan: number
  embudo: { etapa: string; label: string; usuarios: number }[]
  etapas: { etapa: string; label: string }[]
  usuarios: AdminUsuario[]
  cobros_activos: boolean
}

export async function esAdmin(): Promise<boolean> {
  try {
    const r = await api.get<{ es_admin: boolean }>("/admin/me")
    return !!r.data?.es_admin
  } catch {
    return false
  }
}

export async function getAdminResumen(): Promise<AdminResumen> {
  const r = await api.get<AdminResumen>("/admin/resumen")
  return r.data
}

// ── Cobros (Mercado Pago), planes y cupones ──────────────────────────────────

export type Intervalo = 1 | 3 | 6 | 12

export interface Plan {
  id: string
  nombre: string
  descripcion: string | null
  precio: number
  moneda: string
  intervalo_meses: Intervalo
  activo: boolean
}

export type TipoCupon = "porcentaje" | "monto" | "meses_gratis"

export interface Cupon {
  id: string
  codigo: string
  descripcion: string | null
  tipo: TipoCupon
  valor: number
  num_cobros: number | null
  vigente_hasta: string | null
  max_usos: number | null
  usos: number
  activo: boolean
  resumen: string
  creado: string | null
}

export type EstadoSuscripcion = "pendiente" | "activa" | "pausada" | "cancelada" | "cortesia"

export interface SuscripcionAdmin {
  id: string
  estado: EstadoSuscripcion
  plan: string | null
  email: string
  empresa: string | null
  monto: number
  monto_regular: number
  moneda: string
  intervalo_meses: number
  cobros_con_descuento: number | null
  proximo_cobro: string | null
  vence: string | null
  creada: string | null
}

export interface PagoAdmin {
  id: string
  email: string | null
  empresa: string | null
  monto: number
  moneda: string
  estado: string
  fecha: string | null
}

export interface AdminCobros {
  configurado: boolean
  modo: "prueba" | "produccion" | null
  webhook_firmado: boolean
  url_webhook: string
  metricas: {
    suscriptores_activos: number
    cortesias_vigentes: number
    ingreso_mensual: number
    cobrado_30d: number
    cobrado_total: number
  }
  planes: Plan[]
  cupones: Cupon[]
  suscripciones: SuscripcionAdmin[]
  pagos: PagoAdmin[]
}

export type PlanIn = Omit<Plan, "id" | "moneda">
export interface CuponIn {
  codigo: string
  descripcion: string | null
  tipo: TipoCupon
  valor: number
  num_cobros: number | null
  vigente_hasta: string | null
  max_usos: number | null
}

export async function getAdminCobros(): Promise<AdminCobros> {
  return (await api.get<AdminCobros>("/admin/cobros")).data
}

export async function crearPlan(body: PlanIn): Promise<Plan> {
  return (await api.post<Plan>("/admin/planes", body)).data
}

export async function editarPlan(id: string, body: Partial<PlanIn>): Promise<Plan> {
  return (await api.patch<Plan>(`/admin/planes/${id}`, body)).data
}

export async function crearCupon(body: CuponIn): Promise<Cupon> {
  return (await api.post<Cupon>("/admin/cupones", body)).data
}

export async function editarCupon(
  id: string, body: Partial<Pick<Cupon, "descripcion" | "vigente_hasta" | "max_usos" | "activo">>,
): Promise<Cupon> {
  return (await api.patch<Cupon>(`/admin/cupones/${id}`, body)).data
}

/** Mensaje del servidor (detail) o uno genérico. */
export function mensajeError(e: unknown, porDefecto = "No se pudo guardar. Intenta de nuevo."): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "")
  return porDefecto
}
