import { AlertTriangle, FileSearch, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";

export function LoadingNotices({ slow, elapsedMs, giveUpAfterMs }: { slow: boolean; elapsedMs: number; giveUpAfterMs: number }) {
  const pct = Math.min(100, (elapsedMs / giveUpAfterMs) * 100);
  return (
    <div role="status" aria-live="polite" className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
        <p className="text-sm font-medium text-slate-800">
          {slow ? "Waking up the server…" : "Reading this week's circulars from RBI, SEBI and PIB…"}
        </p>
        <p className="mt-0.5 text-[13px] text-slate-500">
          {slow
            ? "The free hosting tier sleeps when idle. This can take up to a minute."
            : "First load can take ~15 seconds."}
        </p>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
          {slow ? (
            <div className="h-full bg-gradient-accent transition-[width] duration-500" style={{ width: `${Math.max(pct, 6)}%` }} />
          ) : (
            <div className="h-full w-1/3 rounded-full bg-gradient-accent motion-safe:animate-indeterminate" />
          )}
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
            <div className="flex justify-between">
              <ShimmerSkeleton className="h-5 w-12 rounded-full" />
              <ShimmerSkeleton className="h-5 w-24 rounded-full" />
            </div>
            <ShimmerSkeleton className="h-4 w-full" />
            <ShimmerSkeleton className="h-4 w-2/3" />
            <ShimmerSkeleton className="h-3 w-1/2" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function EmptyNotices({ filtered }: { filtered: boolean }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-14 text-center">
      <span className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <FileSearch className="size-5" aria-hidden />
      </span>
      <p className="mt-4 text-sm font-semibold text-slate-900">
        {filtered ? "Nothing matches these filters" : "No new notices this week"}
      </p>
      <p className="mt-1 max-w-sm text-[13px] text-slate-500">
        {filtered
          ? "Try another tab or source."
          : "Paste a link instead — you'll be able to check any RBI, SEBI or PIB notice by its address."}
      </p>
    </div>
  );
}

export function ErrorNotices({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-4 rounded-2xl border border-rejected/25 bg-rejected-soft/60 p-6 sm:flex-row sm:items-center">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white text-rejected">
        <AlertTriangle className="size-5" aria-hidden />
      </span>
      <div className="flex-1">
        <p className="text-sm font-semibold text-slate-900">We couldn&apos;t load the notices</p>
        <p className="text-[13px] text-slate-600">{message}</p>
      </div>
      <Button variant="outline" onClick={onRetry} className="gap-2 bg-white">
        <RefreshCw aria-hidden /> Retry
      </Button>
    </div>
  );
}
