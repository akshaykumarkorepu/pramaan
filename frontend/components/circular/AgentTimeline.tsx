"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";
import { formatMs } from "@/lib/circular";
import { STEP_ORDER, type AnalyzePhase, type Steps } from "@/lib/useAnalyze";
import { StepRow } from "./StepRow";

/**
 * The live agent stepper. Render it with key={runId}: every run starts with fresh local state
 * (open, no manual toggle), and after completion it folds into one summary row.
 */
export function AgentTimeline({ steps, phase, totalMs }: { steps: Steps; phase: AnalyzePhase; totalMs: number | null }) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(true);
  const touched = useRef(false);

  useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(() => {
      if (!touched.current) setOpen(false);
    }, 900);
    return () => clearTimeout(t);
  }, [phase]);

  const doneCount = STEP_ORDER.filter((n) => steps[n].status === "done").length;
  const pct = phase === "done" ? 100 : (doneCount / STEP_ORDER.length) * 100;
  const failed = phase === "error";

  const title =
    phase === "done" ? `Done in ${formatMs(totalMs)}` : failed ? "Stopped before finishing" : "Pramaan is working on it…";
  const Icon = phase === "done" ? ShieldCheck : failed ? TriangleAlert : Loader2;

  return (
    <section aria-label="What Pramaan is doing" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft">
      <div className="h-1 bg-slate-100" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
        <motion.div
          className={failed ? "h-full bg-rejected" : "h-full bg-gradient-accent"}
          initial={false}
          animate={{ width: `${Math.max(pct, phase === "running" ? 4 : 0)}%` }}
          transition={{ duration: reduce ? 0 : 0.4, ease: "easeOut" }}
        />
      </div>
      <button
        type="button"
        onClick={() => {
          touched.current = true;
          setOpen((o) => !o);
        }}
        aria-expanded={open}
        className="flex min-h-12 w-full items-center gap-3 px-5 py-3 text-left"
      >
        <Icon
          className={
            phase === "done" ? "size-5 text-verified" : failed ? "size-5 text-rejected" : "size-5 animate-spin text-brand"
          }
          aria-hidden
        />
        <span className="text-sm font-semibold text-slate-900" aria-live="polite">{title}</span>
        {phase === "done" && <span className="text-[13px] text-slate-500">· {doneCount} steps</span>}
        <ChevronDown className={`ml-auto size-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.28, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <ol className="border-t border-slate-100 px-5 py-5">
              {STEP_ORDER.map((n, i) => (
                <StepRow key={n} name={n} s={steps[n]} last={i === STEP_ORDER.length - 1} />
              ))}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
