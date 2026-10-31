"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Bot, Cpu, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CountUp } from "@/components/motion/CountUp";
import { FadeIn } from "@/components/motion/FadeIn";
import { PulseDot } from "@/components/motion/PulseDot";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";
import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { useHealth } from "@/lib/useHealth";
import type { SourceHealth, SourceId } from "@/lib/types";

const SOURCES: { id: SourceId; name: string; full: string }[] = [
  { id: "rbi", name: "RBI", full: "Reserve Bank of India" },
  { id: "sebi", name: "SEBI", full: "Securities and Exchange Board of India" },
  { id: "pib", name: "PIB", full: "Press Information Bureau" },
];

function ago(iso: string | null, now: number): string {
  if (!iso) return "not fetched yet";
  const mins = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (mins < 1) return "fetched just now";
  if (mins === 1) return "fetched 1 min ago";
  if (mins < 60) return `fetched ${mins} min ago`;
  const h = Math.floor(mins / 60);
  return `fetched ${h} h ago`;
}

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
    <div className="flex items-center gap-4 px-5 py-4">
      <PulseDot tone={tone} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <p className={tone === "fail" ? "text-[13px] text-rejected" : "text-[13px] text-slate-500 break-words"}>{sub}</p>
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

export function LiveStatus() {
  const { phase, data, error, elapsedMs, giveUpAfterMs, retry } = useHealth();
  const [now, setNow] = useState(0) // set after mount: Date.now() must not run during prerender;

  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const t = setInterval(tick, 30_000);
    return () => clearInterval(t);
  }, []);

  const waking = phase === "loading" || phase === "waking";
  const progress = Math.min(100, (elapsedMs / giveUpAfterMs) * 100);

  return (
    <section className="mx-auto w-full max-w-[1100px] px-4 sm:px-6" aria-labelledby="live-status">
      <FadeIn delay={0.5}>
        <Card className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-0 shadow-soft ring-0">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 id="live-status" className="text-base font-semibold text-slate-900">
                Live status
              </h2>
              <p className="text-[13px] text-slate-500">Real responses from the Pramaan server, right now.</p>
            </div>
            {phase === "ready" && (
              <span className="rounded-full bg-verified-soft px-2.5 py-1 text-xs font-medium text-verified">Online</span>
            )}
          </div>

          {waking && (
            <div role="status" aria-live="polite">
              <div className="px-5 pb-1 pt-4">
                <p className="text-sm font-medium text-slate-800">Waking up the server…</p>
                <p className="mt-0.5 text-[13px] text-slate-500">
                  The free hosting tier sleeps when idle. This can take up to a minute.
                </p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="relative h-full" style={{ width: `${Math.max(progress, 6)}%` }}>
                    <div className="h-full w-full rounded-full bg-gradient-accent transition-[width] duration-500" />
                  </div>
                </div>
              </div>
              <div className="divide-y divide-slate-100">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex items-center gap-4 px-5 py-4">
                    <ShimmerSkeleton className="size-2.5 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <ShimmerSkeleton className="h-3.5 w-24" />
                      <ShimmerSkeleton className="h-3 w-52 max-w-full" />
                    </div>
                    <ShimmerSkeleton className="h-6 w-10" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {phase === "failed" && (
            <div className="flex flex-col items-start gap-4 px-5 py-8 sm:flex-row sm:items-center" role="alert">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-rejected-soft text-rejected">
                <AlertTriangle className="size-5" aria-hidden />
              </span>
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">We couldn&apos;t reach the server</p>
                <p className="text-[13px] text-slate-500">{error} Nothing is shown here until it answers.</p>
              </div>
              <Button variant="outline" onClick={retry} className="gap-2">
                <RefreshCw aria-hidden /> Retry
              </Button>
            </div>
          )}

          {phase === "ready" && data && (
            <Stagger className="divide-y divide-slate-100" gap={0.06}>
              {SOURCES.map((s) => (
                <StaggerItem key={s.id}>
                  <SourceRow s={s} h={data.sources[s.id]} now={now} />
                </StaggerItem>
              ))}
              <StaggerItem>
                <Row
                  tone={data.llm.ok ? "ok" : "fail"}
                  title="AI model"
                  sub={data.llm.ok ? (data.llm.model ?? "Connected") : (data.llm.error ?? "The AI service is not responding.")}
                  right={<Bot className="size-5 text-slate-300" aria-hidden />}
                />
              </StaggerItem>
              <StaggerItem>
                <Row
                  tone={data.runtime.ok ? "ok" : "fail"}
                  title="Document reader"
                  sub={data.runtime.ok ? "HTML and PDF pipeline ready" : (data.runtime.error ?? "The document reader failed to load.")}
                  right={<Cpu className="size-5 text-slate-300" aria-hidden />}
                />
              </StaggerItem>
            </Stagger>
          )}
        </Card>
      </FadeIn>
    </section>
  );
}
