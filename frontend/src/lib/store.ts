import { create } from "zustand"
import { persist } from "zustand/middleware"

interface OnboardingState {
  sessionId: string | null
  token: string | null
  completedStages: number[]
  setSessionId: (id: string) => void
  setToken: (token: string) => void
  markStageComplete: (stage: number) => void
  reset: () => void
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    set => ({
      sessionId: null,
      token: null,
      completedStages: [],
      setSessionId: id => set({ sessionId: id }),
      setToken: token => set({ token }),
      markStageComplete: stage =>
        set(s => ({
          completedStages: s.completedStages.includes(stage)
            ? s.completedStages
            : [...s.completedStages, stage],
        })),
      reset: () => set({ sessionId: null, token: null, completedStages: [] }),
    }),
    { name: "gobernia-onboarding" }
  )
)
