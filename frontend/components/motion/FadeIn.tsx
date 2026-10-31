"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

/** Fade + slide up on mount (or, with `inView`, when scrolled into view once). Plain element under prefers-reduced-motion. */
export function FadeIn({
  children,
  delay = 0,
  y = 14,
  className,
  inView = false,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
  inView?: boolean;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  const target = { opacity: 1, y: 0 };
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      animate={inView ? undefined : target}
      whileInView={inView ? target : undefined}
      viewport={inView ? { once: true, margin: "-60px" } : undefined}
      transition={{ duration: 0.4, delay, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}
