"use client";

import { motion, useReducedMotion } from "motion/react";
import { Loader2, Minus, X } from "lucide-react";
import { PulseDot } from "@/components/motion/PulseDot";
import { formatMs, STEP_META } from "@/lib/circular";
import { useNow } from "@/lib/time";
import type { StepName, StepState } from "@/lib/useAnalyze";
import { cn } from "@/lib/utils";

function Check({ animate }: { animate: boolean }) {
  return (
    <motion.svg viewBox="0 0 24 24" className="size-4 text-white" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <motion.path
        d="M5 12.5l4.5 4.5L19 7.5"
        initial={animate ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      />
    </motion.svg>
  );
}

function Marker({ name, s, waiting }: { name: StepName; s: StepState; waiting: boolean }) {
  const reduce = useReducedMotion();
  const Icon = STEP_META[name].icon;
  if (s.status === "done" && s.skipped)
    return <span className="flex size-7 items-center justify-center rounded-full bg-slate-100 text-slate-400"><Minus className="size-4" aria-hidden /></span>;
  if (s.status === "done")
    return (
      <motion.span
        className="flex size-7 items-center justify-center rounded-full bg-verified"
        initial={reduce ? false : { scale: 0.6 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 20 }}
      >
        <Check animate={!reduce} />
      </motion.span>
    );
  if (s.status === "failed")
    return <span className="flex size-7 items-center justify-center rounded-full bg-rejected text-white"><X className="size-4" strokeWidth={3} aria-hidden /></span>;
  if (s.status === "running")
    return (
      <span className={cn("flex size-7 items-center justify-center rounded-full border-2", waiting ? "border-review/40 bg-review-soft" : "border-brand/30 bg-brand-soft")}>
        {waiting ? <PulseDot tone="pending" /> : <Loader2 className="size-4 animate-spin text-brand" aria-hidden />}
      </span>
    );
  return <span className="flex size-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-300"><Icon className="size-3.5" aria-hidden /></span>;
}

export function StepRow({ name, s, last }: { name: StepName; s: StepState; last: boolean }) {
  const now = useNow(1000);
  const waiting = s.status === "running" && !!s.wait;
  const left = s.wait && now ? Math.max(0, Math.ceil(s.wait.seconds - (now - s.wait.since) / 1000)) : null;
  const meta = STEP_META[name];

  return (
    <li className="relative flex gap-4 pb-5 last:pb-0" aria-current={s.status === "running" ? "step" : undefined}>
      {!last && <span aria-hidden className={cn("absolute left-3.5 top-8 -ml-px h-[calc(100%-1.75rem)] w-0.5 rounded-full", s.status === "done" ? "bg-verified/40" : "bg-slate-200")} />}
      <Marker name={name} s={s} waiting={waiting} />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <p className={cn("text-sm font-semibold", s.status === "pending" ? "text-slate-400" : s.skipped ? "text-slate-500" : "text-slate-900")}>{meta.label}</p>
          {s.status === "done" && s.cached && (
            <span className="rounded-full border border-fixed/25 bg-fixed-soft px-2 py-0.5 text-[11px] font-medium text-fixed">instant · cached</span>
          )}
          {s.status === "done" && !s.cached && !!s.ms && <span className="text-xs tabular-nums text-slate-400">{formatMs(s.ms)}</span>}
          {s.status === "failed" && s.ms !== null && <span className="text-xs tabular-nums text-slate-400">{formatMs(s.ms)}</span>}
        </div>
        {waiting && (
          <p className="mt-0.5 flex items-center gap-1.5 text-[13px] font-medium text-review" role="status">
            Waiting for AI capacity{left !== null ? ` · about ${left}s` : ""}
            <span className="text-slate-400 font-normal">(free-tier rate limit)</span>
          </p>
        )}
        {s.status === "running" && !waiting && <p className="mt-0.5 text-[13px] text-slate-500">Working…</p>}
        {s.detail && s.status !== "running" && (
          <p className={cn("mt-0.5 break-words text-[13px]", s.status === "failed" ? "text-rejected" : "text-slate-500")}>{s.detail}</p>
        )}
      </div>
    </li>
  );
}
