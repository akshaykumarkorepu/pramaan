"use client";

import { motion, useReducedMotion } from "motion/react";
import { BadgeCheck, Pause, Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LangText } from "@/components/LangText";
import { ShimmerSkeleton } from "@/components/motion/ShimmerSkeleton";
import { useSpeech } from "@/lib/speech";
import type { Explainer } from "@/lib/types";

const LANG_NAME = { en: "English", te: "తెలుగు", hi: "हिंदी" } as const;

function Waveform({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  return (
    <span className="flex h-6 items-center gap-0.5" aria-hidden>
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <motion.span
          key={i}
          className="w-1 rounded-full bg-brand"
          style={{ height: active && !reduce ? undefined : 4 }}
          animate={active && !reduce ? { height: [5, 20, 8, 22, 6] } : { height: 4 }}
          transition={active && !reduce ? { duration: 0.9 + (i % 3) * 0.15, repeat: Infinity, ease: "easeInOut", delay: i * 0.08 } : { duration: 0.2 }}
        />
      ))}
    </span>
  );
}

export function ExplainerCard({ explainer, loading }: { explainer: Explainer | null; loading: boolean }) {
  const speech = useSpeech(explainer?.text ?? "", explainer?.lang ?? "en");
  const playing = speech.state === "playing";

  return (
    <section aria-label="Explanation in your language" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-soft sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">
          In your language{explainer && <span className="font-normal text-slate-400"> · <LangText lang={explainer.lang}>{LANG_NAME[explainer.lang]}</LangText></span>}
        </h2>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-verified/25 bg-verified-soft px-2.5 py-0.5 text-[11px] font-medium text-verified">
            <BadgeCheck className="size-3" aria-hidden /> Generated only from verified duties
          </span>
          {explainer?.source === "template" && (
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">basic summary</span>
          )}
        </div>
      </div>

      {loading || !explainer ? (
        <div className="mt-4 space-y-3" role="status" aria-label="Writing the explanation">
          <ShimmerSkeleton className="h-5 w-full" />
          <ShimmerSkeleton className="h-5 w-11/12" />
          <ShimmerSkeleton className="h-5 w-2/3" />
        </div>
      ) : (
        <>
          <LangText lang={explainer.lang} as="p" className="mt-4 whitespace-pre-line text-lg leading-8 text-slate-800 sm:text-xl sm:leading-9">
            {explainer.text}
          </LangText>
          <div className="mt-5 flex flex-wrap items-center gap-4">
            <Button
              onClick={speech.toggle}
              disabled={speech.state === "loading"}
              aria-pressed={playing}
              className="h-11 gap-2 bg-gradient-accent px-5 text-[15px] text-white shadow-md shadow-indigo-900/20"
            >
              {speech.state === "loading" ? <Loader2 className="animate-spin" aria-hidden /> : playing ? <Pause aria-hidden /> : <Play aria-hidden />}
              {playing ? "Pause" : speech.state === "paused" ? "Resume" : "Listen"}
            </Button>
            <Waveform active={playing} />
            {speech.error && <p role="alert" className="text-[13px] text-rejected">{speech.error}</p>}
          </div>
        </>
      )}
    </section>
  );
}
