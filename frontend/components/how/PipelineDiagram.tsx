"use client";

import { useRef } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";
import { Languages, ListChecks, Radio, RefreshCcw, ScrollText, ShieldCheck, UserCheck, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Kind = "live" | "ai" | "code" | "mixed";

const STEPS: { icon: LucideIcon; title: string; note: string; kind: Kind }[] = [
  { icon: Radio, title: "Fetch live notice", note: "From the official feed, right now", kind: "live" },
  { icon: ScrollText, title: "Read full text", note: "HTML or PDF", kind: "code" },
  { icon: ListChecks, title: "Extract duties", note: "AI, with a verbatim quote for each", kind: "ai" },
  { icon: ShieldCheck, title: "Verify every quote, number & date", note: "Plain code, no AI", kind: "code" },
  { icon: RefreshCcw, title: "Self-correct once", note: "AI retries the rejected items, one time", kind: "ai" },
  { icon: UserCheck, title: "Check who it applies to", note: "Rules first, AI only if unsure", kind: "mixed" },
  { icon: Languages, title: "Explain in Telugu, Hindi or English", note: "AI, verified items only", kind: "ai" },
];
const GUARD = 3; // index of the Verify step

const TAG: Record<Kind, { label: string; cls: string }> = {
  live: { label: "Live", cls: "bg-slate-100 text-slate-600 border-slate-200" },
  code: { label: "Code", cls: "bg-verified-soft text-verified border-verified/25" },
  ai: { label: "AI", cls: "bg-brand-soft text-brand border-indigo-200" },
  mixed: { label: "Rules + AI", cls: "bg-review-soft text-review border-review/30" },
};

const STEP_S = 0.45; // seconds between one step lighting up and the next

/** The pipeline as an SVG diagram. Nodes and connectors light up one after another once it scrolls into view. */
export function PipelineDiagram() {
  const ref = useRef<HTMLOListElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.25 });
  const reduce = useReducedMotion();
  const lit = seen || !!reduce; // reduced motion: everything is shown lit straight away
  const t = (i: number) => (reduce ? 0 : i * STEP_S);

  return (
    <ol ref={ref} className="grid gap-0 md:grid-cols-7" aria-label="Pramaan pipeline, in order">
      {STEPS.map((s, i) => {
        const guard = i === GUARD;
        const stroke = guard ? "#059669" : "#3730a3";
        const last = i === STEPS.length - 1;
        return (
          <li key={s.title} className="relative flex gap-4 pb-8 md:flex-col md:items-center md:gap-3 md:pb-0 md:text-center">
            {/* connector to the next step: vertical on phones, horizontal from md up */}
            {!last && (
              <>
                <svg aria-hidden className="absolute left-8 top-8 h-full w-0.5 -translate-x-1/2 md:hidden" viewBox="0 0 2 100" preserveAspectRatio="none">
                  <path d="M1 0V100" stroke="#e2e8f0" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  <motion.path
                    d="M1 0V100"
                    stroke={stroke}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: lit ? 1 : 0 }}
                    transition={{ duration: reduce ? 0 : STEP_S, delay: t(i) + 0.2 }}
                  />
                </svg>
                <svg aria-hidden className="absolute left-1/2 top-8 hidden h-0.5 w-full -translate-y-1/2 md:block" viewBox="0 0 100 2" preserveAspectRatio="none">
                  <path d="M0 1H100" stroke="#e2e8f0" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                  <motion.path
                    d="M0 1H100"
                    stroke={stroke}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: lit ? 1 : 0 }}
                    transition={{ duration: reduce ? 0 : STEP_S, delay: t(i) + 0.2 }}
                  />
                </svg>
              </>
            )}

            <div className="relative z-10 size-16 shrink-0">
              <svg viewBox="0 0 64 64" className="size-16" aria-hidden>
                {guard && (
                  <motion.circle
                    cx="32"
                    cy="32"
                    r="30"
                    fill="none"
                    stroke="#059669"
                    strokeWidth="2"
                    strokeDasharray="4 5"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: lit ? 1 : 0 }}
                    transition={{ delay: t(i) }}
                  />
                )}
                <motion.circle
                  cx="32"
                  cy="32"
                  r="24"
                  strokeWidth="2.5"
                  initial={{ fill: "#ffffff", stroke: "#cbd5e1" }}
                  animate={lit ? { fill: guard ? "#ecfdf5" : "#eef2ff", stroke } : undefined}
                  transition={{ duration: reduce ? 0 : 0.4, delay: t(i) }}
                />
              </svg>
              <motion.span
                className="absolute inset-0 flex items-center justify-center"
                initial={{ color: "#94a3b8" }}
                animate={lit ? { color: stroke } : undefined}
                transition={{ duration: reduce ? 0 : 0.4, delay: t(i) }}
              >
                <s.icon className="size-6" aria-hidden />
              </motion.span>
            </div>

            <div className="min-w-0 flex-1 md:px-1">
              <div className="flex flex-wrap items-center gap-1.5 md:justify-center">
                <span className="text-xs font-semibold text-slate-400">{i + 1}</span>
                <span className={cn("rounded-full border px-1.5 py-px text-[11px] font-semibold", TAG[s.kind].cls)}>{TAG[s.kind].label}</span>
              </div>
              <p className={cn("mt-1 text-sm font-semibold leading-snug", guard ? "text-verified" : "text-slate-900")}>{s.title}</p>
              <p className="mt-0.5 text-[13px] leading-snug text-slate-500">{s.note}</p>
              {guard && (
                <span className="mt-2 inline-block rounded-full bg-verified px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white">
                  The guardrail
                </span>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
