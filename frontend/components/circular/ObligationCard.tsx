"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Calendar, ChevronDown, FlaskConical, Quote } from "lucide-react";
import { OBLIGATION_STATUS } from "@/components/status";
import { formatDeadline, friendlyReason, proofParts } from "@/lib/circular";
import type { Doc, Obligation } from "@/lib/types";
import { cn } from "@/lib/utils";

function Proof({ doc, o, defaultOpen }: { doc: Doc; o: Obligation; defaultOpen: boolean }) {
  const parts = proofParts(doc, o.match_span);
  const rejected = o.status === "rejected";
  return (
    <details className="group mt-4 rounded-xl border border-slate-200 bg-slate-50/70" open={defaultOpen}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-[13px] font-medium text-slate-700 [&::-webkit-details-marker]:hidden">
        <Quote className="size-3.5 text-slate-400" aria-hidden />
        {rejected ? "The claimed quote" : "Proof from the official text"}
        {parts && <span className="text-slate-400">· paragraph {parts.id}</span>}
        <ChevronDown className="ml-auto size-4 text-slate-400 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="border-t border-slate-200 px-4 py-3 text-[14px] leading-relaxed text-slate-700">
        {parts ? (
          <p>
            {parts.before}
            <mark className="rounded bg-yellow-200/80 px-0.5 text-slate-900 [box-decoration-break:clone]">{parts.hit}</mark>
            {parts.after}
          </p>
        ) : (
          <p className={rejected ? "italic text-slate-500" : ""}>“{o.quote}”</p>
        )}
        {o.status === "near" && o.matched_text && o.matched_text !== o.quote && (
          <p className="mt-2 text-[12px] text-slate-500">The model&apos;s quote differed slightly from the source; the source wording is highlighted.</p>
        )}
      </div>
    </details>
  );
}

export function ObligationCard({
  o,
  doc,
  index,
  openProof,
}: {
  o: Obligation;
  doc: Doc;
  index: number;
  openProof: boolean;
}) {
  const reduce = useReducedMotion();
  const test = o.injected_test;
  // The injected claim is already final in the stream (rejected by the code checker). We show it as "checking…" for a
  // moment first, then flip it to its real status, so the viewer sees the moment of rejection. The outcome is not faked.
  const [revealed, setRevealed] = useState(!test);
  useEffect(() => {
    if (!test) return;
    const t = setTimeout(() => setRevealed(true), reduce ? 300 : 1300);
    return () => clearTimeout(t);
  }, [test, reduce]);

  const status = revealed ? o.status : null;
  const rejected = status === "rejected";
  const st = OBLIGATION_STATUS[o.status];
  const label = o.status === "fixed" ? "Fixed by self-correction" : o.status === "near" && o.score ? `Near match · ${Math.round(o.score)}%` : st.label;

  return (
    <motion.article
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1], delay: Math.min(index, 6) * 0.07 }}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-white p-5 shadow-soft sm:p-6",
        rejected ? "border-rejected/30 bg-slate-50 motion-safe:animate-shake" : test ? "border-dashed border-slate-300" : "border-slate-200",
      )}
    >
      {rejected && test && <span aria-hidden className="pointer-events-none absolute inset-0 bg-rejected motion-safe:animate-flash opacity-0" />}
      {test && (
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-white">
          <FlaskConical className="size-3" aria-hidden /> Test — fake claim inserted on purpose
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{o.who}</p>
        {status ? (
          <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-semibold", st.badge)}>{label}</span>
        ) : (
          <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-500">Checking…</span>
        )}
      </div>

      <h3 className={cn("mt-2 text-lg font-semibold leading-snug sm:text-xl", rejected ? "text-slate-500 line-through decoration-rejected/60" : "text-slate-900")}>
        {o.must_do}
      </h3>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[13px]">
        <span className={cn("inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 font-medium", o.deadline ? "border-brand/20 bg-brand-soft text-brand" : "border-slate-200 bg-slate-50 text-slate-500")}>
          <Calendar className="size-3.5" aria-hidden />
          {o.deadline ? formatDeadline(o.deadline) : "No fixed date"}
        </span>
        {o.paragraph && (
          <span className="inline-flex items-center gap-1.5 text-slate-500">
            Paragraph {o.paragraph}
            {o.paragraph_corrected && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">corrected</span>}
          </span>
        )}
      </div>

      {rejected && (
        <p className="mt-3 text-[13px] font-medium text-rejected">
          Rejected: {friendlyReason(o.reason)}. Nothing in the document backs this up.
        </p>
      )}
      {(revealed || !test) && <Proof doc={doc} o={o} defaultOpen={openProof} />}
    </motion.article>
  );
}
