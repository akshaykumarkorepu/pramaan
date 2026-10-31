import { ExternalLink, RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { STEP_META } from "@/lib/circular";
import { STEP_ORDER, type StepName } from "@/lib/useAnalyze";
import type { ErrorEvent } from "@/lib/types";

const isStep = (s: string): s is StepName => (STEP_ORDER as readonly string[]).includes(s);

export function AnalyzeError({ error, onRetry }: { error: ErrorEvent; onRetry: () => void }) {
  const dropped = error.step === "connection";
  const where = isStep(error.step) ? STEP_META[error.step].label : null;
  const safeUrl = error.url && /^https?:\/\//i.test(error.url) ? error.url : null;
  return (
    <div role="alert" className="rounded-2xl border border-rejected/25 bg-rejected-soft/60 p-6">
      <div className="flex items-start gap-4">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white text-rejected">
          <TriangleAlert className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-base font-semibold text-slate-900">{dropped ? "Connection lost" : "We couldn't finish this one"}</p>
          {where && <p className="text-[13px] text-slate-500">Stopped at: {where}</p>}
          <p className="mt-2 text-[15px] text-slate-700">{error.message}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={onRetry} className="h-10 gap-2 bg-gradient-accent text-white">
              <RefreshCw aria-hidden /> Retry
            </Button>
            {safeUrl && (
              <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-border bg-white px-4 text-sm font-medium hover:bg-muted">
                Read the original <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
