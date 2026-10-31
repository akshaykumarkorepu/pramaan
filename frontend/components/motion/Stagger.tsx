"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Children wrapped in <StaggerItem> animate in one after another; items lift slightly on hover. */
export function Stagger({
  children,
  className,
  gap = 0.07,
  delay = 0,
  inView = false,
}: {
  children: ReactNode;
  className?: string;
  gap?: number;
  delay?: number;
  inView?: boolean; // start when scrolled into view instead of on mount
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate={inView ? undefined : "show"}
      whileInView={inView ? "show" : undefined}
      viewport={inView ? { once: true, margin: "-60px" } : undefined}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap, delayChildren: delay } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
  lift = false,
}: {
  children: ReactNode;
  className?: string;
  lift?: boolean;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
      }}
      whileHover={lift ? { y: -3, transition: { duration: 0.15 } } : undefined}
    >
      {children}
    </motion.div>
  );
}
