"use client";

import { useMemo, useState } from "react";
import { AnimatePresence } from "motion/react";
import { EmptyNotices, ErrorNotices, LoadingNotices } from "@/components/StateViews";
import { NoticeCard } from "@/components/NoticeCard";
import { NoticeFilters, type Tab } from "@/components/NoticeFilters";
import { SummaryBar } from "@/components/SummaryBar";
import { FadeIn } from "@/components/motion/FadeIn";
import { useNow } from "@/lib/time";
import type { NoticesStatus } from "@/lib/useNotices";
import type { Lang, NoticesResponse, ProfileId, SourceId } from "@/lib/types";

export function NoticesSection({
  status,
  data,
  error,
  slow,
  elapsedMs,
  giveUpAfterMs,
  onRetry,
  profile,
  lang,
}: {
  status: NoticesStatus;
  data: NoticesResponse | null;
  error: string | null;
  slow: boolean;
  elapsedMs: number;
  giveUpAfterMs: number;
  onRetry: () => void;
  profile: ProfileId | null;
  lang: Lang;
}) {
  const [tab, setTab] = useState<Tab>("all");
  const [sources, setSources] = useState<SourceId[]>([]);
  const now = useNow();

  const items = useMemo(() => data?.items ?? [], [data]);
  const counts = useMemo<Record<Tab, number>>(
    () => ({
      all: items.length,
      yes: items.filter((n) => n.applies === "yes").length,
      review: items.filter((n) => n.applies === "review").length,
    }),
    [items],
  );
  const visible = useMemo(
    () => items.filter((n) => (tab === "all" || n.applies === tab) && (!sources.length || sources.includes(n.source))),
    [items, tab, sources],
  );

  if (status === "idle") return null;

  return (
    <section className="mx-auto mt-10 w-full max-w-[1100px] px-4 sm:px-6" aria-label="Notices" aria-live="polite">
      {status === "loading" && <LoadingNotices slow={slow} elapsedMs={elapsedMs} giveUpAfterMs={giveUpAfterMs} />}

      {status === "error" && !data && <ErrorNotices message={error ?? "Please try again."} onRetry={onRetry} />}

      {data && profile && (
        <FadeIn>
          <div className="relative space-y-5" aria-busy={status === "refreshing"}>
            {status === "refreshing" && (
              <div className="absolute inset-x-0 -top-3 h-1 overflow-hidden rounded-full bg-slate-200/70">
                <div className="h-full w-1/3 rounded-full bg-gradient-accent motion-safe:animate-indeterminate" />
              </div>
            )}
            {status === "error" && <ErrorNotices message={error ?? "Please try again."} onRetry={onRetry} />}
            <div className={status === "refreshing" ? "space-y-5 opacity-60 transition-opacity" : "space-y-5 transition-opacity"}>
              <SummaryBar items={items} sources={data.sources} />
              {items.length > 0 && (
                <NoticeFilters tab={tab} onTab={setTab} counts={counts} sources={sources} onSources={setSources} />
              )}
              {visible.length === 0 ? (
                <EmptyNotices filtered={items.length > 0} />
              ) : (
                <div className="grid gap-4 md:grid-cols-2" role="list">
                  <AnimatePresence mode="popLayout" initial>
                    {visible.map((n, i) => (
                      <NoticeCard key={n.id} notice={n} profile={profile} lang={lang} now={now} index={i} />
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </div>
        </FadeIn>
      )}
    </section>
  );
}
