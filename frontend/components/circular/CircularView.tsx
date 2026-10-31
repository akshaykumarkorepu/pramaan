"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FadeIn } from "@/components/motion/FadeIn";
import { ActionsBar } from "./ActionsBar";
import { AgentTimeline } from "./AgentTimeline";
import { AnalyzeError } from "./AnalyzeError";
import { ApplicabilityBanner } from "./ApplicabilityBanner";
import { CircularHeader } from "./CircularHeader";
import { ExplainerCard } from "./ExplainerCard";
import { ObligationCard } from "./ObligationCard";
import { VerifierBar } from "./VerifierBar";
import { icsUrl } from "@/lib/api";
import { splitObligations } from "@/lib/circular";
import { usePrefs } from "@/lib/usePrefs";
import { useAnalyze } from "@/lib/useAnalyze";
import type { Lang, ProfileId } from "@/lib/types";

export function CircularView({ url, profile, initialLang }: { url: string; profile: ProfileId; initialLang: Lang }) {
  const [lang, setLang] = useState<Lang>(initialLang);
  const [testOn, setTestOn] = useState(false);
  const { update } = usePrefs();
  const { steps, phase, result, error, totalMs, runId, start } = useAnalyze();
  const testRef = useRef<HTMLDivElement>(null);
  const running = phase === "running";

  // first load
  useEffect(() => {
    start(url, profile, initialLang, false);
  }, [start, url, profile, initialLang]);

  const changeLang = useCallback(
    (next: Lang) => {
      if (next === lang) return;
      setLang(next);
      setTestOn(false);
      update({ lang: next }); // so "All notices" keeps the language
      const u = new URL(window.location.href);
      u.searchParams.set("lang", next);
      window.history.replaceState(null, "", u);
      start(url, profile, next, false);
    },
    [lang, start, url, profile, update],
  );

  const runTest = useCallback(() => {
    setTestOn(true);
    start(url, profile, lang, true);
  }, [start, url, profile, lang]);

  // bring the fake claim into view once it arrives
  useEffect(() => {
    if (testOn && phase === "done") setTimeout(() => testRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 250);
  }, [testOn, phase]);

  const { real, test } = useMemo(() => splitObligations(result?.obligations ?? []), [result]);
  const hasDeadlines = real.some((o) => o.status !== "rejected" && !!o.deadline);
  const stale = running && !!result; // an older result is still on screen while a re-run streams
  const explainerLoading = running && (!result || result.explainer.lang !== lang || steps.explain.status !== "done");

  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 py-8 sm:px-6 sm:py-12">
      <FadeIn>
        <CircularHeader title={result?.doc.title ?? null} url={url} profile={profile} lang={lang} onLang={changeLang} />
      </FadeIn>

      <div className="mt-8 space-y-6">
        <AgentTimeline key={runId} steps={steps} phase={phase} totalMs={totalMs} />

        {phase === "error" && error && <AnalyzeError error={error} onRetry={() => start(url, profile, lang, testOn)} />}

        {result && (
          <div className={`space-y-6 transition-opacity ${stale ? "opacity-60" : ""}`} aria-busy={stale}>
            <FadeIn>
              <ApplicabilityBanner applies={result.applies} />
            </FadeIn>
            <FadeIn delay={0.05}>
              <VerifierBar counts={result.counts} />
            </FadeIn>

            <section aria-label="What you have to do" className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">What you have to do</h2>
              {real.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-8 text-center text-sm text-slate-500">
                  No verified duties were found in this notice. It may be informational only — open the original to read it.
                </div>
              ) : (
                real.map((o, i) => <ObligationCard key={`${o.quote}-${i}`} o={o} doc={result.doc} index={i} openProof={i === 0} />)
              )}
              {test && (
                <div ref={testRef} className="space-y-3 pt-2">
                  <p className="rounded-xl bg-slate-900 px-4 py-2.5 text-[13px] text-white">
                    We inserted a fabricated duty to show the checker catches it.
                  </p>
                  <ObligationCard key={`test-${runId}`} o={test} doc={result.doc} index={0} openProof />
                </div>
              )}
            </section>

            <ExplainerCard explainer={explainerLoading ? null : result.explainer} loading={explainerLoading} />

            <ActionsBar hasDeadlines={hasDeadlines} icsHref={icsUrl(url, profile)} onTest={runTest} testing={running} testOn={testOn} />
          </div>
        )}
      </div>
    </div>
  );
}
