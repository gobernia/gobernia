"use client"

import { motion, AnimatePresence } from "framer-motion"
import { ReactNode } from "react"

interface StepWrapperProps {
  stepKey: string
  children: ReactNode
}

export default function StepWrapper({ stepKey, children }: StepWrapperProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={stepKey}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -16 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="w-full"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
