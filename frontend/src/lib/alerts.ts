import api from "@/lib/api"

export type AlertLevel = "critical" | "warning" | "info"

export interface AlertItem {
  level: AlertLevel
  category: string
  message: string
}

export async function getAlertas(): Promise<AlertItem[]> {
  const r = await api.get<AlertItem[]>("/annual-plan/alertas")
  return r.data
}
