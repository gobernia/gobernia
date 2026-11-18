// Suscripción del cliente con Stripe. Por ahora el cobro es opcional.
import api from "@/lib/api"
import type { EstadoSuscripcion, Plan, TipoCupon } from "@/lib/admin"

export interface MiSuscripcion {
  id: string
  estado: EstadoSuscripcion
  plan: string | null
  monto: number
  monto_regular: number
  moneda: string
  intervalo_meses: number
  cobros_con_descuento: number | null
  proximo_cobro: string | null
  vence: string | null
  liga_pago: string | null
  /** Ya tiene cliente en Stripe: puede abrir el portal (tarjeta y facturas). */
  puede_administrar: boolean
}

export interface EstadoPagos {
  cobros_activos: boolean
  /** Con Stripe conectado: prueba (sk_test_) o produccion. Los clientes solo ven la suscripción en produccion. */
  modo: "prueba" | "produccion" | null
  planes: Plan[]
  suscripcion: MiSuscripcion | null
}

export interface CuponRevisado {
  codigo: string
  tipo: TipoCupon
  resumen: string
  precio?: number
  precio_final?: number
}

export async function getPagos(): Promise<EstadoPagos> {
  return (await api.get<EstadoPagos>("/pagos")).data
}

export async function revisarCupon(codigo: string, planId?: string): Promise<CuponRevisado> {
  return (await api.post<CuponRevisado>("/pagos/cupon", { codigo, plan_id: planId ?? null })).data
}

/** Cómo se paga: dentro de gobernia.ai (Checkout incrustado de Stripe) o en la página de Stripe. */
export type InicioPago =
  | { modo: "incrustado"; client_secret: string; clave_publica: string }
  | { modo: "liga"; liga_pago: string }

/** Abre el pago. Pide el incrustado; el servidor regresa a la liga si no hay clave publicable. */
export async function suscribirme(planId: string, codigo?: string): Promise<InicioPago> {
  return (await api.post<InicioPago>("/pagos/suscribirme", { plan_id: planId, codigo: codigo || null, incrustado: true })).data
}

/** Lo que la página de agradecimiento sabe de la compra (confirmada con Stripe). */
export interface ConfirmacionPago {
  pagado: boolean
  estado: EstadoSuscripcion
  plan: string | null
  /** Lo cobrado en este pago (con descuento si hubo cupón). */
  monto: number
  moneda: string
  intervalo_meses: number
  /** Id de la sesión de pago: identificador único de la compra para la analítica. */
  transaccion: string
}

export async function confirmarPago(sessionId: string): Promise<ConfirmacionPago> {
  return (await api.get<ConfirmacionPago>("/pagos/confirmacion", { params: { session_id: sessionId } })).data
}

export async function canjearCupon(codigo: string): Promise<MiSuscripcion> {
  return (await api.post<{ suscripcion: MiSuscripcion }>("/pagos/canjear", { codigo })).data.suscripcion
}

export async function cancelarSuscripcion(): Promise<MiSuscripcion> {
  return (await api.post<{ suscripcion: MiSuscripcion }>("/pagos/cancelar")).data.suscripcion
}

/** Liga al portal de Stripe: cambiar la tarjeta y ver facturas. */
export async function abrirPortal(): Promise<string> {
  return (await api.post<{ url: string }>("/pagos/portal")).data.url
}

export const INTERVALO: Record<number, string> = { 1: "mensual", 3: "trimestral", 6: "semestral", 12: "anual" }
export const CADA: Record<number, string> = { 1: "al mes", 3: "cada 3 meses", 6: "cada 6 meses", 12: "al año" }

export function pesos(n: number, moneda = "MXN"): string {
  return n.toLocaleString("es-MX", { style: "currency", currency: moneda, maximumFractionDigits: n % 1 ? 2 : 0 })
}
