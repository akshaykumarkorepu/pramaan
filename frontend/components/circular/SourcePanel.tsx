"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, SearchX } from "lucide-react";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";
import { SOURCE_STYLE } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { getDoc } from "@/lib/api";
import { highlightTargets, paragraphLabel, paragraphSegments, sourceFromUrl, friendlyReason } from "@/lib/circular";
import { ago, useNow } from "@/lib/time";
import type { Doc, Obligation, Paragraph } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Paragraphs from the analysis result; if that came without them, ask the server's cache (no re-analysis). */
function useParagraphs(doc: Doc, open: boolean) {
  const [fetched, setFetched] = useState<{ url: string; paragraphs: Paragraph[] } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const missing = doc.paragraphs.length === 0;

  useEffect(() => {
    if (!open || !missing || fetched?.url === doc.url) return;
    const ctrl = new AbortController();
    getDoc(doc.url, ctrl.signal)
      .then((d) => setFetched({ url: doc.url, paragraphs: d.paragraphs }))
      .catch((e) => {
        if (!ctrl.signal.aborted) setFailed(e instanceof Error ? e.message : "Couldn't load the document text.");
      });
    return () => ctrl.abort();
  }, [open, missing, doc.url, fetched?.url]);

  if (!missing) return { paragraphs: doc.paragraphs, loading: false, error: null };
  if (fetched?.url === doc.url) return { paragraphs: fetched.paragraphs, loading: false, error: null };
  return { paragraphs: [] as Paragraph[], loading: !failed, error: failed };
}

/**
 * The official text beside the analysis. The duty being shown has its proof sentence highlighted (with a soft pulse) and the
 * panel scrolls to it; other duties' sentences are marked more quietly. Up/Down jump between duties, Esc closes.
 * A rejected duty has nothing to mark, so the panel says so at the top instead.
 */
export function SourcePanel({
  open,
  onOpenChange,
  doc,
  real,
  active,
  onActive,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  doc: Doc;
  real: Obligation[];
  active: Obligation | null;
  onActive: (o: Obligation) => void;
}) {
  const now = useNow();
  const { paragraphs, loading, error } = useParagraphs(doc, open);
  const targets = useMemo(() => highlightTargets(real, paragraphs), [real, paragraphs]);
  const at = targets.findIndex((t) => t.obligation === active);
  const src = sourceFromUrl(doc.url);
  const refs = useRef(new Map<string, HTMLElement>());

  // scroll the active duty's paragraph into view once the sheet has laid out; also when ↑/↓ changes the duty
  useEffect(() => {
    if (!open || at < 0) return;
    const el = refs.current.get(targets[at].paragraph);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = setTimeout(() => el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" }), 150);
    return () => clearTimeout(t);
  }, [open, at, targets]);

  const go = (delta: number) => {
    const next = targets[at + delta];
    if (next) onActive(next.obligation);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.key !== "ArrowDown" && e.key !== "ArrowUp") || targets.length < 2 || at < 0) return;
      e.preventDefault();
      const next = targets[at + (e.key === "ArrowDown" ? 1 : -1)];
      if (next) onActive(next.obligation);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, at, targets, onActive]);

  const notFound = open && !!active && at < 0 && !loading;
  const activeKey = at >= 0 ? `${targets[at].paragraph}:${targets[at].start}` : "none";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-xl" aria-label="The official text">
        <SheetHeader className="gap-2 border-b border-slate-200 p-4 pr-14">
          <div className="flex flex-wrap items-center gap-2">
            {src && <span className={cn("rounded-full border px-2 py-0.5 text-xs font-semibold", SOURCE_STYLE[src].badge)}>{SOURCE_STYLE[src].label}</span>}
            <a href={doc.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline">
              Open original <ExternalLink className="size-3" aria-hidden />
            </a>
            <span className="text-xs text-slate-500">{ago(doc.fetched_at, now)}</span>
          </div>
          <SheetTitle className="text-balance text-base font-semibold leading-snug text-slate-900">{doc.title}</SheetTitle>
          <SheetDescription className="sr-only">The full official text with the proving sentence highlighted.</SheetDescription>
          {targets.length > 1 && at >= 0 && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Button variant="outline" size="icon-sm" onClick={() => go(-1)} disabled={at === 0} aria-label="Previous duty">
                <ChevronUp aria-hidden />
              </Button>
              <Button variant="outline" size="icon-sm" onClick={() => go(1)} disabled={at === targets.length - 1} aria-label="Next duty">
                <ChevronDown aria-hidden />
              </Button>
              <span>
                Duty {at + 1} of {targets.length} · <kbd className="rounded border border-slate-200 bg-slate-50 px-1">↑</kbd>{" "}
                <kbd className="rounded border border-slate-200 bg-slate-50 px-1">↓</kbd> to jump
              </span>
            </div>
          )}
        </SheetHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {notFound && active && (
            <div role="status" className="mb-4 rounded-xl border border-rejected/25 bg-rejected-soft/60 p-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-rejected">
                <SearchX className="size-4" aria-hidden /> Not found in the official text
              </p>
              <p className="mt-1.5 text-[13px] text-slate-700">
                {active.status === "rejected" ? `${friendlyReason(active.reason)}. ` : ""}The claimed quote:
              </p>
              <p className="mt-1 text-[13px] italic text-slate-600">“{active.quote}”</p>
            </div>
          )}

          {loading && (
            <div className="space-y-3" role="status" aria-label="Loading the document">
              <ShimmerSkeleton className="h-4 w-full" />
              <ShimmerSkeleton className="h-4 w-11/12" />
              <ShimmerSkeleton className="h-4 w-4/5" />
            </div>
          )}
          {error && <p role="alert" className="text-sm text-rejected">{error}</p>}

          <ol className="space-y-5">
            {paragraphs.map((p) => {
              const here = targets.filter((t) => t.paragraph === p.id);
              const isActive = at >= 0 && targets[at].paragraph === p.id;
              const segments = paragraphSegments(p.text, here.map((t) => ({ start: t.start, end: t.end, active: t.obligation === active })));
              return (
                <li
                  key={p.id}
                  ref={(el) => {
                    if (el) refs.current.set(p.id, el);
                    else refs.current.delete(p.id);
                  }}
                  className={cn("scroll-mt-4 border-l-2 pl-3", isActive ? "border-yellow-400" : "border-transparent")}
                >
                  <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{paragraphLabel(p.id)}</p>
                  <p className="mt-0.5 whitespace-pre-line text-[14px] leading-relaxed text-slate-800">
                    {segments.map((seg, i) =>
                      seg.mark === "active" ? (
                        <mark
                          key={`${activeKey}-${i}`}
                          className="rounded bg-yellow-200 px-0.5 text-slate-900 motion-safe:animate-pulse-mark [box-decoration-break:clone]"
                        >
                          {seg.text}
                        </mark>
                      ) : seg.mark === "other" ? (
                        <mark key={i} className="rounded bg-yellow-100 px-0.5 text-slate-900 [box-decoration-break:clone]">
                          {seg.text}
                        </mark>
                      ) : (
                        <span key={i}>{seg.text}</span>
                      ),
                    )}
                  </p>
                </li>
              );
            })}
          </ol>
        </div>
      </SheetContent>
    </Sheet>
  );
}
