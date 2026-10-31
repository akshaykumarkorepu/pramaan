import { CheckCircle2, CircleHelp, MinusCircle } from "lucide-react";
import type { Applicability } from "@/lib/types";

const LOOK = {
  yes: { title: "This applies to you", icon: CheckCircle2, box: "border-verified/30 bg-verified-soft", ic: "bg-verified text-white", tx: "text-verified" },
  review: { title: "Needs your review", icon: CircleHelp, box: "border-review/30 bg-review-soft", ic: "bg-review text-white", tx: "text-review" },
  no: { title: "Doesn't apply to you", icon: MinusCircle, box: "border-slate-200 bg-slate-100", ic: "bg-slate-400 text-white", tx: "text-slate-600" },
} as const;

export function ApplicabilityBanner({ applies }: { applies: Applicability }) {
  const l = LOOK[applies.value];
  const Icon = l.icon;
  return (
    <section aria-label="Does this apply to you" className={`rounded-2xl border p-5 sm:p-6 ${l.box}`}>
      <div className="flex items-start gap-4">
        <span className={`flex size-11 shrink-0 items-center justify-center rounded-full ${l.ic}`}>
          <Icon className="size-6" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className={`text-xl font-semibold sm:text-2xl ${l.tx}`}>{l.title}</h2>
          <p className="mt-1 text-[15px] text-slate-700">{applies.reason}</p>
        </div>
      </div>
      {applies.quote && (
        <blockquote className="mt-4 border-l-2 border-slate-300 pl-4 text-[13px] italic leading-relaxed text-slate-600">
          {applies.quote}
        </blockquote>
      )}
    </section>
  );
}
