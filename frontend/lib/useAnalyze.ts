"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyze } from "./api";
import type { ErrorEvent, Lang, ProfileId, ResultEvent, StepEvent } from "./types";

export const STEP_ORDER = ["fetch_document", "extract", "verify", "retry", "applicability", "explain"] as const;
export type StepName = (typeof STEP_ORDER)[number];

export interface StepState {
  status: "pending" | "running" | "done" | "failed";
  ms: number | null;
  detail: string | null;
  cached: boolean; // replayed from the server cache
  skipped: boolean; // e.g. self-correction had nothing to fix
  wait: { seconds: number; since: number } | null; // Groq rate-limit wait, with when we heard about it
}

export type Steps = Record<StepName, StepState>;
export type AnalyzePhase = "idle" | "running" | "done" | "error";

const blank = (): StepState => ({ status: "pending", ms: null, detail: null, cached: false, skipped: false, wait: null });
const initialSteps = (): Steps =>
  Object.fromEntries(STEP_ORDER.map((n) => [n, blank()])) as Steps;

const WAIT_RE = /waiting for AI capacity \(~(\d+)s\)/;
const isStepName = (n: string): n is StepName => (STEP_ORDER as readonly string[]).includes(n);

function applyStep(prev: Steps, e: StepEvent): Steps {
  if (!isStepName(e.name)) return prev;
  const cur = prev[e.name];
  const wait = e.detail ? WAIT_RE.exec(e.detail) : null;
  let next: StepState;
  if (e.status === "running" && wait) {
    next = { ...cur, status: "running", wait: { seconds: Number(wait[1]), since: Date.now() } };
  } else if (e.status === "running") {
    next = { ...cur, status: "running" };
  } else {
    const cached = !!e.detail && e.detail.includes("(cached)");
    const detail = e.detail ? e.detail.replace(" (cached)", "") : null;
    next = {
      status: e.status,
      ms: e.ms,
      detail,
      cached,
      skipped: e.status === "done" && !!detail && /skipped/.test(detail),
      wait: null,
    };
  }
  return { ...prev, [e.name]: next };
}

/**
 * Drives one /analyze stream. The previous result stays available while a re-run is in flight
 * (language change, verifier test), so the page never blanks; `runId` changes on every start.
 */
export function useAnalyze() {
  const [steps, setSteps] = useState<Steps>(initialSteps);
  const [phase, setPhase] = useState<AnalyzePhase>("idle");
  const [result, setResult] = useState<ResultEvent | null>(null);
  const [error, setError] = useState<ErrorEvent | null>(null);
  const [totalMs, setTotalMs] = useState<number | null>(null);
  const [runId, setRunId] = useState(0);
  const cancel = useRef<(() => void) | null>(null);

  useEffect(() => () => cancel.current?.(), []);

  const start = useCallback((url: string, profile: ProfileId, lang: Lang, verifierTest: boolean) => {
    cancel.current?.();
    const t0 = performance.now();
    setSteps(initialSteps());
    setPhase("running");
    setError(null);
    setTotalMs(null);
    setRunId((n) => n + 1);
    cancel.current = analyze(url, profile, lang, verifierTest, {
      onStep: (e) => setSteps((s) => applyStep(s, e)),
      onResult: (r) => {
        setResult(r);
        setTotalMs(performance.now() - t0);
        setPhase("done");
      },
      onError: (e) => {
        console.warn("[pramaan] analyze failed", e);
        setError(e);
        setPhase("error");
      },
    });
  }, []);

  return { steps, phase, result, error, totalMs, runId, start };
}
