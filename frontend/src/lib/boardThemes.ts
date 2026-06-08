import api from "@/lib/api"

export type ThemeType = "permanente" | "cobertura" | "emergente"

export interface BoardTheme {
  id: string
  key: string
  label: string
  type: ThemeType
  every_n_sessions: number | null
  active: boolean
  is_default: boolean
  order_index: number
}

export const FREQ_LABEL: Record<number, string> = {
  1: "cada sesión",
  2: "bimestral",
  3: "trimestral",
  6: "semestral",
  12: "anual",
}

export async function getThemes(): Promise<BoardTheme[]> {
  const r = await api.get<BoardTheme[]>("/annual-plan/themes")
  return r.data
}

export async function createTheme(body: {
  label: string
  type: ThemeType
  every_n_sessions: number | null
}): Promise<BoardTheme> {
  const r = await api.post<BoardTheme>("/annual-plan/themes", body)
  return r.data
}

export async function updateTheme(
  id: string,
  patch: Partial<Pick<BoardTheme, "label" | "every_n_sessions" | "active" | "order_index">>,
): Promise<BoardTheme> {
  const r = await api.patch<BoardTheme>(`/annual-plan/themes/${id}`, patch)
  return r.data
}

export async function deleteTheme(id: string): Promise<void> {
  await api.delete(`/annual-plan/themes/${id}`)
}
