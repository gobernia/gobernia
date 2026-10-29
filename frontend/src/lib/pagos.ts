// Suscripción del cliente con Mercado Pago. Por ahora el cobro es opcional.
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
}

export interface EstadoPagos {
  cobros_activos: boolean
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

/** Devuelve la liga de Mercado Pago donde el cliente captura su tarjeta. */
export async function suscribirme(planId: string, codigo?: string): Promise<string> {
  return (await api.post<{ liga_pago: string }>("/pagos/suscribirme", { plan_id: planId, codigo: codigo || null })).data.liga_pago
}

export async function canjearCupon(codigo: string): Promise<MiSuscripcion> {
  return (await api.post<{ suscripcion: MiSuscripcion }>("/pagos/canjear", { codigo })).data.suscripcion
}

export async function cancelarSuscripcion(): Promise<MiSuscripcion> {
  return (await api.post<{ suscripcion: MiSuscripcion }>("/pagos/cancelar")).data.suscripcion
}

export const INTERVALO: Record<number, string> = { 1: "mensual", 3: "trimestral", 6: "semestral", 12: "anual" }
export const CADA: Record<number, string> = { 1: "al mes", 3: "cada 3 meses", 6: "cada 6 meses", 12: "al año" }

export function pesos(n: number, moneda = "MXN"): string {
  return n.toLocaleString("es-MX", { style: "currency", currency: moneda, maximumFractionDigits: n % 1 ? 2 : 0 })
}
