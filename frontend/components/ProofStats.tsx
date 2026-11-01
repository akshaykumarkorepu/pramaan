"use client";

import { Info, ShieldCheck } from "lucide-react";
import { CountUp } from "@/components/motion/CountUp";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { sinceLabel } from "@/lib/time";
import { useStats } from "@/lib/useStats";
import type { SourceId, StatsBlock, StatsResponse } from "@/lib/types";

export const WARMING_UP = "Warming up — stats appear after the first analyses";
const MEANING =
  "Verified = the exact quote, dates and numbers were found in the official document. This measures grounding, not whether every duty was found.";

const SOURCES: { id: SourceId; name: string }[] = [
  { id: "rbi", name: "RBI" },
  { id: "sebi", name: "SEBI" },
  { id: "pib", name: "PIB" },
];

/** Duties that passed the verifier, including ones fixed on retry (the same ones the explainer may use). */
const grounded = (s: StatsBlock) => s.verified + s.near + s.fixed;
const seconds = (ms: number | null) => (ms === null ? "—" : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

function MeaningTip() {
  return (
    <Tooltip>
      <TooltipTrigger aria-label="What does verified mean?" className="inline-flex align-middle text-slate-400 hover:text-slate-600">
        <Info className="size-3.5" aria-hidden />
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-pretty">{MEANING}</TooltipContent>
    </Tooltip>
  );
}

/** One line under the home hero. Renders nothing until there is something real to say. */
export function ProofStatsLine() {
  const stats = useStats(true);
  if (!stats || stats.circulars_analysed === 0) return null;
  const parts: string[] = [];
  if (stats.duties_extracted > 0) parts.push(`${grounded(stats)} of ${stats.duties_extracted} extracted duties verified against official text`);
  if (stats.injected_tests_run > 0) parts.push(`${stats.injected_tests_caught} of ${stats.injected_tests_run} fake claims caught`);
  if (parts.length === 0) return null;
  return (
    <p className="mx-auto -mt-6 mb-6 flex max-w-[1100px] flex-wrap items-center justify-center gap-x-1.5 px-4 text-center text-[13px] text-slate-600 sm:px-6">
      <ShieldCheck className="size-3.5 text-verified" aria-hidden />
      <span>{parts.join(" · ")}</span>
      <span className="text-slate-400">· {sinceLabel(stats.started_at)}</span>
      <MeaningTip />
    </p>
  );
}

function Tile({ value, label, tone }: { value: number; label: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className={`text-3xl font-bold tabular-nums ${tone ?? "text-slate-900"}`}>
        <CountUp value={value} />
      </p>
      <p className="mt-1 text-[13px] text-slate-600">{label}</p>
    </div>
  );
}

function Card({ stats }: { stats: StatsResponse }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-soft sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <ShieldCheck className="size-5 text-verified" aria-hidden />
          Proof stats <MeaningTip />
        </p>
        <p className="text-[13px] text-slate-500">live, {sinceLabel(stats.started_at)}</p>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile value={stats.circulars_analysed} label="notices analysed" />
        <Tile value={stats.duties_extracted} label="duties extracted" />
        <Tile value={grounded(stats)} label="verified against the official text" tone="text-verified" />
        <Tile value={stats.rejected} label="rejected, shown, never hidden" tone="text-rejected" />
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-3xl font-bold tabular-nums text-slate-900">
            <CountUp value={stats.injected_tests_caught} />
            <span className="text-slate-400"> / {stats.injected_tests_run}</span>
          </p>
          <p className="mt-1 text-[13px] text-slate-600">fake claims caught</p>
        </div>
      </div>

      <p className="mt-4 text-sm text-slate-600">
        Average time per notice: <strong className="text-slate-900">{seconds(stats.avg_latency_ms_fresh)}</strong> analysed fresh,{" "}
        <strong className="text-slate-900">{seconds(stats.avg_latency_ms_cached)}</strong> from the cache.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead className="text-[13px] text-slate-500">
            <tr>
              <th className="py-1.5 pr-3 font-medium">Source</th>
              <th className="py-1.5 pr-3 font-medium">Notices</th>
              <th className="py-1.5 pr-3 font-medium">Duties</th>
              <th className="py-1.5 pr-3 font-medium">Verified</th>
              <th className="py-1.5 font-medium">Rejected</th>
            </tr>
          </thead>
          <tbody className="tabular-nums text-slate-800">
            {SOURCES.map(({ id, name }) => {
              const b = stats.by_source[id];
              return (
                <tr key={id} className="border-t border-slate-100">
                  <td className="py-1.5 pr-3 font-semibold">{name}</td>
                  <td className="py-1.5 pr-3">{b.circulars_analysed}</td>
                  <td className="py-1.5 pr-3">{b.duties_extracted}</td>
                  <td className="py-1.5 pr-3">{grounded(b)}</td>
                  <td className="py-1.5">{b.rejected}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** The full card for How it works. */
export function ProofStatsCard() {
  const stats = useStats(true);
  if (!stats || stats.circulars_analysed === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 p-6 text-base font-semibold text-slate-700 sm:p-8">
        {WARMING_UP}
      </div>
    );
  }
  return <Card stats={stats} />;
}
