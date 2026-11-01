"use client";

import { AlertTriangle, Bot, ChevronDown, Cpu, RefreshCw, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CountUp } from "@/components/motion/CountUp";
import { FadeIn } from "@/components/motion/FadeIn";
import { PulseDot } from "@/components/motion/PulseDot";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";
import { ago, useNow } from "@/lib/time";
import { useHealth } from "@/lib/useHealth";
import { useWarmStatus } from "@/lib/useWarmStatus";
import type { HealthResponse, SourceHealth, SourceId } from "@/lib/types";

const SOURCES: { id: SourceId; name: string; full: string }[] = [
  { id: "rbi", name: "RBI", full: "Reserve Bank of India" },
  { id: "sebi", name: "SEBI", full: "Securities and Exchange Board of India" },
  { id: "pib", name: "PIB", full: "Press Information Bureau" },
];

function Row({
  tone,
  title,
  sub,
  right,
}: {
  tone: "ok" | "fail" | "pending";
  title: string;
  sub: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 px-5 py-3.5">
      <PulseDot tone={tone} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className={tone === "fail" ? "text-[13px] text-rejected" : "break-words text-[13px] text-slate-500"}>{sub}</p>
      </div>
      {right}
    </div>
  );
}

function SourceRow({ s, h, now }: { s: (typeof SOURCES)[number]; h: SourceHealth; now: number }) {
  return (
    <Row
      tone={h.ok ? "ok" : "fail"}
      title={s.name}
      sub={h.ok ? `${s.full} · ${ago(h.last_fetch, now)}` : (h.error ?? `${s.name} is not responding.`)}
      right={
        h.ok ? (
          <div className="text-right">
            <CountUp value={h.count} className="text-xl font-semibold tabular-nums text-slate-900" />
            <p className="text-[11px] uppercase tracking-wide text-slate-400">notices</p>
          </div>
        ) : null
      }
    />
  );
}

function allOk(h: HealthResponse) {
  return SOURCES.every((s) => h.sources[s.id].ok) && h.llm.ok && h.runtime.ok;
}

/** Compact "System status" strip: one line with the real state, expands to per-source detail. */
export function LiveStatus() {
  const { phase, data, error, elapsedMs, giveUpAfterMs, retry } = useHealth();
  const now = useNow();
  const warm = useWarmStatus(phase === "ready");
  const waking = phase === "loading" || phase === "waking";
  const progress = Math.min(100, (elapsedMs / giveUpAfterMs) * 100);

  const summary =
    phase === "ready" && data
      ? allOk(data)
        ? "All systems online"
        : "Some systems have problems"
      : phase === "failed"
        ? "Server unreachable"
        : "Waking up the server…";
  const tone = phase === "ready" && data ? (allOk(data) ? "ok" : "fail") : phase === "failed" ? "fail" : "pending";

  return (
    <section className="mx-auto mt-4 w-full max-w-[1100px] px-4 sm:px-6" aria-label="System status">
      <FadeIn delay={0.55}>
        <details className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft">
          <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-3 text-sm [&::-webkit-details-marker]:hidden">
            <PulseDot tone={tone} />
            <span className="font-medium text-slate-900">System status</span>
            <span className="text-slate-500">· {summary}</span>
            {warm && warm.cached_count > 0 && (
              <span className="hidden text-xs text-slate-400 md:inline">
                · {warm.cached_count} {warm.cached_count === 1 ? "circular" : "circulars"} pre-analysed
              </span>
            )}
            {phase === "ready" && data && (
              <span className="ml-auto hidden items-center gap-3 text-xs text-slate-500 sm:flex">
                {SOURCES.map((s) => (
                  <span key={s.id} className="inline-flex items-center gap-1.5">
                    <PulseDot tone={data.sources[s.id].ok ? "ok" : "fail"} className="size-2" /> {s.name}
                  </span>
                ))}
              </span>
            )}
            <ChevronDown
              className="ml-auto size-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180 sm:ml-2"
              aria-hidden
            />
          </summary>

          <div className="border-t border-slate-100">
            {waking && (
              <div role="status" aria-live="polite">
                <div className="px-5 pb-1 pt-4">
                  <p className="text-sm font-medium text-slate-800">Waking up the server…</p>
                  <p className="mt-0.5 text-[13px] text-slate-500">
                    The free hosting tier sleeps when idle. This can take up to a minute.
                  </p>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-accent transition-[width] duration-500"
                      style={{ width: `${Math.max(progress, 6)}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-3 px-5 py-4">
                  <ShimmerSkeleton className="h-4 w-40" />
                  <ShimmerSkeleton className="h-4 w-64 max-w-full" />
                </div>
              </div>
            )}

            {phase === "failed" && (
              <div className="flex flex-col items-start gap-4 px-5 py-6 sm:flex-row sm:items-center" role="alert">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-rejected-soft text-rejected">
                  <AlertTriangle className="size-5" aria-hidden />
                </span>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-900">We couldn&apos;t reach the server</p>
                  <p className="text-[13px] text-slate-500">{error}</p>
                </div>
                <Button variant="outline" onClick={retry} className="gap-2">
                  <RefreshCw aria-hidden /> Retry
                </Button>
              </div>
            )}

            {phase === "ready" && data && (
              <div className="divide-y divide-slate-100">
                {SOURCES.map((s) => (
                  <SourceRow key={s.id} s={s} h={data.sources[s.id]} now={now} />
                ))}
                <Row
                  tone={data.llm.ok ? "ok" : "fail"}
                  title="AI model"
                  sub={data.llm.ok ? (data.llm.model ?? "Connected") : (data.llm.error ?? "The AI service is not responding.")}
                  right={<Bot className="size-5 text-slate-300" aria-hidden />}
                />
                {warm && (
                  <Row
                    tone="ok"
                    title="Pre-analysed circulars"
                    sub={
                      warm.running
                        ? `${warm.cached_count} ready · analysing the next one in the background (${warm.queued} left)`
                        : `${warm.cached_count} ${warm.cached_count === 1 ? "circular" : "circulars"} ready to open instantly`
                    }
                    right={<Zap className="size-5 text-slate-300" aria-hidden />}
                  />
                )}
                <Row
                  tone={data.runtime.ok ? "ok" : "fail"}
                  title="Document reader"
                  sub={data.runtime.ok ? "HTML and PDF pipeline ready" : (data.runtime.error ?? "The document reader failed to load.")}
                  right={<Cpu className="size-5 text-slate-300" aria-hidden />}
                />
              </div>
            )}
          </div>
        </details>
      </FadeIn>
    </section>
  );
}
