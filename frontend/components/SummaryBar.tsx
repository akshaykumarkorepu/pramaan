import { AlertCircle, Check } from "lucide-react";
import { CountUp } from "@/components/motion/CountUp";
import { SOURCE_STYLE } from "@/components/status";
import { cn } from "@/lib/utils";
import type { Notice, NoticesResponse, SourceId } from "@/lib/types";

const SOURCE_IDS: SourceId[] = ["rbi", "sebi", "pib"];

function Stat({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <CountUp value={value} className={cn("text-2xl font-semibold tabular-nums", tone)} />
      <span className="text-sm text-slate-600">{label}</span>
    </span>
  );
}

/** Numbers come straight from the /notices items and per-source counts, nothing else. */
export function SummaryBar({ items, sources }: { items: Notice[]; sources: NoticesResponse["sources"] }) {
  const yes = items.filter((n) => n.applies === "yes").length;
  const review = items.filter((n) => n.applies === "review").length;
  const no = items.filter((n) => n.applies === "no").length;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft sm:p-5">
      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
        <Stat value={yes} label="apply to you" tone="text-verified" />
        <span className="text-slate-300" aria-hidden>·</span>
        <Stat value={review} label="need review" tone="text-review" />
        <span className="text-slate-300" aria-hidden>·</span>
        <Stat value={no} label="don't apply" tone="text-slate-500" />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {SOURCE_IDS.map((id) => {
          const s = sources[id];
          const name = SOURCE_STYLE[id].label;
          return s.ok ? (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-full border border-verified/25 bg-verified-soft px-2.5 py-1 text-xs font-medium text-verified"
            >
              {name} <Check className="size-3" aria-hidden /> {s.count}
            </span>
          ) : (
            <span
              key={id}
              className="inline-flex max-w-full items-start gap-1 rounded-full border border-rejected/25 bg-rejected-soft px-2.5 py-1 text-xs font-medium text-rejected"
            >
              <AlertCircle className="mt-0.5 size-3 shrink-0" aria-hidden />
              <span>
                {name}: {s.error ?? "not responding"}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
