"use client"

import { motion } from "framer-motion"

const STEPS = [
  "Empresa",
  "Equipo",
  "Prioridades",
  "Diagnóstico",
  "KPIs",
  "Gobierno",
  "Documentos",
  "Visión",
]

interface ProgressBarProps {
  currentStep: number  // 1-8
}

export default function ProgressBar({ currentStep }: ProgressBarProps) {
  const pct = ((currentStep - 1) / (STEPS.length - 1)) * 100

  return (
    <div className="w-full max-w-xl mx-auto px-4">
      {/* Step label */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">
          Paso {currentStep} de {STEPS.length}
        </span>
        <span className="text-xs font-semibold text-primary">
          {STEPS[currentStep - 1]}
        </span>
      </div>

      {/* Track */}
      <div className="relative h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <motion.div
          className="absolute inset-y-0 left-0 bg-primary rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>

      {/* Step dots */}
      <div className="flex justify-between mt-2">
        {STEPS.map((_, i) => {
          const step = i + 1
          const done = step < currentStep
          const active = step === currentStep
          return (
            <motion.div
              key={step}
              initial={false}
              animate={{
                scale: active ? 1.3 : 1,
                backgroundColor: done || active ? "#000000" : "#E5E7EB",
              }}
              transition={{ duration: 0.25 }}
              className="w-2 h-2 rounded-full"
            />
          )
        })}
      </div>
    </div>
  )
}
