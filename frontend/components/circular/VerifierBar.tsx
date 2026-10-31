"use client";

import { motion, useReducedMotion } from "motion/react";
import { Info } from "lucide-react";
import { CountUp } from "@/components/motion/CountUp";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Counts } from "@/lib/types";

const TIP = "Every quote, date and number is checked against the official text in code. Anything not found is rejected.";

export function VerifierBar({ counts }: { counts: Counts }) {
  const reduce = useReducedMotion();
  // counts.verified already includes near matches; fixed items are counted separately by the backend
  const total = counts.verified + counts.rejected + counts.fixed;
  const segs = [
    { key: "verified", n: counts.verified, bar: "bg-verified", text: "text-verified", label: "verified" },
    { key: "rejected", n: counts.rejected, bar: "bg-rejected", text: "text-rejected", label: "rejected" },
    { key: "fixed", n: counts.fixed, bar: "bg-fixed", text: "text-fixed", label: "fixed by self-correction" },
  ];
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {segs.map((s, i) => (
            <span key={s.key} className="inline-flex items-baseline gap-1.5">
              {i > 0 && <span className="mr-1.5 text-slate-300" aria-hidden>·</span>}
              <CountUp value={s.n} className={`text-2xl font-semibold tabular-nums ${s.n ? s.text : "text-slate-300"}`} />
              <span className="text-sm text-slate-600">{s.label}</span>
            </span>
          ))}
        </div>
        <Tooltip>
          <TooltipTrigger render={<button type="button" aria-label="How verification works" className="rounded-full p-1 text-slate-400 hover:text-brand" />}>
            <Info className="size-4" aria-hidden />
          </TooltipTrigger>
          <TooltipContent className="max-w-64 text-[13px] leading-snug">{TIP}</TooltipContent>
        </Tooltip>
      </div>
      <div className="mt-4 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${counts.verified} verified, ${counts.rejected} rejected, ${counts.fixed} fixed`}>
        {total > 0 &&
          segs
            .filter((s) => s.n > 0)
            .map((s) => (
              <motion.div
                key={s.key}
                className={`h-full first:rounded-l-full last:rounded-r-full ${s.bar}`}
                initial={reduce ? false : { width: 0 }}
                animate={{ width: `${(s.n / total) * 100}%` }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            ))}
      </div>
      <p className="mt-3 text-[13px] text-slate-500">{TIP}</p>
    </div>
  );
}
